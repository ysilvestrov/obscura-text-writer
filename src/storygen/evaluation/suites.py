"""Canonical admission suite identity, independent of model-supplied reports."""

import hashlib
import json

from .prompting import resource_text


def canonical_suite():
    return json.loads(resource_text('calibration_suite_v2.json'))


def canonical_suite_hash():
    return hashlib.sha256(json.dumps(canonical_suite(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
