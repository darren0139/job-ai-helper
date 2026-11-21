import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path[:0]=[str(root),str(root/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
from browser_integration.ui_review_capture import CaptureSession
s=CaptureSession();r={}
try:
 s.start('http://127.0.0.1:8707/');s.call(lambda:s.page.close())
 try:s.capture('closed browser')
 except RuntimeError as e:r['closed_error']=str(e)
 s.end();s.start('http://127.0.0.1:8707/');v=s.capture('recovered visible view',visible=True);r['recovered']=v['status'];s.end()
except Exception as e:r['error']=str(e)
finally:
 s.pool.shutdown(wait=False);(Path(__file__).resolve().parent/'recovery.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(r)
