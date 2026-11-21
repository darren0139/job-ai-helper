from pathlib import Path
import sys,os
root=Path('C:\\Users\\Admin\\Documents\\GitHub\\Job-AI-Helper')
sys.path[:0]=[str(root),str(root/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
os.chdir(root/'reports/v37_normal_final_fixture')
from streamlit.web.cli import main
sys.argv=['streamlit','run','view.py','--server.address','127.0.0.1','--server.port','8700','--server.headless','true','--server.fileWatcherType','none','--browser.gatherUsageStats','false']
main()
