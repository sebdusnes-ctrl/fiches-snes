/**
 * Liste de diffusion de la section SNES-FSU du collège Joséphine Baker.
 *
 * Script lié à une feuille Google (onglet « Inscrits ») :
 *  - inscription depuis le site (doPost), avec confirmation par courriel (double opt-in) ;
 *  - confirmation et désinscription par lien (doGet) ;
 *  - menu « SNES » dans la feuille : annoncer une HIS aux statuts choisis ;
 *  - alertes « stages » envoyées par le relevé quotidien de GitHub (clé secrète) ;
 *  - HIS saisies dans l'espace admin du site : annonce et rappel deux jours avant (GitHub, clé secrète).
 * Installation : voir LISEZMOI.md dans ce dossier.
 */

const NOM_SECTION = 'SNES-FSU · collège Joséphine Baker';
const SITE = 'https://sebdusnes-ctrl.github.io/fiches-snes/';
const REPONDRE_A = 'sebdusnes@gmail.com';
// Doit rester identique à liste_diffusion.statuts dans config.yaml.
const STATUTS = [
  'Professeur·e titulaire',
  'Professeur·e contractuel·le',
  'CPE',
  'Psy-ÉN',
  'AED',
  'AESH',
  'Personnel administratif, social ou de santé',
  'Autre',
];
const ONGLET = 'Inscrits';
const ENTETES = ['courriel', 'statut', 'etat', 'jeton', 'statut_demande', 'inscrit_le', 'confirme_le'];
const JOURS_POUR_CONFIRMER = 7;
const JOURS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre'];


// --- Menu de la feuille ------------------------------------------------------

function onOpen() {
  SpreadsheetApp.getUi().createMenu('SNES')
    .addItem('Annoncer une HIS…', 'ouvrirHIS')
    .addItem('Inscrit·es par statut', 'afficherBilan')
    .addSeparator()
    .addItem('Installer (une seule fois)', 'installer')
    .addToUi();
}

/** Crée l'onglet, la clé secrète des alertes stages et le nettoyage quotidien. */
function installer() {
  feuille_();
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('CLE')) props.setProperty('CLE', Utilities.getUuid());
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'purgerNonConfirmes')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('purgerNonConfirmes').timeBased().everyDays(1).atHour(3).create();
  SpreadsheetApp.getUi().alert(
    'Installation terminée.\n\nClé secrète à copier dans GitHub (secret LISTE_CLE) :\n\n' + props.getProperty('CLE'));
}

function afficherBilan() {
  const n = effectifs();
  const lignes = STATUTS.map(s => s + ' : ' + (n[s] || 0));
  SpreadsheetApp.getUi().alert('Inscrit·es confirmé·es : ' + n.total + '\n\n' + lignes.join('\n'));
}

function ouvrirHIS() {
  const html = HtmlService.createHtmlOutputFromFile('HIS').setWidth(480).setHeight(640);
  SpreadsheetApp.getUi().showModalDialog(html, 'Annoncer une heure d’information syndicale');
}

/** Pour la fenêtre HIS : statuts et nombre d'inscrit·es confirmé·es. */
function effectifs() {
  const n = { total: 0 };
  lignes_().filter(l => l.etat === 'confirme').forEach(l => {
    n[l.statut] = (n[l.statut] || 0) + 1;
    n.total++;
  });
  n.statuts = STATUTS;
  return n;
}

/**
 * Envoie l'annonce d'une HIS. d = {date: 'aaaa-mm-jj', debut, fin, lieu, odj, statuts: [...], test}
 * Avec test = true, n'envoie qu'à vous-même.
 */
function envoyerHIS(d) {
  const m = messageHIS_(d, false);
  if (d.test) {
    const moi = Session.getEffectiveUser().getEmail();
    envoyer_([{ courriel: moi, jeton: 'test' }], '[TEST] ' + m.sujet, m.corps);
    return 1;
  }
  const cibles = destinatairesHIS_(d.statuts);
  envoyer_(cibles, m.sujet, m.corps);
  return cibles.length;
}

/** Inscrit·es confirmé·es des statuts visés (liste vide : tout le monde). */
function destinatairesHIS_(statuts) {
  const tous = !statuts || !statuts.length;
  return lignes_().filter(l => l.etat === 'confirme' && (tous || statuts.indexOf(l.statut) >= 0));
}

