"""URL-based locales and interface translation catalogs."""
from functools import lru_cache
import json
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, current_app, g, redirect, request, url_for as flask_url_for
from werkzeug.exceptions import HTTPException

LOCALES = ("en", "ko")
ROOT = Path(__file__).parent / "translations"
LOCALIZED_ENDPOINTS = {}


def base_endpoint(endpoint):
    return endpoint.removeprefix("ko_") if endpoint else None


def locale():
    return getattr(g, "locale", "en")


@lru_cache(maxsize=4)
def catalog(language):
    path = ROOT / language / "ui.json"
    return json.loads(path.read_text()) if path.exists() else {}


def translate(message):
    return catalog(locale()).get(message, message)


def url_for(endpoint, **values):
    language = values.pop("_locale", locale())
    endpoint = base_endpoint(endpoint)
    if language == "ko":
        endpoint = LOCALIZED_ENDPOINTS.get(endpoint, endpoint)
    return flask_url_for(endpoint, **values)


def page_url(language, external=False):
    endpoint = base_endpoint(request.endpoint)
    if endpoint not in LOCALIZED_ENDPOINTS:
        endpoint, values = "index", {}
    else:
        values = dict(request.view_args or {})
    return url_for(endpoint, _locale=language, _external=external, **values)


def format_date(value, short=False):
    if locale() == "ko":
        if short:
            return value.strftime("%Y.%m.%d.")
        return f"{value.year}년 {value.month}월 {value.day}일"
    return value.strftime("%b %d, %Y" if short else "%B %d, %Y")



def setup(app):
    @app.before_request
    def choose_locale():
        g.locale = "ko" if request.path == "/ko" or request.path.startswith("/ko/") else "en"
        if request.endpoint == "index" and request.method in {"GET", "HEAD"}:
            selected = request.cookies.get("language")
            if selected not in LOCALES:
                selected = request.accept_languages.best_match(LOCALES, default="en")
            if selected == "ko":
                return redirect(flask_url_for("ko_index"), code=302)

    @app.after_request
    def language_headers(response):
        if response.mimetype == "text/html":
            response.headers["Content-Language"] = locale()
        if request.endpoint == "index":
            response.vary.add("Accept-Language")
        return response

    @app.context_processor
    def language_context():
        return {
            "_": translate, "locale": locale(),
            "has_language_versions": base_endpoint(request.endpoint) in LOCALIZED_ENDPOINTS, "base_endpoint": base_endpoint,
            "page_url": page_url, "format_date": format_date,
            "language_switch_url": lambda language: flask_url_for(
                "set_language", language=language, next=page_url(language)
            ),
        }

    app.jinja_env.globals["url_for"] = url_for

    @app.get("/language/<language>/")
    def set_language(language):
        if language not in LOCALES:
            abort(404)
        target = request.args.get("next", "/")
        try:
            parsed = urlsplit(target)
        except ValueError:
            target, parsed = "/", urlsplit("/")
        destination = url_for("index", _locale=language)
        if not parsed.scheme and not parsed.netloc and target.startswith("/") and "\\" not in target:
            try:
                endpoint, values = current_app.url_map.bind_to_environ(request.environ).match(parsed.path, method="GET")
                endpoint = base_endpoint(endpoint)
                if endpoint in LOCALIZED_ENDPOINTS:
                    destination = url_for(endpoint, _locale=language, **values)
            except HTTPException:
                pass
        response = redirect(destination, code=303)
        response.set_cookie("language", language, max_age=31536000, httponly=True,
                            secure=current_app.config["SESSION_COOKIE_SECURE"], samesite="Lax")
        return response


def register_routes(app):
    for rule in list(app.url_map.iter_rules()):
        endpoint = rule.endpoint
        if endpoint in {"index", "updates", "cv"} or endpoint.startswith(("writing.", "reading.", "auth.")):
            translated = "ko_" + endpoint
            LOCALIZED_ENDPOINTS[endpoint] = translated
            app.add_url_rule("/ko" + rule.rule, endpoint=translated,
                             view_func=app.view_functions[endpoint],
                             methods=rule.methods, defaults=rule.defaults)
