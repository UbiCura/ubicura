"""Confirmation des structures par des listes officielles indépendantes de FINESS et du ROR (décision du
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
  FINESS a été évalué sous une catégorie FINESS de son type est confirmée (accord du 16 octobre 2026).
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
           "sae": "concordante avec la SAE (nombre de CATTP de l'établissement, places d'hôpital de jour ou lits à temps plein du site)",
           "examinee": "examinée à la main et maintenue (source dans la colonne examen)",
           "bases": "à confirmer, inscrite dans FINESS ou le ROR, pas encore vérifiée une à une",
           # cherchée sur les sources de son établissement sans rien trouver (statut « bases » de la liste vérifiée), puis
           # demande de confirmation envoyée à l'établissement (décision du 18 novembre 2026, maquette
           # prototypes/structures_non_confirmees/) ; la date s'écrit après « @ » (cherchee@2026-11-18), libelle() la lit
           "cherchee": "non confirmée, aucune source officielle de moins de trois ans trouvée",
           "demande": "non confirmée, demande envoyée à l'établissement, en attente de réponse"}
# libellés courts lus dans l'atlas (encadré des structures d'un territoire, fiche d'une structure), le niveau « bases »
# seul est montré par un point creux, les autres par un point plein (décision du 15 octobre 2026)
NIVEAUX_COURTS = {"etablissement": "vérifiée sur les sources de l'établissement",
                  "source_publique": "vérifiée sur une autre source publique",
                  "has_sirene": "confirmée par la HAS et Sirene",
                  "has": "confirmée par la HAS",
                  "sirene": "confirmée par Sirene",
                  "sae": "recoupée par la statistique des hôpitaux (nombre de CATTP de l'établissement ou places d'hôpital de "
                         "jour ou lits à temps plein du site, l'adresse n'est pas confirmée)",
                  "examinee": "examinée à la main et maintenue",
                  "bases": "à confirmer, inscrite dans FINESS ou le ROR, pas encore vérifiée une à une",
                  "cherchee": "non confirmée, aucune source officielle de moins de trois ans trouvée",
                  "demande": "non confirmée, demande envoyée à l'établissement, en attente de réponse"}
# Classes montrées au lecteur (décisions du 21 octobre et du 18 novembre 2026), le détail par source restant dans la
# page méthode et la colonne confirmation des fichiers. Confirmée, la structure est nommée par une source indépendante
# des deux bases. Recoupée par la SAE, c'est le nombre (CATTP) ou l'activité du site (hôpital de jour) qui est
# confirmé, pas l'adresse. À confirmer, elle n'est inscrite que dans FINESS ou le ROR et n'a pas encore été vérifiée une
# à une. Non confirmée, elle a été cherchée sur les sources de son établissement sans source officielle récente.
CLASSES = {"confirmee": "confirmée", "recoupee": "recoupée par la statistique des hôpitaux", "a_verifier": "à confirmer",
           "non_confirmee": "non confirmée"}
NON_CONFIRMEES = ("cherchee", "demande")
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre"]


def _date_fr(iso: str) -> str:
    try:
        a, m, j = (int(v) for v in iso.split("-"))
        return f"{'1er' if j == 1 else j} {MOIS[m - 1]} {a}"
    except (ValueError, IndexError):
        return ""


def libelle(niveau, court: bool = False) -> str | None:
    """Libellé d'un niveau, daté pour une structure cherchée ou une demande envoyée (« cherchee@2026-11-18 »)."""
    if not isinstance(niveau, str) or not niveau:
        return None
    # niveau suivi d'une structure d'un autre gestionnaire à la même adresse ou dans la même rue
    # (« bases|adresse|CMPEA Blanquefort », « bases|rue|... »)
    niveau, _, meme = niveau.partition("|")
    if meme:
        lib, phrase = libelle(niveau, court), meme_adresse(niveau + "|" + meme)
        return (lib + ", " + phrase) if lib else phrase[0].upper() + phrase[1:]
    base, _, date = niveau.partition("@")
    d = _date_fr(date) if date else ""
    if base == "cherchee":
        return "non confirmée, aucune source officielle de moins de trois ans trouvée" + (f" au {d}" if d else "")
    if base == "demande":
        return ("non confirmée, demande envoyée à l'établissement" + (f" le {d}" if d else "")
                + ", en attente de réponse")
    return (NIVEAUX_COURTS if court else NIVEAUX).get(base, NIVEAUX.get(base))


