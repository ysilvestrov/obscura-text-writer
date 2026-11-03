"""Explicit offline qualification and activation. Never performs inference."""
import argparse
import json
from pathlib import Path
from .local_profiles import register,activate,deactivate,metadata


def main(argv=None):
    parser=argparse.ArgumentParser(description='Кваліфікований локальний tokenizer; без модельних викликів')
    parser.add_argument('--data-dir',type=Path,default=Path('data'))
    parser.add_argument('action',choices=['register','activate','deactivate','show'])
    parser.add_argument('--id');parser.add_argument('--endpoint',default='http://localhost:1235/v1')
    for name in ['tokenizer','template','evidence']:parser.add_argument('--'+name,type=Path)
    parser.add_argument('--activate',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.action=='register':
            if not all([args.tokenizer,args.template,args.evidence]):raise ValueError('Missing files')
            if args.evidence.stat().st_size>20000000:raise ValueError('Evidence too large')
            evidence=json.loads(args.evidence.read_text(encoding='utf-8'))
            if not isinstance(evidence,list) or not evidence:raise ValueError('Missing evidence')
            result=register(args.data_dir,args.endpoint,evidence[0]['request'],args.tokenizer,args.template,evidence)
            if args.activate:activate(args.data_dir,result['id'])
        else:
            if not args.id:raise ValueError('Missing id')
            result={'activate':activate,'deactivate':deactivate,'show':metadata}[args.action](args.data_dir,args.id)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,KeyError,OSError,TypeError):
        print('Кваліфікацію або активацію tokenizer не виконано: перевірте файли, контрольні суми, формат і usage. Тексти не виводяться.');return 2


if __name__=='__main__':raise SystemExit(main())
