"""Data-only evaluator identity shared by domain guards and storage.
No model clients or content processing.
"""
import hashlib
import json
from urllib.parse import urlparse


def evaluator_identity(config):
    url = urlparse(config.base_url)
    endpoint = config.base_url.rstrip('/')
    if config.provider == 'codex_cli':
        endpoint = '<CLI>'  # base_url is never used by this transport.
    elif config.provider == 'local':
        endpoint = f'{url.scheme}://loopback:{url.port or (443 if url.scheme == "https" else 80)}{url.path.rstrip("/")}'
    return {'provider': config.provider, 'base_url': endpoint,
            'model': config.model if config.model is not None else '<CLI default>'}


def block_key(story_id, config):
    encoded = json.dumps(evaluator_identity(config), sort_keys=True).encode()
    return 'evaluator_block:' + story_id + ':' + hashlib.sha256(encoded).hexdigest()
