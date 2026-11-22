"""Vérification des structures de santé mentale par lots d'établissements (chantier du 18 novembre 2026, « il faut
une liste des structures totalement vérifiée », santé mentale d'abord).

Pour chaque établissement gestionnaire (entité juridique de FINESS) qui a au moins une structure de santé mentale
« à vérifier » ou seulement « recoupée par la statistique des hôpitaux », la liste de ses structures est reprise sur
ses propres sources, comme pour les établissements déjà vérifiés (pipeline/structures_verifiees.py). Trois commandes.

    python outils\\lots_structures.py preparer --region 84 --taille 8     dossiers du prochain lot de la région
    python outils\\lots_structures.py valider  <lot>                      contrôle des lignes trouvées
    python outils\\lots_structures.py integrer <lot>                      ajout aux listes vérifiées, après validation
    python outils\\lots_structures.py preparer --region 84 --taille 8 --completer
        lot de complément : établissements déjà vérifiés, seulement leurs types pas encore relus, fondus à
        l'intégration dans la ligne vérifiée (completer.json du lot)

Un lot vit dans docs/structures/verification_sm/<lot>/ :
- dossier.md, par établissement, ses inscriptions dans FINESS et le ROR pour les types de santé mentale ;
- structures.csv, à remplir, mêmes colonnes que contenus/structures_verifiees.csv ;
- etablissements.csv, à remplir, une ligne par établissement vérifié (sans empreinte, calculée à l'intégration) ;
- controle.md, écrit par « valider ».

Règles du contrôle (bloquant pour l'intégration) : colonnes et valeurs permises, établissement du lot, commune au
code INSEE du référentiel, date du jour de la recherche ou avant, source cliquable d'un domaine admis (jamais Ameli,
Doctolib, Mon Soutien Psy, Retab, France Victimes, Google Maps, ni santé.fr qui reprend le ROR), page qui répond, et
qui cite la commune ou la rue de la structure. Une structure qu'aucune source ne confirme reste inscrite avec le statut
« bases » et la date de la recherche : elle sera dite « non confirmée, aucune source officielle trouvée ».
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

DOSSIER = RACINE / "docs" / "structures" / "verification_sm"
BASES = RACINE / "donnees" / "intermediaire" / "structures_avant_verification.parquet"
TYPES_SM = ["lieu_cmp", "lieu_cattp", "lieu_hdj_psy_adultes", "lieu_hdj_psy_enfants", "lieu_cmpp", "lieu_camsp",
            "lieu_csapa", "lieu_caarud"]
COLS = ["ej", "etablissement", "type", "public", "nom", "adresse", "commune", "statut", "finess", "source",
        "adresse_source", "date", "remarque"]
COLS_ETAB = ["ej", "etablissement", "departement", "types", "date", "sources", "remarque"]
STATUTS = {"etablissement", "source_publique", "bases"}
PUBLICS = {"adultes", "enfants", "adultes et enfants", ""}
# domaines refusés ; retab seulement comme nom de domaine (« retablissement » passe), santé.fr avec ou sans barre finale,
# Google Maps sous toutes ses adresses, annuaires commerciaux (audit du 19 novembre 2026)
INTERDITS = re.compile(r"ameli\.fr|doctolib|monsoutienpsy|mon-soutien-psy|//(?:[\w-]+\.)*retab\.|france-victimes|"
                       r"francevictimes|google\.[a-z.]+/maps|maps\.google|goo\.gl/maps|maps\.app\.goo\.gl|pagesjaunes\."
                       r"|chi-poissy-st-germain|camsp-apamsp-lorraine\.fr|apajh37\.org|anvol\.bzh|//(?:www\.)?sante\.fr(?:[/?#]|$)", re.I)
# mots qui ne distinguent pas une structure d'une autre (le nom doit aussi se lire sur la page, pas seulement la commune,
# que les en-têtes des sites d'établissement citent toutes : lot pilote r94-01 du 18 novembre 2026)
GENERIQUES = set("""cmp cattp cmpp camsp csapa caarud hdj hj centre centres hopital hopitaux jour nuit adulte adultes enfant
enfants adolescent adolescents psychiatrie psychiatrique psy medico psychologique psychologiques therapeutique accueil temps
partiel antenne consultation consultations unite pole secteur site de du la le les des et en aux au pour sur sud nord est
ouest saint sainte hospitalisation hospitalisations complete ambulatoire ambulatoires soins service services
lieu lieux equipe""".split())
# mots du type, cherchés près du lieu quand le nom n'a aucun mot distinctif (« CMP Sarrebourg » sur la liste des sites
# de la HAS, lot r44-01 du 18 novembre 2026)
MOTS_TYPE = {"lieu_cmp": ["cmp", "cmpi", "cmpia", "cmpea", "cmpe", "centre medico psychologique",
                          "centres medico psychologiques"],
             "lieu_cattp": ["cattp", "temps partiel", "cattg"],
             "lieu_hdj_psy_adultes": ["hopital de jour", "hopitaux de jour", "hdj", "hj", "hospitalisation de jour",
                                      "temps partiel de jour"],
             "lieu_hdj_psy_enfants": ["hopital de jour", "hopitaux de jour", "hdj", "hj", "hospitalisation de jour",
                                      "temps partiel de jour"],
             "lieu_cmpp": ["cmpp", "centre medico psycho pedagogique"], "lieu_camsp": ["camsp"], "lieu_csapa": ["csapa"],
             "lieu_caarud": ["caarud"]}


def simple(s) -> str:
    """Minuscules sans accents ni ponctuation, « st » et « ste » écrits « saint » et « sainte » (« St Denis »)."""
    # apostrophe typographique en espace avant de retirer les accents (« d’hôpital » donnait « dhopital », lot r24-02)
    s = re.sub(r"[’‘ʼ'`]", " ", str(s or ""))
    # sigles à points (« C.M.P.I.A. », « C.A.T.T.G. ») écrits d'un seul mot, lot r84-01
    s = re.sub(r"(?<![A-Za-z])((?:[A-Za-z]\.){2,}[A-Za-z]?)", lambda m: m.group(1).replace(".", ""), s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\bste\b", "sainte", re.sub(r"\bst\b", "saint", s))


def contient(texte: str, mots: str) -> bool:
    """Mots entiers, dans l'ordre, dans le texte simplifié (« ote » ne se lit plus dans « leperon », lot r04-01)."""
    return bool(mots) and f" {mots} " in f" {texte} "


def communes() -> dict:
    """Communes actuelles par code INSEE, avec les noms de leurs communes déléguées ou associées (« anciens noms »,
    Doué-la-Fontaine pour Doué-en-Anjou). Une commune déléguée porte souvent le code de sa commune nouvelle : elle
    n'écrase plus son nom (lot r52-01 du 18 novembre 2026)."""
    brut = json.loads((RACINE / "donnees" / "brut" / "ref_communes.json").read_text(encoding="utf-8"))
    out = {c["code"]: dict(c, anciens=[]) for c in brut if c.get("type") in ("commune-actuelle", "arrondissement-municipal")}
    for c in brut:
        if c.get("type") in ("commune-deleguee", "commune-associee") and c.get("chefLieu") in out:
            out[c["chefLieu"]]["anciens"].append(c["nom"])
    return out


def _positions(texte: str, mots: str) -> list[int]:
    return [m.start() for m in re.finditer(rf"(?<![a-z0-9]){re.escape(mots)}(?![a-z0-9])", texte)] if mots else []


def proches(texte: str, a: list[str], b: list[str], dist: int = 600) -> bool:
    """Un des mots de a et un des mots de b à moins de dist caractères : le nom de la structure et son lieu se lisent
    ensemble, et non le lieu dans un pied de page (« MAYENNE Cedex », lot r52-01)."""
    pa = [i for x in a for i in _positions(texte, x)]
    pb = [i for x in b for i in _positions(texte, x)]
    return any(abs(i - j) <= dist for i in pa for j in pb)


