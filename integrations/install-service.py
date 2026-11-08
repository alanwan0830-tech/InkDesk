"""Install Paper as the current user's launch agent; elevate only the plist copy."""
import os, plistlib, subprocess, sys, time
from pathlib import Path
root = Path(__file__).resolve().parent.parent
label = 'local.paper.dashboard'
plist = Path.home() / 'Library/LaunchAgents' / f'{label}.plist'
(root / 'runtime').mkdir(exist_ok=True)
env = {'PATH': '/opt/homebrew/bin:/usr/bin:/bin', 'DYLD_FALLBACK_LIBRARY_PATH': '/opt/homebrew/lib'}
for key in ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy', 'NO_PROXY', 'no_proxy']:
    if os.environ.get(key): env[key] = os.environ[key]
obj = {'Label': label, 'ProgramArguments': [str(root / '.venv/bin/python'), '-m', 'paper.server'],
       'WorkingDirectory': str(root), 'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 30,
       'EnvironmentVariables': env, 'StandardOutPath': str(root / 'runtime/service.log'),
       'StandardErrorPath': str(root / 'runtime/service.log')}
prepared = root / 'runtime' / f'{label}.plist'
# Preserve working network settings when reinstalling from a plain Terminal.
if prepared.exists():
    previous = plistlib.loads(prepared.read_bytes()).get('EnvironmentVariables', {})
    for key, value in previous.items(): env.setdefault(key, value)
prepared.write_bytes(plistlib.dumps(obj)); prepared.chmod(0o600)
if '--prepare' in sys.argv:
    print('登录启动配置已准备好。'); sys.exit(0)
plist.parent.mkdir(parents=True, exist_ok=True)
try:
    plist.write_bytes(prepared.read_bytes()); plist.chmod(0o600)
except PermissionError:
    if not sys.stdin.isatty():
        raise SystemExit('请双击 Install Paper Autostart.command，在本机输入管理员密码完成安装。')
    print('安装需要管理员权限；密码只由 macOS 验证，不会保存。', flush=True)
    subprocess.run(['sudo', '/usr/bin/install', '-m', '600', '-o', str(os.getuid()),
                    str(prepared), str(plist)], check=True)
uid = os.getuid()
subprocess.run(['launchctl', 'bootout', f'gui/{uid}/{label}'], capture_output=True)
r = subprocess.run(['lsof', '-tiTCP:8766', '-sTCP:LISTEN'], text=True, capture_output=True)
for pid in r.stdout.split():
    command = subprocess.run(['ps', '-p', pid, '-o', 'command='], text=True, capture_output=True).stdout
    if '-m paper.server' in command: os.kill(int(pid), 15)
subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(plist)], check=True)
from urllib.request import urlopen
for _ in range(30):
    try:
        with urlopen('http://127.0.0.1:8766/status.json', timeout=2) as response:
            if response.status == 200:
                print('安装成功：Paper 已在后台运行，以后登录 Mac 会自动启动。'); break
    except OSError: pass
    time.sleep(1)
else: raise SystemExit('启动未验证成功，请查看 runtime/service.log。')
