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
SOURCE_PATIENTELE = "Assurance Maladie, patientèle des libéraux par territoire (data.ameli.fr, licence ODbL)"
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


def _patientele(hors_ligne, rafraichir):
    """File active moyenne et patientèle « médecin traitant » moyenne des libéraux, toutes les années publiées (2016 et
    suivantes), pour l'historique. NS (moins de 5 libéraux, secret statistique) et NC (non calculé) deviennent des
    valeurs manquantes, jamais des 0."""
    dest = config.BRUT / "ameli_patientele.csv"
    profs = ",".join(f'"{p}"' for p, *_ in config.AMELI_PATIENTELE_PROFESSIONS)
    meta = _export(config.AMELI_PATIENTELE_API, dest,
                   "annee,profession_sante,region,departement,nombre_patients_uniques,nombre_patients_medecin_traitant",
                   f"profession_sante in ({profs})", hors_ligne, rafraichir)
    df = pd.read_csv(dest, sep=";", dtype=str)
    df["annee"] = df["annee"].str[:4]
    df["file_active"] = _nombre(df["nombre_patients_uniques"])
    df["patients_mt"] = _nombre(df["nombre_patients_medecin_traitant"])
    df["secret"] = df["nombre_patients_uniques"].astype(str).str.strip().eq("NS")
    # 0 patient : aucun libéral de la profession dans le territoire (effectif nul dans le jeu des secteurs, vérifié le
    # 10 novembre 2026 pour les pédiatres des Hautes-Alpes et de Mayotte), écrit « aucun », jamais un faux 0
    df["aucun"] = df["file_active"].eq(0)
    df.loc[df["aucun"], ["file_active", "patients_mt"]] = float("nan")
    df["niveau"] = "dep"
    df.loc[df["departement"] == "999", "niveau"] = "reg"
    df.loc[(df["departement"] == "999") & (df["region"] == "99"), "niveau"] = "FR"
    df["code"] = df["departement"].where(df["niveau"] == "dep", df["region"]).str.zfill(2)
    df.loc[df["niveau"] == "FR", "code"] = "FR"
    ids = {p: i for p, i, _lab, _fam in config.AMELI_PATIENTELE_PROFESSIONS}
    df["prof"] = df["profession_sante"].map(ids)
    return (df[["annee", "niveau", "code", "prof", "file_active", "patients_mt", "secret", "aucun"]]
            .sort_values(["prof", "niveau", "code", "annee"]).reset_index(drop=True), meta)


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


def _non_publies(x: pd.DataFrame, lab: str) -> dict:
    """Raison écrite de chaque taux de dépassement non publié, par niveau et par territoire (décision de Lucas du 30
    octobre 2026, « non publié, 2 médecins généralistes en secteur 2, moins de 5 »), montrée à la place du chiffre."""
    seuil = config.AMELI_SECTEURS_EFFECTIF_MIN
    plur = lab.lower()
    sing = " ".join(m[:-1] if m.endswith("s") else m for m in plur.split())
    out = {}
    for r in x[x["taux_depassement_s2"].isna() & x["niveau"].isin(["dep", "reg"])].itertuples():
        n = getattr(r, "n_secteur_2", float("nan"))
        if getattr(r, "trop_peu", False) and n == n:
            n = int(n)
            # espaces insécables, « secteur 2 » et « moins de 5 » ne se coupent pas sur téléphone
            txt = (f"non publié, aucun {sing} en secteur 2" if n == 0 else
                   f"non publié, {n} {sing if n == 1 else plur} en secteur 2, moins de {seuil}")
        else:
            txt = "non publié, montants couverts par le secret statistique"
        out.setdefault(r.niveau, {})[r.code] = txt
    return out