def derniere_version() -> Path:
    r = RACINE / "resultats"
    return max(d for d in r.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name)
               and (d / "lieux_soins.csv").exists())


def a_reprendre(version: Path, toutes: bool = False) -> pd.DataFrame:
    """Structures de santé mentale non confirmées (à vérifier ou seulement recoupées), une ligne par structure. Avec
    toutes, aussi celles que le croisement des bases disait confirmées sans qu'une source les ait relues une à une
    (liste entièrement vérifiée, demande du 18 novembre 2026)."""
    x = pd.read_csv(version / "lieux_soins.csv", sep=";", dtype=str, low_memory=False)
    x = x[(x["famille"] == "Santé mentale") & x["type"].isin(TYPES_SM) & x["classe_confirmation"].notna()
          & (toutes | (x["classe_confirmation"] != "confirmée"))]
    return x.drop_duplicates(["id_structure", "type"])


def _num_lot(region: str) -> Path:
    """Dossier du prochain lot de la région, numéro le plus haut plus un (jamais un dossier existant, même après la
    suppression d'un lot)."""
    nums = [int(m.group(1)) for d in DOSSIER.glob(f"r{region}-*") if (m := re.fullmatch(rf"r{region}-(\d+)", d.name))]
    lot = DOSSIER / f"r{region}-{max(nums, default=0) + 1:02d}"
    lot.mkdir(parents=True)
    return lot


def _en_cours(lot: Path) -> bool:
    """Lot ni intégré ni abandonné (abandonne.txt, lot revenu vide : ses établissements sont à reprendre, 20 novembre
    2026)."""
    return not (lot / "integre.txt").exists() and not (lot / "abandonne.txt").exists()


def deja_faits(region: str = "") -> tuple[set[str], dict[str, set[str]]]:
    """Établissements à ne pas mettre dans un lot ordinaire de la région : vérifiés pour tout l'établissement (ligne
    sans département), ou dans un lot en cours de la région. Et, pour les établissements vérifiés département par
    département, les départements déjà couverts : leurs autres départements restent à reprendre (CH de Montfavet
    vérifié pour les Bouches-du-Rhône et pas pour le Vaucluse, audit du 19 novembre 2026)."""
    e = pd.read_csv(RACINE / "contenus" / "etablissements_verifies.csv", sep=";", dtype=str).fillna("")
    exclus = set(e.loc[e["departement"] == "", "ej"])
    couverts: dict[str, set[str]] = {}
    for r in e[e["departement"] != ""].itertuples():
        couverts.setdefault(r.ej, set()).add(r.departement)
    for f in DOSSIER.glob(f"r{region}-*/etablissements_attendus.txt"):
        if _en_cours(f.parent):
            exclus |= set(f.read_text(encoding="utf-8").split())
    return exclus, couverts


def _bases_dep() -> pd.DataFrame:
    """Inscriptions des bases avec leur département, pris dans le référentiel de la chaîne comme dans appliquer."""
    from pipeline.sources import referentiel
    b = pd.read_parquet(BASES)
    b["dep"] = b["commune"].map(referentiel.charger(True, False).communes.set_index("code")["dep"])
    return b


def _jetons(types: str) -> list[tuple[str, str]]:
    return [(t.strip().partition(":")[0], t.strip().partition(":")[2].strip()) for t in types.split(",") if t.strip()]


def _bases_types(types: str) -> set[str]:
    return {t for t, _p in _jetons(types)}


AUTRE_PUBLIC = {"adultes": "enfants", "enfants": "adultes"}


def a_reprendre_verifies(region: str, b: pd.DataFrame | None = None) -> dict[tuple[str, str], dict]:
    """Périmètres déjà vérifiés (ej, département, vide pour tout l'établissement) à reprendre dans la région (19 novembre
    2026, liste entièrement vérifiée) :
    - « reverifier », quand les inscriptions des bases ont changé depuis la vérification (empreinte), que la
      vérification a plus d'un an, ou qu'une de ses structures est confirmée par une source de plus de trois ans : tout
      le périmètre est repris, et remplacé à l'intégration ;
    - « completer », quand des types de santé mentale inscrits dans les bases n'ont pas été relus (un centre hospitalier
      vérifié pour ses CMP, pas pour ses hôpitaux de jour), ou l'autre public d'un type vérifié pour un seul public
      (« lieu_cmp:adultes » et des CMP pour enfants inscrits) : seuls ces types sont repris, et fondus à l'intégration.
    Un établissement vérifié en entier est repris dans la région où il a le plus d'inscriptions. Un périmètre déjà dans
    un lot en cours, de n'importe quelle région, n'est pas repris."""
    from pipeline import structures_verifiees as sv
    e, s = sv.charger()
    com = communes()
    deps = {c["departement"] for c in com.values() if c.get("region") == region}
    b = _bases_dep() if b is None else b
    # structures confirmées par une source de plus de trois ans (66 lignes, certifications HAS de 2022 et inventaires
    # de l'ARS de 2017, constat du 19 novembre 2026) : leur périmètre est à revérifier
    dep_s = s["commune"].map(lambda c: (com.get(str(c)) or {}).get("departement", ""))
    vieilles = s[(s["statut"] != "bases") & s["source"].map(lambda x: bool(age_source(x, dt.date.today())))]
    vieilles = set(zip(vieilles["ej"], dep_s[vieilles.index]))
    enf = sum(sv.ENFANTS_DE.values(), [])
    pere = {c: t for t, cs in sv.ENFANTS_DE.items() for c in cs}
    bb = b[b["type"].isin(TYPES_SM + enf)]
    reg = bb["commune"].map(lambda c: (com.get(str(c)) or {}).get("region", ""))
    pris = set()
    for f in DOSSIER.glob("r*-*/completer.json"):
        if _en_cours(f.parent):
            pris |= {(x["ej"], x["departement"]) for x in json.loads(f.read_text(encoding="utf-8"))}
    auj = dt.date.today()
    out = {}
    for r in e.itertuples():
        if (r.ej, r.departement) in pris or (r.departement and r.departement not in deps):
            continue
        m = (bb["ej"] == r.ej) & ((bb["dep"] == r.departement) if r.departement else True)
        g = bb[m]
        if not r.departement and (g.empty or reg[m].value_counts().idxmax() != region):
            continue
        ts_old = [t for t in sv.types_de(r.types) if t not in enf]
        age = (auj - dt.date.fromisoformat(r.date)).days if r.date else 9999
        presents = set(g["type"].map(lambda t: pere.get(t, t))) & set(TYPES_SM)
        ancienne = any(ej_ == r.ej and (not r.departement or d_ == r.departement) for ej_, d_ in vieilles)
        if (r.empreinte and sv.empreinte(b, r.ej, ts_old, r.departement) != r.empreinte) or age > sv.DUREE_JOURS                 or ancienne:
            out[(r.ej, r.departement)] = {"mode": "reverifier", "types_deja": r.types,
                                          "types_a_relire": sorted(presents | _bases_types(r.types))}
            continue
        manquants = sorted(presents - _bases_types(r.types))
        for t, p in _jetons(r.types):
            autre = AUTRE_PUBLIC.get(p)
            if autre and (g["type"] == f"{t}_{autre}").any():
                manquants.append(f"{t}:{autre}")
        if manquants:
            out[(r.ej, r.departement)] = {"mode": "completer", "types_deja": r.types, "types_a_relire": manquants}
    return out


