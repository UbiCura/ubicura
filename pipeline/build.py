"""Agrégation. Un professionnel est compté une fois par territoire, profession et mode
(et une fois au total tous modes confondus), au lieu de sa structure d'exercice."""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from . import config
from .util import JOURNAL, norm


@dataclass
class Agregats:
    effectifs: dict          # niveau -> DataFrame (code, prof, mode, n)
    national: pd.DataFrame   # prof, mode, n (toutes activités, localisées ou non)
    secteurs: pd.DataFrame   # niveau(FR|dep), code, prof, secteur, n
    categories: pd.DataFrame | None   # niveau, code, prof, categorie, agregat, n
    structures: pd.DataFrame | None   # niveau, code, prof, rs, commune, n
    appariement_finess: pd.DataFrame | None
    multisites: pd.DataFrame | None = None      # prof, personnes, part sur 2 communes ou plus, 2 EPCI ou plus
    liens: pd.DataFrame | None = None           # prof, epci_a, epci_b, n (personnes exerçant dans les deux)
    feminisation: pd.DataFrame | None = None    # niveau, code, prof, mode, personnes, femmes, part_femmes
    particulieres: dict | None = None   # activités sans soins à la population et pour un public particulier
    parcours: pd.DataFrame | None = None   # prof et personnes à chaque étape, de l'activité déclarée aux densités
    cmp: pd.DataFrame | None = None        # CMP actifs de FINESS par intercommunalité, dont avec un psychiatre déclaré


def cmp_et_psychiatres(act: pd.DataFrame, finess: pd.DataFrame | None, ref) -> pd.DataFrame | None:
    """Centres médico-psychologiques (CMP) actifs de FINESS par intercommunalité, et nombre d'entre eux où au moins un
    psychiatre déclare une activité au répertoire (numéro FINESS de l'établissement). Sert à nuancer « aucun
    psychiatre ne déclare exercer » (question de Lucas du 9 octobre 2026)."""
    if finess is None or "com" not in finess:
        return None
    f = finess[(finess["categetab"] == config.FINESS_CMP) & finess["actif"]].copy()
    if f.empty:
        return None
    com = ref.communes.set_index("code")
    c = f["com"].where(f["com"].isin(com.index), f["com"].map(ref.anciens))
    f["epci"], f["dep"] = c.map(com["epci"]), c.map(com["dep"])
    psy = act[act["prof"].astype(str).isin(["psychiatre", "pedopsychiatre"]) & (act["finess"] != "")]
    f["avec_psychiatre"] = f["nofinesset"].isin(set(psy["finess"]))
    JOURNAL.controle("CMP actifs de FINESS où au moins un psychiatre déclare son activité au répertoire",
                     f"{int(f['avec_psychiatre'].sum())} sur {len(f)}, {int(f['epci'].isna().sum())} hors du référentiel")
    t = (f.dropna(subset=["epci"]).groupby(["epci", "dep"], as_index=False)
         .agg(cmp=("nofinesset", "size"), cmp_avec_psychiatre=("avec_psychiatre", "sum")))
    t.attrs["total"], t.attrs["avec"] = len(f), int(f["avec_psychiatre"].sum())
    return t


