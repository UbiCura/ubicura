"""CAF, allocataires par prestation (CNAF, Licence Ouverte), par intercommunalité, département et région.

Deux jeux du portail Opendatasoft de la CNAF (config.CAF_JEUX). Le dernier mois de décembre publié pour les
intercommunalités est retenu aux deux niveaux, pour que les chiffres se comparent. Les régions sont la somme de leurs
départements. Les effectifs sont rapportés à la population du référentiel. Les allocataires du régime agricole, payés
par la MSA, ne sont pas comptés (config.LIMITES["caf"]). Ces indicateurs décrivent des situations de handicap ou de
précarité, ils ne mesurent pas un besoin de soins et ne servent pas au calcul de l'effectif attendu."""
from __future__ import annotations

from urllib.parse import quote

import pandas as pd

from .. import config
from ..lecture import nombre
from ..util import JOURNAL, get_json, lire_meta, telecharger

SOURCE = "CAF, allocataires par prestation"


def _dernier_decembre() -> str:
    jeu = config.CAF_JEUX["epci"][0]
    r = get_json(config.CAF_API + jeu + "/records?select=dtreffre&group_by=dtreffre&order_by=dtreffre%20desc&limit=20")
    mois = [str(x["dtreffre"])[:7] for x in r.get("results", [])]
    dec = [m for m in mois if m.endswith("-12")]
    if not dec:
        raise IOError("aucun mois de décembre publié")
    return dec[0]


def _lire(niv, mois, hors_ligne, rafraichir):
    jeu, cle = config.CAF_JEUX[niv]
    dest = config.BRUT / f"caf_{jeu}.csv"
    if hors_ligne:
        if not dest.exists():
            raise FileNotFoundError(dest)
    else:
        maj = (get_json(config.CAF_API + jeu).get("metas", {}).get("default", {}) or {}).get("modified", "")
        champs = [cle] + [c for _i, c, *_ in config.CAF_INDICATEURS]
        url = (config.CAF_API + jeu + "/exports/csv?delimiter=%3B&select=" + quote(",".join(champs))
               + "&where=" + quote(f"dtreffre = date'{mois}-01'"))
        ancien = lire_meta(dest)
        change = ancien.get("maj_source") != maj or ancien.get("mois") != mois
        telecharger(url, dest, "caf", rafraichir or (bool(ancien) and change), taille_min=500,
                    extra_meta={"maj_source": maj, "mois": mois})
    df = pd.read_csv(dest, sep=";", dtype={cle: str})
    df = df.rename(columns={cle: "code"})
    for _i, c, *_ in config.CAF_INDICATEURS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, lire_meta(dest)


def charger(ref, hors_ligne=False, rafraichir=False):
    """Renvoie {"contexte": {"epci", "dep", "reg"}, "defs": [...], "table": DataFrame} ou None."""
    try:
        mois = None if hors_ligne else _dernier_decembre()
        ep, meta = _lire("epci", mois, hors_ligne, rafraichir)
        mois = meta.get("mois", mois)
        dep, _m = _lire("dep", mois, hors_ligne, rafraichir)
    except Exception as e:  # noqa: BLE001
        JOURNAL.note(SOURCE, "erreur", str(e)[:300], page=config.CAF_PAGE.format(config.CAF_JEUX["epci"][0]))
        return None
    dep["code"] = dep["code"].str.zfill(2)
    regs = ref.deps.set_index("code")["reg"]
    champs = [c for _i, c, *_ in config.CAF_INDICATEURS]
    reg = dep.assign(code=dep["code"].map(regs)).dropna(subset=["code"]).groupby("code")[champs].sum(min_count=1)
    effectifs = {"epci": ep.drop_duplicates("code").set_index("code")[champs],
                 "dep": dep.drop_duplicates("code").set_index("code")[champs], "reg": reg}
    pops = {"epci": ref.epci.set_index("code")["pop"], "dep": ref.deps.set_index("code")["pop"],
            "reg": ref.regs.set_index("code")["pop"]}
    ctx, lignes = {}, []
    for niv, t in effectifs.items():
        pop = pops[niv].reindex(t.index).astype(float)
        cols = {}
        for iid, champ, _lab, _u, facteur, *_ in config.CAF_INDICATEURS:
            cols[iid] = (t[champ] / pop * facteur).where(pop > 0)
            lignes.append(pd.DataFrame({"niveau": niv, "code": t.index, "indicateur": iid, "mois": mois,
                                        "effectif": t[champ].to_numpy(), "population": pop.to_numpy(),
                                        "valeur": cols[iid].to_numpy()}))
        ctx[niv] = pd.DataFrame(cols)
    defs = [{"id": iid, "libelle": lab, "unite": unite, "explication": expl + f" Décembre {mois[:4]}.",
             "source": SOURCE, "famille": "", "licence": "Licence Ouverte 2.0", "niveau_origine": "epci",
             "annee": mois[:4], "groupe": groupe}
            for iid, _c, lab, unite, _f, groupe, expl in config.CAF_INDICATEURS]
    apparies = ctx["epci"].index.isin(ref.epci["code"]).sum()
    JOURNAL.note(SOURCE, "ok", f"décembre {mois[:4]}, {len(ep)} intercommunalités dont {apparies} reconnues, "
                 f"{int(dep['code'].isin(ref.deps['code']).sum())} départements", url=config.CAF_API + config.CAF_JEUX["epci"][0],
                 page=config.CAF_PAGE.format(config.CAF_JEUX["epci"][0]), date_donnees=(meta.get("maj_source") or "")[:10])
    JOURNAL.controle("CAF, bénéficiaires de l'AAH, somme des départements",
                     f"{nombre(dep['indben_aah'].sum())} en décembre {mois[:4]} (allocataires de la CAF seulement)")
    return {"contexte": ctx, "defs": defs, "table": pd.concat(lignes, ignore_index=True)}
