"""DREES, démographie des professionnels de santé depuis 2012 (Licence Ouverte).

Séries officielles d'effectifs par profession, département et année, tirées du RPPS (médecins, chirurgiens-dentistes,
masseurs-kinésithérapeutes, sages-femmes, pharmaciens, pédicures-podologues), du répertoire Adeli jusqu'en 2024
(psychologues, professions de rééducation et médico-techniques), du SNDS et de la base Tous salariés de l'INSEE pour
les infirmières. Elles ne servent à aucun résultat. Elles servent de référence publiée au tableau de concordance
(pipeline/concordance.py), qui vérifie nos effectifs profession par profession, au national et par département.

Les classeurs sont listés par l'API Opendatasoft de la DREES (config.DREES_DEMOGRAPHIE_API), aucune adresse de
fichier n'est écrite en dur. La date de mise à jour de chaque pièce jointe (en-tête Last-Modified) est consignée.
Les classeurs sont lourds (73 Mo pour les médecins), seul un résumé (France et départements, toutes catégories
confondues) est relu d'une exécution à l'autre."""
from __future__ import annotations

import hashlib
import json
import re

import pandas as pd

from .. import config
from ..util import JOURNAL, _session, get_json, lire_meta, log, norm, telecharger

SOURCE = "DREES, démographie des professionnels de santé"
DOSSIER = config.BRUT / "drees_demographie"


def _pieces_jointes():
    """{motif: (url, last_modified, titre)} pour chaque motif de config.DREES_DEMOGRAPHIE."""
    pj = get_json(config.DREES_DEMOGRAPHIE_API + "/attachments").get("attachments", [])
    s, out = _session(), {}
    for motif in dict.fromkeys(x[0] for x in config.DREES_DEMOGRAPHIE):
        cand = [a["metas"] for a in pj if re.search(motif, norm(a["metas"].get("title", "")))
                and norm(a["metas"].get("title", "")).endswith("xlsx")]
        if not cand:
            continue
        # si plusieurs versions restent en ligne, la série qui va le plus loin l'emporte
        c = max(cand, key=lambda c: max(map(int, re.findall(r"(20\d\d)", c.get("title", "")) or [0])))
        date = s.head(c["url"], timeout=60, allow_redirects=True).headers.get("Last-Modified", "")
        out[motif] = (c["url"], date, c.get("title", ""))
    return out


def _fichier(motif):
    return DOSSIER / (re.sub(r"[^a-z]+", "_", motif).strip("_") + ".xlsx")


def _code_dep(v):
    """« 075 -Paris », « 75-Paris », « 971 - Guadeloupe », « 2A-Corse-du-Sud » donnent 75, 971, 2A."""
    m = re.match(r"^\s*(\w{2,3})\s*-", str(v))
    if not m:
        return None
    c = m.group(1).upper()
    if len(c) == 3 and c.startswith("0"):
        c = c[1:]
    return None if c.strip("0") == "" else c


def _ensemble(v):
    n = norm(v)
    return "ensemble" in n or "france entiere" in n or "region entiere" in n


