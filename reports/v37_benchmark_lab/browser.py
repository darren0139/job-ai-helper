from pathlib import Path
import json,time
from playwright.sync_api import sync_playwright
out=Path(__file__).resolve().parent;shots=out/'screenshots';shots.mkdir(exist_ok=True)
record={'url':'http://127.0.0.1:8701','runtime_root':str(out.parents[1]),'entrypoint':str(out.parents[1]/'app.py'),'cwd':str(out/'disposable'),'screenshots':[],'page_errors':[],'console_errors':[]}
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
 page.on('pageerror',lambda e:record['page_errors'].append(str(e)))
 page.on('console',lambda m:record['console_errors'].append(m.text) if m.type=='error' else None)
 page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(('http://127.0.0.1','ws://127.0.0.1','http://localhost','data:','blob:')) else route.abort())
 def settle():
  page.wait_for_timeout(350)
  page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=120000)
  page.wait_for_timeout(400)
 def shot(name,locator):
  settle();locator.scroll_into_view_if_needed();page.screenshot(path=str(shots/name));record['screenshots'].append({'file':name,'viewport':page.viewport_size})
 def tab(name):page.get_by_role('tab',name=name,exact=True).click();settle()
 def select(label,value):
  box=page.get_by_test_id('stSelectbox').filter(has=page.get_by_text(label,exact=True)).last();box.get_by_role('combobox').click();page.get_by_role('option',name=value,exact=True).click();settle()
 try:
  page.goto(record['url']);page.get_by_text('Bullet-Choice Benchmark Lab',exact=True).first.wait_for(timeout=120000)
  page.get_by_text('Bullet-Choice Benchmark Lab',exact=True).first.click();settle()
  shot('01-navigation.png',page.get_by_role('heading',name='Bullet-Choice Benchmark Lab',exact=True))
  tab('Run Benchmarks');page.get_by_role('button',name='Run All Benchmarks',exact=True).click();settle()
  page.get_by_role('button',name='Run All Benchmarks',exact=True).wait_for(timeout=120000);settle()
  tab('Benchmark Overview');shot('02-overview.png',page.get_by_role('heading',name='Benchmark Overview',exact=True))
  tab('JD & Bullet Comparison Explorer');shot('03-synthetic.png',page.get_by_role('heading',name='JD & Bullet Comparison Explorer',exact=True))
  select('Explorer dataset','corpus');shot('04-corpus.png',page.get_by_role('heading',name='JD & Bullet Comparison Explorer',exact=True))
  select('Explorer dataset','real');select('Case','R07');shot('05-real.png',page.get_by_role('heading',name='JD & Bullet Comparison Explorer',exact=True))
  tab('Best-of Optimizer Evaluation');shot('06-selector.png',page.get_by_role('heading',name='Best-of Optimizer Evaluation',exact=True))
  tab('Previous vs Current');shot('07-before-after.png',page.get_by_role('heading',name='Previous vs Current',exact=True))
  tab('Exports and Optional Review')
  for label,name in [('Download benchmark JSON','ui-run.json'),('Download results CSV','ui-results.csv'),('Download benchmark ZIP','ui-benchmark.zip')]:
   with page.expect_download() as pending:page.get_by_role('button',name=label,exact=True).click()
   pending.value.save_as(str(out/name))
  record['lab_exceptions']=page.get_by_test_id('stException').all_text_contents()
  page.set_viewport_size({'width':760,'height':1100});tab('JD & Bullet Comparison Explorer');shot('08-narrow.png',page.get_by_role('heading',name='JD & Bullet Comparison Explorer',exact=True))
  record['overflow']=page.evaluate("()=>{const m=document.querySelector('[data-testid=stMain]');return {client:m.clientWidth,scroll:m.scrollWidth}}")
  page.set_viewport_size({'width':1440,'height':1100})
  page.get_by_text('Application Sessions',exact=True).first.click();settle()
  page.locator('.st-key-load_app_2 button').click();settle()
  page.get_by_text('Open Best-of résumé comparison',exact=True).wait_for(timeout=120000)
  page.get_by_text('Open Best-of résumé comparison',exact=True).click();settle()
  page.get_by_role('heading',name='JD Relevance Comparison',exact=True).first.wait_for(timeout=120000)
  shot('09-normal-tailor.png',page.get_by_role('heading',name='JD Relevance Comparison',exact=True).first)
  record['final_exceptions']=page.get_by_test_id('stException').all_text_contents()
 except Exception as exc:
  record['error']=str(exc);record['body']=page.locator('body').inner_text()[-12000:];page.screenshot(path=str(shots/'failure.png'))
 finally:
  browser.close();(out/'browser.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='body'},indent=2))
