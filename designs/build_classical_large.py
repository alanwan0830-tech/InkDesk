"""Large vertical letterpress-style typesetting for E1001, Lanting excerpt."""
from pathlib import Path
import ast
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent
module=ast.parse((ROOT/'build_classical.py').read_text())
full=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TEXT' for t in n.targets))
text=full.split('夫人之相與')[0].strip()
chars=[]
for c in text:
 if '\u4e00'<=c<='\u9fff':chars.append([c,False])
 elif c in '。！？' and chars:chars[-1][1]=True
S=4
im=Image.new('L',(800*S,480*S),255);d=ImageDraw.Draw(im)
fp='/System/Library/Fonts/Supplemental/Songti.ttc'
def font(size,bold=False):return ImageFont.truetype(fp,round(size*S),index=2 if bold else 7)
def line(x,y,x2,y2,w=1):d.line((round(x*S),round(y*S),round(x2*S),round(y2*S)),fill=0,width=max(1,round(w*S)))
def rect(box,w=1):d.rectangle(tuple(round(v*S) for v in box),outline=0,width=max(1,round(w*S)))
def glyph(c,x,y,size,bold=False):d.text((round(x*S),round(y*S)),c,font=font(size,bold),fill=0,anchor='mm')
rect((12,12,788,468),2);rect((19,19,781,461),.8)
# 14 ruled columns of nine large characters; separate full-height title panel.
left=27;right=671;top=28;bottom=452
line(left,top,right,top,1);line(left,bottom,right,bottom,1)
for col in range(15):
 x=left+46*col
 line(x,top,x,bottom,.8 if col not in (0,14) else 1.2)
for i,(c,stop) in enumerate(chars):
 col,row=divmod(i,9);x=right-23-col*46;y=53+row*46.5
 glyph(c,x,y,37)
 if stop:d.ellipse(((x+17)*S,(y+13)*S,(x+19.5)*S,(y+15.5)*S),outline=0,width=3)
# Title, attribution, and a small monochrome engraved-style chapter mark.
for i,c in enumerate('蘭亭集序'):glyph(c,742,67+i*66,52,True)
for i,c in enumerate('晉王羲之'):glyph(c,695,116+i*27,21)
line(687,312,765,312,.8)
for i,c in enumerate('暮春修禊'):glyph(c,747,339+i*27,22)
for i,c in enumerate('節選'):glyph(c,695,341+i*25,19)
rect((684,403,710,443),1)
glyph('永',697,414,17);glyph('和',697,433,17)
im=im.resize((800,480),Image.Resampling.LANCZOS)
im.point(lambda v:0 if v<170 else 255,mode='1').save(ROOT/'classical-lanting-large.png')
(ROOT/'classical-lanting-large.txt').write_text('蘭亭集序 · 王羲之（開篇節選）\n\n'+text)
print('body:37px; title:52px; excerpt:',len(chars),'characters')
