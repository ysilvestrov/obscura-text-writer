"""PACKAGING-001: what the build script recorded about the checkout it froze.

The manifest lies in the package next to the edition marker: the version of the project and a digest of every
tracked data file. A source checkout has none.
"""
import json
from functools import lru_cache
from importlib.resources import files

NAME = 'build_manifest.json'
DISTRIBUTION = 'storygen'


@lru_cache(maxsize=1)
def load() -> dict | None:
    source = files(__package__).joinpath(NAME)
    if not source.is_file():
        return None
    data = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('version'), str) or not isinstance(data.get('files'), dict):
        raise ValueError('Некоректний файл збірки build_manifest.json')
    return data


def project_version() -> str:
    """The version of this application: the build manifest when frozen, the installed metadata otherwise."""
    manifest = load()
    if manifest is not None:
        return manifest['version']
    from importlib.metadata import PackageNotFoundError, version
    try:
        # Through a name, not a literal: the freezer copies the metadata of every distribution named literally in a
        # version() call, and the installed metadata may belong to another checkout.
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return '0.0.0'
