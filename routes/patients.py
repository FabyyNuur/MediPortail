from __future__ import annotations

from flask import Blueprint, render_template, request

import analytics as an

bp = Blueprint("patients", __name__, url_prefix="")


@bp.route("/patients")
def patients_list():
    df = an.get_prepared_dataframe()
    page = max(1, int(request.args.get("page", 1)))
    search = request.args.get("search", "").strip()
    dept = request.args.get("dept", "Tous")
    status = request.args.get("status", "Tous")
    risk = request.args.get("risk", "Tous")
    sort_key = request.args.get("sort")
    sort_dir = request.args.get("dir", "asc")
    rows, total = an.patients_list_paginated(
        df, page=page, page_size=8, search=search, dept=dept, status=status, risk=risk,
        sort_key=sort_key, sort_dir=sort_dir,
    )
    page_size = 8
    total_pages = max(1, (total + page_size - 1) // page_size)
    stats = an.stats_patients_page(df)
    depts = ["Tous"] + sorted(df["Departement"].unique().tolist())
    pages = list(range(1, total_pages + 1))
    return render_template(
        "patients.html",
        rows=rows,
        total=total,
        page=page,
        total_pages=total_pages,
        pages=pages,
        stats=stats,
        search=search,
        dept=dept,
        status=status,
        risk=risk,
        sort_key=sort_key or "",
        sort_dir=sort_dir,
        depts=depts,
    )
