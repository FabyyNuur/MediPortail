from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from flask import Blueprint, Response, render_template, request, send_file, url_for

import analytics as an
from reporting.maquette import build_maquette_sheets, format_generated_date_long

_log = logging.getLogger(__name__)

bp = Blueprint("main", __name__)

_CHART_COLORS_5 = ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#06B6D4"]
_CHART_COLORS_7 = _CHART_COLORS_5 + ["#10B981", "#8B5CF6"]


def _admissions_year_span_label(df) -> str:
    """Années min–max sur DateAdmission (libellé court KPI / intro maquette)."""
    if df.empty:
        return "—"
    da = df["DateAdmission"].dropna()
    if da.empty:
        return "—"
    y1, y2 = int(da.dt.year.min()), int(da.dt.year.max())
    return f"{y1}–{y2}" if y1 != y2 else str(y1)


def _hero_stats(filtered) -> list[dict]:
    if filtered.empty:
        return [
            {"label": "Patients suivis", "value": "0", "icon_key": "users"},
            {"label": "Départements", "value": "0 services", "icon_key": "building"},
            {"label": "Période couverte", "value": "—", "icon_key": "calendar"},
        ]
    period_str = _admissions_year_span_label(filtered)
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


_PERIOD_ALLOWED = frozenset({"all", "2425", "2024", "2025", "30", "90", "365"})


def _period_arg() -> str:
    v = (request.args.get("periode") or "all").strip()
    return v if v in _PERIOD_ALLOWED else "all"


def _maquette_cover_period_label(df) -> str:
    """Libellé période (couverture / en-tête) à partir des dates d’admission du fichier."""
    if df.empty or df["DateAdmission"].isna().all():
        return "Données sans plage datée exploitable"
    da = df["DateAdmission"].dropna()
    y1, y2 = int(da.dt.year.min()), int(da.dt.year.max())
    if y1 == y2:
        return f"Année {y1} (admissions datées)"
    return f"{y1} – {y2} (admissions datées)"


def _maquette_cover_dept_label(df) -> str:
    """Libellé services pour la couverture (données complètes du fichier)."""
    if df.empty:
        return "—"
    n = int(df["Departement"].nunique())
    return f"Tous les départements ({n} services)"


def _absolute_maquette_pdf_source_url() -> str:
    """URL joignable par Playwright : rapport maquette figé (sans paramètres de filtre)."""
    override = (os.environ.get("MAQUETTE_PDF_BASE_URL") or "").rstrip("/")
    base = override if override else request.url_root.rstrip("/")
    path = url_for("main.rapport_maquette", _external=False)
    return f"{base}{path}"


def _active_filter_count() -> int:
    n = sum(
        1
        for key in ("sexe", "dept", "maladie", "traitement")
        if (request.args.get(key) or "").strip()
    )
    if _period_arg() != "all":
        n += 1
    return n


def _rapports_active_filter_count() -> int:
    """Filtres page Rapports (période + département)."""
    n = 0
    if _period_arg() != "all":
        n += 1
    if (request.args.get("dept") or "").strip():
        n += 1
    return n


def _rapports_maquette_url() -> str:
    """URL du rapport maquette (vue consolidée, indépendante des filtres de la page Rapports)."""
    return url_for("main.rapport_maquette")


def _rapport_maquette_intro_context(df) -> dict:
    """Métadonnées d’introduction du rapport maquette (jeu complet du fichier CSV)."""
    from config import get_data_path

    data_file = Path(get_data_path()).name
    if df.empty:
        return {
            "data_file": data_file,
            "total_n": 0,
            "n_dept": 0,
            "n_mal": 0,
            "n_trait": 0,
            "period_str": "—",
        }
    period_str = _admissions_year_span_label(df)
    return {
        "data_file": data_file,
        "total_n": len(df),
        "n_dept": int(df["Departement"].nunique()),
        "n_mal": int(df["Maladie"].nunique()),
        "n_trait": int(df["Traitement"].nunique()),
        "period_str": period_str,
    }


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
        "chart_colors": _CHART_COLORS_5,
        "hero_stats": _hero_stats(filtered),
        "chart_captions": an.chart_captions_dashboard(filtered),
    }
    return render_template("dashboard.html", **ctx)


@bp.route("/rapports")
def rapports():
    raw = an.get_prepared_dataframe()
    df = an.apply_period_filter(raw, _period_arg())
    dept_arg = _parse_filter_arg("dept")
    filtered = an.filter_dataframe(df, None, dept_arg, None, None)
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
        departments=sorted(raw["Departement"].unique().tolist()),
        maladies=sorted(raw["Maladie"].unique().tolist()),
        traitements=sorted(raw["Traitement"].unique().tolist()),
        chart_colors=_CHART_COLORS_7,
        chart_captions=an.chart_captions_rapports(filtered),
        selected_periode=_period_arg(),
        selected_dept=(request.args.get("dept") or "").strip(),
        active_filter_count=_rapports_active_filter_count(),
        maquette_url=_rapports_maquette_url(),
    )


@bp.route("/rapport/maquette")
def rapport_maquette():
    """Rapport analytique A4 : toujours calculé sur l’ensemble du fichier (sans filtres d’URL)."""
    data = an.get_prepared_dataframe()
    period_cover = _maquette_cover_period_label(data)
    dept_cover = _maquette_cover_dept_label(data)

    sheets, extras = build_maquette_sheets(
        data,
        period_label=period_cover,
        dept_label=dept_cover,
    )
    return render_template(
        "report_maquette.html",
        sheets=sheets,
        total_pages=len(sheets),
        generated_date=format_generated_date_long(),
        period_display=period_cover,
        dept_display=dept_cover,
        maquette_extras=extras,
        chart_colors=_CHART_COLORS_7,
        rapport_intro=_rapport_maquette_intro_context(data),
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
