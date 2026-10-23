"""Synthetic PDF acceptance using explicit local Poppler tools, no working author data."""
import argparse
import io
import json
import subprocess
import tempfile
from pathlib import Path
import pdfplumber
from pypdf import PdfReader
from PIL import Image
from storygen.application.exports import export_story
from storygen.domain import StoryCreate,SceneCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.publication_models import PublicationData
from storygen.storage.repository import Repository


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pdftoppm',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('artifacts/pdf-acceptance'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True);results=[]
    with tempfile.TemporaryDirectory(dir=args.output.resolve(),prefix='data-') as temporary:
        repo=Repository(Path(temporary));author=repo.publication('create_signature',display_name='Тестовий автор')
        for variant in ['minimal','full','incomplete','long-title']:
            story=repo.create_story(StoryCreate(title='Ґанок: Єва, Ірина та Їжак'))
            for index in range(7):
                title=f'Сцена {index+1}: Двері'
                if variant=='long-title' and index==0:title='Довга назва '+('Ї'*270)
                scene=repo.create_scene(story.id,SceneCreate(title=title))
                if variant=='incomplete' and index==6:continue
                text='Ґанок & Єва <b>не розмітка</b>.\n\n— Ідімо, — сказала Ірина.\n'
                if variant=='full':text+=' '.join(['слово']*2200)
                if variant=='long-title':text+='довгеслово'*100
                save_manual_prose(repo,scene.id,text,0)
            cover_id=None
            if variant=='full':
                buffer=io.BytesIO();Image.new('RGBA',(200,300),(80,100,150,180)).save(buffer,format='PNG')
                cover_id=repo.publication('upload_cover',story_id=story.id,content=buffer.getvalue()).id
            card=PublicationData(author_ids=[author.id],genres=['short_story'],cover_id=cover_id,
                cycle_title='Тестовий цикл' if variant=='full' else '',cycle_number=2 if variant=='full' else None)
            repo.publication('save_card',story_id=story.id,data=card,expected_revision=0,expected_signature_revisions={author.id:0})
            path=export_story(repo,story.id,'pdf',variant=='incomplete');target=args.output/(variant+'.pdf');target.write_bytes(path.read_bytes())
            manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
            reader=PdfReader(target);texts=[page.extract_text() for page in reader.pages]
            assert all(text.strip() and text.strip()!=str(index+1) for index,text in enumerate(texts) if not (variant=='full' and index==0)),'Empty page'
            if variant=='full':assert sum(text.count('слово') for text in texts)==15400
            violations=[]
            with pdfplumber.open(target) as inspection:
                for index,page in enumerate(inspection.pages,1):
                    for word in page.extract_words():
                        x0,y0,x1,y1=[word[key] for key in ['x0','top','x1','bottom']]
                        footer=(word['text']==str(index) and y0>page.height-18*72/25.4)
                        if not footer and (x0<17*72/25.4-1 or x1>page.width-17*72/25.4+1 or y0<17*72/25.4-1 or y1>page.height-18*72/25.4+1):
                            violations.append({'page':index,'word':word['text'],'bbox':[x0,y0,x1,y1]})
            subprocess.run([str(args.pdftoppm.resolve()),'-r','72','-png',str(target.resolve()),str((args.output/variant).resolve())],check=True,capture_output=True)
            results.append({'file':target.name,'sha256':manifest['output_sha256'],'word_count':manifest['word_count'],'format_details':manifest['format_details'],'pages':len(texts),'bounds_violations':violations,'fonts_embedded':all('/FontFile2' in f.get_object()['/FontDescriptor'] for page in reader.pages for f in page['/Resources']['/Font'].get_object().values() if 'NotoSerif' in str(f.get_object().get('/BaseFont')))})
    (args.output/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))
    return int(any(r['bounds_violations'] or not r['fonts_embedded'] for r in results))


if __name__=='__main__':raise SystemExit(main())