def _lire(chemin, specs, age=False):
    """Lit la feuille des effectifs et garde, pour chaque motif de spécialité (None pour toutes), la France et les
    départements, toutes les autres dimensions à « Ensemble ». Renvoie un DataFrame (spec, niveau, code, annee,
    effectif) pour chaque année publiée. Avec age=True, la tranche d'âge est gardée (colonne tranche, « Ensemble »
    compris), les autres dimensions restant à « Ensemble »."""
    import openpyxl
    wb = openpyxl.load_workbook(chemin, read_only=True)
    ws = next(w for w in wb.worksheets if norm(w.title).startswith("effectif"))
    lignes = ws.iter_rows(values_only=True)
    entete = [norm(h) if h is not None else "" for h in next(lignes)]
    annees = {j: int(m.group(1)) for j, h in enumerate(entete) if (m := re.match(r"effectif (\d{4})$", h))}
    j_dep = next(j for j, h in enumerate(entete) if h.startswith("departement"))
    j_reg = next((j for j, h in enumerate(entete) if h.startswith("region")), None)
    j_ter = next((j for j, h in enumerate(entete) if h.startswith("territoire")), None)
    j_spe = next((j for j, h in enumerate(entete) if h == "specialites"), None)
    j_agr = next((j for j, h in enumerate(entete) if h == "specialites agregees"), None)
    j_age = next((j for j, h in enumerate(entete) if h.startswith("tranche age")), None) if age else None
    if age and j_age is None:
        return None
    autres = [j for j, h in enumerate(entete) if h and j not in annees and j not in (j_dep, j_reg, j_ter, j_spe, j_agr, j_age)]
    out = []
    for r in lignes:
        if not r or r[j_dep] is None or not all(_ensemble(r[j]) for j in autres):
            continue
        dep_ens = _ensemble(r[j_dep])
        if dep_ens:
            if j_reg is not None and not _ensemble(r[j_reg]):
                continue
            if j_ter is not None and not str(r[j_ter]).startswith("0"):
                continue
            niveau, code = "france", "FR"
        else:
            niveau, code = "dep", _code_dep(r[j_dep])
            if code is None:
                continue
        for spec in specs:
            if spec is None:
                ok = j_spe is None or (_ensemble(r[j_spe]) and (j_agr is None or _ensemble(r[j_agr])))
            elif spec.startswith("agr:"):   # spécialités agrégées (« autres spécialités », hors médecine générale)
                ok = (j_agr is not None and (j_spe is None or _ensemble(r[j_spe]))
                      and re.search(spec[4:], norm(re.sub(r"^\d+-", "", str(r[j_agr])))) is not None)
            else:
                ok = j_spe is not None and re.search(spec, norm(re.sub(r"^\d+-", "", str(r[j_spe])))) is not None
            if ok:
                for j, a in annees.items():
                    out.append((spec or "", niveau, code, a, r[j]) + ((str(r[j_age]),) if age else ()))
    wb.close()
    d = pd.DataFrame(out, columns=["spec", "niveau", "code", "annee", "effectif"] + (["tranche"] if age else []))
    d["effectif"] = pd.to_numeric(d["effectif"], errors="coerce")
    return d


def _resume(chemin, specs):
    """Résumé en cache, refait si le classeur ou la liste des spécialités a changé."""
    cle = hashlib.sha1(json.dumps([s or "" for s in specs]).encode()).hexdigest()[:10]
    res = chemin.with_suffix(f".{cle}.csv")
    if res.exists() and res.stat().st_mtime >= chemin.stat().st_mtime:
        return pd.read_csv(res, sep=";", dtype={"code": str, "spec": str}, keep_default_na=False,
                           na_values=[""]).assign(spec=lambda d: d["spec"].fillna(""))
    log.info("lecture de %s", chemin.name)
    d = _lire(chemin, specs)
    # seuls les anciens résumés sans âge sont effacés, le résumé par âge (« .ages. ») a son propre cache
    for vieux in chemin.parent.glob(chemin.stem + ".*.csv"):
        if re.fullmatch(re.escape(chemin.stem) + r"\.[0-9a-f]{10}\.csv", vieux.name):
            vieux.unlink()
    d.to_csv(res, sep=";", index=False)
    return d


