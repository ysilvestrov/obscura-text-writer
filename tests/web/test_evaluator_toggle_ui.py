import shutil,subprocess
from pathlib import Path
import pytest

def test_off_switch_works_with_unfinished_json():
 node=shutil.which('node')
 if not node:pytest.skip('Node required')
 root=Path(__file__).resolve().parents[2]
 result=subprocess.run([node,str(root/'tests/web/js/evaluator_toggle.mjs'),str(root)],capture_output=True,text=True,timeout=15)
 assert result.returncode==0,result.stderr
