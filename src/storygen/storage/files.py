import hashlib
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
