"""RPPS, extraction en libre accès de l'Annuaire Santé (Agence du numérique en santé).
Trois fichiers, l'activité (une ligne par situation d'exercice), les savoir-faire, les diplômes."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd

from .. import config
from ..util import (JOURNAL, entier_fr, choisir_ressource, date_version, detecter_separateur, lire_meta, log, norm,
                    premiere_ligne, ressources_datagouv, telecharger, trouver_colonne)

FICHIERS = {k: config.BRUT / f"rpps_{k}.txt" for k in config.RPPS_RESSOURCES}


def telecharger_tout(hors_ligne=False, rafraichir=False) -> dict[str, Path]:
    if hors_ligne:
        manquants = [str(p) for p in FICHIERS.values() if not p.exists()]
        if manquants:
            raise FileNotFoundError("Fichiers RPPS absents : " + ", ".join(manquants))
        return dict(FICHIERS)
    res = ressources_datagouv(config.RPPS_DATASET)
    choisis = {k: choisir_ressource(res, m) for k, m in config.RPPS_RESSOURCES.items()}
    if not all(choisis.values()):
        # Repli : les titres ne permettent pas d'identifier les fichiers, on se fie aux tailles.
        txt = sorted([r for r in res if r["format"] in ("txt", "csv", "")], key=lambda r: -(r["taille"] or 0))
        if len(txt) < 3:
            raise RuntimeError("Jeu RPPS sur data.gouv : moins de trois fichiers trouvés, structure inattendue.")
        log.warning("Ressources RPPS identifiées par taille (titres non reconnus).")
        choisis = {"activite": txt[0], "diplomes": txt[1], "savoirfaire": txt[2]}
    for k, r in choisis.items():
        telecharger(r["url"], FICHIERS[k], "rpps", rafraichir, taille_min=10_000_000 if k == "activite" else 100_000,
                    extra_meta={"titre": r["titre"], "maj_source": r["maj"]})
    return dict(FICHIERS)


def _lecteur(chemin: Path, colonnes: list[str], sep: str, taille=400_000):
    return pd.read_csv(chemin, sep=sep, dtype=str, usecols=colonnes, quoting=csv.QUOTE_NONE,
                       encoding="utf-8-sig", encoding_errors="replace", keep_default_na=False,
                       chunksize=taille, on_bad_lines="warn", engine="c", index_col=False)


def _entete(chemin: Path):
    ligne = premiere_ligne(chemin)
    sep = detecter_separateur(ligne)
    cols = [c for c in ligne.split(sep)]
    return sep, cols


def _mode(serie: pd.Series) -> pd.Series:
    n = serie.map(norm)
    return n.map(lambda s: "lib" if s.startswith("lib") else ("sal" if s.startswith("sal") else "aut"))


# ---------------------------------------------------------------- classement des professions
def classer_profession(libelle: str):
    n = norm(libelle)
    for motif, pid, lab, grp, fam in config.PROFESSIONS:
        if re.search(motif, n):
            return pid, lab, grp, fam
    if re.search(r"\bmedecin\b", n):
        return None  # traité via les savoir-faire
    lab = (libelle or "Profession non renseignée").strip() or "Profession non renseignée"
    return (norm(lab).replace(" ", "_") or "inconnue", lab) + config.GROUPE_AUTRES


def classer_medecin(savoirs: str):
    n = norm(savoirs)
    if not n:
        return config.MEDECIN_INCONNU
    for motif, pid, lab, grp, fam in config.SPECIALITES_MEDECINS:
        if re.search(motif, n):
            return pid, lab, grp, fam
    return config.MEDECIN_AUTRE


def qualifications_medecin(savoirs: str) -> list[str]:
    """Identifiants des qualifications complémentaires repérées dans l'ensemble des savoir-faire."""
    n = norm(savoirs)
    return [qid for motif, qid, _lab, _fam in config.QUALIFICATIONS_MEDECINS if re.search(motif, n)]


