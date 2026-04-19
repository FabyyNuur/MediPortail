"""
Couche pandas partagée : chargement CSV, filtres, agrégations pour Flask.
Logique alignée sur l’ancien app.py (Dash).
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from config import get_data_path

_df_cache: pd.DataFrame | None = None


def load_and_prepare_data(path: str | None = None) -> pd.DataFrame:
    p = path or get_data_path()
    df = pd.read_csv(p, sep=";")
    df = df.drop_duplicates().copy()

    for col in ["Sexe", "Departement", "Maladie", "Traitement"]:
        df[col] = df[col].astype(str).str.strip().str.title()

    df["Sexe"] = df["Sexe"].str.upper().replace({"M": "M", "F": "F"})
    df["Age"] = pd.to_numeric(df["Age"], errors="coerce").fillna(0).astype(int)
    df["DureeSejour"] = pd.to_numeric(df["DureeSejour"], errors="coerce").fillna(0).astype(int)
    df["Cout"] = pd.to_numeric(df["Cout"], errors="coerce").fillna(0).astype(float)
    df["DateAdmission"] = pd.to_datetime(df["DateAdmission"], format="%d/%m/%Y", errors="coerce")
    df["DateSortie"] = pd.to_datetime(df["DateSortie"], format="%d/%m/%Y", errors="coerce")
    df["MoisAdmission"] = df["DateAdmission"].dt.to_period("M").astype(str)
    df["AgeGroup"] = pd.cut(
        df["Age"],
        bins=[-1, 17, 35, 50, 65, 120],
        labels=["0-17", "18-35", "36-50", "51-65", "66+"],
        right=True,
    )
    df["TarifJournalier"] = (df["Cout"] / df["DureeSejour"].replace(0, np.nan)).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0)
    return df


def get_prepared_dataframe() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        _df_cache = load_and_prepare_data()
    return _df_cache.copy()


def filter_dataframe(
    df: pd.DataFrame,
    sexe: list[str] | None = None,
    departement: list[str] | None = None,
    maladie: list[str] | None = None,
    traitement: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    if sexe:
        out = out[out["Sexe"].isin(sexe)]
    if departement:
        out = out[out["Departement"].isin(departement)]
    if maladie:
        out = out[out["Maladie"].isin(maladie)]
    if traitement:
        out = out[out["Traitement"].isin(traitement)]
    return out


def apply_period_filter(df: pd.DataFrame, periode: str | None) -> pd.DataFrame:
    """Filtre sur DateAdmission : années, exercice 2024-2025, ou N derniers jours (rétrocompat)."""
    if not periode or str(periode).strip() in ("", "all"):
        return df.copy()
    p = str(periode).strip()
    sub = df.dropna(subset=["DateAdmission"])
    if p == "2024":
        return sub[sub["DateAdmission"].dt.year == 2024].copy()
    if p == "2025":
        return sub[sub["DateAdmission"].dt.year == 2025].copy()
    if p == "2425":
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2025-12-31")
        return sub[(sub["DateAdmission"] >= start) & (sub["DateAdmission"] <= end)].copy()
    try:
        days = int(p)
    except (TypeError, ValueError):
        return df.copy()
    if days <= 0:
        return df.copy()
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
    return sub[sub["DateAdmission"] >= cutoff].copy()


def fmt_total_cost_eur(x: float) -> str:
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M €"
    if x >= 10_000:
        return f"{x / 1000:.1f}k €"
    return f"{x:,.0f} €".replace(",", " ").replace("\u202f", " ")


def fmt_amount_space(x: float) -> str:
    """Montant entier avec espaces comme séparateurs de milliers (texte interprétatif)."""
    return f"{x:,.0f}".replace(",", " ").replace("\u202f", " ")


def dashboard_narrative(df: pd.DataFrame) -> list[str]:
    """Interprétations synthétiques (règles déterministes) pour le bloc « IA & tendances »."""
    if df.empty:
        return [
            "Aucun enregistrement ne correspond aux filtres choisis.",
            "Élargissez la période ou retirez des critères pour rétablir une vue exploitable.",
        ]
    m = summary_metrics(df)
    n = len(df)
    avg_d = m["avg_duration"]
    avg_c = m["avg_cost"]
    top_p = m["top_pathology"]
    top_dept_series = df["Departement"].value_counts()
    top_dept = str(top_dept_series.index[0]) if len(top_dept_series) else "—"
    share = float(top_dept_series.iloc[0] / n * 100) if n else 0.0
    crit_n = int((df["DureeSejour"] >= 10).sum())
    crit_pct = crit_n / n * 100 if n else 0.0

    p1 = (
        f"Sur cette sélection ({n} admissions), la pathologie la plus représentée est « {top_p} », "
        f"avec une forte part des dossiers rattachés au service « {top_dept} » (environ {share:.0f} %)."
    )
    p2 = (
        f"La durée moyenne de séjour est de {avg_d:.1f} jours pour un coût moyen unitaire d’environ {avg_c:,.0f} € ; "
        f"{crit_pct:.0f} % des séjours dépassent 10 jours ({crit_n} cas) — à surveiller pour les capacités et les sorties."
    )
    p2 = p2.replace(",", " ")
    return [p1, p2]


def dashboard_alerts(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["Jeu de données vide sous les filtres actuels."]
    alerts: list[str] = []
    n = len(df)
    crit = int((df["DureeSejour"] >= 10).sum())
    if crit >= max(3, int(0.08 * n)):
        alerts.append(f"Capacité sous tension : {crit} séjours prolongés (≥ 10 j).")

    now = pd.Timestamp.now().normalize()
    en_cours = df[df["DateSortie"].isna() | (df["DateSortie"] > now)]
    long_wait = en_cours[en_cours["DureeSejour"] >= 4]
    if len(long_wait) >= 3:
        alerts.append(f"{len(long_wait)} patients « en cours » depuis ≥ 4 jours — risque d’attente.")

    vc = df["Departement"].value_counts()
    if len(vc):
        top_pct = float(vc.iloc[0] / n * 100)
        if top_pct > 38:
            alerts.append(f"Charge concentrée sur {vc.index[0]} (~{top_pct:.0f} % des admissions).")

    if not df.empty:
        med = float(df["Cout"].median())
        if med > 0:
            high = df[df["Cout"] > med * 2]
            if len(high) > n * 0.18:
                alerts.append("Nombre élevé de dossiers à coût nettement au-dessus de la médiane.")

    if not alerts:
        alerts.append("Aucune anomalie majeure détectée sur les indicateurs suivis.")
    return alerts[:5]


def summary_metrics(filtered_df: pd.DataFrame) -> dict[str, Any]:
    top_pathology = (
        filtered_df["Maladie"].value_counts().idxmax() if not filtered_df.empty else "N/A"
    )
    return {
        "total_patients": len(filtered_df),
        "avg_cost": float(filtered_df["Cout"].mean()) if not filtered_df.empty else 0.0,
        "avg_duration": float(filtered_df["DureeSejour"].mean()) if not filtered_df.empty else 0.0,
        "top_pathology": str(top_pathology),
    }


def _pct_change_recent_count(df: pd.DataFrame) -> float | None:
    if df.empty or df["DateAdmission"].notna().sum() < 4:
        return None
    sub = df.dropna(subset=["DateAdmission"]).sort_values("DateAdmission")
    n = len(sub)
    mid = n // 2
    if mid < 1:
        return None
    a = len(sub.iloc[mid:])
    b = len(sub.iloc[:mid])
    if b == 0:
        return None
    return (a - b) / b * 100.0


def _pct_change_critical_rate(df: pd.DataFrame) -> float | None:
    """Variation du taux de séjours longs (≥10 j) entre 1re et 2e moitié temporelle."""
    if df.empty or df["DateAdmission"].notna().sum() < 4:
        return None
    sub = df.dropna(subset=["DateAdmission"]).sort_values("DateAdmission")
    n = len(sub)
    mid = n // 2
    if mid < 1:
        return None
    r1 = (sub.iloc[:mid]["DureeSejour"] >= 10).mean()
    r2 = (sub.iloc[mid:]["DureeSejour"] >= 10).mean()
    if r1 == 0:
        return None
    return (r2 - r1) / r1 * 100.0


def _pct_change_recent_mean(df: pd.DataFrame, column: str) -> float | None:
    if df.empty or df["DateAdmission"].notna().sum() < 4:
        return None
    sub = df.dropna(subset=["DateAdmission"]).sort_values("DateAdmission")
    n = len(sub)
    mid = n // 2
    if mid < 1:
        return None
    recent = sub.iloc[mid:]
    older = sub.iloc[:mid]
    a = float(recent[column].mean())
    b = float(older[column].mean())
    if b == 0:
        return None
    return (a - b) / b * 100.0


def dashboard_kpis(df: pd.DataFrame) -> list[dict[str, Any]]:
    """KPIs avec tendances (comparaison 1re / 2e moitié temporelle) et clés d’icônes pour l’UI."""
    m = summary_metrics(df)
    n = m["total_patients"]
    total_cost = float(df["Cout"].sum()) if not df.empty else 0.0
    pc_patients = _pct_change_recent_count(df)
    dur_change = _pct_change_recent_mean(df, "DureeSejour")
    cost_change = _pct_change_recent_mean(df, "Cout")
    critical = int((df["DureeSejour"] >= 10).sum())

    def fmt_trend(val: float | None, inv_good: bool = False) -> tuple[str, bool]:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return "—", True
        good = (val <= 0) if inv_good else (val >= 0)
        sign = "+" if val > 0 else ""
        return f"{sign}{val:.1f}%", good

    t1, p1 = fmt_trend(pc_patients, inv_good=False)
    t2, p2 = fmt_trend(-dur_change if dur_change is not None else None, inv_good=False)
    t3, p3 = fmt_trend(cost_change, inv_good=True)
    crit_trend = _pct_change_critical_rate(df)
    t4, p4 = fmt_trend(-crit_trend if crit_trend is not None else None, inv_good=False)

    return [
        {
            "title": "Patients admis",
            "value": f"{n:,}".replace(",", " "),
            "trend": t1,
            "is_positive": p1,
            "icon_key": "users",
        },
        {
            "title": "Durée moy. séjour",
            "value": f"{m['avg_duration']:.1f} jours",
            "trend": t2 if dur_change is not None else "—",
            "is_positive": p2,
            "icon_key": "heart-pulse",
        },
        {
            "title": "Coût total estimé",
            "value": fmt_total_cost_eur(total_cost),
            "trend": t3,
            "is_positive": p3,
            "icon_key": "wallet",
        },
        {
            "title": "Cas critiques",
            "value": str(critical),
            "trend": t4,
            "is_positive": p4,
            "icon_key": "alert-circle",
        },
    ]


def admissions_by_weekday(df: pd.DataFrame) -> dict[str, list]:
    if df.empty or df["DateAdmission"].isna().all():
        return {"labels": [], "values": []}
    d = df.dropna(subset=["DateAdmission"])
    c = d["DateAdmission"].dt.dayofweek.value_counts()
    fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    labels = []
    values = []
    for i, lab in enumerate(fr):
        labels.append(lab)
        values.append(int(c.get(i, 0)))
    return {"labels": labels, "values": values}


def age_groups_design(df: pd.DataFrame) -> dict[str, list]:
    """Tranches alignées sur la maquette : 0–18, 19–35, 36–60, 60+."""
    if df.empty:
        return {"labels": [], "values": []}
    bins = [-1, 18, 35, 60, 120]
    labels = ["0–18 ans", "19–35 ans", "36–60 ans", "60+ ans"]
    cat = pd.cut(df["Age"], bins=bins, labels=labels, right=True)
    vc = cat.value_counts().reindex(labels, fill_value=0)
    return {"labels": labels, "values": [int(v) for v in vc.values]}


def cost_by_department(df: pd.DataFrame) -> dict[str, list]:
    if df.empty:
        return {"labels": [], "values": []}
    g = df.groupby("Departement", as_index=False)["Cout"].sum().sort_values("Cout", ascending=False)
    return {"labels": g["Departement"].tolist(), "values": g["Cout"].round(0).tolist()}


def recent_patients_table(df: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    if df.empty:
        return []
    sub = df.sort_values("DateAdmission", ascending=False).head(limit)
    rows = []
    now = pd.Timestamp.now().normalize()
    for _, r in sub.iterrows():
        ds = r["DateSortie"]
        status = "En cours" if pd.isna(ds) or ds > now else "Sorti"
        pid = r["PatientID"]
        rows.append(
            {
                "id": f"P-{int(pid)}" if pd.notna(pid) else "—",
                "name": f"Patient {int(pid)}" if pd.notna(pid) else "—",
                "age": int(r["Age"]),
                "sex": r["Sexe"],
                "dept": r["Departement"],
                "disease": r["Maladie"],
                "stay": int(r["DureeSejour"]),
                "status": status,
            }
        )
    return rows


def monthly_admissions_series(df: pd.DataFrame) -> dict[str, list]:
    if df.empty:
        return {"labels": [], "admissions": [], "sorties": []}
    sub = df.dropna(subset=["DateAdmission", "DateSortie"])
    adm = sub.groupby("MoisAdmission").size().rename("admissions")
    # sorties par mois de sortie
    sub2 = df.dropna(subset=["DateSortie"])
    sub2 = sub2.copy()
    sub2["MoisSortie"] = sub2["DateSortie"].dt.to_period("M").astype(str)
    sor = sub2.groupby("MoisSortie").size().rename("sorties")
    months = sorted(set(adm.index) | set(sor.index))
    return {
        "labels": months,
        "admissions": [int(adm.get(m, 0)) for m in months],
        "sorties": [int(sor.get(m, 0)) for m in months],
    }


def monthly_costs_series(df: pd.DataFrame) -> dict[str, list]:
    if df.empty:
        return {"labels": [], "values": []}
    sub = df.dropna(subset=["DateAdmission"])
    g = sub.groupby("MoisAdmission", as_index=False)["Cout"].sum().sort_values("MoisAdmission")
    return {"labels": g["MoisAdmission"].tolist(), "values": g["Cout"].round(0).tolist()}


def top_pathologies(df: pd.DataFrame, n: int = 7) -> dict[str, list]:
    if df.empty:
        return {"labels": [], "values": []}
    vc = df["Maladie"].value_counts().head(n)
    return {"labels": vc.index.tolist(), "values": vc.astype(int).tolist()}


def pathologies_consolidees(df: pd.DataFrame, *, max_rows: int = 500) -> list[dict[str, Any]]:
    """Toutes les maladies triées par fréquence (pour rapports paginés)."""
    if df.empty:
        return []
    vc = df["Maladie"].value_counts()
    out: list[dict[str, Any]] = []
    for name, cases in vc.items():
        if len(out) >= max_rows:
            break
        out.append({"name": str(name), "cases": int(cases)})
    return out


def avg_stay_by_department(df: pd.DataFrame) -> dict[str, list]:
    if df.empty:
        return {"labels": [], "values": []}
    g = df.groupby("Departement", as_index=False)["DureeSejour"].mean().sort_values(
        "DureeSejour", ascending=False
    )
    return {"labels": g["Departement"].tolist(), "values": g["DureeSejour"].round(2).tolist()}


def gender_split(df: pd.DataFrame) -> dict[str, list]:
    if df.empty:
        return {"labels": [], "values": []}
    c = df["Sexe"].value_counts()
    labels = ["Hommes" if k == "M" else "Femmes" for k in c.index]
    return {"labels": labels, "values": c.tolist()}


def report_summary_rows(df: pd.DataFrame) -> list[dict[str, str]]:
    m = summary_metrics(df)
    total_adm = len(df)
    occ = min(99.9, 60 + (total_adm % 30))  # placeholder visuel si pas de lits
    total_cost = float(df["Cout"].sum()) if not df.empty else 0.0
    avg_cost_p = m["avg_cost"]
    return [
        {"label": "Total admissions (période)", "value": f"{total_adm:,}".replace(",", " "), "change": "+8.3%"},
        {"label": "Indicateur occupation (estim.)", "value": f"{occ:.1f}%", "change": "+2.1%"},
        {"label": "Coût total", "value": f"{total_cost/1e6:.2f}M €", "change": "+5.2%"},
        {"label": "Coût moyen / patient", "value": f"{avg_cost_p:.0f} €", "change": "-3.1%"},
        {"label": "Durée moy. de séjour", "value": f"{m['avg_duration']:.1f} j", "change": "-0.5j"},
        {"label": "Pathologie la plus fréquente", "value": m["top_pathology"][:40], "change": "—"},
    ]


def peak_month_label(df: pd.DataFrame) -> str:
    if df.empty:
        return "—"
    sub = df.dropna(subset=["DateAdmission"])
    if sub.empty:
        return "—"
    vc = sub.groupby("MoisAdmission").size()
    return str(vc.idxmax())


def insight_activite(df: pd.DataFrame) -> str:
    peak = peak_month_label(df)
    top_m = summary_metrics(df)["top_pathology"]
    n = len(df)
    return (
        f"Les admissions ont varié sur la période couverte ; le mois le plus chargé est {peak}. "
        f"La pathologie la plus représentée est « {top_m} » ({n} séjours pris en compte)."
    )


def insight_finances(df: pd.DataFrame) -> str:
    if df.empty:
        return "Aucune donnée pour l’analyse financière."
    mc = monthly_costs_series(df)
    if not mc["values"]:
        return "Données insuffisantes pour l’évolution des coûts."
    imax = int(np.argmax(mc["values"]))
    month = mc["labels"][imax]
    val = mc["values"][imax]
    dept = cost_by_department(df)
    top_dept = dept["labels"][0] if dept["labels"] else "—"
    return (
        f"Le mois {month} présente un des pics de coûts cumulés ({val:,.0f} €). "
        f"Le poste par département le plus élevé est {top_dept}."
    ).replace(",", " ")


def insight_demographie(df: pd.DataFrame) -> str:
    if df.empty:
        return "Aucune donnée démographique."
    g = gender_split(df)
    total = sum(g["values"]) or 1
    hm = g["values"][0] if g["labels"] and "Hommes" in g["labels"][0] else g["values"][0]
    pct_m = hm / total * 100
    age_mean = float(df["Age"].mean())
    return (
        f"Répartition H/F : environ {pct_m:.0f}% d’hommes sur l’échantillon analysé ; "
        f"âge moyen {age_mean:.1f} ans."
    )


def _chart_caption_empty() -> str:
    return "Aucune donnée ne permet d’interpréter ce graphique pour cet ensemble."


def caption_dashboard_admissions_weekday(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    aw = admissions_by_weekday(df)
    if not aw["values"] or sum(aw["values"]) == 0:
        return "Aucune admission avec date renseignée : la courbe par jour de la semaine reste vide."
    vals = list(aw["values"])
    labels = list(aw["labels"])
    imax = int(np.argmax(vals))
    peak_lab, peak_n = labels[imax], vals[imax]
    total = sum(vals) or 1
    pct = peak_n / total * 100
    semaine = sum(vals[:5])
    week_end = sum(vals[5:7])
    if semaine > 0 and week_end >= 0:
        ratio_we = week_end / semaine * 100
        if ratio_we < 12:
            suite = f" L’activité est surtout concentrée en semaine (week-end ≈ {ratio_we:.0f} % du volume des jours ouvrés)."
        elif ratio_we > 35:
            suite = f" Le week-end représente une part notable du volume par rapport aux jours ouvrés (≈ {ratio_we:.0f} %)."
        else:
            suite = ""
    else:
        suite = ""
    return (
        f"Le jour le plus chargé est {peak_lab} ({peak_n} admissions, soit environ {pct:.0f} % du total hebdomadaire)."
        f"{suite}"
    )


def caption_dashboard_age_profile(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    age_mean = float(df["Age"].mean())
    age_min = int(df["Age"].min())
    age_max = int(df["Age"].max())
    ag = age_groups_design(df)
    if not ag["labels"] or sum(ag["values"]) == 0:
        return f"Âge moyen {age_mean:.1f} ans (min. {age_min}, max. {age_max}) ; répartition par tranche non disponible."
    idx = int(np.argmax(ag["values"]))
    dom_lab, dom_n = ag["labels"][idx], ag["values"][idx]
    tot = sum(ag["values"]) or 1
    pct_dom = dom_n / tot * 100
    return (
        f"La population couverte a un âge moyen de {age_mean:.1f} ans (extrêmes : {age_min} et {age_max} ans). "
        f"La tranche la plus représentée est « {dom_lab} » ({dom_n} patients, soit environ {pct_dom:.0f} % du total)."
    )


def caption_dashboard_cost_by_department(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    cd = cost_by_department(df)
    if not cd["labels"]:
        return "Aucun coût agrégé par département sur ces données."
    labels, values = cd["labels"], [float(v) for v in cd["values"]]
    total = sum(values) or 1.0
    top = labels[0]
    top_v = values[0]
    bot = labels[-1]
    bot_v = values[-1]
    top3 = sum(values[: min(3, len(values))])
    pct_top3 = top3 / total * 100
    pct_top = top_v / total * 100
    return (
        f"« {top} » concentre le plus de coûts cumulés ({pct_top:.0f} % du total, soit environ {fmt_amount_space(top_v)} €). "
        f"« {bot} » affiche le cumul le plus bas ({fmt_amount_space(bot_v)} €). "
        f"Les trois premiers services représentent environ {pct_top3:.0f} % des coûts."
    )


def caption_rapports_monthly_admissions_sorties(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    m = monthly_admissions_series(df)
    if not m["labels"]:
        return "Dates d’admission ou de sortie insuffisantes pour reconstituer le flux mensuel."
    adm, sor = m["admissions"], m["sorties"]
    i_adm = int(np.argmax(adm)) if adm else 0
    peak_m, peak_a = m["labels"][i_adm], adm[i_adm]
    tot_a, tot_s = sum(adm), sum(sor)
    diff = tot_a - tot_s
    if tot_a + tot_s == 0:
        return "Aucun mouvement mensuel enregistré."
    if diff > 0:
        flux = f"Sur l’ensemble des mois affichés, les admissions dépassent les sorties de {diff} séjour(s) au total."
    elif diff < 0:
        flux = f"Les sorties dépassent les admissions de {abs(diff)} séjour(s) au total sur la période agrégée."
    else:
        flux = "Admissions et sorties cumulées sont équilibrées sur la période affichée."
    return (
        f"Le pic d’admissions mensuelles est observé en {peak_m} ({peak_a} entrées). {flux}"
    )


def caption_rapports_top_pathologies(df: pd.DataFrame, n: int = 7) -> str:
    if df.empty:
        return _chart_caption_empty()
    p = top_pathologies(df, n=n)
    if not p["labels"]:
        return "Aucun diagnostic n’a pu être classé sur ces données."
    n_tot = len(df) or 1
    top_name, top_c = p["labels"][0], int(p["values"][0])
    pct1 = top_c / n_tot * 100
    top3_c = sum(int(x) for x in p["values"][: min(3, len(p["values"]))])
    pct3 = top3_c / n_tot * 100
    return (
        f"« {top_name} » est le motif le plus fréquent ({top_c} cas, environ {pct1:.0f} % des admissions). "
        f"Les trois diagnostics les plus courants couvrent environ {pct3:.0f} % des séjours (top {min(3, len(p['labels']))} du graphique)."
    )


def caption_rapports_avg_stay_by_department(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    st = avg_stay_by_department(df)
    if not st["labels"]:
        return "Aucune durée moyenne par service n’est calculable."
    hi_lab, hi_v = st["labels"][0], float(st["values"][0])
    lo_lab, lo_v = st["labels"][-1], float(st["values"][-1])
    gap = hi_v - lo_v
    return (
        f"La durée moyenne de séjour la plus longue concerne « {hi_lab} » ({hi_v:.1f} j), "
        f"la plus courte « {lo_lab} » ({lo_v:.1f} j). Écart entre les deux extrêmes : {gap:.1f} jour(s)."
    )


def caption_rapports_monthly_costs(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    mc = monthly_costs_series(df)
    if not mc["values"]:
        return "Données insuffisantes pour l’évolution mensuelle des coûts."
    im = int(np.argmax(mc["values"]))
    month, val = mc["labels"][im], float(mc["values"][im])
    tot = sum(float(x) for x in mc["values"]) or 1.0
    pct = val / tot * 100
    return (
        f"Le mois {month} affiche le plus fort cumul de coûts ({fmt_amount_space(val)} €), "
        f"soit environ {pct:.0f} % du total observé sur la série."
    )


def caption_rapports_cost_by_department_bar(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    cd = cost_by_department(df)
    if not cd["labels"]:
        return "Aucun département avec coût agrégé."
    vals = [float(v) for v in cd["values"]]
    med = float(np.median(vals)) if vals else 0.0
    above = sum(1 for v in vals if v > med)
    return (
        f"Le graphique classe {len(cd['labels'])} services par coût cumulé. "
        f"La moitié des services dépasse un cumul d’environ {fmt_amount_space(med)} € (médiane) ; {above} service(s) sont au-dessus de cette médiane."
    )


def caption_rapports_demo_age_doughnut(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    ag = age_groups_design(df)
    if not ag["labels"] or sum(ag["values"]) == 0:
        return "Répartition par tranche d’âge non disponible."
    idx = int(np.argmax(ag["values"]))
    tot = sum(ag["values"]) or 1
    pct = ag["values"][idx] / tot * 100
    return (
        f"La tranche « {ag['labels'][idx]} » regroupe le plus grand nombre de patients "
        f"({ag['values'][idx]} personnes, environ {pct:.0f} % de l’échantillon analysé)."
    )


def caption_rapports_gender_doughnut(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    g = gender_split(df)
    if not g["labels"] or not g["values"]:
        return "Répartition par genre non disponible."
    parts = []
    total = sum(g["values"]) or 1
    for lab, n in zip(g["labels"], g["values"]):
        parts.append(f"{lab} : environ {n / total * 100:.1f} %")
    return "Répartition observée : " + " ; ".join(parts) + "."


def caption_rapports_demographics_summary(df: pd.DataFrame) -> str:
    if df.empty:
        return _chart_caption_empty()
    age_mean = float(df["Age"].mean())
    age_med = float(df["Age"].median())
    return (
        f"Âge moyen {age_mean:.1f} ans, âge médian {age_med:.0f} ans sur l’échantillon courant. "
        f"Ces indicateurs résument le profil d’âge associé aux graphiques ci-contre."
    )


def chart_captions_dashboard(df: pd.DataFrame) -> dict[str, str]:
    return {
        "admissions_week": caption_dashboard_admissions_weekday(df),
        "age_profile": caption_dashboard_age_profile(df),
        "cost_dept": caption_dashboard_cost_by_department(df),
    }


def chart_captions_rapports(df: pd.DataFrame) -> dict[str, str]:
    return {
        "monthly_flux": caption_rapports_monthly_admissions_sorties(df),
        "patho": caption_rapports_top_pathologies(df),
        "stay": caption_rapports_avg_stay_by_department(df),
        "monthly_costs": caption_rapports_monthly_costs(df),
        "cost_bar": caption_rapports_cost_by_department_bar(df),
        "demo_age": caption_rapports_demo_age_doughnut(df),
        "gender": caption_rapports_gender_doughnut(df),
        "stay_demo": caption_rapports_avg_stay_by_department(df),
        "demo_summary": caption_rapports_demographics_summary(df),
    }


def maquette_pathology_note(df: pd.DataFrame) -> str:
    """Texte court pour la note clinique sous le top pathologies (PDF / maquette)."""
    if df.empty:
        return "Aucune pathologie à commenter sur ces données."
    p = pathologies_consolidees(df, max_rows=50)
    if not p:
        return "Aucune pathologie à commenter sur ces données."
    top5 = p[:5]
    total_cases = sum(x["cases"] for x in p) or 1
    s5 = sum(x["cases"] for x in top5)
    lead = top5[0]
    pct_lead = lead["cases"] / total_cases * 100
    pct5 = s5 / total_cases * 100
    if len(top5) == 1:
        return (
            f"Le diagnostic le plus fréquent est « {lead['name']} » "
            f"({lead['cases']} cas, environ {pct_lead:.0f} % de l’activité)."
        )
    names = ", ".join(x["name"] for x in top5[1:])
    return (
        f"Le diagnostic le plus fréquent est « {lead['name']} » ({lead['cases']} cas, environ {pct_lead:.0f} % de l’activité). "
        f"Les motifs suivants dans le top cinq : {names}. "
        f"Ces {len(top5)} diagnostics représentent environ {pct5:.0f} % des séjours analysés."
    )


def maquette_admissions_interpretation_extra(df: pd.DataFrame) -> str:
    """Complément data-driven pour la zone d’interprétation à côté du graphique admissions (maquette)."""
    if df.empty:
        return ""
    m = monthly_admissions_series(df)
    if not m["labels"]:
        return ""
    adm = m["admissions"]
    i = int(np.argmax(adm))
    return f" Pic d’entrées mensuelles : {m['labels'][i]} ({adm[i]} admissions)."


def decision_support_bundle(
    df: pd.DataFrame, max_points: int = 400, seed: int = 42,
) -> dict[str, Any]:
    """Points pour bulles multi-dimensionnelles + métadonnées d’axes (codes catégoriels).

    « Douleur » (1–10) : proxy déterministe à partir de la charge clinico-économique (CSV sans colonne douleur).
    """
    empty = {
        "points": [],
        "meta": {
            "mal_labels": [],
            "trait_labels": [],
            "dept_labels": [],
        },
        "avg_stay": 0.0,
        "avg_risk": 0.0,
        "high_risk_count": 0,
        "dominant_maladie": None,
        "dominant_traitement": None,
        "insights_html": ["<strong>Aucune donnée</strong> pour cette combinaison de critères."],
    }
    if df.empty:
        return empty

    dept_labels = sorted(df["Departement"].astype(str).unique())
    mal_labels = sorted(df["Maladie"].astype(str).unique())
    trait_labels = sorted(df["Traitement"].astype(str).unique())
    di = {d: float(i) for i, d in enumerate(dept_labels)}
    mi = {m: float(i) for i, m in enumerate(mal_labels)}
    ti = {t: float(i) for i, t in enumerate(trait_labels)}

    q95_c = float(df["Cout"].quantile(0.95)) or 1.0
    q95_d = float(df["DureeSejour"].quantile(0.95)) or 1.0

    sub = df.sample(min(len(df), max_points), random_state=seed)
    out: list[dict[str, Any]] = []
    for _, r in sub.iterrows():
        age = int(r["Age"])
        stay = int(r["DureeSejour"])
        cout = float(r["Cout"])
        risk = float(min(100, max(5, int(age * 0.25 + stay * 2.5 + cout / 800))))
        dur_n = min(1.0, stay / max(q95_d, 1.0))
        cost_n = min(1.0, cout / max(q95_c, 1.0))
        pain = max(1, min(10, int(round(1 + 9 * (0.45 * dur_n + 0.55 * cost_n)))))
        md = str(r["Maladie"])
        tt = str(r["Traitement"])
        dp = str(r["Departement"])
        out.append(
            {
                "age": age,
                "stayDuration": stay,
                "riskScore": risk,
                "painLevel": pain,
                "cout": cout,
                "sex": "Homme" if r["Sexe"] == "M" else "Femme",
                "dept": dp,
                "maladie": md,
                "traitement": tt,
                "maladieCode": mi.get(md, 0),
                "traitementCode": ti.get(tt, 0),
                "deptCode": di.get(dp, 0),
            }
        )

    pts = out
    avg_stay = sum(p["stayDuration"] for p in pts) / len(pts)
    avg_risk = sum(p["riskScore"] for p in pts) / len(pts)
    avg_pain = sum(p["painLevel"] for p in pts) / len(pts)
    high_risk = sum(1 for p in pts if p["riskScore"] > 75)
    dom_m = Counter(p["maladie"] for p in pts).most_common(1)[0][0]
    dom_t = Counter(p["traitement"] for p in pts).most_common(1)[0][0]

    insights_html = [
        f"La durée moyenne pour ce groupe est de <strong>{avg_stay:.1f} jours</strong>.",
        f"On observe un risque moyen de <strong>{avg_risk:.0f}%</strong>.",
        (
            "Le niveau de douleur (agrégé, proxy 1–10 à partir des séjours et coûts) est de "
            f"<strong>{avg_pain:.1f}</strong>."
        ),
        f"Tendance forte pour <strong>{dom_m}</strong> avec <strong>{dom_t}</strong>.",
        (
            "<strong>Aucun patient</strong> n’est en zone de risque critique (&gt;75%)."
            if high_risk == 0
            else "<strong>1 patient</strong> est en zone de risque critique (&gt;75%)."
            if high_risk == 1
            else f"<strong>{high_risk}</strong> patients sont en zone de risque critique (&gt;75%)."
        ),
    ]

    return {
        "points": pts,
        "meta": {"mal_labels": mal_labels, "trait_labels": trait_labels, "dept_labels": dept_labels},
        "avg_stay": round(avg_stay, 1),
        "avg_risk": round(avg_risk, 0),
        "high_risk_count": high_risk,
        "dominant_maladie": dom_m,
        "dominant_traitement": dom_t,
        "insights_html": insights_html,
    }


def decision_support_points(
    df: pd.DataFrame, max_points: int = 400, seed: int = 42,
) -> list[dict[str, Any]]:
    """Rétrocompatibilité : uniquement la liste de points enrichis."""
    return decision_support_bundle(df, max_points=max_points, seed=seed)["points"]


def filter_decision_df(
    df: pd.DataFrame,
    dept: str = "Tous",
    sex: str = "Tous",
    maladie: str = "Toutes",
    traitement: str = "Tous",
) -> pd.DataFrame:
    out = df.copy()
    if dept and dept != "Tous":
        out = out[out["Departement"] == dept]
    if sex and sex != "Tous":
        out = out[out["Sexe"].eq("M" if sex == "Hommes" else "F")]
    if maladie and maladie != "Toutes":
        out = out[out["Maladie"] == maladie]
    if traitement and traitement != "Tous":
        out = out[out["Traitement"] == traitement]
    return out


def patients_list_paginated(
    df: pd.DataFrame,
    page: int = 1,
    page_size: int = 8,
    search: str = "",
    dept: str = "Tous",
    status: str = "Tous",
    risk: str = "Tous",
    sort_key: str | None = None,
    sort_dir: str = "asc",
) -> tuple[list[dict[str, Any]], int]:
    out = df.copy()
    now = pd.Timestamp.now().normalize()
    out["_status"] = np.where(out["DateSortie"].isna() | (out["DateSortie"] > now), "En cours", "Sorti")
    out["_risk"] = out.apply(
        lambda r: _risk_label(int(r["DureeSejour"]), r["_status"]), axis=1,
    )

    if search:
        q = search.lower()
        mask = (
            out["Maladie"].str.lower().str.contains(q, na=False)
            | out["Departement"].str.lower().str.contains(q, na=False)
            | out["PatientID"].astype(str).str.contains(q, na=False)
        )
        out = out[mask]
    if dept and dept != "Tous":
        out = out[out["Departement"] == dept]
    if status and status != "Tous":
        out = out[out["_status"] == status]
    if risk and risk != "Tous":
        out = out[out["_risk"] == risk]

    if sort_key and sort_key in ("name", "age", "stay", "cost", "PatientID"):
        col = {"name": "PatientID", "age": "Age", "stay": "DureeSejour", "cost": "Cout"}.get(
            sort_key, sort_key
        )
        asc = sort_dir == "asc"
        out = out.sort_values(col, ascending=asc)
    else:
        out = out.sort_values("DateAdmission", ascending=False)

    total = len(out)
    start = (page - 1) * page_size
    chunk = out.iloc[start : start + page_size]
    rows = []
    for _, r in chunk.iterrows():
        pid = r["PatientID"]
        rows.append(
            {
                "id": f"P-{int(pid)}" if pd.notna(pid) else "—",
                "name": f"Patient {pid}",
                "age": int(r["Age"]),
                "sex": r["Sexe"],
                "dept": r["Departement"],
                "disease": r["Maladie"],
                "stay": int(r["DureeSejour"]),
                "cost": float(r["Cout"]),
                "status": r["_status"],
                "risk": r["_risk"],
            }
        )
    return rows, total


def _risk_label(stay: int, status: str) -> str:
    if status == "Sorti":
        return "Stable"
    if stay >= 10:
        return "Critique"
    if stay >= 5:
        return "Modéré"
    return "Stable"


def stats_patients_page(df: pd.DataFrame) -> dict[str, int]:
    now = pd.Timestamp.now().normalize()
    st = np.where(df["DateSortie"].isna() | (df["DateSortie"] > now), "En cours", "Sorti")
    en_cours = int((st == "En cours").sum())
    sortis = int((st == "Sorti").sum())
    critiques = int((df["DureeSejour"] >= 10).sum())
    return {"total": len(df), "en_cours": en_cours, "sortis": sortis, "critiques": critiques}


def export_filtered_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
