"""Entretien de contenu/his/his.yaml, avant chaque construction du site.

Usage : python outils/his_entretien.py
- HIS passée à « Annulée » : note la date d'annulation (annulee_le), pour ne l'afficher barrée
  que quelques jours (his.annulee_affichee_jours dans config.yaml) ;
- HIS rétablie (« Prévue ») : efface cette date ;
- HIS passée depuis plus de his.conservation_jours : retirée du fichier (et donc de l'admin).
Ne réécrit le fichier que s'il y a quelque chose à changer. Lancé par les workflows GitHub.
"""
import datetime as dt
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "contenu" / "his" / "his.yaml"


def jour(valeur):
    if isinstance(valeur, dt.date):
        return valeur
    return dt.date.fromisoformat(str(valeur)[:10]) if valeur else None


def main():
    if not FICHIER.exists():
        return
    reglages = (yaml.safe_load((RACINE / "config.yaml").read_text(encoding="utf-8")) or {}).get("his") or {}
    conservation = int(reglages.get("conservation_jours", 30))
    aujourdhui = dt.date.today()
    donnees = yaml.safe_load(FICHIER.read_text(encoding="utf-8")) or {}
    avant = yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False)
    gardees = []
    for h in donnees.get("his") or []:
        date = jour(h.get("date"))
        if date and (aujourdhui - date).days > conservation:
            print(f"HIS du {date} retirée (passée depuis plus de {conservation} jours).")
            continue
        if h.get("etat") == "annulee" and not h.get("annulee_le"):
            h["annulee_le"] = aujourdhui.isoformat()
        elif h.get("etat") != "annulee" and h.get("annulee_le"):
            h["annulee_le"] = ""
        gardees.append(h)
    donnees["his"] = gardees
    apres = yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False)
    if apres != avant:
        FICHIER.write_text(apres, encoding="utf-8")
        print("contenu/his/his.yaml mis à jour.")


if __name__ == "__main__":
    main()
