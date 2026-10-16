"""DREES, Statistique annuelle des établissements de santé (SAE), bordereau psychiatrie (Licence Ouverte).

Les bases statistiques sont publiées chaque année en pièces jointes du jeu 708 du portail de la DREES, dans une
archive 7z (formats SAS et CSV). Le programme prend le millésime le plus récent, n'extrait que le bordereau PSY
(lits, places, CMP, file active, personnels de psychiatrie, par établissement et par discipline) et la table
d'identification (département de l'établissement), puis supprime l'archive. La date de modification de
l'archive côté producteur est consignée (maj_source).

Le RPPS compte des personnes, la SAE des équivalents temps plein salariés et des capacités. Les deux se lisent
côte à côte. Un établissement est rattaché au département où il est enregistré, même si certaines de ses
structures (CMP, hôpitaux de jour) sont situées dans un département voisin."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime

import pandas as pd

from .. import config
from ..util import JOURNAL, get_json, lire_meta, log, meta_path, telecharger

DOSSIER = config.BRUT / "sae"
PAGE = "https://data.drees.solidarites-sante.gouv.fr/explore/dataset/708_bases-statistiques-sae/"
SOURCE = "DREES, Statistique annuelle des établissements de santé (SAE), bordereau psychiatrie"


def _archive():
    """Adresse et millésime de l'archive CSV la plus récente."""
    att = get_json(config.SAE_API + "/attachments").get("attachments", [])
    cands = []
    for a in att:
        m = re.search(config.SAE_MOTIF, a.get("href", ""))
        if m:
            cands.append((int(m.group(1)), a["href"]))
    if not cands:
        raise IOError("aucune archive des bases statistiques SAE au format CSV")
    return max(cands)


def _telecharger(hors_ligne, rafraichir):
    DOSSIER.mkdir(parents=True, exist_ok=True)
    psy, ident = DOSSIER / "psy.csv", DOSSIER / "id.csv"
    meta = lire_meta(psy)
    if hors_ligne:
        if not psy.exists():
            raise FileNotFoundError(psy)
        return psy, ident, meta
    # en ligne, le millésime et la date de l'archive chez le producteur décident, pas l'âge du cache
    annee, url = _archive()
    import requests
    maj = requests.head(url, timeout=60, allow_redirects=True).headers.get("Last-Modified", "")
    if psy.exists() and meta.get("annee") == annee and meta.get("maj_source") == maj and not rafraichir:
        psy.touch()
        return psy, ident, meta
    import py7zr
    tmp = DOSSIER / f"sae_{annee}.7z"
    telecharger(url, tmp, "sae", rafraichir=True, taille_min=1_000_000)
    try:
        with py7zr.SevenZipFile(tmp) as z:
            noms = z.getnames()
            cibles = {n for n in noms if re.search(rf"/(PSY|ID)_{annee}r?\.csv$", n, re.I)}
            z.extract(path=DOSSIER / "tmp", targets=list(cibles))
        for n in cibles:
            dest = psy if re.search(r"/PSY_", n, re.I) else ident
            shutil.move(str(DOSSIER / "tmp" / n), dest)
    finally:
        tmp.unlink(missing_ok=True)
        meta_path(tmp).unlink(missing_ok=True)
        shutil.rmtree(DOSSIER / "tmp", ignore_errors=True)
    meta = {"url": url, "annee": annee, "maj_source": maj, "telecharge_le": datetime.now().isoformat(timespec="seconds")}
    meta_path(psy).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("SAE %s, bordereau psychiatrie extrait", annee)
    return psy, ident, meta


