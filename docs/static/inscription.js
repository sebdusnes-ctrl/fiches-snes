// Envoie le formulaire d'inscription au script Google sans quitter la page.
// La réponse est opaque (« no-cors ») : la confirmation arrive par courriel.
(function () {
  var f = document.getElementById('form-inscription');
  if (!f || !window.fetch) return;  // sans JavaScript, le formulaire s'envoie normalement
  var message = document.getElementById('inscription-message');
  // Adresses institutionnelles refusées : message de la consigne affiché sur le champ.
  var champ = document.getElementById('courriel');
  var refuses = (champ.dataset.domainesRefuses || '').split(',').filter(Boolean);
  var consigne = document.getElementById('consigne-adresse');
  function verifierAdresse() {
    var domaine = champ.value.trim().toLowerCase().split('@')[1] || '';
    var refuse = refuses.some(function (d) { return domaine === d || domaine.slice(-d.length - 1) === '.' + d; });
    champ.setCustomValidity(refuse ? (consigne ? consigne.textContent : 'Adresse personnelle uniquement.') : '');
    if (consigne) consigne.classList.toggle('consigne-erreur', refuse);
  }
  champ.addEventListener('input', verifierAdresse);
  f.addEventListener('submit', function (e) {
    e.preventDefault();
    verifierAdresse();
    if (!champ.checkValidity()) { champ.reportValidity(); return; }
    var bouton = f.querySelector('button');
    bouton.disabled = true;
    message.textContent = 'Envoi…';
    fetch(f.action, { method: 'POST', mode: 'no-cors', body: new URLSearchParams(new FormData(f)) })
      .then(function () {
        message.textContent = 'Merci ! Un courriel de confirmation vient de partir : cliquez sur le bouton qu’il contient (pensez à regarder dans les indésirables).';
        f.reset();
      })
      .catch(function () {
        message.textContent = 'Envoi impossible pour le moment. Réessayez plus tard, ou écrivez à la section.';
      })
      .finally(function () { bouton.disabled = false; });
  });
})();
