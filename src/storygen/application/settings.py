from pathlib import Path
from typing import Literal

from pydantic import Field

from ..domain import DomainModel


class AppSettings(DomainModel):
    data_dir: Path=Field(default_factory=lambda:Path("data").resolve())
    env_file: Path=Field(default_factory=lambda:Path(".env").resolve())
    host: Literal["127.0.0.1","localhost","::1"]="127.0.0.1"
    port: int=Field(default=8765,ge=1,le=65535)
