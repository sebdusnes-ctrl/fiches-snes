"""Construit sources/ : le texte de chaque PDF des Mémos, une page par bloc.

Usage : python outils/corpus.py "E:/Ressources Collège/SNES/Mémos_SNES" [dossier_retranscriptions]
- PDF numériques : texte extrait directement (PyMuPDF).
- PDF scannés : OCR Tesseract (fra), avec redressement automatique des pages tournées.
- Retranscriptions relues (HTML pNN) : prioritaires sur l'OCR pour les pages concernées.
sources/ n'est pas versionné (textes intégraux des publications).
"""
import html
import io
import re
import sys
from pathlib import Path

import fitz

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "sources"
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def est_scanne(doc):
    return all(len(p.get_images()) >= 1 for p in doc) and \
        "scan" in ((doc.metadata.get("producer") or "") + (doc.metadata.get("creator") or "")).lower()


def ocr_page(page):
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = TESSERACT
    img = Image.open(io.BytesIO(page.get_pixmap(dpi=300).tobytes("png")))
    try:
        rot = pytesseract.image_to_osd(img, config="--psm 0").split("Rotate:")[1].split()[0]
        if rot != "0":
            img = img.rotate(-int(rot), expand=True)
    except Exception:
        pass
    return pytesseract.image_to_string(img, lang="fra", config="--psm 3")


def html_vers_texte(fragment):
    t = re.sub(r"<(h2|h3)[^>]*>", "\n## ", fragment)
    t = re.sub(r"<li[^>]*>", "\n- ", t)
    t = re.sub(r"</(p|h2|h3|li|dt|dd|blockquote|tr)>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(t)).strip()


def relus(dossier):
    """{page: texte} à partir des sections <section data-pages="N"> retranscrites."""
    pages = {}
    if not dossier:
        return pages
    for f in sorted(Path(dossier).glob("*.html")):
        for m in re.finditer(r'<section[^>]*data-pages="(\d+)"[^>]*>(.*?)</section>', f.read_text(encoding="utf-8"), re.S):
            pages[int(m.group(1))] = html_vers_texte(m.group(2))
    return pages


def main(dossier_pdf, dossier_relus=None):
    SORTIE.mkdir(exist_ok=True)
    index = []
    for pdf in sorted(Path(dossier_pdf).glob("*.pdf")):
        doc = fitz.open(pdf)
        scanne = est_scanne(doc)
        relu = relus(dossier_relus) if scanne else {}
        morceaux = []
        for i, page in enumerate(doc, 1):
            if i in relu:
                texte, origine = relu[i], "relu"
            elif scanne:
                texte, origine = ocr_page(page), "ocr"
            else:
                texte, origine = page.get_text(sort=True), "texte"
            morceaux.append(f"=== {pdf.name} — page {i} ({origine})\n{texte.strip()}\n")
            print(f"{pdf.name} p{i} {origine}", flush=True)
        (SORTIE / (pdf.stem + ".txt")).write_text("\n".join(morceaux), encoding="utf-8")
        index.append(f"{pdf.stem}.txt\t{doc.page_count} p.\t{'scanné' if scanne else 'numérique'}")
    (SORTIE / "INDEX.txt").write_text("\n".join(index) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
