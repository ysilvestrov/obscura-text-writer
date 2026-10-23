from importlib.resources import files
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..application.settings import AppSettings
from ..domain import RevisionConflict, StorageCorruption
from ..storage.repository import Repository
from ..generation.worker import RunCoordinator


def create_app(settings: AppSettings, *, gateway_factory=None,evaluator_factory=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.coordinator.start()
        try:
            yield
        finally:
            app.state.coordinator.stop()

    app=FastAPI(title="Obscura Text Writer",docs_url=None,redoc_url=None,lifespan=lifespan)
    load_dotenv(settings.env_file)
    app.state.settings=settings
    app.state.repo=Repository(settings.data_dir)
    app.state.gateway_factory=gateway_factory
    app.state.coordinator=RunCoordinator(app.state.repo,gateway_factory,evaluator_factory)
    root=files("storygen.web")
    app.state.templates=Jinja2Templates(directory=str(root.joinpath("templates")))
    app.mount("/static",StaticFiles(directory=str(root.joinpath("static"))),name="static")

    @app.middleware("http")
    async def local_requests(request: Request,call_next):
        hostname=request.url.hostname
        if hostname not in {"127.0.0.1","localhost","::1"}:
            return JSONResponse({"detail":"Дозволено лише локальний доступ"},status_code=403)
        origin=request.headers.get("origin")
        if request.method not in {"GET","HEAD","OPTIONS"} and origin:
            parsed=urlparse(origin)
            if parsed.netloc!=request.headers.get("host") or parsed.scheme!=request.url.scheme:
                return JSONResponse({"detail":"Запит з іншого сайту відхилено"},status_code=403)
        response=await call_next(request)
        # Relative ES module imports must be refreshed together with the document.
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(RevisionConflict)
    async def conflict(request,exc):
        return JSONResponse({"detail":str(exc)},status_code=409)

    @app.exception_handler(StorageCorruption)
    async def corrupt(request,exc):
        return JSONResponse({"detail":str(exc)},status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request,exc):
        return JSONResponse({"detail":"Матеріал не знайдено"},status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):
        return JSONResponse({"detail":"Некоректні дані: "+str(exc)[:500]},status_code=400)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):
        fields=[]
        allowed={'provider','model','base_url','timeout','key_env','include_usage','response_mode','venice_include_system_prompt','venice_disable_thinking','venice_reasoning_effort','context_tokens','max_output_tokens','max_input_chars','temperature'}
        for error in exc.errors():
            loc=error.get('loc',())
            if len(loc)>=3 and tuple(loc[:3])==('body','settings','classification'):
                path='.'.join(part for part in loc[3:] if isinstance(part,str) and part in allowed)
                fields.append(path or 'профіль')
        if fields:
            return JSONResponse({'detail':'Профіль класифікатора: перевірте поля '+', '.join(dict.fromkeys(fields))},status_code=422)
        return JSONResponse({'detail':'Перевірте формат і допустимі значення полів'},status_code=422)

    from .routes_stories import router
    app.include_router(router)
    from .routes_settings import router as settings_router
    app.include_router(settings_router)
    from .routes_role_profiles import router as role_profiles_router
    app.include_router(role_profiles_router)
    from .routes_characters import router as characters_router
    app.include_router(characters_router)
    from .routes_runs import router as runs_router
    from .routes_versions import router as versions_router
    app.include_router(runs_router)
    app.include_router(versions_router)
    from .routes_evaluation import router as evaluation_router
    app.include_router(evaluation_router)
    from .routes_exports import router as exports_router
    app.include_router(exports_router)
    from .routes_publication import router as publication_router
    app.include_router(publication_router)
    from .routes_budget import router as budget_router
    app.include_router(budget_router)
    from .routes_statistics import router as statistics_router
    app.include_router(statistics_router)
    return app
