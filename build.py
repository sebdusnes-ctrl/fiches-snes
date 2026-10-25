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


def formater(texte, dossier_fiches=""):
    """Échappe le HTML puis interprète **gras** et [lien](https://…).

    dossier_fiches : préfixe des liens [texte](fiche:id), « fiches/ » depuis une page à la racine du site.
    """
    t = html.escape(typographie(texte), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s\"]+)\)",  # pas de « " » : il fermerait l'attribut href
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    # Lien vers une autre fiche : [texte](fiche:identifiant) ; les pages sont toutes dans fiches/.
    t = re.sub(r"\[([^\]]+)\]\(fiche:([a-z0-9-]+)\)",
               rf'<a class="lien-fiche" href="{dossier_fiches}\2.html">\1</a>', t)
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
    # Textes généraux (titres, accroche, intros), modifiables depuis l'espace admin.
    textes = yaml.safe_load((RACINE / "contenu" / "textes" / "site.yaml").read_text(encoding="utf-8")) or {}
    config.setdefault("contact", {})["permanence"] = textes.pop("permanence", "")
    config.update({k: textes[k] for k in ("titre_site", "section", "accroche", "esprit") if k in textes})
    config["textes"] = textes
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
    liste.setdefault("domaines_refuses", [])

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
    for cible in re.findall(r"\]\(fiche:([a-z0-9-]+)\)", " ".join(map(str, config["textes"].values()))):
        if cible not in ids:
            erreurs.append(f"textes du site : lien vers une fiche inconnue « {cible} »")
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
    """Titre en capitales (ancienne source) → casse normale ; un titre déjà en minuscules est gardé."""
    if any(c.islower() for c in t):
        return t
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
        cloture = dt.date.fromisoformat(s["cloture"]) if s.get("cloture") else None
        s["cloture_fr"] = date_fr(cloture, jour=False) if cloture else ""
        if jour is None:
            s["statut"], s["statut_libelle"] = "info", "Date à préciser"
        else:
            limite = moins_un_mois(jour)
            s["limite_fr"] = date_fr(limite, jour=False)
            if jour < aujourdhui:
                s["statut"], s["statut_libelle"] = "termine", "Terminé"
            elif s.get("inscriptions_closes") or (cloture and cloture < aujourdhui):
                s["statut"], s["statut_libelle"] = "ferme", "Inscriptions closes"
            elif s.get("sans_autorisation"):
                s["statut"], s["statut_libelle"] = "info", "Sans autorisation d’absence"
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


# --- Heures d'information syndicale (contenu/his/his.yaml, saisies dans /admin) ------

def preparer_his(aujourdhui, jours_annulee=7):
    """HIS à venir, de la plus proche à la plus lointaine. Une HIS annulée reste affichée (barrée)
    jours_annulee jours après son annulation (annulee_le, noté par outils/his_entretien.py)."""
    fichier = RACINE / "contenu" / "his" / "his.yaml"
    if not fichier.exists():
        return []
    liste = []
    for h in (yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}).get("his") or []:
        jour = h.get("date")
        if isinstance(jour, str):
            jour = dt.date.fromisoformat(jour[:10])
        if not jour or jour < aujourdhui:
            continue
        h = dict(h, date=jour.isoformat(), date_fr=date_fr(jour, jour=True))
        h["horaire"] = (h.get("debut") or "") + (f"-{h['fin']}" if h.get("fin") else "")
        h["annulee"] = h.get("etat") == "annulee"
        if h["annulee"] and h.get("annulee_le"):
            if (aujourdhui - dt.date.fromisoformat(str(h["annulee_le"])[:10])).days > jours_annulee:
                continue
        liste.append(h)
    return sorted(liste, key=lambda h: (h["date"], h.get("debut") or ""))


# --- Espace admin (/admin : Sveltia CMS, connexion par jeton GitHub) ---------------

VERSION_CMS = "0.233.0"
# Empreinte SRI du fichier ci-dessus : le navigateur refuse un fichier modifié (CDN compromis),
# qui pourrait sinon voler le jeton GitHub. À recalculer en changeant de version :
# curl -sL https://unpkg.com/@sveltia/cms@VERSION/dist/sveltia-cms.js | openssl dgst -sha384 -binary | openssl base64 -A
INTEGRITE_CMS = "sha384-lq8uMtdOlotHkm4oFSd+o7whev4/k4o8uZwio5iwuW8sJsUxf9K4OewbxVUzGP5m"
AIDE_TEXTE = "**gras** · [texte](https://…) · lien vers une fiche : [texte](fiche:identifiant)"


