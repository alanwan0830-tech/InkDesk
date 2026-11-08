from __future__ import annotations
import math, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from .common import cached_source

STOCKS = [('1810.HK','小米集团','01810','HKD'),('3690.HK','美团','03690','HKD'),
          ('QQQ','QQQ','NASDAQ 100','USD'),('TSLA','特斯拉','TSLA','USD'),('PDD','拼多多','PDD','USD')]

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def get_json(url, params=None):
    response=requests.get(url, params=params, timeout=(8,15), headers={'User-Agent':'Mozilla/5.0 PaperDashboard/0.1'})
    response.raise_for_status()
    return response.json()

def parse_yahoo(payload, symbol, currency):
    chart=payload.get('chart',{})
    if chart.get('error') or not chart.get('result'): raise ValueError('Missing quote')
    item=chart['result'][0]; meta=item['meta']; price=meta.get('regularMarketPrice')
    if not number(price) or price<=0 or meta.get('currency')!=currency: raise ValueError('Invalid quote/currency')
    change=meta.get('regularMarketChangePercent')
    # chartPreviousClose is the first day of the selected range, NOT yesterday.
    if not number(change):
        close=meta.get('previousClose')
        if not number(close):
            stamps=item.get('timestamp',[]); closes=item.get('indicators',{}).get('quote',[{}])[0].get('close',[])
            tz=ZoneInfo(meta.get('exchangeTimezoneName','UTC'))
            market_day=datetime.fromtimestamp(meta['regularMarketTime'],tz).date()
            candidates=[c for t,c in zip(stamps,closes) if number(c) and datetime.fromtimestamp(t,tz).date()<market_day]
            close=candidates[-1] if candidates else None
        change=(price/close-1)*100 if number(close) and close>0 else None
    at=meta.get('regularMarketTime')
    if not number(at): raise ValueError('Missing quote time')
    return {'symbol':symbol,'price':price,'change':change,'currency':currency,'quote_at':at,'source':'Yahoo Finance'}

def fetch_stock(row):
    symbol,name,ticker,currency=row
    result=cached_source('quote_'+symbol, lambda:parse_yahoo(get_json('https://query1.finance.yahoo.com/v8/finance/chart/'+symbol,{'interval':'1d','range':'5d'}),symbol,currency))
    return {**result,'name':name,'ticker':ticker,'currency':currency,'symbol':symbol}

def fetch_btc():
    def fetch():
        d=get_json('https://api.exchange.coinbase.com/products/BTC-USD/stats')
        price=float(d['last']); opened=float(d['open'])
        if not number(price) or price<=0 or opened<=0:raise ValueError('Invalid BTC price')
        return {'symbol':'BTC-USD','price':price,'change':(price/opened-1)*100,'quote_at':time.time(),'currency':'USD','source':'Coinbase','period':'24h'}
    return {**cached_source('quote_BTC',fetch),'name':'BTC','ticker':'USD / 24H','currency':'USD','symbol':'BTC-USD'}

def quotes():
    with ThreadPoolExecutor(max_workers=6) as pool:
        stocks=list(pool.map(fetch_stock,STOCKS)); btc=pool.submit(fetch_btc).result()
    return stocks+[btc]

def weather(settings):
    def fetch():
        d=get_json('https://api.open-meteo.com/v1/forecast',{
          'latitude':settings['latitude'],'longitude':settings['longitude'],'timezone':'Asia/Shanghai',
          'current':'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,is_day',
          'hourly':'temperature_2m,weather_code,is_day','forecast_days':2})
        current=d['current']; hourly=d['hourly']
        if not number(current.get('temperature_2m')):raise ValueError('Missing weather')
        return {'current':current,'hourly':hourly,'source':'Open-Meteo','name':settings['name']}
    return cached_source('weather',fetch)

def forecast_hours(data, now):
    hourly=data['hourly']; result=[]; last=None
    for i,value in enumerate(hourly['time']):
        dt=datetime.fromisoformat(value).replace(tzinfo=now.tzinfo)
        if dt<=now or (last is not None and (dt-last).total_seconds()<3*3600):continue
        temp=hourly['temperature_2m'][i]
        if not number(temp):continue
        result.append({'time':dt.strftime('%H:%M'),'temperature':temp,'code':hourly['weather_code'][i],'is_day':hourly.get('is_day',[1]*len(hourly['time']))[i]})
        last=dt
        if len(result)==4:break
    return result
