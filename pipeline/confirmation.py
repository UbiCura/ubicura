"""Confirmation des structures par des listes officielles indépendantes de FINESS et du ROR (décision de Lucas du
13 octobre 2026, « qu'à la fin on n'ait plus de doute »).

Trois listes, tirées automatiquement à chaque mise à jour.
- Les sites que chaque établissement déclare à sa certification par la HAS (sources/has_certification.py). Un CMP
  dont un numéro FINESS (le sien, celui d'une inscription rapprochée ou réunie) est un site de certification dont le
  nom désigne un CMP est confirmé.
- Les établissements de son gestionnaire inscrits au répertoire Sirene sous une enseigne de CMP
  (sources/sirene.py), dans la même commune. Quand une commune en compte plusieurs, ils sont appariés un à un par les
  mots du nom, le public (enfants ou adultes) et la rue. L'adresse de Sirene est gardée à côté.
- Pour le médico-social (CMPP, CAMSP, CSAPA, CAARUD), que la certification ne couvre pas, les évaluations des
  établissements et services médico-sociaux publiées par la HAS (sources/has_essms.py). Une structure dont un numéro
  FINESS a été évalué sous une catégorie FINESS de son type est confirmée (accord de Lucas du 16 octobre 2026).
Les types confirmés et le nom qui les désigne sont dans config.SIRENE_ENSEIGNES. Un type réservé à un public (hôpitaux de
jour pour adultes ou pour enfants) n'est confirmé que par un établissement ou un site du même public.

Les structures vérifiées sur les sources de leur établissement gardent leur statut. Les établissements Sirene actifs
sans correspondant sont listés à part, à vérifier, jamais ajoutés d'eux-mêmes (un hôpital ferme rarement ses anciens
établissements dans Sirene).
"""
from __future__ import annotations

import re

import pandas as pd

from . import config
from .util import JOURNAL

NIVEAUX = {"etablissement": "vérifiée sur les sources de l'établissement",
           "source_publique": "vérifiée sur une autre source publique (HAS, ARS, Acceslibre)",
           "has_sirene": "confirmée par la HAS et par Sirene",
           "has": "confirmée par la HAS (certification de l'hôpital ou évaluation de la structure)",
           "sirene": "confirmée par Sirene",
           "principal": "confirmée par son site principal (antenne ou site rattaché)",
           "sae": "concordante avec la SAE (nombre de CATTP de l'établissement, places d'hôpital de jour du site)",
           "examinee": "examinée à la main et maintenue (source dans la colonne examen)",
           "bases": "inscrite dans FINESS ou le ROR, à vérifier"}
# libellés courts lus dans l'atlas (encadré des structures d'un territoire, fiche d'une structure), le niveau « bases »
# seul est montré par un point creux, les autres par un point plein (décision de Lucas du 15 octobre 2026)
NIVEAUX_COURTS = {"etablissement": "vérifiée sur les sources de l'établissement",
                  "source_publique": "vérifiée sur une autre source publique",
                  "has_sirene": "confirmée par la HAS et Sirene",
                  "has": "confirmée par la HAS",
                  "sirene": "confirmée par Sirene",
                  "sae": "recoupée par la statistique des hôpitaux (nombre de CATTP de l'établissement ou places d'hôpital de "
                         "jour du site, l'adresse n'est pas confirmée)",
                  "examinee": "examinée à la main et maintenue",
                  "bases": "inscrite dans FINESS ou le ROR seulement, à vérifier"}
# Trois classes montrées au lecteur (décision de Lucas du 21 octobre 2026), le détail par source restant dans la page
# méthode et la colonne confirmation des fichiers. Confirmée, la structure est nommée par une source indépendante des
# deux bases. Recoupée par la SAE, c'est le nombre (CATTP) ou l'activité du site (hôpital de jour) qui est confirmé, pas
# l'adresse. À vérifier, la structure n'est inscrite que dans FINESS ou le ROR.
CLASSES = {"confirmee": "confirmée", "recoupee": "recoupée par la statistique des hôpitaux", "a_verifier": "à vérifier"}


