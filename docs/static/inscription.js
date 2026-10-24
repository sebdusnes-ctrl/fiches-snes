// Envoie le formulaire d'inscription au script Google sans quitter la page.
// La réponse est opaque (« no-cors ») : la confirmation arrive par courriel.
(function () {
  var f = document.getElementById('form-inscription');
  if (!f || !window.fetch) return;  // sans JavaScript, le formulaire s'envoie normalement
  var message = document.getElementById('inscription-message');
  f.addEventListener('submit', function (e) {
    e.preventDefault();
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
