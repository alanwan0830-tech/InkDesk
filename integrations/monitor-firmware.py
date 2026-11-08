"""Passive serial observation; never toggles RTS/DTR or sends a command."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from pathlib import Path
import re
import select
import subprocess
import termios
import time

parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=180);args=parser.parse_args()
port='/dev/cu.usbserial-210'
if subprocess.run(['lsof',port],capture_output=True).returncode==0:raise SystemExit('Serial port occupied')
root=Path(__file__).resolve().parents[1];directory=root/'runtime/firmware-monitor';directory.mkdir(exist_ok=True,mode=0o700)
stamp=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')
raw=directory/f'{stamp}.log';summary=directory/f'{stamp}-summary.log'
fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
settings=termios.tcgetattr(fd)
settings[0]=0;settings[1]=0;settings[2]=termios.CS8|termios.CREAD|termios.CLOCAL;settings[3]=0
settings[4]=termios.B115200;settings[5]=termios.B115200
settings[6][termios.VMIN]=0;settings[6][termios.VTIME]=0
termios.tcsetattr(fd,termios.TCSANOW,settings)
out=os.open(raw,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
clean=os.open(summary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
allowed=re.compile(r'Manual page|Button |Paper firmware|Full refresh|Partial complete|Frame committed|Panel BUSY|Display failed|First-screen|Keeping cached|Memory unavailable|PSRAM unavailable|rst:|boot:|Guru Meditation|Brownout|assert failed')
end=time.monotonic()+args.seconds;buffer=b''
print(f'Passive monitor: {summary}',flush=True)
try:
    while time.monotonic()<end:
        if not select.select([fd],[],[],1)[0]:continue
        try:data=os.read(fd,16384)
        except BlockingIOError:continue
        os.write(out,data);buffer+=data
        while b'\n' in buffer:
            line,buffer=buffer.split(b'\n',1);line=line.decode('utf-8','replace').strip()
            if allowed.search(line):
                text=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%H:%M:%S')+' '+line+'\n'
                os.write(clean,text.encode());print(text,end='',flush=True)
finally:
    os.close(out);os.close(clean);os.close(fd)
