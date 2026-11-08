from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import re
ROOT=Path(__file__).resolve().parent
TEXT='''永和九年，歲在癸丑，暮春之初，會於會稽山陰之蘭亭，修禊事也。群賢畢至，少長咸集。此地有崇山峻嶺，茂林修竹，又有清流激湍，映帶左右，引以為流觴曲水，列坐其次。雖無絲竹管弦之盛，一觴一詠，亦足以暢敘幽情。
是日也，天朗氣清，惠風和暢，仰觀宇宙之大，俯察品類之盛，所以遊目騁懷，足以極視聽之娛，信可樂也。
夫人之相與，俯仰一世，或取諸懷抱，悟言一室之內；或因寄所託，放浪形骸之外。雖趣舍萬殊，靜躁不同，當其欣於所遇，暫得於己，快然自足，不知老之將至。及其所之既倦，情隨事遷，感慨係之矣。向之所欣，俯仰之間，已為陳跡，猶不能不以之興懷。況修短隨化，終期於盡。古人云：死生亦大矣。豈不痛哉！
每覽昔人興感之由，若合一契，未嘗不臨文嗟悼，不能喻之於懷。固知一死生為虛誕，齊彭殤為妄作。後之視今，亦猶今之視昔，悲夫！故列敘時人，錄其所述，雖世殊事異，所以興懷，其致一也。後之覽者，亦將有感於斯文。'''
# Typesetting original text, not altering a reference photograph.
chars=[]
for c in TEXT:
 if '\u4e00'<=c<='\u9fff':chars.append([c,False])
 elif c in '。！？' and chars:chars[-1][1]=True
S=3
im=Image.new('L',(800*S,480*S),255);d=ImageDraw.Draw(im)
fontpath='/System/Library/Fonts/Supplemental/Songti.ttc'
body=ImageFont.truetype(fontpath,26*S,index=7)
title=ImageFont.truetype(fontpath,30*S,index=2)
small=ImageFont.truetype(fontpath,21*S,index=7)
def line(box,width=1):d.line(tuple(int(x*S) for x in box),fill=0,width=width*S)
for inset,width in [(11,2),(16,1)]:d.rectangle((inset*S,inset*S,(800-inset)*S,(480-inset)*S),outline=0,width=width*S)
def glyph(c,x,y,font):d.text((x*S,y*S),c,font=font,fill=0,anchor='mm')
# 24 body columns, 14 characters each, read right-to-left.
rows=14;colstep=29.6
assert len(chars)<=24*rows,(len(chars),24*rows)
for i,(c,stop) in enumerate(chars):
 col,row=divmod(i,rows);x=735-col*colstep;y=40+row*30.7
 glyph(c,x,y,body)
 if stop:d.ellipse(((x+11)*S,(y+9)*S,(x+13)*S,(y+11)*S),outline=0,width=S)
line((755,23,755,457))
for i,c in enumerate('蘭亭集序'):glyph(c,774,47+i*34,title)
for i,c in enumerate('晉王羲之'):glyph(c,774,335+i*27,small)
im=im.resize((800,480),Image.Resampling.LANCZOS)
im.point(lambda v:0 if v<170 else 255,mode='1').save(ROOT/'classical-lanting.png')
(ROOT/'classical-lanting.txt').write_text('蘭亭集序 · 王羲之\n\n'+TEXT)
print('characters',len(chars),'columns',(len(chars)+rows-1)//rows)
