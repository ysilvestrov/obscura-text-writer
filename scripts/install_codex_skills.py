"""Generate or install Obscura Codex skills from this checkout; never invoke a model."""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path

# A shared editable install may point to a different checkout.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from storygen.codex_skill_install import install_skills  # noqa: E402
from storygen.codex_skills import GenerationError, generate_skills  # noqa: E402


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    destinations=parser.add_mutually_exclusive_group(required=True)
    destinations.add_argument('--output',type=Path,help='Generate into a new or empty folder')
    destinations.add_argument('--install',action='store_true',help='Install into the current user Agents skills folder')
    args=parser.parse_args(argv)
    try:
        bundle=generate_skills(source_root()/'integrations/claude/obscura')
        names=sorted({key.split('/')[0] for key in bundle.files})
        if args.output is not None:
            output=args.output.absolute()
            info=output.lstat() if output.exists() or output.is_symlink() else None
            if info and (output.is_symlink() or getattr(info,'st_file_attributes',0) & 0x400
                         or not output.is_dir() or any(output.iterdir())):
                result={'result':'failed','errors':['output_not_empty_or_unsafe']}
            else:
                output.mkdir(parents=True,exist_ok=True)
                for relative,raw in bundle.files.items():
                    path=output/relative
                    path.parent.mkdir(parents=True,exist_ok=True)
                    with path.open('xb') as stream:
                        stream.write(raw)
                result={'result':'generated','names':names,'path':str(output)}
        else:
            profile=Path(os.environ.get('USERPROFILE') or Path.home())
            result=dataclasses.asdict(install_skills(bundle,profile))
            result['names']=names
    except GenerationError as error:
        result={'result':'failed','errors':[str(error)]}
    except (OSError,ValueError):
        result={'result':'failed','errors':['operation_failed']}
    print(json.dumps(result,ensure_ascii=False,default=str))
    return 0 if result['result'] in {'generated','installed','unchanged'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
