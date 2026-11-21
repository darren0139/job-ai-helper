from pathlib import Path
import sys,os
root=Path('C:\\Users\\Admin\\Documents\\GitHub\\Job-AI-Helper')
sys.path.insert(0,str(root));sys.path.insert(1,str(root/'reports/v37_bestof_release_ui_workspace'))
from sandbox import enable
enable()
os.chdir(root/'reports/v37_b4_workspace/app')
from streamlit.web.cli import main
sys.argv=['streamlit','run',str(root/'reports/v37_normal_integration/completion_review/browser_fixture.py'),'--server.address','127.0.0.1','--server.port','8699','--server.headless','true','--server.fileWatcherType','none','--browser.gatherUsageStats','false']
main()
