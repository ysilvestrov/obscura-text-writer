"""Shell entry point of the planted-pair annotation tool (#25); see memory_bench/annotate_pairs.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from memory_bench.annotate_pairs import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
