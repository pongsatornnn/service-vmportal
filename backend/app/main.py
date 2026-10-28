import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.console import router as console_router
from app.api.errors import public_message, validation_message
from app.api.passwords import router as password_router
from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()
app = FastAPI(
    title="Proxmox Self-Service Portal",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.include_router(router)
app.include_router(password_router)
app.include_router(console_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Never echo submitted password/token/CA input in validation errors.
    return JSONResponse(
        {
            "message": "กรุณาตรวจข้อมูลที่กรอกตามรายละเอียดด้านล่าง",
            "detail": [
                {"loc": e["loc"], "msg": validation_message(e), "type": e["type"]}
                for e in exc.errors()
            ],
        },
        status_code=422,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    if getattr(request.state, "user_role", None) == "user" and exc.detail in (
        "Complete system setup first",
        "Verify connection and enable the system in Setup first",
    ):
        return JSONResponse(
            {"detail": "ระบบยังไม่พร้อม", "message": "ระบบยังไม่พร้อม"},
            status_code=exc.status_code,
            headers=exc.headers,
        )
    return JSONResponse(
        {"detail": exc.detail, "message": public_message(exc.detail, exc.status_code)},
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logging.getLogger("portal.api").error(
            "request_failed", extra={"method": request.method, "path": request.url.path}
        )
        response = JSONResponse(
            {
                "detail": "Internal server error",
                "message": public_message("", 500),
                "request_id": request_id,
            },
            status_code=500,
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    logging.getLogger("portal.api").info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
        },
    )
    return response


# The existing reverse-proxy deployment leaves this unset. Standalone HTTPS
# serves the compiled UI after registering API and WebSocket routes.
if settings().portal_static_dir:
    from app.web import install_web

    install_web(app, settings().portal_static_dir)
# Outermost, so everything inside sees paths without the URL prefix.
if settings().portal_base_path:
    from app.web import BasePathMiddleware

    app.add_middleware(BasePathMiddleware, base=settings().portal_base_path)
