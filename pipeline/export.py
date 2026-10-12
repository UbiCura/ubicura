"""Exports. CSV lisibles dans Excel (séparateur point-virgule, virgule décimale), JSON pour
le site, archive datée pour l'historique, rapport en Markdown."""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import limites as limites_mod
from . import (build, cartes, config, dictionnaire, graphiques, indicateurs, libelles, mises_a_jour, rapport,
               rapport_territoire)
from .analyses import tables
from .lecture import GLOSSAIRE, noms_classes as noms_classes_uniques
from .util import JOURNAL, log


LICENCE_LO = "Résultats sous Licence Ouverte 2.0, en citant la source et la date de la version."
LICENCE_ODBL = ("Résultats sous Licence Ouverte 2.0, en citant la source et la date de la version, sauf les indicateurs "
                "tirés des bases de l'Assurance Maladie (Cnam, data.ameli.fr, cartographie des pathologies, secteurs "
                "conventionnels, patients sans médecin traitant) et ce qui en dérive, diffusés sous licence ODbL 1.0 (partage à l'identique). Les fichiers suffixés _odbl et les "
                "données intégrées à l'atlas, qui contiennent ces indicateurs, sont sous ODbL. Les rapports et les "
                "cartes qui les affichent contiennent des informations issues de cette base sous ODbL.")


def _nombre_csv(x: float) -> str:
    """Six chiffres significatifs, sans notation scientifique pour les grands nombres. Les populations et effectifs
    restent exacts (« %.6g » écrivait 1,24631e+07 pour 12 463 067 habitants)."""
    if abs(x) < 1e6:
        t = f"{x:.6g}"
    else:
        t = f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}"
    return t.replace(".", ",")


def _csv(df, chemin: Path):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return
    df.to_csv(chemin, sep=";", decimal=",", index=False, encoding="utf-8-sig", float_format=_nombre_csv)


def _r(x, d=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), d)


