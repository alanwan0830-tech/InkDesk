from pathlib import Path
from html import escape
P=Path(__file__).parent
s=['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" viewBox="0 0 800 480" role="img" aria-labelledby="title desc"><title id="title">Paper — desktop dashboard</title><desc id="desc">Static demo with Hong Kong and US markets, BTC, combined clock and weather, and simulated Codex attention and usage status.</desc><rect width="800" height="480" fill="white"/>']
def text(x,y,t,size=14,weight=400,anchor='start'):
 font='PingFang SC' if any(ord(c)>0x4e00 for c in str(t)) else ('Helvetica' if size<=15 else 'Courier New')
 weight=max(weight,700)
 s.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="black">{escape(str(t))}</text>')
def line(x,y,x2,y2,w=1):s.append(f'<path d="M{x} {y}H{x2}" stroke="black" stroke-width="{w}"/>' if y==y2 else f'<path d="M{x} {y}L{x2} {y2}" stroke="black" stroke-width="{w}"/>')
def rect(x,y,w,h,fill='black',stroke='none'):s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>')
def cloud(x,y,k=1):s.append(f'<g transform="translate({x} {y}) scale({k})"><path d="M5 27C-3 26-1 14 7 13C7 1 24-3 31 8C43 3 52 12 49 20C58 28 50 35 43 35H10C1 35-3 29 5 27Z" fill="black"/></g>')
def bars(x,y,values,width=198,height=32):
 for i,v in enumerate(values):rect(x+i*width/len(values),y+height-v*height,width/len(values)-2,v*height)
 line(x,y+height+3,x+width,y+height+3)
def spark(x,y,values):
 s.append('<polyline points="'+' '.join(f'{x+i*8},{y-v*.45}' for i,v in enumerate(values))+'" fill="none" stroke="black" stroke-width="2"/>')
def progress(x,y,p):
 rect(x,y,220,12,'white','black');rect(x+2,y+2,216*p,8)
 for a in range(1,10):line(x+a*22,y,x+a*22,y+12)
text(18,25,'PAPER / MARKET & MOMENT',13,700);text(782,25,'E1001   •   DEMO DATA',12,700,'end');line(18,37,782,37,2)
line(280,52,280,432);line(532,52,532,432)
# Grouped quote table restored from the selected reference.
text(18,67,'01 / MARKETS',14,700)
def section(y,label,currency):
 rect(18,y-13,244,22);s.append(f'<text x="25" y="{y+2}" font-family="Courier New" font-size="14" font-weight="700" fill="white">{label}</text>');s.append(f'<text x="255" y="{y+2}" text-anchor="end" font-family="Courier New" font-size="14" font-weight="700" fill="white">{currency}</text>')
def stock(y,name,ticker,price,change):
 text(20,y,name,16,700);text(260,y,price,20,700,'end');text(20,y+19,ticker,14,700);text(260,y+19,change,14,700,'end')
section(96,'HONG KONG','HKD')
stock(132,'小米集团','01810','52.80','+1.54%')
line(20,158,260,158)
stock(182,'美团','03690','108.60','-0.82%')
section(226,'UNITED STATES','USD')
stock(262,'QQQ','NASDAQ 100','615.42','+0.68%')
line(20,287,260,287)
stock(309,'特斯拉','TSLA','428.15','+2.13%')
line(20,334,260,334)
stock(356,'拼多多','PDD','126.80','-1.06%')
line(18,387,262,387,2)
stock(411,'BTC','USD / 24H','73,635','+2.41%')
# Time + weather share a single quiet column.
text(298,67,'02 / HERE & NOW',14,700)
# Dense square matrix: 8 x 12 digits, double-cell strokes, chamfered zero.
patterns={
 '2':['01111110','11111111','11000011','00000011','00000011','00001111','00111110','01111000','11100000','11000000','11111111','11111111'],
 '3':['01111110','11111111','00000011','00000011','00000111','00111110','00111110','00000111','00000011','00000011','11111111','01111110'],
 '0':['01111110','11111111','11000011','11000011','11000011','11000011','11000011','11000011','11000011','11000011','11111111','01111110'],
 '8':['01111110','11111111','11000011','11000011','11000011','01111110','01111110','11000011','11000011','11000011','11111111','01111110'],
 ':':['00','00','11','11','00','00','00','00','11','11','00','00']}
x=298
for ch in '23:08':
 for r,row in enumerate(patterns[ch]):
  for c,v in enumerate(row):
   if v=='1':rect(x+c*5.65,85+r*6.6,4.45,5.25)
 x+=(len(patterns[ch][0])+1)*5.65
text(298,193,'07 Nov 2026',16,700);text(514,193,'SAT',16,700,'end');line(298,213,514,213)
cloud(299,234,1.05);text(361,280,'24°',54,700);text(510,279,'C',20,700,'end');text(298,306,'PARTLY CLOUDY',15,700)
text(298,331,'RH 48%',15);text(514,331,'NW 8 km/h',15,400,'end')
line(298,347,514,347)
for x,h,temp in [(298,'00:00','22°'),(355,'03:00','21°'),(412,'06:00','20°'),(469,'09:00','23°')]:
 text(x,369,h,15,700);cloud(x+2,379,.62);text(x+19,430,temp,17,700,'middle')
# Codex notification-first hierarchy. This is a mock state, not a real approval.
text(550,67,'03 / CODEX',14,700);text(782,67,'DEMO',11,700,'end')
rect(550,84,232,62)
s.append('<text x="562" y="108" font-family="Helvetica" font-size="14" font-weight="700" fill="white">01 / NEEDS YOUR INPUT</text>')
s.append('<text x="562" y="134" font-family="PingFang SC,sans-serif" font-size="20" font-weight="700" fill="white">有 1 项需要你确认</text>')
text(550,173,'PAPER / 界面开发',15,700)
text(550,199,'样稿已完成，等待上屏确认',15)
text(550,222,'请返回 Codex 查看并回复',13)
line(550,240,782,240)
text(550,261,'TASKS',11,700)
text(550,289,'01',24,700);text(586,287,'待确认',13)
text(669,289,'02',24,700);text(705,287,'进行中',13)
line(550,305,782,305)
text(550,333,'CODEX USAGE',19,700)
text(550,359,'WEEK / 已用 21%',17,700)
text(550,382,'3天8小时后重置',16,700)
rect(550,392,232,12,'white','black');rect(551,393,230*.21,10)
line(550,414,782,414)
text(550,434,'更新 23:08 · 示例',14)
line(18,447,782,447,2);rect(18,459,7,7);text(32,467,'DEMO / 模拟数据',14,700);text(782,467,'800 × 480 / V0.6',14,700,'end')
s.append('</svg>');svg=''.join(s);(P/'paper-dashboard.svg').write_text(svg)
(P/'paper-dashboard.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Paper — E1001 static dashboard</title><style>*{box-sizing:border-box}html,body{margin:0;background:#fff}svg{display:block;width:800px;height:480px}@media(max-width:799px){svg{width:100vw;height:auto}}</style>'+svg+'</html>')
