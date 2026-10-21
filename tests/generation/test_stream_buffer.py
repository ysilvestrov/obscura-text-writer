import os

import pytest

from storygen.storage.files import FileStore
from storygen.generation.stream_buffer import StreamBuffer


def test_many_small_deltas_use_one_durable_batch(tmp_path, monkeypatch):
    syncs = []
    original = os.fsync
    def sync(fd):
        syncs.append(fd)
        original(fd)
    monkeypatch.setattr(os, 'fsync', sync)
    path = tmp_path / 'partial.txt'
    batches = []
    writes = []
    class CountWrites:
        def __init__(self, handle):
            self.handle = handle
        def __getattr__(self, name):
            return getattr(self.handle, name)
        def write(self, data):
            writes.append(data)
            return self.handle.write(data)
    def checkpoint(text):
        assert path.read_text(encoding='utf-8') == ''.join(batches) + text
        batches.append(text)
    with StreamBuffer(CountWrites(FileStore(tmp_path).open_partial('partial.txt')), checkpoint, clock=lambda: 0) as buffer:
        for _ in range(1000):
            buffer.append('0123456789')
        assert not batches
    assert path.read_bytes() == b'0123456789' * 1000
    assert ''.join(batches) == '0123456789' * 1000
    assert len(batches) <= 3 and len(syncs) <= 3 and len(writes) <= 3


def test_utf8_threshold_and_time_checkpoint_preserve_order(tmp_path):
    tick = [0.0]
    batches = []
    with StreamBuffer(FileStore(tmp_path).open_partial('partial.txt'), batches.append, clock=lambda: tick[0]) as buffer:
        buffer.append('ї' * 8191)
        assert batches == []
        buffer.append('є')
        assert batches == ['ї' * 8191 + 'є']
        buffer.append('А')
        tick[0] = .5
        buffer.append('Б')
        assert batches[-1] == 'АБ'
        tick[0] = 100
        buffer.append('')
        buffer.append('— кінець')
    assert batches == ['ї' * 8191 + 'є', 'АБ', '— кінець']
    assert (tmp_path / 'partial.txt').read_text(encoding='utf-8') == ''.join(batches)


def test_exception_flushes_tail_and_closes_file(tmp_path):
    batches = []
    with pytest.raises(RuntimeError, match='gateway'):
        with StreamBuffer(FileStore(tmp_path).open_partial('partial.txt'), batches.append) as buffer:
            buffer.append('Збережений хвіст')
            raise RuntimeError('gateway')
    assert batches == ['Збережений хвіст']
    path = tmp_path / 'partial.txt'
    path.rename(tmp_path / 'closed.txt')


@pytest.mark.parametrize('failure', ['fsync', 'event'])
def test_failed_checkpoint_is_not_retried_on_close(tmp_path, monkeypatch, failure):
    path = tmp_path / 'partial.txt'
    calls = []
    def checkpoint(text):
        calls.append(text)
        if failure == 'event':
            raise RuntimeError('event storage failed')
    with pytest.raises((OSError, RuntimeError)):
        with StreamBuffer(FileStore(tmp_path).open_partial('partial.txt'), checkpoint) as buffer:
            if failure == 'fsync':
                def fail_sync(fd):
                    raise OSError('disk failed')
                monkeypatch.setattr(os, 'fsync', fail_sync)
            buffer.append('ї' * 8192)
    assert calls == ([] if failure == 'fsync' else ['ї' * 8192])
    assert path.read_bytes() == ('ї' * 8192).encode('utf-8')
    path.rename(tmp_path / 'closed.txt')
