"""Relève les stages syndicaux de l'académie de Lille et tient un journal des changements.

Usage : python outils/stages.py [--table page.html] [--s3 page.html] [--nouveautes fichier.json]
Deux sources, combinées :
  - le tableau d'inscription du SNES-FSU (INSCRIPTION) : liste complète et officielle des stages,
    date, horaires, lieu, clôture des inscriptions, inscriptions closes (ligne barrée) ;
  - la page du SNES-FSU Lille (PAGE) : programme (PDF) et anciennes date ou lieu barrés (report).
Écrit contenu/stages.json : stages, date de vérification et journal (stage ajouté, retiré, date
reportée, lieu modifié). Lancé chaque jour par GitHub Actions ; --nouveautes écrit les changements
du jour pour outils/alertes.py. --table et --s3 : pages déjà téléchargées (tests).
"""
import argparse
import datetime as dt
import html
import json
import re
import ssl
import sys
import unicodedata
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


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fiches SNES-FSU)"})
    # Certificats à jour de certifi si présent (le magasin de certains Python Windows est périmé).
    try:
        import certifi
        contexte = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        contexte = None
    with urllib.request.urlopen(req, timeout=60, context=contexte) as r:
        return decoder(r.read())


def decoder(octets):
    """Le tableau d'inscription annonce de l'UTF-8 mais sert du Windows-1252."""
    try:
        return octets.decode("utf-8")
    except UnicodeDecodeError:
        return octets.decode("cp1252", errors="replace")


def date_iso(texte):
    m = RE_DATE.search(texte)
    if not m:
        return None
    j, mois, a = int(m.group(1)), MOIS[m.group(2).lower()], int(m.group(3))
    return dt.date(a, mois, j).isoformat()


def texte_brut(fragment):
    t = re.sub(r"<br\s*/?>", " ", fragment)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ").replace("�", "à")
    return re.sub(r"\s+", " ", t).strip()


def identifiant(titre):
    """Identifiant stable tiré du titre : il ne change ni quand le stage est reporté, ni quand il ferme."""
    t = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def horaires_courts(texte):
    """« 09h00-16h30 » → « 9h-16h30 »."""
    m = re.search(r"(\d{1,2})h(\d{2})\s*-\s*(\d{1,2})h(\d{2})", texte)
    if not m:
        return ""
    def h(heure, minutes):
        return f"{int(heure)}h" + ("" if minutes == "00" else minutes)
    return f"{h(m.group(1), m.group(2))}-{h(m.group(3), m.group(4))}"


# --- Tableau d'inscription (source principale) -------------------------------

def analyser_inscription(page):
    # Le tableau des « autres sections académiques » (autres académies) est écarté.
    autres = page.find("proposés par d'autres sections académiques")
    if autres >= 0:
        suite = page.find('<table class="AfficheTabListe', page.find("</table>", page.find("<table", autres)))
        page = page[:autres] + (page[suite:] if suite >= 0 else "")
    lignes = re.findall(r'<tr onclick="ChangementStage\(\$\(this\)\);"[^>]*>(.*?)</tr>\s*<tr>(.*?)</table>\s*</td>\s*</tr>',
                        page, re.S)
    stages, vus = [], {}
    for ligne, detail in lignes:
        cellules = re.findall(r"<td([^>]*)>(.*?)</td>", ligne, re.S)
        if len(cellules) < 3:
            continue
        titre = texte_brut(cellules[0][1])
        if titre.lower().startswith("académie :"):
            continue
        style_date, date_txt = cellules[1][0], texte_brut(cellules[1][1])
        lieu = texte_brut(cellules[2][1])
        m = re.match(r"(.*?)\s*\((.*)\)\s*$", lieu)
        if m:
            lieu = f"{m.group(1)} · {m.group(2)}"
        m_clot = re.search(r"Clôture des inscriptions\s*:\s*</b>\s*([^<]+)", detail)
        ident = identifiant(titre)
        vus[ident] = vus.get(ident, 0) + 1
        if vus[ident] > 1:
            ident += f"-{vus[ident]}"
        stages.append({
            "id": ident,
            "titre": titre,
            "date": date_iso(date_txt),
            "date_initiale": None,
            "horaires": horaires_courts(date_txt),
            "lieu": lieu,
            "lieu_barre": "",
            "reporte": False,
            "programme": None,
            "cloture": date_iso(m_clot.group(1)) if m_clot else None,
            "inscriptions_closes": "line-through" in style_date or "Inscriptions closes" in detail,
            # Ligne bleue du SNES : réunion qui ne donne pas droit à une autorisation d'absence.
            "sans_autorisation": bool(re.search(r"(?i)background-color:\s*(?:blue|#(?:00|33|66)[0-9a-f]{2}ff|lightblue|#add8e6|aqua|cyan)", style_date)),
        })
    return stages


