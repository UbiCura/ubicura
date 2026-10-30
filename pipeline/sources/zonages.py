"""Zonages des professionnels de santé libéraux arrêtés par les ARS (fichier national d'Atlasanté, réseau des ARS,
Licence Ouverte 2.0), en brouillon : lus, contrôlés et écrits dans donnees/intermediaire/zonages, jamais publiés tant
que PUBLIER est faux (décision de Lucas du 30 octobre 2026, intégration en brouillon jusqu'à la fiche de territoire en
bandes). Note de faisabilité docs/note_zonages_2026-10-30.md.

Jeu data.gouv.fr 69bd265e2545e17d2d65fd37, « Zonages des professionnels de santé libéraux », lu par l'API de data.gouv le
30 octobre 2026 (licence « lov2 », mise à jour tous les deux mois). Trois tables : communes (avec les arrondissements de
Paris, Lyon et Marseille), quartiers prioritaires de la ville et grands quartiers de La Réunion, où le zonage des
médecins est fait par grand quartier. Six professions, chacune avec la catégorie de zonage de la commune et la date de
l'arrêté de l'ARS. Les catégories gardent le vocabulaire officiel, expliqué, et ne sont jamais appliquées à un
territoire nommé dans une phrase (décision de Lucas du 30 octobre 2026).

La part de la population d'un territoire dans chaque catégorie se calcule sur les communes du référentiel. Une commune
découpée (arrondissements, grands quartiers de La Réunion pour les médecins) a une part par catégorie, d'après la
population de ses morceaux. Les professions ne s'additionnent jamais."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .. import config
from ..util import JOURNAL, lire_meta, log, norm, ressources_datagouv, telecharger, trouver_colonne

PUBLIER = False
# jeu data.gouv.fr vérifié par l'API le 30 octobre 2026, à reporter dans config.SOURCES_SUIVIES et SOURCES_INFO à la
# sortie du brouillon (fichier partagé)
JEU = "69bd265e2545e17d2d65fd37"
PAGE = "https://www.data.gouv.fr/datasets/zonages-des-professionnels-de-sante-liberaux"
SOURCE = "Atlasanté, zonages des professionnels de santé libéraux"
DOSSIER = config.BRUT / "zonages"
DOSSIER_INTERNE = config.INTER / "zonages"
# ressources du jeu, par motif sur leur titre
TABLES = {"com": r"zonages[-_ ]com", "qpv": r"zonages[-_ ]qpv", "gq": r"zonages[-_ ]gq"}

# professions du fichier (préfixe des colonnes), identifiant de profession du site, territoire de construction
PROFESSIONS = {"zmed": ("medecin_generaliste", "Médecins", "territoires de vie-santé"),
               "zide": ("infirmier", "Infirmiers", "bassins de vie ou cantons-villes"),
               "zmk": ("masseur_kinesitherapeute", "Masseurs-kinésithérapeutes", "bassins de vie ou cantons-villes"),
               "zsf": ("sage_femme", "Sages-femmes", "bassins de vie ou cantons-villes"),
               "zdent": ("chirurgien_dentiste", "Chirurgiens-dentistes", "territoires de vie-santé"),
               "zortho": ("orthophoniste", "Orthophonistes", "bassins de vie ou cantons-villes")}

# catégories officielles, code normalisé vers leur libellé (vocabulaire réglementaire gardé, expliqué sur la page
# méthode) ; un code inconnu est signalé par un contrôle et n'est jamais deviné
CATEGORIES = {
    "1_zip": "zone d'intervention prioritaire (ZIP)",
    "2_zac": "zone d'action complémentaire (ZAC)",
    "3_hz": "hors zonage",
    "4_zar": "catégorie régionale (ZAR)",
    "1_tres_sous_dotee": "zone très sous-dotée",
    "1b_sous_dense": "zone sous-dense",
    "2_sous_dotee": "zone sous-dotée",
    "3_intermediaire": "zone intermédiaire",
    "4_tres_dotee": "zone très dotée",
    "5_sur_dotee": "zone sur-dotée",
    "5b_non_prioritaire": "zone non prioritaire",
    "nc": "non classée",
}
# zones « sous-denses » des médecins au sens de l'article L1434-4 du code de la santé publique (ZIP et ZAC)
SOUS_DENSES_MEDECINS = ("1_zip", "2_zac")


def code_categorie(v) -> str | None:
    """Code normalisé d'une catégorie (« 3_Intermediaire » et « 3_intermediaire » donnent le même), « nc » pour toutes
    les formes non classées (collectivités d'outre-mer, détail au niveau du quartier prioritaire)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    t = norm(str(v)).replace(" ", "_")
    if t.startswith("nc"):
        return "nc"
    return t or None


def ville_arrondissement(code: str) -> str:
    """Ville d'un arrondissement municipal, Paris (751xx), Lyon (6938x) et Marseille (132xx)."""
    return "75056" if code.startswith("751") else "69123" if code.startswith("6938") else "13055" if code.startswith("132") else code


def _date(v) -> str | None:
    m = re.match(r"^\s*(\d{2})/(\d{2})/(\d{4})", str(v or ""))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _nombre(v) -> float:
    return pd.to_numeric(re.sub(r"[^\d]", "", str(v or "")) or np.nan, errors="coerce")


def _telecharger(hors_ligne=False, rafraichir=False) -> dict:
    """Les trois tables en cache dans donnees/brut/zonages, adresses lues par l'API de data.gouv (jamais devinées),
    date de chaque ressource consignée comme version du producteur."""
    DOSSIER.mkdir(parents=True, exist_ok=True)
    chemins = {k: DOSSIER / f"t_zonages_{k}.csv" for k in TABLES}
    if hors_ligne:
        manque = [k for k, c in chemins.items() if not c.exists()]
        if manque:
            raise FileNotFoundError(f"tables absentes du cache : {', '.join(manque)}")
        return chemins
    res = ressources_datagouv(JEU)
    for k, motif in TABLES.items():
        r = next((x for x in res if re.search(motif, x["titre"], re.I) and x["format"] == "csv"), None)
        if r is None:
            raise IOError(f"ressource {k} introuvable dans le jeu {JEU}")
        telecharger(r["url"], chemins[k], "zonages", rafraichir, taille_min=1000,
                    extra_meta={"maj_source": r["maj"], "titre": r["titre"]})
    return chemins


def _lire(chemin) -> pd.DataFrame:
    t = pd.read_csv(chemin, dtype=str, encoding="utf-8", sep=",")
    t.columns = [c.strip() for c in t.columns]   # espaces en fin de nom dans la table des grands quartiers
    return t


def _colonnes(t: pd.DataFrame, prefixe: str) -> tuple[str | None, str | None]:
    """Colonnes de la catégorie et de la date d'arrêté d'une profession, trouvées par motif (la table des quartiers
    prioritaires nomme la catégorie de la commune « zmed_niveau_tvs » et non « zmed_niveau_com »)."""
    cat = trouver_colonne(t.columns, [rf"^{prefixe}[ _]niveau$", rf"^{prefixe}[ _]niveau[ _](com|tvs)$"], False)
    dat = trouver_colonne(t.columns, [rf"^{prefixe}[ _]date[ _]arrete$"], False)
    return cat, dat


def lire(chemins: dict, ref) -> pd.DataFrame:
    """Table longue (commune, profession, categorie, part, date_arrete, territoire, unite) : une ligne par commune du
    référentiel, profession et catégorie, part de la population de la commune dans cette catégorie (1 sauf commune
    découpée en arrondissements ou, pour les médecins de La Réunion, en grands quartiers)."""
    com = _lire(chemins["com"])
    c_niv = trouver_colonne(com.columns, [r"^niveau$"])
    c_code = trouver_colonne(com.columns, [r"^code$"])
    c_com = trouver_colonne(com.columns, [r"^com[ _]code$"])
    c_pop = trouver_colonne(com.columns, [r"^pop$"])
    com["_code"] = com[c_code].str.strip().str.zfill(5)
    com["_com"] = com[c_com].str.strip().str.zfill(5)
    com["_pop"] = com[c_pop].map(_nombre)
    # communes découpées en arrondissements : les arrondissements portent le zonage (sous leur propre code, 75101 à
    # 75120, 69381 à 69389, 13201 à 13216), la ligne de la ville est « NC » et n'est pas reprise
    arm = com[c_niv].str.strip() == "ARM"
    com.loc[arm, "_com"] = com.loc[arm, "_code"].map(ville_arrondissement)
    villes_arm = set(com.loc[arm, "_com"])
    unites = com[(com[c_niv].str.strip().isin(["COM", "ARM"])) & ~((com[c_niv].str.strip() == "COM") & com["_com"].isin(villes_arm))]
    gq = _lire(chemins["gq"])
    g_com = trouver_colonne(gq.columns, [r"^com[ _]code$"])
    g_pop = trouver_colonne(gq.columns, [r"^pop$"])
    gq["_com"] = gq[g_com].str.strip().str.zfill(5)
    gq["_pop"] = gq[g_pop].map(_nombre)
    lignes = []
    for pre, (prof, _lab, terr) in PROFESSIONS.items():
        cat, dat = _colonnes(unites, pre)
        if cat is None:
            JOURNAL.note(SOURCE, "erreur", f"colonne de la catégorie {pre} introuvable")
            continue
        x = unites.assign(categorie=unites[cat].map(code_categorie), date_arrete=unites[dat].map(_date) if dat else None)
        # médecins de La Réunion, zonage par grand quartier (la table des communes les dit « NC »)
        if pre == "zmed":
            gc, gd = _colonnes(gq, pre)
            if gc:
                g = gq.assign(categorie=gq[gc].map(code_categorie), date_arrete=gq[gd].map(_date) if gd else None)
                x = pd.concat([x[~x["_com"].isin(set(g["_com"]))],
                               g.assign(_code=g[trouver_colonne(gq.columns, [r"^code$"])].str.strip())], ignore_index=True)
        x = x.dropna(subset=["categorie"])
        poids = x.groupby(["_com", "categorie"])["_pop"].sum()
        tot = x.groupby("_com")["_pop"].sum()
        part = (poids / tot.reindex(poids.index.get_level_values(0)).to_numpy()).rename("part").reset_index()
        part.loc[part["part"].isna(), "part"] = 1.0
        dates = x.groupby(["_com", "categorie"])["date_arrete"].agg(lambda s: ",".join(sorted(set(s.dropna()))))
        part = part.join(dates, on=["_com", "categorie"])
        lignes.append(part.assign(profession=prof, territoire=terr, unite=pre))
    t = pd.concat(lignes, ignore_index=True).rename(columns={"_com": "commune"})
    t["libelle"] = t["categorie"].map(CATEGORIES)
    actuelles = set(ref.communes["code"])
    return t[t["commune"].isin(actuelles)][["commune", "profession", "categorie", "libelle", "part", "date_arrete",
                                            "territoire", "unite"]]


def parts_territoires(t: pd.DataFrame, ref) -> dict:
    """Part de la population de chaque intercommunalité, département et région dans chaque catégorie, par profession,
    pondérée par la population des communes du référentiel."""
    com = ref.communes.set_index("code")[["pop", "epci", "dep", "reg"]]
    x = t.join(com, on="commune")
    x["pop_cat"] = x["pop"].astype(float) * x["part"]
    out = {}
    for niv in ("epci", "dep", "reg"):
        p = x.groupby([niv, "profession", "categorie"])["pop_cat"].sum()
        tot = com.groupby(niv)["pop"].sum().astype(float)
        out[niv] = (p / tot.reindex(p.index.get_level_values(0)).to_numpy()).rename("part_population").reset_index() \
            .rename(columns={niv: "code"})
    return out


def controler(t: pd.DataFrame, ref, chemins: dict) -> dict:
    """Contrôles du brouillon, écrits au journal : communes du référentiel retrouvées pour chaque profession, aucune
    catégorie inconnue, parts d'une commune qui font 1, part nationale de la population par catégorie, et repère publié
    d'Auvergne-Rhône-Alpes (ZIP 28,5 %, ZAC 49,2 %, ARS, zonage des médecins de 2025, à un point près)."""
    r = {}
    actuelles = set(ref.communes["code"])
    for prof, g in t.groupby("profession"):
        manque = actuelles - set(g["commune"])
        r[f"communes_sans_{prof}"] = len(manque)
    inconnues = sorted(set(t["categorie"]) - set(CATEGORIES))
    r["categories_inconnues"] = inconnues
    somme = t.groupby(["commune", "profession"])["part"].sum()
    r["parts_hors_1"] = int(((somme - 1).abs() > 1e-6).sum())
    parts = parts_territoires(t, ref)
    reg = parts["reg"]
    med = reg[(reg["profession"] == "medecin_generaliste") & (reg["code"] == "84")].set_index("categorie")["part_population"]
    r["ara_zip"], r["ara_zac"] = float(med.get("1_zip", np.nan)), float(med.get("2_zac", np.nan))
    pop = ref.communes.set_index("code")["pop"].astype(float)
    x = t.assign(p=t["commune"].map(pop) * t["part"])
    fr = (x.groupby(["profession", "categorie"])["p"].sum() / pop.sum()).round(3)
    JOURNAL.controle("Zonages des professionnels de santé, communes du référentiel retrouvées (attendu, toutes)",
                     ", ".join(f"{p.split('_')[0]} {len(actuelles) - n} sur {len(actuelles)}"
                               for p, n in ((k[len('communes_sans_'):], v) for k, v in r.items() if k.startswith("communes_sans_"))))
    JOURNAL.controle("Zonages des professionnels de santé, catégories inconnues et parts d'une commune hors de 1 "
                     "(attendu, aucune)", f"{', '.join(inconnues) or 'aucune'} ; {r['parts_hors_1']}")
    JOURNAL.controle("Zonages des médecins, Auvergne-Rhône-Alpes face au repère de l'ARS (ZIP 28,5 %, ZAC 49,2 %)",
                     f"ZIP {r['ara_zip'] * 100:.1f} %, ZAC {r['ara_zac'] * 100:.1f} %".replace(".", ","))
    JOURNAL.controle("Zonages des médecins, part de la population française par catégorie",
                     ", ".join(f"{CATEGORIES.get(c, c)} {v * 100:.1f} %".replace(".", ",")
                               for (p, c), v in fr.items() if p == "medecin_generaliste"))
    return r


def charger(ref, hors_ligne=False, rafraichir=False) -> dict | None:
    """Brouillon : tables lues et contrôlées, écrites dans donnees/intermediaire/zonages (zonages_communes.csv et
    parts par niveau). Renvoie {"communes", "parts", "controles"} ou None si la source manque (jamais bloquant)."""
    try:
        chemins = _telecharger(hors_ligne, rafraichir)
        t = lire(chemins, ref)
    except Exception as e:  # noqa: BLE001
        log.warning("zonages des professionnels de santé : %s", e)
        JOURNAL.note(SOURCE, "erreur", f"{type(e).__name__} {e}"[:300], url=PAGE)
        return None
    r = controler(t, ref, chemins)
    parts = parts_territoires(t, ref)
    DOSSIER_INTERNE.mkdir(parents=True, exist_ok=True)
    t.to_csv(DOSSIER_INTERNE / "zonages_communes.csv", sep=";", index=False, encoding="utf-8-sig")
    for niv, p in parts.items():
        p.to_csv(DOSSIER_INTERNE / f"zonages_parts_{niv}.csv", sep=";", index=False, encoding="utf-8-sig")
    meta = lire_meta(chemins["com"])
    JOURNAL.note(SOURCE, "ok", f"brouillon, {t['commune'].nunique()} communes, {t['profession'].nunique()} professions, "
                               f"table des communes du {(meta.get('maj_source') or '')[:10]}, non publié",
                 url=PAGE, date_donnees=(meta.get("maj_source") or "")[:10], producteur="Atlasanté (réseau des ARS)",
                 licence="Licence Ouverte 2.0")
    return {"communes": t, "parts": parts, "controles": r}


if __name__ == "__main__":
    # brouillon lancé seul (python -m pipeline.sources.zonages [--hors-ligne]), sans passer par run.py : son entrée au
    # journal ferait paraître la source sur la page « Données sources » avant la fiche de territoire en bandes
    import sys
    from . import referentiel
    o = charger(referentiel.charger(hors_ligne=True), hors_ligne="--hors-ligne" in sys.argv)
    print(o["controles"] if o else "zonages indisponibles")
