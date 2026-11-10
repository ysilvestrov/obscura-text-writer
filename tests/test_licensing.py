"""PUB-001-S03: the current licence is the official FSL-1.1-MIT text, and the MIT boundary is kept."""
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# getsentry/fsl.software FSL-1.1-MIT.template.md, last file commit 6a886da97c12 (2024-02-14).
FSL_TEMPLATE_SHA256 = '0905af4c021cb64aff11a80aae7f25f0d7bafc69c14e97992273873d175a718b'
TEMPLATE_NOTICE = 'Copyright ${year} ${licensor name}'
NOTICE = 'Copyright 2026 Yuriy Silvestrov'

SEPARATOR = '-' * 72 + '\n\n'
# SHA-256 of LICENSE (MIT) as it stood on main before the switch (5c7d281), LF line endings.
MIT_SHA256 = '997a49cb1721fa62bf2be51734ff94f37aba99b30d7d83ad56ff5c6b0e467c17'

# Places that describe the licence of the current code to readers.
PUBLIC_DESCRIPTIONS = [
    'README.md',
    'docs/terms-of-use.md',
    'docs/en/terms-of-use.md',
    'docs/github-publication.md',
    'SPEC.MD',
]
STALE_CLAIMS = [
    'розповсюджується за [MIT License]',
    'distributed under the [MIT License]',
    'Ліцензія коду — MIT',
    'MIT License та актуальну документацію',
    'визначених [MIT License]',
    'as set out in the [MIT License]',
]


def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8').replace('\r\n', '\n')


@pytest.mark.req('PUB-001')
def test_licence_is_official_fsl_template_with_only_the_notice_filled_in():
    text = read('LICENSE')
    assert text.count(NOTICE) == 1
    restored = text.replace(NOTICE, TEMPLATE_NOTICE)
    assert hashlib.sha256(restored.encode('utf-8')).hexdigest() == FSL_TEMPLATE_SHA256


@pytest.mark.req('PUB-001')
def test_previous_mit_text_is_kept_with_its_boundary_tag():
    intro, separator, body = read('docs/licensing/MIT-previous-versions.txt').partition(SEPARATOR)
    assert separator
    assert '`last-mit`' in intro
    assert hashlib.sha256(body.encode('utf-8')).hexdigest() == MIT_SHA256


@pytest.mark.req('PUB-001')
@pytest.mark.parametrize('relative', PUBLIC_DESCRIPTIONS)
def test_public_descriptions_do_not_claim_current_code_is_mit(relative):
    text = read(relative)
    assert 'FSL-1.1-MIT' in text
    for claim in STALE_CLAIMS:
        assert claim not in text, f'{relative}: {claim}'
