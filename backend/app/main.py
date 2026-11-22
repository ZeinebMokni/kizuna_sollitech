import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, request_id_var
from app.modules.advanced.routes import router as advanced_router
from app.modules.data_sources.routes import router as data_router
from app.modules.devices.mqtt import MqttTelemetryService
from app.modules.devices.routes import router as devices_router
from app.modules.farms.routes import router as farms_router
from app.modules.identity.routes import router as identity_router
from app.modules.recommendations.routes import router as recommendations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    service = None
    if settings.mqtt_enabled:
        service = MqttTelemetryService(
            host=settings.mqtt_host,
            port=settings.mqtt_port,
            topic=settings.mqtt_topic,
        )
        service.start()
        app.state.mqtt_service = service
    try:
        yield
    finally:
        if service is not None:
            service.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="QATRA Platform API",
        version="0.2.0",
        description="Trusted agricultural data and decision platform",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(identity_router)
    app.include_router(farms_router)
    app.include_router(data_router)
    app.include_router(devices_router)
    app.include_router(recommendations_router)
    app.include_router(advanced_router)
    return app


app = create_app()
