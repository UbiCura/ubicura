"""Assurance Maladie, accès financier aux spécialistes et accès au médecin traitant (data.ameli.fr, ODbL).

Trois jeux, lus par l'API Opendatasoft de data.ameli.fr.
- Effectifs de libéraux par secteur conventionnel. Pour chaque spécialité retenue, part des libéraux qui peuvent
  pratiquer des dépassements d'honoraires (secteur 2, avec ou sans Optam, et non conventionnés), et part de ceux
  dont les dépassements ne sont pas encadrés (secteur 2 sans Optam et non conventionnés).
- Part des patients en affection longue durée sans médecin traitant.
- Montants des honoraires des libéraux (28 octobre 2026). Pour les mêmes spécialités, taux de dépassement des libéraux
  de secteur 2, tel que publié, c'est-à-dire les dépassements réellement facturés en part de leurs honoraires.

Les deux décrivent l'accès aux soins, pas le besoin. Données sous licence ODbL, isolées comme les autres données
de l'Assurance Maladie dans les fichiers suffixés _odbl."""
from __future__ import annotations

from urllib.parse import quote

import pandas as pd

from .. import config
from ..util import JOURNAL, get_json, lire_meta, telecharger

SOURCE_SECTEURS = "Assurance Maladie, effectifs de libéraux par secteur conventionnel (data.ameli.fr, licence ODbL)"
SOURCE_ALD = "Assurance Maladie, patients en affection longue durée sans médecin traitant (data.ameli.fr, licence ODbL)"
SOURCE_HONORAIRES = "Assurance Maladie, montants des honoraires des libéraux par territoire (data.ameli.fr, licence ODbL)"
PAGE = "https://data.ameli.fr/explore/dataset/{}/"


def _derniere_annee(api, champ="annee"):
    r = get_json(api + f"/records?select={champ}&group_by={champ}&limit=100")["results"]
    return max(str(x[champ])[:4] for x in r)


def _export(api, dest, select, where, hors_ligne, rafraichir, famille_cache="ameli"):
    if hors_ligne:
        if not dest.exists():
            raise FileNotFoundError(dest)
        return lire_meta(dest)
    maj = (get_json(api).get("metas", {}).get("default", {}) or {}).get("modified", "")
    url = api + "/exports/csv?delimiter=%3B&select=" + quote(select) + "&where=" + quote(where)
    ancien = lire_meta(dest).get("maj_source")
    telecharger(url, dest, famille_cache, rafraichir or (bool(ancien) and ancien != maj), taille_min=1000,
                extra_meta={"maj_source": maj, "where": where})
    return lire_meta(dest)


