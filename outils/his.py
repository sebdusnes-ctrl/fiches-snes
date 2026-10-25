"""Envoie l'annonce des HIS saisies dans l'espace admin, et leur rappel deux jours avant.

Usage : python outils/his.py
Lit contenu/his/his.yaml. Pour chaque HIS à venir dont « annoncer » est coché :
annonce (le script Google ne l'envoie qu'une fois), et rappel si elle a lieu dans deux jours
(dernier moment pour prévenir la direction 48 h avant).
Adresse et clé : variables d'environnement LISTE_URL et LISTE_CLE (secrets GitHub).
Lancé après chaque publication et par le relevé quotidien des stages.
"""
import datetime as dt
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "contenu" / "his" / "his.yaml"


def appeler(url, cle, action, his):
    donnees = {k: his.get(k) for k in ("date", "debut", "fin", "lieu", "odj", "statuts")}
    corps = urllib.parse.urlencode({"action": action, "cle": cle,
                                    "donnees": json.dumps(donnees, ensure_ascii=False, default=str)}).encode()
    try:
        import certifi
        contexte = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        contexte = None
    with urllib.request.urlopen(urllib.request.Request(url, data=corps), timeout=120, context=contexte) as r:
        return r.read().decode("utf-8", errors="replace")


def main():
    url, cle = os.environ.get("LISTE_URL"), os.environ.get("LISTE_CLE")
    if not (url and cle):
        print("LISTE_URL ou LISTE_CLE absent : pas d'envoi.")
        return
    if not FICHIER.exists():
        return
    aujourdhui = dt.date.today()
    rappel = aujourdhui + dt.timedelta(days=2)
    erreur = False
    for h in (yaml.safe_load(FICHIER.read_text(encoding="utf-8")) or {}).get("his") or []:
        jour = h.get("date")
        if isinstance(jour, str):
            jour = dt.date.fromisoformat(jour[:10])
        if not jour or jour < aujourdhui or h.get("annoncer") is False or not h.get("debut"):
            continue
        h = dict(h, date=jour.isoformat(), debut=str(h["debut"]), fin=str(h.get("fin") or ""))
        actions = ["his_annonce"] + (["his_rappel"] if jour == rappel else [])
        for action in actions:
            reponse = appeler(url, cle, action, h)
            print(f"HIS du {h['date']} {h['debut']} : {action} → {reponse}")
            if not reponse.startswith(("envoyé", "déjà", "annonce récente")):
                erreur = True
    if erreur:
        sys.exit("Réponse inattendue du script Google.")


if __name__ == "__main__":
    main()