function messageHIS_(d, rappel) {
  const jour = new Date(d.date + 'T12:00:00');
  const quand = JOURS[jour.getDay()] + ' ' + jour.getDate() + ' ' + MOIS[jour.getMonth()];
  const horaire = d.debut + (d.fin ? '-' + d.fin : '');
  const sujet = (rappel ? 'Rappel : prévenez la direction aujourd’hui · ' : '') +
    'Heure d’information syndicale le ' + quand + ', ' + horaire;
  // Rappel envoyé deux jours avant : c'est le dernier moment pour respecter les 48 h de prévenance.
  const corps =
    (rappel ? '<p style="padding:10px 12px;border-left:4px solid #ed0f4c;background:#fdeef2">' +
      '<strong>Rappel : l’HIS a lieu dans deux jours.</strong> Si vous avez cours sur ce créneau, ' +
      '<strong>prévenez la direction aujourd’hui</strong> pour respecter le délai de 48 h ' +
      '(un simple courriel suffit, sans avoir à donner l’ordre du jour).</p>' : '') +
    '<p>La section SNES-FSU organise une <strong>heure d’information syndicale</strong> :</p>' +
    '<p style="font-size:1.1em"><strong>' + echapper_(quand + ', ' + horaire) + '</strong>' +
    (d.lieu ? '<br>' + echapper_(d.lieu) : '') + '</p>' +
    (d.odj ? '<p><strong>Ordre du jour</strong><br>' + echapper_(d.odj).replace(/\n/g, '<br>') + '</p>' : '') +
    '<p>Chaque agent, titulaire ou non, a droit à une heure par mois sur son temps de service, ' +
    'syndiqué·e ou non. <strong>Enseignant·es</strong> : si vous avez cours, prévenez la direction ' +
    '<strong>au moins 48 h avant</strong> (un courriel suffit) et vos élèves. ' +
    '<strong>AED, AESH</strong> : prévenez le ou la CPE.</p>' +
    '<p><a href="' + SITE + 'fiches/heure-information-syndicale.html">Vos droits : la fiche HIS</a></p>';
  return { sujet: sujet, corps: corps };
}


// --- Site : inscription, confirmation, désinscription -----------------------

function doPost(e) {
  const p = (e && e.parameter) || {};
  if (p.action === 'stages') return alertesStages_(p);
  if (p.action === 'his_annonce' || p.action === 'his_rappel') return hisAutomatique_(p);
  if (p.action === 'confirmer') return confirmer_(p.j);
  if (p.action === 'desinscrire') return desinscrire_(p.j);
  return inscrire_(p);
}

/**
 * Les liens des courriels mènent à une page avec un bouton : les anti-virus de messagerie
 * ouvrent souvent les liens d'eux-mêmes, ils ne doivent ni confirmer ni désinscrire à votre place.
 */
function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.a === 'confirmer') return bouton_('Confirmer votre inscription', 'confirmer', p.j, 'Confirmer mon inscription');
  if (p.a === 'desinscrire') return bouton_('Se désinscrire', 'desinscrire', p.j, 'Me désinscrire');
  return page_('Liste de diffusion', '<p>Rien à faire ici.</p>');
}

function bouton_(titre, action, jeton, libelle) {
  return page_(titre,
    '<form method="post" action="' + ScriptApp.getService().getUrl() + '" target="_top">' +
    '<input type="hidden" name="action" value="' + action + '">' +
    '<input type="hidden" name="j" value="' + echapper_(jeton || '') + '">' +
    '<button type="submit" style="font-size:1em;padding:10px 18px;border:0;border-radius:8px;background:#3067b7;color:#fff;cursor:pointer">' +
    libelle + '</button></form>');
}

function inscrire_(p) {
  if (p.site) return page_('Merci', '<p>Merci.</p>');  // pot de miel rempli : robot
  const courriel = String(p.courriel || '').trim().toLowerCase();
  const statut = String(p.statut || '');
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(courriel) || STATUTS.indexOf(statut) < 0 || p.consentement !== 'oui') {
    return page_('Inscription incomplète',
      '<p>Adresse, statut et accord sont nécessaires. <a href="' + SITE + 'inscription.html">Revenir au formulaire</a>.</p>');
  }
  const verrou = LockService.getScriptLock();
  verrou.waitLock(10000);
  let jeton;
  try {
    const sh = feuille_();
    const l = lignes_().find(x => x.courriel === courriel);
    if (l) {
      jeton = l.jeton;
      sh.getRange(l.ligne, ENTETES.indexOf('statut_demande') + 1).setValue(statut);
    } else {
      jeton = Utilities.getUuid();
      sh.appendRow([courriel, '', 'en_attente', jeton, statut, new Date(), '']);
    }
  } finally {
    verrou.releaseLock();
  }
  const lien = ScriptApp.getService().getUrl() + '?a=confirmer&j=' + jeton;
  MailApp.sendEmail({
    to: courriel,
    subject: 'Confirmez votre inscription à la liste de la section SNES-FSU',
    name: NOM_SECTION,
    replyTo: REPONDRE_A,
    htmlBody: '<p>Bonjour,</p><p>Vous avez demandé à recevoir les informations de la section SNES-FSU ' +
      'du collège Joséphine Baker (HIS, stages syndicaux), en tant que <strong>' + echapper_(statut) + '</strong>.</p>' +
      '<p><a href="' + lien + '" style="font-weight:bold">Confirmer mon inscription</a></p>' +
      '<p>Si vous n’êtes pas à l’origine de cette demande, ignorez ce message : sans confirmation, ' +
      'votre adresse est effacée sous ' + JOURS_POUR_CONFIRMER + ' jours.</p>',
  });
  return page_('Presque fini',
    '<p>Un courriel de confirmation vient de partir : cliquez sur le lien qu’il contient ' +
    '(pensez à regarder dans les indésirables).</p><p><a href="' + SITE + '">Retour au site</a></p>');
}

