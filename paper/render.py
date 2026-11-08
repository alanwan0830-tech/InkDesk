from __future__ import annotations
import io, math, os, tempfile
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import cairosvg
from PIL import Image
from .common import RUNTIME
from .data import forecast_hours, number

# Square dots with double-dot strokes, as approved on the physical device.
GLYPHS={
'0':['01111110','11111111']+['11000011']*8+['11111111','01111110'],
'1':['00001100','00011100','00111100','00001100','00001100','00001100','00001100','00001100','00001100','00001100','00111111','00111111'],
'2':['01111110','11111111','11000011','00000011','00000011','00001111','00111110','01111000','11100000','11000000','11111111','11111111'],
'3':['01111110','11111111','00000011','00000011','00000111','00111110','00111110','00000111','00000011','00000011','11111111','01111110'],
'4':['11000011']*5+['11111111']*2+['00000011']*5,
'5':['11111111','11111111','11000000','11000000','11111110','11111111','00000011','00000011','00000011','11000011','11111111','01111110'],
'6':['01111110','11111111','11000000','11000000','11111110','11111111','11000011','11000011','11000011','11000011','11111111','01111110'],
'7':['11111111','11111111','00000011','00000110','00000110','00001100','00001100','00011000','00011000','00110000','00110000','00110000'],
'8':['01111110','11111111','11000011','11000011','11000011','01111110','01111110','11000011','11000011','11000011','11111111','01111110'],
'9':['01111110','11111111','11000011','11000011','11000011','11111111','01111111','00000011','00000011','00000011','11111111','01111110'],
':':['00','00','11','11','00','00','00','00','11','11','00','00']}

class Canvas:
    def __init__(self):self.parts=['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" viewBox="0 0 800 480"><rect width="800" height="480" fill="white"/>']
    def text(self,x,y,value,size=14,anchor='start',color='black'):
        font='PingFang SC' if any(ord(c)>0x4e00 for c in str(value)) else ('Helvetica' if size<=15 else 'Courier New')
        self.parts.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="700" text-anchor="{anchor}" fill="{color}">{escape(str(value))}</text>')
    def rect(self,x,y,w,h,fill='black',stroke='none'):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{max(0,w)}" height="{max(0,h)}" fill="{fill}" stroke="{stroke}"/>')
    def line(self,x,y,x2,y2,width=1):self.parts.append(f'<path d="M{x} {y}L{x2} {y2}" stroke="black" stroke-width="{width}"/>')
    def icon(self,x,y,code,day=1,scale=1):
        self.parts.append(f'<g transform="translate({x} {y}) scale({scale})">')
        if code is None:self.text(15,28,'?',30)
        elif code==0:
            if day:
                self.parts.append('<circle cx="25" cy="23" r="12" fill="black"/>')
                for deg in range(0,360,45):
                    r=math.radians(deg);self.line(25+16*math.cos(r),23+16*math.sin(r),25+22*math.cos(r),23+22*math.sin(r),2)
            else:self.parts.append('<path d="M32 3A21 21 0 1 0 45 35A23 23 0 0 1 32 3Z" fill="black"/>')
        else:
            self.parts.append('<path d="M5 27C-3 26-1 14 7 13C7 1 24-3 31 8C43 3 52 12 49 20C58 28 50 35 43 35H10C1 35-3 29 5 27Z" fill="black"/>')
            if code in [45,48]:
                self.line(4,40,49,40,2);self.line(10,45,43,45,2)
            elif code>=95:self.parts.append('<path d="M25 30L17 43H26L21 54L38 37H28L32 30Z" fill="black"/>')
            elif 71<=code<=77 or code in (85,86):
                for dx in [10,26,42]:self.text(dx,49,'*',20)
            elif code>=51:
                for dx in [10,26,42]:self.line(dx,39,dx-4,48,2)
        self.parts.append('</g>')
    def svg(self):return ''.join(self.parts)+'</svg>'

def weather_label(code):
    if code==0:return '晴'
    if code in (1,2):return '多云'
    if code==3:return '阴'
    if code in (45,48):return '有雾'
    if code in (56,57,66,67):return '冻雨'
    if 51<=code<=65:return '有雨'
    if 71<=code<=77 or code in (85,86):return '有雪'
    if 80<=code<=82:return '阵雨'
    if code>=95:return '雷雨'
    return '暂无天气'

