import hashlib
import codecs
import os
from pathlib import Path

from ..domain import StorageCorruption, new_id


class FileStore:
    def __init__(self,root: Path):
        self.root=root.resolve()

    def resolve(self,relative: str) -> Path:
        path=(self.root/relative).resolve()
        if not path.is_relative_to(self.root):
            raise StorageCorruption("Шлях поза сховищем")
        return path

    def write(self,relative: str,content: bytes):
        path=self.resolve(relative)
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+"."+new_id()+".tmp")
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)

    def read(self,relative: str,sha256: str) -> bytes:
        try:
            data=self.resolve(relative).read_bytes()
        except OSError as exc:
            raise StorageCorruption("Файл версії відсутній або недоступний") from exc
        if hashlib.sha256(data).hexdigest() != sha256:
            raise StorageCorruption("Вміст версії не відповідає збереженому hash")
        return data

    def open_partial(self, relative: str):
        """Create a new mutable partial; immutable versions still use write()."""
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.open('xb')

    def read_partial(self, relative: str) -> str:
        path = self.resolve(relative)
        if not path.exists():
            return ''
        # Concurrent append (or a crash) may leave only the first bytes of the
        # last character. Ignore that incomplete tail, not invalid inner bytes.
        return codecs.getincrementaldecoder('utf-8')().decode(path.read_bytes(), final=False)
