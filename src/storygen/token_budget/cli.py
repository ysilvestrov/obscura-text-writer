"""Local, explicit control of token profiles. No provider calls."""
import argparse
import json
from pathlib import Path
from ..storage.repository import Repository


def main(argv=None):
    parser = argparse.ArgumentParser(description='Перевірені профілі оцінки токенів; без модельних викликів')
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('action', choices=['list', 'build', 'activate', 'deactivate', 'collect'])
    parser.add_argument('--identity')
    args = parser.parse_args(argv)
    repo = Repository(args.data_dir)
    try:
        if args.action == 'list':
            result = {'profiles': repo.token_records('profile'), 'observations': len(repo.token_records('observation')),
                'identities': sorted({r['identity'] for r in repo.token_records('observation')})}
        elif args.action == 'collect':
            from .service import record_usage
            count = 0
            for story in repo.list_stories(include_trashed=True):
                for attempt in repo.list_attempts(story.id):
                    body = attempt.context.get('api_request')
                    if not body: continue
                    role = attempt.context.get('settings', {}).get('provider') or attempt.context.get('config', {})
                    if role.get('provider') == 'codex_cli': continue
                    if record_usage(repo, role['provider'], role['base_url'], body, attempt.usage, attempt.id): count += 1
            result = {'collected_attempts': count}
        else:
            if not args.identity: raise ValueError('Потрібен --identity зі списку list')
            result = repo.token_profile_action(args.identity, args.action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError):
        print('Профіль не пройшов перевірку, прострочений або спостереження змінилися. Виконайте list/build; активацію не виконано.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
