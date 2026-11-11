"""Shared rules of the user-guide site (#29): manifest, heading ids, page hashes."""
import hashlib
import json
import posixpath
import re
from pathlib import Path

SITE='docs/site'
IMAGES='docs/images/site'
LABELS={'uk':{'name':'Українська','nav':'Розділи','lang':'Мова'},'en':{'name':'English','nav':'Sections','lang':'Language'}}


def load_manifest(root):
    manifest=json.loads((Path(root)/SITE/'site.json').read_text(encoding='utf-8'))
    if manifest.get('languages')!=['uk','en']:raise ValueError('site.json: languages має бути ["uk","en"]')
    return manifest


def page_path(root,lang,slug):return Path(root)/SITE/lang/f'{slug}.md'


def heading_text(inline):
    """Visible text of a heading's inline token: text and code, without link URLs or markup."""
    return ''.join(child.content for child in (inline.children or []) if child.type in ('text','code_inline'))


def heading_id(text,seen):
    """Lowercase, Cyrillic kept, spaces to '-', other punctuation dropped; repeats get -2, -3, never an id already used."""
    slug=text.strip().lower()
    slug=re.sub(r'[^\w\s-]','',slug)
    slug=re.sub(r'\s+','-',slug).strip('-') or 'section'
    used=seen.setdefault(None,set());number=seen.get(slug,0)
    while True:
        number+=1;candidate=slug if number==1 else f'{slug}-{number}'
        if candidate not in used:break
    seen[slug]=number;used.add(candidate)
    return candidate


def page_slug(path,slugs):
    """Manifest slug of a same-folder page link (`install.md`, `./install.md`), else None."""
    path=posixpath.normpath(path) if path else path
    if path and path.endswith('.md') and '/' not in path and path[:-3] in slugs:return path[:-3]
    return None


def page_hash(path):
    """SHA-256 of the page with CRLF folded to LF, so a Windows checkout and CI agree."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