def charger(ref, hors_ligne=False, rafraichir=False):
    """Renvoie {"contexte": {"dep", "reg"}, "defs": [...], "secteurs", "ald", "honoraires" (DataFrame)} ou None."""
    out = {"contexte": {"dep": pd.DataFrame(), "reg": pd.DataFrame()}, "defs": [], "secteurs": None, "ald": None,
           "honoraires": None, "patientele": None}
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
        # le taux n'est publié qu'à partir du même effectif que les parts de secteur 2 (AMELI_SECTEURS_EFFECTIF_MIN) :
        # 144 couples département et profession sur 505 reposaient sur 1 à 4 libéraux de secteur 2, dont 167 % pour
        # 2 médecins généralistes du Tarn-et-Garonne (audit du 30 octobre 2026), et sans aucun, un taux n'a pas de sens
        if out["secteurs"] is not None:
            s2 = out["secteurs"].set_index(["niveau", "code", "prof"])["secteur_2"]
            n_s2 = s2.reindex(pd.MultiIndex.from_frame(h[["niveau", "code", "prof"]])).to_numpy()
            trop_peu = ~(n_s2 >= config.AMELI_SECTEURS_EFFECTIF_MIN)
            h["n_secteur_2"] = n_s2
            h["trop_peu"] = trop_peu
            h.loc[trop_peu, "taux_depassement_s2"] = float("nan")
            JOURNAL.controle(f"Assurance Maladie, taux de dépassement non publiés (moins de "
                             f"{config.AMELI_SECTEURS_EFFECTIF_MIN} libéraux de secteur 2)",
                             f"{int((trop_peu & (h['niveau'] == 'dep').to_numpy()).sum())} sur "
                             f"{int((h['niveau'] == 'dep').sum())} couples département et profession")
        out["honoraires"] = h
        for p, iid, lab, fam in config.AMELI_SECTEURS_PROFESSIONS:
            x = h[h["prof"] == iid]
            cle = f"taux_depassement_{iid}"
            for niv in ("dep", "reg"):
                out["contexte"][niv][cle] = x[x["niveau"] == niv].set_index("code")["taux_depassement_s2"] * 100
            out["defs"].append({
                "non_publies": _non_publies(x, lab),
                "id": cle, "libelle": f"{lab} libéraux en secteur 2, dépassements rapportés aux honoraires sans dépassement",
                "unite": "%",
                "explication": f"Montant des dépassements facturés par les {lab.lower()} libéraux de secteur 2 du "
                               f"territoire, rapporté à leurs honoraires sans dépassement, en {h['annee'].iloc[0]}, tel "
                               f"que le publie l'Assurance Maladie. Mesure les dépassements réellement facturés, en "
                               f"moyenne, pas ce que paie chaque patient. Non publié quand les montants sont couverts "
                               f"par le secret statistique ou quand le territoire compte moins de "
                               f"{config.AMELI_SECTEURS_EFFECTIF_MIN} libéraux de secteur 2, car un ou deux médecins "
                               f"suffiraient à faire varier fortement le taux.",
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
        pt, meta = _patientele(hors_ligne, rafraichir)
        out["patientele"] = pt
        an = pt["annee"].max()
        d = pt[pt["annee"] == an]
        for p, iid, lab, fam in config.AMELI_PATIENTELE_PROFESSIONS:
            x = d[d["prof"] == iid]
            # article, singulier et accord (« une sage-femme libérale », « un masseur-kinésithérapeute libéral »)
            un, sing, lib, libs = {"sage_femme": ("une", "sage-femme", "libérale", "libérales"),
                                   "masseur_kinesitherapeute": ("un", "masseur-kinésithérapeute", "libéral", "libéraux"),
                                   "chirurgien_dentiste": ("un", "chirurgien-dentiste", "libéral", "libéraux")}.get(
                iid, ("un", " ".join(m[:-1] if m.endswith("s") else m for m in lab.lower().split()), "libéral",
                      "libéraux"))
            cle = f"file_active_{iid}"
            for niv in ("dep", "reg"):
                out["contexte"][niv][cle] = x[x["niveau"] == niv].set_index("code")["file_active"]
            ns = {niv: {**{c: f"non publié, moins de 5 {lab.lower()} {libs} (secret statistique)"
                           for c in x.loc[(x["niveau"] == niv) & x["secret"], "code"]},
                        **{c: f"non publié, {'aucune' if un == 'une' else 'aucun'} {sing} {lib}" for c in x.loc[(x["niveau"] == niv) & x["aucun"], "code"]}}
                  for niv in ("dep", "reg")}
            out["defs"].append({
                "non_publies": {k: v for k, v in ns.items() if v},
                "id": cle, "libelle": f"Patientèle d'{un} {sing} {lib}",
                "unite": "patients vus dans l'année, en moyenne",
                "explication": f"Nombre moyen de patients différents vus au moins une fois en {an} par {un} {sing} "
                               f"{lib} dont le cabinet principal est dans le territoire (file active), quel que soit "
                               f"le domicile des patients. Elle décrit la charge d'un libéral, pas l'accès des habitants.",
                "source": SOURCE_PATIENTELE, "famille": fam, "licence": config.AMELI_LICENCE, "niveau_origine": "dep",
                "groupe": config.GROUPE_ACCES})
            if iid in ("medecin_generaliste", "pediatre") and x["patients_mt"].notna().any():
                cle = f"patients_mt_{iid}"
                for niv in ("dep", "reg"):
                    out["contexte"][niv][cle] = x[x["niveau"] == niv].set_index("code")["patients_mt"]
                out["defs"].append({
                    "non_publies": {k: v for k, v in ns.items() if v},
                    "id": cle, "libelle": f"Patients qui ont choisi un {sing} libéral comme médecin traitant",
                    "unite": "patients, en moyenne",
                    "explication": f"Nombre moyen de patients qui ont déclaré un {sing} libéral du territoire comme "
                                   f"médecin traitant, en {an}, qu'il les ait vus ou non dans l'année.",
                    "source": SOURCE_PATIENTELE, "famille": fam, "licence": config.AMELI_LICENCE,
                    "niveau_origine": "dep", "groupe": config.GROUPE_ACCES})
        fr = d[(d["niveau"] == "FR") & (d["prof"] == "psychiatre")]
        dd = d[d["niveau"] == "dep"]
        JOURNAL.note("Assurance Maladie, patientèle des libéraux", "ok",
                     f"années {pt['annee'].min()} à {an}, {dd['code'].nunique()} départements, file active moyenne "
                     f"d'un psychiatre libéral en France "
                     + (f"{int(fr['file_active'].iloc[0])} patients" if len(fr) and fr['file_active'].notna().all()
                        else "non publiée"),
                     url=PAGE.format("patientele"), date_donnees=(meta.get("maj_source") or "")[:10])
        JOURNAL.controle("Assurance Maladie, file active des libéraux non publiée (moins de 5 libéraux)",
                         f"{int(dd['file_active'].isna().sum())} sur {len(dd)} couples département et profession en {an}")
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("Assurance Maladie, patientèle des libéraux", "erreur", str(e)[:300])
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
