"""INSEE, base du dossier complet (recensement, Filosofi...). Une seule base couvre
communes et intercommunalités. Les effectifs sont agrégés depuis les communes, les médianes
de revenu et taux de pauvreté sont repris tels quels quand l'INSEE les publie au niveau voulu,
sinon approchés par une moyenne pondérée par la population (signalé dans le rapport)."""
from __future__ import annotations

import io
import re
import zipfile

import numpy as np
import pandas as pd

from .. import config
from ..util import JOURNAL, date_version, get_texte, lire_meta, log, telecharger

NON_ADDITIFS = {"med", "tp60", "salaire", "minima_sociaux"}


def _telecharger(hors_ligne, rafraichir):
    def cache():
        for ext in ("parquet", "zip"):
            p = config.BRUT / f"insee_dossier_complet.{ext}"
            if p.exists():
                try:
                    return telecharger("", p, "insee", False, hors_ligne=True)
                except Exception:  # noqa: BLE001
                    pass
        return None
    if hors_ligne:
        c = cache()
        if c is None:
            raise FileNotFoundError("dossier complet INSEE absent")
        return c
    # en ligne, la date de parution de la page décide (même date, le fichier en cache est gardé)
    try:
        page = get_texte(config.INSEE_PAGE_DOSSIER)
    except Exception as e:  # noqa: BLE001
        c = cache()
        if c is None:
            raise
        log.warning("page du dossier complet de l'INSEE injoignable (%s), fichier en cache conservé", e)
        return c
    liens = sorted(set(re.findall(r'href="([^"]*?/statistiques/fichier/5359146/[^"]+)"', page)))
    liens = ["https://www.insee.fr" + l if l.startswith("/") else l for l in liens]
    log.info("Liens trouvés sur la page INSEE : %s", liens)
    # parquet d'abord, puis le zip CSV non daté (version courante), puis les zip datés du plus récent au plus ancien
    zips = [l for l in liens if l.lower().endswith(".zip") and "meta" not in l.lower()]
    zips = [l for l in zips if not re.search(r"\d{4}\.zip$", l)] + sorted(
        [l for l in zips if re.search(r"\d{4}\.zip$", l)], reverse=True)
    choix = [l for l in liens if l.lower().endswith(".parquet")] + zips
    if not choix:
        raise RuntimeError("aucun fichier parquet ou zip trouvé sur la page INSEE du dossier complet")
    # date de parution affichée sur la page du dossier complet (« Paru le JJ/MM/AAAA »), seule date côté producteur
    m = re.search(r"Paru le.{0,400}?(\d{2})/(\d{2})/(\d{4})", page, re.S)
    maj = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""
    erreurs = []
    for url in choix:
        ext = "parquet" if url.lower().endswith(".parquet") else "zip"
        try:
            return telecharger(url, config.BRUT / f"insee_dossier_complet.{ext}", "insee", rafraichir,
                               taille_min=10_000_000, extra_meta={"maj_source": maj, "page": config.INSEE_PAGE_DOSSIER})
        except Exception as e:  # noqa: BLE001
            log.warning("dossier complet INSEE, échec avec %s : %s", url, e)
            erreurs.append(f"{url.rsplit('/', 1)[-1]} ({e})")
    raise RuntimeError("aucun fichier du dossier complet n'a pu être téléchargé : " + " ; ".join(erreurs))


def _format_long(chemin) -> bool:
    if chemin.suffix != ".parquet":
        return False
    import pyarrow.parquet as pq
    return "TAB_MEASURE" in pq.read_schema(chemin).names


def _lire_long(chemin):
    """Format long (2026). Renvoie un tableau large (code + une colonne par variable) et les années."""
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    d = ds.dataset(chemin)
    tabs = sorted({t for t, _m in config.INSEE_MESURES.values()})
    # 1. repérage des codes de mesure et des années sur les seules intercommunalités (peu de lignes)
    rep = d.to_table(columns=["ID_TAB", "TAB_MEASURE", "TIME_PERIOD"],
                     filter=(pc.field("GEO_OBJECT") == "EPCI") & pc.field("ID_TAB").isin(tabs)).to_pandas()
    rep = rep.drop_duplicates()
    choix = {}
    for cle, (tab, motif) in config.INSEE_MESURES.items():
        r = rep[(rep["ID_TAB"] == tab) & rep["TAB_MEASURE"].str.match(motif)]
        if len(r):
            an = r["TIME_PERIOD"].max()
            choix[cle] = (tab, sorted(r.loc[r["TIME_PERIOD"] == an, "TAB_MEASURE"]), an)
    if "pop" not in choix:
        raise RuntimeError("mesure de population introuvable dans le dossier complet (format long)")
    # 2. lecture ciblée, communes et intercommunalités
    mesures = sorted({m for _t, ms, _a in choix.values() for m in ms})
    t = d.to_table(columns=["GEO_OBJECT", "GEO", "TIME_PERIOD", "ID_TAB", "TAB_MEASURE", "OBS_VALUE"],
                   filter=pc.field("GEO_OBJECT").isin(["COM", "EPCI", "DEP", "REG"]) & pc.field("ID_TAB").isin(tabs)
                   & pc.field("TAB_MEASURE").isin(mesures)).to_pandas()
    t = t.drop_duplicates(["GEO_OBJECT", "GEO", "ID_TAB", "TAB_MEASURE", "TIME_PERIOD"])
    colonnes = {}
    for cle, (tab, ms, an) in choix.items():
        s = t[(t["ID_TAB"] == tab) & t["TAB_MEASURE"].isin(ms) & (t["TIME_PERIOD"] == an)]
        colonnes[cle] = s.groupby(["GEO_OBJECT", "GEO"])["OBS_VALUE"].sum(min_count=1)
    df = pd.DataFrame(colonnes)
    df.index.names = ["objet", "code"]
    millesimes = {k: int(a) for k, (_t, _m, a) in choix.items()}
    return df.reset_index(), choix, millesimes


