"""Relève les stages syndicaux publiés par le SNES-FSU Lille et tient un journal des changements.

Usage : python outils/stages.py [--fichier page.html]
Écrit contenu/stages.json : la liste des stages, la date de la vérification et le journal
(stage ajouté, retiré, date reportée, lieu modifié). Lancé chaque jour par GitHub Actions ;
--nouveautes écrit les changements du jour pour outils/alertes.py.
"""
import argparse
import datetime as dt
import html
import json
import re
import ssl
import sys
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "contenu" / "stages.json"
PAGE = "https://lille.snes.edu/Stages-SNES-FSU-2026-2027.html"
BASE = "https://lille.snes.edu/"
INSCRIPTION = "https://adherent.snes.edu/Public/indexStages.php?Aca=15"

MOIS = {m: i for i, m in enumerate(
    ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
     "septembre", "octobre", "novembre", "décembre"], 1)}
JOURS = {"lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"}
RE_DATE = re.compile(r"(\d{1,2})(?:er)?\s+(" + "|".join(MOIS) + r")\s+(\d{4})", re.I)
RE_HEURES = re.compile(r"\d{1,2}\s*h(?:\s*\d{2})?\s*[-–]\s*\d{1,2}\s*h(?:\s*\d{2})?", re.I)
TIRET = "—"
BARRE = "\x01"  # marque interne d'une ligne barrée (<del>) : ancienne information


def telecharger():
    req = urllib.request.Request(PAGE, headers={"User-Agent": "Mozilla/5.0 (fiches SNES-FSU)"})
    # Certificats à jour de certifi si présent (le magasin de certains Python Windows est périmé).
    try:
        import certifi
        contexte = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        contexte = None
    with urllib.request.urlopen(req, timeout=60, context=contexte) as r:
        return r.read().decode("utf-8", errors="replace")


def lignes(fragment):
    """Lignes d'une légende sous forme (texte, barré)."""
    def marquer(m):
        return "\n".join(BARRE + l.strip() for l in re.split(r"<br\s*/?>", m.group(1)))
    f = re.sub(r"<del>(.*?)</del>", marquer, fragment, flags=re.S)
    f = re.sub(r"<br\s*/?>", "\n", f)
    f = re.sub(r"<[^>]+>", "", f)
    f = html.unescape(f).replace("\xa0", " ")
    sortie = []
    for l in f.splitlines():
        barre = BARRE in l
        l = l.replace(BARRE, "").strip()
        if l:
            sortie.append((l, barre))
    return sortie


def date_iso(texte):
    m = RE_DATE.search(texte)
    if not m:
        return None
    j, mois, a = int(m.group(1)), MOIS[m.group(2).lower()], int(m.group(3))
    return dt.date(a, mois, j).isoformat()


def nature(l):
    if l.strip(" " + TIRET) == "":
        return "separateur"
    if l.lower() in JOURS:
        return "jour"
    if RE_DATE.search(l):
        return "date"
    if RE_HEURES.search(l):
        return "heures"
    if re.match(r"report", l, re.I):
        return "report"
    return "texte"


