from storygen.token_budget.cli import main
from storygen.storage.repository import Repository
from storygen.domain import StoryCreate, SceneCreate, StageAttempt
from storygen.token_budget.service import record_usage


def test_cli_lists_only_aggregates_and_collects_exact_attempts(tmp_path, capsys):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Приватна назва'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    request = {'model': 'm', 'messages': [{'role': 'user', 'content': 'Приватний авторський текст'}]}
    repo.save_attempt(StageAttempt(id='a', story_id=story.id, scene_id=scene.id, stage='draft',
        context={'api_request': request, 'settings': {'provider': {'provider': 'local', 'base_url': 'http://localhost:1235/v1'}}},
        usage={'prompt_tokens': 10}, partial_path='partial/a.txt'))
    assert main(['--data-dir', str(tmp_path), 'collect']) == 0
    assert len(repo.token_records('observation')) == 1
    assert main(['--data-dir', str(tmp_path), 'list']) == 0
    output = capsys.readouterr().out
    assert 'Приватний' not in output and 'Приватна назва' not in output


def test_snapshot_and_backup_preserve_profile_records(tmp_path):
    from storygen.storage.backup import create_backup, restore_backup
    from storygen.token_budget.service import build
    repo = Repository(tmp_path / 'source')
    story = repo.create_story(StoryCreate(title='Тест'))
    body = {'model': 'm', 'messages': [{'role': 'user', 'content': 'Слова'}]}
    record = record_usage(repo, 'local', 'http://localhost:1235/v1', body, {'prompt_tokens': 10}, 'a')
    profile = build(repo, record['identity'])
    view = repo.context_view(story.id)
    repo.token_profile_action(record['identity'], 'deactivate')
    assert view.token_records('profile') == [profile]
    backup = create_backup(repo.root, tmp_path / 'backup')
    restored = Repository(restore_backup(backup, tmp_path / 'restored'))
    assert restored.token_records('observation') == repo.token_records('observation')
    assert restored.token_records('profile') == repo.token_records('profile')