def classe(niveau) -> str | None:
    """Classe montrée au lecteur pour un niveau de confirmation (None quand le niveau n'est pas établi)."""
    if not isinstance(niveau, str) or not niveau:
        return None
    return "a_verifier" if niveau == "bases" else "recoupee" if niveau == "sae" else "confirmee"


def compter_classes(niveaux: pd.Series) -> dict:
    """Nombre de structures par classe, les trois refont le total des structures au niveau établi."""
    c = niveaux.map(classe).value_counts()
    return {k: int(c.get(k, 0)) for k in CLASSES}


VIDES = {"cmp", "centre", "medico", "psychologique", "cattp", "hdj", "hopital", "jour", "de", "du", "des", "la", "le",
         "les", "et", "adultes", "adulte", "enfants", "enfant", "secteur", "ch", "chs", "epsm", "psychiatrie",
         "consultations", "consultation", "infanto", "juvenile", "pole", "ado", "ados", "adolescents", "intersecteur"}


def _simple(s) -> str:
    from .lieux import _simple as s_
    return s_(s)


def _mots(x) -> set[str]:
    return {w for w in _simple(x).split() if w not in VIDES and len(w) > 2 and not w.isdigit()}


def _nums(r) -> set[str]:
    out = set()
    for c in ("finess", "finess_rapproche", "finess_absorbes"):
        v = r.get(c)
        if isinstance(v, str) and v:
            out |= set(v.split(","))
    return out


# Types confirmés aussi par le nombre que leur établissement déclare à la SAE, avec la colonne de statut de
# lieux.concordance_etablissements (décision de Lucas du 16 octobre 2026 pour les CATTP, souvent une activité tenue dans
# un CMP ou un centre de jour plutôt qu'un lieu à part, que les sites des hôpitaux ne listent presque jamais)
PAR_SAE = {"lieu_cattp": "statut_cattp"}
# Hôpitaux de jour, activité d'un site plutôt que lieu nommé (16 octobre 2026). Un hôpital de jour qu'aucune liste ne
# confirme l'est quand un de ses numéros FINESS est un site qui déclare à la SAE des places d'hôpital de jour dans la
# discipline de son public (psychiatrie générale pour les adultes, infanto-juvénile pour les enfants).
PAR_SAE_SITE = {"lieu_hdj_psy_adultes": "GEN", "lieu_hdj_psy_enfants": "INF"}
# types pour lesquels la classe « recoupée » existe, « sans objet » pour les autres (remarque de Lucas du 21 octobre
# 2026, un 0 laissait croire que la statistique des hôpitaux avait été consultée sans rien trouver)
TYPES_RECOUPES = set(PAR_SAE) | set(PAR_SAE_SITE)


