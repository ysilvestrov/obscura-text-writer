import os
import subprocess
import sys
from pathlib import Path


def test_embeddings_module_optional():
    code = ("import sys, memory_bench.strategies, memory_bench.ranking;"
            "assert 'sentence_transformers' not in sys.modules; assert 'numpy' not in sys.modules")
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(root / 'scripts'), str(root)])}
    subprocess.run([sys.executable, '-c', code], check=True, cwd=root, env=env)