def _dormantes(s: pd.DataFrame, ej: str, dep: str, jetons: list[str], dep_de: dict) -> pd.Series:
    """Lignes de la liste vérifiée d'un établissement, de ces types (« lieu_cmp:enfants », seulement celles de ce
    public) et dans ce périmètre. Au complément, ce sont des lignes qu'aucune ligne vérifiée n'applique encore (type
    absent de la ligne de l'établissement), qui s'appliqueraient à côté des structures relues (16 lignes des lots du
    18 novembre, CATTP de Redon compté deux fois, audit du 19 novembre) ; à la revérification, l'ancienne liste."""
    m = pd.Series(False, index=s.index)
    for t, p in _jetons(",".join(jetons)):
        m |= (s["type"] == t) & ((s["public"] == p) if p else True)
    return m & (s["ej"] == ej) & ((s["commune"].map(dep_de) == dep) if dep else True)


def preparer_reprise(region: str, taille: int) -> Path:
    """Lot de reprise d'établissements déjà vérifiés (a_reprendre_verifies) : complément des seuls types pas encore
    relus, ou revérification de tout le périmètre. Le lot porte completer.json (ej, département, mode, types déjà
    vérifiés, types à relire), que « valider » et « integrer » lisent."""
    from pipeline import structures_verifiees as sv
    from pipeline.sources import referentiel
    version = derniere_version()
    b = _bases_dep()
    cand = a_reprendre_verifies(region, b)
    if not cand:
        sys.exit(f"Région {region} : aucun établissement vérifié à reprendre.")
    com = communes()
    dep_de = referentiel.charger(True, False).communes.set_index("code")["dep"].to_dict()

    def inscriptions(k, v):
        ts = {f"{t}_{p}" if p else t for t, p in _jetons(",".join(v["types_a_relire"]))}
        return b[(b["ej"] == k[0]) & b["type"].isin(ts) & ((b["dep"] == k[1]) if k[1] else True)]
    taille_de = {k: len(inscriptions(k, v)) for k, v in cand.items()}
    choisis = sorted(cand, key=lambda k: -taille_de[k])[:taille]
    e, s = sv.charger()
    lot = _num_lot(region)
    lignes = [f"# Lot de reprise {lot.name}, région {region}, préparé le {dt.date.today():%d/%m/%Y} sur la version "
              f"{version.name}", "",
              "Établissements déjà vérifiés. « Compléter » : retrouver sur ses propres sources ses structures des seuls "
              "types « à relire » (les autres sont déjà vérifiés, ne pas les reprendre). « Revérifier » : ses inscriptions "
              "ont changé depuis la vérification, reprendre toutes ses structures des types « à relire », la liste "
              "remplacera l'ancienne. Une ligne par structure dans structures.csv, une ligne par établissement dans "
              "etablissements.csv avec exactement le département ci-dessous (vide s'il dit « tous ») et, dans la colonne "
              "types, les types relus. Voir la section « Lots de reprise » du mode d'emploi "
              "(docs/structures/verification_sm/mode_emploi.md).", ""]
    marque = []
    for ej, dep in choisis:
        v = cand[(ej, dep)]
        et = e[(e["ej"] == ej) & (e["departement"] == dep)].iloc[0]
        marque.append({"ej": ej, "departement": dep, **v})
        anc = s[_dormantes(s, ej, dep, v["types_a_relire"] if v["mode"] == "completer"
                           else sorted({t.partition(":")[0] for t in v["types_a_relire"]}), dep_de)]
        g = inscriptions((ej, dep), v).astype(object)
        g = g.where(g.notna(), "")
        quoi = "Compléter" if v["mode"] == "completer" else "Revérifier (inscriptions changées ou vérification ancienne)"
        lignes += [f"## {ej}, {et['etablissement']}", "",
                   f"{quoi}. Département de la ligne vérifiée : {dep or 'tous (ligne valable pour tout l’établissement)'}. "
                   f"Déjà vérifiés le {et['date']} : {et['types']}. À relire : {', '.join(v['types_a_relire'])}.", "",
                   "| Type | Nom dans les bases | Adresse | Commune (code) | FINESS | Provenance | Unités du ROR |",
                   "|---|---|---|---|---|---|---|"]
        for r in g.sort_values(["type", "commune", "nom"]).to_dict("records"):
            c = com.get(str(r.get("commune") or ""), {})
            lignes.append(f"| {r['type']} | {r.get('nom') or r.get('nom_finess') or ''} | {r.get('adresse') or ''} | "
                          f"{c.get('nom', '')} ({r.get('commune') or ''}) | {r.get('finess') or ''} | "
                          f"{r.get('provenance') or ''} | {str(r.get('noms_unites') or '')[:120]} |")
        if len(anc):
            lignes += ["", "Lignes déjà dans la liste vérifiée pour ces types, qui seront remplacées par celles du lot "
                       "(les reprendre si la source les confirme) :", ""]
            lignes += [f"- {x.type}, {x.nom}, {x.adresse}, {com.get(x.commune, {}).get('nom', '')} ({x.commune}), "
                       f"statut {x.statut}" for x in anc.itertuples()]
        lignes.append("")
    (lot / "dossier.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    (lot / "completer.json").write_text(json.dumps(marque, ensure_ascii=False, indent=1), encoding="utf-8")
    (lot / "etablissements_attendus.txt").write_text("\n".join(sorted({m["ej"] for m in marque})) + "\n",
                                                     encoding="utf-8")
    pd.DataFrame(columns=COLS).to_csv(lot / "structures.csv", sep=";", index=False, encoding="utf-8")
    pd.DataFrame(columns=COLS_ETAB).to_csv(lot / "etablissements.csv", sep=";", index=False, encoding="utf-8")
    print(f"Lot de reprise {lot.name} : {len(marque)} établissements "
          f"({sum(m['mode'] == 'reverifier' for m in marque)} à revérifier), "
          f"{sum(taille_de[k] for k in choisis)} inscriptions, dossier {lot / 'dossier.md'}")
    return lot


def _complement(lot: Path) -> dict[tuple[str, str], dict] | None:
    f = lot / "completer.json"
    if not f.exists():
        return None
    return {(m["ej"], m["departement"]): dict(m, mode=m.get("mode", "completer"))
            for m in json.loads(f.read_text(encoding="utf-8"))}


def fusion_types(deja: str, neufs: str) -> tuple[str | None, str]:
    """Types d'une ligne complétée, ou None et la raison du refus. Un type déjà vérifié n'est jamais repris, sauf
    l'autre public d'un type vérifié pour un seul public : « lieu_cmp:adultes » et « lieu_cmp:enfants » donnent
    « lieu_cmp »."""
    vieux = dict(_jetons(deja))
    out = [f"{t}:{p}" if p else t for t, p in _jetons(deja)]
    for t, p in _jetons(neufs):
        if t in vieux:
            if p and vieux[t] and AUTRE_PUBLIC.get(vieux[t]) == p:
                out[out.index(f"{t}:{vieux[t]}")] = t
                continue
            return None, f"{t}{':' + p if p else ''} déjà vérifié ({deja})"
        out.append(f"{t}:{p}" if p else t)
    return ",".join(out), ""


def preparer(region: str, taille: int, nationaux: bool = False, toutes: bool = False) -> Path:
    """Dossiers du prochain lot de la région. Avec nationaux, seulement les associations présentes dans plus de trois
    départements, limitées aux structures de la région, une ligne d'etablissements.csv par département (18 novembre
    2026, après les établissements locaux)."""
    version = derniere_version()
    x = a_reprendre(version, toutes)
    com = communes()
    x["region"] = x["commune"].map(lambda c: (com.get(c) or {}).get("region", ""))
    x["dep"] = x["commune"].map(lambda c: (com.get(c) or {}).get("departement", ""))
    x = x[(x["region"] == region) & x["entite_juridique"].notna()]
    exclus, couverts = deja_faits(region)
    # un établissement vérifié département par département reste à reprendre dans ses autres départements
    x = x[~x["entite_juridique"].isin(exclus)
          & ~pd.Series([d in couverts.get(e_, ()) for e_, d in zip(x["entite_juridique"], x["dep"])], index=x.index)]
    ordre = x.groupby("entite_juridique").size().sort_values(ascending=False).index.tolist()
    # associations présentes dans plus de trois départements (APAJH, Addictions France...) : lots à part, département par
    # département (lot r24-01 du 18 novembre 2026, une fédération sur neuf départements ne tient pas dans un lot)
    bb = pd.read_parquet(BASES, columns=["ej", "type", "commune"])
    bb = bb[bb["type"].isin(TYPES_SM)]
    ndep = bb.assign(dep=bb["commune"].map(lambda c: (com.get(c) or {}).get("departement", ""))).groupby("ej")["dep"].nunique()
    nationaux_ = [e_ for e_ in ordre if ndep.get(e_, 0) > 3]
    if nationaux_ and not nationaux:
        print(f"Mis à part (plus de trois départements, à vérifier département par département) : {', '.join(nationaux_)}")
    ejs = ([e_ for e_ in ordre if e_ in nationaux_] if nationaux else [e_ for e_ in ordre if e_ not in nationaux_])[:taille]
    if not ejs:
        sys.exit(f"Région {region} : plus aucun établissement à reprendre.")
    lot = _num_lot(region)
    b = pd.read_parquet(BASES)
    sys.path.insert(0, str(RACINE / "outils"))
    from structures_a_verifier import noms_gestionnaires
    fin = noms_gestionnaires()
    lignes = [f"# Lot {lot.name}, région {region}, préparé le {dt.date.today():%d/%m/%Y} sur la version {version.name}", "",
              "Pour chaque établissement : retrouver sur ses propres sources la liste de ses structures de santé mentale "
              "(types ci-dessous), une ligne par structure dans structures.csv, et une ligne dans etablissements.csv. "
              "Voir le mode d'emploi dans docs/structures/verification_sm/mode_emploi.md.", ""]
    for ej in ejs:
        g = b[(b["ej"] == ej) & b["type"].isin(TYPES_SM)]
        if nationaux or ej in couverts:   # seulement les structures de la région, hors départements déjà vérifiés
            g = g[g["commune"].map(lambda c: (com.get(str(c)) or {}).get("region", "")) == region]
            g = g[~g["commune"].map(lambda c: (com.get(str(c)) or {}).get("departement", "")).isin(couverts.get(ej, ()))]
        g = g.astype(object)
        g = g.where(g.notna(), "")
        nr = x[x["entite_juridique"] == ej]
        nom = fin.get(ej) or (nr["etablissement"].iloc[0] if "etablissement" in nr and len(nr) else "")
        deps = sorted({(com.get(c) or {}).get("departement", "") for c in g["commune"].dropna()})
        deja = (f"Déjà vérifié pour {', '.join(sorted(couverts[ej]))} : une ligne d'etablissements.csv par département "
                "relu, colonne departement remplie. " if ej in couverts else "")
        lignes += [f"## {ej}, {nom}", "", f"{deja}Départements : {', '.join(d for d in deps if d)}. "
                   f"Structures non confirmées dans la version publiée : {len(nr)} "
                   f"({', '.join(f'{k} {v}' for k, v in nr['libelle_type'].value_counts().items())}).", "",
                   "| Type | Nom dans les bases | Adresse | Commune (code) | FINESS | Provenance | Unités du ROR |",
                   "|---|---|---|---|---|---|---|"]
        for r in g.sort_values(["type", "commune", "nom"]).to_dict("records"):
            c = com.get(str(r.get("commune") or ""), {})
            lignes.append(f"| {r['type']} | {r.get('nom') or r.get('nom_finess') or ''} | {r.get('adresse') or ''} | "
                          f"{c.get('nom', '')} ({r.get('commune') or ''}) | {r.get('finess') or ''} | "
                          f"{r.get('provenance') or ''} | {str(r.get('noms_unites') or '')[:120]} |")
        lignes.append("")
    (lot / "dossier.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    (lot / "etablissements_attendus.txt").write_text("\n".join(ejs) + "\n", encoding="utf-8")
    pd.DataFrame(columns=COLS).to_csv(lot / "structures.csv", sep=";", index=False, encoding="utf-8")
    pd.DataFrame(columns=COLS_ETAB).to_csv(lot / "etablissements.csv", sep=";", index=False, encoding="utf-8")
    print(f"Lot {lot.name} : {len(ejs)} établissements, {len(x[x['entite_juridique'].isin(ejs)])} structures non "
          f"confirmées, dossier {lot / 'dossier.md'}")
    return lot


MOIS_FR = {m: i + 1 for i, m in enumerate(["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
                                          "septembre", "octobre", "novembre", "decembre"])}


def age_source(source: str, auj: dt.date) -> str | None:
    """Date la plus récente que le libellé de la source donne (« décision du 22 mars 2023 », « 03/2024 », « 2025 »),
    rendue si elle a plus de trois ans ; None si elle est récente ou si le libellé n'en donne aucune."""
    s = unicodedata.normalize("NFKD", str(source or "")).encode("ascii", "ignore").decode().lower()
    # une date d'ouverture ou de création n'est pas celle de la source (Sirene « actif depuis le 01/12/2020 »)
    s = re.sub(r"\b(?:depuis|cree|creee|ouvert|ouverte|ouverture|immatricul\w*)\b(?:\s+(?:le|en|du))?\s+[\w/ ]{0,20}?20\d\d",
               " ", s)
    dates = []
    for j, m, a in re.findall(r"\b(\d{1,2}|1er)\s+(" + "|".join(MOIS_FR) + r")\s+(20\d\d)\b", s):
        dates.append(dt.date(int(a), MOIS_FR[m], 1 if j == "1er" else min(int(j), 28)))
    for m, a in re.findall(r"\b(" + "|".join(MOIS_FR) + r")\s+(20\d\d)\b", s):
        dates.append(dt.date(int(a), MOIS_FR[m], 28))
    for m, a in re.findall(r"\b(\d{1,2})/(20\d\d)\b", s):
        if 1 <= int(m) <= 12:
            dates.append(dt.date(int(a), int(m), 28))
    for j, m, a in re.findall(r"\b(\d{1,2})/(\d{1,2})/(20\d\d)\b", s):
        if 1 <= int(m) <= 12:
            dates.append(dt.date(int(a), int(m), min(int(j), 28)))
    if not dates:
        dates = [dt.date(int(a), 12, 31) for a in re.findall(r"\b(20\d\d)\b", s)]
    if not dates:
        return None
    d = max(dates)
    limite = auj.replace(year=auj.year - 3)
    return None if d >= limite else f"{d:%m/%Y}"


def age_adresse(url: str, auj: dt.date) -> str | None:
    """Date de publication écrite dans l'adresse d'un article (« /2022/11/23/camsp/ »), rendue si elle a plus de trois
    ans (page de l'Adapei Charente de novembre 2022, relecture du 20 novembre 2026). Les dossiers de fichiers
    (« /uploads/2023/06/ ») ne comptent pas : un guide d'octobre 2024 peut y être rangé sous juin 2023."""
    m = re.search(r"/(20\d\d)/(0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01])/", str(url or ""))
    if not m:
        return None
    d = dt.date(int(m.group(1)), int(m.group(2)), 28)
    return None if d >= auj.replace(year=auj.year - 3) else f"{d:%m/%Y}"


def voie_cle(adresse) -> tuple[str, str]:
    """Numéro et rue sans les mots de liaison, pour comparer deux écritures d'une même adresse (« rue de Montaury » et
    « RUE MONTAURY », doublon de Nîmes vu le 19 novembre 2026)."""
    from pipeline import structures_verifiees as sv
    n, rue = sv._voie(adresse)
    return n, " ".join(w for w in rue.split() if w not in {"de", "du", "des", "la", "le", "les", "d", "l"})


def _texte_page(url: str) -> tuple[int, str]:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verification de sources)"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            brut = r.read()
            code = r.status
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", 0) or 0
        return code, ""
    if brut[:4] == b"%PDF":
        try:
            import io
            import pypdf
            t = " ".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(brut)).pages)
        except Exception:  # noqa: BLE001
            t = ""
    else:
        # encodage de la page (en-tête ou balise meta), sinon UTF-8, sinon Windows-1252 (page en Latin-1 du lot pilote)
        m = re.search(rb"charset=[\"']?([A-Za-z0-9_-]+)", brut[:3000])
        enc = m.group(1).decode() if m else "utf-8"
        try:
            t = brut.decode(enc)
        except (UnicodeDecodeError, LookupError):
            t = brut.decode("cp1252", errors="ignore")
        t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)   # les scripts restent : cartes des sites en JSON
        t = re.sub(r"<[^>]+>", " ", t)
        import html as h
        t = h.unescape(t)
    return code, simple(t)


