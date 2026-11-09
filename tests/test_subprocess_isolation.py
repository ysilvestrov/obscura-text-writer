import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_child_python_imports_this_checkout_src():
    # A shared .venv may point its editable install at another worktree; child processes must still test this checkout.
    out=subprocess.run([sys.executable,'-c','import storygen;print(storygen.__file__)'],capture_output=True,text=True,timeout=60)
    assert out.returncode==0,out.stderr
    assert Path(out.stdout.strip()).resolve().is_relative_to(ROOT/'src')