def _colonnes(chemin):
    if chemin.suffix == ".parquet":
        import pyarrow.parquet as pq
        return pq.read_schema(chemin).names, None
    z = zipfile.ZipFile(chemin)
    nom = max([n for n in z.namelist() if n.lower().endswith(".csv") and "meta" not in n.lower()],
              key=lambda n: z.getinfo(n).file_size)
    with z.open(nom) as f:
        entete = io.TextIOWrapper(f, encoding="utf-8-sig").readline().strip()
    return entete.split(";"), nom


def _lire(chemin, colonnes, nom_csv):
    if chemin.suffix == ".parquet":
        return pd.read_parquet(chemin, columns=colonnes)
    with zipfile.ZipFile(chemin).open(nom_csv) as f:
        return pd.read_csv(f, sep=";", usecols=colonnes, dtype={colonnes[0]: str}, encoding="utf-8-sig",
                           low_memory=False)


def _choisir_variables(colonnes):
    """Pour chaque variable, colonne du millésime le plus récent."""
    choix, millesimes = {}, {}
    for cle, motif in config.INSEE_VARIABLES.items():
        cands = []
        for c in colonnes:
            m = re.match(motif, c)
            if m:
                cands.append((int(m.group(1)) if m.groups() else 0, c))
        if cands:
            an, col = max(cands)
            choix[cle], millesimes[cle] = col, (2000 + an if an else None)
    return choix, millesimes


