import os
import psycopg2
import psycopg2.extras
from functools import partial
from enum import Enum, auto

import click
from flask import current_app, g

def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            os.environ['DATABASE_URL']
        )
        g.db.autocommit = True
    return g.db


def close_db(e=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()

def init_db():
    db = get_db()

    with db.cursor() as curs, current_app.open_resource("schema.sql") as f:
        curs.execute(f.read().decode("utf8"))

@click.command("init-db")
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

class Count(Enum):
    NONE = auto()
    ONE = auto()
    SOME = auto()
    ALL = auto()

def execute(cmd, args=None, retmode=Count.NONE, count=0):
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as curs:
        (lambda x: x() if args is None else x(args))(partial(curs.execute, cmd))
        return ({
            Count.ONE: curs.fetchone, 
            Count.SOME: lambda: curs.fetchmany(count),
            Count.ALL: curs.fetchall,
            Count.NONE: lambda: None
        }[retmode]())

