"""Récupère le texte de pages officielles via Chrome visible : python recup.py nom=URL [nom=URL ...]
(education.gouv.fr et Légifrance bloquent les navigateurs sans fenêtre.)"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ICI = Path(__file__).resolve().parent.parent / "sources" / "officiels"


async def main(paires):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=False,
                                    args=["--disable-blink-features=AutomationControlled"])
        pg = await b.new_page(locale="fr-FR")
        for nom, url in paires:
            try:
                r = await pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                await pg.wait_for_timeout(5000)
                txt = await pg.inner_text("body")
                (ICI / f"{nom}.txt").write_text(f"SOURCE: {url}\n\n{txt}", encoding="utf-8")
                print(nom, r.status if r else "?", len(txt))
            except Exception as e:
                print(nom, "ERREUR", e)
        await b.close()


asyncio.run(main([a.split("=", 1) for a in sys.argv[1:]]))