def charger(ref, hors_ligne=False, rafraichir=False) -> dict | None:
    try:
        chemin = _telecharger(hors_ligne, rafraichir)
        if _format_long(chemin):
            df, choix, millesimes = _lire_long(chemin)
            manquantes = sorted(set(config.INSEE_MESURES) - set(choix))
            format_lu = "format long"
        else:
            cols, nom_csv = _colonnes(chemin)
            c_geo = next((c for c in cols if c.upper() in ("CODGEO", "CODE_GEO", "GEO")), cols[0])
            c_niv = next((c for c in cols if re.match(r"(?i)^niv", c)), None)
            choix, millesimes = _choisir_variables(cols)
            if "pop" not in choix:
                raise RuntimeError("variable de population introuvable dans le dossier complet")
            manquantes = sorted(set(config.INSEE_VARIABLES) - set(choix))
            lues = [c_geo] + ([c_niv] if c_niv else []) + list(choix.values())
            df = _lire(chemin, lues, nom_csv)
            df = df.rename(columns={v: k for k, v in choix.items()} | {c_geo: "code"})
            format_lu = "format large"
        df["code"] = df["code"].astype(str).str.replace(r"^[A-Za-z]{2,6}[-_]", "", regex=True).str.strip()
        if "objet" not in df:
            # format large, seules les communes et les EPCI sont distinguables par la longueur du code
            df["objet"] = np.select([df["code"].str.len() == 5, df["code"].str.fullmatch(r"\d{9}")],
                                    ["COM", "EPCI"], "")
        for k in choix:
            df[k] = pd.to_numeric(df[k], errors="coerce")
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("INSEE dossier complet", "erreur", str(e)[:300])
        return None

    meta = lire_meta(chemin)
    actuels = set(ref.communes["code"])
    # lignes communales, sans double compte des arrondissements municipaux
    com = df[df["objet"] == "COM"].copy()
    presents = set(com["code"])
    com["code_actuel"] = com["code"].where(com["code"].isin(actuels), com["code"].map(ref.anciens))
    com = com[com["code"].isin(actuels) | (~com["code_actuel"].isin(presents) & com["code_actuel"].notna())]
    additifs = [k for k in choix if k not in NON_ADDITIFS]
    com_g = com.groupby("code_actuel")[additifs].sum(min_count=1)
    for k in NON_ADDITIFS & set(choix):
        # valeur de la commune principale (la plus peuplée) en cas de fusion
        com_g[k] = com.sort_values("pop", ascending=False).drop_duplicates("code_actuel").set_index("code_actuel")[k]
    rattach = ref.communes.set_index("code")[["epci", "dep", "reg"]]
    com_g = com_g.join(rattach, how="inner")

    # valeurs publiées par l'INSEE au niveau voulu, préférées aux moyennes de communes
    officiels = {niv: df[df["objet"] == obj].set_index("code") for niv, obj in
                 [("epci", "EPCI"), ("dep", "DEP"), ("reg", "REG")]}
    niveaux, approx = {"com": com_g.drop(columns=["epci", "dep", "reg"])}, []
    for niv in ["epci", "dep", "reg"]:
        g = com_g.groupby(niv)[additifs].sum(min_count=1)
        for k in NON_ADDITIFS & set(choix):
            pond = com_g.dropna(subset=[k])
            moy = (pond[k] * pond["pop"]).groupby(pond[niv]).sum() / pond["pop"].groupby(pond[niv]).sum()
            g[k] = moy
            off = officiels[niv][k].dropna() if k in officiels[niv] else pd.Series(dtype=float)
            off = off[off.index.isin(g.index)]
            if off.empty:
                approx.append((k, niv, len(g)))
            else:
                g.loc[off.index, k] = off
                if (~g.index.isin(off.index)).any():
                    approx.append((k, niv, int((~g.index.isin(off.index)).sum())))
        niveaux[niv] = g

    ctx = {}
    for niv, t in niveaux.items():
        out = pd.DataFrame(index=t.index)
        for cid, _lab, unite, num, den in config.CONTEXTE + config.CONTEXTE_VULNERABILITE:
            if num not in t:
                continue
            if den is None:
                out[cid] = t[num]
            elif den in t:
                v = t[num] / t[den].replace(0, np.nan)
                out[cid] = v * 100 if unite == "%" else v
        ctx[niv] = out
    JOURNAL.controle("Population INSEE des communes appariées",
                     f"{com_g['pop'].sum():,.0f} habitants".replace(",", " "))
    # Les densités utilisent la population du référentiel (Etalab), les indicateurs celle de l'INSEE. Les deux
    # doivent être la même population municipale, sinon le millésime du référentiel a changé sans l'INSEE.
    p_ref = ref.communes.groupby("dep")["pop"].sum()
    p_ins = com_g.groupby("dep")["pop"].sum().reindex(p_ref.index).replace(0, np.nan)
    nom_dep = ref.deps.set_index("code")["nom"]
    ecart = ((p_ref - p_ins).abs() / p_ins).dropna()
    sans = sorted(set(p_ref.index) - set(ecart.index))   # Mayotte, pas de recensement publié
    JOURNAL.controle("Population du référentiel et population municipale INSEE (" + str(millesimes.get("pop", "")) + ")",
                     f"{(ecart < 1e-3).sum()} départements identiques à 0,1 % près sur {len(ecart)}, "
                     f"écart maximal {ecart.max() * 100:.2f} %".replace(".", ",") + (f" ({nom_dep.get(ecart.idxmax(), ecart.idxmax())})" if len(ecart) else "")
                     + (f", sans population de l'INSEE pour {', '.join(nom_dep.get(c, c) for c in sans)}" if sans else ""))
    JOURNAL.note("INSEE dossier complet", "ok",
                 f"{format_lu}, {len(com_g)} communes appariées, " + (f"variables absentes, {', '.join(manquantes)}" if manquantes else "toutes les variables présentes"),
                 url=meta.get("url", ""), date_donnees=date_version(meta), lignes=len(df))
    from collections import Counter
    annees = Counter(str(v) for v in millesimes.values() if v)
    JOURNAL.controle("Millésimes de l'INSEE retenus", ", ".join(f"{a} pour {n} indicateur{'s' if n > 1 else ''}"
                                                               for a, n in sorted(annees.items())))
    if approx:
        noms = {"med": "niveau de vie médian", "tp60": "taux de pauvreté", "minima_sociaux": "part des minima sociaux",
                "salaire": "salaire moyen"}
        niveaux_fr = {"dep": "départements", "epci": "intercommunalités", "reg": "régions"}
        par_k = {}
        for k, niv, n in approx:
            par_k.setdefault(k, []).append(f"{n} {niveaux_fr.get(niv, niv)}")
        JOURNAL.controle("Valeurs officielles manquantes remplacées par la moyenne des communes pondérée par la population",
                         ", ".join(f"{noms.get(k, k)} ({', '.join(v)})" for k, v in par_k.items()))
    return {"contexte": ctx, "millesimes": millesimes}
