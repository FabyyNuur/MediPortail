"""Construction du contexte « rapport maquette » A4 (HTML / print / PDF Playwright)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import analytics as an

PATHO_FIRST_LIMIT = 8
PATHO_NEXT_LIMIT = 20
DEPT_CHUNK_LIMIT = 15


def _strip_html(s: str) -> str:
    if not s:
        return ""
    t = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", t).strip()


def build_maquette_sheets(
    filtered,
    *,
    period_label: str,
    dept_label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retourne (liste des feuilles pour le template, extras JSON pour Chart.js)."""
    patho_all = an.pathologies_consolidees(filtered)
    total_cases = sum(p["cases"] for p in patho_all)

    report_summary = an.report_summary_rows(filtered)
    monthly = an.monthly_admissions_series(filtered)
    avg_stay = an.avg_stay_by_department(filtered)
    cost_dep = an.cost_by_department(filtered)

    stay_labels = avg_stay["labels"]
    stay_vals = avg_stay["values"]
    cost_labels = cost_dep["labels"]
    cost_vals = cost_dep["values"]
    max_cost = max(cost_vals, default=0) or 0

    peak = an.peak_month_label(filtered)
    interpretation = (
        f"L'évolution de l'activité reflète les données agrégées du périmètre sélectionné. "
        f"Le mois le plus chargé est {peak}. Les flux mensuels permettent d'anticiper les tensions "
        f"capitaires et d'aligner les ressources sur les pics d'activité observés."
    )

    sheets: list[dict[str, Any]] = [{"kind": "cover"}]

    sheets.append(
        {
            "kind": "summary",
            "report_summary": report_summary,
            "interpretation": interpretation,
        }
    )

    patho_first = patho_all[:PATHO_FIRST_LIMIT]
    patho_remaining = patho_all[PATHO_FIRST_LIMIT:]
    remaining_chunks: list[list[dict[str, Any]]] = []
    for i in range(0, len(patho_remaining), PATHO_NEXT_LIMIT):
        remaining_chunks.append(patho_remaining[i : i + PATHO_NEXT_LIMIT])

    sheets.append(
        {
            "kind": "patho_first",
            "top5": patho_all[:5],
            "rows": patho_first,
            "show_total": len(patho_remaining) == 0,
            "total_cases": total_cases,
        }
    )
    for idx, chunk in enumerate(remaining_chunks):
        sheets.append(
            {
                "kind": "patho_continue",
                "rows": chunk,
                "show_total": idx == len(remaining_chunks) - 1,
                "total_cases": total_cases,
            }
        )

    max_dept_len = max(len(stay_labels), len(cost_labels))
    dept_chunks: list[dict[str, Any]] = []
    for i in range(0, max(max_dept_len, 1), DEPT_CHUNK_LIMIT):
        stay_slice = [
            {"dept": stay_labels[j], "duree": float(stay_vals[j])}
            for j in range(i, min(i + DEPT_CHUNK_LIMIT, len(stay_labels)))
        ]
        cost_slice = [
            {"name": cost_labels[j], "cout": float(cost_vals[j])}
            for j in range(i, min(i + DEPT_CHUNK_LIMIT, len(cost_labels)))
        ]
        dept_chunks.append({"stay": stay_slice, "cost": cost_slice})

    for idx, ch in enumerate(dept_chunks):
        sheets.append(
            {
                "kind": "dept",
                "suite": idx > 0,
                "stay": ch["stay"],
                "cost": ch["cost"],
                "max_cost": max_cost,
            }
        )

    bundle = an.decision_support_bundle(filtered)
    insights_html = bundle.get("insights_html") or []
    lead_parts = [
        _strip_html(x)
        for x in insights_html[:3]
        if _strip_html(x)
    ]
    lead = (
        " ".join(lead_parts)
        if lead_parts
        else an.insight_activite(filtered)
    )

    cards = [
        {
            "n": 1,
            "title": "Axe capacitaire",
            "body": an.insight_activite(filtered),
            "accent": "teal",
        },
        {
            "n": 2,
            "title": "Ressources & démographie",
            "body": an.insight_demographie(filtered),
            "accent": "indigo",
        },
        {
            "n": 3,
            "title": "Gestion financière",
            "body": an.insight_finances(filtered),
            "accent": "amber",
        },
    ]

    sheets.append(
        {
            "kind": "insights",
            "lead": lead,
            "cards": cards,
        }
    )

    extras = {
        "monthly_labels": monthly["labels"],
        "monthly_admissions": monthly["admissions"],
        "patho_top5": patho_all[:5],
        "period_label": period_label,
        "dept_label": dept_label,
    }

    return sheets, extras


_MONTHS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def format_generated_date_long() -> str:
    """Date lisible type « 18 avril 2026 à 14:30 »."""
    now = datetime.now()
    return (
        f"{now.day} {_MONTHS_FR[now.month - 1]} {now.year} "
        f"à {now.strftime('%H:%M')}"
    )
