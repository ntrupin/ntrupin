from flask import Blueprint, render_template

from server import db, meta, models

bp = Blueprint("reading", __name__, url_prefix="/reading")

def get_readings(n: int = 100) -> list[models.Reading]:
    database = db.get()
    readings_data = (
        database.table("reading")
        .select("*")
        .limit(n)
        .order("created_at", desc=True)
        .execute()
    ).data
    return [models.Reading.from_dict(w) for w in readings_data]

@bp.route("/", methods=["GET"])
def index():
    reading = get_readings(1000)

    cfg = meta.Metadata()
    return render_template("reading/index.jinja", **cfg.serialize(), readings=reading)
