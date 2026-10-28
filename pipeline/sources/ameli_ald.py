"""Assurance Maladie, bénéficiaires du dispositif des affections de longue durée (ALD), par département
(Licence Ouverte).

Le jeu data.gouv (config.ALD_DATAGOUV) publie chaque année un classeur par département, tableau VII (effectifs arrondis
à la dizaine, « <10 » sous le seuil) et tableau VIII (taux standardisé sur l'âge pour 100 000 personnes protégées du
régime général), pour les 30 affections de la liste. Le classeur le plus récent est choisi par son titre. Les 30
affections sont gardées dans la table, seules celles de config.ALD_INDICATEURS deviennent des indicateurs de contexte.
Une ALD mesure une maladie reconnue et le recours aux soins, pas le besoin (voir config.LIMITES["ald"])."""
from __future__ import annotations

import re

import pandas as pd

from .. import config
from ..lecture import nombre
from ..util import JOURNAL, choisir_ressource, lire_meta, norm, ressources_datagouv, telecharger

SOURCE = "Assurance Maladie, affections de longue durée"
DEST = config.BRUT / "ald_departements.xls"
PAGE = "https://www.data.gouv.fr/datasets/beneficiaires-du-dispositif-des-affections-de-longue-duree-ald"


def _tableau(feuille: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par département et par affection, à partir d'un tableau du classeur (en-tête sur la 2e ligne)."""
    entete = [str(x) for x in feuille.iloc[1]]
    j_code = next(j for j, h in enumerate(entete) if "code" in norm(h))
    lignes = feuille.iloc[2:]
    lignes = lignes[lignes.iloc[:, j_code].astype(str).str.fullmatch(r"\d[\dAB]\d?")]
    out = []
    for j, h in enumerate(entete):
        m = re.search(r"\(ALD\s*(\d+)\)\s*$", h)
        if not m:
            continue
        brut = lignes.iloc[:, j].astype(str).str.strip()
        out.append(pd.DataFrame({"code": lignes.iloc[:, j_code].astype(str).str.zfill(2).to_numpy(),
                                 "ald": int(m.group(1)), "libelle_officiel": re.sub(r"\s*\(ALD\s*\d+\)\s*$", "", h),
                                 "brut": brut.to_numpy()}))
    return pd.concat(out, ignore_index=True)


def lire(chemin) -> pd.DataFrame:
    """Table longue (code, ald, libelle_officiel, effectif, secret, taux_standardise)."""
    x = pd.ExcelFile(chemin)
    ef = next(s for s in x.sheet_names if re.search(r"VII(?!I)", s))
    tx = next(s for s in x.sheet_names if "VIII" in s)
    e = _tableau(x.parse(ef, header=None))
    t = _tableau(x.parse(tx, header=None))
    e["secret"] = e["brut"].str.startswith("<")
    e["effectif"] = pd.to_numeric(e["brut"].where(~e["secret"]), errors="coerce")
    t["taux_standardise"] = pd.to_numeric(t["brut"], errors="coerce")
    return (e.drop(columns="brut").merge(t[["code", "ald", "taux_standardise"]], on=["code", "ald"], how="outer")
            .sort_values(["code", "ald"]).reset_index(drop=True))


def charger(hors_ligne=False, rafraichir=False):
    """Renvoie {"contexte": {"dep": DataFrame}, "defs": [...], "table": DataFrame} ou None."""
    try:
        if hors_ligne:
            if not DEST.exists():
                raise FileNotFoundError(DEST)
        else:
            res = [r for r in ressources_datagouv(config.ALD_DATAGOUV)
                   if re.search(config.ALD_MOTIF, norm(r["titre"]))]
            r = max(res, key=lambda r: int(re.search(config.ALD_MOTIF, norm(r["titre"])).group(1))) if res else None
            if r is None:
                r = choisir_ressource(ressources_datagouv(config.ALD_DATAGOUV), config.ALD_MOTIF)
            if r is None:
                raise IOError("classeur départemental introuvable dans le jeu data.gouv")
            annee = re.search(config.ALD_MOTIF, norm(r["titre"])).group(1)
            ancien = lire_meta(DEST)
            change = ancien.get("maj_source") != r["maj"] or ancien.get("annee") != annee
            telecharger(r["url"], DEST, "ald", rafraichir or (bool(ancien) and change), taille_min=10_000,
                        extra_meta={"maj_source": r["maj"], "annee": annee, "titre": r["titre"]})
        meta = lire_meta(DEST)
        table = lire(DEST)
    except Exception as e:  # noqa: BLE001
        JOURNAL.note(SOURCE, "erreur", str(e)[:300], page=PAGE)
        return None
    annee = meta.get("annee", "")
    table.insert(0, "annee", annee)
    noms = dict(zip(table["ald"], table["libelle_officiel"]))
    ctx, defs = {}, []
    for num, lab, fam in config.ALD_INDICATEURS:
        x = table[(table["ald"] == num) & table["taux_standardise"].notna()]
        # Mayotte, données non exhaustives selon l'Assurance Maladie, gardée dans la table mais pas en indicateur
        x = x[x["code"] != "976"]
        if x.empty:
            continue
        iid = f"ald_{num}"
        ctx[iid] = x.set_index("code")["taux_standardise"]
        defs.append({"id": iid, "libelle": f"{lab} (ALD {num})", "unite": "pour 100 000 (standardisé)",
                     "explication": (f"Personnes en affection de longue durée n° {num} ({noms.get(num, lab)}) pour "
                                     f"100 000 personnes protégées du régime général, taux standardisé sur l'âge pour "
                                     f"comparer des départements jeunes et âgés. Année {annee}."),
                     "source": SOURCE, "famille": fam, "licence": "Licence Ouverte 1.0", "niveau_origine": "dep",
                     "annee": annee, "groupe": None if fam == config.SANTE_MENTALE else config.GROUPE_ALD})
    n_dep = table["code"].nunique()
    JOURNAL.note(SOURCE, "ok", f"{table['ald'].nunique()} affections, {n_dep} départements, année {annee}, "
                 f"{len(defs)} indicateurs retenus", url=meta.get("url", ""), page=PAGE,
                 date_donnees=(meta.get("maj_source") or "")[:10])
    total23 = table.loc[table["ald"] == 23, "effectif"].sum()
    JOURNAL.controle("ALD 23, affections psychiatriques de longue durée, somme des départements",
                     f"{nombre(total23)} personnes en {annee} (régime général, effectifs arrondis)")
    return {"contexte": {"dep": pd.DataFrame(ctx)}, "defs": defs, "table": table}