def _secteurs(hors_ligne, rafraichir):
    dest = config.BRUT / "ameli_secteurs_conventionnels.csv"
    profs = ",".join(f'"{p}"' for p, *_ in config.AMELI_SECTEURS_PROFESSIONS)
    annee = None if hors_ligne else _derniere_annee(config.AMELI_SECTEURS_API)
    where = f"profession_sante in ({profs})" + (f" and annee=date'{annee}'" if annee else "")
    meta = _export(config.AMELI_SECTEURS_API, dest, "annee,profession_sante,region,departement,secteur_conventionnel,effectif",
                   where, hors_ligne, rafraichir)
    df = pd.read_csv(dest, sep=";", dtype=str)
    df["effectif"] = pd.to_numeric(df["effectif"], errors="coerce").fillna(0)
    df["annee"] = df["annee"].str[:4]
    df = df[df["annee"] == df["annee"].max()]
    # les codes 3 et 4 détaillent le secteur 2, le code 2 seul n'est pas additionné pour éviter un double compte
    piv = df.pivot_table(index=["profession_sante", "region", "departement"], columns="secteur_conventionnel",
                         values="effectif", aggfunc="sum", fill_value=0)
    for c in "12345":
        if c not in piv:
            piv[c] = 0
    s2 = piv[["3", "4"]].sum(axis=1).where(piv[["3", "4"]].sum(axis=1) > 0, piv["2"])
    t = pd.DataFrame({"secteur_1": piv["1"], "secteur_2_optam": piv["3"], "secteur_2_sans_optam": piv["4"],
                      "secteur_2": s2, "non_conventionnes": piv["5"]}).reset_index()
    t["liberaux"] = t["secteur_1"] + t["secteur_2"] + t["non_conventionnes"]
    t["part_depassements"] = (t["secteur_2"] + t["non_conventionnes"]) / t["liberaux"]
    t["part_depassements_libres"] = (t["secteur_2_sans_optam"] + t["non_conventionnes"]) / t["liberaux"]
    t.loc[t["liberaux"] < config.AMELI_SECTEURS_EFFECTIF_MIN, ["part_depassements", "part_depassements_libres"]] = float("nan")
    t["niveau"] = "dep"
    t.loc[t["departement"] == "999", "niveau"] = "reg"
    t.loc[(t["departement"] == "999") & (t["region"] == "99"), "niveau"] = "FR"
    t["code"] = t["departement"].where(t["niveau"] == "dep", t["region"]).str.zfill(2)
    t.loc[t["niveau"] == "FR", "code"] = "FR"
    ids = {p: (i, lab, fam) for p, i, lab, fam in config.AMELI_SECTEURS_PROFESSIONS}
    t["prof"] = t["profession_sante"].map(lambda p: ids[p][0])
    t["annee"] = df["annee"].max()
    return t.drop(columns=["region", "departement"]), meta


def _nombre(s):
    """Montant publié, « NS » (secret statistique) ou vide donnent une valeur manquante."""
    return pd.to_numeric(s.where(~s.fillna("").str.strip().isin(["", "NS"])), errors="coerce")


def _honoraires(hors_ligne, rafraichir):
    dest = config.BRUT / "ameli_honoraires.csv"
    profs = ",".join(f'"{p}"' for p, *_ in config.AMELI_SECTEURS_PROFESSIONS)
    annee = None if hors_ligne else _derniere_annee(config.AMELI_HONORAIRES_API)
    where = f"profession_sante in ({profs})" + (f" and annee=date'{annee}'" if annee else "")
    meta = _export(config.AMELI_HONORAIRES_API, dest,
                   "annee,profession_sante,region,departement,hono_sans_depassement_totaux,depassements_totaux,"
                   "depassements_moyens,taux_depassement_s2", where, hors_ligne, rafraichir)
    df = pd.read_csv(dest, sep=";", dtype=str)
    df["annee"] = df["annee"].str[:4]
    df = df[df["annee"] == df["annee"].max()].copy()
    for c in ("hono_sans_depassement_totaux", "depassements_totaux", "depassements_moyens", "taux_depassement_s2"):
        df[c] = _nombre(df[c])
    # sous secret statistique, le jeu écrit un taux de 0, gardé comme valeur manquante (jamais un faux 0)
    df.loc[df["depassements_totaux"].isna(), "taux_depassement_s2"] = float("nan")
    df["niveau"] = "dep"
    df.loc[df["departement"] == "999", "niveau"] = "reg"
    df.loc[(df["departement"] == "999") & (df["region"] == "99"), "niveau"] = "FR"
    df["code"] = df["departement"].where(df["niveau"] == "dep", df["region"]).str.zfill(2)
    df.loc[df["niveau"] == "FR", "code"] = "FR"
    ids = {p: i for p, i, _lab, _fam in config.AMELI_SECTEURS_PROFESSIONS}
    df["prof"] = df["profession_sante"].map(ids)
    return df.drop(columns=["region", "departement"]), meta


