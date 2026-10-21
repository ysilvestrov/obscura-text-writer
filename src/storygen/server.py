import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .application.settings import AppSettings


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {'fsck', 'backup', 'restore'}:
        from .maintenance import main as maintenance_main
        return maintenance_main(argv)
    parser=argparse.ArgumentParser(description='Локальна майстерня оповідань українською')
    parser.add_argument('--data-dir',type=Path,default=Path.cwd()/'data')
    parser.add_argument('--env-file',type=Path,default=Path.cwd()/'.env')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open-browser',action='store_true')
    args=parser.parse_args(argv)
    from .web.app import create_app
    import uvicorn
    settings=AppSettings(data_dir=args.data_dir.resolve(),env_file=args.env_file.resolve(),port=args.port)
    app=create_app(settings)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=settings.port,workers=1,log_level='info'))
    done=threading.Event()
    def open_when_ready():
        while not done.wait(.1):
            if server.started:
                webbrowser.open(f'http://127.0.0.1:{settings.port}')
                return
    if args.open_browser:threading.Thread(target=open_when_ready,daemon=True).start()
    try:
        server.run()
    finally:
        done.set()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
