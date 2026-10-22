# Fiches pratiques SNES-FSU (site de la section)

Site statique mobile, accessible par QR code, généré à partir des Mémos du SNES-FSU
(`E:\Ressources Collège\SNES\Mémos_SNES`).

## Organisation

| Élément | Rôle |
|---|---|
| `config.yaml` | Nom de la section, contacts, adresse du site (`url_site`, pour les QR codes), sources |
| `contenu/NN_theme.yaml` | Un fichier par thème : en-tête `theme` + liste de `fiches` |
| `modeles/` | Gabarits HTML (Jinja2) : accueil, fiche, affiche, contact |
| `static/` | Feuille de style (écran + impression A4) et petits scripts (recherche, partage) |
| `build.py` | Génère le site dans `docs/` |
| `docs/` | Site généré, **ne pas modifier à la main** (servi par GitHub Pages) |

## Modifier ou ajouter une fiche

Dans le fichier du thème, chaque fiche a la forme :

```yaml
  - id: identifiant-unique          # devient fiches/identifiant-unique.html (ne plus le changer après impression des QR)
    titre: "Titre de la fiche"
    resume: "Une ligne affichée sur l’accueil."
    a_jour: "Avertissement facultatif (texte daté…)"
    en_bref: ["…", "…"]             # obligatoire
    textes: ["…"]                   # Ce que disent les textes
    agir: ["…"]                     # Ce que vous pouvez faire
    snes: "Position du SNES-FSU (facultatif)"
    liens:
      - { libelle: "…", url: "https://…" }
    source: { doc: abecedaire, pages: "12" }   # ou une liste de sources
```

Mise en forme possible dans les textes : `**gras**` et `[texte du lien](https://…)`.
Toujours mettre les textes entre guillemets droits `"…"` (le « : » français casse sinon le YAML).

Puis : `python build.py` (contrôle les champs obligatoires et les identifiants en double).

## Publier sur GitHub Pages

1. Créer un dépôt public sur github.com (ex. `fiches-snes`).
2. Renseigner `url_site: "https://<compte>.github.io/fiches-snes/"` dans `config.yaml`, puis `python build.py`.
3. `git add -A && git commit -m "…" && git push` vers ce dépôt.
4. Sur GitHub : Settings → Pages → Source « Deploy from a branch », branche `main`, dossier `/docs`.

Après chaque modification : `python build.py`, commit, push. L’adresse ne change pas, les QR déjà imprimés restent valables.

## QR codes

- `docs/affiche.html` : affiche A4 (QR vers l’accueil) à imprimer depuis le navigateur.
- `docs/qr/accueil.png` et `docs/qr/<id>.png` : QR en image (pour un document, un mail…).
- Chaque fiche imprimée porte son propre QR code en pied de page.

## Corpus des sources (pour rédiger les fiches)

`python outils/corpus.py "E:/Ressources Collège/SNES/Mémos_SNES"` écrit dans `sources/`
le texte de chaque PDF du dossier des Mémos (une page par bloc, origine indiquée) :
texte direct pour les PDF numériques, OCR Tesseract (fra, pages tournées redressées) pour les scans.
Un 2e argument facultatif pointe vers des retranscriptions relues (`<section data-pages="N">`),
prioritaires sur l'OCR. `sources/` est **exclu de git** : ce sont les textes intégraux des publications.
L'OCR peut mélanger les encadrés pleine largeur : vérifier chiffres et dates sur le PDF.

## Points de vigilance

- Le Mémo TZR date de 2024-2025 : les montants d’ISSR sont à vérifier chaque année.
- Ne pas publier de nom ni d’adresse personnelle sans l’accord des intéressé·es (champ `contact`).
