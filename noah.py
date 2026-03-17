from datetime import datetime
import os

from flask import Flask, Response, g, make_response, redirect, render_template, request

from server import db, meta

ANON_BROWSER_CACHE_CONTROL = "public, max-age=0, must-revalidate"
ANON_CDN_CACHE_CONTROL = "public, s-maxage=300, stale-while-revalidate=86400"
PRIVATE_CACHE_CONTROL = "private, no-store, max-age=0"

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="./templates",
        static_folder="./static",
    )
    app.secret_key = os.getenv("SECRET_KEY")

    from server.auth import setup as auth_setup
    auth_setup(app)

    return app

app = create_app()

@app.context_processor
def inject_vars():
    return {
        "now": datetime.utcnow()
    }

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

from server.draft_optimizer.draft_optimizer.web import create_blueprint
draft_bp = create_blueprint()
@draft_bp.before_request
def auth():
    if g.user is None:
        return "Forbidden", 403
app.register_blueprint(draft_bp, url_prefix="/baseball-draft")
