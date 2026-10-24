"""Génère le site statique des fiches SNES-FSU dans docs/ (servi par GitHub Pages).

Usage : python build.py
Contenu : config.yaml + contenu/*.yaml (un fichier par thème).
"""
import datetime as dt
import hashlib
import json
import html
import re
import shutil
import sys
from io import BytesIO
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

RACINE = Path(__file__).parent
SORTIE = RACINE / "docs"


# --- Mise en forme du texte des fiches -------------------------------------

def typographie(texte):
    """Espaces insécables : milliers (1 250), unités (18 h, 90 %), ponctuation haute."""
    t = re.sub(r"(\d) (?=\d{3}\b)", "\\1\u202f", str(texte))
    t = re.sub(r"(\d) (?=(h|€|%|km|jours?|semaines?|mois|points?)\b|€|%)", "\\1\u00a0", t)
    t = re.sub(r" ([:;?!»])", "\u00a0\\1", t)
    return re.sub(r"« ", "«\u00a0", t)


def formater(texte):
    """Échappe le HTML puis interprète **gras** et [lien](https://…)."""
    t = html.escape(typographie(texte), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    # Lien vers une autre fiche : [texte](fiche:identifiant) ; les pages sont toutes dans fiches/.
    t = re.sub(r"\[([^\]]+)\]\(fiche:([a-z0-9-]+)\)",
               r'<a class="lien-fiche" href="\2.html">\1</a>', t)
    return t


def texte_brut(texte):
    return re.sub(r"\*\*|\[|\]\([^)]*\)", "", str(texte))


# --- QR codes ---------------------------------------------------------------

def qr_svg(url):
    """QR code en SVG inline (net à l'impression), ou chaîne vide sans URL."""
    if not url:
        return ""
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=2)
    buf = BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    # Taille pilotée par le CSS, couleur forcée en noir sur blanc.
    svg = re.sub(r'\swidth="[^"]*"', "", svg, count=1)
    svg = re.sub(r'\sheight="[^"]*"', "", svg, count=1)
    return svg.replace("<svg", '<svg class="qr" role="img" aria-label="QR code"', 1)


