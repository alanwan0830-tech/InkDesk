import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import pytest

@pytest.mark.parametrize('failure', [None,'preflight','metadata','write','protected'])
@pytest.mark.parametrize('baud', [57600,115200])
def test_app_only_installer_verification_and_failure_paths(tmp_path,monkeypatch,failure,baud):
    stub=types.SimpleNamespace()
    monkeypatch.setitem(sys.modules,'esptool',stub)
    spec=importlib.util.spec_from_file_location('installer',Path(__file__).parents[1]/'integrations/flash-reviewed-firmware.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m.os,'umask',lambda _:None)
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:types.SimpleNamespace(returncode=1))
    stock=bytearray(b'\xff'*m.FLASH_SIZE)
    stock[0x86000:0x86020]=m.SUPPORTED_OTA
    monkeypatch.setattr(m,'PARTITION_SHA256',hashlib.sha256(stock[0x8000:0x9000]).hexdigest())
    base=tmp_path/'runtime/firmware-backups/fixture';base.mkdir(parents=True)
    (base/'stock-full.bin').write_bytes(stock)
    (base/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(stock).hexdigest(),'device_md5_verified':True}))
    (tmp_path/'config.json').write_text('{"device":{"enabled":false}}')
    binary=b'\xe9'+bytes(11)+b'\x09\x00'+bytes(10)
    image=tmp_path/'app.bin';image.write_bytes(binary)
    args=['installer','--port','/dev/mock','--backup',str(base),'--image',str(image),
          '--sha256',hashlib.sha256(binary).hexdigest(),'--baud',str(baud)]
    if failure!='preflight':args.append('--execute')
    monkeypatch.setattr(sys,'argv',args)
    class Device:
        CHIP_NAME='ESP32-S3'
        reset=False;closed=False;written=False
        def get_secure_boot_enabled(self):return False
        def get_flash_encryption_enabled(self):return False
        def run_stub(self):return self
        def flash_id(self):return 25<<16
        def flash_set_parameters(self,size):assert size==33554432
        def flash_md5sum(self,offset,size):
            if offset==0 and size==m.FLASH_SIZE:return 'changed' if failure=='metadata' else hashlib.md5(stock).hexdigest()
            if offset==m.APP0_OFFSET:return hashlib.md5(binary).hexdigest()
            if failure=='protected' and self.written:return 'changed'
            return 'original'
        def hard_reset(self):self.reset=True
    device=Device();device._port=types.SimpleNamespace(close=lambda:setattr(device,'closed',True))
    def detect_chip(port,**kwargs):
        assert kwargs['baud']==baud
        return device
    stub.detect_chip=detect_chip
    def write_flash(esp,items,compress):
        assert items==[(0x90000,binary)] and compress
        device.written=True
        if failure=='write':raise RuntimeError('write failed')
    stub.cmds=types.SimpleNamespace(write_flash=write_flash)
    if failure in ('metadata','write','protected'):
        with pytest.raises(RuntimeError):m.main()
    else:m.main()
    assert device.closed
    assert device.written==(failure not in ('metadata','preflight'))
    assert device.reset==(failure in [None,'metadata','preflight'])
