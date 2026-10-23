"""Explicit local budget configuration; no completion calls."""
import argparse
import json
from pathlib import Path
from ..storage.repository import Repository
from .models import Tariff, money, BudgetError
from ..storage.locking import AppInstanceLock
from .service import set_limit, summary, save_tariff


def main(argv=None):
    parser=argparse.ArgumentParser(description='Явні бюджети викликів API')
    parser.add_argument('--data-dir',type=Path,default=Path('data'))
    parser.add_argument('--scope',required=True)
    parser.add_argument('action',choices=['set','summary','calls','tariff','reconcile'])
    parser.add_argument('--limit-usd')
    parser.add_argument('--run-limit-usd')
    parser.add_argument('--expected-revision',type=int,default=0)
    parser.add_argument('--file',type=Path)
    parser.add_argument('--call-id')
    parser.add_argument('--amount-usd')
    parser.add_argument('--source')
    args=parser.parse_args(argv)
    lock=AppInstanceLock(args.data_dir)
    try:
        try: lock.__enter__()
        except RuntimeError: raise BudgetError("Каталог уже відкрито застосунком або іншим CLI") from None
        repo=Repository(args.data_dir)
        if args.action=='set':
            if args.limit_usd is None:raise ValueError('Потрібен --limit-usd')
            result=set_limit(repo,args.scope,args.limit_usd,args.expected_revision,args.run_limit_usd)
        elif args.action=='summary':result=summary(repo,args.scope)
        elif args.action=='calls':result=repo.billing('calls',scope=args.scope)
        elif args.action=='tariff':
            if args.file is None:raise ValueError('Потрібен --file з ручним тарифом')
            raw=json.loads(args.file.read_text(encoding='utf-8'));raw['kind']='manual'
            result=save_tariff(repo,Tariff.model_validate(raw))
        else:
            if not args.call_id or args.amount_usd is None or not args.source:raise ValueError('Потрібні call ID, сума й джерело')
            result=repo.billing('manual',scope=args.scope,call_id=args.call_id,amount_nanos=money(args.amount_usd),source=args.source)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError,KeyError) as exc:
        if isinstance(exc,BudgetError):
            print(str(exc));return 2
        print('Бюджетну операцію відхилено: перевірте ліміт, ревізію, тариф і джерело; completion не викликався.')
        return 2
    finally:
        lock.__exit__(None,None,None)


if __name__=='__main__':raise SystemExit(main())
