from pathlib import Path
import shutil,subprocess,pytest

def test_app_dialogs():
    node=shutil.which('node')
    if not node: pytest.skip('Node потрібен для перевірки діалогів')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/app-dialogs.mjs')],cwd=root,capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr


def test_app_uses_no_native_confirm_or_prompt():
    import re
    root=Path(__file__).resolve().parents[2]/'src/storygen/web/static'
    matches=[]
    for path in root.glob('*.js'):
        if re.search(r'(?<![\w.])(?:(?:window|globalThis|self)\s*\.\s*)?(?:confirm|prompt)\s*\(',path.read_text(encoding='utf-8')):
            matches.append(path.name)
    assert not matches, matches
