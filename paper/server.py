from __future__ import annotations
import argparse, fcntl, hashlib, json, logging, os, secrets, signal, threading, time
from urllib.parse import parse_qs
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo
from . import data, codex
from .common import ROOT,RUNTIME,config,atomic_json,read_json,env_value
from .render import write_frame

LOG=logging.getLogger('paper')
def local_firmware(cfg):
    return cfg.get('device',{}).get('transport')=='local' or cfg.get('firmware_bridge',{}).get('enabled',False)
PAGE='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Paper 实时看板</title><style>body{background:#eeeae3;color:#171714;font:16px -apple-system,BlinkMacSystemFont,sans-serif;max-width:1080px;margin:48px auto;padding:0 24px}header{display:flex;justify-content:space-between;align-items:baseline}h1{font:600 28px Georgia;margin-bottom:8px}p{line-height:1.7}img{width:100%;max-width:800px;height:auto;border:12px solid #ddd6c9;background:white;box-shadow:0 3px 18px #0002}section{margin-top:24px;max-width:824px}.status{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.status div{border-top:2px solid #222;padding-top:12px}small{color:#5e5b54}code{background:#fff8;padding:3px 6px}a{color:inherit}pre{white-space:pre-wrap;font-size:13px;line-height:1.6}</style><header><h1>Paper / 实时看板</h1><small>北京海淀 · E1001</small></header><p>本机预览每 10 秒检查更新。设备端连接状态见下方；这里显示的是实时生成的画面。</p><img id="screen" src="/dashboard.png" alt="800×480 实时墨水屏看板"><section class="status"><div><b>数据</b><p id="sources">正在读取…</p></div><div><b>Codex 通知</b><p id="events">正在读取…</p></div><div><b>设备连接</b><p id="device">正在读取…</p></div></section><section><small>行情可能延迟：Yahoo Finance；BTC/USD：Coinbase；天气：<a href="https://open-meteo.com/">Open-Meteo</a>。日期与时钟使用北京时间。Mac 必须保持运行才能采集与更新。</small></section><section><p><a href="/setup">连接 Paper 设备</a></p><details><summary>接入状态与说明</summary><pre id="details"></pre></details></section><script>async function refresh(){try{const r=await fetch('/status.json',{cache:'no-store'});const s=await r.json();document.getElementById('screen').src='/dashboard.png?v='+s.rendered_at;document.getElementById('sources').textContent=s.sources;document.getElementById('events').textContent=s.events;document.getElementById('device').textContent=s.device;document.getElementById('details').textContent=s.notes;}catch(e){document.getElementById('sources').textContent='本地服务暂未响应';}}refresh();setInterval(refresh,10000);</script></html>'''

