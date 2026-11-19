import os

from flask import Flask, Response, render_template, request
from jinja2 import select_autoescape

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


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["VERCEL_ANALYTICS_ENABLED"] = os.getenv("VERCEL") is not None
    app.jinja_env.autoescape = select_autoescape(
        ("html", "htm", "xml", "xhtml", "svg", "jinja"), default_for_string=True
    )
    app.add_url_rule("/", view_func=index)
    app.after_request(add_security_headers)
    app.after_request(cache_pages)
    return app


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
