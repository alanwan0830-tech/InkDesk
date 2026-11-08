import hashlib
import importlib.util
from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def backup_module(tmp_path, monkeypatch):
    stub = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, 'esptool', stub)
    spec = importlib.util.spec_from_file_location('backup_firmware', Path(__file__).parents[1] / 'integrations/backup-firmware.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'SIZE', 12)
    monkeypatch.setattr(module, 'BLOCK', 4)
    monkeypatch.setattr(module.os, 'umask', lambda _: None)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: types.SimpleNamespace(returncode=1))
    monkeypatch.setattr(sys, 'argv', ['backup-firmware.py'])
    return module


class Device:
    CHIP_NAME = 'ESP32-S3'
    data = b'abcd' + b'\xff' * 4 + b'wxyz'

    def __init__(self, corrupt=False, bad_final=False):
        self.reads = []
        self.reset = self.closed = False
        self.corrupt, self.bad_final = corrupt, bad_final
        self._port = types.SimpleNamespace(close=lambda: setattr(self, 'closed', True))

    def get_secure_boot_enabled(self): return False
    def get_flash_encryption_enabled(self): return False
    def run_stub(self): return self
    def flash_id(self): return 25 << 16
    def flash_set_parameters(self, size): pass
    def hard_reset(self): self.reset = True

    def flash_md5sum(self, offset, length):
        if self.bad_final and length == len(self.data): return '0' * 32
        return hashlib.md5(self.data[offset:offset + length]).hexdigest()

    def read_flash(self, offset, length):
        self.reads.append(offset)
        return b'BAD!' if self.corrupt else self.data[offset:offset + length]


def test_complete_image_includes_verified_erased_blocks(backup_module):
    m = backup_module
    device = Device()
    m.esptool.detect_chip = lambda *a, **kw: device
    m.main()
    image = next(m.ROOT.rglob('stock-full.bin'))
    assert image.read_bytes() == device.data
    assert device.reads == [0, 8]
    assert image.with_name('manifest.json').exists()
    assert device.reset and device.closed


@pytest.mark.parametrize('options', [{'corrupt': True}, {'bad_final': True}])
def test_failed_verification_never_produces_verified_backup(backup_module, options):
    m = backup_module
    device = Device(**options)
    m.esptool.detect_chip = lambda *a, **kw: device
    with pytest.raises(RuntimeError, match='verification failed'):
        m.main()
    assert not list(m.ROOT.rglob('stock-full.bin'))
    assert not list(m.ROOT.rglob('manifest.json'))
    assert device.reset and device.closed


def test_resume_rechecks_cached_blocks(backup_module, monkeypatch):
    m = backup_module
    target = m.ROOT / 'runtime/firmware-backups/retry'
    target.mkdir(parents=True)
    (target / 'stock-full.bin.partial').write_bytes(b'OLD!' + b'\xff' * 4 + b'wxyz')
    monkeypatch.setattr(sys, 'argv', ['backup-firmware.py', '--resume', str(target)])
    device = Device()
    m.esptool.detect_chip = lambda *a, **kw: device
    m.main()
    assert (target / 'stock-full.bin').read_bytes() == device.data
    assert device.reads == [0]


@pytest.mark.parametrize('check,value', [('get_secure_boot_enabled', True), ('get_flash_encryption_enabled', True), ('flash_id', 24 << 16)])
def test_unexpected_device_or_security_stops_before_read(backup_module, check, value):
    m = backup_module
    device = Device()
    setattr(device, check, lambda: value)
    m.esptool.detect_chip = lambda *a, **kw: device
    with pytest.raises(RuntimeError):
        m.main()
    assert device.reads == []
    assert device.reset and device.closed
    assert not list(m.ROOT.rglob('stock-full.bin'))
