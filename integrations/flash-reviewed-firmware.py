"""Explicit app-only installation after review. Never erases the whole flash."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import esptool

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from paper.common import atomic_json

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--baud',type=int,choices=(57600,115200),default=115200)
    args=parser.parse_args()
    if not args.execute:raise SystemExit('Requires an explicitly authorized --execute operation')
    os.umask(0o077)
    lock=(ROOT/'runtime/firmware-install.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    port='/dev/cu.usbserial-210'
    if subprocess.run(['lsof',port],capture_output=True).returncode==0:raise SystemExit('Serial port occupied')
    cfg=json.loads((ROOT/'config.json').read_text())
    if cfg['device']['enabled']:raise SystemExit('Stop cloud push before flashing')
    backup_dir=ROOT/'runtime/firmware-backups/20261108-183714'
    stock=(backup_dir/'stock-full.bin').read_bytes()
    backup=json.loads((backup_dir/'manifest.json').read_text())
    if len(stock)!=33554432 or hashlib.sha256(stock).hexdigest()!=backup['sha256']:
        raise SystemExit('Original backup verification failed')
    build=ROOT/'runtime/firmware-build'
    manifest=json.loads((build/'release.json').read_text())
    binary=(build/manifest['artifact']).read_bytes()
    if not manifest['reviewed'] or not manifest['network_configured']:
        raise SystemExit('Not a reviewed configured release')
    if hashlib.sha256(binary).hexdigest()!=manifest['sha256'] or not 0<len(binary)<0xc00000 or binary[0]!=0xe9:
        raise SystemExit('Release verification failed')
    stamp=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')
    out=ROOT/'runtime/firmware-installs'/stamp;out.mkdir(parents=True,mode=0o700)
    result={'created_at':stamp,'app_offset':'0x90000','sha256':manifest['sha256'],'write_verified':False,'protected_regions_verified':False}
    esp=None;write_started=False
    try:
        esp=esptool.detect_chip(port,baud=args.baud)
        if esp.CHIP_NAME!='ESP32-S3' or esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise RuntimeError('Unexpected chip or security state')
        esp=esp.run_stub()
        if (esp.flash_id()>>16)&255!=25:raise RuntimeError('Unexpected flash capacity')
        esp.flash_set_parameters(33554432)
        prefix=esp.read_flash(0,0x90000)
        (out/'preinstall-boot-nvs.bin').write_bytes(prefix)
        # Current bootloader, partitions and OTA selection must match reviewed stock.
        if prefix[:0x9000]!=stock[:0x9000] or prefix[0x86000:0x89000]!=stock[0x86000:0x89000]:
            raise RuntimeError('Boot/partition/OTA metadata changed; review again')
        ranges=[(0,0x90000),(0x1890000,0x600000)]
        expected=[esp.flash_md5sum(offset,size) for offset,size in ranges]
        print('Preflight passed. Writing only app0 at 0x90000.',flush=True)
        write_started=True
        esptool.cmds.write_flash(esp,[(0x90000,binary)],compress=True)
        result['write_verified']=esp.flash_md5sum(0x90000,len(binary))==hashlib.md5(binary).hexdigest()
        result['protected_regions_verified']=all(esp.flash_md5sum(offset,size)==value for (offset,size),value in zip(ranges,expected))
        if not result['write_verified'] or not result['protected_regions_verified']:
            raise RuntimeError('Post-write verification failed')
        print('App verified; boot/NVS/OTA and image partition unchanged.',flush=True)
    finally:
        atomic_json(out/'result.json',result)
        if esp:
            try:
                if not write_started or (result['write_verified'] and result['protected_regions_verified']):esp.hard_reset()
                else:print('Write not verified; leaving download mode for recovery.',flush=True)
            finally:esp._port.close()

if __name__=='__main__':main()
