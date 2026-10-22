"""Affiche le texte d'articles : python art.py [ce|cgfp] R421-51 D511-41 L912-1-1 ..."""
import re
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent.parent / "sources" / "officiels"
code = {"ce": "code_education.txt", "cgfp": "cgfp.txt"}[sys.argv[1]]
t = (ICI / code).read_text(encoding="utf-8")
# En-tête d'article : « R. 421-51  Décret n°… » (ou « L. 912-1-1 », « D. 511-41 », « R*. … »)
ENTETE = re.compile(r"^([LRD])\*?\. ?(\d+(?:-\d+)+)\b(?=\s)", re.M)
debuts = [(m.start(), m.group(1) + m.group(2)) for m in ENTETE.finditer(t)]
BRUIT = {"Legif.", "Plan", "Jp.Judi.", "Jp.Admin.", "Juricaf", ""}
for num in sys.argv[2:]:
    hits = [i for i, (_, n) in enumerate(debuts) if n == num]
    if not hits:
        print(f"===== {num} : introuvable\n")
    for i in hits:
        pos = debuts[i][0]
        fin = debuts[i + 1][0] if i + 1 < len(debuts) else len(t)
        lignes = [l for l in t[pos:fin].splitlines() if l.strip() not in BRUIT]
        print("===== " + "\n".join(lignes).strip() + "\n")
