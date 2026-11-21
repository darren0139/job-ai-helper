import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path[:0]=[str(root),str(root/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
from browser_integration.ui_review_capture import CaptureSession
s=CaptureSession();out=Path(__file__).resolve().parent
try:
 s.start('http://127.0.0.1:8705/');print('FIREFOX_STARTED',flush=True)
 def navigate():
  p=s.page;p.get_by_text('Application Sessions',exact=True).first.click();p.wait_for_timeout(1500);p.locator('.st-key-load_app_156 button').click();p.get_by_text('Open Best-of résumé comparison',exact=True).wait_for(timeout=120000);p.get_by_text('Open Best-of résumé comparison',exact=True).click();p.get_by_role('heading',name='Available Source Wordings — Estimated JD Relevance',exact=True).wait_for(timeout=120000)
 s.call(navigate)
 def choose(fragment):
  p=s.page;box=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Comparison project',exact=True)).last;box.get_by_role('combobox').click();box.get_by_role('combobox').fill(fragment);p.get_by_role('option').filter(has_text=fragment).first.click();p.wait_for_timeout(2000)
 for fragment in ['Job AI Helper','CyberSphere','QueryAI']:
  s.call(lambda:choose(fragment));s.capture(fragment+' actual saved App156','Standalone wording estimate; saved selection/native evidence separate.');print('CAPTURED',fragment,flush=True)
 (out/'JobAIHelper_UI_Review.zip').write_bytes(s.export());(out/'capture_result.json').write_text(json.dumps({'status':'engine_verified','captures':[{k:v for k,v in x.items() if k!='files'} for x in s.views],'limitation':'Service exercised directly, not complete real sidebar lifecycle acceptance.'},indent=2),encoding='utf-8')
except Exception as exc:
 (out/'capture_result.json').write_text(json.dumps({'status':'blocked','type':type(exc).__name__,'error':str(exc)},indent=2),encoding='utf-8');print(str(exc),flush=True)
finally:
 try:s.end()
 except Exception:pass
 s.pool.shutdown(wait=False)