def config_admin(config, themes):
    """Configuration du CMS, tirée du contenu réel : un formulaire par thème, sources de config.yaml."""
    def liste_textes(nom, libelle, requis=True):
        return {"name": nom, "label": libelle, "widget": "list", "required": requis, "hint": AIDE_TEXTE,
                "field": {"name": "point", "label": "Point", "widget": "text"}}
    fiche = [
        {"name": "id", "label": "Identifiant (adresse de la page)", "widget": "string",
         "pattern": ["^[a-z0-9-]+$", "minuscules, chiffres et tirets"],
         "hint": "Ne plus le changer une fois la fiche imprimée : il est dans le QR code."},
        {"name": "titre", "label": "Titre", "widget": "string"},
        {"name": "resume", "label": "Résumé (une ligne, sous le titre)", "widget": "string"},
        {"name": "a_jour", "label": "Avertissement (facultatif)", "widget": "string", "required": False},
        liste_textes("en_bref", "En bref"),
        liste_textes("textes", "Ce que disent les textes", False),
        liste_textes("agir", "Ce que vous pouvez faire", False),
        {"name": "snes", "label": "Position du SNES-FSU (facultatif)", "widget": "text", "required": False},
        {"name": "liens", "label": "Pour aller plus loin", "widget": "list", "required": False,
         "summary": "{{fields.libelle}}",
         "fields": [{"name": "libelle", "label": "Libellé", "widget": "string"},
                    {"name": "url", "label": "Adresse", "widget": "string"}]},
        {"name": "source", "label": "Sources", "widget": "list", "summary": "{{fields.doc}} {{fields.pages}} {{fields.ref}}",
         "fields": [{"name": "doc", "label": "Document", "widget": "select",
                     "options": [{"label": d["titre"], "value": k} for k, d in config["sources"].items()]},
                    {"name": "pages", "label": "Pages", "widget": "string", "required": False},
                    {"name": "ref", "label": "Référence (articles…)", "widget": "string", "required": False}]},
    ]
    theme = {"name": "theme", "label": "Thème", "widget": "object", "collapsed": True, "fields": [
        {"name": "id", "label": "Identifiant", "widget": "string"},
        {"name": "titre", "label": "Titre", "widget": "string"},
        {"name": "description", "label": "Description", "widget": "string"},
        {"name": "couleur", "label": "Couleur", "widget": "string"}]}
    fichiers = [{"name": f.stem, "label": th["titre"], "file": f"contenu/{f.name}",
                 "fields": [theme, {"name": "fiches", "label": "Fiches", "widget": "list",
                                    "summary": "{{fields.titre}}", "fields": fiche}]}
                for f, th in zip(sorted((RACINE / "contenu").glob("*.yaml")), themes)]
    statuts = (config.get("liste_diffusion") or {}).get("statuts") or []
    his = {"name": "his", "label": "Heures d’information syndicale", "files": [{
        "name": "his", "label": "HIS", "file": "contenu/his/his.yaml", "fields": [{
            "name": "his", "label": "HIS", "widget": "list", "summary": "{{fields.date}} {{fields.debut}} {{fields.lieu}}",
            "hint": "Une HIS enregistrée s’affiche sur l’accueil ; l’annonce, puis un rappel deux jours avant (délai de prévenance de 48 h), partent tout seuls. Changer la date, l’horaire ou le lieu envoie un courriel « HIS modifiée ». Une HIS annulée reste affichée barrée 7 jours ; une HIS passée disparaît de cette liste après 30 jours.",
            "fields": [
                {"name": "id", "label": "Identifiant (automatique)", "widget": "uuid", "read_only": True},
                {"name": "etat", "label": "État", "widget": "select", "default": "prevue",
                 "options": [{"label": "Prévue", "value": "prevue"}, {"label": "Annulée", "value": "annulee"}],
                 "hint": "Pour annuler, choisissez « Annulée » sans supprimer l’HIS : un courriel d’annulation part aux inscrit·es."},
                {"name": "date", "label": "Date", "widget": "datetime", "format": "YYYY-MM-DD",
                 "date_format": "DD/MM/YYYY", "time_format": False},
                {"name": "debut", "label": "Début", "widget": "string", "hint": "ex. 12h30"},
                {"name": "fin", "label": "Fin", "widget": "string", "required": False, "hint": "ex. 13h30"},
                {"name": "lieu", "label": "Lieu", "widget": "string", "required": False},
                {"name": "odj", "label": "Ordre du jour", "widget": "text", "required": False},
                {"name": "statuts", "label": "Destinataires", "widget": "select", "multiple": True,
                 "required": False, "options": statuts, "hint": "Vide : tout le monde."},
                {"name": "annoncer", "label": "Envoyer l’annonce et le rappel par courriel", "widget": "boolean",
                 "default": True},
                # Rempli par le robot à l'annulation (affichage limité dans le temps) : à conserver.
                {"name": "annulee_le", "label": "Annulée le (automatique)", "widget": "hidden", "required": False}]}]}]}
    def champ(nom, libelle, widget="string", aide=""):
        return {"name": nom, "label": libelle, "widget": widget, "hint": aide, "required": False}
    textes = {"name": "textes", "label": "Textes du site", "files": [{
        "name": "site", "label": "Titres, accroches et intros", "file": "contenu/textes/site.yaml", "fields": [
            champ("titre_site", "Titre du site (en-tête de chaque page)"),
            champ("section", "Nom de la section (au-dessus du titre)"),
            champ("accroche", "Accroche de l’accueil", "text"),
            champ("esprit", "Encadré « Faire valoir ses droits » (accueil et bas des fiches)", "text", AIDE_TEXTE),
            champ("note_pied", "Note en bas de chaque page", "text", AIDE_TEXTE),
            champ("permanence", "Permanence (bloc « Contactez la section »)"),
            champ("stages_titre", "Page Stages : titre"),
            champ("stages_intro", "Page Stages : introduction", "text", AIDE_TEXTE),
            champ("inscription_titre", "Page Inscription : titre"),
            champ("inscription_intro", "Page Inscription : introduction", "text", AIDE_TEXTE),
            champ("inscription_public", "Page Inscription : qui peut s’inscrire", "text", AIDE_TEXTE),
            champ("inscription_adresse", "Page Inscription : consigne sous l’adresse (adresse personnelle)", "text"),
        ]}]}
    return {
        "backend": {"name": "github", "repo": "sebdusnes-ctrl/fiches-snes", "branch": "main"},
        "site_url": config["url_site"], "display_url": config["url_site"],
        "media_folder": "static/images", "public_folder": "/static/images",
        "editor": {"preview": False},
        "output": {"yaml": {"quote": "double"}},
        "collections": [his, {"name": "fiches", "label": "Fiches", "files": fichiers}, textes],
    }


