import psycopg2
import psycopg2.extras

import click
import flask
from flask import current_app, g

# fetch current db
# connects to db if no connection active
def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            current_app.config["DB_URL"]
        )
        g.db.autocommit = True
    return g.db

# close connection if exists
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# init db using schema
def init_db():
    db = get_db() 
    with current_app.open_resource("schema.sql") as f:
        execute(f.read.decode("utf8"))

# click command for init_db
@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("database initialized")

# register teardown and click command
def init_app(app: flask.Flask):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

# db query helper 
def execute(cmd: str, args: list[any] = []):
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as curs:
        curs.execute(cmd, args)
        if curs.description is not None:
            return curs.fetchall()
        return None
    