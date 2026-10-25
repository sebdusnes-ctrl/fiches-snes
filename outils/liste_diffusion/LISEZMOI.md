# Liste de diffusion de la section (HIS, stages)

Inscription facultative sur le site (`inscription.html`), liste tenue dans une feuille Google
du compte de la section, courriels envoyés depuis sa messagerie Gmail.

- **Inscription** : adresse + statut + accord ; un courriel de confirmation est envoyé
  (personne ne peut inscrire quelqu'un d'autre). Sans confirmation, effacement sous 7 jours.
- **HIS** : dans la feuille, menu **SNES → Annoncer une HIS…** (date, heure, lieu, ordre du jour,
  statuts visés, bouton « M'envoyer un test »).
- **Stages** : le relevé quotidien de GitHub envoie les nouveaux stages et les changements de
  date ou de lieu. Un stage AESH, AED ou CPE ne part qu'aux statuts concernés.
- **Désinscription** : lien dans chaque courriel, qui efface la ligne.

## Installation (une seule fois, dans le compte de la section)

1. Créer une feuille Google, par exemple « Liste SNES Baker ». **Ne la partager avec personne.**
2. Dans la feuille : **Extensions → Apps Script**.
   - Remplacer le contenu de `Code.gs` par celui de [Code.gs](Code.gs).
   - Ajouter un 2e fichier, la fenêtre « Annoncer une HIS » : dans la colonne de gauche, cliquer
     sur **+** à côté de « Fichiers », choisir **HTML**, taper le nom **HIS** (Google ajoute `.html`
     tout seul). Effacer les quelques lignes déjà présentes et coller tout le contenu de [HIS.html](HIS.html).
   - Enregistrer (Ctrl+S). À gauche, il doit y avoir deux fichiers : `Code.gs` et `HIS.html`.
3. Revenir à la feuille et la recharger : un menu **SNES** apparaît.
   **SNES → Installer (une seule fois)**, puis autoriser le script
   (« Google n'a pas validé cette application » → *Paramètres avancés* → *Accéder au projet*).
   Une fenêtre affiche la **clé secrète** : la copier.
4. Dans Apps Script : **Déployer → Nouveau déploiement → Application Web**.
   - Exécuter en tant que : **Moi**
   - Qui a accès : **Tout le monde**
   - Copier l'adresse qui se termine par `/exec`.
5. Dans `config.yaml`, coller cette adresse entre les guillemets de la ligne `url: ""`
   (sous `liste_diffusion:`), et enregistrer. Puis, dans un terminal, **lancer** (rien à modifier
   dans ce fichier) la commande `python build.py`, et publier : commit, `git pull --rebase`, push.
   Le formulaire apparaît sur le site.
6. Sur GitHub : **Settings → Secrets and variables → Actions → New repository secret** :
   - `LISTE_URL` : l'adresse `/exec`
   - `LISTE_CLE` : la clé secrète de l'étape 3
7. Tester : s'inscrire sur le site, confirmer, puis **SNES → Annoncer une HIS… → M'envoyer un test**.

## Modifier le script ensuite

Après avoir changé `Code.gs` : **Déployer → Gérer les déploiements → ✏️ → Version : Nouvelle version**.
L'adresse `/exec` ne change pas.

Les statuts sont listés deux fois, à garder identiques : `STATUTS` dans `Code.gs`
et `liste_diffusion.statuts` dans `config.yaml`.

## Limites

- Compte Gmail gratuit : environ **100 destinataires par jour**. Le script refuse un envoi qui dépasserait le quota.
- Les données (adresse, statut) restent dans la feuille : n'y donnez accès à personne d'autre.
