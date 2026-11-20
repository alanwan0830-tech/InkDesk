import json
import threading
import zlib
import struct
import http.client
from http.server import ThreadingHTTPServer

from paper import vehicle
from paper.firmware_bridge import make_handler
from paper.common import atomic_json


def test_snapshots_cache_late_parking_and_failures(tmp_path, monkeypatch):
    config = tmp_path/'cfg'
    atomic_json(config, {'api_key':'test', 'base_url':'https://example.invalid','vehicle_id':1})
    feed = vehicle.VehicleFeed(config,tmp_path)
    invoked, release = threading.Event(), threading.Event()
    calls = []
    payload = {'vehicleId':1, 'batteryLevel':0, 'remainingRange':0, 'charging':False,
               'observedAt':'2025-04-12 16:40:00', 'vehicleName':'示例车辆'}
    def api(cfg, route, body=None):
        calls.append(route)
        if body:
            invoked.set()
            assert release.wait(5)
            return {'content':json.dumps({'place':'停车场','area':'B2 F 区','time':'15:12'})}
        if route == '/vehicles':
            return [{'id':1,'carModel':'Demo EV'}]
        return payload
    monkeypatch.setattr(vehicle, 'request_data',api)
    state, parking, ok = feed.snapshot()
    assert ok and state['batteryLevel']==0 and not parking
    assert invoked.wait(2)
    assert feed.snapshot()[1]=={}
    release.set()
    assert feed.parking_lock.acquire(timeout=2)
    feed.parking_lock.release()
    assert feed.snapshot()[1]['area']=='B2 F 区'
    assert calls.count('/assistant/completions')==1
    payload['batteryLevel']=200
    previous,_,ok = feed.snapshot()
    assert not ok and previous==state
    atomic_json(config, {'api_key':'other','vehicle_id':2})
    assert feed.snapshot()==({}, {}, False)


def test_vehicle_endpoint_and_image(tmp_path,monkeypatch):
    token='t'*40
    state={'vehicleName':'测试','remainingRange':318,'batteryLevel':61,'observed':'2025-04-12 16:40:00'}
    def snapshot(self):
        return state, {'place':'示例'*80}, bool(state)
    monkeypatch.setattr(vehicle.VehicleFeed,'snapshot',snapshot)
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(token,tmp_path/'unused'))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    def get(key, encoding=None):
        client=http.client.HTTPConnection(*server.server_address)
        headers = {'Authorization':'Bearer '+key}
        if encoding:
            headers['Accept-Encoding'] = encoding
        client.request('GET','/vehicle',headers=headers)
        res=client.getresponse()
        data=res.read()
        client.close()
        return res.status,data,res.getheader("Content-Encoding")
    try:
        assert get('invalid')[0]==401
        status, packet, encoding=get(token)
        assert encoding is None
        assert status==200 and len(packet)==48024 and packet[:4]==b'VEH1'
        assert struct.unpack_from('<I',packet,20)[0]==zlib.crc32(packet[24:],zlib.crc32(packet[:20]))
        assert packet[24:]==vehicle.vehicle_image(state,{'place':'示例'*80},True).tobytes()
        status,wire,encoding=get(token,'deflate')
        assert status==200 and encoding=='deflate' and len(wire)<len(packet)
        decoded=zlib.decompress(wire)
        assert decoded[:8]==packet[:8] and decoded[24:]==packet[24:]
        assert struct.unpack_from('<I',decoded,20)[0]==zlib.crc32(decoded[24:],zlib.crc32(decoded[:20]))
        assert get(token,'identity')[2] is None
        assert get('invalid','deflate')[0]==401
        state.clear()
        assert get(token)[0]==503
    finally:
        server.shutdown();server.server_close();thread.join()


