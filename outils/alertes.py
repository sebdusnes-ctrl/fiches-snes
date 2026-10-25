"""Envoie à la liste de diffusion les changements de stages du jour (nouveau stage, date ou lieu modifiés).

Usage : python outils/alertes.py nouveautes.json
Le fichier vient de « outils/stages.py --nouveautes ». L'envoi passe par le script Google de la
liste (outils/liste_diffusion/Code.gs) ; adresse et clé viennent des variables d'environnement
LISTE_URL et LISTE_CLE (secrets GitHub). Sans elles, rien n'est envoyé.
"""
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from build import date_fr, moins_un_mois, titre_lisible  # noqa: E402

TYPES_ALERTE = {"nouveau", "date", "lieu"}


def preparer(nouveautes, stages):
    par_id = {s["id"]: s for s in stages}
    items = []
    for e in nouveautes:
        s = par_id.get(e.get("id"))
        if e.get("type") not in TYPES_ALERTE or not s:
            continue
        jour = dt.date.fromisoformat(s["date"]) if s.get("date") else None
        items.append({
            "type": e["type"],
            "titre": titre_lisible(s["titre"]),
            "changement": e["changement"],
            "date_fr": date_fr(jour) + (f", {s['horaires']}" if jour and s.get("horaires") else ""),
            "lieu": s.get("lieu", ""),
            "limite_fr": date_fr(moins_un_mois(jour), jour=False) if jour else "",
            "programme": s.get("programme", ""),
        })
    return items


def main():
    url, cle = os.environ.get("LISTE_URL"), os.environ.get("LISTE_CLE")
    if not (url and cle):
        print("LISTE_URL ou LISTE_CLE absent : pas d'alerte envoyée.")
        return
    fichier = Path(sys.argv[1])
    nouveautes = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else []
    stages = json.loads((RACINE / "contenu" / "stages.json").read_text(encoding="utf-8"))["stages"]
    items = preparer(nouveautes, stages)
    if not items:
        print("Aucun changement à signaler.")
        return
    corps = urllib.parse.urlencode({"action": "stages", "cle": cle,
                                    "donnees": json.dumps(items, ensure_ascii=False)}).encode()
    try:
        import certifi
        contexte = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        contexte = None
    with urllib.request.urlopen(urllib.request.Request(url, data=corps), timeout=120, context=contexte) as r:
        reponse = r.read().decode("utf-8", errors="replace")
    # Journaux GitHub publics : on n'y écrit pas le nombre d'inscrit·es.
    print(f"{len(items)} changement(s) transmis : {re.sub(r' à [0-9]+', '', reponse)}")
    if not reponse.startswith(("envoyé", "rien")):
        sys.exit("Réponse inattendue du script Google.")


if __name__ == "__main__":
    main()
