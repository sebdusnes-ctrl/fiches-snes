// Compteur anonyme : ni cookie ni identifiant. Une visite par session de navigation, une
// consultation par fiche et par session (mémorisées dans sessionStorage, effacé à la fermeture).
// Ne pas compter ce navigateur : ouvrir une page avec ?nostat=1 (?nostat=0 pour annuler).
(function () {
  var script = document.currentScript;
  var url = script && script.dataset.url;
  if (!url || !window.fetch) return;

  function lire(stockage, cle) { try { return stockage.getItem(cle); } catch (e) { return null; } }
  function ecrire(stockage, cle, val) { try { stockage.setItem(cle, val); return true; } catch (e) { return false; } }

  function afficher() {
    var el = document.getElementById('compteur');
    if (!el) return;
    fetch(url + '?a=stats', { credentials: 'omit', referrerPolicy: 'no-referrer' })
      .then(function (r) { return r.json(); })
      .then(function (s) {
        if (typeof s.visites !== 'number' || typeof s.fiches !== 'number') return;
        el.textContent = s.visites.toLocaleString('fr-FR') + ' visites · ' +
          s.fiches.toLocaleString('fr-FR') + ' fiches consultées · mesure anonyme, sans cookie';
        el.hidden = false;
      })
      .catch(function () {});  // script pas encore à jour ou injoignable : pas de compteur
  }

  function compter() {
    var stockageLocal = null, stockageSession = null;
    try { stockageLocal = localStorage; stockageSession = sessionStorage; } catch (e) { return; }
    var demande = new URLSearchParams(location.search).get('nostat');
    if (demande === '1') ecrire(stockageLocal, 'nostat', '1');
    if (demande === '0') { try { stockageLocal.removeItem('nostat'); } catch (e) {} }
    if (lire(stockageLocal, 'nostat') === '1') return;
    if (navigator.webdriver || !/^https?:$/.test(location.protocol)) return;

    var parametres = new URLSearchParams({ a: 'vue' });
    var fiche = script.dataset.fiche;
    // Sans sessionStorage, on ne compte pas : chaque page ferait sinon une nouvelle visite.
    if (lire(stockageSession, 'vu') === null) {
      if (!ecrire(stockageSession, 'vu', '1')) return;
      parametres.set('v', '1');
    }
    if (fiche && lire(stockageSession, 'vu:' + fiche) === null) {
      ecrire(stockageSession, 'vu:' + fiche, '1');
      parametres.set('f', fiche);
    }
    if (!parametres.has('v') && !parametres.has('f')) return;
    fetch(url + '?' + parametres, { mode: 'no-cors', credentials: 'omit', keepalive: true, referrerPolicy: 'no-referrer' })
      .catch(function () {});
  }

  compter();
  afficher();
})();