def meme_adresse(niveau) -> str | None:
    """Mention d'une structure d'un autre gestionnaire à la même adresse ou dans la même rue, lue dans le niveau codé
    (« bases|adresse|CMPEA Blanquefort ») ; None sans elle. La même phrase dans les fichiers, l'atlas et les fiches."""
    if not isinstance(niveau, str) or "|" not in niveau:
        return None
    _, _, meme = niveau.partition("|")
    lieu, _, nom = meme.partition("|")
    return f"même {'adresse' if lieu == 'adresse' else 'rue'} que « {nom} », d'un autre gestionnaire, peut-être la même structure"


def avec_meme_adresse(x: pd.DataFrame) -> pd.Series:
    """Niveau de confirmation de chaque structure, suivi après « | » du nom de la structure d'un autre gestionnaire à la
    même adresse quand il y en a une (lieux.py, contrôle des paires à la même adresse, 22 novembre 2026)."""
    conf = x["confirmation"] if "confirmation" in x else pd.Series(None, index=x.index, dtype=object)
    if "meme_adresse_que" not in x:
        return conf
    m = conf.notna() & x["meme_adresse_que"].notna()
    num = x["meme_adresse_numero"].astype(str).eq("True") if "meme_adresse_numero" in x else pd.Series(True, index=x.index)
    lieu = num.map({True: "adresse", False: "rue"})
    return conf.where(~m, conf.astype(str) + "|" + lieu + "|" + x["meme_adresse_que"].astype(str))


def classe(niveau) -> str | None:
    """Classe montrée au lecteur pour un niveau de confirmation (None quand le niveau n'est pas établi)."""
    if not isinstance(niveau, str) or not niveau:
        return None
    base = niveau.partition("|")[0].partition("@")[0]
    return ("a_verifier" if base == "bases" else "non_confirmee" if base in NON_CONFIRMEES
            else "recoupee" if base == "sae" else "confirmee")