def multisites(loc: pd.DataFrame, rattach) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Exercice sur plusieurs communes ou intercommunalités (point 10 du chantier 4), et liens agrégés
    entre intercommunalités. Les liens réunissant moins de config.SECRET_MIN personnes sont retirés."""
    x = loc[["id", "prof", "com", "epci"]].drop_duplicates()
    par = x.groupby(["prof", "id"], observed=True).agg(communes=("com", "nunique"), epci=("epci", "nunique"))
    ms = par.groupby("prof", observed=True).agg(personnes=("communes", "size"),
                                                plusieurs_communes=("communes", lambda s: int((s >= 2).sum())),
                                                plusieurs_epci=("epci", lambda s: int((s >= 2).sum())),
                                                communes_moyennes=("communes", "mean")).reset_index()
    ms["part_plusieurs_communes"] = ms["plusieurs_communes"] / ms["personnes"]
    ms["part_plusieurs_epci"] = ms["plusieurs_epci"] / ms["personnes"]
    e = x[x["prof"].astype(str).isin(config.PROFESSIONS_PRINCIPALES)][["id", "prof", "epci"]].drop_duplicates()
    e = e[e["id"].isin(e.groupby("id")["epci"].transform("nunique").pipe(lambda s: e.loc[s >= 2, "id"]))]
    paires = e.merge(e, on=["id", "prof"])
    paires = paires[paires["epci_x"] < paires["epci_y"]]
    liens = (paires.groupby(["prof", "epci_x", "epci_y"], observed=True)["id"].nunique().rename("n").reset_index()
             .rename(columns={"epci_x": "epci_a", "epci_y": "epci_b"}))
    liens = liens[liens["n"] >= config.SECRET_MIN].sort_values("n", ascending=False)
    liens["prof"] = liens["prof"].astype(str)
    ms["prof"] = ms["prof"].astype(str)
    return ms, liens


def feminisation(act: pd.DataFrame, loc: pd.DataFrame) -> pd.DataFrame | None:
    """Part de femmes (civilité déclarée « Madame ») par profession, en France et par département, tous
    modes et par mode (point 11)."""
    if "femme" not in act or act["femme"].isna().all():
        return None
    out = []
    for niv, df in [("FR", act.assign(code="FR")), ("dep", loc.assign(code=loc["dep"]))]:
        d = df.dropna(subset=["femme"])
        for mode in ["all", "lib", "sal"]:
            m = d if mode == "all" else d[d["mode"].astype(str) == mode]
            p = m[["code", "prof", "id", "femme"]].drop_duplicates(["code", "prof", "id"])
            g = p.groupby(["code", "prof"], observed=True)["femme"].agg(personnes="size", femmes="sum").reset_index()
            g.insert(0, "niveau", niv)
            g["mode"] = mode
            out.append(g)
    f = pd.concat(out, ignore_index=True)
    f = f[f["personnes"] > 0]
    f["femmes"] = f["femmes"].astype(int)
    f["part_femmes"] = f["femmes"] / f["personnes"]
    f["prof"] = f["prof"].astype(str)
    return f


def _compter(df, cles):
    """Effectifs distincts par mode, plus la modalité 'all' tous modes confondus."""
    parts = []
    m = df[cles + ["mode", "id"]].drop_duplicates()
    g = m.groupby(cles + ["mode"], observed=True).size().rename("n").reset_index()
    parts.append(g)
    a = df[cles + ["id"]].drop_duplicates().groupby(cles, observed=True).size().rename("n").reset_index()
    a["mode"] = "all"
    parts.append(a)
    out = pd.concat(parts, ignore_index=True)
    out["mode"] = out["mode"].astype(str)
    return out[out["n"] > 0]


def perimetre_elargi(act: pd.DataFrame, finess: pd.DataFrame | None, professions: pd.DataFrame):
    """Offre de santé mentale au sens élargi. Les activités salariées exercées dans un établissement
    psychiatrique ou médico-psychologique (config.FINESS_SANTE_MENTALE) sont dupliquées sous un
    identifiant « esm_<profession> ». On compte ainsi, profession par profession, les personnes qui
    travaillent dans ces établissements (infirmiers, psychomotriciens, éducateurs...). Ces comptages
    se lisent à côté du périmètre strict et ne s'additionnent jamais aux professions."""
    if finess is None or not config.FINESS_SANTE_MENTALE:
        return act, professions
    cat = finess.set_index("nofinesset")["categetab"]
    reelles = professions.loc[professions["nature"] == "profession", "id"]
    prof = act["prof"].astype(str)
    # les spécialités ajoutées en version 2 restent réunies sous « autre spécialité » dans ce périmètre
    prof = prof.where(~prof.isin(config.SPECIALITES_AJOUTEES), config.MEDECIN_AUTRE[0])
    m = (act["mode"].astype(str) == "sal") & prof.isin(reelles) & (act["finess"] != "") \
        & act["finess"].map(cat).isin(list(config.FINESS_SANTE_MENTALE))
    sel = act[m]
    n_par_prof = sel.groupby(prof[m])["id"].nunique()
    gardees = n_par_prof[n_par_prof >= config.ELARGI_EFFECTIF_MIN].index
    JOURNAL.controle("Santé mentale, périmètre élargi",
                     f"{sel['id'].nunique()} personnes salariées d'un établissement psychiatrique ou "
                     f"médico-psychologique, {len(gardees)} professions retenues (au moins "
                     f"{config.ELARGI_EFFECTIF_MIN} personnes en France)")
    if not len(gardees):
        return act, professions
    sel = sel[prof[m].isin(gardees)]
    ajout = sel.assign(prof=config.PREFIXE_ELARGI + prof[sel.index])
    lab = professions.set_index("id")["libelle"]
    defs = pd.DataFrame({"id": [config.PREFIXE_ELARGI + p for p in gardees],
                         "libelle": [f"{lab[p]}, en établissement psychiatrique" for p in gardees],
                         "groupe": config.GROUPE_ELARGI, "famille": config.SANTE_MENTALE,
                         "nature": "perimetre_elargi", "base": list(gardees)})
    act = pd.concat([act.astype({"prof": str}), ajout.astype({"prof": str})], ignore_index=True)
    act["prof"] = act["prof"].astype("category")
    attrs = dict(professions.attrs)   # pd.concat ne garde pas les attributs
    professions = pd.concat([professions, defs], ignore_index=True)
    professions.attrs.update(attrs)
    # nombre de personnes distinctes du périmètre, toutes professions (une personne n'est comptée qu'une fois)
    professions.attrs["elargi_personnes"] = int(sel["id"].nunique())
    return act, professions


