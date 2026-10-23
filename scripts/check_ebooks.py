"""Offline synthetic acceptance; Java/official EPUBCheck are explicit dev tools."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from storygen.application.exports import export_story
from storygen.domain import StoryCreate,SceneCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.publication_models import PublicationData
from storygen.storage.repository import Repository


def main():
    parser=argparse.ArgumentParser(description='Синтетичні FB2 XSD / EPUBCheck, без моделей і робочих даних')
    parser.add_argument('--java',type=Path,required=True)
    parser.add_argument('--epubcheck',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('artifacts/ebook-acceptance'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    with tempfile.TemporaryDirectory(prefix='ebook-data-',dir=args.output.resolve()) as temporary:
        repo=Repository(Path(temporary))
        author=repo.publication('create_signature',display_name='Тестовий псевдонім')
        for variant in ['minimal','full','incomplete']:
            story=repo.create_story(StoryCreate(title='Ґанок & Єва <Двері>'))
            for index in range(7):
                scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {index+1}: Двері'))
                if variant=='incomplete' and index==6:continue
                text='— Ґанок & Єва <не тег>, — сказала вона.\n\n'+' '.join(['слово']*2200)
                save_manual_prose(repo,scene.id,text,0)
            card=PublicationData(author_ids=[author.id],genres=['short_story'])
            if variant=='full':
                import io
                from PIL import Image
                buffer=io.BytesIO();Image.new('RGB',(40,60),'white').save(buffer,format='JPEG')
                cover=repo.publication('upload_cover',story_id=story.id,content=buffer.getvalue())
                card=PublicationData(author_ids=[author.id],translator_ids=[author.id],genres=['short_story'],
                    title='Публічна назва',annotation='Перший абзац.\n\nДругий.',keywords=['тест','двері'],
                    cover_id=cover.id,cycle_title='Цикл',cycle_number=2,publication_date='2026-10-22',
                    publisher='Видавець',isbn='9780306406157',rights='Права автора',source_language='en')
            repo.publication('save_card',story_id=story.id,data=card,expected_revision=0,expected_signature_revisions={author.id:0})
            for format in ['fb2','epub']:
                exported=export_story(repo,story.id,format,variant=='incomplete')
                target=args.output/f'{variant}.{format}';target.write_bytes(exported.read_bytes())
                record={'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'validator':'bundled FB2 XSD','exit_code':0}
                if format=='epub':
                    command=[str(args.java.resolve()),'-jar',str(args.epubcheck.resolve()),str(target.resolve())]
                    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
                    record.update(validator='official EPUBCheck',command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
                results.append(record)
    report={'epubcheck_jar_sha256':hashlib.sha256(args.epubcheck.read_bytes()).hexdigest(),'results':results}
    (args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for item in results:print(item['file'],item['exit_code'])
    return int(any(item['exit_code'] for item in results))


if __name__=='__main__':raise SystemExit(main())