function confirmer_(jeton) {
  const l = jeton && lignes_().find(x => x.jeton === jeton);
  if (!l) return page_('Lien expiré', '<p>Ce lien n’est plus valable. <a href="' + SITE + 'inscription.html">Recommencer l’inscription</a>.</p>');
  const sh = feuille_();
  const statut = l.statut_demande || l.statut;
  sh.getRange(l.ligne, 1, 1, ENTETES.length).setValues([[
    l.courriel, statut, 'confirme', l.jeton, '', l.inscrit_le, new Date()]]);
  return page_('Inscription confirmée',
    '<p>C’est fait : vous recevrez les informations de la section (' + echapper_(statut) + ').</p>' +
    '<p>Chaque courriel contient un lien pour vous désinscrire.</p><p><a href="' + SITE + '">Retour au site</a></p>');
}

function desinscrire_(jeton) {
  const l = jeton && lignes_().find(x => x.jeton === jeton);
  if (l) feuille_().deleteRow(l.ligne);
  return page_('Désinscription', '<p>Votre adresse a été effacée de la liste. Vous ne recevrez plus de courriel de la section.</p>' +
    '<p><a href="' + SITE + '">Retour au site</a></p>');
}

/** Déclencheur quotidien : efface les inscriptions jamais confirmées. */
function purgerNonConfirmes() {
  const limite = Date.now() - JOURS_POUR_CONFIRMER * 86400000;
  const sh = feuille_();
  lignes_().filter(l => l.etat !== 'confirme' && new Date(l.inscrit_le).getTime() < limite)
    .reverse()  // du bas vers le haut, pour ne pas décaler les lignes restantes
    .forEach(l => sh.deleteRow(l.ligne));
}


// --- HIS saisies dans l'espace admin du site (appelé par GitHub) ------------

/**
 * p.donnees : {date, debut, fin, lieu, odj, statuts}. Chaque HIS n'est annoncée qu'une fois,
 * et rappelée qu'une fois, deux jours avant, pour le délai de prévenance de 48 h
 * (pas de rappel si l'annonce est partie il y a moins de 24 h).
 */
function hisAutomatique_(p) {
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('CLE') || p.cle !== props.getProperty('CLE')) return ContentService.createTextOutput('refusé');
  const d = JSON.parse(p.donnees || '{}');
  if (!d.date || !d.debut) return ContentService.createTextOutput('incomplet');
  const id = d.date + ' ' + d.debut;
  const rappel = p.action === 'his_rappel';
  const marque = (rappel ? 'RAPPEL ' : 'ANNONCE ') + id;
  if (props.getProperty(marque)) return ContentService.createTextOutput('déjà envoyé');
  if (rappel) {
    const annonce = Number(props.getProperty('ANNONCE ' + id) || 0);
    if (Date.now() - annonce < 24 * 3600 * 1000) {
      props.setProperty(marque, String(Date.now()));
      return ContentService.createTextOutput('annonce récente, pas de rappel');
    }
  }
  const verrou = LockService.getScriptLock();
  verrou.waitLock(30000);
  try {
    if (props.getProperty(marque)) return ContentService.createTextOutput('déjà envoyé');
    const m = messageHIS_(d, rappel);
    const cibles = destinatairesHIS_(d.statuts);
    envoyer_(cibles, m.sujet, m.corps);
    props.setProperty(marque, String(Date.now()));
    return ContentService.createTextOutput('envoyé à ' + cibles.length);
  } finally {
    verrou.releaseLock();
  }
}


// --- Alertes stages (appelées par GitHub) ------------------------------------