def charger(hors_ligne=False, rafraichir=False):
    """Renvoie un DataFrame (motif, spec, niveau, code, annee, effectif, titre, maj_source) ou None."""
    try:
        pj = None if hors_ligne else _pieces_jointes()
    except Exception as e:  # noqa: BLE001
        JOURNAL.note(SOURCE, "erreur", str(e)[:300])
        return None
    tables, titres = [], []
    for motif in dict.fromkeys(x[0] for x in config.DREES_DEMOGRAPHIE):
        dest = _fichier(motif)
        try:
            if pj is not None:
                if motif not in pj:
                    JOURNAL.note(f"{SOURCE}, {motif}", "absent", "pièce jointe introuvable")
                    continue
                url, maj, titre = pj[motif]
                ancien = lire_meta(dest).get("maj_source")
                telecharger(url, dest, "drees_demographie", rafraichir or (bool(ancien) and ancien != maj),
                            extra_meta={"maj_source": maj, "titre": titre})
            elif not dest.exists():
                continue
            specs = list(dict.fromkeys(x[1] for x in config.DREES_DEMOGRAPHIE if x[0] == motif))
            meta = lire_meta(dest)
            d = _resume(dest, specs).assign(motif=motif, titre=meta.get("titre", dest.name),
                                            maj_source=meta.get("maj_source", ""))
            tables.append(d)
            titres.append(meta.get("titre", dest.name))
        except Exception as e:  # noqa: BLE001
            JOURNAL.note(f"{SOURCE}, {motif}", "erreur", str(e)[:300])
    if not tables:
        return None
    d = pd.concat(tables, ignore_index=True)
    dates = sorted(pd.to_datetime(d["maj_source"], errors="coerce", utc=True).dropna())
    JOURNAL.note(SOURCE, "ok", f"{len(titres)} séries lues (référence du tableau de concordance)",
                 url=config.DREES_DEMOGRAPHIE_PAGE, date_donnees=dates[-1].date().isoformat() if dates else "")
    return d


# ---------------------------------------------------------------- âge des professionnels (28 octobre 2026)
GROUPE_AGE = "Âge des professionnels"
AGE_SEUIL = 60


def _borne(tranche: str) -> int | None:
    """Âge le plus bas d'une tranche de la DREES, « 08-entre 60 et 64 ans » donne 60, « 10- 65 ans et plus » 65,
    « 01-moins de 25 ans » 0, « Ensemble » None."""
    t = norm(re.sub(r"^\s*\d+\s*-\s*", "", str(tranche)))
    if "ensemble" in t:
        return None
    if t.startswith("moins"):
        return 0
    m = re.search(r"(\d+)", t)
    return int(m.group(1)) if m else None


def _resume_ages(chemin, specs):
    """Résumé par tranche d'âge en cache (« .ages. »), refait si le classeur ou la liste des spécialités a changé."""
    cle = hashlib.sha1(json.dumps([s or "" for s in specs]).encode()).hexdigest()[:10]
    res = chemin.with_suffix(f".ages.{cle}.csv")
    if res.exists() and res.stat().st_mtime >= chemin.stat().st_mtime:
        return pd.read_csv(res, sep=";", dtype={"code": str, "spec": str, "tranche": str}, keep_default_na=False,
                           na_values=[""]).assign(spec=lambda d: d["spec"].fillna(""))
    log.info("lecture des âges de %s", chemin.name)
    d = _lire(chemin, specs, age=True)
    if d is None:
        return None
    for vieux in chemin.parent.glob(chemin.stem + ".ages.*.csv"):
        vieux.unlink()
    d.to_csv(res, sep=";", index=False)
    return d