def test_parking_limit_survives_restart_and_bad_reply_preserves_location(tmp_path, monkeypatch):
    config = tmp_path/'config.json'
    atomic_json(config, {'vehicle_id':1,'base_url':'https://example.invalid','api_key':'test'})
    clock = [10000]
    monkeypatch.setattr(vehicle.time, 'time', lambda: clock[0])
    attempts = []
    def api(cfg, route, body=None):
        if body:
            attempts.append(clock[0])
            return {'content':'{"place":"停车场","area":"B2","time":"15:12"}' if len(attempts)==1 else '未能查询'}
        if route=='/vehicles':
            return [{'id':1,'carModel':'Demo EV'}]
        return {'vehicleId':1,'remainingRange':318,'batteryLevel':61,'observedAt':'2025-04-12 12:00:00'}
    monkeypatch.setattr(vehicle,'request_data',api)
    def enter():
        feed=vehicle.VehicleFeed(config,tmp_path)
        state,parking,ok=feed.snapshot()
        assert ok and state['remainingRange']==318
        assert feed.parking_lock.acquire(timeout=3)
        feed.parking_lock.release()
        return parking
    assert enter()=={}
    clock[0]+=899
    assert enter()['area']=='B2' and attempts==[10000]
    clock[0]+=1
    assert enter()['area']=='B2' and attempts==[10000,10900]
    assert enter()['time']=='15:12' and len(attempts)==2


def test_vehicle_render_charge_limits_unknowns_and_clipping():
    base={'remainingRange':318,'observed':'2025-04-12 12:00:00'}
    empty=vehicle.vehicle_image({}, {}, False)
    low=vehicle.vehicle_image(dict(base,batteryLevel=0,charging=False),{},True)
    high=vehicle.vehicle_image(dict(base,batteryLevel=100,charging=True),{},True)
    assert low.crop((38,110,159,114)).getextrema()==(255,255)
    assert high.crop((38,110,159,114)).getextrema()==(0,0)
    badge = (36,120,216,150)
    assert high.crop(badge).getextrema()==(0,255)
    assert low.crop(badge).getextrema()==empty.crop(badge).getextrema()==(255,255)
    assert empty.mode=='1' and empty.size==(800,480)
    assert empty.crop((36,151,764,366)).tobytes()==high.crop((36,151,764,366)).tobytes()
    long=vehicle.vehicle_image(base,{'place':'测试停车场'*100},True)
    assert long.crop((310,412,800,465)).tobytes()==vehicle.vehicle_image(base,{},True).crop((310,412,800,465)).tobytes()
    assert vehicle.vehicle_image(base,{},False).crop((400,0,800,60)).tobytes()!=long.crop((400,0,800,60)).tobytes()


def test_model_lookup_timeout_preserves_fresh_status(tmp_path, monkeypatch):
    config = tmp_path/'cfg'
    atomic_json(config, {'vehicle_id':1, 'base_url':'https://example.invalid', 'api_key':'test'})
    def api(cfg, route, body=None):
        if route == '/vehicles':
            raise vehicle.requests.Timeout()
        if body:
            return {'content':'{}'}
        return {'vehicleId':1, 'remainingRange':318, 'batteryLevel':61,
                'observedAt':'2025-04-12 16:40:00'}
    monkeypatch.setattr(vehicle, 'request_data', api)
    feed = vehicle.VehicleFeed(config, tmp_path)
    state, _, ok = feed.snapshot()
    assert ok and state['remainingRange']==318 and state['model']==''
    assert feed.parking_lock.acquire(timeout=2)
    feed.parking_lock.release()

def test_transient_status_retry_and_persistent_failure(tmp_path, monkeypatch):
    config = tmp_path/'cfg'
    atomic_json(config, {'vehicle_id':1, 'base_url':'https://example.invalid', 'api_key':'test'})
    feed = vehicle.VehicleFeed(config, tmp_path)
    attempts = []
    def api(cfg, route, body=None):
        if body:
            return {'content':'{}'}
        if route == '/vehicles':
            raise vehicle.requests.Timeout()
        attempts.append(route)
        if len(attempts) != 2:
            raise vehicle.requests.ReadTimeout()
        return {'vehicleId':1, 'remainingRange':318, 'batteryLevel':61,
                'observedAt':'2025-04-12 16:40:00'}
    monkeypatch.setattr(vehicle, 'request_data', api)
    state, _, ok = feed.snapshot()
    assert ok and state['remainingRange']==318 and len(attempts)==2
    assert feed.parking_lock.acquire(timeout=2)
    feed.parking_lock.release()
    cached, _, ok = feed.snapshot()
    assert not ok and cached==state and len(attempts)==4
