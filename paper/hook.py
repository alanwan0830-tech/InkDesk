"""Notification-only Codex hook. Never returns approval decisions or model context."""
from __future__ import annotations
import fcntl, json, os, sys, time
from pathlib import Path
# Work with any cwd, without a dependency installer or network access.
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from paper.common import RUNTIME, read_json, atomic_json


def reduce_event(previous, event, now):
    name=event.get('hook_event_name');tool=event.get('tool_name','')
    if event.get('agent_id'):return previous # Do not let child events overwrite a parent's task.
    status={'SessionStart':'idle','UserPromptSubmit':'running','PreModelRequest':'running',
            'PermissionRequest':'approval','PostToolUse':'running','Stop':'completed',
            'Interrupt':'interrupted','SessionEnd':'idle'}.get(name)
    if name=='PreToolUse':
        status='input' if ('request_user_input' in tool or 'requestUserInput' in tool) else 'running'
    if not status:return previous
    # Async question invocation is not a blocking wait; keep running and report question separately.
    if name=='PreToolUse' and 'request_user_input_async' in tool:status='running'
    cwd=event.get('cwd','');label=Path(cwd).name or 'Codex'
    return {'state':status,'project':label[:30],'cwd':cwd,'updated_at':now,
            'turn_id':event.get('turn_id'),'event':name}

def consume(event):
    sid=event.get('session_id')
    if not isinstance(sid,str) or not sid:return
    RUNTIME.mkdir(parents=True,exist_ok=True)
    with (RUNTIME/'events.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        data=read_json(RUNTIME/'events.json',{'threads':{}});threads=data.setdefault('threads',{})
        result=reduce_event(threads.get(sid),event,time.time())
        if result:threads[sid]=result
        threads={k:v for k,v in threads.items() if v.get('updated_at',0)>time.time()-7*86400}
        atomic_json(RUNTIME/'events.json',{'threads':threads})

if __name__=='__main__':
    try:consume(json.loads(sys.stdin.buffer.read(1024*1024)))
    except Exception:pass
    # Explicitly no output and success, even if the dashboard is unavailable.
