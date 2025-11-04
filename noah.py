from datetime import datetime
import os

from flask import Flask, redirect, render_template

from server import db, meta

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

@app.route("/")
def index():
    cfg = meta.Metadata()
    updates = db.get_updates(5)
    return render_template(
        "index.jinja",
        **cfg.serialize(),
        updates=updates
    )

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