def confirmer_par_sae(lieux: pd.DataFrame, etab: pd.DataFrame | None, sae: dict | None = None) -> pd.DataFrame:
    """Une structure d'un type de PAR_SAE qu'aucune liste ne confirme (niveau « bases ») prend le niveau « sae » quand
    son établissement en compte ici autant qu'il en déclare à la SAE (à 20 % ou une structure près). C'est une
    confirmation du nombre, pas de chaque adresse, d'où un niveau à part, après les listes nommant la structure."""
    if "confirmation" not in lieux:
        return lieux
    x = lieux.copy()
    sites = (sae or {}).get("hdj_sites") or {}
    for tid, dis in PAR_SAE_SITE.items():
        fi = sites.get(dis, set())
        if not fi:
            continue
        m = (x["type"] == tid) & (x["confirmation"] == "bases")
        m &= pd.Series([bool(_nums(r) & fi) for _, r in x.iterrows()], index=x.index) if m.any() else m
        x.loc[m, "confirmation"] = "sae"
        n = x.loc[x["type"] == tid, "confirmation"].value_counts()
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}[tid]
        JOURNAL.controle(f"Confirmation des structures par la SAE, {lib}",
                         f"{int(m.sum())} structures sur un site qui déclare des places d'hôpital de jour à la SAE, "
                         f"{int(n.get('bases', 0))} restent à vérifier")
    if not isinstance(etab, pd.DataFrame):
        return x
    for tid, col in PAR_SAE.items():
        if col not in etab:
            continue
        ok = set(etab.loc[etab[col] == "concorde", "ej"])
        m = (x["type"] == tid) & (x["confirmation"] == "bases") & x["ej"].isin(ok)
        x.loc[m, "confirmation"] = "sae"
        n = x.loc[x["type"] == tid, "confirmation"].value_counts()
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}[tid]
        JOURNAL.controle(f"Confirmation des structures par la SAE, {lib}",
                         f"{int(m.sum())} structures de {len(ok)} établissements au nombre concordant avec la SAE, "
                         f"{int(n.get('bases', 0))} restent à vérifier")
    return x


def _du_public(noms: pd.Series, public: str | None) -> pd.Series:
    """Noms compatibles avec le public d'un type (tous quand le type n'a pas de public propre)."""
    enf = noms.fillna("").str.contains(config.NOM_PUBLIC_ENFANTS, case=False, regex=True)
    adu = noms.fillna("").str.contains(config.NOM_PUBLIC_ADULTES, case=False, regex=True)
    # un nom neutre (« HDJ Les Tilleuls ») peut confirmer l'un ou l'autre public, l'appariement un à un tranche
    return (enf | ~adu) if public == "enfants" else ~enf if public == "adultes" else pd.Series(True, index=noms.index)