def categories_activites(act: pd.DataFrame) -> pd.Series:
    """Catégorie de chaque activité (soins, public_particulier, sans_soins) d'après son secteur et la
    profession, selon config.SECTEURS_CATEGORIES."""
    regles = [(re.compile(m), profs, c) for m, profs, c in config.SECTEURS_CATEGORIES]

    def cat(secteur, prof):
        n = norm(secteur)
        return next((c for rx, profs, c in regles if rx.search(n) and (profs is None or prof in profs)), "soins")
    sec, prof = act["secteur"].astype(str), act["prof"].astype(str)
    d = {(a, b): cat(a, b) for a, b in set(zip(sec, prof))}
    return pd.Series([d[k] for k in zip(sec, prof)], index=act.index)


def parcours(act, cat, loc) -> pd.DataFrame:
    """Personnes distinctes à chaque étape, de l'activité déclarée au répertoire à la densité d'un territoire.
    avec_activite, au moins une activité déclarée (effectif national). sans_lieu, aucune activité avec une commune
    d'exercice (remplacements, exercice sans site fixe), comptées au national seulement. avec_lieu, au moins une
    activité localisée. sans_soins_seulement, toutes les activités localisées sont sans soins à la population
    (sièges, contrôle médical, industrie, téléconsultation...), dont_teleconsultation parmi elles. dans_densites,
    au moins une activité localisée de soins ou pour un public particulier, comptées dans les territoires."""
    sec = act["secteur"].astype(str)
    tele = sec.map({v: bool(re.search(config.SECTEUR_TELECONSULTATION, norm(v))) for v in sec.unique()}).astype(bool)
    a = act.assign(prof=act["prof"].astype(str), categorie=cat, tele=tele, lieu=act["com"].notna())
    a = a[~a["prof"].str.startswith(("q_", config.PREFIXE_ELARGI, config.PREFIXE_ENSEMBLE))]
    l = loc.assign(prof=loc["prof"].astype(str))
    dans = set(zip(l["prof"], l["id"]))
    ss = a[a["lieu"] & (a["categorie"] == "sans_soins")]
    ss = ss[[(p, i) not in dans for p, i in zip(ss["prof"], ss["id"])]]
    t = pd.DataFrame({
        "avec_activite": a.groupby("prof")["id"].nunique(),
        "avec_lieu": a[a["lieu"]].groupby("prof")["id"].nunique(),
        "dans_densites": l.groupby("prof")["id"].nunique(),
        "sans_soins_seulement": ss.groupby("prof")["id"].nunique(),
        "dont_teleconsultation": ss[ss["tele"]].groupby("prof")["id"].nunique(),
    }).fillna(0).astype(int)
    t = t[t["avec_activite"] > 0]
    t.insert(1, "sans_lieu", t["avec_activite"] - t["avec_lieu"])
    # contrôle, toute personne avec un lieu est soit comptée dans les densités, soit écartée comme sans soins
    ecart = int((t["avec_lieu"] - t["dans_densites"] - t["sans_soins_seulement"]).abs().sum())
    JOURNAL.controle("Du répertoire aux densités, personnes avec un lieu = comptées dans les densités + sans soins seulement",
                     "vérifié" if ecart == 0 else f"écart de {ecart} personnes")
    return t.rename_axis("prof").reset_index()


