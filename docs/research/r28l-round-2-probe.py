"""Round-two offline preparation. Live inference is intentionally unavailable until gates pass."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--self-check',action='store_true',help='Run isolated tests with networking forbidden')
    action.add_argument('--audit-dataset',type=Path,help='Structural checks only, never inference')
    args=parser.parse_args()
    if args.self_check:
        return subprocess.run([sys.executable,'-m','pytest',str(Path(__file__).parent/'round2'),'-q'],check=False).returncode
    from round2.dataset import validate_dataset
    print(json.dumps(validate_dataset(json.loads(args.audit_dataset.read_text(encoding='utf-8'))),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
