import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import struct
import subprocess
import threading
import zlib

import pytest
from paper.firmware_bridge import frame_packet, make_handler, PACKET_SIZE


@pytest.fixture(scope='module')
def core(tmp_path_factory):
    root=Path(__file__).parents[1]
    exe=tmp_path_factory.mktemp('native')/'firmware-core-test'
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-I',str(root/'firmware/include'),
                    str(root/'tests/firmware_core_test.cpp'),'-o',str(exe)],check=True)
    return exe


def test_clock_only_change_does_not_refresh_other_regions_or_pages(core):
    subprocess.run([str(core)],check=True)


def test_actual_panel_transport_bounds_old_frame_and_timeout(tmp_path):
    root=Path(__file__).parents[1]
    exe=tmp_path/'panel-test'
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror',
                    '-I',str(root/'tests/panel_stubs'),'-I',str(root/'firmware/include'),
                    str(root/'tests/panel_transport_test.cpp'),str(root/'firmware/src/panel.cpp'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=5)


def test_host_packet_accepted_by_actual_firmware_parser(core,tmp_path):
    packet=frame_packet({},1794132000,1794131900)
    assert len(packet)==PACKET_SIZE
    assert struct.unpack_from('<I',packet,16)[0]==1  # Missing data remains visible.
    assert zlib.crc32(packet[24:],zlib.crc32(packet[:20]))==struct.unpack_from('<I',packet,20)[0]
    # The device owns the clock: changing time must not paint server clock digits.
    bitmap=packet[24:]
    for y in range(80,208):
        assert bitmap[y*100+37:y*100+65]==b'\xff'*28
    f=tmp_path/'frame.bin';f.write_bytes(packet)
    subprocess.run([str(core),str(f)],check=True)
    for corrupt in [packet[:-1],packet+b'X',b'FAIL'+packet[4:],packet[:8]+b'\x00'*4+packet[12:],
                    packet[:100]+bytes([packet[100]^1])+packet[101:]]:
        f.write_bytes(corrupt)
        assert subprocess.run([str(core),str(f)]).returncode==2


@pytest.mark.parametrize('field,value',[(8,0),(8,2145916800),(12,0),(12,1794132006),(16,2)])
def test_semantically_invalid_packet_rejected_even_with_valid_crc(core,tmp_path,field,value):
    packet=bytearray(frame_packet({},1794132000,1794131900))
    struct.pack_into('<I',packet,field,value)
    struct.pack_into('<I',packet,20,zlib.crc32(packet[24:],zlib.crc32(packet[:20])))
    path=tmp_path/'invalid.bin';path.write_bytes(packet)
    assert subprocess.run([str(core),str(path)]).returncode==2


def test_source_offline_flag_is_independent_of_fresh_render_timestamp():
    snapshot={'quotes':[{'ok':True} for _ in range(6)],'weather':{'ok':True},'usage':{'ok':True}}
    packet=frame_packet(snapshot,1794132000,1794132000)
    assert struct.unpack_from('<I',packet,16)[0]==0
    snapshot['weather']['ok']=False
    packet=frame_packet(snapshot,1794132000,1794132000)
    assert struct.unpack_from('<I',packet,16)[0]==1


def test_feed_is_authenticated_read_only_and_preserves_missing_data(tmp_path):
    path=tmp_path/'snapshot.json'
    token='t'*40
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(token,path))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def request(route='/frame',auth=True,method='GET'):
        client=http.client.HTTPConnection(*server.server_address)
        headers={'Authorization':'Bearer '+token} if auth else {}
        client.request(method,route,headers=headers)
        response=client.getresponse();status=response.status;body=response.read();client.close()
        return status,body
    try:
        assert request(auth=False)[0]==401
        assert request('/page/2')[0]==404
        assert request(method='POST')[0]==501
        assert request()[0]==503
        path.write_text('{broken')
        assert request()[0]==503
        path.write_text('[]')
        assert request()[0]==503
        path.write_text(json.dumps({}))
        status,body=request()
        assert status==200 and len(body)==PACKET_SIZE
        assert path.read_text()=='{}'
    finally:
        server.shutdown();server.server_close();thread.join()