def specialites_medecins(chemin: Path | None, ids: set) -> tuple[dict, dict]:
    """Deux dictionnaires identifiant -> libellés concaténés, l'un pour la spécialité ordinale,
    l'autre pour tous les savoir-faire (qualifications complémentaires)."""
    if chemin is None or not chemin.exists():
        return {}, {}
    sep, cols = _entete(chemin)
    c_id = trouver_colonne(cols, [r"^identification nationale pp$", r"^identifiant pp$"], nom="identifiant")
    c_type = trouver_colonne(cols, [r"^libelle type savoir faire$", r"^code type savoir faire$"], False)
    c_lib = trouver_colonne(cols, [r"^libelle savoir faire$"], nom="libellé savoir-faire")
    usecols = [c for c in [c_id, c_type, c_lib] if c]
    morceaux, tous = [], []
    for ch in _lecteur(chemin, usecols, sep):
        ch = ch[ch[c_id].isin(ids)]
        tous.append(ch[[c_id, c_lib]])
        if c_type:
            t = ch[c_type].map(norm)
            # La spécialité est la spécialité ordinale (S). À défaut, la compétence exclusive (CEX, environ
            # 750 gynécologues médicaux sans spécialité ordinale) puis la qualification PAC, comme le fait la
            # DREES (vérifié le 5 octobre 2026). Les autres types servent aux qualifications complémentaires.
            rang = pd.Series(9, index=ch.index)
            rang[t.str.contains("qualification pac") | (t == "pac")] = 2
            rang[t.str.contains("competence exclusive") | (t == "cex")] = 1
            rang[t.str.contains("specialite ordinale") | (t == "s")] = 0
            ch = ch.assign(_rang=rang)[rang < 9]
            ch = ch[ch["_rang"] == ch.groupby(c_id)["_rang"].transform("min")]
        else:
            ch = ch.assign(_rang=0)
        morceaux.append(ch[[c_id, c_lib, "_rang"]])
    if not morceaux:
        return {}, {}

    def joindre(parts, par_rang=False):
        sf = pd.concat(parts)
        if par_rang:   # un même médecin peut figurer dans deux morceaux du fichier
            sf = sf[sf["_rang"] == sf.groupby(c_id)["_rang"].transform("min")]
        return sf.groupby(c_id)[c_lib].agg(lambda s: " ; ".join(sorted(set(s)))).to_dict()
    return joindre(morceaux, par_rang=True), joindre(tous)


# ---------------------------------------------------------------- activités
def _inscrits(ins, act):
    """Par libellé de profession du RPPS, personnes inscrites (hors étudiants) et personnes ayant au moins une
    activité déclarée. Le fichier ne dit rien des inscrits sans activité (ni lieu, ni âge, ni date), on ne peut donc
    pas dire qu'ils n'exercent pas (retraite, autre métier, congé ou activité non déclarée). Demande de Lucas du
    5 octobre 2026, publié comme tableau de contrôle."""
    exclus = ins["prof_lib"].map(norm).str.contains("|".join(config.PROFESSIONS_EXCLUES))         if config.PROFESSIONS_EXCLUES else pd.Series(False, index=ins.index)
    ins = ins[~exclus & (ins["prof_lib"] != "")]
    t = pd.DataFrame({"inscrits": ins.groupby("prof_lib")["id"].nunique(),
                      "avec_activite": act.groupby("prof_lib")["id"].nunique()}).fillna(0).astype(int)
    t = t[t["inscrits"] > 0]
    t["sans_activite_declaree"] = t["inscrits"] - t["avec_activite"]
    t["part_sans_activite_declaree"] = t["sans_activite_declaree"] / t["inscrits"]
    t = t.rename_axis("libelle_rpps").reset_index().sort_values("inscrits", ascending=False)
    psy = t[t["libelle_rpps"].map(norm) == "psychologue"]
    if len(psy):
        JOURNAL.controle("Psychologues inscrits au RPPS sans activité déclarée",
                         f"{int(psy['sans_activite_declaree'].iloc[0])} sur {int(psy['inscrits'].iloc[0])} inscrits")
    return t


