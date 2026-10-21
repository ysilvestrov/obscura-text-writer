"""Durable append checkpoints before publishing batched stream events."""

import os
import time
from typing import BinaryIO, Callable


class StreamBuffer:
    def __init__(self, handle: BinaryIO, on_checkpoint: Callable[[str], object],
                 *, clock: Callable[[], float] = time.monotonic):
        self.handle = handle
        self.on_checkpoint = on_checkpoint
        self.clock = clock
        self.parts: list[str] = []
        self.size = 0
        self.failed = False
        self.last_flush = clock()
        try:
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            raise

    def append(self, text: str):
        if not text:
            return
        self.parts.append(text)
        self.size += len(text.encode('utf-8'))
        if self.size >= 16384 or self.clock() - self.last_flush >= .5:
            self.flush()

    def flush(self):
        if not self.parts or self.failed:
            return
        text = ''.join(self.parts)
        try:
            self.handle.write(text.encode('utf-8'))
            self.handle.flush()
            os.fsync(self.handle.fileno())
            self.on_checkpoint(text)
        except BaseException:
            # A failed SQL acknowledgement or partial file write is uncertain.
            # Retrying here could duplicate bytes or events.
            self.failed = True
            raise
        self.parts.clear()
        self.size = 0
        self.last_flush = self.clock()

    def close(self):
        try:
            if not self.handle.closed:
                self.flush()
        finally:
            self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
