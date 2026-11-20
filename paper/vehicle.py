"""Read-only EV Mate data and the vehicle page for InkDesk."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, RUNTIME, atomic_json, read_json

LOG = logging.getLogger(__name__)
ART = ROOT / 'assets/vehicle-alpine.png'
PARKING_QUERY = ('只读查询最近保存的停车记录，只返回 JSON 对象，字段 place 为场所名称，'
                 'area 为楼层和区域，time 为记录的 HH:mm。缺失用 null，禁止估算、'
                 '不含经纬度、照片，不执行或确认任何车控。')


def request_data(cfg, route, payload=None):
    base = cfg['base_url'].rstrip('/')
    url = urlsplit(base)
    if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise ValueError('Invalid transport')
    response = requests.request('POST' if payload else 'GET', base+'/api/openapi/v1'+route,
                                headers={'Authorization': 'Bearer '+cfg['api_key']}, json=payload,
                                timeout=(3, 65 if payload else 6), allow_redirects=False)
    if response.status_code in (502, 503, 504):
        response.raise_for_status()
    if response.status_code != 200:
        raise ValueError('Vehicle service unavailable')
    result = response.json()
    if result.get('code') != 200:
        raise ValueError('Vehicle service rejected request')
    return result['data']


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def short(v, limit=100):
    return ' '.join(v.split())[:limit] if isinstance(v, str) else ''


class VehicleFeed:
    def __init__(self, config=None, cache=RUNTIME/'cache'):
        self.config = config or RUNTIME/'vehicle-config.json'
        self.cache = cache
        self.lock = threading.Lock()
        self.parking_lock = threading.Lock()

    def parking_worker(self, cfg, path, attempt):
        try:
            data = request_data(cfg, '/assistant/completions', {
                'carId': int(cfg['vehicle_id']), 'content': PARKING_QUERY, 'stream': False})
            reply = data['content'].strip()
            if reply.startswith('```'):
                reply = '\n'.join(reply.splitlines()[1:-1])
            parsed = json.loads(reply)
            record = {k: short(parsed.get(k)) for k in ('place', 'area', 'time')}
            if not record['place'] and not record['area']:
                return
            atomic_json(path, {'attempt': attempt, 'record': record})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, requests.RequestException):
            pass
        finally:
            self.parking_lock.release()

    def snapshot(self):
        with self.lock:
            cfg = read_json(self.config, {})
            identity = hashlib.sha256(json.dumps([cfg.get(k) for k in ('base_url','vehicle_id','api_key')]).encode()).hexdigest()[:24]
            state_path = self.cache / ('vehicle-'+identity+'.json')
            parking_path = self.cache / ('parking-'+identity+'.json')
            state = read_json(state_path, {})
            parking = read_json(parking_path, {})
            stage = 'config'
            try:
                car = int(cfg['vehicle_id'])
                stage = 'status'
                route = f'/vehicles/status/{car}'
                try:
                    data = request_data(cfg, route)
                except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                    LOG.warning('Vehicle status retry: %s', type(exc).__name__)
                    data = request_data(cfg, route)
                stage = 'fields'
                if data.get('vehicleId') != car or not number(data.get('remainingRange')) or not number(data.get('batteryLevel')) or data['batteryLevel'] > 100:
                    raise ValueError('Invalid vehicle snapshot')
                stamp = datetime.strptime(data['observedAt'], '%Y-%m-%d %H:%M:%S')
                model = state.get('model', '')
                if not model:
                    try:
                        vehicles = request_data(cfg, '/vehicles')
                        model = next((short(v.get('carModel')) for v in vehicles if v.get('id') == car), '')
                    except (ValueError, TypeError, KeyError, AttributeError, requests.RequestException):
                        model = ''
                state = {k: data.get(k) for k in ('vehicleName','remainingRange','batteryLevel','totalMileage','charging','sentryModeEnabled','parkingSpotNumber')}
                state.update(model=model, observed=stamp.isoformat(' '))
                stage = 'cache'
                atomic_json(state_path, state)
                now = time.time()
                if now-parking.get('attempt', 0) >= 900 and self.parking_lock.acquire(False):
                    try:
                        atomic_json(parking_path, {**parking, 'attempt': now})
                        threading.Thread(target=self.parking_worker, args=(cfg,parking_path,now), daemon=True).start()
                    except Exception:
                        self.parking_lock.release()
                        raise
                ok = True
            except (OSError, ValueError, TypeError, AttributeError, KeyError, requests.RequestException) as exc:
                LOG.warning('Vehicle snapshot failed: stage=%s error=%s', stage, type(exc).__name__)
                ok = False
            return state, parking.get('record', {}), ok


@lru_cache(maxsize=24)
def font(size, bold=False):
    roots = Path('/System/Library/AssetsV2')
    file = next(roots.glob('com_apple_MobileAsset_Font*/*/AssetData/PingFang.ttc'), None)
    if file:
        return ImageFont.truetype(str(file), size, index=11 if bold else 7)
    return ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', size)


def vehicle_image(state, parking, ok):
    page = Image.new('L', (800,480), 255)
    with Image.open(ART) as art:
        page.paste(art,((page.width-art.width)//2,135))
    draw = ImageDraw.Draw(page)
    def label(x,center,value,size,limit,bold=False,right=False):
        face = font(size,bold)
        value = str(value)
        if face.getlength(value)>limit:
            while value and face.getlength(value+'...')>limit:
                value=value[:-1]
            value += '...'
        width = face.getlength(value)
        cursor = x-width if right else x
        # Optical alignment: CJK glyphs and Latin capitals have different ink heights.
        for run in re.findall(r'[A-Za-z0-9.,:%]+|[^A-Za-z0-9.,:%\s]+|\s+',value):
            if not run.isspace():
                sample = 'H0' if run[0].isascii() else '国'
                _,top,_,bottom = face.getbbox(sample,anchor='ls')
                draw.text((round(cursor),round(center-(top+bottom)/2)),run,font=face,fill=0,anchor='ls')
            cursor += face.getlength(run)
        return round(width)
    name_width = label(36,38,short(state.get('vehicleName')) or '车辆',20,125,True)
    label(50+name_width,38,state.get('model',''),20,240,True)
    stamp = state.get('observed','')
    timestamp = stamp[11:16] if ok else stamp[5:16]
    label(764,38,('更新时间 ' if ok else '更新失败 · 上次 ') + timestamp if stamp else '暂未获取车况',20,360,True,right=True)
    value = state.get('remainingRange')
    label(35,83,f'{value:.0f} km' if number(value) else '-- km',36,230,True)
    level = state.get('batteryLevel')
    draw.rounded_rectangle((36,108,161,115),radius=3,outline=0)
    if number(level) and level>0:
        draw.rectangle((38,110,38+round(120*level/100),113),fill=0)
    if state.get('charging') is True:
        draw.rounded_rectangle((36,124,95,147),radius=4,fill=0)
        draw.text((66,135),'充电中',font=font(14,True),fill=255,anchor='mm')
    spot = short(state.get('parkingSpotNumber'))
    sentry = state.get('sentryModeEnabled')
    mileage = state.get('totalMileage')
    rows = [(36,'最近停车'+(' · '+parking['time'] if parking.get('time') else ''),parking.get('place') or '未获取',258),
            (323,'车位',spot or parking.get('area') or '未获取',127),
            (460,'哨兵','开启' if sentry is True else '关闭' if sentry is False else '未知',99),
            (579,'总里程',f'{mileage:,.1f} km' if number(mileage) else '-- km',186)]
    for x,title,val,width in rows:
        label(x,393,title,18,width)
        label(x,433,val,22,width,True)
    return page.point(lambda v: 255 if v>145 else 0).convert('1',dither=Image.Dither.NONE)
