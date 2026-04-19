from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from flask import Blueprint, Response, render_template, request, send_file, url_for

import analytics as an
from reporting.maquette import build_maquette_sheets, format_generated_date_long

_log = logging.getLogger(__name__)

bp = Blueprint("main", __name__)


def _hero_stats(filtered) -> list[dict]:
    if filtered.empty:
        return [
            {"label": "Patients suivis", "value": "0", "icon_key": "users"},
            {"label": "Départements", "value": "0 services", "icon_key": "building"},
            {"label": "Période couverte", "value": "—", "icon_key": "calendar"},
        ]
    da = filtered["DateAdmission"].dropna()
    if da.empty:
        period_str = "—"
    else:
        y1, y2 = int(da.dt.year.min()), int(da.dt.year.max())
        period_str = f"{y1}–{y2}" if y1 != y2 else str(y1)
    return [
        {"label": "Patients suivis", "value": f"{len(filtered):,}".replace(",", " "), "icon_key": "users"},
        {"label": "Départements", "value": f"{filtered['Departement'].nunique()} services", "icon_key": "building"},
        {"label": "Période couverte", "value": period_str, "icon_key": "calendar"},
    ]


def _filter_lists():
    df = an.get_prepared_dataframe()
    return {
        "sexes": sorted(df["Sexe"].unique().tolist()),
        "departements": sorted(df["Departement"].unique().tolist()),
        "maladies": sorted(df["Maladie"].unique().tolist()),
        "traitements": sorted(df["Traitement"].unique().tolist()),
    }


def _parse_filter_arg(name: str) -> list[str] | None:
    """Une valeur par select ; vide ou absent = pas de filtre sur ce champ."""
    v = (request.args.get(name) or "").strip()
    if not v:
        return None
    return [v]


def _period_arg() -> str:
    v = (request.args.get("periode") or "all").strip()
    return v if v in ("30", "90", "365", "all") else "all"


def _period_label() -> str:
    return {
        "30": "30 derniers jours",
        "90": "90 derniers jours",
        "365": "365 derniers jours",
        "all": "Toute la période",
    }.get(_period_arg(), "Toute la période")


def _dept_maquette_label() -> str:
    v = (request.args.get("dept") or "").strip()
    return v if v else "Tous les départements"


def _absolute_maquette_pdf_source_url() -> str:
    """URL joignable par Playwright pour rendre la même vue que les filtres passés à l’export."""
    override = (os.environ.get("MAQUETTE_PDF_BASE_URL") or "").rstrip("/")
    base = override if override else request.url_root.rstrip("/")
    path = url_for("main.rapport_maquette", _external=False)
    params = []
    for key in ("periode", "sexe", "dept", "maladie", "traitement"):
        val = (request.args.get(key) or "").strip()
        if val:
            params.append((key, val))
    qs = urlencode(params)
    return f"{base}{path}?{qs}" if qs else f"{base}{path}"


def _active_filter_count() -> int:
    n = sum(
        1
        for key in ("sexe", "dept", "maladie", "traitement")
        if (request.args.get(key) or "").strip()
    )
    if _period_arg() != "all":
        n += 1
    return n


@bp.route("/")
def dashboard():
    raw = an.get_prepared_dataframe()
    df = an.apply_period_filter(raw, _period_arg())
    sexe = _parse_filter_arg("sexe")
    dept = _parse_filter_arg("dept")
    mal = _parse_filter_arg("maladie")
    trait = _parse_filter_arg("traitement")
    filtered = an.filter_dataframe(df, sexe, dept, mal, trait)
    opts = _filter_lists()
    chart_colors = ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#06B6D4"]
    ctx = {
        "kpis": an.dashboard_kpis(filtered),
        "metrics": an.summary_metrics(filtered),
        "admissions_week": an.admissions_by_weekday(filtered),
        "age_groups": an.age_groups_design(filtered),
        "cost_by_dept": an.cost_by_department(filtered),
        "recent": an.recent_patients_table(filtered, 5),
        "filters": opts,
        "selected_sexe": request.args.get("sexe") or "",
        "selected_dept": request.args.get("dept") or "",
        "selected_maladie": request.args.get("maladie") or "",
        "selected_traitement": request.args.get("traitement") or "",
        "selected_periode": _period_arg(),
        "active_filter_count": _active_filter_count(),
        "ai_paragraphs": an.dashboard_narrative(filtered),
        "alert_items": an.dashboard_alerts(filtered),
        "generated_at": datetime.now(),
        "total_patients": len(filtered),
        "n_depts": filtered["Departement"].nunique() if not filtered.empty else 0,
        "chart_colors": chart_colors,
        "hero_stats": _hero_stats(filtered),
    }
    return render_template("dashboard.html", **ctx)