def ecrire(agg, ref, professions, insee, R, diplomes, jour=None):
    jour = jour or date.today().isoformat()
    out = config.RESULTATS / jour
    out.mkdir(parents=True, exist_ok=True)
    hist = config.RESULTATS / "historique"
    hist.mkdir(parents=True, exist_ok=True)
    noms = {"com": ref.communes, "epci": ref.epci, "dep": ref.deps, "reg": ref.regs}
    lab = dict(zip(professions["id"], professions["libelle"]))

    # --- effectifs et densités, format large, par niveau
    for niv in config.NIVEAUX:
        for mode in ["all", "lib", "sal"]:
            n, dens, pop = tables(agg, ref, niv, mode)
            base = noms[niv].set_index("code").loc[n.index, ["nom"]]
            base["population"] = pop
            t = base.join(n.add_prefix("n_")).join(dens.add_prefix("densite_"))
            t.index.name = "code"
            _csv(t.reset_index(), out / f"effectifs_{niv}_{mode}.csv")
    agg.national.assign(libelle=agg.national["prof"].map(lab)).pipe(_csv, out / "effectifs_france.csv")
    # libellé officiel de la nomenclature et libellé d'affichage, côte à côte
    if agg.secteurs is not None:
        _csv(agg.secteurs.assign(categorie=build.categories_activites(agg.secteurs)).rename(
            columns={"secteur": "secteur_libelle_officiel"}).assign(
            secteur=lambda d: d["secteur_libelle_officiel"].map(libelles.affichage)), out / "secteurs.csv")
    if agg.categories is not None:
        _csv(agg.categories.rename(columns={"categorie": "categorie_libelle_officiel",
                                            "agregat": "agregat_libelle_officiel"}).assign(
            categorie=lambda d: d["categorie_libelle_officiel"].map(libelles.affichage),
            agregat=lambda d: d["agregat_libelle_officiel"].map(libelles.affichage)),
            out / "categories_etablissements.csv")
    shutil.copy(libelles.TABLE, out / "libelles.csv")
    _csv(agg.multisites, out / "exercice_multisites.csv")
    if agg.liens is not None:
        nom = ref.epci.set_index("code")["nom"]
        _csv(agg.liens.assign(nom_a=agg.liens["epci_a"].map(nom), nom_b=agg.liens["epci_b"].map(nom)),
             out / "liens_entre_intercommunalites.csv")
    _csv(agg.feminisation, out / "feminisation.csv")
    if agg.particulieres:
        cat_lab = config.CATEGORIES_SECTEURS
        x = agg.particulieres["france"]
        _csv(x.assign(libelle=x["prof"].map(lab), categorie_libelle=x["categorie"].map(cat_lab)),
             out / "activites_particulieres.csv")
        for niv in ("dep", "reg", "epci"):
            x = agg.particulieres[niv]
            _csv(x.assign(nom=x["code"].map(noms[niv].set_index("code")["nom"]), libelle=x["prof"].map(lab),
                          categorie_libelle=x["categorie"].map(cat_lab)), out / f"activites_particulieres_{niv}.csv")
    _csv(agg.structures, out / "structures_principales.csv")
    _csv(agg.appariement_finess, out / "controle_appariement_finess.csv")
    _csv(professions, out / "professions.csv")
    ins = professions.attrs.get("inscrits")
    if isinstance(ins, pd.DataFrame) and len(ins):
        _csv(ins, out / "inscrits_sans_activite.csv")
    # du répertoire aux densités, personnes à chaque étape (schéma de l'atlas et des rapports)
    parc = _parcours(agg, ins, lab)
    if parc is not None:
        _csv(parc, out / "parcours_activites.csv")
    # Les indicateurs sous licence ODbL (partage à l'identique) et ce qui en dérive vont dans des fichiers
    # séparés, suffixés _odbl, pour que le reste des résultats reste sous Licence Ouverte.
    odbl = indicateurs.odbl(insee)
    if insee:
        for niv, t in insee["contexte"].items():
            t = t.reset_index().rename(columns={"index": "code"})
            t = t.rename(columns={t.columns[0]: "code"})
            libres = [c for c in t.columns if c not in odbl]
            _csv(t[libres], out / f"contexte_{niv}.csv")
            if odbl & set(t.columns):
                _csv(t[["code"] + [c for c in t.columns if c in odbl]].dropna(how="all", subset=[c for c in t.columns if c in odbl]),
                     out / f"contexte_{niv}_odbl.csv")
        if insee.get("ameli"):
            _csv(insee["ameli"]["table"], out / "sante_mentale_assurance_maladie_odbl.csv")
        if insee.get("odisse"):
            _csv(insee["odisse"]["table"], out / "sante_mentale_sante_publique_france.csv")
        if insee.get("ameli_acces") and insee["ameli_acces"].get("secteurs") is not None:
            _csv(insee["ameli_acces"]["secteurs"], out / "secteurs_conventionnels_odbl.csv")
        if insee.get("sae"):
            _csv(insee["sae"]["table"], out / "psychiatrie_hopital.csv")
        if insee.get("ald"):
            t = insee["ald"]["table"]
            noms_dep = ref.deps.set_index("code")["nom"]
            _csv(t.assign(nom=t["code"].map(noms_dep)), out / "ald_departements.csv")
        if insee.get("caf"):
            _csv(insee["caf"]["table"], out / "allocataires_caf.csv")
    for k, v in R.items():
        if isinstance(v, dict):
            for niv, m in v.items():
                _csv(m.reset_index().rename(columns={"prof": "prof"}), out / f"{k}_{niv}.csv")
        elif isinstance(v, pd.DataFrame) and "variable_a" in v and odbl:
            o = v["variable_a"].isin(odbl) | v["variable_b"].isin(odbl)
            _csv(v[~o], out / f"{k}.csv")
            _csv(v[o], out / f"{k}_odbl.csv")
        elif isinstance(v, pd.DataFrame) and "variable" in v and odbl:
            o = v["variable"].isin(odbl)
            _csv(v[~o], out / f"{k}.csv")
            _csv(v[o], out / f"{k}_odbl.csv")
        else:
            _csv(v, out / f"{k}.csv")
    _csv(diplomes.dropna(axis=1, how="all") if diplomes is not None else None, out / "diplomes_psychologues.csv")

    # --- historique (effectifs départementaux datés)
    e = agg.effectifs["dep"].assign(date=jour)
    _csv(e, hist / f"effectifs_dep_{jour}.csv")
    serie = _historique(hist)

    # --- données du site
    site = _site(agg, ref, professions, insee, R, serie, jour)
    texte = rapport.ecrire(out, agg, ref, professions, insee, R, jour)
    try:
        cartes.ecrire_fond_atlas(ref)
    except Exception as e:  # noqa: BLE001
        log.exception("fond de carte de l'atlas")
        JOURNAL.note("Fond de carte de l'atlas", "erreur", str(e)[:300])
    try:
        texte += "\n" + rapport_territoire.ecrire(out, agg, ref, professions, insee, R, jour)
    except Exception as e:  # noqa: BLE001
        log.exception("rapports territoriaux")
        JOURNAL.note("Rapports territoriaux", "erreur", str(e)[:300])
    try:
        graphiques.ecrire(out, agg, ref, professions, insee, R)
    except Exception as e:  # noqa: BLE001
        log.exception("graphiques")
        JOURNAL.note("Graphiques des rapports", "erreur", str(e)[:300])
    dictionnaire.ecrire(out, indicateurs.liste(insee))
    # contrôle du langage sur tout ce qu'un lecteur voit (hors raisons sociales, qui sont des noms propres)
    site_txt = json.dumps({k: v for k, v in site.items() if k != "structures"}, ensure_ascii=False)
    pb = libelles.termes_proscrits(texte) + libelles.termes_proscrits(site_txt)
    JOURNAL.controle("Termes à proscrire dans le rapport et les données du site",
                     "aucun" if not pb else f"{len(pb)} occurrence(s), voir le journal d'exécution")
    for x in pb:
        log.warning("terme à proscrire : %s", x)
    site["meta"]["journal"] = JOURNAL.to_dict()
    (out / "site_data.json").write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out / "journal.json").write_text(json.dumps(JOURNAL.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Résultats écrits dans %s", out)
    return out


def _historique(hist: Path):
    fichiers = sorted(hist.glob("effectifs_dep_*.csv"))
    if not fichiers:
        return None
    parts = [pd.read_csv(f, sep=";", decimal=",", dtype={"code": str}) for f in fichiers]
    h = pd.concat(parts)
    h = h[h["mode"] == "all"].groupby(["date", "prof"])["n"].sum().reset_index()
    return h


def _parcours(agg, ins, lab):
    """Étapes du répertoire aux densités par profession, avec les inscrits quand la profession correspond à un
    libellé du répertoire (les spécialités médicales n'ont pas d'inscrits propres)."""
    t = agg.parcours
    if not isinstance(t, pd.DataFrame) or t.empty:
        return None
    t = t.copy()
    t.insert(1, "libelle", t["prof"].map(lab))
    if isinstance(ins, pd.DataFrame) and len(ins):
        from .sources.rpps import classer_profession
        corr = {}
        for r in ins.itertuples():
            c = classer_profession(r.libelle_rpps)
            if c and c[0] in set(t["prof"]):
                corr[c[0]] = int(r.inscrits)
        t.insert(2, "inscrits", t["prof"].map(corr).astype("Int64"))
    return t


def _offre_besoin_site(R):
    """Zones du Moran local bivarié par département (indicateur du département, offre des voisins)."""
    t = R.get("offre_besoin_lisa")
    if not isinstance(t, pd.DataFrame) or t.empty:
        return None
    z = {}
    for (p, v), g in t.groupby(["prof", "variable"]):
        z.setdefault(p, {})[v] = {c: [zone, _r(q, 4)] for c, zone, q in zip(g["code"], g["zone"], g["q"])}
    return {"palette": config.BIVARIEE, "variables": list(dict.fromkeys(t["variable"])), "zones": z}


def _gwr_site(R, epci):
    """Coefficient local du niveau de vie par intercommunalité (régression géographiquement pondérée)."""
    co, re_ = R.get("gwr_coefficients"), R.get("gwr_resume")
    if not isinstance(co, pd.DataFrame) or co.empty or not epci:
        return None
    codes = [u["c"] for u in epci["units"]]
    out = {}
    for p, g in co.groupby("prof"):
        g = g.set_index("code").reindex(codes)
        r = re_.set_index("prof").loc[p]
        out[p] = {"coef": [None if pd.isna(c) else [_r(c, 3), int(bool(n))] for c, n in zip(g["coef_niveau_de_vie"], g["net"])],
                  "resume": {k: (_r(v, 4) if isinstance(v, float) else int(v) if isinstance(v, (int, np.integer)) else v)
                             for k, v in r.items()}}
    return out


def _parcours_site(agg, professions):
    t = _parcours(agg, professions.attrs.get("inscrits"), dict(zip(professions["id"], professions["libelle"])))
    if t is None:
        return None
    cols = ["inscrits", "avec_activite", "sans_lieu", "avec_lieu", "sans_soins_seulement", "dont_teleconsultation",
            "dans_densites"]
    return {r["prof"]: [None if c not in r or pd.isna(r[c]) else int(r[c]) for c in cols] for _i, r in t.iterrows()}


def _site(agg, ref, professions, insee, R, serie, jour):
    ctx_def = [{k: d[k] for k in ("id", "label", "unite", "explication", "source", "famille", "licence", "groupe", "niveaux")}
               for d in indicateurs.liste(insee)]
    # lien de chaque indicateur vers la fiche de son jeu de données (page « Données sources » du site)
    for d in ctx_def:
        jeu = mises_a_jour.jeu_de_source(d.get("source") or "")
        d["fiche"] = mises_a_jour.ancre(jeu) if jeu else None
    niveaux = {}
    # régions ajoutées le 7 octobre 2026 (carte et tableau de l'atlas par région, demande de Lucas)
    reg_de_dep = ref.deps.set_index("code")["reg"]
    for niv in ["reg", "dep", "epci"]:
        base = {"epci": ref.epci, "dep": ref.deps, "reg": ref.regs}[niv].set_index("code")
        n_all, _d, pop = tables(agg, ref, niv, "all")
        codes = list(n_all.index)
        tab = {m: tables(agg, ref, niv, m)[0].reindex(codes).fillna(0).astype(int) for m in ["lib", "sal", "all"]}
        ctx = insee["contexte"].get(niv) if insee else None
        ctx = ctx.reindex(codes) if ctx is not None else None
        parent = (pd.Series("France", index=codes) if niv == "reg"
                  else base.loc[codes, "reg"].map(ref.regs.set_index("code")["nom"]) if niv == "dep"
                  else base.loc[codes, "dep"])
        unites = []
        for c in codes:
            u = {"c": c, "nm": base.at[c, "nom"], "p": parent.get(c) or "", "pop": int(pop[c])}
            if ctx is not None:
                u["x"] = [_r(ctx.at[c, d["id"]]) if d["id"] in ctx else None for d in ctx_def]
            unites.append(u)
        bloc = {"units": unites, "n": {p: {m: tab[m][p].tolist() if p in tab[m] else [0] * len(codes)
                                           for m in tab} for p in professions["id"]}}
        # centres médico-psychologiques actifs de FINESS, pour nuancer « aucun psychiatre déclaré » (9 octobre 2026)
        cm = getattr(agg, "cmp", None)
        if isinstance(cm, pd.DataFrame) and not cm.empty:
            cle_niv = {"epci": cm["epci"], "dep": cm["dep"], "reg": cm["dep"].map(reg_de_dep)}[niv]
            par = cm.groupby(cle_niv)["cmp"].sum()
            bloc["cmp"] = [int(par.get(c, 0)) for c in codes]
        if niv == "epci" and isinstance(R.get("ecarts_attendu"), pd.DataFrame) and not R["ecarts_attendu"].empty:
            ea = R["ecarts_attendu"]
            bloc["attendu"] = {p: [_r(v) for v in g.set_index("code")["attendu"].reindex(codes)]
                               for p, g in ea.groupby("prof")}
        if niv == "epci" and R.get("typologie_affectation") is not None:
            # une typologie par famille (santé mentale, santé, ensemble), avec la position sur les axes 1 et 2 de l'ACP
            bloc["classe"], bloc["acp"] = {}, {}
            for fam, g in R["typologie_affectation"].groupby("famille"):
                g = g.set_index("code").reindex(codes)
                bloc["classe"][fam] = [None if pd.isna(v) else int(v) for v in g["classe"]]
                bloc["acp"][fam] = [None if pd.isna(a) else [_r(a, 2), _r(b, 2)] for a, b in zip(g["axe1"], g["axe2"])]
        tc = R.get("accessibilite_communes")
        if isinstance(tc, pd.DataFrame) and len(tc):
            if niv not in tc:
                tc = tc.assign(reg=tc["dep"].map(reg_de_dep))
            g = (tc.assign(ap=tc["accessibilite"] * tc["population"], dp=tc["distance_km"] * tc["population"])
                 .groupby(["prof", niv])[["ap", "dp", "population"]].sum())
            g["acc"], g["dist"] = g["ap"] / g["population"], g["dp"] / g["population"]
            bloc["acces"] = {p: [_r(v, 2) for v in h.droplevel(0)["acc"].reindex(codes)] for p, h in g.groupby(level=0)}
            bloc["distance"] = {p: [_r(v, 1) for v in h.droplevel(0)["dist"].reindex(codes)] for p, h in g.groupby(level=0)}
        li = R.get("lisa")
        if niv == "epci" and isinstance(li, pd.DataFrame) and len(li):
            bloc["zones"] = {p: [None if pd.isna(v) else v for v in g.set_index("code")["zone"].reindex(codes)]
                             for p, g in li.groupby("prof")}
        en = R.get("entonnoir")
        if isinstance(en, pd.DataFrame) and len(en):
            e = en[en["niveau"] == niv]
            bloc["entonnoir"] = {p: [None if pd.isna(v) else int(v) for v in g.set_index("code")["statut"].reindex(codes)]
                                 for p, g in e.groupby("prof")}
        # évolution de la densité sur dix ans (séries de la DREES), régions et départements
        ev = R.get("evolution_offre_resume")
        if isinstance(ev, pd.DataFrame) and len(ev) and niv in ("reg", "dep"):
            e = ev[ev["niveau"] == niv]
            bloc["evolution"] = {p: [None if pd.isna(r.evolution_densite) else
                                     [_r(r.densite_debut, 2), _r(r.densite_fin, 2), _r(r.evolution_densite, 4)]
                                     for r in g.set_index("code").reindex(codes).itertuples()]
                                 for p, g in e.groupby("prof")}
        # temps de trajet par la route (INSEE), part des habitants à plus de 20 minutes et durée médiane
        ta = R.get("temps_acces")
        if isinstance(ta, pd.DataFrame) and len(ta):
            t = ta[ta["niveau"] == niv]
            bloc["route"] = {e: [None if pd.isna(r.part_population_a_plus_de_20_min) else
                                 [_r(r.part_population_a_plus_de_20_min, 4), _r(r.temps_median_min, 1)]
                                 for r in g.set_index("code").reindex(codes).itertuples()]
                             for e, g in t.groupby("equipement")}
        # personnes déclarant ici une activité sans soins à la population (sièges, téléconsultation...), non
        # comptées dans la densité du territoire, pour les professions où il y en a
        ap = (agg.particulieres or {}).get(niv)
        if isinstance(ap, pd.DataFrame) and len(ap):
            a = ap[ap["categorie"] == "sans_soins"]
            bloc["hors_soins"] = {p: {c: int(n) for c, n in zip(g["code"], g["n"])} for p, g in a.groupby("prof")}
        niveaux[niv] = bloc

    def top(df, cle_lab, niveau_fr=True, k=10):
        """Les k premières modalités par profession et territoire. Les libellés sont rangés une seule fois dans
        une liste (lib), chaque ligne y renvoie par son numéro, ce qui allège nettement les données de l'atlas."""
        if df is None or df.empty:
            return {}
        libs, index, out = [], {}, {}
        for (code, p), g in df.groupby(["code", "prof"], observed=True):
            lignes = []
            for _, r in g.nlargest(k, "n").iterrows():
                lab = libelles.affichage(r[cle_lab])
                if lab not in index:
                    index[lab] = len(libs)
                    libs.append(lab)
                lignes.append([index[lab], int(r["n"])])
            out.setdefault(p, {})[code] = lignes
        return {"lib": libs, "v": out}

    struct = {}
    if agg.structures is not None:
        for (code, p), g in agg.structures.groupby(["code", "prof"], observed=True):
            struct.setdefault(p, {})[code] = [[r["rs"], r["commune"], int(r["n"])] for _, r in g.head(10).iterrows()]

    corr = None
    cc = R.get("correlations_contexte")
    if isinstance(cc, pd.DataFrame) and len(cc):
        corr = [{"niv": r["niveau"], "mode": r["mode"], "prof": r["prof"], "var": r["variable"],
                 "rho": _r(r["rho_spearman"], 3), "lo": _r(r["ic95_bas"], 3), "hi": _r(r["ic95_haut"], 3),
                 "q": _r(r["q_bh"], 4), "rp": _r(r.get("rho_partiel_densite"), 3),
                 "lp": _r(r.get("ic95_bas_partiel"), 3), "hp": _r(r.get("ic95_haut_partiel"), 3),
                 "qp": _r(r.get("q_bh_partiel"), 4)} for _, r in cc.iterrows()]
    ineg = R.get("inegalites")
    ineg = ([{"niv": r["niveau"], "mode": r["mode"], "prof": r["prof"], "gini": _r(r["gini"], 3),
              "zero": _r(r["part_population_sans_professionnel"], 4)}
             for _, r in ineg[ineg["niveau"].isin(["epci", "dep"])].iterrows()] if isinstance(ineg, pd.DataFrame) else [])
    prof_typo = R.get("typologie_profils")
    noms_classes = {}
    if isinstance(prof_typo, pd.DataFrame) and len(prof_typo):
        lab = dict(zip(professions["id"], professions["libelle"]))
        # les noms de groupes ne tiennent qu'aux professions qui forment les groupes, pas aux spécialités décrites
        formees = prof_typo[prof_typo["dans_typologie"]] if "dans_typologie" in prof_typo else prof_typo
        for fam, gf in formees.groupby("famille"):
            profils = {k: {lab.get(p, p): v for p, v in zip(g["prof"], g["indice_vs_national"])}
                       for k, g in gf.groupby("classe")}
            noms_classes.update({f"{fam}|{k}": v for k, v in noms_classes_uniques(profils).items()})
    sp = R.get("spatial")
    nat = agg.national.pivot_table(index="prof", columns="mode", values="n", fill_value=0)
    return {
        "meta": {"genere_le": jour, "demo": False, "journal": JOURNAL.to_dict(),
                 "millesimes_insee": insee["millesimes"] if insee else {},
                 "familles": config.FAMILLES,
                 # groupes des spécialités médicales, repliés dans la fiche d'un territoire (version 2)
                 "groupes_specialites": config.GROUPES_SPECIALITES + [config.MEDECIN_AUTRE[2]],
                 "glossaire": [{"id": g[0], "terme": g[1], "definition": g[2], "famille": g[3]} for g in GLOSSAIRE],
                 "exclus_croisements": list(config.DEPARTEMENTS_EXCLUS_CROISEMENTS),
                 "noms_classes": noms_classes,
                 "licences": LICENCE_ODBL if indicateurs.odbl(insee) else LICENCE_LO,
                 "libelles": "Les libellés de certaines nomenclatures officielles sont remplacés par des formulations "
                             "respectueuses des personnes, sigles d'usage conservés. La table de correspondance "
                             "(libelles.csv) accompagne les résultats."},
        "professions": professions.fillna("").to_dict("records"),
        "contexte": ctx_def,
        "niveaux": niveaux,
        "france": {"pop": int(ref.communes["pop"].sum()),
                   "n": {p: [int(nat.at[p, m]) if (p in nat.index and m in nat.columns) else 0 for m in ["lib", "sal", "all"]]
                         for p in professions["id"]}},
        "secteurs": top(agg.secteurs[agg.secteurs["niveau"].isin(["FR", "dep"])], "secteur"),
        "categories": top(agg.categories, "categorie"),
        "structures": struct,
        "correlations": corr,
        "inegalites": ineg,
        "typologie": prof_typo.to_dict("records") if isinstance(prof_typo, pd.DataFrame) else None,
        "spatial": sp.to_dict("records") if isinstance(sp, pd.DataFrame) else None,
        "historique": serie.to_dict("records") if isinstance(serie, pd.DataFrame) else None,
        "revenu": _revenu_site(R),
        "entonnoir": _entonnoir_site(R),
        # limites connues des données avec leurs sources (5 octobre 2026), affichées là où la donnée est montrée
        "limites": {k: {"risque": L["risque"], "texte": L["texte"], "sources": L["sources"],
                        "territoires": L.get("territoires", {}), "nom": limites_mod.NOMS.get(k, k)}
                    for k, L in config.LIMITES.items()},
        "limites_alias": config.LIMITES_ALIAS,
        "sensibilite": _sensibilite_site(R),
        "route": _route_site(R),
        "evolution": _evolution_site(R),
        "acp": _acp_site(R),
        "croisements_indicateurs": _croisements_ind_site(R),
        "croisements_bases": _croisements_bases_site(R, professions, insee),
        "regressions": _regressions_site(R),
        "parcours": _parcours_site(agg, professions),
        "offre_besoin": _offre_besoin_site(R),
        "gwr": _gwr_site(R, niveaux.get("epci")),
    }


def _croisements_bases_site(R, professions, insee):
    """Croisements entre bases par département (config.CROISEMENTS), avec leur question, leurs corrélations et la
    valeur de chaque département, pour l'onglet Croisements de l'atlas (demande de Lucas du 9 octobre 2026)."""
    from .lecture import pluriel
    from .rapport import THEMES_CROISEMENTS
    cr = R.get("croisements")
    if not isinstance(cr, pd.DataFrame) or cr.empty:
        return None
    lab = dict(zip(professions["id"], professions["libelle"]))
    ctxlab = indicateurs.libelles(insee)
    ta = R.get("temps_acces")
    eq = (ta.drop_duplicates("equipement").set_index("equipement")["libelle"].to_dict()
          if isinstance(ta, pd.DataFrame) and not ta.empty else {})
    questions = {t: (f, q) for f, d in THEMES_CROISEMENTS.items() for t, q in d.items()}

    def nom(cle):
        if cle.startswith("dens_lib:"):
            return pluriel(lab.get(cle[9:], cle[9:])).capitalize() + " libéraux pour 10 000 habitants"
        if cle.startswith("dens:"):
            return pluriel(lab.get(cle[5:], cle[5:])).capitalize() + " pour 10 000 habitants"
        if cle.startswith("route:"):
            e_ = eq.get(cle[6:], cle[6:])
            return "Temps médian par la route, " + e_[:1].lower() + e_[1:] + " (minutes)"
        v = cle[4:] if cle.startswith("ctx:") else cle
        return ctxlab.get(v, v)
    pts = cr.attrs.get("points", {})
    out = []
    for r in cr.itertuples():
        fam, q = questions.get(r.theme, ("", ""))
        out.append({"theme": r.theme, "famille": fam, "question": q, "x": nom(r.mesure), "y": nom(r.variable),
                    "rho": _r(r.rho, 3), "lo": _r(r.ic95_bas, 3), "hi": _r(r.ic95_haut, 3),
                    "rp": _r(getattr(r, "rho_partiel_densite", None), 3),
                    "lop": _r(getattr(r, "ic95_bas_partiel", None), 3), "hip": _r(getattr(r, "ic95_haut_partiel", None), 3),
                    "n": int(r.departements),
                    "pts": [[c, _r(a, 3), _r(b, 3)] for c, a, b in pts.get((r.mesure, r.variable), [])]})
    return out


def _croisements_ind_site(R):
    """Corrélations entre indicateurs, par département (données de l'atlas, déclarées sous ODbL)."""
    t = R.get("croisements_indicateurs")
    if not isinstance(t, pd.DataFrame) or t.empty:
        return None
    return [{"a": r.variable_a, "b": r.variable_b, "rho": _r(r.rho, 3), "lo": _r(r.ic95_bas, 3), "hi": _r(r.ic95_haut, 3),
             "q": _r(r.q_bh, 4), "sans": _r(r.rho_sans_ile_de_france, 3), "n": int(r.departements)} for r in t.itertuples()]


def _regressions_site(R):
    t = R.get("regressions_indicateurs")
    if not isinstance(t, pd.DataFrame) or t.empty:
        return None
    return [{"res": r.resultat, "champ": r.champ, "var": r.variable, "b": _r(r.coef_standardise, 3),
             "lo": _r(r.ic95_bas, 3), "hi": _r(r.ic95_haut, 3), "r2": _r(r.r2, 3), "n": int(r.departements),
             "rho": _r(getattr(r, "rho_simple", None), 3),
             "dep": getattr(r, "depend_de", None) if isinstance(getattr(r, "depend_de", None), str) else None,
             "bsans": _r(getattr(r, "coef_sans_depend_de", None), 3)}
            for r in t.itertuples()]


def _acp_site(R):
    """Part d'inertie des axes, corrélation des professions avec les axes 1 et 2, qualité de la typologie."""
    ine, ch, q = R.get("acp_inertie"), R.get("acp_charges"), R.get("typologie_qualite")
    if not isinstance(ine, pd.DataFrame) or ine.empty:
        return None
    out = {}
    for fam, g in ine.groupby("famille"):
        c = ch[(ch["famille"] == fam) & ch["axe"].isin([1, 2])].pivot_table(index="prof", columns="axe", values="correlation")
        qq = q[q["famille"] == fam].iloc[0]
        out[fam] = {"inertie": [_r(v, 4) for v in g.sort_values("axe")["part_inertie"]],
                    "charges": {p: [_r(r[1], 3), _r(r[2], 3)] for p, r in c.iterrows()},
                    "silhouette": _r(qq["silhouette"], 3), "inertie_classes": _r(qq["part_inertie_classes"], 3),
                    "classes": int(qq["classes"])}
    return out


def _evolution_site(R):
    """Professions dont l'évolution est connue, période et valeur de la France entière."""
    ev = R.get("evolution_offre_resume")
    if not isinstance(ev, pd.DataFrame) or ev.empty:
        return None
    fr = ev[ev["niveau"] == "FR"]
    return [{"prof": r.prof, "lib": r.libelle, "debut": int(r.annee_debut), "fin": int(r.annee_fin),
             "fr": [_r(r.densite_debut, 2), _r(r.densite_fin, 2), _r(r.evolution_densite, 4)]} for r in fr.itertuples()]


def _sensibilite_site(R):
    """Corrélations avec et sans l'Île-de-France, où les suicides sont nettement sous-déclarés."""
    s = R.get("sensibilite_ile_de_france")
    if not isinstance(s, pd.DataFrame) or s.empty:
        return None
    return [{"prof": r["prof"], "var": r["variable"], "rho": _r(r["rho_tous"], 3),
             "sans": _r(r["rho_sans_ile_de_france"], 3)} for _, r in s.iterrows()]


def _route_site(R):
    """Équipements dont le temps de trajet est connu, avec la profession comparable et la valeur nationale."""
    ta = R.get("temps_acces")
    if not isinstance(ta, pd.DataFrame) or ta.empty:
        return None
    fr = ta[ta["niveau"] == "FR"].set_index("equipement")
    return [{"id": e, "lib": lib, "fam": fam, "prof": prof,
             "fr": [_r(fr.at[e, "part_population_a_plus_de_20_min"], 4), _r(fr.at[e, "temps_median_min"], 1)]}
            for _code, e, lib, fam, prof in config.ACCES_ROUTE if e in fr.index]


def _revenu_site(R):
    co, es = R.get("concentration_revenu"), R.get("escalier_social")
    if not isinstance(co, pd.DataFrame) or co.empty:
        return None
    out = {"concentration": [{"niv": r["niveau"], "prof": r["prof"], "c": _r(r["indice_concentration"], 3),
                              "lo": _r(r["ic95_bas"], 3), "hi": _r(r["ic95_haut"], 3)}
                             for _, r in co[co["mode"] == "all"].iterrows()],
           "escalier": {}, "bornes": {}}
    for niv, g in es.groupby("niveau"):
        out["escalier"][niv] = {p: [_r(v, 2) for v in h.sort_values("decile")["densite"]] for p, h in g.groupby("prof")}
        b = g[g["prof"] == g["prof"].iloc[0]].sort_values("decile")
        out["bornes"][niv] = [[_r(a, 0), _r(z, 0)] for a, z in zip(b["niveau_de_vie_min"], b["niveau_de_vie_max"])]
    return out


def _entonnoir_site(R):
    lim, res = R.get("entonnoir_limites"), R.get("entonnoir_resume")
    if not isinstance(lim, pd.DataFrame) or lim.empty:
        return None
    out = {"limites": {}, "resume": {}}
    for (niv, p), g in lim.groupby(["niveau", "prof"]):
        out["limites"].setdefault(niv, {})[p] = [[int(r["population"]), _r(r["bas_95"], 3), _r(r["haut_95"], 3),
                                                   _r(r["bas_998"], 3), _r(r["haut_998"], 3)] for _, r in g.iterrows()]
    for _, r in res.iterrows():
        out["resume"].setdefault(r["niveau"], {})[r["prof"]] = {
            "hors95": _r(r["part_hors_95"], 4), "sous998": _r(r["part_nettement_en_dessous"], 4),
            "pop_sous998": _r(r["part_population_nettement_en_dessous"], 4)}
    return out