def lire_activites(fichiers: dict, ref) -> tuple[pd.DataFrame, pd.DataFrame]:
    chemin = fichiers["activite"]
    sep, cols = _entete(chemin)
    C = {
        "id": trouver_colonne(cols, [r"^identification nationale pp$", r"^identifiant pp$"], nom="identifiant"),
        "prof": trouver_colonne(cols, [r"^libelle profession$"], nom="libellé profession"),
        "cat": trouver_colonne(cols, [r"^libelle categorie professionnelle$"], False),
        "mode": trouver_colonne(cols, [r"^libelle mode (d )?exercice$"], nom="mode d'exercice"),
        "secteur": trouver_colonne(cols, [r"^libelle secteur d ?activite$"], False),
        "finess": trouver_colonne(cols, [r"^numero finess site$"], False),
        "com": trouver_colonne(cols, [r"^code commune coord structure$"], nom="code commune"),
        "cp": trouver_colonne(cols, [r"^code postal coord structure$"], False),
        "rs": trouver_colonne(cols, [r"^raison sociale site$"], False),
        "sf": trouver_colonne(cols, [r"^libelle savoir faire$"], False),
        "struct": trouver_colonne(cols, [r"^identifiant technique de la structure$"], False),
        "civ": trouver_colonne(cols, [r"^code civilite$"], False),
    }
    log.info("RPPS activité, colonnes retenues : %s", {k: v for k, v in C.items() if v})
    usecols = sorted({v for v in C.values() if v})
    morceaux, inscrits, n_lu, n_etud, n_sans = [], [], 0, 0, 0
    for ch in _lecteur(chemin, usecols, sep):
        n_lu += len(ch)
        if C["cat"]:
            etud = ch[C["cat"]].map(norm).str.contains("etudiant")
            n_etud += int(etud.sum())
            ch = ch[~etud]
        # tous les inscrits (hors étudiants), pour le tableau des inscrits sans activité déclarée
        inscrits.append(pd.DataFrame({"id": ch[C["id"]].str.strip(), "prof_lib": ch[C["prof"]].str.strip()})
                        .drop_duplicates())
        # Lignes d'inscrits sans aucune situation d'exercice (ni structure, ni mode d'exercice).
        # Ce ne sont pas des activités, elles sont écartées.
        vide = ch[C["mode"]].str.strip() == ""
        vide &= (ch[C["struct"]].str.strip() == "") if C["struct"] else (ch[C["com"]].str.strip() == "")
        n_sans += int(vide.sum())
        ch = ch[~vide]
        out = pd.DataFrame({
            "id": ch[C["id"]].str.strip(),
            "prof_lib": ch[C["prof"]].str.strip(),
            "mode": _mode(ch[C["mode"]]),
            "secteur": ch[C["secteur"]].str.strip() if C["secteur"] else "",
            "finess": ch[C["finess"]].str.strip().str.zfill(9).where(ch[C["finess"]].str.strip() != "", "") if C["finess"] else "",
            "rs": ch[C["rs"]].str.strip() if C["rs"] else "",
            "sf_activite": ch[C["sf"]].str.strip() if C["sf"] else "",
            "avec_structure": (ch[C["struct"]].str.strip() != "") if C["struct"] else True,
            # civilité déclarée (Madame, Monsieur), seule approximation du sexe dans l'extraction publique
            "femme": ch[C["civ"]].map(norm).map({"mme": True, "mlle": True, "m": False}) if C["civ"] else None,
            "com": ref.resoudre(ch[C["com"]], ch[C["cp"]] if C["cp"] else pd.Series("", index=ch.index)),
        })
        morceaux.append(out)
        log.info("  RPPS : %s lignes lues", f"{n_lu:,}".replace(",", " "))
    act = pd.concat(morceaux, ignore_index=True)
    act.loc[act["secteur"] == "", "secteur"] = "Secteur non renseigné"

    exclus = act["prof_lib"].map(norm).str.contains("|".join(config.PROFESSIONS_EXCLUES)) \
        if config.PROFESSIONS_EXCLUES else pd.Series(False, index=act.index)
    if exclus.any():
        JOURNAL.controle("Lignes écartées car ne désignant pas une profession de soin",
                         f"{int(exclus.sum())} ({', '.join(sorted(act.loc[exclus, 'prof_lib'].unique()))})")
        act = act[~exclus].reset_index(drop=True)

    # classement des professions
    libs = act["prof_lib"].drop_duplicates()
    table = {lib: classer_profession(lib) for lib in libs}
    medecins_libs = [lib for lib, v in table.items() if v is None]
    est_med = act["prof_lib"].isin(medecins_libs)
    ids_med = set(act.loc[est_med, "id"])
    spec, savoirs = specialites_medecins(fichiers.get("savoirfaire"), ids_med)
    if not spec and est_med.any():
        log.warning("Aucune spécialité lue dans le fichier savoir-faire, repli sur la colonne du fichier activité.")
        spec = act[est_med].groupby("id")["sf_activite"].agg(lambda s: " ; ".join(sorted(set(s) - {""}))).to_dict()
        savoirs = spec
    cls_med = {i: classer_medecin(s) for i, s in spec.items()}
    pid = act["prof_lib"].map(lambda l: table[l][0] if table[l] else None)
    if est_med.any():
        pid[est_med] = act.loc[est_med, "id"].map(lambda i: cls_med.get(i, config.MEDECIN_INCONNU)[0])
    act["prof"] = pid
    vus = set(pid.dropna().unique())
    defs = [v for v in table.values() if v] + list(cls_med.values()) + [config.MEDECIN_INCONNU]
    professions = pd.DataFrame(defs, columns=["id", "libelle", "groupe", "famille"]).drop_duplicates("id")
    professions["nature"] = "profession"

    table_inscrits = _inscrits(pd.concat(inscrits).drop_duplicates(), act)

    meta = lire_meta(chemin)
    localisees = act["com"].notna().mean()
    JOURNAL.note("RPPS activité", "ok", f"{n_lu} lignes lues, {n_etud} lignes d'étudiants écartées, "
                 f"{n_sans} lignes d'inscrits sans situation d'exercice écartées, "
                 f"{act['id'].nunique()} professionnels distincts", url=meta.get("url", ""),
                 date_donnees=date_version(meta), lignes=n_lu)
    JOURNAL.controle("Inscrits sans aucune situation d'exercice, écartés", f"{n_sans} lignes")
    JOURNAL.controle("Part des activités localisées dans une commune", f"{localisees:.1%}")
    if C["struct"]:
        s = act["avec_structure"]
        JOURNAL.controle("Part des activités avec lieu d'exercice localisées", f"{act.loc[s, 'com'].notna().mean():.1%}")
        JOURNAL.controle("Activités déclarées sans lieu d'exercice (remplacements, exercice sans site fixe)",
                         f"{int((~s).sum())} lignes, {(~s).mean():.1%}")
    if C["secteur"]:
        JOURNAL.controle("Part des activités avec secteur renseigné",
                         f"{(act['secteur'] != 'Secteur non renseigné').mean():.1%}")
    if est_med.any():
        JOURNAL.controle("Part des médecins avec spécialité identifiée",
                         f"{(act.loc[est_med, 'prof'] != config.MEDECIN_INCONNU[0]).mean():.1%}")

    # Qualifications complémentaires. Les activités des médecins concernés sont dupliquées sous
    # l'identifiant de la qualification, qui se compte ensuite comme une profession à part.
    # Ces comptages ne s'additionnent jamais aux professions (nature = « qualification »).
    quals = {}
    for i, s in savoirs.items():
        for q in qualifications_medecin(s):
            quals.setdefault(q, set()).add(i)
    ajouts, qdefs = [], []
    for _motif, qid, lab, fam in config.QUALIFICATIONS_MEDECINS:
        ids_q = quals.get(qid, set())
        if ids_q:
            ajouts.append(act[est_med & act["id"].isin(ids_q)].assign(prof=qid))
            qdefs.append((qid, lab, config.GROUPE_QUALIFICATIONS, fam, "qualification"))
            vus.add(qid)
        JOURNAL.controle(f"Médecins comptés dans « {lab} »", entier_fr(len(ids_q)))
    # Repère « médecins spécialistes, ensemble » (version 2, 11 octobre 2026), chaque médecin spécialiste compté une
    # fois, hors généralistes et médecins sans spécialité renseignée, comme dans les séries de la DREES. Il réunit les
    # spécialités et ne s'y ajoute pas (nature « ensemble »).
    eid, elab, egrp, efam, enat = config.ENSEMBLE_SPECIALISTES
    specialistes = est_med & ~act["prof"].isin(["medecin_generaliste", config.MEDECIN_INCONNU[0]])
    if specialistes.any():
        ajouts.append(act[specialistes].assign(prof=eid))
        qdefs.append((eid, elab, egrp, efam, enat))
        vus.add(eid)
        JOURNAL.controle("Médecins spécialistes, ensemble (hors généralistes)",
                         entier_fr(act.loc[specialistes, "id"].nunique()))
    if qdefs:
        professions = pd.concat([professions, pd.DataFrame(
            qdefs, columns=["id", "libelle", "groupe", "famille", "nature"])], ignore_index=True)
        act = pd.concat([act] + ajouts, ignore_index=True)
    ordre_famille = {f: i for i, f in enumerate(config.FAMILLES)}
    professions = (professions[professions["id"].isin(vus)]
                   .assign(_o=lambda d: d["famille"].map(ordre_famille))
                   .sort_values(["_o", "nature", "groupe", "libelle"]).drop(columns="_o").reset_index(drop=True))
    act = act.drop(columns=["prof_lib", "sf_activite", "avec_structure"])
    for c in ["mode", "secteur", "prof", "com"]:
        act[c] = act[c].astype("category")
    professions.attrs["inscrits"] = table_inscrits
    return act, professions