def analyser(page):
    stages = []
    # Chaque stage est une figure : un lien vers son programme PDF, puis sa légende.
    for fig in page.split('<figure class="spip_doc_inner">')[1:]:
        m_pdf = re.search(r'<a href="([^"]+\.pdf)"', fig)
        m_leg = re.search(r"<div class='spip_doc_descriptif[^']*'>(.*?)</div>", fig, re.S)
        if not (m_pdf and m_leg):
            continue
        pdf = m_pdf.group(1)
        lgn = lignes(m_leg.group(1))
        i = next((k for k, (l, _) in enumerate(lgn) if nature(l) == "separateur"), None)
        if i is None:
            continue
        titre = re.sub(r"\s+", " ", " ".join(l for l, _ in lgn[:i])).strip()
        corps = [(l, b, nature(l)) for l, b in lgn[i + 1:] if nature(l) != "separateur"]
        actuelles = [x for x in corps if not x[1]]
        anciennes = [x for x in corps if x[1]]
        dates = [date_iso(l) for l, _, n in actuelles if n == "date"]
        dates_barrees = [date_iso(l) for l, _, n in anciennes if n == "date"]
        heures = [l for l, _, n in actuelles if n == "heures"]
        lieu = [l for l, _, n in actuelles if n == "texte"]
        lieu_barre = [l for l, _, n in anciennes if n == "texte"]
        if any(re.search(r"lieu à définir", l, re.I) for l in lieu):
            lieu = ["Lieu à définir"]
        stages.append({
            "id": Path(pdf).stem,
            "titre": titre,
            "date": dates[-1] if dates else None,
            "date_initiale": dates_barrees[0] if dates_barrees else None,
            "horaires": re.sub(r"\s+", "", heures[-1]) if heures else "",
            "lieu": " · ".join(lieu),
            "lieu_barre": " · ".join(lieu_barre),
            "reporte": any(n == "report" for _, _, n in corps) or bool(dates_barrees),
            "programme": pdf if pdf.startswith("http") else BASE + pdf.lstrip("/"),
        })
    return stages


def lisible(champ, valeur):
    """Valeur pour le journal : dates en toutes lettres (« 5 novembre 2026 »)."""
    if not valeur:
        return "?"
    if champ == "date":
        d = dt.date.fromisoformat(valeur)
        noms = {i: m for m, i in MOIS.items()}
        return f"{d.day} {noms[d.month]} {d.year}"
    return valeur


def comparer(anciens, nouveaux, jour):
    """Entrées de journal entre deux relevés."""
    av = {s["id"]: s for s in anciens}
    ap = {s["id"]: s for s in nouveaux}
    journal = []
    for i, s in ap.items():
        if i not in av:
            if anciens:
                journal.append({"jour": jour, "id": i, "type": "nouveau", "stage": s["titre"],
                                "changement": "nouveau stage publié"})
            continue
        a = av[i]
        for champ, nom in (("date", "date"), ("lieu", "lieu"), ("horaires", "horaires")):
            if a.get(champ) != s.get(champ):
                journal.append({"jour": jour, "id": i, "type": champ, "stage": s["titre"],
                                "changement": f"{nom} : {lisible(champ, a.get(champ))} → {lisible(champ, s.get(champ))}"})
    for i, a in av.items():
        if i not in ap:
            journal.append({"jour": jour, "id": i, "type": "retire", "stage": a["titre"],
                            "changement": "retiré de la page du SNES-FSU Lille"})
    return journal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fichier", help="page HTML déjà téléchargée (test)")
    ap.add_argument("--nouveautes", help="écrit aussi les changements du jour dans ce fichier (alertes)")
    args = ap.parse_args()
    page = (Path(args.fichier).read_text(encoding="utf-8", errors="replace")
            if args.fichier else telecharger())
    stages = analyser(page)
    if not stages:
        sys.exit("Aucun stage reconnu : la page a peut-être changé de forme. Rien n'est modifié.")

    ancien = json.loads(SORTIE.read_text(encoding="utf-8")) if SORTIE.exists() else {}
    jour = dt.date.today().isoformat()
    nouvelles = comparer(ancien.get("stages", []), stages, jour)
    journal = nouvelles + ancien.get("journal", [])
    derniers = {}
    for e in journal:  # le journal est du plus récent au plus ancien
        derniers.setdefault(e["stage"], e["jour"])
    for s in stages:
        s["modifie_le"] = derniers.get(s["titre"])

    donnees = {
        "source": PAGE,
        "inscription": INSCRIPTION,
        "verifie_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stages": stages,
        "journal": journal[:30],
    }
    SORTIE.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.nouveautes:
        Path(args.nouveautes).write_text(json.dumps(nouvelles, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(stages)} stages relevés ; {len(nouvelles)} changement(s) détecté(s).")
    for e in nouvelles:
        print(f"  - {e['stage']} : {e['changement']}")


if __name__ == "__main__":
    main()
