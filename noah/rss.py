from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, make_response
)
from werkzeug.exceptions import abort

from noah.db import get_db, execute, Count

bp = Blueprint("rss", __name__)

@bp.route("/rss.xml")
def index():
    posts = execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM posts p JOIN users u ON p.author_id = u.id"
        " WHERE public IN %s"
        " ORDER BY created DESC",
        args=((True,) if g.user is None else (True, False),),
        retmode=Count.ALL
    )
    t = render_template("rss.xml", 
        title="Noah Trupin", link="https://ntrupin.com", 
        description="Noah Trupin's website. Projects, writings, and maybe more.",
        items=posts)
    response = make_response(t)
    response.headers["Content-Type"] = "application/xml"
    return response