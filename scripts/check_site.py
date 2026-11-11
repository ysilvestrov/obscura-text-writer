"""Check the user-guide site sources (#29, DOCS-SITE); read-only except `--rehash`.

- every manifest page exists in both languages;
- both language versions match the hashes recorded when the pair was confirmed (docs/site/sync.json);
- links, anchors and images resolve inside the site; images have alt text;
- no links to internal material (plans, research, diagnostics, specs, SPEC.MD, STATUS).
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.build_site import markdown
from scripts.site_common import IMAGES, SITE, heading_id, heading_text, load_manifest, page_hash, page_path, page_slug

ROOT=Path(__file__).resolve().parents[1]
SYNC='docs/site/sync.json'
INTERNAL=('docs/superpowers/','docs/research/','docs/diagnostics/','docs/specs/','SPEC.MD','docs/STATUS.md')


def rel(root,path):return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def page_anchors(path):
    tokens=markdown().parse(path.read_text(encoding='utf-8'));seen={}
    return {heading_id(heading_text(tokens[i+1]),seen) for i,token in enumerate(tokens) if token.type=='heading_open'}


def rehash_hint(slug):return f'python scripts/check_site.py --rehash {slug}'


def load_sync(root):
    path=Path(root)/SYNC
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def page_links(source):
    """(line, kind, target, alt) for every link and image markdown-it renders, reference-style included."""
    tokens=markdown().parse(source.read_text(encoding='utf-8'))
    for token in tokens:
        line=token.map[0]+1 if token.map else 1
        for child in token.children or []:
            if child.type=='link_open':yield line,'link',child.attrGet('href') or '',None
            elif child.type=='image':yield line,'image',child.attrGet('src') or '',child.content


def check_links(root,lang,slug,slugs,errors):
    source=page_path(root,lang,slug);where=rel(root,source)
    images=(Path(root)/IMAGES).resolve()
    for number,kind,target,alt in page_links(source):
        at=f'{where}:{number}';external=bool(urlsplit(target).scheme) or target.startswith('//')
        if kind=='image' and not (alt or '').strip():errors.append(f'{at}: зображення без alt-тексту: {target}')
        if external:
            if kind=='image':errors.append(f'{at}: зображення сайту мають лежати в {IMAGES}/, а не за зовнішньою адресою: {target}')
            continue
        path,_,fragment=target.partition('#');path,fragment=unquote(path),unquote(fragment)
        resolved=(source.parent/path).resolve() if path else source.resolve()
        try:inside=rel(root,resolved)
        except ValueError:errors.append(f'{at}: посилання поза репозиторієм: {target}');continue
        if any(inside==prefix or inside.startswith(prefix) for prefix in INTERNAL):
            errors.append(f'{at}: посилання на внутрішній матеріал {target}; сайт містить лише інструкції з docs/site');continue
        if kind=='image':
            if not resolved.is_relative_to(images):errors.append(f'{at}: зображення сайту мають лежати в {IMAGES}/: {target}')
            elif not resolved.is_file():errors.append(f'{at}: зображення не знайдено: {target}')
            continue
        page=page_slug(path,slugs)
        if path and not page:
            errors.append(f'{at}: посилання на файл поза сайтом: {target}; посилайтеся на сторінку з docs/site/site.json');continue
        if fragment:
            linked=page_path(root,lang,page or slug)
            if linked.is_file() and fragment not in page_anchors(linked):errors.append(f'{at}: якоря немає: {target}')


def check(root=ROOT):
    root=Path(root);errors=[]
    try:manifest=load_manifest(root);sync=load_sync(root)
    except (OSError,UnicodeError,ValueError) as exc:return [f'docs/site: не вдалося прочитати маніфест або sync.json: {exc}']
    slugs=[page['slug'] for page in manifest['pages']]
    for slug in slugs:
        missing=[lang for lang in manifest['languages'] if not page_path(root,lang,slug).is_file()]
        for lang in missing:errors.append(f'{slug}: немає docs/site/{lang}/{slug}.md; кожна сторінка має бути обома мовами')
        if missing:continue
        recorded=sync.get(slug)
        if not isinstance(recorded,dict):
            errors.append(f'{slug}: пару не підтверджено; перевірте обидві мовні версії й виконайте {rehash_hint(slug)}')
        else:
            changed=[f'docs/site/{lang}/{slug}.md' for lang in manifest['languages'] if recorded.get(lang)!=page_hash(page_path(root,lang,slug))]
            if changed:errors.append(f'{slug}: змінено {", ".join(changed)} без підтвердження пари; оновіть іншу мовну версію й виконайте {rehash_hint(slug)}')
        for lang in manifest['languages']:check_links(root,lang,slug,set(slugs),errors)
    for slug in sorted(set(sync)-set(slugs)):errors.append(f'{SYNC}: запис {slug} не відповідає жодній сторінці маніфесту')
    return errors


def rehash(root,slug):
    root=Path(root);manifest=load_manifest(root)
    if slug not in [page['slug'] for page in manifest['pages']]:raise ValueError(f'сторінки {slug} немає в docs/site/site.json')
    sync=load_sync(root)
    sync[slug]={lang:page_hash(page_path(root,lang,slug)) for lang in manifest['languages']}
    (root/SYNC).write_text(json.dumps(dict(sorted(sync.items())),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')  # Windows consoles default to a legacy code page
    parser=argparse.ArgumentParser(description='Перевірити джерела сайту інструкцій.')
    parser.add_argument('--rehash',metavar='SLUG',help='записати хеші обох мовних версій після перевірки перекладу')
    args=parser.parse_args(argv)
    if args.rehash:
        rehash(ROOT,args.rehash);print(f'Пару {args.rehash} підтверджено: хеші обох мовних версій записано в {SYNC}.');return 0
    errors=check(ROOT)
    if errors:print('\n'.join(errors));return 1
    print('Сайт інструкцій узгоджений: пари мов, посилання, якорі й зображення.')
    return 0


if __name__=='__main__':sys.exit(main())
