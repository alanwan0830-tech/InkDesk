import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import pytest

@pytest.mark.parametrize('failure', [None,'metadata','write','protected'])
def test_app_only_installer_verification_and_failure_paths(tmp_path,monkeypatch,failure):
    stub=types.SimpleNamespace()
    monkeypatch.setitem(sys.modules,'esptool',stub)
    spec=importlib.util.spec_from_file_location('installer',Path(__file__).parents[1]/'integrations/flash-reviewed-firmware.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m.os,'umask',lambda _:None)
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:types.SimpleNamespace(returncode=1))
    monkeypatch.setattr(sys,'argv',['installer','--execute'])
    stock=b'\xff'*33554432
    base=tmp_path/'runtime/firmware-backups/20261108-183714';base.mkdir(parents=True)
    (base/'stock-full.bin').write_bytes(stock)
    (base/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(stock).hexdigest()}))
    (tmp_path/'config.json').write_text('{"device":{"enabled":false}}')
    build=tmp_path/'runtime/firmware-build';build.mkdir()
    binary=b'\xe9test app'
    (build/'app.bin').write_bytes(binary)
    (build/'release.json').write_text(json.dumps({'artifact':'app.bin','reviewed':True,'network_configured':True,'sha256':hashlib.sha256(binary).hexdigest()}))
    class Device:
        CHIP_NAME='ESP32-S3'
        reset=False;closed=False;written=False
        def get_secure_boot_enabled(self):return False
        def get_flash_encryption_enabled(self):return False
        def run_stub(self):return self
        def flash_id(self):return 25<<16
        def flash_set_parameters(self,size):assert size==33554432
        def read_flash(self,offset,size):return (b'X'+stock[1:size]) if failure=='metadata' else stock[:size]
        def flash_md5sum(self,offset,size):
            if offset==0x90000:return hashlib.md5(binary).hexdigest()
            if failure=='protected' and self.written:return 'changed'
            return 'original'
        def hard_reset(self):self.reset=True
    device=Device();device._port=types.SimpleNamespace(close=lambda:setattr(device,'closed',True))
    stub.detect_chip=lambda *a,**k:device
    def write_flash(esp,items,compress):
        assert items==[(0x90000,binary)] and compress
        device.written=True
        if failure=='write':raise RuntimeError('write failed')
    stub.cmds=types.SimpleNamespace(write_flash=write_flash)
    if failure:
        with pytest.raises(RuntimeError):m.main()
    else:m.main()
    assert device.closed
    assert device.written==(failure!='metadata')
    assert device.reset==(failure in [None,'metadata'])
