import psycopg2
import psycopg2.extras

import click
import flask
from flask import current_app, g

from typing import Any

def get():
    if "db" not in g:
        try:
            g.db = psycopg2.connect(current_app.config["DB_URL"])
        except:
            print("ERROR")
        g.db.autocommit = True
    return g.db

def setup(app: flask.Flask):
    app.teardown_appcontext(close)
    app.cli.add_command(init_db_command)

def query(cmd: str, args: list[Any] = []) -> list[psycopg2.extras.RealDictRow] | None:
    with get().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as curs:
        curs.execute(cmd, args)
        if curs.description is not None:
            return curs.fetchall()
        return None

def close(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

@click.command("init-db")
def init_db_command():
    with current_app.open_resource("lib/schema.sql") as f:
        exec(f.read.decode("utf8"))
    click.echo("database initialized")
