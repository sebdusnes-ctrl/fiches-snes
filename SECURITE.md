# Sécurité et données personnelles

Audit du 25/10/2026. À relire à chaque ajout de fonction qui touche aux adresses ou aux droits d'écriture.

## Où sont les données

| Donnée | Où | Qui y accède |
|---|---|---|
| Adresses et statuts des inscrit·es | Feuille Google « Inscrits » (compte de la section) | La propriétaire du compte Google seulement |
| Suivi des envois d'HIS, clé secrète | Propriétés du script Google | La propriétaire seulement |
| Contenu du site (fiches, HIS, textes) | Dépôt GitHub **public** | Lecture : tout le monde. Écriture : la propriétaire du dépôt |
| `LISTE_URL`, `LISTE_CLE` | Secrets GitHub | Invisibles, y compris dans les journaux |

Les adresses ne quittent jamais Google : GitHub n'envoie au script que des HIS et des stages,
et le script ne renvoie qu'un compte rendu (« envoyé (annonce) »), sans adresse.

## Ce qui est en place

**Liste de diffusion (script Google)**
- Aucune route publique ne renvoie d'adresse : l'adresse publique ne sert qu'à s'inscrire,
  confirmer, se désinscrire (jeton aléatoire propre à chacun·e) et lire la version.
- Annonces d'HIS et alertes stages : uniquement avec la clé secrète `LISTE_CLE`.
- Les fonctions du menu (effectifs, envoi d'HIS, installation) refusent tout appel qui ne vient
  pas de la propriétaire, depuis la feuille (`reserve_()`).
- Inscriptions en rafale : un courriel de confirmation par adresse et par 24 h, 25 par jour au plus,
  100 inscriptions non confirmées au plus. Le quota Gmail reste disponible pour les HIS.
- Le formulaire répond toujours la même chose : impossible de savoir si une adresse est inscrite.
- Double opt-in, effacement des inscriptions non confirmées sous 7 jours, désinscription = effacement.
- Confirmation et désinscription par bouton (pas par simple lien, qu'un anti-virus ouvrirait seul).
- Adresses académiques refusées (`DOMAINES_REFUSES`).
- Envois individuels : personne ne voit les adresses des autres.

**Site et espace admin (GitHub)**
- Écrire dans le dépôt exige un jeton GitHub de la propriétaire : la page `/admin` est publique,
  mais inutilisable sans ce jeton.
- Le script du CMS est vérifié par empreinte (SRI, `INTEGRITE_CMS` dans `build.py`).
- Une fiche déjà en ligne ne peut pas disparaître par erreur : la publication échoue,
  sauf si son identifiant est dans `fiches_retirees` (`config.yaml`). Tout reste dans l'historique Git.
- Contenu échappé à la génération (pas de HTML injectable dans les fiches).
- Journaux GitHub (publics) : le nombre d'inscrit·es n'y figure pas.
- Les propositions de modification venant d'autres comptes (« pull requests ») ne déclenchent
  aucun workflow avec les secrets.

## À faire par la propriétaire (une fois)

1. **Double authentification** sur le compte GitHub (Settings → Password and authentication)
   et sur le compte Google de la section. C'est la protection principale de tout le système.
2. **Interdire la réécriture de l'historique** : dépôt → Settings → Rules → Rulesets → New branch ruleset,
   cible `main`, cocher **Restrict deletions** et **Block force pushes**, Enforcement : Active.
   (Ne pas cocher « Require a pull request » : l'espace admin écrit directement sur `main`.)
3. **Collaborateurs** : dépôt → Settings → Collaborators doit rester vide.
4. **Feuille Google** : bouton Partager → seule la propriétaire a accès.
5. **Jeton de l'admin** : expiration d'un an au plus ; sur un ordinateur partagé, se déconnecter
   de l'admin ; en cas de doute, le supprimer (Developer settings → Fine-grained tokens).

## Risques résiduels connus

- **Même adresse que le site `dhg`** : le navigateur range le jeton de l'admin pour tout
  `sebdusnes-ctrl.github.io`. Un script malveillant sur le site `dhg` pourrait le lire.
  Ne charger aucun script extérieur sur `dhg` (aujourd'hui : seulement son propre `script.js`).
- **Actions GitHub** référencées par version (`@v5`, `@v6`) et non par empreinte : risque très faible.
- **Quota Gmail** : une attaque déterminée peut encore consommer les 25 confirmations du jour ;
  les annonces d'HIS restent possibles (75 envois au moins).
