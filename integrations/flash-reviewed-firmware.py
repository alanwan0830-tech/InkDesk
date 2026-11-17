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

# Partition table from the supported stock E1001 layout, excluding NVS.
PARTITION_SHA256 = '10f61aeffc56289052d36cd0a6da8845370ab63515141c83ec59d82c59525cb0'
APP0_OFFSET, APP0_SIZE, FLASH_SIZE = 0x90000, 0xc00000, 32 * 1024 * 1024
# Factory OTA record: valid sequence 1 selects ota_0. Other records require review.
SUPPORTED_OTA = bytes.fromhex('01000000ffffffffffffffffffffffffffffffffffffffff020000009a984347')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='Serial device path')
    parser.add_argument('--backup', required=True, type=Path, help='Verified backup directory')
    parser.add_argument('--image', required=True, type=Path, help='Locally built app image')
    parser.add_argument('--sha256', required=True, help='Expected SHA-256 of the app image')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--baud',type=int,choices=(57600,115200),default=115200)
    args=parser.parse_args()
    os.umask(0o077)
    (ROOT/'runtime').mkdir(mode=0o700,exist_ok=True)
    lock=(ROOT/'runtime/firmware-install.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    port=args.port
    if subprocess.run(['lsof',port],capture_output=True).returncode==0:raise SystemExit('Serial port occupied')
    cfg=json.loads((ROOT/'config.json').read_text())
    if cfg['device']['enabled']:raise SystemExit('Stop cloud push before flashing')
    stock=(args.backup/'stock-full.bin').read_bytes()
    backup=json.loads((args.backup/'manifest.json').read_text())
    if (len(stock)!=FLASH_SIZE or not backup.get('device_md5_verified')
            or hashlib.sha256(stock).hexdigest()!=backup['sha256']):
        raise SystemExit('Original backup verification failed')
    if (hashlib.sha256(stock[0x8000:0x9000]).hexdigest()!=PARTITION_SHA256
            or stock[0x86000:0x86020]!=SUPPORTED_OTA
            or stock[0x86020:0x88000]!=b'\xff'*(0x88000-0x86020)):
        raise SystemExit('Unsupported partition table or OTA selection')
    binary=args.image.read_bytes()
    digest=hashlib.sha256(binary).hexdigest()
    if digest!=args.sha256 or not 24<=len(binary)<=APP0_SIZE or binary[:1]!=b'\xe9' or binary[12:14]!=b'\x09\x00':
        raise SystemExit('Expected an ESP32-S3 app image with the supplied SHA-256')
    stamp=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')
    out=ROOT/'runtime/firmware-installs'/stamp;out.mkdir(parents=True,mode=0o700)
    result={'created_at':stamp,'app_offset':'0x90000','sha256':digest,'write_verified':False,'protected_regions_verified':False}
    esp=None;write_started=False
    try:
        esp=esptool.detect_chip(port,baud=args.baud)
        if esp.CHIP_NAME!='ESP32-S3' or esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise RuntimeError('Unexpected chip or security state')
        esp=esp.run_stub()
        if (esp.flash_id()>>16)&255!=25:raise RuntimeError('Unexpected flash capacity')
        esp.flash_set_parameters(33554432)
        if esp.flash_md5sum(0,FLASH_SIZE)!=hashlib.md5(stock).hexdigest():
            raise RuntimeError('Device flash differs from the verified backup; no write authorized by preflight')
        if not args.execute:
            print('Preflight passed; no flash written. Repeat with --execute only after reviewing the backup and target.')
            return
        end=APP0_OFFSET+APP0_SIZE
        ranges=[(0,APP0_OFFSET),(end,FLASH_SIZE-end)]
        expected=[esp.flash_md5sum(offset,size) for offset,size in ranges]
        print('Preflight passed. Writing only app0 at 0x90000.',flush=True)
        write_started=True
        esptool.cmds.write_flash(esp,[(APP0_OFFSET,binary)],compress=True)
        result['write_verified']=esp.flash_md5sum(APP0_OFFSET,len(binary))==hashlib.md5(binary).hexdigest()
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
