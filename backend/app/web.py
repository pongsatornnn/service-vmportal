"""Serve the compiled Portal UI when running HTTPS directly with Uvicorn."""

import re

from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
}


def cache_control(path):
    # Hashed build files never change; fonts rarely do. The page always revalidates.
    if path.startswith("/assets/"):
        return "public, max-age=31536000, immutable"
    if path.startswith("/fonts/"):
        return "public, max-age=2592000"
    return "no-cache"


class PortalFiles(StaticFiles):
    async def get_response(self, path, scope):
        if (
            any(
                part not in {"", "."} and part.startswith(".")
                for part in path.split("/")
            )
            or path == "api"
            or path.startswith("api/")
        ):
            raise HTTPException(404)
        return await super().get_response(path, scope)


class DirectWebMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def secured(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {key.lower() for key, _ in headers}
                extra = dict(HEADERS)
                if not scope["path"].startswith("/api/"):
                    extra["cache-control"] = (
                        cache_control(scope["path"])
                        if message["status"] < 400
                        else "no-store"
                    )
                headers.extend(
                    (key.encode(), value.encode())
                    for key, value in extra.items()
                    if key.encode() not in existing
                )
                message = {**message, "headers": headers}
            await send(message)

        # Match the standalone installer's reverse-proxy body limit, including
        # chunked requests. Buffer at most 128 KiB before parsing JSON/form data.
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            messages, size = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > 128 * 1024:
                    response = JSONResponse(
                        {"message": "ข้อมูลที่ส่งมีขนาดใหญ่เกินกำหนด"},
                        status_code=413,
                        headers={"Connection": "close", "Cache-Control": "no-store"},
                    )
                    return await response(scope, receive, secured)
                messages.append(message)
                if not message.get("more_body", False):
                    break
            pending = iter(messages)
            original_receive = receive

            async def replay():
                return next(pending, None) or await original_receive()

            receive = replay
        await self.app(scope, receive, secured)


BASE_PATH = re.compile(r"(?:/[a-z0-9][a-z0-9-]{0,62})+")


class BasePathMiddleware:
    """Serve the whole portal under a URL path such as /vmportal.

    Requests under the path reach the app with the prefix removed, so routes and
    static files stay unchanged; the bare site root redirects to the portal.
    """

    def __init__(self, app, base):
        if not BASE_PATH.fullmatch(base):
            raise ValueError("PORTAL_BASE_PATH must look like /vmportal")
        self.app, self.base = app, base

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path.startswith(self.base + "/"):
            inner = {
                **scope,
                "path": path[len(self.base) :],
                "raw_path": scope.get("raw_path", b"")[len(self.base) :],
                "root_path": scope.get("root_path", "") + self.base,
            }
            return await self.app(inner, receive, send)
        if scope["type"] == "http" and path in {self.base, "/"}:
            response = RedirectResponse(self.base + "/", status_code=307)
            return await response(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        response = JSONResponse({"message": "Not found"}, status_code=404)
        await response(scope, receive, send)


def install_web(app, directory):
    app.mount("/", PortalFiles(directory=directory, html=True), name="portal-web")
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(DirectWebMiddleware)
