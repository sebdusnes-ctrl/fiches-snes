// Bouton « Partager » : partage natif sur téléphone, sinon copie du lien.
(function () {
  var bouton = document.getElementById("partager");
  if (!bouton) return;
  bouton.hidden = false;
  bouton.addEventListener("click", function () {
    var donnees = { title: document.title, url: location.href };
    if (navigator.share) {
      navigator.share(donnees).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(location.href).then(function () {
        bouton.textContent = "Lien copié";
        setTimeout(function () { bouton.textContent = "Partager"; }, 2000);
      });
    }
  });
})();
