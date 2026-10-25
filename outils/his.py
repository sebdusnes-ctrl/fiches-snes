"""Transmet les HIS saisies dans l'espace admin au script Google de la liste de diffusion.

Usage : python outils/his.py
Lit contenu/his/his.yaml et envoie chaque HIS à venir dont « annoncer » est coché, avec son
identifiant et son état (prévue ou annulée). Le script Google compare avec ce qu'il a déjà envoyé
et décide : annonce, modification (date, horaire ou lieu), annulation, ou rappel deux jours avant
(dernier moment pour prévenir la direction 48 h avant). Rien n'est envoyé deux fois.
Adresse et clé : variables d'environnement LISTE_URL et LISTE_CLE (secrets GitHub).
Lancé après chaque publication et par le relevé quotidien des stages.
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

import yaml

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "contenu" / "his" / "his.yaml"


def appeler(url, cle, his, rappel):
    donnees = {k: his.get(k) for k in ("id", "etat", "date", "debut", "fin", "lieu", "odj", "statuts")}
    corps = urllib.parse.urlencode({"action": "his", "cle": cle, "rappel": "oui" if rappel else "non",
                                    "donnees": json.dumps(donnees, ensure_ascii=False, default=str)}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=corps), timeout=120, context=contexte_ssl()) as r:
        return r.read().decode("utf-8", errors="replace")


def version_attendue():
    """Version écrite dans Code.gs (dépôt) : celle que le script Google déployé doit avoir."""
    texte = (RACINE / "outils" / "liste_diffusion" / "Code.gs").read_text(encoding="utf-8")
    return re.search(r"^const VERSION = '([^']+)'", texte, re.M).group(1)


def version_deployee(url):
    with urllib.request.urlopen(url + "?a=version", timeout=60, context=contexte_ssl()) as r:
        texte = r.read().decode("utf-8", errors="replace").strip()
    # Les versions antérieures au numéro de version répondent par une page HTML.
    return "ancienne version, sans numéro" if texte.startswith("<") else texte


def contexte_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


def main():
    url, cle = os.environ.get("LISTE_URL"), os.environ.get("LISTE_CLE")
    if not (url and cle):
        print("LISTE_URL ou LISTE_CLE absent : pas d'envoi.")
        return
    if not FICHIER.exists():
        return
    attendue, deployee = version_attendue(), version_deployee(url)
    if deployee != attendue:
        sys.exit(f"Le script Google n'est pas à jour : version déployée « {deployee} », "
                 f"attendue « {attendue} ». Copiez outils/liste_diffusion/Code.gs dans Apps Script, puis "
                 "Déployer → Gérer les déploiements → Nouvelle version.")
    print(f"Script Google : version {deployee}")
    aujourdhui = dt.date.today()
    jour_rappel = aujourdhui + dt.timedelta(days=2)
    erreur = False
    for h in (yaml.safe_load(FICHIER.read_text(encoding="utf-8")) or {}).get("his") or []:
        jour = h.get("date")
        if isinstance(jour, str):
            jour = dt.date.fromisoformat(jour[:10])
        if not jour or jour < aujourdhui or h.get("annoncer") is False or not h.get("debut"):
            continue
        h = dict(h, date=jour.isoformat(), debut=str(h["debut"]), fin=str(h.get("fin") or ""),
                 etat=h.get("etat") or "prevue")
        if not h.get("id"):
            print(f"HIS du {h['date']} sans identifiant : ouvrez-la et enregistrez-la dans l'espace admin.")
            erreur = True
            continue
        reponse = appeler(url, cle, h, rappel=(jour == jour_rappel))
        print(f"HIS du {h['date']} {h['debut']} ({h['etat']}) → {reponse}")
        if not reponse.startswith(("envoyé", "rien")):
            erreur = True
    if erreur:
        sys.exit("Au moins une HIS n'a pas pu être traitée.")


if __name__ == "__main__":
    main()
