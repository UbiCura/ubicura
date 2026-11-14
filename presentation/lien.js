// Règle unique « lien » ou « pas de lien » (pipeline/regle_lien.py, mêmes valeurs, vérifiées par un test).
var Lien = { SEUIL_RHO: 0.3, ALPHA: 0.05,
  est: function (rho, q) { return rho != null && q != null && isFinite(rho) && isFinite(q) && q < this.ALPHA && Math.abs(rho) >= this.SEUIL_RHO; } };
