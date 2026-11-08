from __future__ import annotations
import json, os, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / 'runtime'

def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def read_json(path: Path, default=None):
    try: return json.loads(path.read_text())
    except (OSError, ValueError): return default

def config(): return read_json(ROOT / 'config.json', {})

def env_value(name):
    if os.environ.get(name): return os.environ[name]
    try:
        for line in (ROOT / '.env').read_text().splitlines():
            k, sep, value = line.partition('=')
            if sep and k.strip()==name: return value.strip().strip('"').strip("'")
    except FileNotFoundError: pass
    return ''

def cached_source(name, fetch):
    path = RUNTIME / 'cache' / (name+'.json')
    try:
        data = fetch()
        result = {'data': data, 'fetched_at': time.time(), 'ok': True}
        atomic_json(path, result)
        return result
    except Exception as exc:
        result = read_json(path, {'data': None, 'fetched_at': None})
        # Do not persist exception strings: HTTP errors can contain credentials/URLs.
        return {**result, 'ok': False, 'error': type(exc).__name__}
