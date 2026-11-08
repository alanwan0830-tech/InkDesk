"""Read-only full E1001 backup. Requires explicit authorization for temporary reset.

Run with: uv run --python 3.12 --with esptool==5.1.0 integrations/backup-firmware.py
The dashboard service must be stopped first. Never writes flash or eFuses.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import esptool
import argparse

ROOT = Path(__file__).resolve().parents[1]
SIZE, BLOCK = 32 * 1024 * 1024, 64 * 1024


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', type=Path, help='Retry a prior backup directory; every block is rechecked')
    args = parser.parse_args()
    os.umask(0o077)
    port = '/dev/cu.usbserial-210'
    if subprocess.run(['lsof', port], capture_output=True).returncode == 0:
        raise SystemExit('Serial port is occupied; stop its owner first.')
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')
    target = args.resume or ROOT / 'runtime/firmware-backups' / stamp
    target = target.resolve()
    if not target.is_relative_to(ROOT / 'runtime/firmware-backups'):
        raise SystemExit('Backup must stay in the private runtime directory')
    target.mkdir(parents=True, mode=0o700, exist_ok=bool(args.resume))
    if (target / 'stock-full.bin').exists():
        raise SystemExit('Verified backup already exists; never overwrite it')
    esp = None
    try:
        esp = esptool.detect_chip(port, baud=115200)
        if esp.CHIP_NAME != 'ESP32-S3':
            raise RuntimeError('Unexpected chip')
        if esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise RuntimeError('Security enabled; raw restore cannot be assumed safe')
        esp = esp.run_stub()
        # JEDEC capacity byte must report 2**25 bytes, not merely a board default.
        if (esp.flash_id() >> 16) & 0xff != 25:
            raise RuntimeError('Unexpected flash capacity')
        esp.flash_set_parameters(SIZE)
        # High-speed probes passed, but a longer 230400 read was corrupt.
        # Keep 115200 for a complete verified backup.
        blank = b'\xff' * BLOCK
        blank_md5 = hashlib.md5(blank).hexdigest()
        records = []
        partial = target / 'stock-full.bin.partial'
        with partial.open('r+b' if partial.exists() else 'x+b') as out:
            for offset in range(0, SIZE, BLOCK):
                expected = esp.flash_md5sum(offset, BLOCK)
                erased = expected == blank_md5
                out.seek(offset)
                cached = out.read(BLOCK)
                if len(cached) == BLOCK and hashlib.md5(cached).hexdigest() == expected:
                    data = cached
                else:
                    data = blank if erased else esp.read_flash(offset, BLOCK)
                if len(data) != BLOCK or hashlib.md5(data).hexdigest() != expected:
                    raise RuntimeError(f'Block verification failed at {offset:#x}')
                out.seek(offset)
                out.write(data)
                records.append({'offset': offset, 'md5': expected, 'erased': erased})
                if len(records) % 16 == 0:
                    out.flush()
                    print(f'Verified {offset + BLOCK}/{SIZE} bytes', flush=True)
            out.flush()
            os.fsync(out.fileno())
        data = partial.read_bytes()
        if len(data) != SIZE or hashlib.md5(data).hexdigest() != esp.flash_md5sum(0, SIZE):
            raise RuntimeError('Whole-device verification failed')
        final = partial.with_suffix('')
        partial.rename(final)
        manifest = {'created_at': stamp, 'chip': 'ESP32-S3', 'size': SIZE,
                    'sha256': hashlib.sha256(data).hexdigest(),
                    'device_md5_verified': True, 'flash_encryption': False,
                    'secure_boot': False, 'method': 'read non-erased blocks; device MD5 for every block and entire image',
                    'restore_tested': False, 'blocks': records}
        (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(f'BACKUP VERIFIED: {final}', flush=True)
    finally:
        if esp is not None:
            try:
                esp.hard_reset()
            finally:
                esp._port.close()


if __name__ == '__main__':
    main()
