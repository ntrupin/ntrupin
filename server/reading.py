from datetime import datetime
import re

from flask import abort, Blueprint, g, redirect, render_template, request, url_for

from server import db, md, meta, models
from server.auth import login_required

bp = Blueprint("reading", __name__, url_prefix="/reading")

def get_readings(n: int = 100) -> list[models.Reading]:
    database = db.get()
    writings_data = (
        database.table("reading")
        .select("*")
        .limit(n)
        .order("created_at", desc=True)
        .execute()
    ).data
    return [models.Reading.from_dict(w) for w in writings_data]

@bp.route("/", methods=["GET"])
def index():
    reading = get_readings(1000)

    cfg = meta.Metadata()
    return render_template("reading/index.jinja", **cfg.serialize(), readings=reading)