class Engine:
    def __init__(self,cfg):
        self.cfg=cfg;self.stop=threading.Event();self.pool=ThreadPoolExecutor(max_workers=3)
        self.snapshot={'quotes':[],'weather':{},'usage':{},'tasks':{}};self.jobs={};self.due={'quotes':0,'weather':0,'usage':0}
        self.rendered_at=0;self.last_key=None;self.last_render_mono=0;self.settled=set()
        self.lock=threading.RLock();self.delivery=None;self.delivery_due=0;self.delivery_error=None;self.last_sent_hash=None;self.last_sent_attention=None
    def public_status(self):
        with self.lock:
            q=self.snapshot['quotes'];w=self.snapshot['weather'];u=self.snapshot['usage'];tasks=self.snapshot['tasks']
            key_set=bool(env_value('HMI_API_KEY'));n=sum(bool(x.get('ok')) for x in q)
            result = {'rendered_at':self.rendered_at,'sources':f'行情 {n}/6 · 天气 '+('正常' if w.get('ok') else '等待/离线')+' · 额度 '+('正常' if u.get('ok') else '等待/离线'),
              'events':'已收到真实任务事件' if tasks.get('connected') else '待启用通知钩子',
              'device':(('设备休眠中，等待联网后更新' if self.delivery_error=='DeviceNotAwake' else '上屏请求失败，稍后重试') if self.delivery_error else ('正在提交到设备' if self.delivery and not self.delivery.done() else ('已提交更新 · 以设备唤醒为准' if read_json(RUNTIME/'hmi.json',{}).get('last_sent_at') else '自动推送待首次验证'))) if key_set and self.cfg['device'].get('enabled') else ('密钥已配置 · 自动推送未启用' if key_set else '未配置设备 API 密钥'),
              'notes':'数据独立刷新：行情 5 分钟、天气 15 分钟、额度 5 分钟。画面每分钟更新。\nCodex 状态仅来自事件钩子，不读取对话正文；当前范围为 Paper 项目。\n约每 5 分钟更新，设备休眠时延后到联网后推送；待处理/完成事件优先，最短间隔 60 秒。本地预览不代表实机已刷新。\nAPI 密钥请保存在项目 .env 的 HMI_API_KEY 中；不要发到聊天。'}
            if local_firmware(self.cfg):
                result['device']=('自研固件数据接口已开启' if self.cfg.get('firmware_bridge',{}).get('enabled') else '自研固件数据接口暂停')+' · 实机以设备日志为准'
                result['notes']='设备本地按分钟走时，约每五分钟读取第一屏数据；断网保留缓存。不轮播。\n原厂云端推送已停用，其他页面归档保留。\nCodex 仅使用项目事件元数据，不读取对话正文。\n本机预览不代表实机已刷新。'
            return result
    def tick(self):
        mono=time.monotonic();ts=time.time()
        jobs={'quotes':data.quotes,'weather':lambda:data.weather(self.cfg['weather']),'usage':codex.usage}
        for name,fn in jobs.items():
            future=self.jobs.get(name)
            if future and future.done():
                try:
                    with self.lock:self.snapshot[name]=future.result()
                except Exception as exc:LOG.warning('%s refresh failed: %s',name,type(exc).__name__)
                self.settled.add(name);self.jobs.pop(name);self.due[name]=mono+self.cfg['intervals'][name]
            elif future is None and mono>=self.due[name]:self.jobs[name]=self.pool.submit(fn)
        with self.lock:
            self.snapshot['tasks']=codex.task_state(self.cfg['codex'],ts)
            now=datetime.fromtimestamp(ts,ZoneInfo(self.cfg['timezone']))
            # Include minute, data updates and state transitions. Debounce tool bursts.
            key=json.dumps({'minute':now.strftime('%Y%m%d%H%M'),'q':self.snapshot['quotes'],'w':self.snapshot['weather'],
                            'u':self.snapshot['usage'],'t':self.snapshot['tasks']},sort_keys=True,ensure_ascii=False)
            if key!=self.last_key and mono-self.last_render_mono>=5:
                write_frame(self.snapshot,now);self.rendered_at=int(ts);self.last_render_mono=mono;self.last_key=key
                atomic_json(RUNTIME/'snapshot.json',self.snapshot)
                atomic_json(RUNTIME/'status.json',self.public_status())
        self.push_if_due(mono)
    def push_if_due(self,mono):
        if local_firmware(self.cfg):return
        if self.delivery and self.delivery.done():
            try:self.delivery.result();self.delivery_error=None
            except Exception as exc:self.delivery_error=type(exc).__name__;self.last_sent_hash=None;self.last_sent_attention=None
            self.delivery=None;self.delivery_due=mono+(15 if self.delivery_error=='DeviceNotAwake' else 60)
        if len(self.settled)<3 or self.delivery or not self.cfg['device'].get('enabled') or not env_value('HMI_API_KEY'):return
        if mono<self.delivery_due:return
        frame=RUNTIME/'dashboard.png'
        if not frame.exists():return
        tasks=self.snapshot['tasks'];sel=tasks.get('selected') or {}
        notice=(sel.get('state'),sel.get('turn_id'))
        urgent=sel.get('state') in ('approval','input','error','completed') and notice!=self.last_sent_attention
        last=read_json(RUNTIME/'hmi.json',{}).get('last_sent_at',0)
        if not urgent and time.time()-last<300:return
        blob=frame.read_bytes();sha=hashlib.sha256(blob).hexdigest()
        if sha==self.last_sent_hash:return
        from .hmi import HmiClient
        self.last_sent_hash=sha;self.last_sent_attention=notice
        self.delivery=self.pool.submit(HmiClient().deploy_once,blob,self.cfg['device']['id'])
    def run(self):
        while not self.stop.is_set():
            try:self.tick()
            except Exception as exc:LOG.error('Refresh error: %s',type(exc).__name__)
            self.stop.wait(2)
        self.pool.shutdown(wait=False,cancel_futures=True)

