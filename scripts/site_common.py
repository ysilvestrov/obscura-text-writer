"""Shared rules of the user-guide site (#29): manifest, heading ids, page hashes."""
import hashlib
import json
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


def heading_id(text,seen):
    """Lowercase, Cyrillic kept, spaces to '-', other punctuation dropped; repeats get -2, -3."""
    slug=re.sub(r'<[^>]*>','',text).strip().lower()
    slug=re.sub(r'[^\w\s-]','',slug)
    slug=re.sub(r'\s+','-',slug).strip('-')
    count=seen.get(slug,0)+1;seen[slug]=count
    return slug if count==1 else f'{slug}-{count}'


def page_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