def particulieres(act, cat, loc, rattach) -> dict | None:
    """Activités sans soins à la population (retirées des densités) et pour un public particulier (gardées),
    comptées à part. Renvoie {"france": ..., "dep" / "reg" / "epci": ...}, effectifs en personnes distinctes."""
    sec = act["secteur"].astype(str)
    tele = sec.map({v: bool(re.search(config.SECTEUR_TELECONSULTATION, norm(v))) for v in sec.unique()})
    a = act.assign(categorie=cat, tele=tele.astype(bool), prof=act["prof"].astype(str))
    a = a[a["categorie"] != "soins"]
    if a.empty:
        return None
    tot = act[["id", "prof"]].drop_duplicates().assign(prof=lambda d: d["prof"].astype(str)).groupby("prof").size()
    # comptés dans une densité, même définition que parcours() pour que les deux chiffres concordent
    comptes = set(zip(loc["id"], loc["prof"].astype(str)))
    fr = []
    for c, g in a.groupby("categorie"):
        p = g.assign(lieu=g["com"].notna()).groupby(["prof", "id"]).agg(tele=("tele", "any"), lieu=("lieu", "any")).reset_index()
        p["seule"] = [l and (i, q) not in comptes for i, q, l in zip(p["id"], p["prof"], p["lieu"])]
        r = p.groupby("prof").agg(personnes=("id", "size"), dont_teleconsultation=("tele", "sum"),
                                  sans_autre_lieu_de_soins=("seule", "sum")).reset_index()
        r["categorie"] = c
        fr.append(r)
    fr = pd.concat(fr, ignore_index=True)
    fr["part_profession"] = fr["personnes"] / fr["prof"].map(tot)
    out = {"france": fr.sort_values(["categorie", "personnes"], ascending=[True, False])}
    l = a[a["com"].notna()].assign(com=lambda d: d["com"].astype(str)).join(rattach, on="com")
    for niv in ("dep", "reg", "epci"):
        out[niv] = (l[[niv, "prof", "categorie", "id"]].drop_duplicates().groupby([niv, "prof", "categorie"]).size()
                    .rename("n").reset_index().rename(columns={niv: "code"}))
    ss = a[a["categorie"] == "sans_soins"]
    JOURNAL.controle("Activités sans soins à la population, retirées des densités",
                     f"{len(ss)} activités, {ss['id'].nunique()} personnes, dont {int(ss.loc[ss['tele'], 'id'].nunique())} "
                     f"en téléconsultation")
    pp = a[a["categorie"] == "public_particulier"]
    JOURNAL.controle("Activités pour un public particulier, gardées dans les densités",
                     f"{len(pp)} activités, {pp['id'].nunique()} personnes")
    return out


