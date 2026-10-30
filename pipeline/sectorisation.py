"""Sectorisation psychiatrique et structures de soins (29 octobre 2026).

Confronte les CMP de FINESS et du ROR réunis aux secteurs des arrêtés des ARS (pipeline/sources/sectorisation.py), pour
chaque région dont l'arrêté est disponible. Un CMP pour adultes se lit face aux secteurs de psychiatrie générale, un CMP
pour enfants face à ceux de psychiatrie infanto-juvénile. Rien n'est corrigé ici, les constats servent à vérifier les
structures (rattachement à leur établissement, CMP sans secteur, secteur sans CMP) et à poser des questions aux
établissements.

Constats par CMP :
- « porteur du secteur », l'établissement du CMP (entité juridique FINESS) porte le secteur de la commune du CMP ;
- « autre secteur du même établissement », il porte des secteurs de ce type dans la région, mais pas celui de la
  commune (CMP intersectoriel ou implanté chez le voisin, à vérifier) ;
- « établissement sans secteur de ce type », il n'en porte aucun dans la région (CMP d'un autre gestionnaire, ou
  inscrit sous un autre numéro que l'établissement de l'arrêté) ;
- « commune sans secteur », la commune n'a pas de secteur de ce type dans l'arrêté.
Le code de secteur cité dans le nom du CMP (colonne secteur, « 59G22 ») est comparé à l'arrêté quand il existe.
Par secteur, le nombre de CMP de son établissement porteur sur ses communes, zéro signalant un secteur sans CMP sur son
territoire (ses habitants vont alors dans un CMP voisin)."""
from __future__ import annotations

import pandas as pd

from . import config
from .util import JOURNAL

# rien ne part dans les résultats publiés avant que la sectorisation ait été montrée à Lucas (demande du 29 octobre
# 2026) ; d'ici là les tables vont dans donnees/intermediaire/sectorisation, jamais publié
PUBLIER = True
DOSSIER_INTERNE = config.INTER / "sectorisation"
TYPE_PUBLIC = {"A": "G", "E": "I"}
CONSTATS = ["porteur du secteur", "autre secteur du même établissement", "établissement sans secteur de ce type",
            "commune sans secteur"]


def cmp_par_public(lieux: pd.DataFrame) -> pd.DataFrame:
    """CMP pour adultes et pour enfants, une ligne par CMP et par public (colonnes id, nom, commune, ej, public,
    secteur_nom). Lit les types enfants lieu_cmp_adultes et lieu_cmp_enfants, ou le suffixe |A et |E de la clé."""
    col_ej = "ej" if "ej" in lieux else "entite_juridique"
    col_id = "id_structure" if "id_structure" in lieux else "lieu"
    x = lieux[lieux["type"].isin(["lieu_cmp_adultes", "lieu_cmp_enfants"])]
    # un CMP sans public connu (FINESS seul, sans âges déclarés) se lit face aux deux types de secteur (public « ? »)
    sans = lieux[(lieux["type"] == "lieu_cmp") & ~lieux[col_id].isin(x[col_id])]
    x = pd.concat([x, sans])
    # pendant l'exécution, la table des structures n'a ni nom affiché exporté ni code de secteur, ils se calculent ici
    # comme dans lieux_soins.csv (pipeline/export.py)
    nom = x["nom_affiche"].fillna(x["nom"]) if "nom_affiche" in x else x["nom"]
    if "secteur" in x:
        secteur = x["secteur"]
    else:
        from .lieux import code_secteur
        secteur = [code_secteur(a, b, c) for a, b, c in zip(nom, x["nom"], x.get("nom_finess", pd.Series(
            index=x.index, dtype=object)))]
    return pd.DataFrame({"id": x[col_id], "nom": nom, "commune": x["commune"], "ej": x[col_ej],
                         "public": x["type"].map({"lieu_cmp_adultes": "A", "lieu_cmp_enfants": "E"}).fillna("?"),
                         "secteur_nom": secteur}).reset_index(drop=True)


