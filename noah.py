from datetime import datetime, timedelta
import hmac
import os
import secrets

from flask import Flask, Response, g, make_response, redirect, render_template, request, session

from server import db, meta

ANON_BROWSER_CACHE_CONTROL = "public, max-age=0, must-revalidate"
ANON_CDN_CACHE_CONTROL = "public, s-maxage=300, stale-while-revalidate=86400"
PRIVATE_CACHE_CONTROL = "private, no-store, max-age=0"
CSRF_SESSION_KEY = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

BASE_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' https: data:; "
    "connect-src 'self' https://vitals.vercel-insights.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)

def get_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if token:
        return token
    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="./templates",
        static_folder="./static",
    )
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise ValueError("Expected SECRET_KEY")
    app.secret_key = secret_key
    default_secure_cookie = (
        os.getenv("VERCEL") is not None
        or os.getenv("ENV", "").lower() == "production"
    )
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=(
            os.getenv(
                "SESSION_COOKIE_SECURE",
                "true" if default_secure_cookie else "false",
            ).lower() == "true"
        ),
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    )

    from server.auth import setup as auth_setup
    auth_setup(app)

    return app

app = create_app()

@app.context_processor
def inject_vars():
    return {
        "now": datetime.utcnow(),
        "csrf_token": get_csrf_token(),
    }

@app.before_request
def csrf_protect():
    if request.method in SAFE_HTTP_METHODS:
        return None
    expected_token = session.get(CSRF_SESSION_KEY)
    provided_token = (
        request.headers.get(CSRF_HEADER_NAME)
        or request.form.get("csrf_token")
    )
    if not expected_token or not provided_token:
        return "Forbidden", 403
    if not hmac.compare_digest(provided_token, expected_token):
        return "Forbidden", 403
    return None

@app.after_request
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

@app.errorhandler(403)
def forbidden(_):
    cfg = meta.Metadata()
    return render_template("403.jinja", **cfg.serialize()), 403

@app.errorhandler(404)
def page_not_found(_):
    cfg = meta.Metadata()
    return render_template("404.jinja", **cfg.serialize()), 404

@app.route("/index/")
def redirect_index():
    return redirect('/', code=301)

def cache_anonymous_page(response: Response) -> Response:
    response.vary.add("Cookie")
    if getattr(g, "user", None) is None:
        response.headers["Cache-Control"] = ANON_BROWSER_CACHE_CONTROL
        response.headers["CDN-Cache-Control"] = ANON_CDN_CACHE_CONTROL
        response.headers["Vercel-CDN-Cache-Control"] = ANON_CDN_CACHE_CONTROL
    else:
        response.headers["Cache-Control"] = PRIVATE_CACHE_CONTROL
        response.headers.pop("CDN-Cache-Control", None)
        response.headers.pop("Vercel-CDN-Cache-Control", None)
    return response

@app.route("/")
def index():
    cfg = meta.Metadata()
    updates = db.get_updates(5)
    response = make_response(render_template(
        "index.jinja",
        **cfg.serialize(),
        updates=updates
    ))
    return cache_anonymous_page(response)

@app.route("/updates/")
def updates():
    cfg = meta.Metadata(
        title="Updates | Noah Trupin",
        description="All updates from Noah Trupin."
    )
    response = make_response(render_template(
        "updates/index.jinja",
        **cfg.serialize(),
        updates=db.get_updates()
    ))
    return cache_anonymous_page(response)

@app.route("/cv/")
def cv():
    return show_canonical("cv")

@app.route("/play/<string:name>/")
def play(name: str):
    cfg = meta.Metadata()
    return render_template(
        "react.jinja",
        **cfg.serialize(),
        name=name
    )


from server.auth import bp as auth_bp
app.register_blueprint(auth_bp)

from server.reading import bp as reading_bp
app.register_blueprint(reading_bp)

from server.writing import bp as writing_bp, show_canonical
app.register_blueprint(writing_bp)

from server.projects import bp as projects_bp
app.register_blueprint(projects_bp)

from server.admin import bp as admin_bp
app.register_blueprint(admin_bp)

from server.draft_optimizer.draft_optimizer.web import create_blueprint
draft_bp = create_blueprint()
@draft_bp.before_request
def auth():
    if g.user is None:
        return "Forbidden", 403
app.register_blueprint(draft_bp, url_prefix="/baseball-draft")