def qr_png(url, chemin):
    import qrcode
    qr = qrcode.QRCode(border=2, box_size=20,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make_image(fill_color="black", back_color="white").save(chemin)


# --- Chargement et contrôle du contenu --------------------------------------

def charger():
    config = yaml.safe_load((RACINE / "config.yaml").read_text(encoding="utf-8"))
    url = (config.get("url_site") or "").strip()
    if url and not url.endswith("/"):
        url += "/"
    config["url_site"] = url
    # Adresses de la section : liste « courriels » (ou ancienne clé « courriel »), jointes pour le mailto.
    contact = config.setdefault("contact", {})
    adresses = contact.get("courriels") or ([contact["courriel"]] if contact.get("courriel") else [])
    contact["courriels"] = adresses
    contact["mailto"] = ",".join(adresses)
    liste = config.setdefault("liste_diffusion", {})
    liste.setdefault("url", "")
    liste.setdefault("statuts", [])

    themes, ids, erreurs = [], set(), []
    for fichier in sorted((RACINE / "contenu").glob("*.yaml")):
        data = yaml.safe_load(fichier.read_text(encoding="utf-8"))
        theme = data["theme"]
        theme["fiches"] = data.get("fiches") or []
        for f in theme["fiches"]:
            for champ in ("id", "titre", "resume", "en_bref", "source"):
                if not f.get(champ):
                    erreurs.append(f"{fichier.name} : fiche {f.get('id', '?')} sans « {champ} »")
            if f.get("id") in ids:
                erreurs.append(f"{fichier.name} : identifiant en double « {f['id']} »")
            ids.add(f.get("id"))
            sources = f.get("source") or []
            f["sources"] = sources if isinstance(sources, list) else [sources]
            for s in f["sources"]:
                if s.get("doc") not in config["sources"]:
                    erreurs.append(f"{fichier.name} : source inconnue « {s.get('doc')} » ({f.get('id')})")
            f["theme"] = theme
        themes.append(theme)
    # Les liens [texte](fiche:id) doivent viser une fiche existante.
    for theme in themes:
        for f in theme["fiches"]:
            morceaux = f.get("en_bref", []) + f.get("textes", []) + f.get("agir", []) + [f.get("snes", "")]
            for cible in re.findall(r"\]\(fiche:([a-z0-9-]+)\)", " ".join(map(str, morceaux))):
                if cible not in ids:
                    erreurs.append(f"fiche {f['id']} : lien vers une fiche inconnue « {cible} »")
    if erreurs:
        sys.exit("Contenu invalide :\n  " + "\n  ".join(erreurs))
    return config, themes


# --- Stages syndicaux (contenu/stages.json, relevé par outils/stages.py) ------

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"]
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
SIGLES = {"TZR", "CPE", "AESH", "SNES", "FSU", "CA", "AED", "SNUEP"}


def date_fr(d, jour=True):
    if not d:
        return ""
    return (f"{JOURS_FR[d.weekday()]} " if jour else "") + f"{d.day} {MOIS_FR[d.month - 1]} {d.year}"


def moins_un_mois(d):
    """Même jour du mois précédent (ou dernier jour de ce mois s'il est plus court)."""
    a, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    j = d.day
    while True:
        try:
            return dt.date(a, m, j)
        except ValueError:  # 31 mars → 28/29 février, etc.
            j -= 1


def titre_lisible(t):
    mots = [m if m.strip("()«»,.") in SIGLES else m.lower() for m in t.split()]
    s = " ".join(mots)
    return s[:1].upper() + s[1:]


def preparer_stages(aujourdhui):
    fichier = RACINE / "contenu" / "stages.json"
    if not fichier.exists():
        return None
    d = json.loads(fichier.read_text(encoding="utf-8"))
    liste = []
    for s in d["stages"]:
        s = dict(s)
        s["titre_affiche"] = titre_lisible(s["titre"])
        jour = dt.date.fromisoformat(s["date"]) if s.get("date") else None
        s["date_fr"] = date_fr(jour)
        s["date_initiale_fr"] = date_fr(dt.date.fromisoformat(s["date_initiale"])) if s.get("date_initiale") else ""
        if jour is None:
            s["statut"], s["statut_libelle"] = "info", "Date à préciser"
        else:
            limite = moins_un_mois(jour)
            s["limite_fr"] = date_fr(limite, jour=False)
            if jour < aujourdhui:
                s["statut"], s["statut_libelle"] = "termine", "Terminé"
            elif aujourdhui > limite:
                s["statut"], s["statut_libelle"] = "depasse", "Délai dépassé"
            elif (limite - aujourdhui).days <= 7:
                s["statut"], s["statut_libelle"] = "proche", "Derniers jours"
            else:
                s["statut"], s["statut_libelle"] = "ouvert", "Ouvert"
        modif = dt.date.fromisoformat(s["modifie_le"]) if s.get("modifie_le") else None
        s["recent"] = bool(modif and (aujourdhui - modif).days <= 30)
        s["modifie_fr"] = date_fr(modif, jour=False) if modif else ""
        liste.append((jour or dt.date.max, s))
    d["liste"] = [s for _, s in sorted(liste, key=lambda x: x[0])]
    for e in d.get("journal", []):
        e["jour_fr"] = date_fr(dt.date.fromisoformat(e["jour"]), jour=False)
        e["stage_affiche"] = titre_lisible(e["stage"])
    v = d.get("verifie_le", "")
    try:
        vd = dt.datetime.strptime(v, "%Y-%m-%d %H:%M")
        d["verifie_le_fr"] = f"{date_fr(vd.date(), jour=False)} à {vd:%H:%M}"
    except ValueError:
        d["verifie_le_fr"] = v
    return d


# --- Génération --------------------------------------------------------------

def construire():
    config, themes = charger()
    url = config["url_site"]

    env = Environment(loader=FileSystemLoader(RACINE / "modeles"), autoescape=True)
    env.filters["fmt"] = lambda t: __import__("markupsafe").Markup(formater(t))
    env.filters["brut"] = texte_brut
    env.filters["typo"] = typographie

    if SORTIE.exists():
        shutil.rmtree(SORTIE)
    (SORTIE / "fiches").mkdir(parents=True)
    (SORTIE / "qr").mkdir()
    shutil.copytree(RACINE / "static", SORTIE / "static")
    (SORTIE / ".nojekyll").write_text("", encoding="utf-8")

    # Empreinte des fichiers statiques : change à chaque modification, ce qui
    # oblige les navigateurs à recharger CSS et scripts (pas de cache périmé).
    empreinte = hashlib.sha1()
    for f in sorted((RACINE / "static").rglob("*")):
        if f.is_file():
            empreinte.update(f.read_bytes())

    commun = dict(config=config, themes=themes, v=empreinte.hexdigest()[:8],
                  nb_fiches=sum(len(t["fiches"]) for t in themes))

    par_id = {f["id"]: f for th in themes for f in th["fiches"]}
    une = [par_id[i] for i in (config.get("a_la_une") or []) if i in par_id]
    aujourdhui = dt.date.today()
    stages = preparer_stages(aujourdhui)
    page = env.get_template("index.html").render(
        racine="", url_page=url, une=une, avec_stages=bool(stages), **commun)
    (SORTIE / "index.html").write_text(page, encoding="utf-8")

    for theme in themes:
        for f in theme["fiches"]:
            url_fiche = f"{url}fiches/{f['id']}.html" if url else ""
            page = env.get_template("fiche.html").render(
                racine="../", fiche=f, url_page=url_fiche, qr=qr_svg(url_fiche), **commun)
            (SORTIE / "fiches" / f"{f['id']}.html").write_text(page, encoding="utf-8")
            if url:
                qr_png(url_fiche, SORTIE / "qr" / f"{f['id']}.png")

    page = env.get_template("affiche.html").render(
        racine="", url_page=url, qr=qr_svg(url), **commun)
    (SORTIE / "affiche.html").write_text(page, encoding="utf-8")
    if url:
        qr_png(url, SORTIE / "qr" / "accueil.png")

    page = env.get_template("inscription.html").render(
        racine="", url_page=f"{url}inscription.html" if url else "", **commun)
    (SORTIE / "inscription.html").write_text(page, encoding="utf-8")

    if stages:
        page = env.get_template("stages.html").render(
            racine="", url_page=f"{url}stages.html" if url else "", stages=stages,
            aujourdhui_fr=date_fr(aujourdhui, jour=False), **commun)
        (SORTIE / "stages.html").write_text(page, encoding="utf-8")

    print(f"{commun['nb_fiches']} fiches, {len(themes)} thèmes → {SORTIE}"
          + (f" ; {len(stages['liste'])} stages" if stages else ""))
    if not url:
        print("⚠ url_site vide dans config.yaml : QR codes non générés.")


if __name__ == "__main__":
    construire()
