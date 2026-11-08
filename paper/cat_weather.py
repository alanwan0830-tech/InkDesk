"""A monochrome, live cat-and-weather page for the 800 x 480 panel."""
from html import escape


def render_cat_weather(snapshot, now):
    from .render import Canvas, weather_label
    c = Canvas()
    weather = snapshot.get('weather') or {}
    data = weather.get('data') or {}
    current = data.get('current') or {}
    def text(x, y, value, size=20, anchor='start', weight=700):
        font = 'PingFang SC' if any(ord(ch)>0x4e00 for ch in str(value)) else 'Helvetica'
        c.parts.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')
    c.parts.append('<rect x="18" y="18" width="764" height="444" rx="12" fill="none" stroke="black" stroke-width="2"/><rect x="34" y="34" width="430" height="412" rx="16" fill="none" stroke="black" stroke-width="2"/>')
    text(56, 69, data.get('name', '北京海淀'), 22)
    text(440, 68, 'WEATHER / 04', 15, 'end')
    code = current.get('weather_code')
    c.icon(64, 108, code, current.get('is_day', 1), 2.2)
    text(120, 255, weather_label(code) if code is not None else '等待天气', 23, 'middle')
    temp = current.get('temperature_2m')
    text(443, 160, f'{temp:.1f}°' if isinstance(temp,(int,float)) else '--°', 65, 'end')
    text(440, 191, '当前温度', 18, 'end')
    text(232, 233, '湿度', 19)
    rh = current.get('relative_humidity_2m')
    text(440, 233, f'{rh}%' if rh is not None else '--', 25, 'end')
    text(232, 270, '风速', 19)
    wind = current.get('wind_speed_10m')
    text(440, 270, f'{wind:g} km/h' if isinstance(wind,(int,float)) else '--', 23, 'end')
    c.line(56, 295, 442, 295, 2)
    text(55, 369, now.strftime('%H:%M'), 66)
    text(441, 347, now.strftime('%m / %d'), 24, 'end')
    text(441, 378, ['MON','TUE','WED','THU','FRI','SAT','SUN'][now.weekday()], 24, 'end')
    text(56, 419, '慢慢来，喵。', 20)
    text(441, 419, '缓存天气' if not weather.get('ok') else 'HAIDIAN', 16, 'end')
    # Soft, asymmetric ears and broad cheeks keep the silhouette playful.
    c.parts.append('''<path d="M514 175 Q524 150 534 140 L531 78 Q548 79 579 119 Q609 111 645 118 Q675 80 692 82 L697 147 Q729 170 744 208 Q755 237 734 264 Q710 302 634 308 Q557 310 520 277 Q486 250 500 214Z" fill="black"/>
    <g fill="white"><ellipse cx="579" cy="207" rx="14" ry="19" transform="rotate(12 579 207)"/><ellipse cx="651" cy="203" rx="14" ry="19" transform="rotate(-8 651 203)"/>
    <path d="M606 234 Q615 225 624 233 Q619 244 614 244Z"/><path d="M614 251 Q598 264 603 276 Q614 284 624 274 Q627 263 614 251Z"/></g>
    <g fill="black"><ellipse cx="585" cy="204" rx="7" ry="11"/><ellipse cx="657" cy="200" rx="7" ry="11"/></g>
    <g stroke="white" stroke-width="6" stroke-linecap="round" fill="none"><path d="M543 238L564 243 M542 255L562 253 M676 238L697 232 M678 251L698 253"/></g>
    <g stroke="black" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" fill="none"><path d="M528 378L531 343L558 379L561 343 M586 345L601 362L616 343 M601 362L602 381 M641 381L654 344L671 380 M646 367L666 367 M702 362L719 362"/></g>''')
    text(625, 424, 'STAY COZY', 17, 'middle')
    return c.svg()