def diplomes_psychologues(fichiers: dict, ids: set) -> pd.DataFrame | None:
    """Répartition des diplômes déclarés par les psychologues (libellé et année)."""
    chemin = fichiers.get("diplomes")
    if not chemin or not Path(chemin).exists():
        return None
    sep, cols = _entete(chemin)
    c_id = trouver_colonne(cols, [r"^identification nationale pp$", r"^identifiant pp$"], False)
    c_lib = trouver_colonne(cols, [r"^libelle diplome$", r"libelle.*diplome"], False)
    c_date = trouver_colonne(cols, [r"date.*(obtention|diplome)", r"^annee"], False)
    if not (c_id and c_lib):
        JOURNAL.note("RPPS diplômes", "ignoré", "colonnes identifiant ou libellé introuvables")
        return None
    usecols = [c for c in [c_id, c_lib, c_date] if c]
    morceaux = [ch[ch[c_id].isin(ids)] for ch in _lecteur(chemin, usecols, sep)]
    d = pd.concat(morceaux) if morceaux else pd.DataFrame(columns=usecols)
    d["annee"] = d[c_date].str.extract(r"((?:19|20)\d\d)")[0] if c_date else None
    out = d.groupby([c_lib, "annee"], dropna=False)[c_id].nunique().reset_index()
    out.columns = ["diplome", "annee", "psychologues"]
    JOURNAL.note("RPPS diplômes", "ok", f"{d[c_id].nunique()} psychologues avec au moins un diplôme renseigné",
                 url=lire_meta(chemin).get("url", ""), date_donnees=date_version(lire_meta(chemin)))
    return out.sort_values("psychologues", ascending=False)