/**
 * p.donnees : liste JSON de {type, titre, date_fr, lieu, limite_fr, programme, changement}
 * envoyée par outils/alertes.py. Chaque inscrit·e reçoit un seul courriel avec ce qui le ou la concerne.
 */
function alertesStages_(p) {
  const cle = PropertiesService.getScriptProperties().getProperty('CLE');
  if (!cle || p.cle !== cle) return ContentService.createTextOutput('refusé');
  const items = JSON.parse(p.donnees || '[]');
  if (!items.length) return ContentService.createTextOutput('rien');
  let envois = 0;
  lignes_().filter(l => l.etat === 'confirme').forEach(l => {
    const siens = items.filter(it => concerne_(it.titre, l.statut));
    if (!siens.length) return;
    const blocs = siens.map(it =>
      '<li><strong>' + echapper_(it.titre) + '</strong> — ' +
      (it.type === 'nouveau' ? 'nouveau stage' : echapper_(it.changement)) + '<br>' +
      echapper_(it.date_fr || 'date à préciser') + (it.lieu ? ' · ' + echapper_(it.lieu) : '') +
      (it.limite_fr ? '<br>Demande d’absence avant le ' + echapper_(it.limite_fr) : '') +
      (it.programme ? '<br><a href="' + it.programme + '">Programme</a>' : '') + '</li>').join('');
    envoyer_([l], 'Stages syndicaux : ' + (siens.length > 1 ? siens.length + ' nouveautés' : 'du nouveau'),
      '<p>Du nouveau dans les stages du SNES-FSU Lille :</p><ul>' + blocs + '</ul>' +
      '<p><a href="' + SITE + 'stages.html">Calendrier complet et disponibilités</a></p>' +
      '<p>Rappel : 12 jours de formation syndicale par an, adhérent·e ou non, demande d’absence au moins un mois avant.</p>');
    envois++;
  });
  return ContentService.createTextOutput('envoyé à ' + envois);
}

/** Stages réservés à un public (titre) : seul·es les statuts concernés sont prévenu·es. */
function concerne_(titre, statut) {
  const t = String(titre).toUpperCase();
  if (/\bAESH\b/.test(t)) return statut === 'AESH';
  if (/\bAED\b/.test(t)) return statut === 'AED';
  if (/\bCPE\b/.test(t)) return statut === 'CPE';
  if (/NON[- ]TITULAIRES?/.test(t)) return ['Professeur·e contractuel·le', 'AED', 'AESH'].indexOf(statut) >= 0;
  if (/\bTZR\b/.test(t)) return statut.indexOf('Professeur') === 0;
  return true;
}


// --- Outils --------------------------------------------------------------------

function envoyer_(destinataires, sujet, corps) {
  if (destinataires.length > MailApp.getRemainingDailyQuota()) {
    throw new Error('Quota quotidien d’envoi insuffisant (' + MailApp.getRemainingDailyQuota() + ' restants).');
  }
  const url = ScriptApp.getService().getUrl();
  destinataires.forEach(d => {
    const lien = url + '?a=desinscrire&j=' + d.jeton;
    const html = corps +
      '<hr style="border:0;border-top:1px solid #ccc;margin:24px 0 8px">' +
      '<p style="font-size:12px;color:#666">' + NOM_SECTION + ' · <a href="' + SITE + '">Fiches pratiques</a><br>' +
      'Vous recevez ce courriel car vous vous êtes inscrit·e sur le site de la section. ' +
      '<a href="' + lien + '">Se désinscrire</a></p>';
    MailApp.sendEmail({ to: d.courriel, subject: sujet, htmlBody: html, name: NOM_SECTION, replyTo: REPONDRE_A });
  });
}

function feuille_() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(ONGLET);
  if (!sh) sh = ss.insertSheet(ONGLET);
  if (sh.getLastRow() === 0) {
    sh.appendRow(ENTETES);
    sh.setFrozenRows(1);
  }
  return sh;
}

function lignes_() {
  const v = feuille_().getDataRange().getValues();
  return v.slice(1).map((r, i) => {
    const o = { ligne: i + 2 };
    ENTETES.forEach((c, j) => { o[c] = r[j]; });
    o.courriel = String(o.courriel).toLowerCase();
    return o;
  });
}

function page_(titre, corps) {
  return HtmlService.createHtmlOutput(
    '<meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<div style="font-family:system-ui,sans-serif;max-width:560px;margin:40px auto;padding:0 16px;line-height:1.5">' +
    '<p style="color:#3067b7;font-weight:bold">' + NOM_SECTION + '</p><h1 style="font-size:1.4em">' + titre + '</h1>' +
    corps + '</div>').setTitle(titre);
}

function echapper_(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
