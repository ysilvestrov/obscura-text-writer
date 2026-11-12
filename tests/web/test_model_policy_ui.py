import pytest
import subprocess
from pathlib import Path


@pytest.mark.req('MODEL-003')
def test_model_policy_consent_visibility_and_texts():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(root/'tests/web/js/model_policy.mjs'),str(root)],capture_output=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr
