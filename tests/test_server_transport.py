import http.client
from http.server import ThreadingHTTPServer
import sys
import threading
import pytest
from paper import server


@pytest.mark.parametrize('feed_enabled',[True,False])
def test_local_transport_never_schedules_cloud_even_during_feed_outage(monkeypatch,feed_enabled):
    cfg={'device':{'enabled':True,'transport':'local'},'firmware_bridge':{'enabled':feed_enabled}}
    engine=server.Engine(cfg);engine.settled={'quotes','weather','usage'}
    def forbidden(*a,**k):raise AssertionError('Local transport touched cloud credentials')
    monkeypatch.setattr(server,'env_value',forbidden)
    try:
        engine.push_if_due(1)
        assert engine.delivery is None
    finally:engine.pool.shutdown()


@pytest.mark.parametrize('feed_enabled',[True,False])
def test_local_transport_setup_cannot_enable_cloud(feed_enabled):
    cfg={'port':8766,'device':{'enabled':False,'transport':'local'},'firmware_bridge':{'enabled':feed_enabled}}
    engine=server.Engine(cfg)
    httpd=ThreadingHTTPServer(('127.0.0.1',0),server.handler(engine))
    thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
    def request(method,path):
        client=http.client.HTTPConnection(*httpd.server_address)
        client.request(method,path);response=client.getresponse();result=response.status,response.read();client.close();return result
    try:
        status,body=request('GET','/setup')
        assert status==200 and b'<form' not in body and b'type="password"' not in body
        assert request('POST','/setup')[0]==409
        assert b'href="/setup"' not in request('GET','/')[1]
        assert cfg['device']['enabled'] is False
    finally:
        httpd.shutdown();httpd.server_close();thread.join();engine.pool.shutdown()


def test_explicit_cloud_cli_refused_in_local_transport(monkeypatch):
    monkeypatch.setattr(server,'config',lambda:{'device':{'enabled':False,'transport':'local'}})
    monkeypatch.setattr(sys,'argv',['server','--deploy-once'])
    with pytest.raises(SystemExit,match='does not permit cloud deployment'):server.main()
