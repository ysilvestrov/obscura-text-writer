import pytest
import subprocess
from pathlib import Path


@pytest.mark.req('MODEL-005')
def test_model_picker_badges_filters_and_selectability():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(root/'tests/web/js/model_picker.mjs'),str(root)],capture_output=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr
