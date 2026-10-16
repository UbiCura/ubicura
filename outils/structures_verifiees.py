"""Outil de la liste vérifiée des structures de soins (voir pipeline/structures_verifiees.py).

    python outils\\structures_verifiees.py fiche 690780119      inscriptions de FINESS et du ROR d'un établissement,
                                                                à confronter à ses sources (nom ou numéro FINESS)
    python outils\\structures_verifiees.py valider               contrôle les deux fichiers, remplace les noms de
                                                                commune par leur code INSEE, géocode les adresses
                                                                nouvelles (service de l'IGN) et calcule l'empreinte
                                                                des établissements qui n'en ont pas
    python outils\\structures_verifiees.py etat                  avancement (établissements et structures vérifiés)
    python outils\\structures_verifiees.py a-verifier            écrit docs\\a_verifier_par_lucas.csv, tout ce qui
                                                                reste à trancher à la main, colonne verdict à remplir
    python outils\\structures_verifiees.py verdicts              range les verdicts remplis dans
                                                                contenus\\verdicts_verification.csv

Les inscriptions des bases viennent de donnees/intermediaire/structures_avant_verification.parquet, écrit à chaque
exécution de la chaîne.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config  # noqa: E402
from pipeline import structures_verifiees as sv  # noqa: E402

TYPES_PSY = ["lieu_cmp", "lieu_cattp", "lieu_hdj_psy_adultes", "lieu_hdj_psy_enfants", "lieu_cmpp", "lieu_camsp",
             "lieu_consult_psy", "lieu_mobile_psy", "lieu_crise_psy", "lieu_rehab_psy", "lieu_hc_psy_adultes",
             "lieu_hc_psy_enfants"]


def _bases() -> pd.DataFrame:
    if not sv.BASES.exists():
        sys.exit("Lancer d'abord la chaîne (python run.py --hors-ligne) pour écrire les inscriptions des bases.")
    return pd.read_parquet(sv.BASES)


def _ref():
    from pipeline.sources import referentiel
    return referentiel.charger(True)


def fiche(cle: str):
    b = _bases()
    ref = _ref()
    nc = ref.communes.set_index("code")["nom"]
    # « 630786754:06 » limite un établissement à plusieurs sites à un département
    cle, _, dep = cle.partition(":")
    if dep:
        b = b[b["commune"].map(ref.communes.set_index("code")["dep"]) == dep]
    g = b[(b["ej"] == cle) | b["nom"].fillna("").str.contains(cle, case=False) |
          b["nom_finess"].fillna("").str.contains(cle, case=False)] if not cle.isdigit() or len(cle) != 9 else \
        b[b["ej"] == cle]
    g = g[g["type"].isin(TYPES_PSY + [c for t in TYPES_PSY for c in sv.ENFANTS_DE.get(t, [])])]
    if g.empty:
        print("aucune inscription")
        return
    pub = g[g["type"].isin(["lieu_cmp_adultes", "lieu_cmp_enfants"])].groupby("lieu")["type"].apply(
        lambda s: "+".join(sorted(t.split("_")[-1] for t in s)))
    for ej, ge in g[~g["type"].isin(["lieu_cmp_adultes", "lieu_cmp_enfants"])].groupby("ej", dropna=False):
        print(f"\n=== entité juridique {ej}")
        for _, r in ge.sort_values(["type", "commune"]).iterrows():
            nom = r["nom"] if isinstance(r["nom"], str) else r["nom_finess"]
            p = pub.get(r["lieu"], "") if r["type"] == "lieu_cmp" else ""
            unites = f" | unités, {r['noms_unites']}" if isinstance(r.get("noms_unites"), str) and \
                r.get("unites_ror", 0) and r["unites_ror"] > 1 else ""
            print(f"{r['type'][5:]:16} {p:15} {nc.get(r['commune'], r['commune']):28} {str(nom)[:60]:60} | "
                  f"{r['adresse'] or ''} | {r['provenance']} | FINESS {r['finess'] or '-'}{unites}")
    # Acceslibre (registre public de l'accessibilité, Licence Ouverte), aide à la vérification seulement
    al = config.BRUT / "acceslibre.csv.gz"
    if al.exists():
        a = pd.read_csv(al, dtype=str, compression="gzip", usecols=["name", "numero", "voie", "commune", "code_insee"])
        deps = set(g["commune"].map(ref.communes.set_index("code")["dep"]).dropna())
        a = a[a["code_insee"].fillna("").str[:2].isin({d[:2] for d in deps})
              & a["name"].fillna("").str.contains(r"\bC\.?M\.?P|CATTP|m[ée]dico.?psycho|h[ôo]pital de jour|psychiatr",
                                                  case=False, regex=True)]
        if len(a):
            print("\n--- Acceslibre, même département")
            for _, r in a.iterrows():
                print(f"   {r['name'][:70]:70} | {r['numero'] or ''} {r['voie'] or ''}, {r['commune']}")


def valider():
    e, s = sv.charger()
    ref = _ref()
    c = ref.communes
    codes = set(c["code"])
    types = {t[0] for t in config.LIEUX_TYPES}
    pb = []
    # communes données par leur nom, remplacées par leur code (nom unique dans le département de l'établissement)
    dep_ej = e.set_index("ej")["departement"].to_dict()
    from pipeline.lieux import _simple
    c = c.assign(s=c["nom"].map(_simple))
    for i, r in s.iterrows():
        if r["commune"] in codes:
            continue
        # départements où l'établissement est vérifié (plusieurs pour un gestionnaire présent dans plusieurs départements)
        deps_v = set(e.loc[e["ej"] == r["ej"], "departement"]) - {""}
        d = dep_ej.get(r["ej"], "") if len(deps_v) <= 1 else ""
        m = c[(c["s"] == _simple(r["commune"])) & ((c["dep"] == d) if d else
                                                     (c["dep"].isin(deps_v) if deps_v else True))]
        if len(m) > 1 and not d:
            # établissement sur plusieurs départements, celui où il a des inscriptions dans les bases
            b0 = _bases()
            deps_ej = set(b0.loc[b0["ej"] == r["ej"], "commune"].map(c.set_index("code")["dep"]).dropna())
            m = m[m["dep"].isin(deps_ej)]
        if len(m) == 1:
            s.at[i, "commune"] = m["code"].iloc[0]
        else:
            pb.append(f"commune introuvable ou ambiguë, « {r['commune']} » ({r['nom']})")
    for i, r in s.iterrows():
        if r["type"] not in types:
            pb.append(f"type inconnu {r['type']} ({r['nom']})")
        if r["statut"] not in sv.STATUTS:
            pb.append(f"statut inconnu « {r['statut']} » ({r['nom']})")
        if r["statut"] != "bases" and (not r["source"] or not r["adresse_source"].startswith("http")):
            pb.append(f"source ou lien manquant ({r['nom']})")
        if r["ej"] not in set(e["ej"]):
            pb.append(f"établissement {r['ej']} absent de etablissements_verifies.csv ({r['nom']})")
        # vérification limitée à un public, chaque structure de la liste doit être de ce public
        for _, et in e[e["ej"] == r["ej"]].iterrows():
            p = sv.perimetres(et["types"]).get(r["type"])
            if p and p.rstrip("s") not in r["public"]:
                pb.append(f"public « {r['public']} » hors du périmètre vérifié ({p}) ({r['nom']})")
    dbl = s[s.duplicated(["ej", "type", "commune", "nom"], keep=False)]
    for _, r in dbl.iterrows():
        pb.append(f"structure en double, {r['nom']}")
    s.to_csv(sv.FICHIER, sep=";", index=False, encoding="utf-8")
    # géocodage des adresses nouvelles (en ligne), pour que la chaîne hors ligne les trouve dans le cache
    from pipeline.lieux import _geocoder
    if len(s):
        _geocoder(s[["adresse", "commune"]].rename(columns={"adresse": "voie"}), False)
    # empreinte des inscriptions au moment de la vérification
    b = _bases()
    for i, r in e.iterrows():
        if not r["empreinte"]:
            ts = [t for t in sv.types_de(r["types"]) if t not in sum(sv.ENFANTS_DE.values(), [])]
            if "dep" not in b:
                b = b.assign(dep=b["commune"].map(ref.communes.set_index("code")["dep"]))
            e.at[i, "empreinte"] = sv.empreinte(b, r["ej"], ts, r["departement"])
    e.to_csv(sv.FICHIER_ETAB, sep=";", index=False, encoding="utf-8")
    for p in pb:
        print("problème |", p)
    print(f"{len(e)} établissements, {len(s)} structures, {len(pb)} problème(s)")
    sys.exit(20 if pb else 0)


A_VERIFIER = RACINE / "docs" / "a_verifier_par_lucas.csv"
VERDICTS = RACINE / "contenus" / "verdicts_verification.csv"
CAS = RACINE / "docs" / "structures_a_verifier_par_lucas.csv"
COLS_AV = ["categorie", "departement", "etablissement", "ej", "structure", "commune", "adresse", "finess",
           "ce_que_disent_les_sources", "question", "lien", "verdict", "commentaire", "cle"]


def _cle(ej, finess, commune, nom) -> str:
    from pipeline.lieux import _simple
    return "|".join([str(ej or ""), str(finess or "").split(",")[0], str(commune or ""), _simple(str(nom or ""))[:40]])


def a_verifier():
    """Écrit docs/a_verifier_par_lucas.csv, tout ce qui reste à trancher à la main, refait à chaque appel à partir de
    la dernière exécution, avec les verdicts déjà donnés (contenus/verdicts_verification.csv)."""
    ref = _ref()
    nc = ref.communes.set_index("code")["nom"]
    dc = ref.communes.set_index("code")["dep"]
    der = sorted(p for p in (RACINE / "resultats").glob("20*") if p.is_dir())[-1]
    e, _ = sv.charger()
    noms_ej = e.drop_duplicates("ej").set_index("ej")["etablissement"]
    lignes = []
    # 1. cas expliqués un à un
    if CAS.exists():
        for _, r in pd.read_csv(CAS, sep=";", dtype=str).fillna("").iterrows():
            lignes.append({"categorie": "1. Cas expliqués", "departement": r["departement"],
                           "etablissement": r["etablissement"], "ej": r["ej"], "structure": r["structure"],
                           "commune": "", "adresse": "", "finess": "", "ce_que_disent_les_sources": r["ce_que_disent_les_sources"],
                           "question": r["question"], "lien": r["liens"]})
    # 2. gardées, absentes de la source de l'établissement mais confirmées par la HAS ou Sirene
    # 3. retirées, absentes de la source de l'établissement et non confirmées
    for fic, cat, q in [("structures_gardees_a_verifier.csv", "2. Absente du site de l'établissement, gardée (HAS ou Sirene)",
                         "Existe-t-elle encore ? Fermée, déménagée, doublon d'une structure de la liste ?"),
                        ("structures_non_retenues.csv", "3. Absente du site de l'établissement, retirée (ni HAS ni Sirene)",
                         "Fermée ou doublon, comme supposé ? Sinon, existe-t-elle ?")]:
        p = der / fic
        if not p.exists():
            continue
        for _, r in pd.read_csv(p, sep=";", dtype=str).fillna("").iterrows():
            src = e.loc[e["ej"] == r["ej"], "sources"]
            lignes.append({"categorie": cat, "departement": dc.get(r["commune"], ""), "etablissement": r["etablissement"],
                           "ej": r["ej"], "structure": r["nom"], "commune": nc.get(r["commune"], r["commune"]),
                           "adresse": "", "finess": r["finess"],
                           "ce_que_disent_les_sources": f"Inscrite dans {'FINESS et le ROR' if r['provenance'] == 'les_deux' else ('FINESS' if r['provenance'] == 'finess' else 'le ROR')}, "
                                                        f"absente de la source de l'établissement ({src.iloc[0] if len(src) else ''}).",
                           "question": q, "lien": ""})
    # 4. CMP inscrits seulement dans les bases, sans confirmation (établissements sans liste en ligne)
    L = pd.read_csv(der / "lieux_soins.csv", sep=";", dtype=str, low_memory=False).fillna("")
    c = L[(L["type"] == "lieu_cmp") & L["confirmation"].str.contains("vérifier")]
    perim = {r["ej"]: sv.perimetres(r["types"]).get("lieu_cmp") for _, r in e.iterrows()}
    for _, r in c.iterrows():
        ej = r["entite_juridique"]
        if ej in perim and perim[ej]:
            suite = f", établissement vérifié pour ses seuls CMP pour {perim[ej]}"
        elif ej in perim:
            suite = ", dans un établissement vérifié"
        else:
            suite = ", établissement sans liste en ligne trouvée"
        lignes.append({"categorie": "4. CMP inscrit seulement dans FINESS ou le ROR" + suite,
                       "departement": r["dep"], "etablissement": noms_ej.get(r["entite_juridique"], ""),
                       "ej": r["entite_juridique"], "structure": r["nom"], "commune": r["nom_commune"],
                       "adresse": r["adresse"], "finess": r["finess"],
                       "ce_que_disent_les_sources": f"Inscrit dans {r['provenance']}, ni la certification HAS ni Sirene ne le confirment.",
                       "question": "Existe-t-il, à cette adresse ? Est-ce bien un CMP ?", "lien": r["adresse_source_verification"]})
    t = pd.DataFrame(lignes, columns=COLS_AV)
    t["cle"] = [_cle(r.ej, r.finess, r.commune, r.structure) for r in t.itertuples()]
    if VERDICTS.exists():
        v = pd.read_csv(VERDICTS, sep=";", dtype=str).fillna("").drop_duplicates("cle", keep="last").set_index("cle")
        t["verdict"] = t["cle"].map(v["verdict"]).fillna("")
        t["commentaire"] = t["cle"].map(v["commentaire"]).fillna("")
    t = t.fillna("").sort_values(["categorie", "departement", "etablissement", "commune", "structure"])
    t.to_csv(A_VERIFIER, sep=";", index=False, encoding="utf-8-sig")
    print(t["categorie"].value_counts().sort_index().to_string())
    print(f"{len(t)} lignes, dont {int((t['verdict'] != '').sum())} déjà tranchées, écrit dans {A_VERIFIER}")


def verdicts():
    """Range les verdicts remplis dans docs/a_verifier_par_lucas.csv dans contenus/verdicts_verification.csv (versionné)."""
    t = pd.read_csv(A_VERIFIER, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    t = t[t["verdict"].str.strip() != ""]
    old = pd.read_csv(VERDICTS, sep=";", dtype=str).fillna("") if VERDICTS.exists() else pd.DataFrame(
        columns=["cle", "etablissement", "structure", "verdict", "commentaire", "date"])
    import datetime as dt
    new = t[["cle", "etablissement", "structure", "verdict", "commentaire"]].assign(date=dt.date.today().isoformat())
    out = pd.concat([old, new]).drop_duplicates("cle", keep="last")
    out.to_csv(VERDICTS, sep=";", index=False, encoding="utf-8")
    print(f"{len(new)} verdicts lus, {len(out)} en tout dans {VERDICTS}")


def etat():
    e, s = sv.charger()
    b = _bases()
    n_ej = b.loc[b["type"] == "lieu_cmp", "ej"].nunique()
    print(f"{len(e)} établissements vérifiés sur {n_ej} qui gèrent des CMP, {len(s)} structures vérifiées")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("commande", choices=["fiche", "valider", "etat", "a-verifier", "verdicts"])
    ap.add_argument("cle", nargs="?")
    a = ap.parse_args()
    {"fiche": lambda: fiche(a.cle), "valider": valider, "etat": etat, "a-verifier": a_verifier,
     "verdicts": verdicts}[a.commande]()
