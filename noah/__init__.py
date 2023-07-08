import os
from datetime import datetime

from flask import Flask, render_template

# create and configure application
def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DB_URL=os.environ["DATABASE_URL"]
    )

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # inject current time into template 
    @app.context_processor
    def inject_now():
        return { "now": datetime.utcnow() }
    
    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)
    auth.init_app(app)

    from . import projects
    app.register_blueprint(projects.bp)

    from . import rss
    app.register_blueprint(rss.bp)

    @app.route("/")
    def index():
        return render_template("index.html")
    
    @app.route("/about")
    def about():
        return render_template("about.html")
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    return app