"""Check the user-guide site sources (#29, DOCS-SITE); read-only except `--rehash`.

- every manifest page exists in both languages;
- both language versions match the hashes recorded when the pair was confirmed (docs/site/sync.json);
- links, anchors and images resolve inside the site; images have alt text;
- no links to internal material (plans, research, diagnostics, specs, SPEC.MD, STATUS).
"""
import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.build_site import ads_settings, markdown, page_form, waitlist_settings
from scripts.site_common import IMAGES, SITE, WAITLIST_PRIVACY_ANCHOR, heading_id, heading_text, load_manifest, page_hash, page_path, page_slug

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
    check_waitlist(root,manifest,errors)
    check_ads(root,manifest,errors)
    return errors


GOOGLE_COOKIES=('_ga','_gcl_au')


def check_ads(root,manifest,errors):
    """DOCS-SITE-S11: with Google tags the privacy page of each language names their cookies."""
    try:
        if not ads_settings(manifest):return
    except ValueError as exc:errors.append(str(exc));return
    if 'privacy' not in [page['slug'] for page in manifest['pages']]:
        errors.append('site.json: розділ ads потребує сторінки privacy з описом cookies Google');return
    for lang in manifest['languages']:
        path=page_path(root,lang,'privacy')
        text=path.read_text(encoding='utf-8') if path.is_file() else ''
        missing=[name for name in GOOGLE_COOKIES if name not in text]
        if missing:errors.append(f'privacy ({lang}): з розділом ads сторінка має назвати cookies Google: {", ".join(missing)}')


def check_waitlist(root,manifest,errors):
    """WAITLIST-001-S07: the form fragment is not markdown, so its manifest section and privacy anchor are checked here."""
    for page in manifest['pages']:
        try:
            if not page_form(page):continue
            waitlist_settings(manifest)
        except ValueError as exc:errors.append(str(exc));continue
        if 'privacy' not in [item['slug'] for item in manifest['pages']]:
            errors.append(f'{page["slug"]}: фрагмент форми посилається на privacy.html, а сторінки privacy немає в маніфесті');continue
        for lang in manifest['languages']:
            anchor=WAITLIST_PRIVACY_ANCHOR[lang];privacy=page_path(root,lang,'privacy')
            if not privacy.is_file() or anchor not in page_anchors(privacy):
                errors.append(f'{page["slug"]}: фрагмент форми посилається на privacy.html#{anchor} ({lang}), а такого якоря немає')


WRANGLER='workers/waitlist/wrangler.toml'
SITEKEY=re.compile(r'0x[0-9A-Za-z_-]{16,}')
DATABASE_ID=re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def publication_problems(root=ROOT):
    """WAITLIST-001-S10: reasons the site must not be published yet, so no dead form goes live.

    A site without a form page has none. The Turnstile site key must be a real one (`0x…`, not the placeholder
    or a test key), the Worker must have its D1 database id, allow exactly the site's own origin, and its custom
    domain must be the form's action host.
    """
    root=Path(root);manifest=load_manifest(root)
    try:
        if not any(page_form(page) for page in manifest['pages']):return []
        settings=waitlist_settings(manifest)
    except ValueError as exc:return [str(exc)]
    problems=[]
    if not SITEKEY.fullmatch(settings['sitekey']):problems.append('site.json: waitlist.sitekey — заглушка чи тестовий ключ; потрібен публічний ключ віджета Turnstile (0x…)')
    try:config=tomllib.loads((root/WRANGLER).read_text(encoding='utf-8'))
    except (OSError,tomllib.TOMLDecodeError) as exc:return problems+[f'{WRANGLER}: не вдалося прочитати: {exc}']
    database=(config.get('d1_databases') or [{}])[0].get('database_id','')
    if not DATABASE_ID.fullmatch(str(database)):problems.append(f'{WRANGLER}: database_id — заглушка; впишіть id бази з wrangler d1 create')
    origin=(manifest.get('base_url') or '').rstrip('/')
    if (config.get('vars') or {}).get('ALLOWED_ORIGINS')!=origin:problems.append(f'{WRANGLER}: ALLOWED_ORIGINS має бути рівно "{origin}" (без localhost)')
    domains=[route.get('pattern') for route in config.get('routes') or [] if route.get('custom_domain')]
    if urlsplit(settings['action']).hostname not in domains:problems.append(f'{WRANGLER}: власний домен Worker не збігається з хостом waitlist.action')
    return problems


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
    parser.add_argument('--publish',action='store_true',help='перевірити, що форма списку очікування готова до публікації')
    args=parser.parse_args(argv)
    if args.publish:
        problems=publication_problems(ROOT)
        if problems:print('\n'.join(problems));return 1
        print('Сайт готовий до публікації.');return 0
    if args.rehash:
        rehash(ROOT,args.rehash);print(f'Пару {args.rehash} підтверджено: хеші обох мовних версій записано в {SYNC}.');return 0
    errors=check(ROOT)
    if errors:print('\n'.join(errors));return 1
    print('Сайт інструкцій узгоджений: пари мов, посилання, якорі й зображення.')
    return 0


if __name__=='__main__':sys.exit(main())
