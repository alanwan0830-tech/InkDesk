import json,time
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from paper.codex import select_weekly,task_state
from paper.hook import reduce_event
from paper.data import parse_yahoo,forecast_hours
from paper.render import render_svg,GLYPHS,reset_label
from paper import common

def test_weekly_in_primary_and_no_fake_five_hour():
    assert select_weekly({'rateLimitsByLimitId':{'codex':{'primary':{'windowDurationMins':10080,'usedPercent':51,'resetsAt':123}}}})['used']==51
    with pytest.raises(ValueError):select_weekly({'rateLimits':{'primary':{'windowDurationMins':300,'usedPercent':0}}})

def test_change_uses_previous_session_not_range_start():
    payload={'chart':{'result':[{'meta':{'currency':'USD','regularMarketPrice':110,'regularMarketTime':1704240000,'exchangeTimezoneName':'UTC','chartPreviousClose':50},'timestamp':[1704067200,1704153600,1704240000],'indicators':{'quote':[{'close':[90,100,110]}]}}]}}
    assert parse_yahoo(payload,'X','USD')['change']==pytest.approx(10)

def test_missing_close_is_unknown_not_zero():
    payload={'chart':{'result':[{'meta':{'currency':'USD','regularMarketPrice':110,'regularMarketTime':1704240000,'chartPreviousClose':50}}]}}
    assert parse_yahoo(payload,'X','USD')['change'] is None

def test_approval_is_not_completion_and_hooks_never_decide():
    event={'session_id':'abc','cwd':'/tmp/Paper','hook_event_name':'PermissionRequest'}
    row=reduce_event(None,event,100)
    assert row['state']=='approval'
    assert 'decision' not in row
    row=reduce_event(row,{**event,'hook_event_name':'PostToolUse'},101)
    assert row['state']=='running'
    row=reduce_event(row,{**event,'hook_event_name':'Stop'},102)
    assert row['state']=='completed'

def test_child_cannot_finish_parent():
    row={'state':'running'}
    assert reduce_event(row,{'hook_event_name':'Stop','agent_id':'sub'},100)==row

def test_async_input_does_not_claim_execution_blocked():
    assert reduce_event(None,{'hook_event_name':'PreToolUse','tool_name':'request_user_input_async'},100)['state']=='running'

def test_forecast_crosses_midnight_and_is_future_only():
    now=datetime(2026,11,7,23,30,tzinfo=ZoneInfo('Asia/Shanghai'))
    h={'time':['2026-11-07T23:00','2026-11-08T00:00','2026-11-08T03:00','2026-11-08T06:00','2026-11-08T09:00'], 'temperature_2m':[1,2,3,4,5],'weather_code':[0]*5}
    assert [x['time'] for x in forecast_hours({'hourly':h},now)]==['00:00','03:00','06:00','09:00']

