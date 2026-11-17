"""Opt-in first-screen image feed for Paper firmware. No cloud mutations."""
from __future__ import annotations
import argparse
from datetime import datetime
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import struct
import time
import zlib
from zoneinfo import ZoneInfo

import cairosvg
from PIL import Image, ImageDraw
from .common import RUNTIME
from .render import render_svg

WIDTH, HEIGHT = 800, 480
HEADER = struct.Struct('<4sHHIIII')
PACKET_SIZE = HEADER.size + WIDTH * HEIGHT // 8


def frame_packet(snapshot: dict, now: int, source_at: int) -> bytes:
    if not isinstance(snapshot, dict):
        raise ValueError('Snapshot must be an object')
    if not 1704067200 <= now < 2145916800 or not 0 < source_at <= now + 5:
        raise ValueError('Invalid timestamps')
    dt = datetime.fromtimestamp(now, ZoneInfo('Asia/Shanghai'))
    svg = render_svg(snapshot, dt).replace('E1001 / LIVE', 'E1001 / LOCAL')
    png = cairosvg.svg2png(bytestring=svg.encode())
    im = Image.open(io.BytesIO(png)).convert('L').point(lambda v: 255 if v >= 150 else 0).convert('1')
    draw = ImageDraw.Draw(im)
    # Device owns clock/date and data-age footer, including during network failure.
    draw.rectangle((296,80,519,207), fill=1)
    draw.rectangle((16,450,443,479), fill=1)
    pixels = im.tobytes()  # 1 = white, MSB first; matches Seeed_GFX 1-bit sprite.
    quotes = snapshot.get('quotes') or []
    offline = len(quotes)!=6 or any(not q.get('ok') for q in quotes)
    offline |= any(not (snapshot.get(k) or {}).get('ok') for k in ('weather','usage'))
    prefix = struct.pack('<4sHHIII', b'PPR2', WIDTH, HEIGHT, now, source_at, int(offline))
    crc = zlib.crc32(pixels, zlib.crc32(prefix))
    return prefix + struct.pack('<I', crc) + pixels


def make_handler(token: str, snapshot_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def log_message(self, *args): pass

        def do_GET(self):
            if self.path != '/frame':
                self.send_error(404)
                return
            if not hmac.compare_digest(self.headers.get('Authorization', '').encode(), ('Bearer ' + token).encode()):
                self.send_error(401)
                return
            try:
                # Read data and mtime from the same open file across atomic replacement.
                import os
                with snapshot_path.open() as file:
                    snapshot = json.load(file)
                    stamp = int(os.fstat(file.fileno()).st_mtime)
                body = frame_packet(snapshot, int(time.time()), stamp)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                self.send_error(503, 'No usable frame; retain cached image')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return Handler


def create_server(host: str, port: int, token_file: Path, snapshot_path: Path):
    token = token_file.read_text().strip()
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError('Use a private token of at least 32 ASCII characters without whitespace')
    return ThreadingHTTPServer((host, port), make_handler(token, snapshot_path))


def main():
    parser = argparse.ArgumentParser(description='Optional local feed for Paper firmware')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--token-file', type=Path, required=True)
    args = parser.parse_args()
    create_server(args.host, args.port, args.token_file, RUNTIME/'snapshot.json').serve_forever()


if __name__ == '__main__':
    main()
