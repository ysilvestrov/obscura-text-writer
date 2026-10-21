"""Maintenance CLI independent from models, credentials and the web server."""
import argparse
import json
import sqlite3
from pathlib import Path

from .storage.backup import create_backup, restore_backup
from .storage.integrity import check_integrity


def main(argv=None):
    parser = argparse.ArgumentParser(description='Перевірка й резервування Storygen')
    subparsers = parser.add_subparsers(dest='command', required=True)
    for command in ('fsck', 'backup', 'restore'):
        child = subparsers.add_parser(command)
        child.add_argument('--json', action='store_true')
        if command == 'restore':
            child.add_argument('--backup-dir', type=Path, required=True)
        else:
            child.add_argument('--data-dir', type=Path, default=Path.cwd() / 'data')
        if command != 'fsck':
            child.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'fsck':
            result = check_integrity(args.data_dir).to_dict()
        else:
            path = create_backup(args.data_dir, args.destination) if args.command == 'backup' else restore_backup(args.backup_dir, args.destination)
            result = {'ok': True, 'destination': str(path)}
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        result = {'ok': False, 'error': str(exc)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print('Успішно' if result['ok'] else 'Помилка')
        for issue in result.get('issues', []):
            print(f"{issue['code']}: {issue['path']} — {issue['message']}")
        if 'error' in result:
            print(result['error'])
        if 'destination' in result:
            print(result['destination'])
    return 0 if result['ok'] else 1
