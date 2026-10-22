// Filtre les fiches de l'accueil au fil de la frappe (sans accents ni casse).
(function () {
  var champ = document.getElementById("recherche");
  var aucun = document.getElementById("aucun");
  if (!champ) return;
  var normaliser = function (s) {
    return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  };
  var cartes = Array.prototype.slice.call(document.querySelectorAll(".carte"));
  cartes.forEach(function (c) { c._texte = normaliser(c.dataset.texte || ""); });

  champ.addEventListener("input", function () {
    var mots = normaliser(champ.value).split(/\s+/).filter(Boolean);
    var total = 0;
    document.querySelectorAll(".theme").forEach(function (theme) {
      var visibles = 0;
      theme.querySelectorAll(".carte").forEach(function (c) {
        var ok = mots.every(function (m) { return c._texte.indexOf(m) !== -1; });
        c.hidden = !ok;
        if (ok) visibles++;
      });
      theme.hidden = visibles === 0;
      total += visibles;
    });
    aucun.hidden = total !== 0;
  });
})();
