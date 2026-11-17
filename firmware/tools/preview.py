"""Render firmware-owned text with its actual GFX font and dot geometry on the Mac."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import re
import subprocess
import time
from PIL import Image,ImageDraw,ImageChops
from paper.firmware_bridge import frame_packet
from paper.render import GLYPHS

font=ROOT/'firmware/.pio/libdeps/paper_e1001/Seeed_GFX/Fonts/Font16.c'
source=subprocess.check_output(['c++','-E','-P','-DPROGMEM=','-x','c++',str(font)],text=True)
def values(name):
    match=re.search(r'\b'+name+r'\[.*?\].*?\{(.*?)\}',source,re.S)
    return [int(v,0) for v in re.findall(r'0x[0-9a-fA-F]+|\b\d+\b',match[1])]
widths=values('widtbl_f16')
def text(draw,x,y,value):
    for char in value:
        width=widths[ord(char)-32];rowbytes=(width+6)//8
        glyph=values(f'chr_f16_{ord(char):02X}')
        draw.rectangle((x,y,x+width-1,y+15),fill=1)
        for row in range(16):
            for col in range(rowbytes*8):
                if glyph[row*rowbytes+col//8] & (128>>(col%8)):
                    draw.point((x+col,y+row),fill=0)
        x+=width

snapshot_path=ROOT/'runtime/snapshot.json'
snapshot=json.loads(snapshot_path.read_text())
now=int(time.time());stamp=int(snapshot_path.stat().st_mtime)
packet=frame_packet(snapshot,now,stamp)
def preview(epoch):
    im=Image.frombytes('1',(800,480),packet[24:]);draw=ImageDraw.Draw(im)
    local=datetime.fromtimestamp(epoch,ZoneInfo('Asia/Shanghai'));x=298.0
    for char in local.strftime('%H:%M'):
        for y,row in enumerate(GLYPHS[char]):
            for col,on in enumerate(row):
                if on=='1':
                    px=int(x+col*5.65+0.5);py=int(85+y*6.6+0.5)
                    draw.rectangle((px,py,px+3,py+4),fill=0)
        x+=(len(GLYPHS[char][0])+1)*5.65
    text(draw,298,179,local.strftime('%d %b %Y  %a'))
    fetched=datetime.fromtimestamp(stamp,ZoneInfo('Asia/Shanghai'))
    text(draw,18,452,'DATA '+fetched.strftime('%m/%d %H:%M')+(' / CACHED' if epoch-stamp>600 else '')+(' / OFFLINE' if packet[16] else ''))
    return im

out=ROOT/'runtime/firmware-preview';out.mkdir(exist_ok=True)
first,second=preview(now),preview(now+60)
first.save(out/'dashboard.png');second.save(out/'minute-later.png')
diff=ImageChops.difference(first.convert('L'),second.convert('L'))
diff.save(out/'minute-difference.png')
(out/'preview.json').write_text(json.dumps({'simulated_at':now,'source_at':stamp,'minute_change_bounds':diff.getbbox(),'hardware_verified':False},indent=2))
print(out/'dashboard.png');print('One-minute change bounds:',diff.getbbox())
