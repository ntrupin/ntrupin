import os
from datetime import datetime

from flask import (Flask, render_template, g)
from noah.db import (execute, Count)

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "noah.sqlite"),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.context_processor
    def inject_now():
        return {"now": datetime.utcnow()}

    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)
    auth.init_app(app)

    from . import posts
    app.register_blueprint(posts.bp)

    from . import projects
    app.register_blueprint(projects.bp)

    from . import rss
    app.register_blueprint(rss.bp)

    @app.route("/")
    def index():
        projects = execute(
            "SELECT p.id, name, about, startdate, enddate, public, author_id, username"
            " FROM projects p JOIN users u ON p.author_id = u.id"
            " WHERE public IN %s"
            " ORDER BY enddate DESC NULLS FIRST, startdate DESC",
            args=((True,) if g.user is None else (True, False),),
            retmode=Count.ALL
        )
        posts = execute(
            "SELECT p.id, title, body, public, created, author_id, username"
            " FROM posts p JOIN users u ON p.author_id = u.id"
            " WHERE public IN %s"
            " ORDER BY created DESC",
            args=((True,) if g.user is None else (True, False),),
            retmode=Count.SOME,
            count=10
        )
        return render_template("index.html", projects=projects, posts=posts)
    
    return app