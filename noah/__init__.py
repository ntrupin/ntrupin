import os
from datetime import datetime

from flask import (Flask, render_template, g)
from noah.db import (execute, Count)
from noah.projects import get_projects

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "noah.sqlite"),
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

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
        projects = get_projects()
        return render_template("index.html", projects=projects, posts=[])

    @app.route("/experimental")
    def experimental():
        projects = get_projects()
        return render_template("experimental.html", projects=projects, posts=[])
    
    return app