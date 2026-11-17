from __future__ import annotations
import json, os, selectors, shutil, subprocess, time
from pathlib import Path
from .common import ROOT, RUNTIME, read_json, cached_source

CLI=shutil.which('codex') or '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'

def rpc(method, params=None, socket=None, timeout=25):
    # Separate stdio server is used ONLY for account limits, never for desktop task state.
    args=[CLI,'app-server','proxy','--sock',socket] if socket else [CLI,'app-server','--stdio']
    p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
    selector=selectors.DefaultSelector();selector.register(p.stdout,selectors.EVENT_READ)
    def send(message):p.stdin.write((json.dumps(message)+'\n').encode());p.stdin.flush()
    send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'paper_dashboard','version':'0.1'}}})
    deadline=time.monotonic()+timeout; buffer=b''
    try:
        while time.monotonic()<deadline:
            for key,_ in selector.select(.25):
                chunk=os.read(key.fd,65536)
                if not chunk:raise ConnectionError('Codex disconnected')
                buffer+=chunk
                while b'\n' in buffer:
                    raw,buffer=buffer.split(b'\n',1)
                    try:d=json.loads(raw)
                    except ValueError:continue
                    if d.get('id')==1:
                        if 'error' in d:raise RuntimeError('Initialize failed')
                        send({'method':'initialized','params':{}});send({'id':2,'method':method,'params':params or {}})
                    elif d.get('id')==2:
                        if 'error' in d:raise RuntimeError('Codex request failed')
                        return d['result']
        raise TimeoutError('Codex timeout')
    finally:
        selector.close()
        p.terminate()
        try:p.wait(3)
        except subprocess.TimeoutExpired:p.kill();p.wait()

def select_weekly(result):
    buckets=result.get('rateLimitsByLimitId') or {}
    bucket=buckets.get('codex') or result.get('rateLimits') or {}
    for key in ['primary','secondary']:
        window=bucket.get(key) or {}
        if window.get('windowDurationMins')==10080 and isinstance(window.get('usedPercent'),(int,float)):
            return {'used':max(0,min(100,window['usedPercent'])),'resets_at':window.get('resetsAt'),'duration_minutes':10080}
    raise ValueError('Weekly window unavailable')

def usage():return cached_source('codex_usage',lambda:select_weekly(rpc('account/rateLimits/read')))

PRIORITY={'approval':0,'input':1,'error':2,'running':3,'completed':4,'interrupted':5,'idle':6,'stale':7}

def task_state(settings, now=None):
    now=now or time.time();state=read_json(RUNTIME/'events.json',{});items=[]
    for key,row in state.get('threads',{}).items():
        item=dict(row)
        if settings.get('scope')=='project' and item.get('cwd')!=str(ROOT):continue
        age=now-item.get('updated_at',0)
        if age>86400:continue
        if age>settings.get('event_stale_seconds',1800) and item.get('state') in ('running','approval','input'):
            item['state']='stale'
        items.append(item)
    items.sort(key=lambda r:(PRIORITY.get(r['state'],9),-r['updated_at']))
    return {'connected':bool(items),'mode':'hooks','selected':items[0] if items else None,
            'running':sum(r['state']=='running' for r in items),
            'attention':sum(r['state'] in ('approval','input') for r in items),
            'last_event_at':max((r['updated_at'] for r in items),default=None)}
