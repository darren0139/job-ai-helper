"""Supplemental real UI verification using existing Capture service on controlled Chromium.
This is NOT a successful sidebar-Firefox acceptance run."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));OUT=Path(__file__).resolve().parent
from playwright.sync_api import sync_playwright
from browser_integration.ui_review_capture import CaptureSession
result={'runtime_root':str(ROOT),'url':'http://127.0.0.1:8721/','method':'Existing CaptureSession.capture/export on task-owned Chromium, same-thread diagnostic adapter; not sidebar Firefox acceptance','errors':[],'console_errors':[],'checks':[]}
s=CaptureSession();s.call=lambda fn:fn()
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 page.on('pageerror',lambda e:result['errors'].append(str(e)))
 page.on('console',lambda e:result['console_errors'].append(e.text) if e.type=='error' else None)
 s.page=page;s.active=True
 from zipfile import ZipFile
 with ZipFile(OUT/'direct_chromium_review.zip') as old:
  prior=json.loads(old.read('JobAIHelper_UI_Review/manifest.json'))
  for view in prior['captures']:
   prefix='JobAIHelper_UI_Review/'+view['directory']+'/'
   files={name[len(prefix):]:old.read(name) for name in old.namelist() if name.startswith(prefix)}
   s.views.append({**view,'files':files,'origin_capture_session':prior['session_id']})
 s.sequence=max(v['sequence'] for v in s.views)
 def settle():
  page.wait_for_timeout(1200);page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=90000)
 def select(label,text):
  for attempt in range(4):
   box=page.get_by_test_id('stSelectbox').filter(has=page.get_by_text(label,exact=True)).last
   if text in box.inner_text():return
   try:
    box.get_by_role('combobox').click();box.get_by_role('combobox').fill(text)
    option=page.get_by_role('option').filter(has_text=text).first
    option.wait_for(timeout=4000);option.click();page.wait_for_timeout(2500);settle()
    if text in page.get_by_test_id('stSelectbox').filter(has=page.get_by_text(label,exact=True)).last.inner_text():return
   except Exception:
    page.keyboard.press('Escape');page.wait_for_timeout(2000)
  raise ValueError('Selection did not settle: '+label+' / '+text)
 def capture(name,notes):
  settle();exceptions=page.get_by_test_id('stException').all_text_contents()
  if exceptions:raise ValueError(str(exceptions))
  body=page.locator('body').inner_text();(OUT/(name+'.txt')).write_text(body,encoding='utf-8')
  view=s.capture(name,notes);result['checks'].append({'name':name,'dimensions':view['dimensions'],'frames':view['frames'],'sections':len(view['sections']),'exceptions':exceptions});print(name,flush=True)
 try:
  page.goto(result['url']);page.get_by_role('heading',name='Compare Base vs Library',exact=True).wait_for(timeout=90000);settle()
  body=page.locator('body').inner_text();assert '13 → 12' in body and '220 → 204' in body
  # Retain byte-identical already-verified captures from this same code version.
  # capture('01_Bestof_summary','Actual saved offline existing31/alternative31 tie; incumbent retained; separate from Phase8 SelectedBase30/Final31. No new native trial.')
  select('Comparison project','QueryAI');select('Source wording to explain','Set up the React');body=page.locator('body').inner_text();assert 'optional, not missing capabilities' in body and 'React' in body
  capture('03_QueryAI_alternatives','Applicable React alternative; Angular/HTML5 optional, no inferred proficiency. Actual shared setup wording and saved membership.')
  select('Comparison project','CyberSphere');assert 'Individual selection cause not recorded' in page.locator('body').inner_text()
  capture('04_CyberSphere','Standalone wording estimate, recorded inclusion/exclusion; no invented replacement winner or cause.')
  page.get_by_text('Bullet-Choice Benchmark Lab',exact=True).first.click();settle()
  page.get_by_role('tab',name='JD & Bullet Comparison Explorer',exact=True).click();select('Explorer dataset','real');select('Case','R08')
  exp=page.get_by_text('Core · Good foundation in modern C/C++ programming',exact=True).last
  exp.click();settle();body=page.locator('body').inner_text();assert 'Matched wording facets: C++' in body;assert 'cedb1bac7efcd7db' not in body
  capture('05_Cpp_atomic_identity','Actual optional real case R08; explicit C++ lexical cue retained, advanced/full proficiency not credited; no leaked internal namespace/hash facets.')
  page.set_viewport_size({'width':760,'height':1100});settle();result['narrow_overflow']=page.evaluate("()=>{const m=document.querySelector('[data-testid=stMain]');return {client:m.clientWidth,scroll:m.scrollWidth}}")
  capture('06_Cpp_narrow','Same actual C++ case at760px; primary wording/facets, no real accuracy labels.')
  page.set_viewport_size({'width':1440,'height':1000});page.goto(result['url']+'?public=1');settle();page.get_by_text('Bullet-Choice Benchmark Lab',exact=True).first.click();settle()
  assert '20 real cases unavailable' in page.locator('body').inner_text()
  page.get_by_role('tab',name='Run Benchmarks',exact=True).click();page.get_by_role('button',name='Run All Benchmarks',exact=True).click();page.wait_for_timeout(2500);settle()
  page.get_by_role('tab',name='Benchmark Overview',exact=True).click();settle();body=page.locator('body').inner_text();assert '96 / 96' in body and '90 / 96' in body
  capture('07_Public_only_Lab','Actual normal Lab page with only public fixture:96controls,90/96 agreement;20real unavailable, not passes. Explicit UI Run All; no native rendering/models.')
 except Exception as e:
  result['failure']=type(e).__name__+': '+str(e);page.screenshot(path=str(OUT/'chromium-capture-failure.png'));(OUT/'chromium-failure-body.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');print(result['failure'],flush=True)
 finally:
  if s.views:(OUT/'direct_chromium_review.zip').write_bytes(s.export())
  result['capture_count']=len(s.views);result['prior_current_code_views_reused']=2;(OUT/'chromium-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8');browser.close();s.pool.shutdown(wait=False)
