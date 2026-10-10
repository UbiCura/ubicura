"""INSEE, temps d'accès par la route aux équipements (Licence Ouverte).

Pour chaque carreau habité de 200 m, l'INSEE publie la durée du trajet en voiture vers l'équipement le plus
proche de chaque type de la base permanente des équipements (BPE). Les fichiers sont volumineux (16 Go par
millésime). Chaque fichier régional est téléchargé, résumé par commune et par type d'équipement, puis supprimé.
Seul ce résumé est conservé en cache, avec la date de mise à jour de chaque fichier régional, pour que la future
tâche planifiée ne retélécharge que ce qui a changé. La lecture par requêtes partielles a été essayée, elle est
plus lente (les fichiers sont découpés en très nombreux petits blocs et la latence l'emporte).

Les professionnels de la BPE sont ceux qui exercent à titre libéral. Les durées sont celles d'un trajet en
voiture aux heures creuses, sans tenir compte des transports en commun."""
from __future__ import annotations

import json
import re
from datetime import datetime

import numpy as np
import pandas as pd

from .. import config
from ..util import JOURNAL, date_version, log, meta_path, ressources_datagouv, telecharger

SOURCE = ("INSEE, données sur la localisation et l'accès de la population aux équipements (base permanente des "
          "équipements, distancier Metric-OSRM, © les contributeurs d'OpenStreetMap et du projet OSRM)")
DOSSIER = config.BRUT / "acces_route"
MINUTES_MAX = 180   # au-delà, les durées sont regroupées dans la dernière tranche de l'histogramme
# version 2 (5 octobre 2026), l'histogramme des durées est gardé par commune et non plus par département, pour
# calculer la médiane à tous les niveaux, intercommunalités comprises (lacune relevée par Lucas)
VERSION_RESUME = 2


def _fichiers():
    """Fichiers régionaux du millésime complet le plus récent, d'après l'API data.gouv."""
    par_annee = {}
    for r in ressources_datagouv(config.ACCES_ROUTE_DATAGOUV):
        # le titre fait foi (un nom de fichier de 2024 porte par erreur l'année 2023)
        m = re.search(config.ACCES_ROUTE_MOTIF, r["titre"].strip().lower()) or \
            re.search(config.ACCES_ROUTE_MOTIF, r["url_directe"].rsplit("/", 1)[-1].replace("-", "_"))
        if m:
            par_annee.setdefault(m.group(1), {})[m.group(2)] = r
    if not par_annee:
        raise IOError("aucun fichier régional trouvé dans le jeu de l'INSEE")
    n_max = max(len(v) for v in par_annee.values())
    # un millésime en cours de publication (moins de régions que le précédent) n'est pas retenu
    annee = max(a for a, v in par_annee.items() if len(v) >= n_max)
    return annee, par_annee[annee]


