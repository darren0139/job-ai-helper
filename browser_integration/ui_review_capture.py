"""Session-owned controlled Firefox captures. No extension, DB or external calls."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
import uuid
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image


def section_ranges(height, size=1800, overlap=80):
    if height<1 or not 1500<=size<=2000 or not 0<=overlap<size:raise ValueError('Invalid section geometry')
    ranges=[];start=0
    while start<height:
        end=min(height,start+size);ranges.append((start,end))
        if end==height:break
        start=end-overlap
    return ranges


def image_files(data):
    with Image.open(BytesIO(data)) as image:
        if image.width*image.height>70_000_000:raise ValueError('Capture pixel bound exceeded')
        width,height=image.size;files={'full.png':data};sections=[]
        for i,(a,b) in enumerate(section_ranges(height),1):
            name=f'sections/{i:03}.png';buffer=BytesIO();image.crop((0,a,width,b)).save(buffer,format='PNG')
            files[name]=buffer.getvalue();sections.append({'name':name,'sha256':sha256(files[name]).hexdigest(),'coordinates':[0,a,width,b]})
    return files,{'dimensions':[width,height],'sha256':sha256(data).hexdigest(),'sections':sections}


class CaptureSession:
    def __init__(self):
        self.id=uuid.uuid4().hex;self.pool=ThreadPoolExecutor(max_workers=1);self.views=[];self.errors=[];self.sequence=0;self.active=False;self.future=None

    def call(self,fn):
        if self.future and not self.future.done():raise RuntimeError('Capture browser is busy; wait before retrying.')
        self.future=self.pool.submit(fn)
        return self.future.result(timeout=120)

    def start(self,url):
        parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Use a plain local application URL without credentials, query or fragment.')
        if self.active:raise RuntimeError('End the current session before starting another.')
        def launch():
            from playwright.sync_api import sync_playwright
            self.runtime=sync_playwright().start()
            try:
                self.browser=self.runtime.firefox.launch(headless=False)
                self.page=self.browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
                # Restrict the controlled review browser to local app surfaces.
                self.page.route('**/*',lambda route:route.continue_() if urlsplit(route.request.url).hostname in ('127.0.0.1','localhost','::1') else route.abort())
                self.page.goto(url,wait_until='domcontentloaded');self.active=True
            except Exception:
                self.runtime.stop();raise
        self.call(launch)

    def capture(self,name,notes='',visible=False,sidebar=False,replace=None):
        if not self.active:raise RuntimeError('Start a capture session first.')
        if len(self.views)>=20 and replace is None:raise ValueError('Session limited to 20 captured views.')
        if len(name)>120 or len(notes)>2000:raise ValueError('Capture name/notes exceed bounds.')
        def grab():
            from browser_integration.ui_review_scroll import _capture
            page=self.page
            if page.is_closed():raise RuntimeError('Controlled Firefox tab closed. End and start a new capture session.')
            if urlsplit(page.url).hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('Controlled tab left the local application.')
            page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=30000)
            state=page.evaluate("""()=>({scroll:document.querySelector('[data-testid=stMain]')?.scrollTop||0,height:document.querySelector('[data-testid=stMain]')?.scrollHeight,headings:[...document.querySelectorAll('h1,h2,h3')].filter(e=>e.getClientRects().length).map(e=>e.innerText).slice(0,25),tabs:[...document.querySelectorAll('[role=tab][aria-selected=true]')].map(e=>e.innerText),selectors:[...document.querySelectorAll('[data-testid=stSelectbox]')].map(e=>({label:e.querySelector('label')?.innerText,value:e.innerText.replace(e.querySelector('label')?.innerText||'','').trim()})).filter(e=>e.label&&/project|wording|Case|dataset/i.test(e.label))})""")
            style=page.add_style_tag(content='header[data-testid="stHeader"]{visibility:hidden!important}')
            redacted=page.evaluate("""()=>{window.__reviewSecretPanels=[];for(const e of document.querySelectorAll('[data-testid=stExpander]')){const summary=e.querySelector('summary');if(summary&&/extension pairing|api key|session secret/i.test(summary.innerText)){window.__reviewSecretPanels.push([e,e.getAttribute('style')]);e.style.visibility='hidden'}}return window.__reviewSecretPanels.length}""")
            try:
                with tempfile.TemporaryDirectory(prefix='jobai-review-') as directory:
                    path=Path(directory)/'full.png'
                    if visible:page.screenshot(path=str(path));detail={'frames':1,'mode':'visible'}
                    else:detail=_capture(page,path,max_height=45000)
                    if not visible and state['height']!=page.evaluate("()=>document.querySelector('[data-testid=stMain]')?.scrollHeight"):
                        raise RuntimeError('Page height changed during capture; no partial image accepted.')
                    files,meta=image_files(path.read_bytes())
                    if sidebar and not visible:
                        side=page.locator('[data-testid=stSidebar]')
                        if side.is_visible():files['sidebar.png']=side.screenshot()
                return files,{**meta,'frames':detail['frames'],'mode':detail['mode'],'redacted_sensitive_panels':redacted,'state':{'headings':state['headings'],'selected_tabs':state['tabs'],'selectors':state['selectors']},'status':'success'}
            finally:
                page.evaluate("""()=>{for(const [e,s] of window.__reviewSecretPanels||[]){if(s===null)e.removeAttribute('style');else e.setAttribute('style',s)}delete window.__reviewSecretPanels}""")
                style.evaluate('(e)=>e.remove()')
                page.evaluate('(y)=>{const m=document.querySelector("[data-testid=stMain]");if(m)m.scrollTop=y}',state['scroll'])
        try:files,meta=self.call(grab)
        except Exception as exc:self.errors.append({'name':name,'status':'failed','error':str(exc)});raise
        if sum(sum(len(b) for b in v['files'].values()) for v in self.views)+sum(map(len,files.values()))>180_000_000:raise ValueError('Session image byte bound exceeded; export/end before more captures.')
        if replace is None:self.sequence+=1;sequence=self.sequence
        else:sequence=next(v['sequence'] for v in self.views if v['id']==replace)
        entry={'id':replace or uuid.uuid4().hex,'sequence':sequence,'name':name,'notes':notes,'application_page':(meta['state']['headings'] or ['Unknown'])[0],**meta,'files':files}
        self.views=[v for v in self.views if v['id']!=replace]+[entry];self.views.sort(key=lambda v:v['sequence']);return entry

    def remove(self,identity):self.views=[v for v in self.views if v['id']!=identity]

    def export(self):
        buffer=BytesIO();entries=[]
        with ZipFile(buffer,'w',ZIP_DEFLATED) as z:
            for view in self.views:
                folder=f"{view['sequence']:02}_"+(re.sub(r'[^a-zA-Z0-9_-]+','_',view['name']).strip('_')[:60] or 'View')
                for name,data in view['files'].items():z.writestr('JobAIHelper_UI_Review/'+folder+'/'+name,data)
                entries.append({**{k:v for k,v in view.items() if k!='files'},'directory':folder,'file_hashes':{n:sha256(b).hexdigest() for n,b in view['files'].items()}})
            z.writestr('JobAIHelper_UI_Review/manifest.json',json.dumps({'session_id':self.id,'captures':entries,'errors':self.errors},indent=2))
            z.writestr('JobAIHelper_UI_Review/README.md','Local controlled Firefox review. full.png retains original pixels; numbered overlapping sections retain original width. Coordinates are [left, top, right, bottom]. Only visible/expanded content is captured; virtualized table offscreen rows require exports. Sidebar is separate and not repeated. Review estimates separately from recorded selection and native evidence; individual native impacts may be unmeasured. No independent ChatGPT review has occurred. Check captured names/notes and manifest errors. No database, resume documents or browser credentials are included.')
        return buffer.getvalue()

    def end(self):
        def close():
            try:
                if hasattr(self,'browser'):self.browser.close()
            finally:
                if hasattr(self,'runtime'):self.runtime.stop()
                self.active=False
        self.call(close)