def construire_admin(config, themes):
    (SORTIE / "admin").mkdir()
    (SORTIE / "admin" / "config.yml").write_text(
        yaml.safe_dump(config_admin(config, themes), allow_unicode=True, sort_keys=False), encoding="utf-8")
    (SORTIE / "admin" / "index.html").write_text(f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Admin · {html.escape(config["titre_site"])}</title>
</head>
<body>
<script src="https://unpkg.com/@sveltia/cms@{VERSION_CMS}/dist/sveltia-cms.js" integrity="{INTEGRITE_CMS}" crossorigin="anonymous"></script>
</body>
</html>
""", encoding="utf-8")


# --- Génération --------------------------------------------------------------

def construire():
    config, themes = charger()
    url = config["url_site"]

    env = Environment(loader=FileSystemLoader(RACINE / "modeles"), autoescape=True)
    env.filters["fmt"] = lambda t: __import__("markupsafe").Markup(formater(t))
    env.filters["fmt_racine"] = lambda t: __import__("markupsafe").Markup(formater(t, "fiches/"))
    env.filters["brut"] = texte_brut
    env.filters["typo"] = typographie

    # Une fiche déjà en ligne ne disparaît pas par erreur (suppression dans l'admin) : son QR code
    # est peut-être imprimé. Pour la retirer volontairement, l'ajouter à fiches_retirees (config.yaml).
    ids = {f["id"] for th in themes for f in th["fiches"]}
    retirees = set(config.get("fiches_retirees") or [])
    en_ligne = {f.stem for f in (SORTIE / "fiches").glob("*.html")} if SORTIE.exists() else set()
    disparues = sorted(en_ligne - ids - retirees)
    if disparues:
        sys.exit("Fiche(s) en ligne absente(s) du contenu : " + ", ".join(disparues) +
                 "\n  Suppression voulue ? Ajoutez l'identifiant à « fiches_retirees » dans config.yaml."
                 "\n  Sinon, rétablissez la fiche (historique GitHub).")

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
        racine="", url_page=url, une=une, avec_stages=bool(stages),
        his=preparer_his(aujourdhui, int((config.get("his") or {}).get("annulee_affichee_jours", 7))), **commun)
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

    construire_admin(config, themes)

    print(f"{commun['nb_fiches']} fiches, {len(themes)} thèmes → {SORTIE}"
          + (f" ; {len(stages['liste'])} stages" if stages else ""))
    if not url:
        print("⚠ url_site vide dans config.yaml : QR codes non générés.")


if __name__ == "__main__":
    construire()