def _resumer_region(chemin, codes, anciens):
    """Lit les colonnes utiles d'un fichier régional et renvoie deux tables, le résumé par commune et
    l'histogramme des durées par commune (minutes entières), toutes deux pondérées par la population."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(chemin)
    cols = ["typeeq_id", "duree", "pop", "depcom"]
    morceaux, histos = [], []
    groupes = list(range(pf.metadata.num_row_groups))
    for i in range(0, len(groupes), 64):
        t = pf.read_row_groups(groupes[i:i + 64], columns=cols)
        t = t.filter(pc.is_in(t["typeeq_id"], value_set=pa.array(codes)))
        d = t.to_pandas()
        if d.empty:
            continue
        d["depcom"] = d["depcom"].astype(str)
        d["depcom"] = d["depcom"].map(anciens).fillna(d["depcom"])
        d["pop"] = d["pop"].astype(float)
        ok = d["duree"].notna()
        d["pd"] = np.where(ok, d["pop"] * d["duree"].fillna(0), 0.0)
        d["pop_calcule"] = np.where(ok, d["pop"], 0.0)
        agg = {"pop": ("pop", "sum"), "pop_calcule": ("pop_calcule", "sum"), "pd": ("pd", "sum")}
        for s in config.ACCES_ROUTE_SEUILS:
            d[f"sup_{s}"] = np.where(ok & (d["duree"] > s), d["pop"], 0.0)
            agg[f"sup_{s}"] = (f"sup_{s}", "sum")
        morceaux.append(d.groupby(["depcom", "typeeq_id"], observed=True).agg(**agg).reset_index())
        h = d[ok].assign(minute=np.minimum(np.floor(d.loc[ok, "duree"]), MINUTES_MAX).astype(int))
        histos.append(h.groupby(["depcom", "typeeq_id", "minute"], observed=True)["pop"].sum().reset_index())
    com = pd.concat(morceaux).groupby(["depcom", "typeeq_id"], as_index=False).sum()
    his = pd.concat(histos).groupby(["depcom", "typeeq_id", "minute"], as_index=False).sum()
    return com, his


def charger(ref, hors_ligne=False, rafraichir=False):
    """Renvoie {"communes": DataFrame, "histogramme": DataFrame, "annee": str, "defs": [...]} ou None."""
    codes = [c for c, *_ in config.ACCES_ROUTE]
    DOSSIER.mkdir(parents=True, exist_ok=True)
    try:
        if hors_ligne:
            metas = sorted(DOSSIER.glob("acces_*_reg*.meta.json"))
            if not metas:
                raise FileNotFoundError("aucun résumé en cache")
            annee = max(json.loads(m.read_text(encoding="utf-8"))["annee"] for m in metas)
            fichiers = {json.loads(m.read_text(encoding="utf-8"))["region"]: None for m in metas
                        if json.loads(m.read_text(encoding="utf-8"))["annee"] == annee}
        else:
            annee, fichiers = _fichiers()
        coms, hiss, maj = [], [], []
        for reg, res in sorted(fichiers.items()):
            base = DOSSIER / f"acces_{annee}_reg{reg}"
            fc, fh, fm = base.with_suffix(".csv"), base.with_name(base.name + "_histo_communes.parquet"), \
                base.with_name(base.name + ".meta.json")
            meta = json.loads(fm.read_text(encoding="utf-8")) if fm.exists() else {}
            a_jour = (fc.exists() and fh.exists() and meta.get("codes") == codes
                      and meta.get("version") == VERSION_RESUME
                      and (res is None or meta.get("maj_source") == res["maj"]))
            if not a_jour or (rafraichir and res is not None):
                if res is None:
                    raise FileNotFoundError(f"résumé absent pour la région {reg}")
                log.info("INSEE, temps d'accès, région %s (%s)", reg, annee)
                tmp = DOSSIER / f"tmp_reg{reg}.parquet"
                telecharger(res["url_directe"], tmp, "acces_route", rafraichir=True)
                try:
                    com, his = _resumer_region(tmp, codes, ref.anciens)
                finally:
                    tmp.unlink(missing_ok=True)
                    meta_path(tmp).unlink(missing_ok=True)
                com.to_csv(fc, index=False)
                his.to_parquet(fh, index=False)
                base.with_name(base.name + "_histo.csv").unlink(missing_ok=True)   # ancien histogramme départemental
                meta = {"url": res["url_directe"], "maj_source": res["maj"], "annee": annee, "region": reg,
                        "codes": codes, "jeu_datagouv": config.ACCES_ROUTE_DATAGOUV, "version": VERSION_RESUME,
                        "telecharge_le": datetime.now().isoformat(timespec="seconds")}
                fm.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            coms.append(pd.read_csv(fc, dtype={"depcom": str}))
            hiss.append(pd.read_parquet(fh).astype({"depcom": str}))
            maj.append(meta.get("maj_source", ""))
    except Exception as e:  # noqa: BLE001
        JOURNAL.note("INSEE, temps d'accès par la route", "erreur", str(e)[:300])
        return None

    com = pd.concat(coms, ignore_index=True)
    his = pd.concat(hiss, ignore_index=True)
    connues = set(ref.communes["code"])
    p_ok = com.loc[com["depcom"].isin(connues), "pop"].sum() / com["pop"].sum()
    JOURNAL.controle("Temps d'accès INSEE, population des carreaux rattachée à une commune du référentiel", f"{p_ok:.1%}")
    regions = sorted(fichiers)
    nom_reg = ref.regs.set_index("code")["nom"]
    JOURNAL.controle("Temps d'accès INSEE, régions couvertes", ", ".join(nom_reg.get(r, r) for r in regions))
    JOURNAL.note("INSEE, temps d'accès par la route", "ok",
                 f"millésime {annee}, {len(regions)} régions, {len(com['depcom'].unique())} communes",
                 url=f"https://www.data.gouv.fr/datasets/{config.ACCES_ROUTE_DATAGOUV}/", lignes=len(com),
                 date_donnees=date_version({"maj_source": max(maj) if maj else ""}))
    defs = [{"code": c, "id": i, "libelle": lab, "famille": fam, "prof": prof}
            for c, i, lab, fam, prof in config.ACCES_ROUTE]
    return {"communes": com, "histogramme": his, "annee": annee, "defs": defs, "regions": regions,
            "maj_source": max(maj) if maj else ""}
