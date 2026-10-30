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
from .analyses import professions_part_liberal, tables
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
    _lieux_csv(agg, noms, lab, out)
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
        if insee.get("ameli_acces") and insee["ameli_acces"].get("honoraires") is not None:
            _csv(insee["ameli_acces"]["honoraires"], out / "honoraires_odbl.csv")
        if insee.get("age"):
            _csv(insee["age"]["table"], out / "age_professionnels.csv")
        if insee.get("sae"):
            _csv(insee["sae"]["table"], out / "psychiatrie_hopital.csv")
        if insee.get("ald"):
            t = insee["ald"]["table"]
            noms_dep = ref.deps.set_index("code")["nom"]
            _csv(t.assign(nom=t["code"].map(noms_dep)), out / "ald_departements.csv")
        if insee.get("caf"):
            _csv(insee["caf"]["table"], out / "allocataires_caf.csv")
        # séries et repères nationaux des descripteurs de la voie légère (30 octobre 2026)
        ext = insee.get("complements") or {}
        if ext.get("series"):
            _csv(pd.concat(ext["series"], ignore_index=True), out / "series_complements.csv")
        if ext.get("reperes"):
            _csv(pd.DataFrame([{k: r.get(k) for k in ("id", "libelle", "unite", "valeur", "annee", "source")}
                               for r in ext["reperes"]]), out / "reperes_nationaux_complements.csv")
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
    # photographie des comptes de cette extraction du RPPS, pour suivre les figures dans le temps (26 octobre 2026)
    try:
        from . import photographies
        photographies.ecrire(agg, jour)
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("Photographie des comptes", f"non écrite ({e.__class__.__name__}: {e})")

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


