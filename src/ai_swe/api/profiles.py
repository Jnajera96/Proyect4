"""Cookie-authenticated profile boundary and direct, streaming ASGI dispatch."""

from __future__ import annotations

import asyncio
import json
import math
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import HTTPConnection

from ai_swe.config import Settings
from ai_swe.resources import frontend_dist
from ai_swe.runtime_logging import profile_log_context
from ai_swe.security.vault import VaultError
from ai_swe.state.budget_ledger import BudgetLedger, LedgerError
from ai_swe.state.profiles import ProfileStore, UnlockedProfile

COOKIE = "aiswe_session"
SAFE = {"GET", "HEAD", "OPTIONS"}


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=12, max_length=1024)


class VaultConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    hf_token: SecretStr | None = None  # null preserves, empty explicitly clears
    model_name: str = Field(default="", max_length=120)
    reviewer_model: str = Field(default="", max_length=120)
    model_provider: str = "openai_compatible"
    model_base_url: str = "https://router.huggingface.co/v1"
    remote_model_roles: list[str] = Field(default_factory=list, max_length=2)
    model_pricing: str = Field(default="", max_length=16000)
    budget_limit: float = Field(ge=0)
    max_cost_per_run: float = Field(gt=0)

    def vault_data(self, previous: dict):
        from ai_swe.models.pricing import pricing_from_json

        if self.model_provider != "openai_compatible":
            raise ValueError("Selecciona un proveedor compatible con OpenAI")
        parsed = urlsplit(self.model_base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("El endpoint remoto debe usar HTTPS sin credenciales en la URL")
        if any(role not in {"coder", "reviewer"} for role in self.remote_model_roles):
            raise ValueError("Rol remoto invalido")
        table = pricing_from_json(self.model_pricing)
        prices = json.loads(self.model_pricing or "[]")
        if any(
            p.get("currency", "USD").upper() != "USD"
            or not all(math.isfinite(p[k]) for k in ("input_per_1k", "output_per_1k"))
            for p in prices
        ):
            raise ValueError("Declara tarifas finitas en USD")
        data = self.model_dump(exclude={"hf_token"})
        data["hf_token"] = (
            previous.get("hf_token", "")
            if self.hf_token is None
            else self.hf_token.get_secret_value()
        )
        models = {self.model_name.strip().lower()}
        if "reviewer" in self.remote_model_roles:
            models.add((self.reviewer_model or self.model_name).strip().lower())
        if self.remote_model_roles and (
            not data["hf_token"].strip()
            or not self.budget_limit
            or not models.issubset(set(table.known_models()))
        ):
            raise ValueError("Para activar IA remota declara token, modelos, tarifas y limite")
        return data


@dataclass
class ProfileContext:
    profile: UnlockedProfile
    app: FastAPI
    lifetime: object
    requests: int = 0


@dataclass
class Session:
    token: str
    csrf: str
    user_id: str
    expires: float


class ProfileManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = ProfileStore(settings.profiles_root or settings.state_db_path.parent / "users")
        self.sessions: dict[str, Session] = {}
        self.contexts: dict[str, ProfileContext] = {}
        self.lock = asyncio.Lock()
        self.attempts: dict[str, deque] = defaultdict(deque)

    def throttle(self, client: str):
        now = time.monotonic()
        attempts = self.attempts[client]
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Demasiados intentos; espera un minuto")
        attempts.append(now)

    def session(self, request: HTTPConnection) -> Session | None:
        session = self.sessions.get(request.cookies.get(COOKIE, ""))
        return session if session and session.expires > time.monotonic() else None

    async def open_context(self, profile: UnlockedProfile):
        from ai_swe.api.app import crear_app

        token = profile_log_context.set(profile.user_id)
        try:
            child = crear_app(settings=profile.settings(self.settings))
            child.state.profile = profile
            child.state.ledger = BudgetLedger(profile.paths.database)
            lifetime = child.router.lifespan_context(child)
            await lifetime.__aenter__()
            context = ProfileContext(profile, child, lifetime)
            self.contexts[profile.user_id] = context
            return context
        finally:
            profile_log_context.reset(token)

    async def login(self, profile: UnlockedProfile):
        async with self.lock:
            if profile.user_id not in self.contexts:
                await self.open_context(profile)
            session = Session(
                secrets.token_urlsafe(32),
                secrets.token_urlsafe(32),
                profile.user_id,
                time.monotonic() + self.settings.profile_session_seconds,
            )
            self.sessions[session.token] = session
            return session

    async def prune(self):
        async with self.lock:
            self.sessions = {k: s for k, s in self.sessions.items() if s.expires > time.monotonic()}
            live = {s.user_id for s in self.sessions.values()}
            for uid, context in list(self.contexts.items()):
                if uid not in live and not context.requests:
                    await self.close_context(uid)

    async def close_context(self, uid):
        context = self.contexts.pop(uid)
        token = profile_log_context.set(uid)
        try:
            await context.lifetime.__aexit__(None, None, None)
        finally:
            profile_log_context.reset(token)

    async def shutdown(self):
        async with self.lock:
            self.sessions.clear()
            for uid in list(self.contexts):
                await self.close_context(uid)


class ProfileDispatch:
    def __init__(self, manager):
        self.manager = manager

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        request = HTTPConnection(scope)
        async with self.manager.lock:
            session = self.manager.session(request)
            if not session and scope["path"] == "/health":
                await JSONResponse({"status": "ok", "profile_mode": True})(scope, receive, send)
                return
            if not session:
                await JSONResponse({"detail": "Autenticacion requerida"}, status_code=401)(
                    scope, receive, send
                )
                return
            if scope["method"] not in SAFE and not valid_csrf(request, session):
                await JSONResponse({"detail": "CSRF invalido"}, status_code=403)(
                    scope, receive, send
                )
                return
            context = self.manager.contexts[session.user_id]
            context.requests += 1
        token = profile_log_context.set(session.user_id)
        try:
            # Direct ASGI call: SSE is never buffered by a proxy or response collector.
            await context.app(scope, receive, send)
        finally:
            profile_log_context.reset(token)
            async with self.manager.lock:
                context.requests -= 1
            await self.manager.prune()


def same_origin(request: HTTPConnection) -> bool:
    if request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
        return False
    origin = request.headers.get("origin")
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
    return origin is None or origin == expected


def valid_csrf(request, session):
    return same_origin(request) and secrets.compare_digest(
        request.headers.get("x-csrf-token", ""), session.csrf
    )


def create_profile_app(settings: Settings) -> FastAPI:
    manager = ProfileManager(settings)

    @asynccontextmanager
    async def lifespan(app):
        async def reap():
            while True:
                await asyncio.sleep(30)
                await manager.prune()

        task = asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await manager.shutdown()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.profiles = manager
    app.state.settings = settings
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))

    @app.middleware("http")
    async def boundary(request, call_next):
        from ai_swe.api.app import CABECERAS_SEGURIDAD

        if request.method not in SAFE and not same_origin(request):
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        response = await call_next(request)
        for name, value in CABECERAS_SEGURIDAD.items():
            response.headers.setdefault(name, value)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Pydantic's usual error body can echo the password/token input.
        return JSONResponse(
            {"detail": "Campos invalidos; revisa nombre, contraseña y limites"}, status_code=422
        )

    def require_session(request):
        session = manager.session(request)
        if not session:
            raise HTTPException(401, "Autenticacion requerida")
        if request.method not in SAFE and not valid_csrf(request, session):
            raise HTTPException(403, "CSRF invalido")
        return session

    def status(session):
        profile = manager.contexts[session.user_id].profile
        return {
            "profile_mode": True,
            "authenticated": True,
            "user": {"id": profile.user_id, "name": profile.name},
            "csrf_token": session.csrf,
        }

    @app.get("/auth/status")
    async def auth_status(request: Request):
        session = manager.session(request)
        return status(session) if session else {"profile_mode": True, "authenticated": False}

    async def authenticate(request, credentials, create=False):
        manager.throttle(request.client.host if request.client else "local")
        # JSON enforces browser preflight; cross-origin requests are rejected above.
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "Usa JSON")
        try:
            operation = manager.store.create if create else manager.store.unlock
            profile = await run_in_threadpool(
                operation, credentials.name, credentials.password.get_secret_value()
            )
        except (ValueError, OSError, VaultError):
            raise HTTPException(
                400 if create else 401,
                "No se pudo crear el perfil" if create else "Credenciales incorrectas",
            ) from None
        session = await manager.login(profile)
        # Revoke the old session on account switch, without leaving old unlocked data behind.
        old = request.cookies.get(COOKIE)
        if old:
            manager.sessions.pop(old, None)
        await manager.prune()
        response = JSONResponse(status(session), status_code=201 if create else 200)
        response.set_cookie(
            COOKIE,
            session.token,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/",
            max_age=settings.profile_session_seconds,
        )
        return response

    @app.post("/auth/register")
    async def register(request: Request, credentials: Credentials):
        return await authenticate(request, credentials, True)

    @app.post("/auth/login")
    async def login(request: Request, credentials: Credentials):
        return await authenticate(request, credentials)

    @app.post("/auth/logout")
    async def logout(request: Request):
        session = require_session(request)
        manager.sessions.pop(session.token, None)
        await manager.prune()
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return response

    @app.get("/auth/vault")
    async def vault_status(request: Request):
        session = require_session(request)
        context = manager.contexts[session.user_id]
        public_fields = set(VaultConfig.model_fields) - {"hf_token"}
        data = {k: v for k, v in context.profile.data.items() if k in public_fields}
        return {
            **data,
            "has_token": bool(context.profile.data.get("hf_token")),
            "ledger": context.app.state.ledger.summary(),
        }

    @app.put("/auth/vault")
    async def configure(request: Request, config: VaultConfig):
        session = require_session(request)
        async with manager.lock:
            session = require_session(request)
            context = manager.contexts[session.user_id]
            if context.requests or context.app.state.worker.active:
                raise HTTPException(409, "Espera a que terminen las operaciones activas")
            try:
                data = config.vault_data(context.profile.data)
                # Validate settings before persisting any change.
                candidate = UnlockedProfile(
                    context.profile.user_id,
                    context.profile.name,
                    context.profile.paths,
                    context.profile.key,
                    context.profile.header,
                    data,
                )
                candidate.settings(settings)
                context.app.state.ledger.set_limit(config.budget_limit)
                context.profile.save(data)
            except (ValueError, LedgerError):
                raise HTTPException(
                    422, "Configuracion invalida: revisa token, tarifas y limites"
                ) from None
            profile = context.profile
            await manager.close_context(session.user_id)
            await manager.open_context(profile)
        return {"saved": True, "has_token": bool(data.get("hf_token"))}

    dist = frontend_dist()
    if dist.is_dir():
        app.mount("/app", StaticFiles(directory=dist, html=True), name="app")
    app.mount("/", ProfileDispatch(manager))
    return app
