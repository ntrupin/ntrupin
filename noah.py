from datetime import datetime
import os

from flask import Flask, redirect, render_template

from noah import db, meta

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = os.getenv("SECRET_KEY")

    from noah.auth import setup as auth_setup
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

@app.route("/index.html")
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

@app.route("/cv")
def cv():
    return show_id(2)

from noah.auth import bp as auth_bp
app.register_blueprint(auth_bp)

from noah.writing import bp as writing_bp, show_id
app.register_blueprint(writing_bp)
