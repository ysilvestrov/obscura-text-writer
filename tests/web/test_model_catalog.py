import subprocess
from pathlib import Path


def test_model_catalog_labels_and_safe_http_localization():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node',str(root/'tests/web/js/model_catalog.mjs'),str(root)],capture_output=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr


def test_server_translates_nested_http_reason():
    from storygen.web.localization import diagnostic
    assert diagnostic('HTTP 429: Перевищено ліміт частоти запитів провайдера. Автоматичного повтору немає.','en')=='HTTP 429: Provider request rate limit exceeded. No automatic retry.'