def confirmer(lieux: pd.DataFrame, has: dict | None, sir: dict | None,
              essms: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ajoute à chaque structure d'un type confirmé (config.SIRENE_ENSEIGNES) les colonnes confirmee_has, siret_sirene,
    enseigne_sirene, adresse_sirene et confirmation (niveau). Renvoie les structures et les établissements Sirene actifs
    sans correspondant."""
    x = lieux.copy()
    for c in ("confirmee_has", "siret_sirene", "enseigne_sirene", "adresse_sirene", "confirmation"):
        x[c] = None
    sans = []
    enfants_de = {t[0]: t[4]["parent"] for t in config.LIEUX_TYPES if t[4].get("parent")}
    params = {t[0]: t[4] for t in config.LIEUX_TYPES}
    for tid, motif in config.SIRENE_ENSEIGNES.items():
        m = x["type"] == tid
        g = x[m]
        public = params.get(tid, {}).get("public")
        x.loc[m, "confirmee_has"] = False
        # certification HAS, sites dont le nom désigne ce type (et son public)
        if has is not None:
            s = has["sites"]
            nom = s["RS_eg"].fillna("")
            eg = set(s.loc[nom.str.contains(motif, case=False, regex=True) & _du_public(nom, public), "FINESS_EG"])
            x.loc[m, "confirmee_has"] = [bool(_nums(r) & eg) for _, r in g.iterrows()]
        # évaluation HAS des établissements médico-sociaux, sous une catégorie FINESS du type
        cats = params.get(tid, {}).get("finess")
        if essms is not None and cats:
            ev = essms["evaluations"]
            nums = set(ev.loc[ev["categorie"].isin(cats), "finess"])
            if nums:
                deja = x.loc[m, "confirmee_has"].fillna(False).astype(bool)
                x.loc[m, "confirmee_has"] = deja | pd.Series([bool(_nums(r) & nums) for _, r in g.iterrows()],
                                                           index=g.index)
        # Sirene, établissements actifs du même gestionnaire, même commune, enseigne du type
        if sir is not None:
            e = sir["etablissements"]
            e = e[(e["etatAdministratifEtablissement"] == "A") & e["enseigne"].str.contains(motif, case=False, regex=True)
                  & _du_public(e["enseigne"], public)]
            par_siren = {k: v for k, v in e.groupby("siren")}
            pub = x[x["type"].isin([k for k, v in enfants_de.items() if v == tid])].groupby("lieu")["type"].apply(set)
            for ej, ge in g.groupby("ej"):
                cand_ej = par_siren.get(sir["siren"].get(ej))
                if cand_ej is None:
                    continue
                pris = set()
                for i, r in ge.iterrows():
                    cand = cand_ej[(cand_ej["codeCommuneEtablissement"] == r["commune"]) & ~cand_ej["siret"].isin(pris)]
                    if cand.empty:
                        continue
                    nom = r.get("nom") if isinstance(r.get("nom"), str) else r.get("nom_finess")
                    publics = set(pub.get(r["lieu"], set())) | ({f"lieu_cmp_{public}"} if public else set())
                    sc = {}
                    for k, cr in cand.iterrows():
                        enf = bool(re.search(config.NOM_PUBLIC_ENFANTS, cr["enseigne"], re.I))
                        sc[k] = (len(_mots(nom) & _mots(cr["enseigne"]))
                                 + 2 * (bool(r.get("adresse")) and _simple(str(r.get("adresse")))[-10:] in _simple(cr["adresse"]))
                                 + ((enf and "lieu_cmp_enfants" in publics) or (not enf and "lieu_cmp_adultes" in publics)))
                    seuls = len(cand) == 1 and (ge["commune"] == r["commune"]).sum() == 1
                    k = max(sc, key=sc.get)
                    if sc[k] > 0 or seuls:
                        pris.add(cand.at[k, "siret"])
                        x.loc[i, ["siret_sirene", "enseigne_sirene", "adresse_sirene"]] = \
                            [cand.at[k, "siret"], cand.at[k, "enseigne"], cand.at[k, "adresse"]]
                reste = cand_ej[~cand_ej["siret"].isin(pris)]
                for _, cr in reste.iterrows():
                    sans.append({"type": tid, "ej": ej, "siret": cr["siret"], "enseigne": cr["enseigne"],
                                 "adresse": cr["adresse"], "commune": cr["codeCommuneEtablissement"],
                                 "date_creation": cr.get("dateCreationEtablissement")})
        # niveau de confirmation
        st = x.loc[m, "statut_verification"] if "statut_verification" in x else pd.Series(None, index=g.index)
        h = x.loc[m, "confirmee_has"].fillna(False).astype(bool)
        si = x.loc[m, "siret_sirene"].notna()
        niv = pd.Series("bases", index=g.index, dtype=object)
        niv[si] = "sirene"
        niv[h] = "has"
        niv[h & si] = "has_sirene"
        niv[st.isin(["etablissement", "source_publique"])] = st[st.isin(["etablissement", "source_publique"])]
        x.loc[m, "confirmation"] = niv
        # les CMP pour adultes et pour enfants prennent le niveau de leur CMP « tous publics »
        par_lieu = x.loc[m].drop_duplicates("lieu").set_index("lieu")
        for enf, par in enfants_de.items():
            if par != tid:
                continue
            me = x["type"] == enf
            for c in ("confirmee_has", "siret_sirene", "enseigne_sirene", "adresse_sirene", "confirmation"):
                x.loc[me, c] = x.loc[me, "lieu"].map(par_lieu[c])
        n = niv.value_counts()
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}[tid]
        JOURNAL.controle(f"Confirmation des structures, {lib}",
                         f"{len(g)} structures, " + ", ".join(f"{NIVEAUX[k]} {int(n.get(k, 0))}" for k in NIVEAUX)
                         + f", établissements Sirene actifs sans correspondant {sum(1 for s_ in sans if s_['type'] == tid)}")
    return x, pd.DataFrame(sans, columns=["type", "ej", "siret", "enseigne", "adresse", "commune", "date_creation"])
