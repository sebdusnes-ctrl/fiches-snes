"""Cherche un texte (décret, arrêté) sur Légifrance et enregistre sa version en vigueur.
Usage : python outils/recup_loda.py nom="Décret n° 2003-484 du 6 juin 2003" [nom="..." ...]
(Chrome visible : Légifrance bloque les navigateurs sans fenêtre.)"""
import asyncio
import re
import sys
import urllib.parse
from pathlib import Path

from playwright.async_api import async_playwright

ICI = Path(__file__).resolve().parent.parent / "sources" / "officiels"


async def main(paires):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=False,
                                    args=["--disable-blink-features=AutomationControlled"])
        pg = await b.new_page(locale="fr-FR")
        for nom, titre in paires:
            q = urllib.parse.quote(f'"{titre}"')
            await pg.goto(f"https://www.legifrance.gouv.fr/search/lois?query={q}&searchField=TITLE",
                          wait_until="domcontentloaded", timeout=60000)
            await pg.wait_for_timeout(5000)
            liens = await pg.eval_on_selector_all(
                "a[href*='/loda/id/']", "es => es.map(e => [e.href, e.innerText.trim()])")
            norm = lambda s: re.sub(r"\s+", "", s).lower()
            liens = [l for l in liens if norm(l[1]).startswith(norm(titre.split(" du ")[0]))]
            if not liens:
                print(nom, "aucun résultat")
                continue
            url, libelle = liens[0]
            await pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            await pg.wait_for_timeout(5000)
            txt = await pg.inner_text("body")
            (ICI / f"{nom}.txt").write_text(f"SOURCE: {url}\nTITRE: {libelle}\n\n{txt}", encoding="utf-8")
            print(nom, url, len(txt), "|", libelle[:90])
        await b.close()


asyncio.run(main([a.split("=", 1) for a in sys.argv[1:]]))
