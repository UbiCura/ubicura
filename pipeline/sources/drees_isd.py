"""DREES, indicateurs sociaux départementaux (ISD), protection de l'enfance et handicap (Licence Ouverte).

Chaque jeu est lu par l'API Opendatasoft de la DREES, filtré sur les indicateurs retenus dans config.DREES_ISD.
La dernière année disponible est gardée pour chaque indicateur. Les totaux régionaux portent le code
département « 1000 ». Ces indicateurs décrivent des situations de vulnérabilité ou l'offre médico-sociale, ils ne
mesurent pas un besoin de soins et ne servent pas au calcul de l'effectif attendu."""
from __future__ import annotations

from urllib.parse import quote

import pandas as pd

from .. import config
from ..util import JOURNAL, get_json, lire_meta, telecharger

PAGE = "https://data.drees.solidarites-sante.gouv.fr/explore/dataset/{}/"
TITRES = {"596_enfance-et-jeunesse-en-danger": "protection de l'enfance",
          "627_personnes-en-situation-de-handicap": "personnes en situation de handicap"}


def _lire(jeu, ids, hors_ligne, rafraichir):
    dest = config.BRUT / f"drees_isd_{jeu.split('_')[0]}.csv"
    if hors_ligne:
        if not dest.exists():
            raise FileNotFoundError(dest)
    else:
        api = config.DREES_API + jeu
        maj = (get_json(api).get("metas", {}).get("default", {}) or {}).get("modified", "")
        where = "id_indicateur in (" + ",".join(f"'{i}'" for i in ids) + ")"
        url = (api + "/exports/csv?delimiter=%3B&select=" + quote("annee,code_reg,code_dep,id_indicateur,value")
               + "&where=" + quote(where))
        ancien = lire_meta(dest).get("maj_source")
        telecharger(url, dest, "drees_isd", rafraichir or (bool(ancien) and ancien != maj), taille_min=1000,
                    extra_meta={"maj_source": maj})
    df = pd.read_csv(dest, sep=";", dtype=str)
    df["valeur"] = pd.to_numeric(df["value"].str.replace(",", "."), errors="coerce")
    return df, lire_meta(dest)


def charger(hors_ligne=False, rafraichir=False):
    """Renvoie {"contexte": {"dep", "reg"}, "defs": [...], "table": DataFrame} ou None."""
    ctx, defs, lignes = {"dep": {}, "reg": {}}, [], []
    for jeu in dict.fromkeys(x[0] for x in config.DREES_ISD):
        inds = [x for x in config.DREES_ISD if x[0] == jeu]
        try:
            df, meta = _lire(jeu, [x[1] for x in inds], hors_ligne, rafraichir)
        except Exception as e:  # noqa: BLE001
            JOURNAL.note(f"DREES, {TITRES.get(jeu, jeu)}", "erreur", str(e)[:300])
            continue
        annees = []
        for _j, idd, iid, lab, unite, facteur, fam, expl in inds:
            x = df[(df["id_indicateur"] == idd) & df["valeur"].notna()]
            if x.empty:
                continue
            annee = x["annee"].max()
            x = x[x["annee"] == annee]
            annees.append(annee)
            dep = x[x["code_dep"].str.len().between(2, 3) & (x["code_dep"] != "20R")]
            reg = x[x["code_dep"] == "1000"]
            for niv, t, cle in [("dep", dep, "code_dep"), ("reg", reg, "code_reg")]:
                v = t.drop_duplicates(cle).set_index(cle)["valeur"] * facteur
                ctx[niv][iid] = v
                lignes.append(pd.DataFrame({"niveau": niv, "code": v.index, "indicateur": iid, "annee": annee,
                                            "valeur": v.to_numpy()}))
            defs.append({"id": iid, "libelle": lab, "unite": unite, "explication": expl + f" Année {annee}.",
                         "source": f"DREES, indicateurs sociaux départementaux, {TITRES.get(jeu, jeu)}", "famille": fam,
                         "licence": "Licence Ouverte 2.0", "niveau_origine": "dep", "annee": annee,
                         "groupe": config.GROUPE_ENFANCE_HANDICAP})
        if annees:
            JOURNAL.note(f"DREES, {TITRES.get(jeu, jeu)}", "ok",
                         f"{len(annees)} indicateurs, années {min(annees)} à {max(annees)}, "
                         f"{df.loc[df['code_dep'].str.len() <= 3, 'code_dep'].nunique()} départements",
                         url=PAGE.format(jeu), date_donnees=(meta.get("maj_source") or "")[:10])
    if not defs:
        return None
    return {"contexte": {niv: pd.DataFrame(v) for niv, v in ctx.items()}, "defs": defs,
            "table": pd.concat(lignes, ignore_index=True)}
