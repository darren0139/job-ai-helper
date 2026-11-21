from pathlib import Path
import os,sys
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root),str(root/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
os.environ['DOTENV_DONT_LOAD']='1';os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True';os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.chdir(root/'reports/v37_comparison_surface/disposable')
from streamlit.web.cli import main
sys.argv=['streamlit','run',str(root/'reports/v37_ui_review_capture/view.py'),'--server.address','127.0.0.1','--server.port','8706','--server.headless','true','--server.fileWatcherType','none','--browser.gatherUsageStats','false']
main()