def _lieux_csv(agg, noms, lab, out: Path):
    """Structures de soins réunies de FINESS et du ROR (pipeline/lieux.py), liste, comptes par territoire, distances,
    concordance des deux bases et couverture de chaque type."""
    from . import lieux as lieux_mod
    from . import structures_verifiees as sv
    from . import confirmation as conf_mod
    L = getattr(agg, "lieux", None)
    if not L:
        return
    x = L["lieux"]
    t = pd.DataFrame({
        "type": x["type"], "libelle_type": x["libelle_type"], "famille": x["famille"], "groupe": x["groupe"],
        "nom": x["nom_affiche"], "unite_ror": x["nom"],
        "secteur": [lieux_mod.code_secteur(a, b, c, d) for a, b, c, d in zip(
            x["nom_affiche"], x["nom"], x.get("nom_finess", pd.Series(index=x.index, dtype=object)),
            x.get("remarque_verification", pd.Series(index=x.index, dtype=object)))],
        "finess": x["finess"].fillna(x.get("finess_rapproche")),
        "finess_rapproche": x.get("finess_rapproche"), "finess_absorbes": x.get("finess_absorbes"),
        "entite_juridique": x["ej"], "commune": x["commune"],
        "commune_inscription": x.get("commune_inscription", pd.Series(index=x.index, dtype=object)),
        "nom_commune": x["commune"].map(noms["com"].set_index("code")["nom"]), "epci": x["epci"], "dep": x["dep"],
        "reg": x["reg"], "adresse": x["adresse"], "latitude": x["lat"].round(5), "longitude": x["lon"].round(5),
        "emplacement": x["precision"].map(lieux_mod.PRECISIONS),
        "provenance": x["provenance"].map(lieux_mod.PROVENANCES),
        "categories_ror": x.get("categories_ror"), "categorie_finess": x.get("categorie_finess"),
        "age_min": x.get("age_min"), "age_max": x.get("age_max"), "lits_ror": x.get("lits"),
        "unites_ror": x.get("unites_ror"),
        "verification": x.get("statut_verification", pd.Series(index=x.index, dtype=object)).map(sv.STATUTS),
        "source_verification": x.get("source_verification"), "adresse_source_verification": x.get("adresse_source"),
        "date_verification": x.get("date_verification"),
        "classe_confirmation": x.get("confirmation", pd.Series(index=x.index, dtype=object)).map(conf_mod.classe)
        .map(conf_mod.CLASSES),
        "confirmation": x.get("confirmation", pd.Series(index=x.index, dtype=object)).map(conf_mod.NIVEAUX),
        "site_certification_has": x.get("confirmee_has"), "siret_sirene": x.get("siret_sirene"),
        "enseigne_sirene": x.get("enseigne_sirene"), "adresse_sirene": x.get("adresse_sirene"),
        "role": x.get("role_structure", pd.Series(index=x.index, dtype=object)).map(lieux_mod.ROLES),
        "verdict": x.get("verdict"), "examen": x.get("examen"), "lieu": x["lieu"]})
    pros = L["pros"].add_prefix("declares_")
    t = t.merge(pros, left_on="lieu", right_index=True, how="left")
    sans_num = t["finess"].isna()
    partage = t.pop("declares_partage_par") if "declares_partage_par" in t else pd.Series(1, index=t.index)
    cols_dec = [c for c in pros.columns if c != "declares_partage_par"]
    for c in cols_dec:
        t[c] = t[c].where(sans_num, t[c].fillna(0))
    # effectif d'un établissement dont plusieurs structures partagent le numéro FINESS dans la commune, jamais attribué
    # à l'une d'elles (règle des trois temps, 29 octobre 2026), montré une seule fois dans declares_etablissements.csv
    partagee = partage.fillna(1) > 1
    etab = t.loc[partagee, ["finess", "commune", "nom_commune"] + cols_dec].assign(structures_partageant=partage[partagee])
    t.loc[partagee, cols_dec] = np.nan
    t["declares_partage_par"] = partage.where(partagee).astype("Int64")
    if len(etab):
        etab = etab.groupby(["finess", "commune", "nom_commune"], as_index=False).first()
        etab["structures_partageant"] = etab["structures_partageant"].astype(int)
        _csv(etab, out / "declares_etablissements.csv")
    # clé persistante de chaque structure, tenue d'une version à l'autre (pipeline/cles_structures.py, 29 octobre 2026)
    from . import cles_structures
    t.insert(0, "id_structure", cles_structures.appliquer(t, out.name))
    _csv(t.drop(columns="lieu").sort_values(["type", "dep", "commune", "nom"]), out / "lieux_soins.csv")
    # établissements Sirene actifs sous une enseigne de CMP sans structure correspondante, à vérifier
    ss = L.get("sirene_seul")
    if isinstance(ss, pd.DataFrame):
        _csv(ss.assign(nom_commune=ss["commune"].map(noms["com"].set_index("code")["nom"])),
             out / "sirene_sans_correspondant.csv")
    # liste vérifiée, établissements vérifiés et inscriptions des bases non retenues
    ver = L.get("verification") or {}
    if isinstance(ver.get("etablissements"), pd.DataFrame) and len(ver["etablissements"]):
        e = ver["etablissements"].drop(columns=["empreinte"], errors="ignore")
        n = x[x.get("verifiee", False) == True]  # noqa: E712
        n = n[~n["type"].isin([c for v in sv.ENFANTS_DE.values() for c in v])]
        par = (n.groupby(["ej", "dep", "statut_verification"]).size().unstack(fill_value=0)
               .reindex(columns=list(sv.STATUTS), fill_value=0))
        tout = par.groupby(level="ej").sum()
        cols = [f"structures_{k}" for k in sv.STATUTS]
        # un établissement vérifié sur tous ses départements (departement vide) compte toutes ses structures
        vals = [(tout.loc[r.ej] if r.departement == "" and r.ej in tout.index else
                 par.loc[(r.ej, r.departement)] if (r.ej, r.departement) in par.index else
                 pd.Series(0, index=list(sv.STATUTS))).to_numpy() for r in e.itertuples()]
        e = pd.concat([e.reset_index(drop=True), pd.DataFrame(vals, columns=cols)], axis=1)
        # par établissement vérifié et non par gestionnaire (le CH Sainte-Marie de Nice signalé seul, et non les cinq
        # établissements de l'association, constat du 29 octobre 2026), avec la raison du signalement
        raisons = {(r[0], r[1]): r[2] for r in ver.get("a_reverifier", [])}
        e["raison_reverification"] = [raisons.get((r.ej, r.etablissement)) for r in e.itertuples()]
        e["a_reverifier"] = e["raison_reverification"].notna()
        _csv(e, out / "etablissements_verifies.csv")
        _csv(pd.DataFrame(ver.get("non_retenues") or [], columns=["ej", "etablissement", "type", "nom", "commune",
                                                                  "nom_commune", "finess", "provenance", "raison"]),
             out / "structures_non_retenues.csv")
        _csv(pd.DataFrame(ver.get("gardees") or [], columns=["ej", "etablissement", "type", "nom", "commune",
                                                             "nom_commune", "finess", "provenance", "raison"]),
             out / "structures_gardees_a_verifier.csv")
        # aucun nom de personne dans les textes de vérification publiés (règle de Lucas du 15 octobre 2026, son nom
        # ne figure que dans les citations et les mentions légales)
        prenom = config.AUTEUR.split()[0]
        textes = pd.concat([t[c].astype(str) for c in ("examen", "source_verification") if c in t]
                           + [e[c].astype(str) for c in ("remarque", "sources") if c in e]
                           + [pd.Series([str(r.get("raison", "")) for r in (ver.get("non_retenues") or [])], dtype=str)])
        n_nom = int(textes.str.contains(prenom, regex=False).sum())
        JOURNAL.controle("Nom de personne dans les textes de vérification publiés (attendu, aucun)",
                         "aucun" if not n_nom else f"{n_nom} textes")
        # verdicts de la vérification à la main sans structure correspondante (clé changée, structure déjà réunie)
        _csv(pd.DataFrame((ver.get("verdicts") or {}).get("non_trouves") or [],
                          columns=["cle", "structure", "verdict", "finess", "situation", "structure_actuelle"]),
             out / "verdicts_sans_structure.csv")
    types = {tp[0]: tp[1] for tp in config.LIEUX_TYPES}
    # un type recensé dans moins de config.LIEUX_COUVERTURE_MIN des départements donne des distances trop longues (la
    # structure existe souvent sans être inscrite sous ce type), signalé dans chaque fichier de distances (28 octobre 2026)
    complet = L["couverture"].set_index("type")["complet"]
    for niv in ("epci", "dep", "reg"):
        c = L["comptes"][niv].pivot_table(index="code", columns="type", values="n", fill_value=0)
        base = noms[niv].set_index("code")[["nom", "pop"]].rename(columns={"pop": "population"})
        n = c.reindex(base.index).fillna(0)
        taux = n.div(base["population"].where(base["population"] > 0), axis=0) * 1e5
        w = pd.concat([base, n.add_prefix("n_"), taux.add_prefix("pour_100000_")], axis=1)
        w.index.name = "code"
        _csv(w.reset_index(), out / f"lieux_soins_{niv}.csv")
        d = (L.get("distances") or {}).get(niv)
        if isinstance(d, pd.DataFrame):
            d = d.assign(libelle_type=d["type"].map(types), nom=d["code"].map(noms[niv].set_index("code")["nom"]),
                         recensement_complet=d["type"].map(complet).fillna(False).astype(bool))
            _csv(d, out / f"distances_lieux_{niv}.csv")
    d = (L.get("distances") or {}).get("fr")
    if isinstance(d, pd.DataFrame):
        _csv(d.assign(libelle_type=d["type"].map(types),
                      recensement_complet=d["type"].map(complet).fillna(False).astype(bool)),
             out / "distances_lieux_france.csv")
    # CMP par public, chaque niveau et la France
    rc = []
    for niv in ("epci", "dep", "reg", "fr"):
        r = lieux_mod.repartition_cmp(x, niv).reset_index()
        rc.append(r.assign(niveau=niv, nom=r["code"].map(noms[niv].set_index("code")["nom"]) if niv in noms else "France"))
    _csv(pd.concat(rc, ignore_index=True)[["niveau", "code", "nom", "cmp", "adultes", "enfants", "les_deux", "non_precise",
                                          "antennes"]],
         out / "cmp_par_public.csv")
    es = L.get("escalier")
    if isinstance(es, pd.DataFrame):
        _csv(es.assign(libelle_type=es["type"].map(types)), out / "escalier_distance_lieux.csv")
    # analyses complémentaires des structures (pipeline/structures_analyses.py, 15 octobre 2026)
    def _nom(n, c):
        return noms[n].set_index("code")["nom"].get(c, "") if n in noms else "France"
    sb = L.get("sensibilite")
    if isinstance(sb, pd.DataFrame) and len(sb):
        _csv(sb, out / "sensibilite_confirmation.csv")
    de = L.get("double_eloignement")
    if isinstance(de, pd.DataFrame) and len(de):
        _csv(de, out / "double_eloignement.csv")
    ch = L.get("charge_cmp")
    if isinstance(ch, pd.DataFrame) and len(ch):
        _csv(ch.assign(nom=[_nom(n, c) for n, c in zip(ch["niveau"], ch["code"])]), out / "charge_cmp_sae.csv")
    ze = L.get("zones_eloignement")
    if isinstance(ze, pd.DataFrame) and len(ze):
        _csv(ze.assign(libelle_type=ze["type_structure"].map(types),
                       nom=ze["code"].map(noms["epci"].set_index("code")["nom"])), out / "zones_eloignement.csv")
    cs = L.get("concordance_sae")
    if isinstance(cs, pd.DataFrame) and len(cs):
        # noms selon le niveau, les codes des régions et des départements se recouvrent (« 01 », Ain et Guadeloupe)
        nom = [noms[n].set_index("code")["nom"].get(c, "") if n in noms else "France" for n, c in zip(cs["niveau"], cs["code"])]
        cols = ["niveau", "code", "nom", "cmp", "adultes", "enfants", "les_deux", "non_precise", "unites_ror", "sae_cmp",
                "sae_adultes", "sae_enfants", "ecart_relatif"]
        _csv(cs.assign(nom=nom)[[c for c in cols if c in cs or c == "nom"]], out / "concordance_cmp_sae.csv")
    ex = L.get("exercice")
    if isinstance(ex, pd.DataFrame) and len(ex):
        from .rapport import EXERCICE_COURTS
        nom = [noms[n].set_index("code")["nom"].get(c, "") if n in noms else "France" for n, c in zip(ex["niveau"], ex["code"])]
        _csv(ex.assign(nom=nom, libelle_type=ex["type"].map(EXERCICE_COURTS))[
            ["niveau", "code", "nom", "type", "libelle_type", "prof", "personnes"]], out / "exercice_structures.csv")
    ce = L.get("concordance_etablissements")
    if isinstance(ce, pd.DataFrame) and len(ce):
        _csv(ce[["ej", "nom", "dep_siege", "sae_cmp", "sae_adultes", "sae_enfants", "ici_cmp", "ici_adultes", "ici_enfants",
                 "unites_ror", "sae_cattp", "ici_cattp", "ecart", "statut", "statut_cattp"]]
             .sort_values(["statut", "ecart"]), out / "concordance_cmp_etablissements.csv")
    cc = L.get("concordance_cattp")
    if isinstance(cc, pd.DataFrame) and len(cc):
        nom = [noms[n].set_index("code")["nom"].get(c, "") if n in noms else "France" for n, c in zip(cc["niveau"], cc["code"])]
        _csv(cc.assign(nom=nom)[["niveau", "code", "nom", "cattp", "sae_cattp", "sae_cattp_adultes", "sae_cattp_enfants",
                                 "ecart_relatif", "concordance"]], out / "concordance_cattp_sae.csv")
    rl = L.get("relecture")
    if isinstance(rl, pd.DataFrame) and len(rl):
        _csv(rl, out / "relecture_structures.csv")
    # sectorisation psychiatrique des arrêtés des ARS reçus, publiée seulement après l'accord de Lucas
    # (sectorisation.PUBLIER), table par commune et contours des secteurs pour le plan de l'atlas
    from . import sectorisation as secto
    sc = L.get("sectorisation") or {}
    if secto.PUBLIER and isinstance(sc.get("secteurs"), pd.DataFrame) and len(sc["secteurs"]):
        _csv(secto.table_publiee(sc["secteurs"]), out / "secteurs_psychiatrie.csv")
        if sc.get("geojson"):
            (out / "secteurs_psychiatrie.geojson").write_text(
                json.dumps(sc["geojson"], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ig = L.get("inegalites") or {}
    cl, te, co = ig.get("classes"), ig.get("tests"), ig.get("concentration")
    if isinstance(cl, pd.DataFrame) and len(cl):
        if isinstance(te, pd.DataFrame) and len(te):
            cl = cl.merge(te, on="type", how="left")
        _csv(cl.assign(libelle_type=cl["type"].map(types)), out / "distances_lieux_classes_densite.csv")
    if isinstance(co, pd.DataFrame) and len(co):
        _csv(co.assign(libelle_type=co["type"].map(types)), out / "concentration_distance_lieux.csv")
    # distance de chaque commune au lieu le plus proche, types recensés presque partout (cartes des rapports)
    ok = set(L["couverture"].loc[L["couverture"]["complet"], "type"])
    # case vide quand le territoire de la commune n'a aucune structure de ce type (lieux.distances)
    dc = L["distances_communes"][[t for t in L["distances_communes"].columns if t in ok]].replace(np.inf, np.nan).round(1)
    com = noms["com"].set_index("code")
    dc = dc.add_prefix("dist_").assign(nom=com["nom"].reindex(dc.index).to_numpy(),
                                       dep=com["dep"].reindex(dc.index).to_numpy())
    dc.index.name = "code"
    _csv(dc.reset_index()[["code", "nom", "dep"] + [c for c in dc.columns if c.startswith("dist_")]],
         out / "distances_lieux_communes.csv")
    _csv(L["concordance"].rename(columns={k: f"lieux_{k}" for k in lieux_mod.PROVENANCES})
         .assign(libelle_type=lambda z: z["type"].map(types)), out / "concordance_finess_ror.csv")
    _csv(L["couverture"].assign(libelle_type=lambda z: z["type"].map(types)), out / "lieux_couverture.csv")
    _csv(L.get("references"), out / "lieux_references.csv")


def _lieux_site(agg, niv, codes):
    """Comptes et distance médiane des habitants par type de lieu, pour les types recensés presque partout."""
    L = getattr(agg, "lieux", None)
    if not L:
        return None, None
    ok = set(L["couverture"].loc[L["couverture"]["complet"], "type"])
    c = L["comptes"][niv]
    c = c[c["type"].isin(ok)]
    comptes = {k: [int(v) for v in g.set_index("code")["n"].reindex(codes).fillna(0)] for k, g in c.groupby("type")}
    for k in ok - set(comptes):
        comptes[k] = [0] * len(codes)
    d = (L.get("distances") or {}).get(niv)
    dist = None
    if isinstance(d, pd.DataFrame):
        d = d[d["type"].isin(ok)]
        dist = {k: [_r(v, 1) for v in g.set_index("code")["distance_mediane_km"].reindex(codes)] for k, g in d.groupby("type")}
    return comptes, dist


def _lieux_points(agg, ref):
    """Lieux montrés point par point dans l'atlas (config.LIEUX_ATLAS_GROUPES). Type, latitude et longitude en
    dix-millièmes de degré, nom (dans une liste à part), commune, provenance et précision de l'emplacement."""
    from . import lieux as lieux_mod
    L = getattr(agg, "lieux", None)
    if not L:
        return None
    x = L["lieux"]
    x = x[x["groupe"].isin(config.LIEUX_ATLAS_GROUPES) & x["lat"].notna()]
    types = [tp for tp in config.LIEUX_TYPES]
    couv = L["couverture"].set_index("type")
    ordre = {tp[0]: i for i, tp in enumerate(types)}
    noms = sorted(set(x["nom_affiche"].fillna("")))
    inom = {n: i for i, n in enumerate(noms)}
    prov, prec = list(lieux_mod.PROVENANCES), list(lieux_mod.PRECISIONS)
    pros = L["pros"]
    psy = [c for c in ("psychiatre", "pedopsychiatre", "psychologue", "infirmier", "orthophoniste", "psychomotricien")
           if c in pros]
    # niveau de confirmation (confirmation.NIVEAUX), public des CMP et signaux (antenne, CATTP au même lieu qu'un CMP),
    # pour l'encadré des structures d'un territoire et les points creux de la carte (16 octobre 2026)
    from . import confirmation as conf_mod
    niveaux = list(conf_mod.NIVEAUX)
    conf = x["confirmation"] if "confirmation" in x else pd.Series(None, index=x.index, dtype=object)
    publics, antennes = _publics_cmp(L["lieux"])
    meme_lieu = _cattp_meme_lieu_cmp(L["lieux"])
    pts = []
    for r, cf in zip(x.itertuples(), conf):
        # professionnels déclarés sur place, 0 quand le lieu a un numéro FINESS mais personne de ces professions,
        # rien quand le lieu n'a pas de numéro FINESS propre (inconnu)
        dec = pros.loc[r.lieu, psy].astype(int).tolist() if r.lieu in pros.index else None
        if dec is None and r.lieu.startswith("F"):
            dec = 0
        elif dec is not None and not any(dec):
            dec = 0
        # numéro FINESS partagé avec d'autres structures de la commune, l'effectif est celui de l'établissement
        npart = int(pros.at[r.lieu, "partage_par"]) if r.lieu in pros.index and "partage_par" in pros else 1
        pts.append([ordre[r.type], int(round(r.lat * 1e4)), int(round(r.lon * 1e4)), inom[r.nom_affiche or ""],
                    r.commune, prov.index(r.provenance), prec.index(r.precision) if r.precision in prec else len(prec) - 1,
                    dec, r.epci if isinstance(r.epci, str) else "", r.dep if isinstance(r.dep, str) else "",
                    r.reg if isinstance(r.reg, str) else "",
                    niveaux.index(cf) if cf in niveaux else None,
                    publics.get(r.lieu, "") if r.type == "lieu_cmp" else "",
                    (1 if r.type == "lieu_cmp" and r.lieu in antennes else 0)
                    + (2 if r.type == "lieu_cattp" and r.Index in meme_lieu else 0),
                    npart if npart > 1 else 0])
    return {"types": [{"id": tp[0], "lib": tp[1], "famille": tp[2], "groupe": tp[3],
                       "complet": bool(couv.at[tp[0], "complet"]) if tp[0] in couv.index else False,
                       "part": _r(couv.at[tp[0], "part_departements"]) if tp[0] in couv.index else None}
                      for tp in types],
            "provenances": [lieux_mod.PROVENANCES[k] for k in prov],
            "precisions": [lieux_mod.PRECISIONS[k] for k in prec],
            "professions": psy, "noms": noms, "pts": pts,
            # distance médiane des habitants et part à plus de 20 et 30 km, France entière, par type
            "fr": {r.type: [_r(r.distance_mediane_km, 1), _r(r.part_plus_20_km, 4), _r(r.part_plus_30_km, 4)]
                   for r in ((L.get("distances") or {}).get("fr", pd.DataFrame(columns=["type"]))).itertuples()},
            "communes": ref.communes[ref.communes["code"].isin(set(x["commune"]))].set_index("code")["nom"].to_dict(),
            "champs": ["type", "lat", "lon", "nom", "commune", "provenance", "precision", "declares", "epci", "dep", "reg",
                       "confirmation", "public", "signaux", "partage"],
            # niveaux de confirmation, libellé court, et types pour lesquels le niveau est établi
            "confirmations": [{"id": k, "lib": conf_mod.NIVEAUX_COURTS.get(k, conf_mod.NIVEAUX[k]),
                               "confirme": k != "bases", "classe": conf_mod.classe(k)} for k in niveaux],
            "classes": [{"id": k, "lib": v} for k, v in conf_mod.CLASSES.items()],
            "types_recoupes": sorted(conf_mod.TYPES_RECOUPES),
            "types_confirmes": sorted(set(x.loc[conf.notna(), "type"])),
            # inégalités de distance (12 octobre 2026), escalier selon le niveau de vie, classes de densité, indice de
            # concentration avec sa fourchette, lieux décrits dans les groupes de la typologie
            "escalier": _enregistrements(L.get("escalier"), ["type", "decile", "niveau_de_vie_min", "niveau_de_vie_max",
                                                             "distance_mediane_km", "part_plus_20_km"]),
            "classes": _enregistrements((L.get("inegalites") or {}).get("classes"),
                                        ["type", "classe", "population", "distance_mediane_km", "part_plus_20_km"]),
            "tests": _enregistrements((L.get("inegalites") or {}).get("tests"), ["type", "epsilon2", "q_bh"]),
            "concentration": _enregistrements((L.get("inegalites") or {}).get("concentration"),
                                              ["type", "indice_concentration", "ic95_bas", "ic95_haut"]),
            "typologie": _enregistrements(getattr(agg, "typologie_lieux", None),
                                          ["famille", "classe", "type", "lieux_pour_100000", "indice_vs_national",
                                           "distance_mediane_km"])}


def _publics_cmp(x: pd.DataFrame) -> tuple[dict, set]:
    """Public de chaque CMP, « a » adultes, « e » enfants et adolescents, « d » les deux, « n » non précisé, selon les
    types enfants où il figure (même règle que lieux.repartition_cmp), et CMP qui sont des antennes ou permanences."""
    from . import lieux as lieux_mod
    c = x[x["type"] == "lieu_cmp"]
    ad = set(x.loc[x["type"] == "lieu_cmp_adultes", "lieu"])
    en = set(x.loc[x["type"] == "lieu_cmp_enfants", "lieu"])
    pub = {k: ("d" if k in ad and k in en else "a" if k in ad else "e" if k in en else "n") for k in c["lieu"]}
    noms = (c["nom"] if "nom" in c else pd.Series("", index=c.index)).fillna(
        c["nom_finess"] if "nom_finess" in c else "").fillna("")
    ant = set(c.loc[noms.map(lieux_mod._simple).str.contains(lieux_mod._ANTENNE), "lieu"])
    return pub, ant


def _cattp_meme_lieu_cmp(x: pd.DataFrame) -> set:
    """Index des CATTP à l'adresse d'un CMP (même adresse normalisée, même commune, même gestionnaire quand les deux en
    ont un). Ils restent comptés à part, un CATTP étant le lieu d'activité déclaré, et sont signalés (décision de Lucas
    du 16 octobre 2026). Un CATTP annoncé par le nom d'un CMP compte aussi comme tel."""
    from .util import norm
    if "adresse" not in x:
        return set()
    cle = x["adresse"].map(lambda a: norm(a) if isinstance(a, str) and a.strip() else "") + "|" + x["commune"].astype(str)
    ej = x["ej"].fillna("") if "ej" in x else pd.Series("", index=x.index)
    cmp_ = (x["type"] == "lieu_cmp") & ~cle.str.startswith("|")
    par_cle = {}
    for k, e in zip(cle[cmp_], ej[cmp_]):
        par_cle.setdefault(k, set()).add(e)
    out = set()
    for i in x.index[(x["type"] == "lieu_cattp")]:
        k, e = cle[i], ej[i]
        if x.at[i, "provenance"] == "nom_cmp" or (not k.startswith("|") and k in par_cle
                                                  and (not e or "" in par_cle[k] or e in par_cle[k])):
            out.add(i)
    return out


def _verifications_site():
    from . import verifications_lieux
    v = verifications_lieux.charger()
    return [{k: (bool(r[k]) if k == "a_refaire" else r[k]) for k in ["code", "etablissement", "date", "source", "adresse",
                                                                    "constat", "a_refaire"]} for _, r in v.iterrows()]


def _enregistrements(t, cols):
    """Lignes d'un tableau pour le site, nombres arrondis à quatre chiffres significatifs."""
    if not isinstance(t, pd.DataFrame) or t.empty:
        return None
    t = t[[c for c in cols if c in t]]
    return [{k: (float(f"{v:.4g}") if isinstance(v, float) and v == v else (None if isinstance(v, float) else v))
             for k, v in r.items()} for r in t.to_dict("records")]


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
    cols = ["inscrits", "avec_activite", "sans_lieu", "avec_lieu", "sans_soins_seulement", "a_distance_seulement",
            "dans_densites"]
    return {r["prof"]: [None if c not in r or pd.isna(r[c]) else int(r[c]) for c in cols] for _i, r in t.iterrows()}


def _addicto_atlas(agg, ref, insee) -> dict:
    """Encadré « Addictologie » de l'atlas (22 octobre 2026), consommations régionales avec fourchette et offre,
    mêmes calculs que la partie du rapport santé mentale."""
    from .rapport import offre_addicto
    spf = (insee or {}).get("odisse") or {}
    t = spf.get("table")
    out = {"offre": [], "ind": [], "regions": ref.regs.set_index("code")["nom"].to_dict()}
    L = getattr(agg, "lieux", None) or {}
    nat = agg.national[agg.national["mode"] == "all"].set_index("prof")["n"] if hasattr(agg, "national") else {}
    out["offre"] = offre_addicto(L.get("lieux"), nat.get("q_addictologie") if len(nat) else None)
    if isinstance(t, pd.DataFrame):
        defs = {d["id"]: d for d in spf.get("defs", [])}
        for i in config.ADDICTO_ODISSE:
            x = t[t["indicateur"] == i]
            if x.empty:
                continue
            d = defs.get(i, {})
            ph = next((o.get("phrase") for o in config.ODISSE if o["id"] == i), None)
            out["ind"].append({"id": i, "lib": d.get("libelle", i), "unite": d.get("unite", ""), "annee": d.get("annee"),
                               "phrase": ph,
                               "v": {c: [round(float(v), 2), None if pd.isna(lo) else round(float(lo), 2),
                                         None if pd.isna(hi) else round(float(hi), 2)]
                                     for c, v, lo, hi in zip(x["code"], x["valeur"], x["ic_bas"], x["ic_haut"])}})
    return out


def _exercice_atlas(L, top) -> dict:
    """Professionnels déclarés dans les structures de santé mentale à numéro FINESS propre, pour l'encadré « Où ils
    exercent » de l'atlas (France et départements, mêmes clés que les secteurs)."""
    ex = (L or {}).get("exercice")
    if not isinstance(ex, pd.DataFrame) or ex.empty:
        return {}
    from .rapport import EXERCICE_COURTS
    e = ex[ex["niveau"].isin(["fr", "dep"]) & (ex["type"] != "ensemble")]
    e = e.assign(code=e["code"].where(e["niveau"] != "fr", "FR"), n=e["personnes"],
                 type_lib=e["type"].map(EXERCICE_COURTS))
    return top(e, "type_lib")


def _site(agg, ref, professions, insee, R, serie, jour):
    ctx_def = [{k: d[k] for k in ("id", "label", "unite", "explication", "source", "famille", "licence", "groupe", "niveaux",
                                  "licence_id", "niveaux_codes", "agregation", "type_valeur", "page_source")}
               | ({"non_publies": d["non_publies"]} if d.get("non_publies") else {})
               # champs des descripteurs de la voie légère (domaine, sens...), absents des autres indicateurs
               | {k: d[k] for k in indicateurs.CHAMPS_DESCRIPTEURS if d.get(k) not in (None, "", [], {})}
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
        if niv == "dep":
            tab_dep = tab["all"]
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
        # lieux de soins (FINESS et ROR réunis), comptes et distance médiane des habitants par type
        lc, ld = _lieux_site(agg, niv, codes)
        if lc:
            bloc["lieux"] = lc
        if ld:
            bloc["lieux_dist"] = ld
        # CMP par public, pour dire les CMP qui accueillent les deux publics et ceux au public non précisé
        if getattr(agg, "lieux", None):
            from . import lieux as lieux_mod
            rc = lieux_mod.repartition_cmp(agg.lieux["lieux"], niv).reindex(codes).fillna(0).astype(int)
            bloc["cmp_public"] = {k: rc[k].tolist() for k in ("adultes", "enfants", "les_deux", "non_precise", "antennes")}
            cs = agg.lieux.get("concordance_sae")
            if isinstance(cs, pd.DataFrame) and niv in ("dep", "reg"):
                c = cs[cs["niveau"] == niv].set_index("code")
                bloc["cmp_sae"] = [[int(c.at[k, "sae_cmp"]), c.at[k, "concordance"]] if k in c.index and
                                   isinstance(c.at[k, "concordance"], str) else None for k in codes]
        # centres médico-psychologiques (FINESS et ROR réunis depuis le 12 octobre 2026), pour nuancer « aucun
        # psychiatre déclaré » (9 octobre 2026)
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
            # temps non fiable (contredit par la distance au CMP, analyses.temps_acces) retiré, territoires listés
            fiable = t["fiable"] if "fiable" in t else pd.Series(True, index=t.index)
            bloc["route"] = {e: [None if pd.isna(r.part_population_a_plus_de_20_min) or r.fiable is False else
                                 [_r(r.part_population_a_plus_de_20_min, 4), _r(r.temps_median_min, 1)]
                                 for r in g.assign(fiable=fiable.astype(object)).set_index("code").reindex(codes)
                                 .itertuples()]
                             for e, g in t.groupby("equipement")}
            masque = t[~fiable.astype(bool)]
            if len(masque):
                pos = {c: k for k, c in enumerate(codes)}
                bloc["route_masque"] = {e: sorted(pos[c] for c in g["code"] if c in pos)
                                        for e, g in masque.groupby("equipement")}
        # personnes déclarant ici une activité sans soins à la population (sièges, contrôle médical...) ou de
        # soins à distance (téléconsultation), non comptées dans la densité du territoire
        ap = (agg.particulieres or {}).get(niv)
        if isinstance(ap, pd.DataFrame) and len(ap):
            for cle, cat in (("hors_soins", "sans_soins"), ("a_distance", "a_distance")):
                a = ap[ap["categorie"] == cat]
                bloc[cle] = {p: {c: int(n) for c, n in zip(g["code"], g["n"])} for p, g in a.groupby("prof")}
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
        # pour les lieux de soins, l'atlas ne garde que le mode « tous modes » (atlas plus léger), les autres modes
        # restent dans correlations_contexte.csv
        lieux_v = cc["variable"].astype(str).str.startswith(("lieux_", "dist_"))
        cc = cc[~lieux_v | (cc["mode"] == "all")]
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
                 # part de l'exercice libéral, indicateur de « Croiser deux indicateurs » calculé dans l'atlas avec
                 # la même règle que analyses.part_liberal (23 octobre 2026)
                 "part_liberal": {"minimum": config.PART_LIBERAL_EFFECTIF_MIN,
                                  "professions": professions_part_liberal(nat, tab_dep)},
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
        "exercice": _exercice_atlas(getattr(agg, "lieux", None), top),
        "addicto": _addicto_atlas(agg, ref, insee),
        "categories": top(agg.categories, "categorie", k=500),
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
                        "territoires": L.get("territoires", {}), "nom": limites_mod.NOMS.get(k, k),
                        "court": config.LIMITES_COURT.get(k, "")}
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
        "lieux": _lieux_points(agg, ref),
        # vérifications des lieux sur d'autres sources, par département (13 octobre 2026)
        "verifications_lieux": _verifications_site(),
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
    # questions préparées des descripteurs de la voie légère, avec leur famille d'après leurs indicateurs
    fam_ind = {d["id"]: d.get("famille", "") for d in indicateurs.liste(insee)}
    for xa, yb, theme, q in cr.attrs.get("questions", []):
        questions.setdefault(theme, (fam_ind.get(yb) or fam_ind.get(xa, ""), q))

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
                    "xk": r.mesure, "yk": r.variable,
                    "rho": _r(r.rho, 3), "lo": _r(r.ic95_bas, 3), "hi": _r(r.ic95_haut, 3),
                    "rp": _r(getattr(r, "rho_partiel_densite", None), 3),
                    "lop": _r(getattr(r, "ic95_bas_partiel", None), 3), "hip": _r(getattr(r, "ic95_haut_partiel", None), 3),
                    "n": int(r.departements),
                    "pts": [[c, _r(a, 3), _r(b, 3)] for c, a, b in pts.get((r.mesure, r.variable), [])]}
                   # correction de Benjamini-Hochberg, présente quand des questions préparées s'y ajoutent
                   | ({"q": _r(r.q_bh, 4)} if _r(getattr(r, "q_bh", None), 4) is not None else {}))
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
    ok = (lambda e: bool(fr.at[e, "fiable"])) if "fiable" in fr else (lambda e: True)
    return [{"id": e, "lib": lib, "fam": fam, "prof": prof,
             "fr": [_r(fr.at[e, "part_population_a_plus_de_20_min"], 4), _r(fr.at[e, "temps_median_min"], 1)]
             if ok(e) else None}
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
