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

Mise en forme possible dans les textes : `**gras**`, `[texte du lien](https://…)` et, pour renvoyer vers une autre fiche, `[texte](fiche:identifiant-de-la-fiche)` (le générateur refuse un lien vers une fiche qui n'existe pas).
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

## Stages syndicaux (`stages.html`, mis à jour chaque jour)

`python outils/stages.py` relève le tableau d'inscription du SNES-FSU (liste complète, clôture des inscriptions)
et la page des stages du SNES-FSU Lille (programmes, reports)
(`PAGE` dans le script : **à changer à chaque rentrée**, ex. `Stages-SNES-FSU-2027-2028.html`)
et écrit `contenu/stages.json` : date, lieu, horaires, ancienne date ou ancien lieu barrés,
et un journal des changements (stage ajouté ou retiré, date reportée, lieu ou horaires modifiés).
`build.py` en tire `docs/stages.html` : la disponibilité de chaque stage est calculée le jour
de la construction (demande d'absence au plus tard un mois avant, CGFP art. R.215-3).

Le workflow `.github/workflows/stages.yml` fait tout cela chaque matin sur GitHub et publie
le résultat (bouton « Run workflow » dans l'onglet Actions pour le lancer à la main).
Si la page du SNES-FSU Lille est injoignable ou a changé de forme, le site est quand même
reconstruit, puis le workflow échoue : GitHub envoie un courriel d'alerte.

Le robot faisant des commits, **toujours `git pull --rebase` avant de pousser** ses propres modifications.

## Liste de diffusion (HIS, stages)

Page `inscription.html` (facultative), feuille Google et envois Gmail : installation et usage dans
[outils/liste_diffusion/LISEZMOI.md](outils/liste_diffusion/LISEZMOI.md). Le relevé quotidien
appelle `outils/alertes.py` (secrets GitHub `LISTE_URL` et `LISTE_CLE`) pour prévenir les inscrit·es
des nouveaux stages et des changements de date ou de lieu.

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

## Espace admin (`/admin`)

https://sebdusnes-ctrl.github.io/fiches-snes/admin/ : formulaires pour modifier ou ajouter des fiches,
et saisir les HIS (Sveltia CMS, version figée dans `build.py`, `VERSION_CMS`). Navigateur récent requis.
La configuration (`docs/admin/config.yml`) est générée par `build.py` à partir des thèmes et des sources.

**Connexion** : « Se connecter avec un jeton d'accès ». Créer le jeton une fois sur GitHub :
Settings (du compte) → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token :
- Repository access : **Only select repositories** → `fiches-snes`
- Permissions → Repository permissions → **Contents : Read and write**
- Expiration : au choix (un an, par exemple), puis le recréer.

Ce jeton ne donne accès qu'à ce dépôt. Ne le communiquer à personne.

**Après chaque enregistrement**, le workflow « Publication » reconstruit et publie le site (1 à 2 minutes),
puis annonce les nouvelles HIS. Une fiche invalide (champ obligatoire vide, identifiant en double, lien
vers une fiche inexistante) fait échouer la publication : GitHub envoie un courriel et le site reste tel quel.
Après une modification depuis l'admin, vérifiez que la fiche tient toujours sur une page A4 (aperçu avant impression).

**HIS** : une HIS enregistrée s'affiche sur l'accueil jusqu'à son jour ; si « Envoyer l'annonce » est coché,
l'annonce part aussitôt (une seule fois), et un rappel deux jours avant au matin (relevé quotidien), qui rappelle de prévenir la direction 48 h avant.
Changer la date, l'horaire ou le lieu d'une HIS déjà annoncée envoie un courriel « HIS modifiée » (l'ancienne version barrée). Pour annuler : état « Annulée » (ne pas supprimer l'HIS) → courriel d'annulation, HIS barrée sur l'accueil pendant 7 jours après l'annulation (au plus jusqu'à sa date). Les HIS passées sont retirées de l'admin 30 jours après leur date (`outils/his_entretien.py`, réglages `his:` dans `config.yaml`). Un changement de l'ordre du jour seul n'envoie rien.