def confronter(secteurs: pd.DataFrame, cmp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Constat pour chaque CMP des régions couvertes, et nombre de CMP de l'établissement porteur par secteur."""
    s = secteurs.dropna(subset=["commune"])
    regions = set(s["region"])
    deps = set(s["dep"])
    c = cmp[cmp["commune"].str[:2].isin(deps) | cmp["commune"].str[:3].isin(deps)].copy()
    # public inconnu, une ligne par type de secteur, le constat retenu est le meilleur des deux
    c = pd.concat([c[c["public"] != "?"].assign(type=lambda d: d["public"].map(TYPE_PUBLIC))]
                  + [c[c["public"] == "?"].assign(type=ty) for ty in ("G", "I")], ignore_index=True)
    par_com = s.groupby(["commune", "type"]).agg(secteurs=("secteur", lambda v: sorted(set(v))),
                                                  porteurs=("ej", lambda v: sorted(set(v.dropna()))))
    porteurs_type = s.groupby("type")["ej"].agg(lambda v: set(v.dropna()))
    secteurs_ej = s.groupby(["ej", "type"])["secteur"].agg(lambda v: sorted(set(v)))

    def constat(r):
        k = (r["commune"], r["type"])
        if k not in par_com.index:
            return "commune sans secteur"
        if r["ej"] in par_com.at[k, "porteurs"]:
            return "porteur du secteur"
        if r["ej"] in porteurs_type.get(r["type"], set()):
            return "autre secteur du même établissement"
        return "établissement sans secteur de ce type"
    c["constat"] = c.apply(constat, axis=1)
    # CMP sans public, garder le meilleur des deux constats (ordre de CONSTATS)
    c["_rang"] = c["constat"].map(CONSTATS.index)
    double = c["public"] == "?"
    garde = c[double].sort_values("_rang").drop_duplicates("id").index
    rattache = c[double].copy()    # les deux types servent au compte des CMP par secteur
    c = pd.concat([c[~double], c.loc[garde]]).drop(columns="_rang")
    c["secteurs_commune"] = [", ".join(par_com.at[(a, b), "secteurs"]) if (a, b) in par_com.index else ""
                             for a, b in zip(c["commune"], c["type"])]
    c["secteurs_etablissement"] = [", ".join(secteurs_ej.get((e, ty), [])) for e, ty in zip(c["ej"], c["type"])]
    # code de secteur cité dans le nom, présent dans l'arrêté et porté par l'établissement du CMP
    connus = s.groupby("secteur")["ej"].agg(lambda v: set(v.dropna()))

    def cite(r):
        sn = r["secteur_nom"]
        if not isinstance(sn, str) or not sn:
            return ""
        codes = [x.strip() for x in sn.split(",") if x.strip()]
        if any(x not in connus.index for x in codes):
            return "secteur cité absent de l'arrêté"
        return "secteur cité porté par l'établissement" if all(r["ej"] in connus[x] for x in codes) else \
            "secteur cité porté par un autre établissement"
    c["secteur_cite"] = c.apply(cite, axis=1)
    # CMP du porteur sur les communes de chaque secteur
    sc = s[["secteur", "type", "ej", "commune", "etablissement"]].drop_duplicates()
    tous = pd.concat([c[c["public"] != "?"], rattache])[["commune", "type", "ej", "id"]]
    m = sc.merge(tous, on=["commune", "type", "ej"], how="left")
    par_secteur = m.groupby(["secteur", "type", "etablissement", "ej"], dropna=False).agg(
        communes=("commune", "nunique"), cmp=("id", "nunique")).reset_index()
    n = c["constat"].value_counts()
    JOURNAL.controle("Sectorisation et CMP, " + ", ".join(sorted(regions)),
                     f"{len(c)} CMP par public ; " + ", ".join(f"{k} {int(n.get(k, 0))}" for k in CONSTATS)
                     + f" ; secteurs sans CMP de leur établissement sur leurs communes "
                       f"{int((par_secteur['cmp'] == 0).sum())} sur {len(par_secteur)}")
    return c, par_secteur


def appliquer(ref, lieux: pd.DataFrame | None) -> dict | None:
    """Secteurs de toutes les régions disponibles et constats des CMP, écrits dans donnees/intermediaire/sectorisation
    (secteurs.csv, cmp.csv, par_secteur.csv). None quand aucun arrêté n'est disponible."""
    from .sources import sectorisation as source
    secteurs = source.charger(ref)
    if secteurs is None:
        return None
    res = {"secteurs": secteurs}
    if isinstance(lieux, pd.DataFrame) and len(lieux):
        res["cmp"], res["par_secteur"] = confronter(secteurs, cmp_par_public(lieux))
    DOSSIER_INTERNE.mkdir(parents=True, exist_ok=True)
    for nom, t in res.items():
        t.to_csv(DOSSIER_INTERNE / f"{nom}.csv", sep=";", index=False, encoding="utf-8-sig")
    if PUBLIER:
        from . import cartes
        res["geojson"] = geojson_secteurs(secteurs, cartes.fonds_communes(ref))
    return res


def table_publiee(secteurs: pd.DataFrame) -> pd.DataFrame:
    """Table publiée de la sectorisation, une ligne par commune, type de secteur et secteur, avec la source de chaque
    ligne (arrêté de l'ARS et sa date) et la façon dont la commune actuelle a été retrouvée."""
    from .sources import sectorisation as source
    types = {k: v for d in source.descriptions() for k, v in d.get("types", {}).items()}
    t = secteurs.assign(type_secteur=secteurs["type"].map(types).fillna(secteurs["type"]))
    return t[["region", "dep", "commune", "partie", "type", "type_secteur", "secteur", "etablissement", "ej",
              "code_arrete", "nom_arrete", "rattachement", "document", "date_document"]] \
        .rename(columns={"region": "reg", "etablissement": "etablissement_responsable", "ej": "finess_entite_juridique",
                         "secteur": "secteur_psychiatrie"}) \
        .sort_values(["reg", "type", "secteur_psychiatrie", "commune"])


def geojson_secteurs(secteurs: pd.DataFrame, fonds: dict, decimales: int = 4) -> dict | None:
    """Contours des secteurs pour le plan de l'atlas (couche « secteurs de psychiatrie », demande de Lucas du 29 octobre
    2026), un objet par secteur et par type, plus un objet par ville partagée entre secteurs d'un même type. Chaque
    secteur porte son code, son type, l'établissement porteur, sa teinte (deux voisins jamais de la même, coloriage de
    cartes.teintes_secteurs sur toute la région), la source et la date de l'arrêté et les limites signalées par l'ARS.
    fonds, contours des communes par département (cartes.fonds_communes)."""
    import shapely
    from shapely.geometry import mapping
    from . import cartes
    from .sources import sectorisation as source
    if secteurs is None or secteurs.empty or not fonds:
        return None
    descr = {d["region"]: d for d in source.descriptions()}
    feats = []

    def arrondi(g):
        return shapely.set_precision(g, 10 ** -decimales)

    for (reg, ty), x in secteurs.dropna(subset=["commune"]).groupby(["region", "type"]):
        d = descr.get(reg, {})
        geoms = {c: g for dep in x["dep"].unique() for c, g in (fonds.get(dep) or {}).items() if c in set(x["commune"])}
        par_com = x.groupby("commune")["secteur"].agg(lambda v: sorted(set(v))).to_dict()
        poly, teinte, _v = cartes.teintes_secteurs(geoms, par_com)
        porteur = x.drop_duplicates("secteur").set_index("secteur")[["etablissement", "ej"]]
        commun = {"region": reg, "type": ty, "type_lib": d.get("types", {}).get(ty, ty),
                  "source": d.get("source_courte") or f"{d.get('emetteur', '')}, {d.get('document', '')}".strip(", "),
                  "date": d.get("date_document", "")}

        def limites(etabs):
            """Limites signalées par l'ARS, seulement celles qui concernent l'établissement du secteur ou toute la
            région (limite de Saint-Quentin sur les seuls secteurs du CH de Saint-Quentin et de l'EPSM de l'Aisne)."""
            out = []
            for li in d.get("limites", []):
                li = li if isinstance(li, dict) else {"texte": li}
                if not li.get("etablissements") or set(etabs) & set(li["etablissements"]):
                    out.append(li["texte"])
            return out
        for s, g in poly.items():
            feats.append({"type": "Feature", "geometry": mapping(arrondi(g)),
                          "properties": {**commun, "secteur": s, "etablissement": porteur.at[s, "etablissement"],
                                         "ej": porteur.at[s, "ej"], "teinte": int(teinte[s]),
                                         "limites": limites([porteur.at[s, "etablissement"]])}})
        for c, ss in par_com.items():
            if len(ss) > 1 and c in geoms:
                feats.append({"type": "Feature", "geometry": mapping(arrondi(geoms[c])),
                              "properties": {**commun, "secteur": None, "partagee": ss, "commune": c,
                                             "etablissement": ", ".join(sorted(set(porteur.loc[ss, "etablissement"]))),
                                             "limites": limites(list(porteur.loc[ss, "etablissement"]))}})
    return {"type": "FeatureCollection", "regions": sorted(descr), "teintes": cartes.TEINTES_SECTEURS,
            "features": feats}
