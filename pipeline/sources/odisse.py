"""Santé publique France, portail Odissé (Opendatasoft, Licence Ouverte 2.0).

Indicateurs de besoin en santé mentale moins dépendants de l'offre que les patients pris en charge,
décès par suicide, gestes auto-infligés (hospitalisations et urgences), et réponses au Baromètre de
Santé publique France (épisodes dépressifs, pensées suicidaires, tentatives de suicide déclarés).

Chaque indicateur est décrit dans config.ODISSE. Récupération automatique par l'API, filtrée sur les
lignes utiles, avec la date de modification du jeu consignée. L'année la plus récente est retenue.
Un indicateur publié par région reste au niveau régional."""
from __future__ import annotations

from urllib.parse import quote

import pandas as pd

from .. import config
from ..util import JOURNAL, get_json, lire_meta, slug, telecharger


def _code(s: pd.Series, niveau: str) -> pd.Series:
    s = s.astype(str).str.strip().str.upper()
    if niveau == "dep":   # « 005 » devient « 05 », « 971 » et « 2A » restent tels quels
        s = s.where(~(s.str.len().eq(3) & s.str.startswith("0")), s.str[1:])
    return s.str.zfill(2)


def _sans_accents(t: str) -> str:
    """Nom de région comparable : sans accents, casse, article de tête ni ponctuation (« Ile-de-France » comme
    « Île-de-France », « Réunion » comme « La Réunion »)."""
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower().strip()
    t = re.sub(r"^(la|le|les|l')\s*", "", t)
    return re.sub(r"[^a-z0-9]", "", t)


def codes_regions_par_nom(noms: pd.Series, ref) -> tuple[pd.Series, list[str]]:
    """Certains jeux du Baromètre 2024 nomment la région au lieu de donner son code (12 novembre 2026). Renvoie les
    codes et la liste des noms non reconnus ; la ligne « Tous », la France entière, est écartée sans être une erreur."""
    table = {_sans_accents(n): c for c, n in zip(ref.regs["code"], ref.regs["nom"])}
    cles = noms.map(_sans_accents)
    codes = cles.map(table)
    inconnus = sorted(set(noms[codes.isna() & (cles != "tous")]))
    return codes, inconnus


def _telecharger(ind, hors_ligne, rafraichir):
    dest = config.BRUT / f"odisse_{slug(ind['id'])}.csv"
    if hors_ligne:
        if not dest.exists():
            raise FileNotFoundError(dest)
        return dest
    meta = get_json(config.ODISSE_API + ind["dataset"])
    maj = (meta.get("metas", {}).get("default", {}) or {}).get("modified", "")
    cols = ["annee", ind["code"], ind["valeur"]] + [ind[k] for k in ("ic_bas", "ic_haut") if ind.get(k)]
    url = (config.ODISSE_API + ind["dataset"] + "/exports/csv?delimiter=%3B&select=" + quote(",".join(cols))
           + "&where=" + quote(ind["where"]))
    ancien = lire_meta(dest).get("maj_source")
    telecharger(url, dest, "odisse", rafraichir or (bool(ancien) and ancien != maj), taille_min=50,
                extra_meta={"maj_source": maj, "jeu_odisse": ind["dataset"]})
    return dest


def charger(hors_ligne=False, rafraichir=False, ref=None):
    """Renvoie {"contexte": {niveau: DataFrame}, "defs": [...], "table": DataFrame} ou None. Avec le référentiel, seuls
    les codes de vrais territoires sont gardés (certains jeux ajoutent des lignes d'ensemble, codes 10 et 99)."""
    ctx, defs, lignes = {}, [], []
    connus = {"dep": set(ref.deps["code"]), "reg": set(ref.regs["code"])} if ref is not None else {}
    for ind in config.ODISSE:
        try:
            chemin = _telecharger(ind, hors_ligne, rafraichir)
            df = pd.read_csv(chemin, sep=";", dtype=str)
            df["_annee"] = df["annee"].str[:4]
            df["_v"] = pd.to_numeric(df[ind["valeur"]].str.replace(",", "."), errors="coerce")
            df = df[df["_v"].notna()]
            annee = df["_annee"].max()
            d = df[df["_annee"] == annee].copy()
            if ind.get("code_par_nom"):
                if ref is None:
                    raise ValueError("référentiel nécessaire pour lire les régions par leur nom")
                codes, inconnus = codes_regions_par_nom(d[ind["code"]], ref)
                JOURNAL.controle(f"Santé publique France, {ind['libelle'].lower()}, régions lues par leur nom",
                                 f"{int(codes.notna().sum())} régions reconnues"
                                 + (f", noms non reconnus {inconnus}" if inconnus else ", aucun nom inconnu"))
                if inconnus:
                    raise ValueError(f"régions non reconnues {inconnus}")
                d = d[codes.notna()].assign(_code=codes[codes.notna()])
            else:
                d["_code"] = _code(d[ind["code"]], ind["niveau"])
            d = d.drop_duplicates("_code")
            if ind["niveau"] in connus:
                d = d[d["_code"].isin(connus[ind["niveau"]])]
            ctx.setdefault(ind["niveau"], {})[ind["id"]] = d.set_index("_code")["_v"]
            t = pd.DataFrame({"niveau": ind["niveau"], "code": d["_code"], "indicateur": ind["id"], "annee": annee,
                              "valeur": d["_v"]})
            for k in ("ic_bas", "ic_haut"):
                t[k] = pd.to_numeric(d[ind[k]].str.replace(",", "."), errors="coerce") if ind.get(k) else float("nan")
            lignes.append(t)
            meta = lire_meta(chemin)
            defs.append({"id": ind["id"], "libelle": ind["libelle"], "unite": ind["unite"],
                         "explication": ind["explication"] + f" Année {annee}.", "source": ind["source"],
                         "famille": config.SANTE_MENTALE, "licence": "Licence Ouverte 2.0", "groupe": ind.get("groupe"),
                         "niveau_origine": ind["niveau"], "annee": annee})
            JOURNAL.note(f"Santé publique France, {ind['libelle'].lower()}", "ok",
                         f"année {annee}, {len(d)} territoires ({'départements' if ind['niveau'] == 'dep' else 'régions'})",
                         url=meta.get("url", "")[:200], date_donnees=(meta.get("maj_source") or "")[:10], lignes=len(df))
        except Exception as e:  # noqa: BLE001
            JOURNAL.note(f"Santé publique France, {ind['id']}", "erreur", str(e)[:300])
    if not defs:
        return None
    return {"contexte": {niv: pd.DataFrame(v) for niv, v in ctx.items()}, "defs": defs,
            "table": pd.concat(lignes, ignore_index=True)}
