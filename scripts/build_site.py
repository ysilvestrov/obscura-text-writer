"""Build the bilingual user-guide site from docs/site into a static directory (#29, DOCS-SITE).

No network and no model calls. Ukrainian pages go to the root, English ones to en/.
All links are relative, so the site works under the GitHub Pages subpath.
The output directory is written over, not emptied: build into a fresh directory (CI does) for an exact tree.
"""
import argparse
import html
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.site_common import IMAGES, LABELS, SITE, heading_id, load_manifest, page_path

ROOT=Path(__file__).resolve().parents[1]


def is_external(href):return bool(urlsplit(href).scheme) or href.startswith('//')


def rewrite_href(href,slugs):
    """`<slug>.md[#anchor]` inside the manifest becomes `<slug>.html[#anchor]`; everything else is unchanged."""
    if is_external(href) or href.startswith('#'):return href
    path,_,fragment=href.partition("#");path,fragment=unquote(path),unquote(fragment)
    if path.endswith('.md') and '/' not in path and path[:-3] in slugs:
        return path[:-3]+'.html'+(f'#{fragment}' if fragment else '')
    return href


def image_target(root,source,src,lang):
    """Map an image path relative to the markdown file onto the copied images/ directory."""
    if is_external(src):return src
    resolved=(source.parent/src).resolve()
    images=(Path(root)/IMAGES).resolve()
    if not resolved.is_relative_to(images):return src
    prefix='' if lang=='uk' else '../'
    return prefix+'images/'+resolved.relative_to(images).as_posix()


def markdown():return MarkdownIt('commonmark').enable('table')


def render(root,lang,slug,slugs):
    md=markdown()
    source=page_path(root,lang,slug)
    tokens=md.parse(source.read_text(encoding='utf-8'))
    seen={}
    for index,token in enumerate(tokens):
        if token.type=='heading_open':token.attrSet('id',heading_id(tokens[index+1].content,seen))
        for child in token.children or []:
            if child.type=='link_open':child.attrSet('href',rewrite_href(child.attrGet('href') or '',slugs))
            elif child.type=='image':child.attrSet('src',image_target(root,source,child.attrGet('src') or '',lang))
    return md.renderer.render(tokens,md.options,{})


def page_html(template,manifest,lang,slug,content):
    pages=manifest['pages'];base='' if lang=='uk' else '../'
    titles={page['slug']:page['title'][lang] for page in pages}
    nav='\n'.join(f'<li><a href="{page["slug"]}.html"'+(' aria-current="page"' if page['slug']==slug else '')+f'>{html.escape(titles[page["slug"]])}</a></li>' for page in pages)
    other='en' if lang=='uk' else 'uk'
    switch_href=f'en/{slug}.html' if lang=='uk' else f'../{slug}.html'
    switch=f'<span>{LABELS[lang]["name"]}</span><a href="{switch_href}" hreflang="{other}" lang="{other}">{LABELS[other]["name"]}</a>'
    home='index.html' if 'index' in titles else f'{pages[0]["slug"]}.html'
    values={'lang':lang,'title':html.escape(titles[slug]),'base':base,'home':home,'switch':switch,'nav':nav,
            'content':content,'nav_label':LABELS[lang]['nav'],'lang_label':LABELS[lang]['lang']}
    out=template
    for key,value in values.items():out=out.replace('{'+key+'}',value)
    return out


def build(root=ROOT,out=None):
    root=Path(root);out=Path(out) if out else root/'_site'
    if out.resolve()==root.resolve() or (out/'.git').exists():raise ValueError(f'не той каталог виходу: {out}')
    manifest=load_manifest(root);slugs={page['slug'] for page in manifest['pages']}
    template=(root/SITE/'template.html').read_text(encoding='utf-8')
    written=[]
    for lang in manifest['languages']:
        folder=out if lang=='uk' else out/lang
        folder.mkdir(parents=True,exist_ok=True)
        for page in manifest['pages']:
            target=folder/f'{page["slug"]}.html'
            target.write_text(page_html(template,manifest,lang,page['slug'],render(root,lang,page['slug'],slugs)),encoding='utf-8',newline='\n')
            written.append(target)
    shutil.copyfile(root/SITE/'site.css',out/'site.css');written.append(out/'site.css')
    images=root/IMAGES
    if images.is_dir():
        for image in sorted(p for p in images.rglob('*') if p.is_file()):
            target=out/'images'/image.relative_to(images);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(image,target);written.append(target)
    (out/'.nojekyll').write_text('',encoding='utf-8')
    return written


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')  # Windows consoles default to a legacy code page
    parser=argparse.ArgumentParser(description='Зібрати сайт інструкцій із docs/site.')
    parser.add_argument('--out',default='_site')
    args=parser.parse_args(argv)
    written=build(ROOT,ROOT/args.out)
    print(f'Сайт зібрано: {len(written)} файлів у {args.out}/')
    return 0


if __name__=='__main__':sys.exit(main())