@bp.route("/rapports")
def rapports():
    df = an.get_prepared_dataframe()
    filtered = an.filter_dataframe(df, None, None, None, None)
    return render_template(
        "rapports.html",
        hero_stats=_hero_stats(filtered),
        monthly_as=an.monthly_admissions_series(filtered),
        monthly_costs=an.monthly_costs_series(filtered),
        patho=an.top_pathologies(filtered),
        avg_stay=an.avg_stay_by_department(filtered),
        gender=an.gender_split(filtered),
        report_rows=an.report_summary_rows(filtered),
        cost_by_dept=an.cost_by_department(filtered),
        insight_act=an.insight_activite(filtered),
        insight_fin=an.insight_finances(filtered),
        insight_demo=an.insight_demographie(filtered),
        age_groups=an.age_groups_design(filtered),
        total_n=len(filtered),
        departments=sorted(df["Departement"].unique().tolist()),
        maladies=sorted(df["Maladie"].unique().tolist()),
        traitements=sorted(df["Traitement"].unique().tolist()),
        chart_colors=["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#06B6D4", "#10B981", "#8B5CF6"],
    )


@bp.route("/rapport/maquette")
def rapport_maquette():
    """Rapport analytique mise en page A4 (aperçu HTML + impression navigateur)."""
    raw = an.get_prepared_dataframe()
    df = an.apply_period_filter(raw, _period_arg())
    sexe = _parse_filter_arg("sexe")
    dept = _parse_filter_arg("dept")
    mal = _parse_filter_arg("maladie")
    trait = _parse_filter_arg("traitement")
    filtered = an.filter_dataframe(df, sexe, dept, mal, trait)

    sheets, extras = build_maquette_sheets(
        filtered,
        period_label=_period_label(),
        dept_label=_dept_maquette_label(),
    )
    chart_colors = ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#06B6D4", "#10B981", "#8B5CF6"]
    return render_template(
        "report_maquette.html",
        sheets=sheets,
        total_pages=len(sheets),
        generated_date=format_generated_date_long(),
        period_display=_period_label(),
        dept_display=_dept_maquette_label(),
        maquette_extras=extras,
        chart_colors=chart_colors,
    )


@bp.route("/export/maquette_a4.pdf")
def export_maquette_a4_pdf():
    """Génère le PDF maquette (Playwright), écrase static/exports/rapport_maquette.pdf, téléchargement."""
    project_root = Path(__file__).resolve().parent.parent
    out_path = project_root / "static" / "exports" / "rapport_maquette.pdf"
    target_url = _absolute_maquette_pdf_source_url()
    cmd = [
        sys.executable,
        "-m",
        "reporting.maquette_pdf_worker",
        target_url,
        str(out_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _log.exception("export_maquette_a4_pdf: timeout après 300s (url=%s)", target_url)
        return (
            "Délai dépassé lors de la génération du PDF. Réessayez ou vérifiez les logs serveur.",
            504,
            {"Content-Type": "text/plain; charset=utf-8"},
        )
    if result.returncode != 0:
        _log.error(
            "export_maquette_a4_pdf échec rc=%s stderr=%s stdout=%s url=%s",
            result.returncode,
            result.stderr,
            result.stdout,
            target_url,
        )
        raw = (result.stderr or result.stdout or "").strip()
        if "Playwright" in raw or "playwright" in raw.lower():
            detail = (
                "Playwright ou Chromium n’est pas disponible sur le serveur. "
                "Exécutez : pip install playwright && playwright install chromium"
            )
        elif raw and "Traceback" not in raw[:100]:
            detail = raw.split("\n")[0][:800]
        else:
            detail = "Échec de la génération du PDF (voir logs serveur)."
        return Response(detail, 503, {"Content-Type": "text/plain; charset=utf-8"})
    if not out_path.is_file():
        return (
            "Le fichier PDF n’a pas été créé.",
            500,
            {"Content-Type": "text/plain; charset=utf-8"},
        )
    return send_file(
        out_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="rapport_maquette.pdf",
        max_age=0,
        conditional=False,
    )


@bp.route("/export.csv")
def export_csv():
    raw = an.get_prepared_dataframe()
    df = an.apply_period_filter(raw, _period_arg())
    sexe = _parse_filter_arg("sexe")
    dept = _parse_filter_arg("dept")
    mal = _parse_filter_arg("maladie")
    trait = _parse_filter_arg("traitement")
    filtered = an.filter_dataframe(df, sexe, dept, mal, trait)
    buf = an.export_filtered_csv_bytes(filtered)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        buf,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=rapport_hospitalier_{ts}.csv",
            "Content-Length": str(len(buf)),
            "Cache-Control": "no-store",
        },
    )