# --- Page du SNES-FSU Lille (programme, report) -------------------------------

def lignes_legende(fragment):
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


def analyser_s3(page):
    stages = []
    # Chaque stage est une figure : un lien vers son programme PDF, puis sa légende.
    for fig in page.split('<figure class="spip_doc_inner">')[1:]:
        m_pdf = re.search(r'<a href="([^"]+\.pdf)"', fig)
        m_leg = re.search(r"<div class='spip_doc_descriptif[^']*'>(.*?)</div>", fig, re.S)
        if not (m_pdf and m_leg):
            continue
        pdf = m_pdf.group(1)
        lgn = lignes_legende(m_leg.group(1))
        i = next((k for k, (l, _) in enumerate(lgn) if nature(l) == "separateur"), None)
        if i is None:
            continue
        corps = [(l, b, nature(l)) for l, b in lgn[i + 1:] if nature(l) != "separateur"]
        actuelles = [x for x in corps if not x[1]]
        anciennes = [x for x in corps if x[1]]
        dates = [date_iso(l) for l, _, n in actuelles if n == "date"]
        dates_barrees = [date_iso(l) for l, _, n in anciennes if n == "date"]
        stages.append({
            "titre": re.sub(r"\s+", " ", " ".join(l for l, _ in lgn[:i])).strip(),
            "date": dates[-1] if dates else None,
            "date_initiale": dates_barrees[0] if dates_barrees else None,
            "lieu": " · ".join(l for l, _, n in actuelles if n == "texte"),
            "lieu_barre": " · ".join(l for l, _, n in anciennes if n == "texte"),
            "reporte": any(n == "report" for _, _, n in corps) or bool(dates_barrees),
            "programme": pdf if pdf.startswith("http") else BASE + pdf.lstrip("/"),
        })
    return stages


def fusionner(stages, s3):
    """Ajoute à chaque stage du tableau le programme et le report de la page du SNES-FSU Lille,
    en rapprochant par la date, puis par la ville."""
    for s in stages:
        candidats = [x for x in s3 if s["date"] and s["date"] in (x["date"], x["date_initiale"])]
        ville = s["lieu"].split(" · ")[0].strip().upper()
        avec_ville = [x for x in candidats if ville and ville in x["lieu"].upper()]
        x = avec_ville[0] if avec_ville else (candidats[0] if len(candidats) == 1 else None)
        if x:
            s.update(programme=x["programme"], date_initiale=x["date_initiale"],
                     lieu_barre=x["lieu_barre"], reporte=x["reporte"])
            # Changement de lieu barré sur la page du SNES-FSU Lille : elle est plus à jour que le tableau.
            if x["lieu_barre"] and x["lieu"] and "définir" not in s["lieu"].lower():
                s["lieu"] = x["lieu"]
    return stages


# --- Journal -----------------------------------------------------------------

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
    """Entrées de journal entre deux relevés. Si aucun identifiant ne correspond (premier relevé,
    ou changement de source), c'est une initialisation : rien n'est signalé."""
    av = {s["id"]: s for s in anciens}
    ap = {s["id"]: s for s in nouveaux}
    if not set(av) & set(ap):
        return []
    journal = []
    for i, s in ap.items():
        if i not in av:
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
                            "changement": "retiré de la liste du SNES-FSU"})
    return journal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", help="tableau d'inscription déjà téléchargé (test)")
    ap.add_argument("--s3", help="page du SNES-FSU Lille déjà téléchargée (test)")
    ap.add_argument("--nouveautes", help="écrit aussi les changements du jour dans ce fichier (alertes)")
    args = ap.parse_args()
    table = decoder(Path(args.table).read_bytes()) if args.table else telecharger(INSCRIPTION)
    stages = analyser_inscription(table)
    if not stages:
        sys.exit("Aucun stage reconnu dans le tableau d'inscription : la page a peut-être changé de forme. "
                 "Rien n'est modifié.")
    try:
        s3 = analyser_s3(decoder(Path(args.s3).read_bytes()) if args.s3 else telecharger(PAGE))
    except OSError as e:  # page du SNES-FSU Lille indisponible : on publie quand même la liste
        print(f"Page du SNES-FSU Lille indisponible ({e}) : programmes et reports non mis à jour.")
        s3 = []
    fusionner(stages, s3)

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
    print(f"{len(stages)} stages relevés ({sum(1 for s in stages if s['programme'])} avec programme) ; "
          f"{len(nouvelles)} changement(s) détecté(s).")
    for e in nouvelles:
        print(f"  - {e['stage']} : {e['changement']}")


if __name__ == "__main__":
    main()