def test_no_data_renders_without_demo_prices_or_usage():
    svg=render_svg({},datetime(2026,11,8,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert '任务通知未连接' in svg and '暂无数据' in svg
    assert '73,635' not in svg and '21%' not in svg
    for digit in '0123456789':assert len(GLYPHS[digit])==12

def test_cache_failure_keeps_original_timestamp(tmp_path,monkeypatch):
    monkeypatch.setattr(common,'RUNTIME',tmp_path)
    good=common.cached_source('x',lambda:{'price':5})
    def bad():raise ValueError('network error')
    cached=common.cached_source('x',bad)
    assert not cached['ok'] and cached['data']==good['data'] and cached['fetched_at']==good['fetched_at']

def test_expired_reset_is_not_fake_new_window():
    now=datetime(2026,11,8,tzinfo=ZoneInfo('Asia/Shanghai'))
    assert '待更新' in reset_label(now.timestamp()-10,now)

def test_stale_event_does_not_claim_running(tmp_path,monkeypatch):
    from paper import codex
    monkeypatch.setattr(codex,'RUNTIME',tmp_path)
    (tmp_path/'events.json').write_text(json.dumps({'threads':{'a':{'state':'running','cwd':'/anything','updated_at':10}}}))
    result=codex.task_state({'scope':'all','event_stale_seconds':60},now=1000)
    assert result['selected']['state']=='stale' and result['running']==0

def test_hmi_never_deletes_unowned_designs(tmp_path,monkeypatch):
    from paper import hmi
    monkeypatch.setattr(hmi,'RUNTIME',tmp_path)
    client=object.__new__(hmi.HmiClient);client.key='test'
    calls=[];page_ids=iter([101,102,103,104])
    def request(method,path,body=None):
        calls.append((method,path,body))
        if path.endswith('/device/list'):return [{'id':20240911,'mac_address':'TEST'}]
        if path.endswith('/playlist'):return {'id':20}
        if path.endswith('/oss/upload'):return {'url':'https://example.com/frame.png'}
        if path.endswith('/page') and method=='POST':return {'ids':[next(page_ids)]}
        if path.endswith('/deploy'):
            assert body=={'mode':'refresh','playlist_id':20,'mac_addresses':['TEST']}
            return {'devices':[{'mac_address':'TEST','playlist_id':20}]}
        return True
    client.request=request
    for _ in range(4):client.deploy_once(b'png',20240911)
    deletes=[body['id'] for method,path,body in calls if method=='DELETE']
    assert deletes==[101]
    manifest=json.loads((tmp_path/'hmi.json').read_text())
    assert manifest['owned_page_ids']==[102,103,104]

def test_hmi_failure_preserves_existing_page(tmp_path,monkeypatch):
    from paper import hmi
    monkeypatch.setattr(hmi,'RUNTIME',tmp_path)
    client=object.__new__(hmi.HmiClient);client.key='test';calls=[]
    def request(method,path,body=None):
        calls.append((method,path))
        if path.endswith('/device/list'):return [{'id':1,'mac_address':'TEST'}]
        if path.endswith('/playlist'):return {'id':20}
        if path.endswith('/oss/upload'):return {'url':'https://example.com/frame.png'}
        if path.endswith('/page'):return {'ids':[100]}
        if path.endswith('/deploy'):raise TimeoutError()
        return True
    client.request=request
    with pytest.raises(TimeoutError):client.deploy_once(b'png',1)
    assert not any(method=='DELETE' for method,path in calls)
    assert 'last_sent_at' not in json.loads((tmp_path/'hmi.json').read_text())

def test_hmi_photo_survives_repeated_dashboard_refresh(tmp_path,monkeypatch):
    from paper import hmi
    monkeypatch.setattr(hmi,'RUNTIME',tmp_path)
    state={'owner':'paper-dashboard','device_id':1,'playlist_id':20,
           'extra_page_ids':[900],'owned_page_ids':[900,101,102,103]}
    (tmp_path/'hmi.json').write_text(json.dumps(state))
    client=object.__new__(hmi.HmiClient);client.key='test';calls=[]
    def request(method,path,body=None):
        calls.append((method,path,body))
        if path.endswith('/device/list'):return [{'id':1,'mac_address':'TEST'}]
        if path.endswith('/oss/upload'):return {'url':'https://example.com/frame.png'}
        if path.endswith('/page') and method=='POST':return {'ids':[104]}
        if path.endswith('/deploy'):return {'devices':[{'mac_address':'TEST','playlist_id':20}]}
        return True
    client.request=request
    client.deploy_once(b'png',1)
    pages=next(body['pages'] for _,path,body in calls if path.endswith('/upsert_pages'))
    assert pages==[{'id':104,'sort':0},{'id':900,'sort':1}]
    assert not any(method=='DELETE' and body['id']==900 for method,_,body in calls)
    assert json.loads((tmp_path/'hmi.json').read_text())['extra_page_ids']==[900]

def test_live_cat_fourth_page_keeps_photos(tmp_path,monkeypatch):
    from paper import hmi
    monkeypatch.setattr(hmi,'RUNTIME',tmp_path)
    state={'owner':'paper-dashboard','device_id':1,'playlist_id':20,
           'extra_page_ids':[900,901],'owned_page_ids':[100,101,102], 'cat_screen_enabled':True}
    (tmp_path/'hmi.json').write_text(json.dumps(state))
    (tmp_path/'cat-weather.png').write_bytes(b'cat')
    client=object.__new__(hmi.HmiClient);calls=[];ids=iter([103,104,105,106])
    def request(method,path,body=None):
        calls.append((method,path,body))
        if path.endswith('/device/list'):return [{'id':1,'mac_address':'TEST'}]
        if path.endswith('/oss/upload'):return {'url':'https://example.com/frame.png'}
        if path.endswith('/page') and method=='POST':return {'ids':[next(ids)]}
        if path.endswith('/deploy'):return {'devices':[{'mac_address':'TEST','playlist_id':20}]}
        return True
    client.request=request
    client.deploy_once(b'png',1);client.deploy_once(b'new',1)
    pages=[body['pages'] for _,path,body in calls if path.endswith('/upsert_pages')]
    assert pages[-1]==[{'id':105,'sort':0},{'id':900,'sort':1},{'id':901,'sort':2},{'id':106,'sort':3}]
    assert not any(method=='DELETE' and body['id'] in [900,901,105,106] for method,_,body in calls)

def test_single_page_preserves_archived_screens(tmp_path,monkeypatch):
    from paper import hmi
    monkeypatch.setattr(hmi,'RUNTIME',tmp_path)
    state={'owner':'paper-dashboard','device_id':1,'playlist_id':20,
           'extra_page_ids':[],'owned_page_ids':[900,101,102,103],
           'archived_page_ids':[900,901,902],'cat_screen_enabled':False}
    (tmp_path/'hmi.json').write_text(json.dumps(state))
    client=object.__new__(hmi.HmiClient);calls=[]
    def request(method,path,body=None):
        calls.append((method,path,body))
        if path.endswith('/device/list'):return [{'id':1,'mac_address':'TEST'}]
        if path.endswith('/oss/upload'):return {'url':'https://example.com/frame.png'}
        if path.endswith('/page') and method=='POST':return {'ids':[104]}
        if path.endswith('/deploy'):return {'devices':[{'mac_address':'TEST','playlist_id':20}]}
        return True
    client.request=request
    client.deploy_once(b'png',1)
    pages=next(body['pages'] for _,path,body in calls if path.endswith('/upsert_pages'))
    assert pages==[{'id':104,'sort':0}]
    assert not any(method=='DELETE' and body['id'] in [900,901,902] for method,_,body in calls)

@pytest.mark.parametrize('status,last_seen',[(3,100000),(1,1000),(1,None),(0,100000)])
def test_sleeping_device_never_replaces_playlist(tmp_path,monkeypatch,status,last_seen):
    from paper import hmi
    monkeypatch.setattr(hmi,'RUNTIME',tmp_path)
    monkeypatch.setattr(hmi.time,'time',lambda:100)
    state={'owner':'paper-dashboard','device_id':1,'playlist_id':20,'publish_only_when_awake':True}
    (tmp_path/'hmi.json').write_text(json.dumps(state))
    client=object.__new__(hmi.HmiClient);calls=[]
    def request(method,path,body=None):
        calls.append(method)
        return [{'id':1,'mac_address':'TEST','online_status':status,'last_seen':last_seen}]
    client.request=request
    with pytest.raises(hmi.DeviceNotAwake):client.deploy_once(b'png',1)
    assert calls==['GET']
    assert json.loads((tmp_path/'hmi.json').read_text())==state

def test_awake_report_gate(monkeypatch):
    from paper import hmi
    monkeypatch.setattr(hmi.time,'time',lambda:100)
    object.__new__(hmi.HmiClient).require_awake({'online_status':1,'last_seen':99000})
