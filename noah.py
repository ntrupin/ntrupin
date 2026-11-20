from datetime import timedelta
import hmac
import json
import logging
import os
from pathlib import Path
import secrets

from flask import Flask, Response, abort, current_app, render_template, request, session
from jinja2 import select_autoescape

from server import auth, db, korean
from server.i18n import translate, url_for
from server.meta import Metadata


ANON_BROWSER_CACHE_CONTROL = "public, max-age=0, must-revalidate"
ANON_CDN_CACHE_CONTROL = "public, s-maxage=300, stale-while-revalidate=60"
PRIVATE_CACHE_CONTROL = "private, no-store, max-age=0"

BASE_CSP = (
    "default-src 'self'; "
    "script-src 'self'; script-src-attr 'none'; "
    "style-src 'self' 'unsafe-inline'; "
    "connect-src 'self' https://vitals.vercel-insights.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)


def create_app(config=None) -> Flask:
    app = Flask(__name__)
    production = os.getenv("VERCEL") is not None or os.getenv("ENV", "").lower() == "production"
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", str(production)).lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        VERCEL_ANALYTICS_ENABLED=os.getenv("VERCEL") is not None,
    )
    if config:
        app.config.update(config)
    app.logger.setLevel(logging.INFO)
    app.jinja_env.autoescape = select_autoescape(
        ("html", "htm", "xml", "xhtml", "svg", "jinja"), default_for_string=True
    )
    app.jinja_env.globals.update(csrf_token=get_csrf_token, url_for=url_for, _=translate)
    manifest_path = Path(app.static_folder) / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    @app.url_defaults
    def version_static_assets(endpoint, values):
        if endpoint == "static" and not app.debug:
            filename = values.get("filename")
            values["filename"] = manifest.get(filename, filename)

    app.add_url_rule("/", view_func=index)
    app.before_request(protect_forms)
    app.register_blueprint(auth.bp)
    app.register_blueprint(korean.bp)
    auth.setup(app)
    app.teardown_appcontext(db.close_clients)
    app.after_request(add_security_headers)
    app.after_request(cache_pages)
    return app


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def protect_forms():
    if request.blueprint not in {"auth", "korean"}:
        return
    if not current_app.secret_key:
        abort(503)
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    request.max_content_length = 24 * 1024
    expected = session.get("csrf_token")
    provided = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not expected or not provided or not hmac.compare_digest(expected.encode(), provided.encode()):
        abort(403)


def index() -> str:
    return render_template("index.jinja", **Metadata().serialize())


def add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", BASE_CSP)
    if request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )
    return response


def cache_pages(response: Response) -> Response:
    if request.endpoint == "static":
        if response.status_code == 200 and request.view_args["filename"].startswith("versioned/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    cacheable = (
        request.method in {"GET", "HEAD"}
        and response.status_code == 200
        and request.endpoint == "index"
        and not request.cookies
        and not request.headers.get("Authorization")
    )
    response.headers["Cache-Control"] = (
        ANON_BROWSER_CACHE_CONTROL if cacheable else PRIVATE_CACHE_CONTROL
    )
    if cacheable:
        response.headers["CDN-Cache-Control"] = ANON_CDN_CACHE_CONTROL
        response.headers["Vercel-CDN-Cache-Control"] = ANON_CDN_CACHE_CONTROL
    response.vary.add("Cookie")
    return response


app = create_app()
