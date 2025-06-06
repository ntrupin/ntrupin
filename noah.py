import os
from datetime import datetime

from flask import Flask, render_template, redirect
import markdown

from lib import pages

def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ["SECRET_KEY"],
        DB_URL=os.environ["DATABASE_URL"]
    )

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    return app

app = create_app()

from lib import db
db.setup(app)

# inject current time
@app.context_processor
def inject_vars():
    return {
        "now": datetime.utcnow()
    }

@app.route("/index.html")
def redirect_index():
    return redirect('/', code=301)

@app.route("/")
def index():
    # return r
    page = dict(pages.get_page_by_fuzzy_name("index"))
    extended = dict(pages.get_page_by_fuzzy_name("cv"))
    page["content"] = markdown.markdown(
        page["content"],
        extensions=["fenced_code", "tables", "nl2br", "toc"]
    )
    page["extended"] = markdown.markdown(
        extended["content"],
        extensions=["fenced_code", "tables", "nl2br"]
    )
    page["extended_id"] = extended["id"]
    return render_template("index.html", page=page), 200

from lib import auth
app.register_blueprint(auth.bp)
auth.setup(app)

from lib import pages
app.register_blueprint(pages.bp)

from lib import projects
app.register_blueprint(projects.bp)

from lib import links
app.register_blueprint(links.bp)

from lib import rss
app.register_blueprint(rss.bp)

@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404