def reset_label(epoch,now):
    if not number(epoch):return '重置时间暂无'
    delta=int(epoch-now.timestamp())
    if delta<=0:return '已到重置时间 · 待更新'
    days=delta//86400;hours=delta//3600%24;mins=delta//60%60
    return f'{days}天{hours}小时后重置' if days else (f'{hours}小时{mins}分后重置' if hours else f'{max(1,mins)}分钟后重置')

def render_svg(snapshot,now):
    c=Canvas();t=c.text;l=c.line;r=c.rect
    t(18,25,'PAPER / MARKET & MOMENT',13);t(782,25,'E1001 / LIVE',13,'end');l(18,37,782,37,2)
    l(280,52,280,432);l(532,52,532,432)
    t(18,67,'01 / MARKETS',14)
    def section(y,label,currency):
        r(18,y-13,244,22);t(25,y+2,label,14,color='white');t(255,y+2,currency,14,'end','white')
    section(96,'HONG KONG','HKD');section(226,'UNITED STATES','USD')
    rows=snapshot.get('quotes',[])
    fallback=[('小米集团','01810'),('美团','03690'),('QQQ','NASDAQ 100'),('特斯拉','TSLA'),('拼多多','PDD'),('BTC','USD / 24H')]
    for i,y in enumerate([132,182,262,309,356,411]):
        q=rows[i] if i<len(rows) else {};d=q.get('data') or {};price=d.get('price');change=d.get('change')
        t(20,y,q.get('name',fallback[i][0]),16)
        t(260,y,(f'{price:,.0f}' if i==5 else f'{price:,.2f}') if number(price) else '--',20,'end')
        ticker=q.get('ticker',fallback[i][1])
        if not q.get('ok'):ticker='缓存 · '+ticker if d else '暂无数据'
        t(20,y+19,ticker,14)
        t(260,y+19,f'{change:+.2f}%' if number(change) else '--',14,'end')
    for y in [158,287,334]:l(20,y,260,y)
    l(18,387,262,387,2)
    w=snapshot.get('weather',{});wd=w.get('data') or {};cur=wd.get('current') or {}
    t(298,67,wd.get('name','北京海淀'),16)
    x=298
    for ch in now.strftime('%H:%M'):
        for yy,row in enumerate(GLYPHS[ch]):
            for xx,v in enumerate(row):
                if v=='1':r(x+xx*5.65,85+yy*6.6,4.45,5.25)
        x+=(len(GLYPHS[ch][0])+1)*5.65
    t(298,193,now.strftime('%d %b %Y'),16);t(514,193,['MON','TUE','WED','THU','FRI','SAT','SUN'][now.weekday()],16,'end');l(298,213,514,213)
    code=cur.get('weather_code');c.icon(299,234,code,cur.get('is_day',1))
    temp=cur.get('temperature_2m');t(361,280,f'{round(temp)}°' if number(temp) else '--',54);t(510,279,'C',20,'end')
    label=weather_label(code) if number(code) else '天气暂不可用'
    if wd and not w.get('ok'):label+=' · 缓存'
    t(298,306,label,18)
    humidity=cur.get('relative_humidity_2m');wind=cur.get('wind_speed_10m');direction=cur.get('wind_direction_10m')
    compass=['N','NE','E','SE','S','SW','W','NW'][int((direction+22.5)//45)%8] if number(direction) else '--'
    t(298,331,f'RH {round(humidity)}%' if number(humidity) else 'RH --',15)
    t(514,331,f'{compass} {round(wind)} km/h' if number(wind) else '-- km/h',15,'end');l(298,347,514,347)
    hours=forecast_hours(wd,now) if wd else []
    for i,x in enumerate([298,355,412,469]):
        f=hours[i] if i<len(hours) else {};t(x,369,f.get('time','--:--'),15)
        c.icon(x+2,379,f.get('code'),f.get('is_day',1),.62);t(x+19,430,f"{round(f['temperature'])}°" if f else '--',17,'middle')
    # Event state is never fabricated from saved transcripts or an isolated server.
    tasks=snapshot.get('tasks') or {};sel=tasks.get('selected') or {};state=sel.get('state','disconnected')
    states={
      'approval':('NEEDS APPROVAL','需要你批准','请回 Codex 查看权限请求'),
      'input':('NEEDS YOUR INPUT','等待你的回复','请回 Codex 回答问题'),
      'error':('TASK ERROR','任务出现异常','请回 Codex 查看错误'),
      'running':('WORKING','Codex 正在执行','正在处理当前请求'),
      'completed':('TURN FINISHED','本轮执行结束','结果已在 Codex 中可查看'),
      'interrupted':('INTERRUPTED','本轮已中断','可回 Codex 继续'),
      'idle':('READY','Codex 已就绪','等待新的请求'),
      'stale':('STATUS STALE','状态待更新','长时间没有收到新事件'),
      'disconnected':('NOT CONNECTED','任务通知未连接','需启用 Codex 通知钩子')}
    heading,title,body=states.get(state,states['disconnected'])
    t(550,67,'03 / CODEX',14);r(550,84,232,62)
    t(562,108,heading,14,color='white');t(562,134,title,20,color='white')
    project=sel.get('project','Paper');t(550,173,('PROJECT / '+project)[:23],15)
    t(550,199,body,16);t(550,222,'任务摘要仅显示项目名',14)
    l(550,240,782,240);t(550,261,'TASKS / 本项目',14)
    t(550,289,f"{tasks.get('attention',0):02}" if tasks.get('connected') else '--',24);t(586,287,'待处理',14)
    t(669,289,f"{tasks.get('running',0):02}" if tasks.get('connected') else '--',24);t(705,287,'进行中',14);l(550,305,782,305)
    t(550,333,'CODEX USAGE',19)
    usage=snapshot.get('usage',{});ud=usage.get('data') or {};used=ud.get('used')
    t(550,359,f'WEEK / 已用 {used:g}%' if number(used) else 'WEEK / 暂无数据',17)
    reset=reset_label(ud.get('resets_at'),now) if ud else '等待账户额度更新'
    if ud and not usage.get('ok'):reset='缓存 · '+reset
    t(550,382,reset,15 if len(reset)>14 else 16)
    r(550,392,232,12,'white','black')
    if number(used):r(551,393,230*max(0,min(100,used))/100,10)
    l(550,414,782,414)
    at=tasks.get('last_event_at');t(550,434,'事件 '+datetime.fromtimestamp(at,now.tzinfo).strftime('%H:%M') if at else '尚未收到任务事件',14)
    l(18,447,782,447,2)
    failed=any(not q.get('ok') for q in rows) or not w.get('ok') or not usage.get('ok')
    t(18,469,'更新 '+now.strftime('%H:%M')+(' · 部分数据离线' if failed else ' · 行情可能延迟'),13)
    # Expose quote date to distinguish closed-market data from a stalled refresh.
    hk=(rows[0].get('data') or {}).get('quote_at') if rows else None
    us=(rows[2].get('data') or {}).get('quote_at') if len(rows)>2 else None
    fmt=lambda v:datetime.fromtimestamp(v,ZoneInfo('Asia/Shanghai')).strftime('%m/%d') if v else '--'
    t(782,469,f'HK {fmt(hk)} / US {fmt(us)}',13,'end')
    return c.svg()

def write_frame(snapshot,now):
    svg=render_svg(snapshot,now);png=cairosvg.svg2png(bytestring=svg.encode())
    im=Image.open(io.BytesIO(png)).convert('L').point(lambda v:255 if v>=150 else 0).convert('1',dither=Image.Dither.NONE)
    out=io.BytesIO();im.save(out,format='PNG');blob=out.getvalue()
    RUNTIME.mkdir(parents=True,exist_ok=True)
    from .cat_weather import render_cat_weather
    cat_svg=render_cat_weather(snapshot,now)
    cat_im=Image.open(io.BytesIO(cairosvg.svg2png(bytestring=cat_svg.encode()))).convert('L').point(lambda v:255 if v>=150 else 0).convert('1',dither=Image.Dither.NONE)
    cat_out=io.BytesIO();cat_im.save(cat_out,format='PNG')
    for name,data in [('dashboard.svg',svg.encode()),('dashboard.png',blob),('cat-weather.svg',cat_svg.encode()),('cat-weather.png',cat_out.getvalue())]:
        fd,tmp=tempfile.mkstemp(dir=RUNTIME)
        with os.fdopen(fd,'wb') as f:f.write(data)
        os.replace(tmp,RUNTIME/name)
    return blob