def agreger(act: pd.DataFrame, ref, finess: pd.DataFrame | None) -> Agregats:
    rattach = ref.communes.set_index("code")[["epci", "dep", "reg"]]
    # Les activités sans soins à la population (contrôle médical, industrie, recherche, téléconsultation...) sont
    # souvent déclarées au siège d'un organisme. Elles sont retirées des comptages par territoire et décrites à
    # part (config.SECTEURS_CATEGORIES). Les personnes restent comptées une fois dans l'effectif national.
    cat_act = categories_activites(act)
    loc = act[act["com"].notna() & (cat_act != "sans_soins")].assign(categorie=cat_act).copy()
    loc["com"] = loc["com"].astype(str)
    loc = loc.join(rattach, on="com")
    eff = {}
    for niv in config.NIVEAUX:
        t = _compter(loc, [niv, "prof"]).rename(columns={niv: "code"})
        t["prof"] = t["prof"].astype(str)
        eff[niv] = t
    # morceau d'intercommunalité situé dans un département (rapports territoriaux), une intercommunalité
    # pouvant s'étendre sur plusieurs départements
    t = _compter(loc.assign(piece=loc["dep"] + "_" + loc["epci"]), ["piece", "prof"]).rename(columns={"piece": "code"})
    t["prof"] = t["prof"].astype(str)
    eff["piece"] = t
    nat = _compter(act.assign(_fr="FR"), ["_fr", "prof"]).drop(columns="_fr")
    nat["prof"] = nat["prof"].astype(str)

    # contrôle : la somme des effectifs départementaux tous modes doit être >= au national localisé
    nat_loc = _compter(loc.assign(_fr="FR"), ["_fr", "prof"])
    vraies = lambda t: t[(t["mode"] == "all") & ~t["prof"].astype(str).str.startswith(("q_", config.PREFIXE_ELARGI, config.PREFIXE_ENSEMBLE))]  # noqa: E731
    tot_dep = vraies(eff["dep"])["n"].sum()
    tot_nat = vraies(nat_loc)["n"].sum()
    JOURNAL.controle("Effectifs localisés, somme des départements et total national",
                     f"{tot_dep:,} pour {tot_nat:,}".replace(",", " ") + ", l'écart venant des personnes qui exercent dans plusieurs départements")

    sect = []
    # par intercommunalité, seulement les principales professions (pour « qui porte l'offre »)
    princ = loc[loc["prof"].astype(str).isin(config.PROFESSIONS_PRINCIPALES)]
    for niv, df in [("FR", act.assign(code="FR")), ("dep", loc.assign(code=loc["dep"])),
                    ("epci", princ.assign(code=princ["epci"]))]:
        s = (df[["code", "prof", "secteur", "id"]].drop_duplicates()
             .groupby(["code", "prof", "secteur"], observed=True).size().rename("n").reset_index())
        s["niveau"] = niv
        sect.append(s[s["n"] > 0])
    secteurs = pd.concat(sect, ignore_index=True)
    secteurs[["prof", "secteur"]] = secteurs[["prof", "secteur"]].astype(str)

    categories = structures = app = None
    if finess is not None:
        f = finess.set_index("nofinesset")
        avec = act[act["finess"] != ""]
        j = avec.join(f[["libcategetab", "libcategagretab"]], on="finess", how="left")
        app = (j.assign(apparie=j["libcategetab"].notna())
               .groupby("prof", observed=True)
               .agg(activites_avec_finess=("apparie", "size"), appariees=("apparie", "sum")).reset_index())
        app["taux"] = app["appariees"] / app["activites_avec_finess"]
        JOURNAL.controle("Appariement RPPS / FINESS (activités avec numéro FINESS)",
                         f"{app['appariees'].sum() / max(app['activites_avec_finess'].sum(), 1):.1%}")
        j = j[j["libcategetab"].notna()]
        j = j.join(rattach, on="com")
        cat = []
        for niv, df in [("FR", j.assign(code="FR")), ("dep", j.assign(code=j["dep"]))]:
            c = (df[["code", "prof", "libcategetab", "libcategagretab", "id"]].drop_duplicates()
                 .groupby(["code", "prof", "libcategetab", "libcategagretab"], observed=True).size()
                 .rename("n").reset_index())
            c["niveau"] = niv
            cat.append(c[c["n"] > 0])
        categories = pd.concat(cat, ignore_index=True).rename(
            columns={"libcategetab": "categorie", "libcategagretab": "agregat"})
        categories["prof"] = categories["prof"].astype(str)

    s = loc[(loc["mode"] != "lib") & (loc["rs"] != "") & loc["prof"].isin(config.PROFESSIONS_PRINCIPALES)]
    if len(s):
        s = s.assign(commune=s["com"].map(ref.communes.set_index("code")["nom"]))
        st = []
        for niv, df in [("FR", s.assign(code="FR")), ("dep", s.assign(code=s["dep"]))]:
            c = (df[["code", "prof", "rs", "commune", "id"]].drop_duplicates()
                 .groupby(["code", "prof", "rs", "commune"], observed=True).size().rename("n").reset_index())
            c = c[c["n"] > 0].sort_values("n", ascending=False).groupby(["code", "prof"], observed=True).head(15)
            c["niveau"] = niv
            st.append(c)
        structures = pd.concat(st, ignore_index=True)
        structures["prof"] = structures["prof"].astype(str)
    ms, liens = multisites(loc, rattach)
    fem = feminisation(act, loc)
    return Agregats(eff, nat, secteurs, categories, structures, app, ms, liens, fem,
                    particulieres(act, cat_act, loc, rattach), parcours(act, cat_act, loc),
                    cmp_et_psychiatres(act, finess, ref))
