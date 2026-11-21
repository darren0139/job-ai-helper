import sys,json
from pathlib import Path
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));OUT=Path(__file__).resolve().parent
from playwright.sync_api import sync_playwright
from browser_integration.ui_review_capture import CaptureSession
s=CaptureSession();s.call=lambda fn:fn()
with ZipFile(OUT/'direct_chromium_review.zip') as old:
 m=json.loads(old.read('JobAIHelper_UI_Review/manifest.json'))
 for v in m['captures']:
  prefix='JobAIHelper_UI_Review/'+v['directory']+'/'
  s.views.append({**v,'files':{n[len(prefix):]:old.read(n) for n in old.namelist() if n.startswith(prefix)},'origin_capture_session':v.get('origin_capture_session',m['session_id'])})
s.sequence=max(v['sequence'] for v in s.views)
r={'url':'http://127.0.0.1:8721/?public=1','method':'Existing Capture service on controlled Chromium; not sidebar-Firefox acceptance','console_errors':[],'page_errors':[]}
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1440,'height':1000});s.page=p;s.active=True
 p.on('pageerror',lambda e:r['page_errors'].append(str(e)));p.on('console',lambda e:r['console_errors'].append(e.text) if e.type=='error' else None)
 try:
  p.goto(r['url']);p.get_by_role('heading',name='Bullet-Choice Benchmark Lab',exact=True).wait_for(timeout=60000)
  assert '20 real cases unavailable' in p.locator('body').inner_text()
  p.get_by_role('tab',name='Run Benchmarks',exact=True).click();p.wait_for_timeout(1500)
  p.get_by_role('button',name='Run All Benchmarks',exact=True).click()
  p.get_by_text('Controlled correct / evaluated',exact=True).wait_for(timeout=90000)
  p.get_by_role('tab',name='Benchmark Overview',exact=True).click();p.wait_for_timeout(1500)
  body=p.locator('body').inner_text();assert '96 / 96' in body and '90 / 96' in body
  view=s.capture('07_Public_only_Lab','Actual UI Run All with public fixture only:96 controls90/96,20real unavailable, no native rendering/models.');r['dimensions']=view['dimensions']
  r['exceptions']=p.get_by_test_id('stException').all_text_contents();assert not r['exceptions'];r['status']='pass'
 except Exception as e:
  r['status']='failed';r['error']=type(e).__name__+': '+str(e);p.screenshot(path=str(OUT/'public-browser-failure.png'))
 finally:
  (OUT/'public-browser-body.txt').write_text(p.locator('body').inner_text(),encoding='utf-8');(OUT/'direct_chromium_review.zip').write_bytes(s.export());(OUT/'public-browser.json').write_text(json.dumps(r,indent=2),encoding='utf-8');b.close();s.pool.shutdown(wait=False);print(r)
