from importlib.resources import files
from jinja2 import pass_context
from .localization import request_locale, translate, diagnostic
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
from .bridge_marker import RUN_OWNER_ONLY, BridgeForbidden, author_only_path, from_bridge
from ..storage.repository import Repository
from ..generation.worker import RunCoordinator


def create_app(settings: AppSettings, *, gateway_factory=None,evaluator_factory=None) -> FastAPI:
    # BUILD-EDITION-001-S04: an invalid build edition marker stops the start before any data directory is touched.
    from .. import build_edition
    build_edition.current()
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
    # DESKTOP-001: lets a second launch tell this process from any other program on the same port.
    from uuid import uuid4
    app.state.instance_id=uuid4().hex
    app.state.repo=Repository(settings.data_dir)
    app.state.gateway_factory=gateway_factory
    app.state.coordinator=RunCoordinator(app.state.repo,gateway_factory,evaluator_factory)
    root=files("storygen.web")
    app.state.templates=Jinja2Templates(directory=str(root.joinpath("templates")))
    @pass_context
    def ui_translate(context, key, **params):
        return translate(key,request_locale(context['request']),**params)
    def app_links():
        # BUILD-EDITION-001-S07: read on every render; only non-empty addresses, in a fixed order.
        from .. import build_edition
        edition=build_edition.current()
        pairs=[('app.link.support',edition.support_url),('app.link.waitlist',edition.waitlist_url),('app.link.report',edition.report_url)]
        return [{'key':key,'url':url} for key,url in pairs if url]
    app.state.templates.env.globals.update(t=ui_translate,ui_locale=request_locale,app_links=app_links)
    app.mount("/static",StaticFiles(directory=str(root.joinpath("static"))),name="static")

    def error_response(request,detail,status_code):
        localized=diagnostic(detail,request_locale(request))
        return JSONResponse({'detail':localized,'detail_original':detail},status_code=status_code)

    @app.middleware("http")
    async def local_requests(request: Request,call_next):
        hostname=request.url.hostname
        if hostname not in {"127.0.0.1","localhost","::1"}:
            return error_response(request,"Дозволено лише локальний доступ",403)
        origin=request.headers.get("origin")
        if request.method not in {"GET","HEAD","OPTIONS"} and origin:
            parsed=urlparse(origin)
            if parsed.netloc!=request.headers.get("host") or parsed.scheme!=request.url.scheme:
                return error_response(request,"Запит з іншого сайту відхилено",403)
        if from_bridge(request) and author_only_path(request.method,request.url.path):
            return error_response(request,RUN_OWNER_ONLY,403)
        response=await call_next(request)
        # Relative ES module imports must be refreshed together with the document.
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(RevisionConflict)
    async def conflict(request,exc):
        return error_response(request,str(exc),409)

    @app.exception_handler(BridgeForbidden)
    async def bridge_forbidden(request,exc):
        return error_response(request,str(exc),403)

    @app.exception_handler(StorageCorruption)
    async def corrupt(request,exc):
        return error_response(request,str(exc),409)

    @app.exception_handler(KeyError)
    async def missing(request,exc):
        return error_response(request,"Матеріал не знайдено",404)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):
        return error_response(request,"Некоректні дані: "+str(exc)[:500],400)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):
        fields=[]
        allowed={'provider','model','base_url','timeout','key_env','include_usage','response_mode','venice_include_system_prompt','venice_disable_thinking','local_disable_thinking','venice_reasoning_effort','context_tokens','max_output_tokens','max_input_chars','temperature'}
        for error in exc.errors():
            loc=error.get('loc',())
            if len(loc)>=3 and tuple(loc[:3])==('body','settings','classification'):
                path='.'.join(part for part in loc[3:] if isinstance(part,str) and part in allowed)
                fields.append(path or 'профіль')
        if fields:
            return error_response(request,'Профіль класифікатора: перевірте поля '+', '.join(dict.fromkeys(fields)),422)
        return error_response(request,'Перевірте формат і допустимі значення полів',422)

    from .routes_stories import router
    app.include_router(router)
    from .routes_structure import router as structure_router
    app.include_router(structure_router)
    from .routes_settings import router as settings_router
    app.include_router(settings_router)
    from .routes_rating import router as rating_router
    app.include_router(rating_router)
    from .routes_app_info import router as app_info_router
    app.include_router(app_info_router)
    from .routes_provider_keys import router as provider_keys_router
    app.include_router(provider_keys_router)
    from .routes_role_profiles import router as role_profiles_router
    app.include_router(role_profiles_router)
    from .routes_characters import router as characters_router
    app.include_router(characters_router)
    from .routes_runs import router as runs_router
    from .routes_versions import router as versions_router
    app.include_router(runs_router)
    app.include_router(versions_router)
    from .routes_comments import router as comments_router
    app.include_router(comments_router)
    from .routes_rewrites import router as rewrites_router
    app.include_router(rewrites_router)
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
    from .routes_impact import router as impact_router
    app.include_router(impact_router)
    from .routes_review import router as review_router
    app.include_router(review_router)
    from .routes_model_policy import router as model_policy_router
    app.include_router(model_policy_router)
    return app
