from flask import (Blueprint, render_template, make_response)

from noah.db import execute

bp = Blueprint("rss", __name__)

# generate an rss feed from public posts
@bp.route("/rss.xml")
def index():
    posts = execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM posts p JOIN users u ON p.author_id = u.id"
        " WHERE public IS TRUE"
        " ORDER BY created DESC",
    ).fetchall()
    t = render_template("rss.xml", 
        title="Noah Trupin", link="https://ntrupin.com", 
        description="Noah Trupin's website. Projects, writings, and maybe more.",
        items=posts)
    response = make_response(t)
    response.headers["Content-Type"] = "application/xml"
    return response