def valider(lot: Path) -> list[str]:
    from pipeline import structures_verifiees as sv
    from pipeline.sources import referentiel
    enf = sum(sv.ENFANTS_DE.values(), [])
    com = communes()
    # communes de la chaîne : un code d'arrondissement (13205, 75101) passerait ici et serait perdu dans la chaîne
    dep_de = referentiel.charger(True, False).communes.set_index("code")["dep"].to_dict()
    attendus = set((lot / "etablissements_attendus.txt").read_text(encoding="utf-8").split())
    try:
        s = pd.read_csv(lot / "structures.csv", sep=";", dtype=str).fillna("")
        e = pd.read_csv(lot / "etablissements.csv", sep=";", dtype=str).fillna("")
    except Exception as ex:  # noqa: BLE001
        return [f"fichier illisible ({ex}) : un point-virgule dans une remarque ? Mettre la remarque entre guillemets "
                "doubles, ou remplacer le point-virgule par une virgule"]
    fautes, avis = [], []
    if list(s.columns) != COLS:
        fautes.append(f"structures.csv, colonnes {list(s.columns)} au lieu de {COLS}")
    if list(e.columns) != COLS_ETAB:
        fautes.append(f"etablissements.csv, colonnes {list(e.columns)} au lieu de {COLS_ETAB}")
    if fautes:
        return fautes
    # inscriptions laissées de côté, une par ligne avec sa raison (laissees.csv du lot, facultatif) : sans ligne ici,
    # une inscription absente de structures.csv reste comptée (règle du 19 novembre 2026, contrôle du 21 novembre)
    f_lai = lot / "laissees.csv"
    if f_lai.exists():
        lai = pd.read_csv(f_lai, sep=";", dtype=str).fillna("")
        if list(lai.columns) != sv.COLS_LAISSEES:
            fautes.append(f"laissees.csv, colonnes {list(lai.columns)} au lieu de {sv.COLS_LAISSEES}")
        else:
            for i, r in lai.iterrows():
                o = f"laissees.csv ligne {i + 2} ({r['nom'][:40]})"
                if r["categorie"] not in sv.CATEGORIES_LAISSEES:
                    fautes.append(f"{o} : catégorie « {r['categorie']} » hors de {sorted(sv.CATEGORIES_LAISSEES)}")
                if len(r["raison"]) < 20:
                    fautes.append(f"{o} : raison absente ou trop courte")
                if r["ej"] not in attendus:
                    fautes.append(f"{o} : établissement {r['ej']} hors du lot")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
                    fautes.append(f"{o} : date « {r['date']} » au lieu de AAAA-MM-JJ")
    auj = dt.date.today()
    pages: dict[str, tuple[int, str]] = {}
    # pages relues à la main par la séance principale (page qui ne s'affiche qu'avec un navigateur, 403) : adresse,
    # date et constat écrits dans rouvertes_a_la_main.csv du lot, jamais par la recherche (18 novembre 2026)
    f_main = lot / "rouvertes_a_la_main.csv"
    a_la_main = {}
    if f_main.exists():
        a_la_main = {x["adresse"]: x for x in pd.read_csv(f_main, sep=";", dtype=str).fillna("").to_dict("records")}
    # sources et remarques sont montrées sur la page de méthode des structures : pas de vocabulaire à éviter sur le site
    # (« contrôle automatique » d'une page refusée, 20 novembre 2026), écrire « contrôle par robot »
    for nom_f, t in (("structures.csv", s), ("etablissements.csv", e)):
        for i, r in t.iterrows():
            if re.search(r"automatique", r.get("source", "") + " " + r.get("sources", "") + " " + r.get("remarque", ""), re.I):
                fautes.append(f"{nom_f} ligne {i + 2} : « automatique » dans la source ou la remarque, écrire « par robot »")
    for i, r in s.iterrows():
        o = f"structures.csv ligne {i + 2} ({r['nom'][:40]})"
        if r["ej"] not in attendus:
            fautes.append(f"{o} : établissement {r['ej']} hors du lot")
        if r["type"] in enf:
            fautes.append(f"{o} : type {r['type']}, écrire le type parent avec le public dans la colonne public")
        elif r["type"] not in TYPES_SM:
            fautes.append(f"{o} : type {r['type']} hors de la santé mentale ou inconnu")
        if r["public"] not in PUBLICS:
            fautes.append(f"{o} : public « {r['public']} »")
        if r["commune"] not in dep_de:
            fautes.append(f"{o} : commune {r['commune']} absente du référentiel de la chaîne (code d'arrondissement ? "
                          "prendre celui de la commune)")
        if r["statut"] not in STATUTS:
            fautes.append(f"{o} : statut « {r['statut']} »")
        try:
            d = dt.date.fromisoformat(r["date"])
            if d > auj or (auj - d).days > 30:
                fautes.append(f"{o} : date {r['date']} hors du mois écoulé")
        except ValueError:
            fautes.append(f"{o} : date « {r['date']} »")
        url = r["adresse_source"]
        if r["statut"] != "bases":
            # source de plus de trois ans (décision HAS du 22 mars 2023 citée le 19 novembre 2026)
            vieille = age_source(r["source"], auj) or age_adresse(r["adresse_source"], auj)
            if vieille:
                fautes.append(f"{o} : source de plus de trois ans ({vieille}), elle ne confirme rien")
            if not re.match(r"https?://", url):
                fautes.append(f"{o} : source sans adresse cliquable")
                continue
            if INTERDITS.search(url):
                fautes.append(f"{o} : source interdite ou non admise ({url})")
                continue
            if url in a_la_main:
                avis.append(f"{o} : page relue à la main le {a_la_main[url]['date']} ({a_la_main[url]['constat'][:80]})")
                continue
            if url not in pages:
                pages[url] = _texte_page(url)
            code, texte = pages[url]
            if code != 200 or not texte:
                # bloquant tant que la page n'est pas relue à la main (44 lignes passées sans relecture, dont 4 pages
                # disparues, audit du 19 novembre 2026)
                fautes.append(f"{o} : la page ne répond pas au contrôle (code {code}), à rouvrir à la main et à noter "
                              f"dans rouvertes_a_la_main.csv : {url}")
                continue
            cr = com.get(r["commune"]) or {}
            nomc = simple(cr.get("nom", ""))
            # lieu-dit ou hameau que la source écrit à la place de la commune (« lieu cité : Sagone » en remarque)
            lc = re.search(r"lieu cit[ée] ?: ?([^.;,(]+)", r["remarque"], re.I)
            lieux_ok = [nomc] + [simple(x) for x in cr.get("anciens", [])] + ([simple(lc.group(1))] if lc else [])
            rue = [w for w in simple(r["adresse"]).split() if len(w) > 3 and not w.isdigit()
                   and w not in {"rue", "avenue", "boulevard", "place", "chemin", "route", "allee", "impasse"}]
            rue_ok = bool(rue) and all(contient(texte, w) for w in rue[:2])
            ou_ok = any(contient(texte, x) for x in lieux_ok) or rue_ok
            mots = [w for w in simple(r["nom"]).split() if len(w) > 2 and w not in GENERIQUES
                    and w not in nomc.split() and not (lc and w in simple(lc.group(1)).split())]
            nom_ok = not mots or any(contient(texte, w) for w in mots)
            if not ou_ok:
                fautes.append(f"{o} : ni la commune « {nomc} », ni un lieu cité, ni la rue ne figurent sur la page {url}")
            elif not nom_ok:
                fautes.append(f"{o} : le nom de la structure ({', '.join(mots)}) ne figure pas sur la page {url}")
            # un document entier consacré à la structure (livret d'accueil en PDF) n'a pas à rapprocher nom et lieu
            elif (not re.search(r"\.pdf$|/pdf/", url, re.I)
                  and not proches(texte, mots or MOTS_TYPE.get(r["type"], []),
                                  [x for x in lieux_ok if x] + (rue[:1] if rue_ok else []), 800)):
                fautes.append(f"{o} : le nom ({', '.join(mots)}) et le lieu ne se lisent pas ensemble sur la page {url} "
                              "(lieu seulement dans un en-tête ou un pied de page ?)")
        elif not r["remarque"]:
            fautes.append(f"{o} : statut « bases » sans remarque qui dit ce qui a été cherché")
    # deux lignes du même nom, du même type et de la même commune pour un établissement : la chaîne s'arrêterait (un CMP
    # pour adultes et pour enfants fait une seule ligne, public « adultes et enfants »)
    cle = s["ej"] + "|" + s["type"] + "|" + s["commune"] + "|" + s["nom"].map(simple) + "|" + s["adresse"].map(simple)
    for k in sorted(set(cle[cle.duplicated()])):
        fautes.append(f"structures.csv : deux lignes pour {k} (même nom et même adresse ; un CMP des deux publics s'écrit en une ligne, public "
                      "« adultes et enfants »)")
    # une structure ajoutée (sans numéro FINESS) et une inscription gardée en bases, seules de leur type dans la commune
    # pour l'établissement : souvent la même structure déménagée, comptée deux fois (lot r76-05, Bagnols-sur-Cèze)
    for (ej_, t_, c_), g in s.groupby(["ej", "type", "commune"]):
        aj, ba = g[(g["statut"] != "bases") & (g["finess"] == "")], g[g["statut"] == "bases"]
        if len(aj) == 1 and len(ba) == 1 and len(g) == 2:
            avis.append(f"{ej_}, {t_}, commune {c_} : « {aj['nom'].iloc[0]} » ajoutée et « {ba['nom'].iloc[0]} » en bases, "
                        "peut-être la même structure déménagée (une seule ligne, avec le numéro FINESS des bases)")
    for ej in attendus - set(e["ej"]):
        fautes.append(f"etablissements.csv : établissement {ej} sans ligne (même sans source, dire ce qui a été cherché)")
    # un seul département par ligne, ou vide (« 22,35 » ne désignait aucun département et la liste vérifiée ne
    # s'appliquait pas, lot du 18 novembre 2026 relu le 19)
    deps_ok = {c["departement"] for c in com.values()}
    for i, r in e.iterrows():
        if r["departement"] and r["departement"] not in deps_ok:
            fautes.append(f"etablissements.csv ligne {i + 2} : département « {r['departement']} » (un seul code par "
                          "ligne, une ligne par département, ou vide pour tout l'établissement)")
    # sans département, la ligne vaut pour tout l'établissement : refusée s'il a des structures hors de la région du lot
    # (associations nationales, lots du 18 novembre 2026)
    region_lot = re.match(r"r(\w+?)-\d+$", lot.name)
    comp = _complement(lot)
    e_old, s_old = sv.charger()
    cles_e = set(zip(e["ej"], e["departement"]))
    # colonne types : types de santé mentale, public « adultes » ou « enfants » seulement pour un type qui en a
    # (« lieu_cmp:adulte » ne correspondait à aucun public et doublait les CMP, audit du 19 novembre 2026)
    for i, r in e.iterrows():
        for t_, p_ in _jetons(r["types"]):
            if t_ not in TYPES_SM or (p_ and (p_ not in AUTRE_PUBLIC or t_ not in sv.ENFANTS_DE)):
                fautes.append(f"etablissements.csv ligne {i + 2} : type « {t_}:{p_} » (types de santé mentale, "
                              "« :adultes » ou « :enfants » seulement pour lieu_cmp)")
        if not _jetons(r["types"]):
            fautes.append(f"etablissements.csv ligne {i + 2} : aucun type relu")
    # chaque structure est appliquée : une ligne d'etablissements.csv de son établissement couvre sa commune et porte
    # son type (16 lignes des lots du 18 novembre intégrées sans effet, audit du 19 novembre 2026)
    for i, r in s.iterrows():
        o = f"structures.csv ligne {i + 2} ({r['nom'][:40]})"
        lignes_e = e[(e["ej"] == r["ej"]) & ((e["departement"] == "") | (e["departement"] == dep_de.get(r["commune"])))]
        if lignes_e.empty:
            fautes.append(f"{o} : aucune ligne d'etablissements.csv de {r['ej']} ne couvre sa commune {r['commune']}")
            continue
        jet = dict(j_ for x in lignes_e["types"] for j_ in _jetons(x))
        if r["type"] not in jet:
            fautes.append(f"{o} : type {r['type']} absent de la colonne types de son établissement, la structure ne "
                          "serait pas appliquée" + (" (type déjà vérifié, à ne pas reprendre)" if comp else ""))
        elif jet[r["type"]] and r["public"] not in (jet[r["type"]], "adultes et enfants", ""):
            fautes.append(f"{o} : public « {r['public']} » hors du public relu ({jet[r['type']]})")
    if comp:
        # lot de reprise : chaque ligne reprend exactement un périmètre de completer.json, et chaque périmètre a sa ligne
        for k in sorted(set(comp) - cles_e):
            fautes.append(f"completer.json : périmètre {k[0]}, département « {k[1]} » sans ligne dans etablissements.csv "
                          "(le chercher, ou le retirer de completer.json pour qu'il revienne dans un prochain lot)")
        for i, r in e.iterrows():
            m = comp.get((r["ej"], r["departement"]))
            if m is None:
                fautes.append(f"etablissements.csv ligne {i + 2} : {r['ej']}, département « {r['departement']} », hors "
                              "du lot (voir completer.json pour le département attendu)")
            elif m["mode"] == "completer":
                ok, raison = fusion_types(m["types_deja"], r["types"])
                if ok is None:
                    fautes.append(f"etablissements.csv ligne {i + 2} : {raison}")
            else:
                manque = _bases_types(m["types_deja"]) - _bases_types(r["types"])
                if manque:
                    fautes.append(f"etablissements.csv ligne {i + 2} : revérification, les types déjà vérifiés sont tous "
                                  f"à reprendre ({', '.join(sorted(manque))} manque)")
    else:
        # lot ordinaire : jamais un périmètre déjà vérifié (il passe par un lot de reprise)
        glob_ = set(e_old.loc[e_old["departement"] == "", "ej"])
        vus = set(zip(e_old["ej"], e_old["departement"]))
        for i, r in e.iterrows():
            if r["ej"] in glob_ or (r["ej"], r["departement"]) in vus \
                    or (r["departement"] == "" and r["ej"] in set(e_old["ej"])):
                fautes.append(f"etablissements.csv ligne {i + 2} : {r['ej']}, département « {r['departement']} », déjà "
                              "vérifié (une ligne par département non vérifié, ou un lot de reprise)")
    # même structure sous deux établissements (CAARUD Beaurepaire à Paris sous l'association Charonne et sous Oppelia,
    # compté deux fois, audit du 19 novembre 2026) : même type, même commune et même adresse qu'une ligne d'un autre
    # établissement, dans le lot ou dans la liste vérifiée. « adresse partagée » en remarque, après vérification que ce
    # sont deux structures distinctes, en fait un simple avis, comme « doublon possible » sur une ligne non confirmée
    # (non tranché, dit au lecteur comme non confirmée).
    autres = pd.concat([s_old.assign(ou_="liste vérifiée"), s.assign(ou_="lot")], ignore_index=True)
    autres["voie_"] = autres["adresse"].map(voie_cle)
    for i, r in s.iterrows():
        if not r["adresse"]:
            continue
        v = voie_cle(r["adresse"])
        g = autres[(autres["ej"] != r["ej"]) & (autres["type"] == r["type"]) & (autres["commune"] == r["commune"])]
        for x in g[g["voie_"].map(lambda w: sv.meme_adresse(v, w))].itertuples():
            msg = (f"structures.csv ligne {i + 2} ({r['nom'][:40]}) : même type, commune et adresse que « {x.nom} » de "
                   f"{x.ej} ({x.ou_}), une seule ligne sous l'établissement qui la gère")
            ok = "adresse partagée" in r["remarque"].lower() or (
                "doublon possible" in r["remarque"].lower() and r["statut"] == "bases")
            (avis if ok else fautes).append(msg)
    if region_lot and not comp and (e["departement"] == "").any():
        bb = pd.read_parquet(BASES, columns=["ej", "type", "commune"])
        bb = bb[bb["type"].isin(TYPES_SM) & bb["ej"].isin(set(e.loc[e["departement"] == "", "ej"]))]
        bb = bb.assign(dep=bb["commune"].map(lambda c: (com.get(str(c)) or {}).get("departement", "")),
                       reg=bb["commune"].map(lambda c: (com.get(str(c)) or {}).get("region", "")))
        nationaux_ = set(bb.groupby("ej")["dep"].nunique().loc[lambda n: n > 3].index)   # dossier limité à la région
        ailleurs = bb[(bb["reg"] != region_lot.group(1)) & bb["ej"].isin(nationaux_)]
        for ej in sorted(set(ailleurs["ej"])):
            fautes.append(f"etablissements.csv : {ej} a des structures hors de la région, une ligne par département "
                          "vérifié avec la colonne departement remplie")
    for i, r in e.iterrows():
        if r["ej"] in attendus and r["ej"] not in set(s["ej"]):
            avis.append(f"etablissements.csv ligne {i + 2} : aucune structure pour {r['ej']}")
    # un type relu sans aucune ligne alors que les bases en inscrivent : ses inscriptions seraient perdues (hôpitaux de
    # jour pour enfants du bassin de Thau, 19 novembre 2026). Les recopier en bases, ou dire en remarque de
    # l'établissement pourquoi elles sont laissées de côté (« laissé », « laissée », « laissées de côté »).
    bb = _bases_dep()
    for i, r in e.iterrows():
        for t_, p_ in _jetons(r["types"]):
            ins = bb[(bb["ej"] == r["ej"]) & (bb["type"] == (f"{t_}_{p_}" if p_ else t_))
                     & ((bb["dep"] == r["departement"]) if r["departement"] else True)]
            lig = s[(s["ej"] == r["ej"]) & (s["type"] == t_)]
            if len(ins) and lig.empty and not re.search(r"laiss", r["remarque"], re.I):
                fautes.append(f"etablissements.csv ligne {i + 2} : {r['ej']}, aucune ligne {t_} alors que les bases en "
                              f"inscrivent {len(ins)} (les recopier en bases avec remarque, ou dire pourquoi elles sont "
                              "laissées de côté)")
    lignes = [f"# Contrôle du lot {lot.name}, {dt.datetime.now():%d/%m/%Y %H:%M}", "",
              f"{len(s)} structures, {len(e)} établissements, {len(pages)} pages ouvertes.", "", "## Fautes (bloquent)", ""]
    lignes += [f"- {x}" for x in fautes or ["aucune"]] + ["", "## À rouvrir à la main", ""]
    lignes += [f"- {x}" for x in avis or ["rien"]]
    (lot / "controle.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return fautes


def fondre_reprise(e_old: pd.DataFrame, s_old: pd.DataFrame, e: pd.DataFrame, b: pd.DataFrame, lot: Path,
                   comp: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fond chaque ligne d'un lot de reprise dans la ligne vérifiée du même périmètre.
    - completer : types ajoutés (fusion_types, contrôlée sur la ligne actuelle et non sur l'instantané du lot),
      sources réunies, date la plus ancienne (la vérification expire avec sa partie la plus vieille), remarque
      complétée. Refusé si la ligne est à revérifier (empreinte changée), pour ne jamais effacer ce signal.
    - reverifier : la ligne est remplacée (types, date, sources), l'ancienne remarque gardée après la nouvelle.
    Dans les deux cas, l'empreinte est recalculée sur tous les types, et les lignes de la liste vérifiée de ces types
    dans le périmètre (dormantes au complément, ancienne liste à la revérification) sont retirées : les structures du
    lot les remplacent. Renvoie la liste des établissements, celle des structures restantes et les lignes retirées."""
    from pipeline import structures_verifiees as sv
    from pipeline.sources import referentiel
    dep_de = referentiel.charger(True, False).communes.set_index("code")["dep"].to_dict()
    enf = sum(sv.ENFANTS_DE.values(), [])
    e_old, retirer = e_old.copy(), pd.Series(False, index=s_old.index)
    for _, r in e.iterrows():
        m = comp[(r["ej"], r["departement"])]
        k = e_old.index[(e_old["ej"] == r["ej"]) & (e_old["departement"] == r["departement"])]
        if len(k) != 1:
            sys.exit(f"{r['ej']}, département « {r['departement']} » : {len(k)} lignes vérifiées au lieu d'une. "
                     "Rien n'est intégré.")
        k = k[0]
        old = e_old.loc[k]
        quand = f"{dt.date.fromisoformat(r['date']):%d/%m/%Y}"
        if m["mode"] == "completer":
            ts_old = [t for t in sv.types_de(old["types"]) if t not in enf]
            if old["empreinte"] and sv.empreinte(b, old["ej"], ts_old, old["departement"]) != old["empreinte"]:
                sys.exit(f"{old['etablissement']} : inscriptions changées depuis la vérification du {old['date']}, à "
                         "revérifier en entier (lot de reprise) avant d'être complété. Rien n'est intégré.")
            types, raison = fusion_types(old["types"], r["types"])
            if types is None:
                sys.exit(f"{old['etablissement']} : {raison}. Rien n'est intégré.")
            e_old.loc[k, "sources"] = old["sources"] if r["sources"] in old["sources"] else \
                f"{old['sources']} ; {r['sources']}"
            e_old.loc[k, "date"] = min(old["date"], r["date"]) if old["date"] else r["date"]
            e_old.loc[k, "remarque"] = (f"{old['remarque']} Complété le {quand} ({r['types']}, lot {lot.name}) : "
                                        f"{r['remarque']}").strip()
            retirer |= _dormantes(s_old, r["ej"], r["departement"], r["types"].split(","), dep_de)
        else:
            types = r["types"]
            e_old.loc[k, "sources"] = r["sources"]
            e_old.loc[k, "date"] = r["date"]
            e_old.loc[k, "remarque"] = (f"Revérifié le {quand} (lot {lot.name}) : {r['remarque']} Vérification du "
                                        f"{old['date']} : {old['remarque']}").strip()
            retirer |= _dormantes(s_old, r["ej"], r["departement"],
                                  sorted(_bases_types(old["types"]) | _bases_types(types)), dep_de)
        e_old.loc[k, "types"] = types
        e_old.loc[k, "empreinte"] = sv.empreinte(b, old["ej"], [t for t in sv.types_de(types) if t not in enf],
                                                 old["departement"])
    return e_old, s_old[~retirer], s_old[retirer]


def integrer(lot: Path) -> None:
    if valider(lot):
        sys.exit(f"Le lot {lot.name} a des fautes, voir {lot / 'controle.md'}. Rien n'est intégré.")
    from pipeline import structures_verifiees as sv
    s = pd.read_csv(lot / "structures.csv", sep=";", dtype=str).fillna("")
    e = pd.read_csv(lot / "etablissements.csv", sep=";", dtype=str).fillna("")
    # empreinte sur le périmètre de la ligne, comme dans appliquer (sans département, l'empreinte d'une ligne d'un
    # seul département couvrait tous ceux de l'établissement : 136 établissements signalés à tort, 19 novembre 2026)
    b = _bases_dep()
    e_old, s_old = sv.charger()
    comp = _complement(lot)
    ejs, n_e = set(e["ej"]), len(e)
    retirees = pd.DataFrame(columns=sv.COLS)
    if comp:
        e_old, s_old, retirees = fondre_reprise(e_old, s_old, e, b, lot, comp)
        e = pd.DataFrame(columns=sv.COLS_ETAB)
    else:
        # un même établissement peut être vérifié département par département, jamais deux fois pour le même périmètre
        cles = lambda d: {(a, b) for a, b in zip(d["ej"], d["departement"])}  # noqa: E731
        globaux = set(e_old.loc[e_old["departement"] == "", "ej"])
        doublons = (cles(e) & cles(e_old)) | {(a, b) for a, b in cles(e)
                                              if a in globaux or (b == "" and a in set(e_old["ej"]))}
        if doublons:
            sys.exit(f"Établissements déjà vérifiés pour ce périmètre : {sorted(doublons)}. Rien n'est intégré.")
        enf = sum(sv.ENFANTS_DE.values(), [])
        e = e.assign(empreinte=[sv.empreinte(b, r["ej"], [t for t in sv.types_de(r["types"]) if t not in enf],
                                             r["departement"]) for _, r in e.iterrows()])[sv.COLS_ETAB]
    # écriture, puis essai à blanc ; en cas d'échec ou d'interruption, les deux listes reviennent à leur état d'avant
    # (lot r44-01 du 18 novembre 2026, un doublon découvert après l'écriture)
    avant = (sv.FICHIER_ETAB.read_bytes(), sv.FICHIER.read_bytes(),
             sv.FICHIER_LAISSEES.read_bytes() if sv.FICHIER_LAISSEES.exists() else None)
    try:
        pd.concat([e_old, e], ignore_index=True).to_csv(sv.FICHIER_ETAB, sep=";", index=False, encoding="utf-8")
        pd.concat([s_old, s[sv.COLS]], ignore_index=True).to_csv(sv.FICHIER, sep=";", index=False, encoding="utf-8")
        if (lot / "laissees.csv").exists():
            cle = ["ej", "type", "commune", "nom"]
            lai = pd.read_csv(lot / "laissees.csv", sep=";", dtype=str).fillna("")
            pd.concat([sv.charger_laissees(), lai], ignore_index=True).drop_duplicates(cle, keep="last")[
                sv.COLS_LAISSEES].to_csv(sv.FICHIER_LAISSEES, sep=";", index=False, encoding="utf-8")
        rendu = essai(ejs, lot / "non_retenues.csv")
    except BaseException as ex:  # noqa: BLE001
        sv.FICHIER_ETAB.write_bytes(avant[0])
        sv.FICHIER.write_bytes(avant[1])
        if avant[2] is not None:
            sv.FICHIER_LAISSEES.write_bytes(avant[2])
        elif sv.FICHIER_LAISSEES.exists():
            sv.FICHIER_LAISSEES.unlink()
        sys.exit(f"Essai à blanc en échec ({ex!r}). Rien n'est intégré, les listes sont revenues à leur état d'avant.")
    if len(retirees):
        retirees.to_csv(lot / "lignes_remplacees.csv", sep=";", index=False, encoding="utf-8")
    # géocodage des adresses nouvelles (en ligne), pour que la chaîne hors ligne les trouve dans le cache ; oublié par
    # cet outil jusqu'au 20 novembre 2026 (1 640 adresses vérifiées posées au centre de leur commune)
    from pipeline.lieux import _geocoder
    _geocoder(s[["adresse", "commune"]].rename(columns={"adresse": "voie"}), False)
    quoi = "repris" if comp else "établissements"
    (lot / "integre.txt").write_text(f"Intégré le {dt.datetime.now():%d/%m/%Y %H:%M}, {n_e} {quoi}, "
                                     f"{len(s)} structures, {len(retirees)} anciennes lignes remplacées.\n",
                                     encoding="utf-8")
    print(f"Lot {lot.name} intégré : {n_e} {quoi}, {len(s)} structures, {len(retirees)} anciennes lignes remplacées.")
    print(rendu)


def essai(ejs: set | None = None, sortie: Path | None = None) -> str:
    """Applique à blanc toutes les listes vérifiées aux inscriptions du dernier calcul (pipeline/structures_verifiees),
    pour qu'un lot intégré ne bloque jamais l'édition suivante (structures en double, colonne manquante)."""
    from pipeline import structures_verifiees as sv
    from pipeline.sources import referentiel
    ref = referentiel.charger(True, False)
    lieux = pd.read_parquet(BASES)
    lieux["dep"] = lieux["commune"].map(ref.communes.set_index("code")["dep"])
    out, rendu = sv.appliquer(lieux, ref, None, True, garder=set(), fermees={})
    if ejs and sortie:
        # inscriptions laissées de côté chez les établissements du lot, à relire selon la règle du mode d'emploi
        nr = pd.DataFrame(rendu["non_retenues"])
        if len(nr):
            nr[nr["ej"].isin(ejs)].to_csv(sortie, sep=";", index=False, encoding="utf-8")
        # inscriptions gardées faute de raison écrite pour les laisser de côté (laissees.csv du lot)
        ga = pd.DataFrame(rendu["gardees"])
        if len(ga):
            ga[ga["ej"].isin(ejs)].to_csv(sortie.with_name("gardees.csv"), sep=";", index=False, encoding="utf-8")
    return (f"essai à blanc réussi : {len(rendu['etablissements'])} établissements vérifiés, {len(out)} structures, "
            f"{rendu['ajoutees']} ajoutées, {len(rendu['non_retenues'])} inscriptions non retenues")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    sous = ap.add_subparsers(dest="cmd", required=True)
    p = sous.add_parser("preparer")
    p.add_argument("--region", required=True)
    p.add_argument("--taille", type=int, default=4)
    p.add_argument("--nationaux", action="store_true", help="associations de plus de trois départements")
    p.add_argument("--toutes", action="store_true", help="aussi les structures dites confirmées par le croisement")
    p.add_argument("--completer", action="store_true",
                   help="établissements déjà vérifiés : types pas encore relus, ou revérification")
    for c in ("valider", "integrer"):
        sous.add_parser(c).add_argument("lot")
    a = ap.parse_args()
    if a.cmd == "preparer":
        if a.completer:
            preparer_reprise(a.region, a.taille)
        else:
            preparer(a.region, a.taille, a.nationaux, a.toutes)
    else:
        lot = DOSSIER / a.lot
        if a.cmd == "valider":
            f = valider(lot)
            print(f"Lot {a.lot} : {len(f)} faute(s), détail dans {lot / 'controle.md'}")
            sys.exit(20 if f else 0)
        integrer(lot)
