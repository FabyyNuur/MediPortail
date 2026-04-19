from __future__ import annotations

from flask import Blueprint, jsonify, request

import analytics as an

bp = Blueprint("api", __name__, url_prefix="/api")


ALLOWED_AXES = frozenset({"age", "duree", "risque", "douleur", "maladie", "traitement", "service"})


@bp.route("/decision-support")
def decision_support():
    df = an.get_prepared_dataframe()
    dept = request.args.get("dept", "Tous")
    sex = request.args.get("sex", "Tous")
    maladie = request.args.get("maladie", "Toutes")
    traitement = request.args.get("traitement", "Tous")
    sub = an.filter_decision_df(df, dept=dept, sex=sex, maladie=maladie, traitement=traitement)

    bundle = an.decision_support_bundle(sub, max_points=450)
    ax = request.args.get("axis_x", "age")
    ay = request.args.get("axis_y", "duree")
    if ax not in ALLOWED_AXES:
        ax = "age"
    if ay not in ALLOWED_AXES:
        ay = "duree"

    bundle["axis_x"] = ax
    bundle["axis_y"] = ay
    # Rétrocompatibilité champ risk count name
    bundle["high_risk_count"] = bundle.get("high_risk_count", 0)
    return jsonify(bundle)
