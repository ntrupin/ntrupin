from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, current_app
)
from werkzeug.exceptions import abort
import markdown
import markdown.extensions.fenced_code
import markdown.extensions.tables
import markdown.extensions.nl2br

from noah.auth import login_required
from noah.db import get_db, execute, Count

bp = Blueprint("posts", __name__, url_prefix="/posts")

@bp.route("/")
def index():
    posts = execute(
        "SELECT p.id, title, body, public, created, author_id, username"
        " FROM posts p JOIN users u ON p.author_id = u.id"
        " WHERE public IN %s"
        " ORDER BY created DESC",
        args=((True,) if g.user is None else (True, False),),
        retmode=Count.ALL
    )
    return render_template("posts/index.html", posts=posts)

@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        error = None
        title = request.form["title"]
        body = request.form["body"]
        public = "public" in request.form
        if not title:
            error = "Title is required."
        if error is not None:
            flash(error)
        else:
            execute(
                "INSERT INTO posts (title, body, public, author_id)"
                " VALUES (%s, %s, %s, %s)",
                args=(title, body, public, g.user["id"])
            )
            return redirect(url_for("posts.index"))

    return render_template("posts/create.html")

def get_post(id, check_author=True):
    post = execute(
        "SELECT p.id, title, body, public, created, author_id, username"
        " FROM posts p JOIN users u ON p.author_id = u.id"
        " WHERE p.id = %s AND public IN %s ",
        args=(id, (True,) if g.user is None else (True, False)),
        retmode=Count.ONE
    )
    if post is None:
        abort(404, f"Post with id {id} does not exist.")
    if check_author and post["author_id"] != g.user["id"]:
        abort(403)
    return post

@bp.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    post = get_post(id)
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        public = "public" in request.form
        error = None
        if not title:
            error = "Title is required"
        if error is not None:
            flash(error)
        else:
            execute(
                "UPDATE posts SET title = %s, body = %s, public = %s"
                " WHERE ID = %s",
                args=(title, body, public, id)
            )
            return redirect(url_for("posts.show", id=id))

    return render_template("posts/update.html", post=post)

@bp.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    get_post(id)
    execute("DELETE FROM posts WHERE id = %s", args=(id,))
    return redirect(url_for("posts.index"))

@bp.route("/<int:id>", methods=("GET",))
def show(id):
    post = dict(get_post(id, False))
    post["body"] = markdown.markdown(post["body"], extensions=["fenced_code", "tables", "nl2br"])
    return render_template("posts/show.html", post=post)