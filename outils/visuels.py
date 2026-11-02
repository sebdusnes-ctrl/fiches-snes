"""Produit les visuels prêts à imprimer ou à partager dans static/visuels/ :
affiche A4 (PDF), planche de 4 cartes A6 (PDF), image carrée (PNG).

Usage : python build.py && python outils/visuels.py && python build.py
(le second build copie les fichiers produits dans docs/). Nécessite Playwright (local).
À relancer si l'adresse du site, le nombre de fiches ou les contacts changent.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

RACINE = Path(__file__).resolve().parent.parent
DOCS = RACINE / "docs"
SORTIE = RACINE / "static" / "visuels"


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        for nom in ("affiche", "cartes"):
            pg.goto((DOCS / f"{nom}.html").resolve().as_uri())
            pg.emulate_media(media="print")
            pg.pdf(path=str(SORTIE / f"{nom}.pdf"), width="210mm", height="297mm", print_background=True)
        pg.emulate_media(media="screen")
        pg.set_viewport_size({"width": 1120, "height": 1120})
        pg.goto((DOCS / "visuel-carre.html").resolve().as_uri())
        pg.locator(".carre").screenshot(path=str(SORTIE / "qr-college-baker.png"))
        b.close()
    for f in sorted(SORTIE.iterdir()):
        print(f"{f.name:24} {f.stat().st_size // 1024} Ko")


if __name__ == "__main__":
    main()
