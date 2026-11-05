"""Request-body limits applied before FastAPI parses anything.

FastAPI reads (and spools to disk) a multipart upload before route dependencies such as sign-in run, so without
this anyone could make the server write large bodies without an account. This middleware:
- refuses an upload to /api/analyses without a valid, unexpired sign-in token before reading the body;
- refuses bodies over the limit up front when Content-Length says so, and stops reading a body (for example a
  chunked one) as soon as it passes the limit.
The full account check (approved, token not revoked) still happens in the route.
"""
from __future__ import annotations

import json

import jwt

import config

UPLOAD_PATH_SUFFIX = "/api/analyses"
MULTIPART_OVERHEAD = 1024 * 1024        # form fields and boundaries around the file
MAX_JSON_BODY_BYTES = 6 * 1024 * 1024   # the largest JSON body is an edited report (limited to 5 MB in app.py)
BODY_METHODS = {"POST", "PUT", "PATCH"}


class _TooLarge(Exception):
    pass


def upload_limit() -> int:
    return config.MAX_UPLOAD_MB * 1024 * 1024 + MULTIPART_OVERHEAD


async def _send_json(send, status_code: int, detail: str, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send({"type": "http.response.start", "status": status_code,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())] + (headers or [])})
    await send({"type": "http.response.body", "body": body})


def _has_valid_token(scope) -> bool:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            if scheme.lower() != "bearer" or not token:
                return False
            try:
                jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
                return True
            except jwt.PyJWTError:
                return False
    return False


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in BODY_METHODS:
            return await self.app(scope, receive, send)

        is_upload = scope["method"] == "POST" and scope["path"].rstrip("/").endswith(UPLOAD_PATH_SUFFIX)
        if is_upload and not _has_valid_token(scope):
            return await _send_json(send, 401, "Not signed in", [(b"www-authenticate", b"Bearer")])

        limit = upload_limit() if is_upload else MAX_JSON_BODY_BYTES
        too_large = f"Files are limited to {config.MAX_UPLOAD_MB} MB" if is_upload else "The request is too large"
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    return await _send_json(send, 400, "Invalid Content-Length")
                if declared > limit:
                    return await _send_json(send, 413, too_large)

        received = 0
        exceeded = False
        replaced = False

        async def limited_receive():
            # Past the limit, report a disconnect instead of handing over more data: FastAPI then stops parsing.
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _TooLarge
            return message

        async def guarded_send(message):
            # The framework may turn the aborted read into its own error reply; send a clear 413 instead.
            nonlocal replaced
            if exceeded:
                if message["type"] == "http.response.start" and not replaced:
                    replaced = True
                    await _send_json(send, 413, too_large)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise  # a real error, not the aborted read
        if exceeded and not replaced:
            await _send_json(send, 413, too_large)
