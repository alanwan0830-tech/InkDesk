"""SenseCraft client using vendor-documented routes. No browser cookies or JWTs."""
from __future__ import annotations
import base64, hashlib, time
from urllib.parse import urlparse
import requests
from .common import RUNTIME, atomic_json, read_json, env_value
BASE='https://sensecraft-hmi-api.seeed.cc'

class DeviceNotAwake(RuntimeError):
    """Defer replacement until the device is online; retain its current image."""

class HmiClient:
    def __init__(self):
        self.key=env_value('HMI_API_KEY')
        if not self.key:raise ValueError('HMI_API_KEY is not configured')
    def request(self,method,path,data=None):
        response=requests.request(method,BASE+path,json=data,headers={'api-key':self.key},timeout=(8,30))
        response.raise_for_status();body=response.json()
        if body.get('code') not in (0,200,None):raise RuntimeError('SenseCraft error code '+str(body.get('code')))
        return body.get('result',body)
    def device(self,device_id):
        data=self.request('GET','/api/v2/user/device/list')
        if isinstance(data,dict):data=data.get('list') or data.get('devices') or data.get('data') or []
        matches=[d for d in data if str(d.get('id'))==str(device_id)]
        if len(matches)!=1:raise ValueError('Configured Paper device not found')
        return matches[0]
    def require_awake(self,device):
        seen=device.get('last_seen',0)
        try:age=time.time()-float(seen)/1000
        except (TypeError,ValueError):age=999
        if device.get('online_status')!=1 or not 0<=age<=90:
            raise DeviceNotAwake('Waiting for a fresh online device report')

    def deploy_once(self,png,device_id):
        """Publish a new frame using documented creation/downlink endpoints.

        Keep three application-owned frames. Never delete pre-existing user designs.
        """
        path=RUNTIME/'hmi.json';state=read_json(path,{})
        if state and (state.get('owner')!='paper-dashboard' or state.get('device_id')!=device_id):
            raise ValueError('Deployment manifest does not match this device')
        state.update(owner='paper-dashboard',device_id=device_id)
        device=self.device(device_id);mac=device['mac_address']
        if state.get('publish_only_when_awake'):self.require_awake(device)
        if not state.get('playlist_id'):
            result=self.request('POST','/api/v2/user/playlist',{'name':'Paper Live','mac_address':mac})
            state['playlist_id']=result['id'];atomic_json(path,state)
        image=self.request('POST','/api/v1/oss/upload',{'image_data':base64.b64encode(png).decode(),'file_name':'paper-live.png'})
        if isinstance(image,str):url=image
        else:url=next((image[k] for k in ['url','image_url','file_url'] if image.get(k)),None)
        if not url or urlparse(url).scheme!='https':raise ValueError('Invalid upload URL')
        page=self.request('POST','/api/v2/user/page',{'mac_address':mac,'pages':[{'type':'img','name':'Paper Live','data':url,'thumbnail':url,'dither':0}]})
        page_id=page.get('id') or (page.get('ids') or [None])[0]
        if not page_id:raise ValueError('Missing page ID')
        state.setdefault('owned_page_ids',[]).append(page_id);state['pending_page_id']=page_id;atomic_json(path,state)
        protected=list(dict.fromkeys(state.get('extra_page_ids',[])))
        if state.get('cat_screen_enabled'):
            cat_png=(RUNTIME/'cat-weather.png').read_bytes()
            image=self.request('POST','/api/v1/oss/upload',{'image_data':base64.b64encode(cat_png).decode(),'file_name':'paper-cat-weather.png'})
            url=image if isinstance(image,str) else next((image[k] for k in ['url','image_url','file_url'] if image.get(k)),None)
            if not url or urlparse(url).scheme!='https':raise ValueError('Invalid cat upload URL')
            cat=self.request('POST','/api/v2/user/page',{'mac_address':mac,'pages':[{'type':'img','name':'Paper / Nya Weather','data':url,'thumbnail':url,'dither':0}]})
            cat_id=cat.get('id') or (cat.get('ids') or [None])[0]
            if not cat_id:raise ValueError('Missing cat page ID')
            state['owned_page_ids'].append(cat_id)
            state['cat_page_id']=cat_id
            atomic_json(path,state)
            protected.append(cat_id)
        pages=[{'id':page_id,'sort':0}]+[{'id':pid,'sort':i+1} for i,pid in enumerate(protected) if pid!=page_id]
        if state.get('publish_only_when_awake'):self.require_awake(self.device(device_id))
        self.request('POST','/api/v2/user/playlist/upsert_pages',{'playlist_id':state['playlist_id'],'pages':pages})
        deployed=self.request('POST','/api/v2/user/device/deploy',{'mode':'refresh','playlist_id':state['playlist_id'],'mac_addresses':[mac]})
        if not isinstance(deployed,dict) or not any(
                row.get('mac_address')==mac and row.get('playlist_id')==state['playlist_id']
                for row in deployed.get('devices',[])):
            raise ValueError('Deployment response did not confirm the target device')
        state.update(page_id=page_id,last_sent_at=time.time(),last_sha256=hashlib.sha256(png).hexdigest());state.pop('pending_page_id',None);atomic_json(path,state)
        # Reclaim only IDs created by this service and retained in its manifest.
        # Cleanup failure never rolls back the latest good screen.
        for old_id in ([] if state.get('retain_uploaded_pages') else list(state.get('owned_page_ids',[]))[:-3]):
            if old_id==page_id or old_id in protected or old_id in state.get('archived_page_ids',[]):continue
            try:
                self.request('DELETE','/api/v2/user/page',{'id':old_id,'mac_address':mac})
                state['owned_page_ids'].remove(old_id);atomic_json(path,state)
            except Exception:break
        return {'submitted':True,'page_id':page_id}