def charger(ref, ctx_dep=None, hors_ligne=False, rafraichir=False):
    """Renvoie {"contexte": {"dep", "reg"}, "defs": [...], "table": DataFrame, "annee"} ou None."""
    try:
        psy, ident, meta = _telecharger(hors_ligne, rafraichir)
        p = pd.read_csv(psy, sep=";", encoding="latin-1", low_memory=False, dtype={"FI": str})
        i = pd.read_csv(ident, sep=";", encoding="latin-1", low_memory=False, dtype=str)
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("DREES, SAE psychiatrie", "erreur", str(e)[:300])
        return None
    i.columns = [c.lower() for c in i.columns]
    # la SAE code les départements d'outre-mer 9A à 9F
    dep_fi = i.drop_duplicates("fi").set_index("fi")["dep"].str.strip().replace(config.SAE_DEPARTEMENTS_OUTRE_MER)
    p["dep"] = p["FI"].map(dep_fi)
    JOURNAL.controle("SAE, établissements de psychiatrie rattachés à un département du référentiel",
                     f"{p['dep'].isin(ref.deps['code']).mean():.1%}")
    pop_dep = ref.deps.set_index("code")["pop"].astype(float)
    pop_reg = ref.regs.set_index("code")["pop"].astype(float)
    dep_reg = ref.deps.set_index("code")["reg"]
    p0014 = None
    if ctx_dep is not None and "part_0_14" in ctx_dep:
        p0014 = pop_dep * ctx_dep["part_0_14"].reindex(pop_dep.index) / 100
    ctx, defs, lignes = {"dep": {}, "reg": {}}, [], []
    for iid, dis, cols, lab, unite, par, expl in config.SAE_INDICATEURS:
        x = p[p["DIS"] == dis]
        somme = x.groupby("dep")[cols].sum(min_count=1).sum(axis=1, min_count=1)
        somme = somme.reindex(pop_dep.index).fillna(0)
        if par == "moins15":
            if p0014 is None:
                continue
            den_dep, den_reg = p0014, p0014.groupby(dep_reg).sum()
        else:
            den_dep, den_reg = pop_dep, pop_reg
        fac = 1e3 if "1 000" in unite else 1e5
        v_dep = somme / den_dep * fac
        v_reg = somme.groupby(dep_reg).sum() / den_reg * fac
        ctx["dep"][iid], ctx["reg"][iid] = v_dep, v_reg
        for niv, v, n in [("dep", v_dep, somme), ("reg", v_reg, somme.groupby(dep_reg).sum())]:
            lignes.append(pd.DataFrame({"niveau": niv, "code": v.index, "indicateur": iid, "valeur": v.to_numpy(),
                                        "nombre": n.reindex(v.index).to_numpy()}))
        lignes.append(pd.DataFrame({"niveau": ["FR"], "code": ["FR"], "indicateur": [iid],
                                    "valeur": [somme.sum() / den_dep.sum() * fac], "nombre": [somme.sum()]}))
        defs.append({"id": iid, "libelle": lab, "unite": unite, "explication": expl + f" Année {meta.get('annee', '')}.",
                     "source": SOURCE, "famille": config.SANTE_MENTALE, "licence": "Licence Ouverte 2.0",
                     "niveau_origine": "dep", "annee": meta.get("annee"), "groupe": config.GROUPE_HOPITAL_PSY})
    try:
        from email.utils import parsedate_to_datetime
        maj = parsedate_to_datetime(meta.get("maj_source", "")).date().isoformat()
    except Exception:  # noqa: BLE001
        maj = ""
    JOURNAL.note("DREES, SAE psychiatrie", "ok",
                 f"année {meta.get('annee', '')}, {p['FI'].nunique()} établissements, {len(defs)} indicateurs",
                 url=PAGE, date_donnees=maj)
    # CMP déclarés par discipline (psychiatrie générale, infanto-juvénile) et par département de l'établissement,
    # pour confronter les CMP recensés par FINESS et le ROR à une source indépendante (12 octobre 2026)
    q = p[p["DIS"].isin(["GEN", "INF"])].copy()
    q["NB_CMP_SEUL"] = pd.to_numeric(q["NB_CMP_SEUL"], errors="coerce")
    cmp_dis = q.groupby(["dep", "DIS"])["NB_CMP_SEUL"].sum().unstack(fill_value=0)
    # file active ambulatoire et psychiatres salariés par discipline et département, pour la charge par CMP
    # (pipeline/structures_analyses.py, 15 octobre 2026)
    for col in ("FIL_AMB", "ETPSAL_PKT"):
        q[col] = pd.to_numeric(q[col], errors="coerce")
    charge = q.groupby(["dep", "DIS"])[["FIL_AMB", "NB_CMP_SEUL", "ETPSAL_PKT"]].sum(min_count=1).reset_index()
    # par entité juridique (hôpital), pour confronter les CMP et CATTP établissement par établissement (13 octobre 2026)
    q["NB_CATTP"] = pd.to_numeric(q["NB_CATTP"], errors="coerce")
    # par établissement géographique (FI), avec son entité juridique de l'année de la SAE, ramenée ensuite à l'entité
    # actuelle de FINESS (fusions d'hôpitaux depuis la collecte)
    ej = q.groupby(["FI", "DIS"])["NB_CMP_SEUL"].sum().unstack(fill_value=0).rename(
        columns={"GEN": "sae_adultes", "INF": "sae_enfants"})
    for c in ("sae_adultes", "sae_enfants"):
        if c not in ej:
            ej[c] = 0
    ej["sae_cattp"] = q.groupby("FI")["NB_CATTP"].sum()
    une = q.drop_duplicates("FI").set_index("FI")
    ej["ej_sae"] = une["FI_EJ"].reindex(ej.index)
    ej["nom_sae"] = une["RS"].reindex(ej.index)
    ej["dep_siege"] = une["dep"].reindex(ej.index)
    ej.index.name = "fi"
    return {"contexte": {niv: pd.DataFrame(v) for niv, v in ctx.items()}, "defs": defs,
            "table": pd.concat(lignes, ignore_index=True), "annee": meta.get("annee"), "cmp_disciplines": cmp_dis, "charge_disciplines": charge,
            "etablissements": ej}