def handler(engine):
    csrf=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path=='/setup' and local_firmware(engine.cfg):
                self.send_error(409,'Local firmware mode; cloud setup is disabled');return
            origin=self.headers.get('Origin','')
            allowed={f'http://127.0.0.1:{engine.cfg["port"]}',f'http://localhost:{engine.cfg["port"]}'}
            if self.path!='/setup' or origin not in allowed:
                self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<8192:raise ValueError()
                form=parse_qs(self.rfile.read(length).decode())
                if not secrets.compare_digest(form.get('csrf',[''])[0],csrf):raise ValueError()
                key=form.get('key',[''])[0].strip()
                if not key or any(c in key for c in '\r\n'):raise ValueError()
                from .hmi import HmiClient
                client=object.__new__(HmiClient);client.key=key
                client.device(engine.cfg['device']['id']) # Verify with the vendor before saving.
                env=ROOT/'.env'
                old=env.read_text().splitlines() if env.exists() else []
                lines=[line for line in old if not line.startswith('HMI_API_KEY=')]
                fd=os.open(env,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                with os.fdopen(fd,'w') as f:f.write('\n'.join(lines+['HMI_API_KEY='+key])+'\n')
                os.chmod(env,0o600)
                engine.cfg['device']['enabled']=True;atomic_json(ROOT/'config.json',engine.cfg)
                self.send_response(303);self.send_header('Location','/');self.end_headers()
            except Exception:
                self.send_error(400,'Device key could not be verified; nothing was enabled')
        def do_GET(self):
            path=self.path.split('?',1)[0]
            host=self.headers.get('Host','').split(':')[0]
            if host not in ['127.0.0.1','localhost','[::1]']:
                self.send_error(403);return
            if path=='/':
                page=PAGE.replace('<a href="/setup">连接 Paper 设备</a>','设备使用本地固件模式') if local_firmware(engine.cfg) else PAGE
                body=page.encode();mime='text/html; charset=utf-8'
            elif path=='/setup' and local_firmware(engine.cfg):
                body='<!doctype html><meta charset="utf-8"><title>Paper</title><p>设备使用本地固件模式，原厂云端配网入口已关闭。</p><a href="/">返回看板</a>'.encode();mime='text/html; charset=utf-8'
            elif path=='/setup':
                body=('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>连接 Paper</title><style>body{font:17px -apple-system,sans-serif;max-width:620px;margin:64px auto;padding:24px;line-height:1.8}input{padding:12px;font:inherit;width:95%;margin:12px 0}button{padding:12px 24px;font:inherit;background:#222;color:#fff;border:0;cursor:pointer}</style><h1>连接 Paper 设备</h1><p>输入 SenseCraft HMI API 密钥。它只保存在这台 Mac 的项目配置中，用于向 Paper 推送看板。不要把密钥发到聊天里。</p><p>连接后每 5 分钟推送一张画面；待处理和完成通知优先更新。设备休眠时要等它唤醒后接收。</p><form method="post" action="/setup"><input type="hidden" name="csrf" value="'''+csrf+'''"><label>设备访问密钥<input name="key" type="password" autocomplete="off" required></label><button>验证密钥并开启设备更新</button></form><p><a href="/">返回看板</a></p></html>''').encode();mime='text/html; charset=utf-8'
            elif path=='/status.json':body=json.dumps(engine.public_status(),ensure_ascii=False).encode();mime='application/json'
            elif path in ['/dashboard.png','/dashboard.svg']:
                file=RUNTIME/path[1:]
                if not file.exists():self.send_error(503,'Preparing first frame');return
                body=file.read_bytes();mime='image/png' if path.endswith('png') else 'image/svg+xml'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    return Handler

def main():
    parser=argparse.ArgumentParser(description='Paper local live dashboard')
    parser.add_argument('--once',action='store_true',help='Fetch sources once and render without a server')
    parser.add_argument('--deploy-once',action='store_true',help='Explicitly send the rendered frame through SenseCraft API')
    args=parser.parse_args();RUNTIME.mkdir(exist_ok=True)
    cfg=config();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    if local_firmware(cfg) and (cfg['device'].get('enabled') or args.deploy_once):
        raise SystemExit('Local firmware mode does not permit cloud deployment')
    lock=(RUNTIME/'server.lock').open('w')
    if not args.once and not args.deploy_once:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Paper service is already running')
    engine=Engine(cfg)
    if args.once or args.deploy_once:
        with ThreadPoolExecutor(max_workers=3) as pool:
            fq=pool.submit(data.quotes);fw=pool.submit(data.weather,cfg['weather']);fu=pool.submit(codex.usage)
            engine.snapshot.update(quotes=fq.result(),weather=fw.result(),usage=fu.result(),tasks=codex.task_state(cfg['codex']))
        now=datetime.now(ZoneInfo(cfg['timezone']));png=write_frame(engine.snapshot,now)
        engine.rendered_at=int(time.time());atomic_json(RUNTIME/'snapshot.json',engine.snapshot);atomic_json(RUNTIME/'status.json',engine.public_status())
        print(json.dumps(engine.public_status(),ensure_ascii=False))
        if args.deploy_once:
            from .hmi import HmiClient
            print(json.dumps(HmiClient().deploy_once(png,cfg['device']['id'])))
        return
    bridge=None;bridge_worker=None
    bridge_cfg=cfg.get('firmware_bridge',{})
    if bridge_cfg.get('enabled'):
        if cfg['device'].get('enabled'):raise SystemExit('Disable cloud push before starting the firmware bridge')
        from .firmware_bridge import create_server
        bridge=create_server(bridge_cfg.get('host','0.0.0.0'),bridge_cfg.get('port',8767),RUNTIME/'firmware-bridge-token',RUNTIME/'snapshot.json')
        bridge_worker=threading.Thread(target=bridge.serve_forever,daemon=True);bridge_worker.start()
    server=ThreadingHTTPServer(('127.0.0.1',cfg['port']),handler(engine))
    worker=threading.Thread(target=engine.run,daemon=True);worker.start()
    def shutdown(*_):engine.stop.set();threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    LOG.info('Paper preview: http://127.0.0.1:%s',cfg['port'])
    try:server.serve_forever(poll_interval=.5)
    finally:
        engine.stop.set();server.server_close();worker.join(timeout=3)
        if bridge:bridge.shutdown();bridge.server_close();bridge_worker.join(timeout=3)

if __name__=='__main__':main()