def non_confirmer(x: pd.DataFrame, demandes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Structure au niveau « bases » que sa liste vérifiée garde sans source (statut « bases ») : « cherchee@date ».
    Avec une demande de confirmation envoyée à son établissement et sans réponse (contenus/demandes_confirmation.csv),
    « demande@date d'envoi ». Une confirmation par la HAS, Sirene ou la SAE l'emporte (niveau autre que « bases »)."""
    if "confirmation" not in x or "statut_verification" not in x:
        return x
    x = x.copy()
    m = (x["confirmation"] == "bases") & (x["statut_verification"] == "bases")
    dates = x.get("date_verification", pd.Series("", index=x.index)).fillna("").astype(str)
    x.loc[m, "confirmation"] = "cherchee@" + dates[m]
    if isinstance(demandes, pd.DataFrame) and not demandes.empty:
        en_attente = demandes[demandes["reponse"].fillna("").str.strip() == ""]
        envoi = en_attente.groupby("ej")["date_envoi"].max().to_dict()
        md = m & x["ej"].isin(envoi)
        x.loc[md, "confirmation"] = "demande@" + x.loc[md, "ej"].map(envoi)
    # chaque structure une fois : un CMP a aussi une ligne pour son public (types « enfants » d'un type parent), qui
    # ne s'ajoute pas au compte (relecture du 21 novembre 2026, 719 lignes pour 615 structures)
    par_public = {t[0] for t in config.LIEUX_TYPES if t[4].get("parent")}
    mu = m & ~x["type"].isin(par_public) if "type" in x else m
    n = x.loc[mu, "confirmation"].map(lambda v: v.partition("@")[0]).value_counts()
    JOURNAL.controle("Structures non confirmées (cherchées sur les sources de leur établissement sans source récente)",
                     f"{int(mu.sum())} structures, dont {int(n.get('demande', 0))} avec une demande de confirmation "
                     "envoyée à l'établissement et sans réponse")
    return x


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
# lieux.concordance_etablissements (décision du 16 octobre 2026 pour les CATTP, souvent une activité tenue dans
# un CMP ou un centre de jour plutôt qu'un lieu à part, que les sites des hôpitaux ne listent presque jamais)
PAR_SAE = {"lieu_cattp": "statut_cattp"}
# Hôpitaux de jour, activité d'un site plutôt que lieu nommé (16 octobre 2026). Un hôpital de jour qu'aucune liste ne
# confirme l'est quand un de ses numéros FINESS est un site qui déclare à la SAE des places d'hôpital de jour dans la
# discipline de son public (psychiatrie générale pour les adultes, infanto-juvénile pour les enfants).
# L'hospitalisation complète l'est de même par les lits à temps plein déclarés par le site (23 novembre 2026, 421 des 641
# structures pour adultes le 22 novembre ; un établissement qui en déclare sur un autre site ne suffit pas).
PAR_SAE_SITE = {"lieu_hdj_psy_adultes": ("hdj_sites", "GEN"), "lieu_hdj_psy_enfants": ("hdj_sites", "INF"),
                "lieu_hc_psy_adultes": ("htp_sites", "GEN"), "lieu_hc_psy_enfants": ("htp_sites", "INF")}
# types pour lesquels la classe « recoupée » existe, « sans objet » pour les autres (remarque du 21 octobre
# 2026, un 0 laissait croire que la statistique des hôpitaux avait été consultée sans rien trouver)
TYPES_RECOUPES = set(PAR_SAE) | set(PAR_SAE_SITE)
# types dont le niveau de confirmation est établi : ceux que des listes indépendantes confirment (config.SIRENE_ENSEIGNES),
# plus ceux que seule la SAE recoupe (hospitalisation complète, 23 novembre 2026), qui partent « à confirmer »
TYPES_ETABLIS = list(config.SIRENE_ENSEIGNES) + [t for t in PAR_SAE_SITE if t not in config.SIRENE_ENSEIGNES]


def confirmer_par_sae(lieux: pd.DataFrame, etab: pd.DataFrame | None, sae: dict | None = None) -> pd.DataFrame:
    """Une structure d'un type de PAR_SAE qu'aucune liste ne confirme (niveau « bases ») prend le niveau « sae » quand
    son établissement en compte ici autant qu'il en déclare à la SAE (à 20 % ou une structure près). C'est une
    confirmation du nombre, pas de chaque adresse, d'où un niveau à part, après les listes nommant la structure."""
    if "confirmation" not in lieux:
        return lieux
    x = lieux.copy()
    for tid, (table, dis) in PAR_SAE_SITE.items():
        fi = ((sae or {}).get(table) or {}).get(dis, set())
        if not fi:
            continue
        m = (x["type"] == tid) & (x["confirmation"] == "bases")
        m &= pd.Series([bool(_nums(r) & fi) for _, r in x.iterrows()], index=x.index) if m.any() else m
        x.loc[m, "confirmation"] = "sae"
        n = x.loc[x["type"] == tid, "confirmation"].value_counts()
        lib = {t[0]: t[1] for t in config.LIEUX_TYPES}[tid]
        JOURNAL.controle(f"Confirmation des structures par la SAE, {lib}",
                         f"{int(m.sum())} structures sur un site qui déclare des "
                         f"{'lits à temps plein' if table == 'htp_sites' else 'places d’hôpital de jour'} à la SAE, "
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
              essms: dict | None = None, etape: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
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
        # l'étape est dans le libellé : la chaîne confirme deux fois, avant et après les listes vérifiées, et le
        # contrôle ne doit pas se lire comme le compte final des tableaux (relecture du 17 novembre 2026)
        JOURNAL.controle(f"Confirmation des structures, {lib}" + (f", {etape}" if etape else ""),
                         # « : aucune » plutôt qu'un 0 collé au libellé (« de l'établissement 0 », 6 novembre 2026)
                         f"{len(g)} structures, " + ", ".join(f"{NIVEAUX[k]} : {int(n.get(k, 0)) or 'aucune'}" for k in NIVEAUX)
                         + f", établissements Sirene actifs sans correspondant : "
                           f"{sum(1 for s_ in sans if s_['type'] == tid) or 'aucun'}")
    # types que seule la SAE recoupe (hospitalisation complète) : aucune liste indépendante ne les nomme, ils partent « à
    # confirmer », ou au niveau de la liste vérifiée de leur établissement, pour que confirmer_par_sae puisse les recouper
    # (relecture du 23 novembre 2026 : sans niveau, la classe « recoupée » annoncée ne s'appliquait à aucune structure)
    st_all = x["statut_verification"] if "statut_verification" in x else pd.Series(None, index=x.index)
    for tid in TYPES_ETABLIS[len(config.SIRENE_ENSEIGNES):]:
        m = x["type"] == tid
        x.loc[m, "confirmee_has"] = False
        niv = pd.Series("bases", index=x.index[m], dtype=object)
        ok = st_all[m].isin(["etablissement", "source_publique"])
        niv[ok] = st_all[m][ok]
        x.loc[m, "confirmation"] = niv
    return x, pd.DataFrame(sans, columns=["type", "ej", "siret", "enseigne", "adresse", "commune", "date_creation"])
