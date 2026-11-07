import subprocess
from pathlib import Path


def test_import_time_and_api_error_contract():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(root/'tests/web/js/import_ui.mjs'),str(root)],capture_output=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr
