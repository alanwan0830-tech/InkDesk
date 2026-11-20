"""Opt-in first-screen image feed for Paper firmware. No cloud mutations."""
from __future__ import annotations
import argparse
from datetime import datetime
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import logging
from pathlib import Path
import socket
import struct
import time
import zlib
from zoneinfo import ZoneInfo

import cairosvg
from PIL import Image, ImageDraw
from .common import RUNTIME
from .render import render_svg

LOG = logging.getLogger(__name__)
WIDTH, HEIGHT = 800, 480
HEADER = struct.Struct('<4sHHIIII')
PACKET_SIZE = HEADER.size + WIDTH * HEIGHT // 8
FRAME_BLOCK_SIZE = 1024
FRAME_BLOCK_INTERVAL = 0.01


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
    from .vehicle import VehicleFeed, vehicle_image
    feed = VehicleFeed()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def log_message(self, *args): pass

        def send_response(self, code, message=None):
            super().send_response(code, message)
            if self.path == '/frame':
                LOG.info('Frame request from %s: HTTP %d', self.client_address[0], code)

        def do_GET(self):
            if self.path not in ('/frame', '/vehicle'):
                self.send_error(404)
                return
            if not hmac.compare_digest(self.headers.get('Authorization', '').encode(), ('Bearer ' + token).encode()):
                self.send_error(401)
                return
            try:
                if self.path == '/vehicle':
                    state, parking, ok = feed.snapshot()
                    if not state and not ok:
                        raise ValueError("No usable vehicle snapshot")
                    pixels = vehicle_image(state, parking, ok).tobytes()
                    now = int(time.time())
                    prefix = struct.pack('<4sHHIII', b'VEH1', WIDTH, HEIGHT, now, now, int(not ok))
                    body = prefix + struct.pack('<I', zlib.crc32(pixels, zlib.crc32(prefix))) + pixels
                else:
                    # Read data and mtime from the same open file across atomic replacement.
                    import os
                    with snapshot_path.open() as file:
                        snapshot = json.load(file)
                        stamp = int(os.fstat(file.fileno()).st_mtime)
                    body = frame_packet(snapshot, int(time.time()), stamp)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                self.send_error(503, 'No usable frame; retain cached image')
                return
            _, _, _, _, source_at, offline, _ = HEADER.unpack_from(body)
            compressed = False
            if self.headers.get('Accept-Encoding', '').strip().lower() == 'deflate':
                encoded = zlib.compress(body)
                if len(encoded) < len(body):
                    body = encoded
                    compressed = True
            try:
                # Pace sub-MTU writes across the local Wi-Fi link. A single
                # 48 KB write has stalled after the device received the headers.
                self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Vary', 'Accept-Encoding')
                if compressed:
                    self.send_header('Content-Encoding', 'deflate')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                for offset in range(0, len(body), FRAME_BLOCK_SIZE):
                    if offset:
                        time.sleep(FRAME_BLOCK_INTERVAL)
                    self.wfile.write(body[offset:offset + FRAME_BLOCK_SIZE])
            except OSError as exc:
                LOG.warning('Frame write to %s failed: %s', self.client_address[0], type(exc).__name__)
                return
            source_time = datetime.fromtimestamp(source_at, ZoneInfo('Asia/Shanghai'))
            LOG.info('Frame written to %s: %d bytes, DATA %s, OFFLINE=%d',
                     self.client_address[0], len(body), source_time.strftime('%m/%d %H:%M:%S'), offline)
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