def ages(familles: dict) -> dict | None:
    """Part des professionnels de 60 ans et plus par département, d'après les classeurs de la DREES déjà en cache
    (lus par charger()). Professions du RPPS et infirmiers libéraux (SNDS) seulement, les séries d'Adeli ne comptant
    que les actifs de moins de 62 ans, ce qui fausserait la part des 60 ans et plus. Renvoie {"contexte": {"dep"},
    "defs": [...], "table": DataFrame (première et dernière année, France et départements)} ou None. familles donne
    la famille de chaque profession (santé mentale ou santé)."""
    lignes, defs, cols = [], [], {}
    try:
        for motif in dict.fromkeys(x[0] for x in config.DREES_DEMOGRAPHIE):
            entrees = [x for x in config.DREES_DEMOGRAPHIE if x[0] == motif and x[5] != config._ADELI]
            f = _fichier(motif)
            if not entrees or not f.exists():
                continue
            d = _resume_ages(f, list(dict.fromkeys(x[1] for x in entrees)))
            if d is None or d.empty:
                continue
            d["borne"] = d["tranche"].map(_borne)
            for _m, spec, _mode, profs, lib, _src in entrees:
                x = d[d["spec"] == (spec or "")]
                if x.empty:
                    continue
                ident = "age60_" + ("medecins" if profs == ["medecins"] else profs[0] if len(profs) <= 2 else "chirurgiens")
                if profs == ["infirmier"]:
                    ident = "age60_infirmier_liberal"
                tot = x[x["borne"].isna()].groupby(["niveau", "code", "annee"])["effectif"].sum()
                plus = x[x["borne"] >= AGE_SEUIL].groupby(["niveau", "code", "annee"])["effectif"].sum()
                somme = x[x["borne"].notna()].groupby(["niveau", "code", "annee"])["effectif"].sum()
                t = pd.DataFrame({"effectif": tot, "plus_60": plus, "somme_tranches": somme}).fillna({"plus_60": 0}).reset_index()
                # vrais départements seulement, le code 999 de la DREES regroupe les cas non localisés
                t = t[(t["effectif"] > 0) & ((t["niveau"] == "france") | t["code"].str.fullmatch(r"\d{2}|2A|2B|97\d"))]
                t["part_60"] = t["plus_60"] / t["effectif"]
                a0, a1 = int(t["annee"].min()), int(t["annee"].max())
                t = t[t["annee"].isin([a0, a1])].assign(indicateur=ident, libelle=lib, professions=",".join(profs))
                lignes.append(t)
                dep = t[(t["niveau"] == "dep") & (t["annee"] == a1)].set_index("code")
                cols[ident] = dep["part_60"] * 100
                fam = familles.get(profs[0], config.SANTE)
                defs.append({
                    "id": ident, "libelle": f"Part des {AGE_SEUIL} ans et plus, {lib.lower()}", "unite": "%",
                    "explication": f"Part des {lib.lower()} âgés de {AGE_SEUIL} ans ou plus au 1er janvier {a1}, "
                                   f"d'après la DREES. La DREES compte chaque professionnel une fois, dans le "
                                   f"département de son activité principale, ce qui diffère des comptages par lieu "
                                   f"d'exercice du reste du site. Repère du renouvellement à venir, pas une prévision "
                                   f"de départs.",
                    "source": SOURCE, "famille": fam, "licence": "Licence Ouverte 2.0", "niveau_origine": "dep",
                    "groupe": GROUPE_AGE})
    except Exception as e:  # noqa: BLE001
        JOURNAL.note(f"{SOURCE}, âge des professionnels", "erreur", str(e)[:300])
        return None
    if not lignes:
        JOURNAL.note(f"{SOURCE}, âge des professionnels", "absent", "classeurs de la DREES absents du cache")
        return None
    table = pd.concat(lignes, ignore_index=True)
    fr = table[table["niveau"] == "france"]
    ecart = ((fr["somme_tranches"] - fr["effectif"]).abs() / fr["effectif"]).max()
    JOURNAL.controle("DREES, âge des professionnels, tranches d'âge additionnées face à l'effectif publié (France)",
                     f"{len(cols)} séries, écart maximal {ecart * 100:.2f} %".replace(".", ","))
    med = fr[(fr["indicateur"] == "age60_medecin_generaliste") & (fr["annee"] == fr["annee"].max())]
    JOURNAL.note(f"{SOURCE}, âge des professionnels", "ok",
                 f"{len(cols)} séries, part des {AGE_SEUIL} ans et plus chez les médecins généralistes en France "
                 + (f"{med['part_60'].iloc[0] * 100:.1f} %".replace(".", ",") if len(med) else "non disponible"),
                 url=config.DREES_DEMOGRAPHIE_PAGE)
    return {"contexte": {"dep": pd.DataFrame(cols)}, "defs": defs, "table": table}
