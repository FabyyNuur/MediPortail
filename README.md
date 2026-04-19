# MediPortail - Dashboard hospitalier

Application web Flask pour visualiser et analyser des donnees hospitalieres depuis un fichier CSV.

Stack utilisee : Flask, Jinja2, pandas, Tailwind CSS, Chart.js.

## Objectif

Le projet permet de :

- explorer les indicateurs globaux (patients, couts, duree de sejour),
- filtrer les donnees (departement, maladie, sexe, periode),
- afficher des graphiques et tableaux de synthese,
- generer des maquettes de rapport.

## Prerequis

- Python 3.10+
- Node.js 18+ (compilation du CSS Tailwind)

## Installation

```bash
cd /Users/fabynuur/Desktop/MediPortail
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build:css
```

## Lancement en local

```bash
source .venv/bin/activate
python app.py
```

Alternative :

```bash
./run.sh
```

L'application ecoute par defaut sur le port 5050 (ou la variable d'environnement PORT).

Interface locale : http://127.0.0.1:5050/

## CSS (Tailwind)

Apres modification des templates HTML ou des scripts JS :

```bash
npm run build:css
```

Fichier genere : `static/css/app.css`.

## Variables d'environnement utiles

| Variable             | Description                                            |
| -------------------- | ------------------------------------------------------ |
| `PORT`               | Port d'ecoute local (defaut : 5050)                    |
| `HOSPITAL_DATA_PATH` | Chemin vers le CSV (defaut : `data/hospital_data.csv`) |
| `FLASK_DEBUG`        | `1` pour activer le mode debug                         |

## Structure du projet

- `app.py` : point d'entree Flask
- `analytics.py` : logique pandas (chargement, filtres, agregations)
- `routes/` : routes HTML et API
- `templates/` : pages Jinja2
- `static/js/` : scripts frontend (dashboard, rapports, aide a la decision)
- `static/css/` : styles compiles
- `data/` : source de donnees CSV
- `reporting/` : generation des maquettes PDF/HTML

## Donnees

Source par defaut : `data/hospital_data.csv` (separateur `;`).

Colonnes attendues :

- `PatientID`
- `Age`
- `Sexe`
- `Departement`
- `Maladie`
- `DureeSejour`
- `Cout`
- `DateAdmission`
- `DateSortie`
- `Traitement`
