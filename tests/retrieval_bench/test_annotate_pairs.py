import json
import tempfile
from pathlib import Path

import pytest

from tests.retrieval_bench.helpers import rec, scene
from memory_bench import annotate_pairs as ap

ROOT = Path(__file__).resolve().parents[2]
PAIRS = {'pairs': [{'id': 'P01', 'first': 1, 'repeat': 3, 'first_words': 'світле каре', 'repeat_words': 'x'}],
         'controls': [{'id': 'C01', 'first': 1, 'repeat': 3, 'words': 'маяк'}]}


def scenes():
    first = scene([rec('old', 'facts', 'Марія у світлому каре')], id='s1', number=1)
    repeat = scene([rec('hit', 'character_states', 'Марія у світлому каре'), rec('miss', 'facts', 'Іде дощ'),
                    rec('beacon', 'facts', "Старий Маяк на скелі")], id='s3', number=3)
    return [first, repeat]


def test_candidates_match_word_stems():
    found = ap.candidates(scenes(), PAIRS['pairs'][0])
    assert [r.claim_id for r in found] == ['hit']
    assert [r.claim_id for r in ap.candidates(scenes(), PAIRS['controls'][0])] == ['beacon']


def test_candidates_use_repeat_scene_snapshot():
    # 'old' lives only in the first-appearance snapshot, and matches the words: it must not be offered
    assert 'old' not in [r.claim_id for r in ap.candidates(scenes(), PAIRS['pairs'][0])]
    assert ap.candidates([scenes()[0]], PAIRS['pairs'][0]) == []


@pytest.fixture
def env(tmp_path, monkeypatch):
    from storygen.domain import StoryCreate
    from storygen.storage.repository import Repository
    data = tmp_path / 'data'
    story = Repository(data).create_story(StoryCreate(title='T'))
    monkeypatch.setattr(ap, 'extract_story', lambda repo, story_id, protagonist=None: (scenes(), {}))
    pairs = tmp_path / 'pairs.json'
    pairs.write_text(json.dumps(PAIRS, ensure_ascii=False), encoding='utf-8')
    return data, story.id, pairs, tmp_path


def test_propose_refuses_out_inside_repo(env, capsys):
    data, story, pairs, _ = env
    out = ROOT / 'docs' / 'candidates-should-not-exist.json'
    code = ap.main(['propose', '--data', str(data), '--story', story, '--pairs', str(pairs), '--out', str(out)])
    captured = capsys.readouterr()
    assert code == 2 and 'inside_repo' in captured.err and not out.exists()


def test_propose_writes_texts_only_to_out(env, capsys, request):
    data, story, pairs, _ = env
    holder = tempfile.TemporaryDirectory(prefix='annot-')  # pytest's basetemp may itself lie inside the repository
    request.addfinalizer(holder.cleanup)
    outside = Path(holder.name)
    out = outside / 'c.json'
    assert ap.main(['propose', '--data', str(data), '--story', story, '--pairs', str(pairs), '--out', str(out)]) == 0
    captured = capsys.readouterr()
    assert 'каре' not in captured.out + captured.err
    written = json.loads(out.read_text(encoding='utf-8'))
    assert written['P01'] == [{'claim_id': 'hit', 'category': 'character_states', 'text': 'Марія у світлому каре'}]


def confirm(env, picks, annotation):
    data, story, pairs, tmp = env
    picks_file = tmp / 'picks.json'
    picks_file.write_text(json.dumps(picks), encoding='utf-8')
    return ap.main(['confirm', '--data', str(data), '--story', story, '--pairs', str(pairs), '--picks', str(picks_file),
                    '--annotation', str(annotation)])


def test_confirm_rejects_unknown_claim(env, capsys):
    annotation = env[3] / 'a.json'
    assert confirm(env, {'P01': ['hit', 'old']}, annotation) == 2
    assert 'unknown_claim' in capsys.readouterr().err and not annotation.exists()


def test_confirm_writes_ids_only(env):
    annotation = env[3] / 'a.json'
    assert confirm(env, {'P01': ['hit']}, annotation) == 0
    story = env[1]
    assert json.loads(annotation.read_text(encoding='utf-8')) == {'stories': {story: {'P01': ['hit']}}}
    assert 'каре' not in annotation.read_text(encoding='utf-8')
    assert confirm(env, {'C01': ['beacon']}, annotation) == 0
    assert json.loads(annotation.read_text(encoding='utf-8'))['stories'][story] == {'P01': ['hit'], 'C01': ['beacon']}
