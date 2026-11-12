import pytest
import subprocess
from pathlib import Path


@pytest.mark.req('MODEL-001')
def test_writer_variant_payload_and_texts():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(root/'tests/web/js/writer_variant.mjs'),str(root)],capture_output=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr
