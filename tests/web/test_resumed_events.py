import shutil,subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('scenario',['events','terminal'])
def test_old_failure_event_cannot_disconnect_resumed_run(scenario):
 node=shutil.which('node')
 if not node:pytest.skip('Node required')
 root=Path(__file__).resolve().parents[2]
 result=subprocess.run([node,str(root/'tests/web/js/resumed_run_events.mjs'),scenario,str(root)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
 assert result.returncode==0,result.stderr