def _ald(hors_ligne, rafraichir):
    dest = config.BRUT / "ameli_ald_sans_medecin_traitant.csv"
    annee = None if hors_ligne else _derniere_annee(config.AMELI_ALD_API)
    where = f"annee='{annee}'" if annee else "annee>='2018'"
    meta = _export(config.AMELI_ALD_API, dest, "annee,region,departement,taux_patients_ald_sans_mt_integer",
                   where, hors_ligne, rafraichir)
    df = pd.read_csv(dest, sep=";", dtype=str)
    df = df[df["annee"] == df["annee"].max()]
    df["valeur"] = pd.to_numeric(df["taux_patients_ald_sans_mt_integer"], errors="coerce")
    df["niveau"] = "dep"
    df.loc[df["departement"] == "999", "niveau"] = "reg"
    df["code"] = df["departement"].where(df["niveau"] == "dep", df["region"]).str.zfill(2)
    df.loc[(df["departement"] == "999") & (df["region"] == "99"), ["niveau", "code"]] = ["FR", "FR"]
    return df[["niveau", "code", "annee", "valeur"]], meta


def charger(ref, hors_ligne=False, rafraichir=False):
    """Renvoie {"contexte": {"dep", "reg"}, "defs": [...], "secteurs", "ald", "honoraires" (DataFrame)} ou None."""
    out = {"contexte": {"dep": pd.DataFrame(), "reg": pd.DataFrame()}, "defs": [], "secteurs": None, "ald": None,
           "honoraires": None}
    try:
        t, meta = _secteurs(hors_ligne, rafraichir)
        out["secteurs"] = t
        for p, iid, lab, fam in config.AMELI_SECTEURS_PROFESSIONS:
            x = t[t["prof"] == iid]
            cle = f"depassements_{iid}"
            for niv in ("dep", "reg"):
                out["contexte"][niv][cle] = x[x["niveau"] == niv].set_index("code")["part_depassements"] * 100
            out["defs"].append({
                "id": cle, "libelle": f"{lab} libéraux pouvant pratiquer des dépassements d'honoraires", "unite": "%",
                "explication": f"Part des {lab.lower()} libéraux conventionnés en secteur 2 (avec ou sans Optam) ou non "
                               f"conventionnés, qui peuvent facturer au-delà du tarif de la Sécurité sociale. Mesure un "
                               f"obstacle financier possible, pas les dépassements réellement pratiqués. Non calculée "
                               f"quand le département compte moins de {config.AMELI_SECTEURS_EFFECTIF_MIN} libéraux.",
                "source": SOURCE_SECTEURS, "famille": fam, "licence": config.AMELI_LICENCE, "niveau_origine": "dep",
                "groupe": config.GROUPE_ACCES})
        fr = t[(t["niveau"] == "FR") & (t["prof"] == "psychiatre")]
        JOURNAL.note("Assurance Maladie, secteurs conventionnels", "ok",
                     f"année {t['annee'].iloc[0]}, {t.loc[t['niveau'] == 'dep', 'code'].nunique()} départements, "
                     f"psychiatres libéraux en France {int(fr['liberaux'].sum())}",
                     url=PAGE.format("demographie-secteurs-conventionnels"), date_donnees=(meta.get("maj_source") or "")[:10])
        JOURNAL.controle("Assurance Maladie, parts de secteur 2 non calculées (moins de "
                         f"{config.AMELI_SECTEURS_EFFECTIF_MIN} libéraux)",
                         f"{int(t.loc[t['niveau'] == 'dep', 'part_depassements'].isna().sum())} sur "
                         f"{int((t['niveau'] == 'dep').sum())}")
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("Assurance Maladie, secteurs conventionnels", "erreur", str(e)[:300])
    try:
        h, meta = _honoraires(hors_ligne, rafraichir)
        # sans aucun libéral de secteur 2 dans le territoire (secteurs conventionnels), un taux de 0 n'a pas de sens
        if out["secteurs"] is not None:
            s2 = out["secteurs"].set_index(["niveau", "code", "prof"])["secteur_2"]
            sans_s2 = s2.reindex(pd.MultiIndex.from_frame(h[["niveau", "code", "prof"]])).to_numpy() == 0
            h.loc[sans_s2, "taux_depassement_s2"] = float("nan")
        out["honoraires"] = h
        for p, iid, lab, fam in config.AMELI_SECTEURS_PROFESSIONS:
            x = h[h["prof"] == iid]
            cle = f"taux_depassement_{iid}"
            for niv in ("dep", "reg"):
                out["contexte"][niv][cle] = x[x["niveau"] == niv].set_index("code")["taux_depassement_s2"] * 100
            out["defs"].append({
                "id": cle, "libelle": f"{lab} libéraux en secteur 2, dépassements rapportés aux honoraires sans dépassement",
                "unite": "%",
                "explication": f"Montant des dépassements facturés par les {lab.lower()} libéraux de secteur 2 du "
                               f"territoire, rapporté à leurs honoraires sans dépassement, en {h['annee'].iloc[0]}, tel "
                               f"que le publie l'Assurance Maladie. Mesure les dépassements réellement facturés, en "
                               f"moyenne, pas ce que paie chaque patient. Non publié quand les montants sont couverts "
                               f"par le secret statistique.",
                "source": SOURCE_HONORAIRES, "famille": fam, "licence": config.AMELI_LICENCE, "niveau_origine": "dep",
                "groupe": config.GROUPE_ACCES})
        fr = h[(h["niveau"] == "FR") & (h["prof"] == "psychiatre")]
        dep = h[h["niveau"] == "dep"]
        JOURNAL.note("Assurance Maladie, montants des honoraires", "ok",
                     f"année {h['annee'].iloc[0]}, {dep['code'].nunique()} départements, taux de dépassement des "
                     f"psychiatres libéraux de secteur 2 en France "
                     + (f"{fr['taux_depassement_s2'].iloc[0] * 100:.1f} %".replace(".", ",") if len(fr) else "non publié"),
                     url=PAGE.format("honoraires"), date_donnees=(meta.get("maj_source") or "")[:10])
        JOURNAL.controle("Assurance Maladie, taux de dépassement non publiés (secret statistique)",
                         f"{int(dep['taux_depassement_s2'].isna().sum())} sur {len(dep)} couples département et profession")
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("Assurance Maladie, montants des honoraires", "erreur", str(e)[:300])
    try:
        a, meta = _ald(hors_ligne, rafraichir)
        out["ald"] = a
        for niv in ("dep", "reg"):
            out["contexte"][niv]["ald_sans_medecin_traitant"] = a[a["niveau"] == niv].set_index("code")["valeur"]
        out["defs"].append({
            "id": "ald_sans_medecin_traitant", "libelle": "Patients en affection longue durée sans médecin traitant",
            "unite": "%", "explication": "Part des patients en affection longue durée (maladie chronique grave) qui n'ont "
                                         "pas déclaré de médecin traitant. Repère d'accès au médecin traitant, au-delà "
                                         "de la densité de généralistes.",
            "source": SOURCE_ALD, "famille": config.SANTE, "licence": config.AMELI_LICENCE, "niveau_origine": "dep",
            "groupe": config.GROUPE_ACCES})
        JOURNAL.note("Assurance Maladie, affection longue durée sans médecin traitant", "ok",
                     f"année {a['annee'].iloc[0]}, {a.loc[a['niveau'] == 'dep', 'code'].nunique()} départements",
                     url=PAGE.format("patients-longueduree-annuelle"), date_donnees=(meta.get("maj_source") or "")[:10])
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("Assurance Maladie, affection longue durée sans médecin traitant", "erreur", str(e)[:300])
    if not out["defs"]:
        return None
    # Mayotte, régime de sécurité sociale distinct, n'est pas comparable (comme pour la cartographie des pathologies)
    out["contexte"]["dep"] = out["contexte"]["dep"].drop(index=config.AMELI_DEPARTEMENTS_EXCLUS, errors="ignore")
    out["contexte"]["reg"] = out["contexte"]["reg"].drop(index=config.AMELI_REGIONS_EXCLUES, errors="ignore")
    return out
