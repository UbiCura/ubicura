"""Sections des rapports nationaux tirées des bases ajoutées le 7 octobre 2026, évolution de l'offre depuis 2016
(DREES et INSEE), affections de longue durée (Assurance Maladie) et allocations de la CAF. Même format que
pipeline/rapport.py, une phrase de tête chiffrée sans nom de territoire, un tableau, « Comment lire », les limites
avec leurs sources, puis « Pour aller plus loin »."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config, limites
from .lecture import minuscule, nombre, pct, phrase_correlations

SM, SANTE = config.SANTE_MENTALE, config.SANTE
EVOLUTION_FAMILLE = {SM: ["psychiatre"],
                     SANTE: ["medecin_generaliste", "pediatre", "gynecologue", "ophtalmologue", "sage_femme",
                             "chirurgien_dentiste", "masseur_kinesitherapeute", "pharmacien"]}


def _tableau(df, colonnes, entetes, fmt=None):
    from .rapport import _tableau as t
    return t(df, colonnes, entetes, fmt)


def _comment_lire(*phrases):
    from .rapport import _comment_lire as c
    return c(*phrases)


def _plus_loin(lignes):
    from .rapport import _plus_loin as p
    return p(lignes)


def _signe(v, d=1):
    return ("+" if v > 0 else "") + nombre(v * 100, d) + " %"


def _a_evolue(v, d=1):
    """« a augmenté de 3,2 % », « a baissé de 33,8 % », pour une évolution relative."""
    if round(v * 100, d) == 0:
        return "est restée stable"
    return ("a augmenté de " if v > 0 else "a baissé de ") + nombre(abs(v) * 100, d) + " %"


def _une_evolution(v, d=1):
    """« une hausse de 3,2 % », « une baisse de 33,8 % »."""
    if round(v * 100, d) == 0:
        return "une densité stable"
    return ("une hausse de " if v > 0 else "une baisse de ") + nombre(abs(v) * 100, d) + " %"


def phrase_evolution(C, prof):
    """Une phrase d'« En bref » sur l'évolution de la densité d'une profession, sans nom de territoire."""
    ev = C.R.get("evolution_offre_resume")
    if not isinstance(ev, pd.DataFrame) or ev.empty or prof not in set(ev["prof"]):
        return ""
    fr = ev[(ev["niveau"] == "FR") & (ev["prof"] == prof)].iloc[0]
    dep = ev[(ev["niveau"] == "dep") & (ev["prof"] == prof)]["evolution_densite"].dropna()
    return (f"D'après les séries de la DREES, de {int(fr['annee_debut'])} à {int(fr['annee_fin'])}, la densité de "
            f"{fr['libelle'].split(',')[0].lower()} {_a_evolue(fr['evolution_densite'])} en France, et elle a "
            f"baissé dans {int((dep < 0).sum())} départements sur {len(dep)}.")


def evolution(C, famille):
    """Évolution de la densité de professionnels depuis 2016, France et départements."""
    ev = C.R.get("evolution_offre_resume")
    if not isinstance(ev, pd.DataFrame) or ev.empty:
        return []
    profs = [p for p in EVOLUTION_FAMILLE[famille] if p in set(ev["prof"])]
    if not profs:
        return []
    lignes = []
    for p in profs:
        fr = ev[(ev["niveau"] == "FR") & (ev["prof"] == p)].iloc[0]
        dep = ev[(ev["niveau"] == "dep") & (ev["prof"] == p)]["evolution_densite"].dropna()
        lignes.append({"libelle": fr["libelle"], "periode": f"{int(fr['annee_debut'])} à {int(fr['annee_fin'])}",
                       "debut": fr["densite_debut"], "fin": fr["densite_fin"], "evolution": fr["evolution_densite"],
                       "baisse": f"{int((dep < 0).sum())} sur {len(dep)}", "mediane": dep.median(),
                       "n_baisse": int((dep < 0).sum()), "n": len(dep)})
    T = pd.DataFrame(lignes)
    r = T.iloc[0]
    tete = (f"D'après les séries de la DREES, de {r['periode']}, la densité de {r['libelle'].split(',')[0].lower()} est passée de "
            f"{nombre(r['debut'], 2)} à {nombre(r['fin'], 2)} pour 10 000 habitants en France ({_signe(r['evolution'])}). "
            f"Elle a baissé dans {r['n_baisse']} départements sur {r['n']}.")
    if famille == SANTE:
        bas = T[T["evolution"] < 0]
        tete = (f"D'après les séries de la DREES, entre 2016 et 2026, la densité baisse en France pour {len(bas)} des {len(T)} professions suivies "
                f"ici, et augmente pour les autres. Pour les médecins généralistes, elle passe de "
                f"{nombre(T.iloc[0]['debut'], 1)} à {nombre(T.iloc[0]['fin'], 1)} pour 10 000 habitants "
                f"({_signe(T.iloc[0]['evolution'])}) et baisse dans {T.iloc[0]['n_baisse']} départements sur "
                f"{T.iloc[0]['n']}.") if T.iloc[0]["libelle"].startswith("Médecins généralistes") else tete
    L = ["### Évolution depuis 2016", "", tete, "",
         _tableau(T, ["libelle", "periode", "debut", "fin", "evolution", "mediane", "baisse"],
                  ["Profession", "Période", "Densité au début (DREES)", "Densité à la fin (DREES)", "Évolution en France",
                   "Évolution médiane des départements", "Départements en baisse"],
                  {"debut": lambda v: nombre(v, 2), "fin": lambda v: nombre(v, 2), "evolution": _signe,
                   "mediane": _signe}), ""]
    L += _comment_lire(
        "La densité rapporte le nombre de professionnels au 1er janvier à la population au 1er janvier de la même "
        "année. Une densité peut baisser alors que le nombre de professionnels augmente, si la population augmente "
        "plus vite.",
        "Les psychologues, les orthophonistes et les autres professions inscrites au répertoire ADELI ne figurent "
        "pas ici, leur série change de source en 2024."
        + (" Les masseurs-kinésithérapeutes ne sont suivis que depuis 2017, année de leur inscription au RPPS."
           if famille == SANTE else ""),
        limites.phrase_md(["evol:"]))
    L += _plus_loin(["Sources, DREES, la démographie des professionnels de santé depuis 2012 (séries tirées du RPPS, "
                     "Licence Ouverte), et INSEE, estimations localisées de population au 1er janvier (provisoires "
                     "pour les trois dernières années). Les régions sont la somme de leurs départements. Valeurs "
                     "année par année dans evolution_offre.csv, résumé par territoire dans evolution_offre_resume.csv."])
    return L


def ald(C, famille):
    """Affections de longue durée retenues pour la famille, par département."""
    a = C.externes.get("ald")
    if not a:
        return []
    t = a["table"]
    noms = C.ref.deps.set_index("code")["nom"]
    lignes = []
    for d in [d for d in a["defs"] if d["famille"] == famille]:
        num = int(d["id"].split("_")[1])
        x = t[(t["ald"] == num) & (t["code"] != "976")]
        s = x.set_index("code")["taux_standardise"].dropna()
        if s.empty:
            continue
        lignes.append({"libelle": re.sub(r" \(ALD \d+\)$", "", d["libelle"]), "num": num,
                       "personnes": x["effectif"].sum(), "mediane": s.median(),
                       "min": f"{nombre(s.min())} ({noms.get(s.idxmin(), s.idxmin())})",
                       "max": f"{nombre(s.max())} ({noms.get(s.idxmax(), s.idxmax())})",
                       "rapport": s.max() / s.min() if s.min() > 0 else None})
    if not lignes:
        return []
    T = pd.DataFrame(lignes)
    r = T.iloc[0]
    annee = a["defs"][0].get("annee", "")
    titre = ("#### Affections psychiatriques de longue durée et démences" if famille == SM
             else "### Maladies chroniques reconnues en affection de longue durée")
    tete = (f"En {annee}, {nombre(r['personnes'])} personnes du régime général sont reconnues en affection de longue "
            f"durée n° {r['num']} ({minuscule(r['libelle'])}). À âge égal, le taux du département le plus "
            f"haut vaut {nombre(r['rapport'], 1)} fois celui du plus bas.")
    L = [titre, "", tete, "",
         _tableau(T, ["libelle", "num", "personnes", "mediane", "min", "max"],
                  ["Affection", "N° d'ALD", "Personnes en France", "Médiane des départements, pour 100 000",
                   "Département le plus bas", "Département le plus haut"],
                  {"personnes": nombre, "mediane": nombre, "num": lambda v: str(int(v))}), ""]
    L += _comment_lire(
        "Le taux compte les personnes en affection de longue durée pour 100 000 personnes protégées, à âge égal "
        "(taux standardisé), pour qu'un département âgé ne paraisse pas plus touché du seul fait de son âge. Une "
        "personne peut avoir plusieurs affections, les lignes ne s'additionnent pas.",
        limites.phrase_md(["ald_23"]))
    if famille == SM:
        L += _lien_offre(C, "ald_23", ["psychiatre", "psychologue"], "dep")
    L += _plus_loin([f"Source, Assurance Maladie, bénéficiaires du dispositif des affections de longue durée, "
                     f"répartition par département, {annee}, Licence Ouverte. Les 30 affections, en effectifs et en "
                     f"taux, sont dans ald_departements.csv. Mayotte, dont les données ne sont pas exhaustives, n'est "
                     f"pas retenue dans les valeurs extrêmes."])
    return L


def _lien_offre(C, var, profs, niv):
    """Phrases de corrélation entre un indicateur et l'offre, l'incertitude dite simplement."""
    cc = C.R.get("correlations_contexte")
    if not isinstance(cc, pd.DataFrame) or cc.empty:
        return []
    f = cc[(cc["niveau"] == niv) & (cc["mode"] == "all") & (cc["variable"] == var) & cc["prof"].isin(profs)]
    lab = {d["id"]: d["libelle"] for k in ("ald", "caf") for d in (C.externes.get(k) or {}).get("defs", [])}
    items = []
    for p in profs:
        x = f[f["prof"] == p]
        if len(x):
            r = x.iloc[0]
            ic = (float(r["ic95_bas"]), float(r["ic95_haut"])) if pd.notna(r.get("ic95_bas")) else None
            items.append((C.lab[p], float(r["rho_spearman"]), ic))
    if not items:
        return []
    ph = phrase_correlations(items, lab.get(var, var))
    return [ph + (" Quand un lien apparaît, il peut aller dans les deux sens et ne dit rien d'une cause."
                  if not ph.startswith("Aucun") else ""), ""]


def allocations(C, famille):
    """Allocations de la CAF liées au handicap et à la précarité, par intercommunalité."""
    c = C.externes.get("caf")
    if not c or famille != SM:
        return []
    t = c["table"]
    lignes = []
    for d in c["defs"]:
        x = t[(t["niveau"] == "epci") & (t["indicateur"] == d["id"])].dropna(subset=["valeur"])
        x = x[x["code"].isin(C.ref.epci["code"])]
        dep = t[(t["niveau"] == "dep") & (t["indicateur"] == d["id"])]
        if x.empty:
            continue
        fr = dep["effectif"].sum() / dep["population"].sum() * (100 if d["unite"] == "%" else 1000)
        lignes.append({"libelle": d["libelle"], "unite": d["unite"], "effectif": dep["effectif"].sum(), "france": fr,
                       "q1": x["valeur"].quantile(.1), "q9": x["valeur"].quantile(.9)})
    if not lignes:
        return []
    T = pd.DataFrame(lignes)
    mois = c["defs"][0].get("annee", "")
    e = T.set_index("libelle")
    aah = e.loc["Bénéficiaires de l'AAH"] if "Bénéficiaires de l'AAH" in e.index else None
    tete = (f"En décembre {mois}, la CAF verse l'AAH, l'allocation pour les adultes en situation de handicap, à {nombre(aah['effectif'])} "
            f"personnes, soit {nombre(aah['france'], 1)} pour 1 000 habitants. Entre intercommunalités, ce taux va de "
            f"{nombre(aah['q1'], 1)} à {nombre(aah['q9'], 1)} pour 1 000 si l'on écarte les 10 % les plus bas et les "
            f"10 % les plus hauts.") if aah is not None else ""
    f1 = lambda v: nombre(v, 1)  # noqa: E731
    L = ["#### Handicap et précarité, allocations de la CAF", "", tete, "",
         _tableau(T, ["libelle", "unite", "effectif", "france", "q1", "q9"],
                  ["Indicateur", "Unité", "Effectif en France", "France", "Intercommunalités, 1er décile",
                   "Intercommunalités, 9e décile"], {"effectif": nombre, "france": f1, "q1": f1, "q9": f1}), ""]
    L += _comment_lire(
        "Ces allocations signalent un handicap reconnu (AAH pour les adultes, AEEH pour les enfants) ou une "
        "situation de pauvreté (RSA). Elles ne mesurent pas un besoin de soins et ne servent pas au calcul de "
        "l'effectif attendu. Les déciles montrent l'écart entre territoires sans désigner les extrêmes, souvent "
        "de petite taille.",
        limites.phrase_md(["caf_aah"]))
    L += _lien_offre(C, "caf_aah", ["psychiatre", "psychologue"], "epci")
    L += _plus_loin([f"Source, CAF, allocataires par prestation, par intercommunalité (s_ben_epci_f) et par département "
                     f"(s_ben_dep), décembre {mois}, Licence Ouverte. Effectif rapporté à la population du référentiel. "
                     f"Valeurs par territoire dans allocataires_caf.csv et contexte_*.csv."])
    return L


# ---------------------------------------------------------------- rapports par département et par région
def _nom_niv(T):
    return "départements" if T["niveau"] == "dep" else "régions"


def territoire_phrase_evolution(B, T, prof):
    """Phrase d'« En bref » d'un rapport territorial sur l'évolution de la densité d'une profession."""
    ev = B.R.get("evolution_offre_resume")
    if not isinstance(ev, pd.DataFrame) or ev.empty:
        return ""
    x = ev[(ev["prof"] == prof) & (ev["niveau"] == T["niveau"]) & (ev["code"] == T["code"])]
    fr = ev[(ev["prof"] == prof) & (ev["niveau"] == "FR")]
    if x.empty or fr.empty or pd.isna(x.iloc[0]["evolution_densite"]):
        return ""
    x, fr = x.iloc[0], fr.iloc[0]
    return (f"D'après les séries de la DREES, la densité de {x['libelle'].split(',')[0].lower()} "
            f"{_a_evolue(x['evolution_densite'])} de {int(x['annee_debut'])} à {int(x['annee_fin'])}, contre "
            f"{_une_evolution(fr['evolution_densite'])} en France.")


def territoire_evolution(B, T, famille):
    from .rapport_territoire import _comment_lire as cl, _tableau as tb
    ev = B.R.get("evolution_offre_resume")
    if not isinstance(ev, pd.DataFrame) or ev.empty:
        return []
    lignes = []
    for p in EVOLUTION_FAMILLE[famille]:
        x = ev[(ev["prof"] == p) & (ev["niveau"] == T["niveau"]) & (ev["code"] == T["code"])]
        if x.empty or pd.isna(x.iloc[0]["evolution_densite"]):
            continue
        x = x.iloc[0]
        fr = ev[(ev["prof"] == p) & (ev["niveau"] == "FR")].iloc[0]
        r = {"libelle": x["libelle"], "periode": f"{int(x['annee_debut'])} à {int(x['annee_fin'])}",
             "debut": x["densite_debut"], "fin": x["densite_fin"], "ici": x["evolution_densite"],
             "france": fr["evolution_densite"]}
        if T["niveau"] == "dep" and not T.get("reg_seul"):
            rg = ev[(ev["prof"] == p) & (ev["niveau"] == "reg") & (ev["code"] == T["reg"])]
            r["region"] = rg.iloc[0]["evolution_densite"] if len(rg) else None
        lignes.append(r)
    if not lignes:
        return []
    d = pd.DataFrame(lignes)
    avec_reg = "region" in d and d["region"].notna().any()
    cols = ["libelle", "periode", "debut", "fin", "ici"] + (["region"] if avec_reg else []) + ["france"]
    ents = ["Profession", "Période", "Densité au début (DREES)", "Densité à la fin (DREES)", "Évolution ici"] + (
        ["Évolution de la région"] if avec_reg else []) + ["Évolution en France"]
    f2 = lambda v: nombre(v, 2)  # noqa: E731
    L = ["## Évolution depuis 2016", "",
         tb(d, cols, ents, {"debut": f2, "fin": f2, "ici": _signe, "region": _signe, "france": _signe}), ""]
    L += cl("Professionnels pour 10 000 habitants au 1er janvier, d'après les séries de la DREES. Ces densités "
            "peuvent différer de celles du début du rapport, qui comptent une personne dans chaque département où elle "
            "exerce. Une densité peut baisser alors que le nombre de "
            "professionnels augmente, si la population augmente plus vite. "
            + ("Les psychologues et les autres professions du répertoire ADELI" if famille == SM else
               "Les infirmiers, les orthophonistes, les psychomotriciens et les autres professions du répertoire ADELI")
            + " ne figurent pas ici, leur série change de source en 2024.",
            limites.phrase_md(["evol:"]))
    return L


def territoire_ald(B, T, famille):
    """Affections de longue durée, par département seulement (non publiées pour les régions)."""
    from .rapport_territoire import _comment_lire as cl, _tableau as tb
    a = B.insee.get("ald")
    if not a or T["niveau"] != "dep":
        return []
    t = a["table"]
    lignes = []
    for d in [d for d in a["defs"] if d["famille"] == famille]:
        num = int(d["id"].split("_")[1])
        x = t[(t["ald"] == num) & (t["code"] != "976")].set_index("code")["taux_standardise"]
        v = t[(t["ald"] == num) & (t["code"] == T["code"])]
        if v.empty:
            continue
        v = v.iloc[0]
        lignes.append({"libelle": re.sub(r" \(ALD \d+\)$", "", d["libelle"]), "num": str(num),
                       "effectif": "moins de 10" if v["secret"] else nombre(v["effectif"]),
                       "taux": nombre(v["taux_standardise"]) if pd.notna(v["taux_standardise"]) else "",
                       "milieu": nombre(x.median())})
    if not lignes:
        return []
    titre = "### Affections de longue durée" if famille == SM else "## Maladies chroniques en affection de longue durée"
    L = [titre, "", tb(pd.DataFrame(lignes), ["libelle", "num", "effectif", "taux", "milieu"],
                       ["Affection", "N° d'ALD", "Personnes", "Pour 100 000, à âge égal", "Milieu des départements"]), ""]
    L += cl("Personnes du régime général dont l'affection est reconnue en affection de longue durée, effectifs arrondis "
            "à la dizaine. Le taux est calculé à âge égal pour comparer les départements.",
            limites.phrase_md(["ald_23"], T["code"]))
    return L


def territoire_caf(B, T):
    """Allocations de la CAF, pour le territoire, sa région et le milieu des territoires du même niveau."""
    from .rapport_territoire import _comment_lire as cl, _tableau as tb
    c = B.insee.get("caf")
    if not c:
        return []
    t = c["table"]
    niv, code = T["niveau"], T["code"]
    lignes = []
    for d in c["defs"]:
        x = t[(t["indicateur"] == d["id"]) & (t["niveau"] == niv)].set_index("code")["valeur"]
        x = x[x.index.isin(B.noms[niv].index)]
        if code not in x.index:
            continue
        r = {"libelle": d["libelle"], "unite": d["unite"], "valeur": x[code], "milieu": x.median()}
        if niv == "dep" and not T.get("reg_seul"):
            rg = t[(t["indicateur"] == d["id"]) & (t["niveau"] == "reg") & (t["code"] == T["reg"])]["valeur"]
            r["region"] = rg.iloc[0] if len(rg) else None
        lignes.append(r)
    if not lignes:
        return []
    d = pd.DataFrame(lignes)
    f1 = lambda v: nombre(v, 1)  # noqa: E731
    avec_reg = "region" in d and d["region"].notna().any()
    cols = ["libelle", "unite", "valeur"] + (["region"] if avec_reg else []) + ["milieu"]
    ents = ["Indicateur", "Unité", "Ce territoire"] + (["Région"] if avec_reg else []) + [f"Milieu des {_nom_niv(T)}"]
    L = ["### Handicap et précarité, allocations de la CAF", "",
         tb(d, cols, ents, {"valeur": f1, "region": f1, "milieu": f1}), ""]
    L += cl("Ces allocations signalent un handicap reconnu (AAH, AEEH) ou une situation de pauvreté (RSA). Elles ne "
            "mesurent pas un besoin de soins.", limites.phrase_md(["caf_aah"], code if niv == "dep" else None))
    return L


# ---------------------------------------------------------------- indicateurs entre eux, régressions multiples
def indicateurs_entre_eux(C, ctxlab):
    """Indicateurs de santé mentale et de vulnérabilité croisés entre eux, par département, et régressions multiples."""
    t, r = C.R.get("croisements_indicateurs"), C.R.get("regressions_indicateurs")
    if not isinstance(t, pd.DataFrame) or t.empty:
        return []
    lab = lambda v: ctxlab.get(v, v)  # noqa: E731
    nets = t[(t["ic95_bas"] > 0) | (t["ic95_haut"] < 0)].copy()
    nets["force"] = nets["rho"].abs()
    top = nets.sort_values("force", ascending=False).head(12).assign(
        a=lambda d: d["variable_a"].map(lab), b=lambda d: d["variable_b"].map(lab),
        ic=lambda d: [f"de {nombre(x, 2)} à {nombre(y, 2)}" for x, y in zip(d["ic95_bas"], d["ic95_haut"])])
    L = ["#### Besoins, recours aux soins et conditions de vie, croisés entre eux", "",
         INTRO_ENTRE_EUX, "",
         f"Entre départements, {len(nets)} des {len(t)} paires de ces indicateurs ont un lien net, c'est-à-dire une "
         f"fourchette plausible qui exclut zéro. Le tableau donne les plus forts.", "",
         _tableau(top, ["a", "b", "rho", "ic", "rho_sans_ile_de_france"],
                  ["Indicateur", "Indicateur", "Corrélation de rang", "Fourchette plausible", "Sans l'Île-de-France"],
                  {"rho": lambda v: nombre(v, 2), "rho_sans_ile_de_france": lambda v: nombre(v, 2)}), ""]
    L += _comment_lire(
        "Une corrélation proche de 1 signifie que les deux indicateurs classent les départements de la même façon, "
        "proche de -1 qu'ils les classent en sens inverse. Deux indicateurs liés ne mesurent pas forcément la même chose, "
        "et le lien ne dit pas que l'un cause l'autre.")
    if isinstance(r, pd.DataFrame) and not r.empty:
        L += _regressions(r, lab)
    L += _plus_loin(["Corrélation de rang de Spearman, intervalle de confiance à 95 % par bootstrap, correction de "
                     "Benjamini-Hochberg sur l'ensemble des paires. Toutes les paires dans croisements_indicateurs.csv "
                     "(celles qui comprennent un indicateur de l'Assurance Maladie dans croisements_indicateurs_odbl.csv), "
                     "régressions dans regressions_indicateurs.csv. Régression linéaire sur variables centrées et réduites, "
                     "erreurs standard robustes (HC3), départements de l'Hexagone, facteurs d'inflation de la variance "
                     "tous inférieurs à 5. Mayotte est écartée de tous les croisements entre départements, sa population "
                     "de référence étant incertaine faute de recensement exhaustif."])
    return L


INTRO_ENTRE_EUX = (
    "Ces croisements réunissent, par département, des indicateurs déjà présentés dans ce rapport, de trois sortes. "
    "Des indicateurs liés à la santé mentale (décès par suicide, gestes auto-infligés, personnes prises en charge pour "
    "un trouble psychique, affections psychiatriques de longue durée, traitements antidépresseurs). Des situations "
    "suivies par les services publics (aide sociale à l'enfance, allocations liées au handicap, RSA). Des conditions "
    "de vie connues pour peser sur la santé mentale (pauvreté, chômage, isolement, diplôme, logement, âge). La maladie "
    "d'Alzheimer et la densité de population servent de points de repère. Aucun de ces indicateurs ne mesure à lui "
    "seul la santé mentale d'une population, et ce regroupement est celui de ce rapport, pas une nomenclature "
    "officielle.")

NOMS_RESULTATS = {"suicides": "le taux de décès par suicide",
                  "hospit_gestes_auto_infliges": "le taux d'hospitalisation pour geste auto-infligé",
                  "ald_23": "le taux de personnes en affection psychiatrique de longue durée"}


def _net(lo, hi):
    return lo > 0 or hi < 0


def _compensations(g, lab):
    """Un lien net qui n'existe qu'à autres indicateurs égaux, faible ou de sens contraire pris seul, et qui disparaît
    sans un autre indicateur, est un effet de compensation entre deux indicateurs liés. Il est dit en clair, en une
    seule phrase quand les deux indicateurs dépendent l'un de l'autre."""
    if "depend_de" not in g:
        return []
    flag = {}
    for _, x in g.iterrows():
        if x["net"] != "oui" or pd.isna(x["coef_sans_depend_de"]) or not isinstance(x["depend_de"], str):
            continue
        b, rho, sans = x["coef_standardise"], x["rho_simple"], x["coef_sans_depend_de"]
        if (abs(rho) < .2 or np.sign(rho) != np.sign(b)) and abs(sans) < abs(b) / 2:
            flag[x["variable"]] = (x["depend_de"], rho, sans)
    L, vus = [], set()
    for v, (w, rho, sans) in flag.items():
        if v in vus:
            continue
        nv, nw = minuscule(lab(v)), minuscule(lab(w))
        if w in flag and flag[w][0] == v:
            vus |= {v, w}
            L += [f"Les liens avec « {nv} » et « {nw} » n'apparaissent qu'ensemble. Pris seuls, ils sont faibles "
                  f"(rho = {nombre(rho, 2)} et {nombre(flag[w][1], 2)}). Ces deux indicateurs vont souvent de pair, "
                  f"et le modèle compare des départements où l'un est plus élevé que ne le laisserait attendre "
                  f"l'autre. Aucun des deux ne doit être lu comme un effet propre.", ""]
        else:
            vus.add(v)
            L += [f"Le lien avec « {nv} » n'apparaît qu'à autres indicateurs égaux. Pris seul, il est faible"
                  + (" et de sens contraire" if np.sign(rho) != np.sign(g.set_index("variable").at[v, "coef_standardise"])
                     else "")
                  + f" (rho = {nombre(rho, 2)}). Cet indicateur va souvent de pair avec « {nw} », et sans ce dernier "
                  f"le coefficient tombe à {nombre(sans, 2)}. Le modèle compare donc des départements où « {nv} » est "
                  f"plus élevé ou plus bas que ne le laisserait attendre « {nw} ». Ce lien ne doit pas être lu comme "
                  f"un effet propre de « {nv} ».", ""]
    return L


def _regressions(r, lab):
    h = r[r["champ"] == "hexagone"]
    L = []
    for res, g in h.groupby("resultat", sort=False):
        g = g.assign(v=g["variable"].map(lab),
                     ic=[f"de {nombre(x, 2)} à {nombre(y, 2)}" for x, y in zip(g["ic95_bas"], g["ic95_haut"])],
                     net=["oui" if _net(x, y) else "non" for x, y in zip(g["ic95_bas"], g["ic95_haut"])])
        plus = [minuscule(lab(v)) for v, x in zip(g["variable"], g["ic95_bas"]) if x > 0]
        moins = [minuscule(lab(v)) for v, y in zip(g["variable"], g["ic95_haut"]) if y < 0]
        nom = NOMS_RESULTATS.get(res, lab(res))
        if plus or moins:
            morceaux = []
            def valeurs(xs):
                q = [f"« {x} »" for x in xs]
                q = q[0] if len(q) == 1 else ", ".join(q[:-1]) + " et " + q[-1]
                return ("la valeur de " + q + " est plus haute") if len(xs) == 1 else ("les valeurs de " + q + " sont plus hautes")
            if plus:
                morceaux.append("plus élevé dans les départements où " + valeurs(plus))
            if moins:
                morceaux.append("plus bas dans ceux où " + valeurs(moins))
            phrase = f"À autres indicateurs égaux, {nom} est " + ", et ".join(morceaux) + "."
        else:
            phrase = f"À autres indicateurs égaux, aucun de ces indicateurs n'est nettement lié à {nom}."
        phrase += f" Ensemble, ils résument {pct(g['r2'].iloc[0], 0)} des écarts entre départements."
        cols = ["v", "coef_standardise", "ic", "net"]
        ents = ["Indicateur", "Coefficient standardisé", "Fourchette plausible", "Lien net"]
        if "rho_simple" in g:
            cols.insert(1, "rho_simple")
            ents.insert(1, "Lien simple (rho)")
        L += [f"**Ce qui accompagne {nom}, à autres indicateurs égaux**", "", phrase, "",
              _tableau(g, cols, ents, {"coef_standardise": lambda v: ("+" if v > 0 else "") + nombre(v, 2),
                                       "rho_simple": lambda v: nombre(v, 2)}), ""]
        L += _compensations(g, lab)
        if res == "suicides":
            s = r[(r["champ"] != "hexagone") & (r["resultat"] == res)].set_index("variable")
            perdus = [minuscule(lab(v)) for v, n in zip(g["variable"], g["net"])
                      if n == "oui" and v in s.index and not _net(s.at[v, "ic95_bas"], s.at[v, "ic95_haut"])]
            L += [("Sans les départements d'Île-de-France, où les suicides sont sous-déclarés, "
                   + (f"le lien avec {' et '.join('« ' + x + ' »' for x in perdus)} n'est plus net, il est à lire avec "
                      f"prudence." if perdus else "les mêmes liens restent nets.")), ""]
    L += _comment_lire(
        "Le coefficient standardisé dit de combien d'écarts-types l'indicateur étudié varie quand un autre indicateur "
        "augmente d'un écart-type, les autres restant égaux. Il peut différer du lien simple entre deux indicateurs, "
        "donné à côté, car il retire ce que les autres indicateurs expliquent déjà. Quand deux indicateurs liés entre eux "
        "agissent en sens opposé, l'un peut sembler sans lien pris seul et lié une fois l'autre pris en compte. Un lien "
        "net a une fourchette qui exclut zéro.",
        "Ces modèles portent sur les 96 départements de l'Hexagone, l'outre-mer ayant un profil trop différent pour être "
        "décrit par les mêmes relations. Ils décrivent des départements, pas des personnes, et ne disent rien d'une "
        "cause. Les limites de ces indicateurs (sous-déclaration des suicides, reconnaissance des affections de longue "
        "durée) sont rappelées plus haut, avec leurs sources.")
    return L


def profil_egal(C):
    """Pour les chercheurs, effet de chaque caractéristique de la population sur l'effectif de professionnels, à autres
    caractéristiques égales (modèle de l'effectif attendu)."""
    co = C.R.get("modeles_coefficients")
    if not isinstance(co, pd.DataFrame) or co.empty or "ic95_bas" not in co:
        return []
    from .indicateurs import liste
    from .lecture import pluriel
    lab = {d["id"]: d["label"] for d in liste(C.externes)}
    L = ["### À profil égal, ce qui accompagne la présence des professionnels", "",
         "Le modèle de l'effectif attendu décrit le nombre de professionnels de chaque intercommunalité selon le profil de "
         "sa population. Ses coefficients disent, à autres caractéristiques égales, de combien l'effectif varie quand une "
         "caractéristique augmente d'un écart-type.", ""]
    for p in ["psychologue", "psychiatre", "medecin_generaliste"]:
        g = co[(co["prof"] == p) & (co["variable"] != "constante")]
        if g.empty:
            continue
        g = g.assign(v=g["variable"].map(lambda v: lab.get(v, v)),
                     effet=[("+" if x >= 1 else "") + nombre((x - 1) * 100, 0) + " %" for x in g["rapport_de_taux"]],
                     ic=[f"de {nombre((a - 1) * 100, 0)} à {nombre((b - 1) * 100, 0)} %" for a, b in zip(g["ic95_bas"], g["ic95_haut"])],
                     net=["oui" if (a > 1 or b < 1) else "non" for a, b in zip(g["ic95_bas"], g["ic95_haut"])])
        L += [f"**{pluriel(C.lab.get(p, p)).capitalize()}**", "", _tableau(g, ["v", "effet", "ic", "net"],
              ["Caractéristique (un écart-type de plus)", "Effectif", "Fourchette plausible", "Lien net"]), ""]
    L += _comment_lire(
        "Par exemple, « +20 % » signifie qu'à autres caractéristiques égales, une intercommunalité dont cette "
        "caractéristique est plus élevée d'un écart-type compte en moyenne 20 % de professionnels de plus. La densité de "
        "population est prise en logarithme. Ces chiffres décrivent des territoires et ne disent rien d'une cause.")
    L += _plus_loin(["Régression de Poisson avec la population en terme de décalage, erreurs standard robustes (sandwich), "
                     "variables centrées et réduites, intervalles à 95 %, correction de Benjamini-Hochberg par profession. "
                     "Un modèle binomial négatif sert de contrôle (modeles_qualite.csv)."])
    return L


# ---------------------------------------------------------------- offre et besoin sur une même carte (audit 4.2, 2.5)
def cap_(t):
    return t[:1].upper() + t[1:]


def offre_besoin_carte(C, insee, ctxlab, prof="psychiatre", var="suicides"):
    """Carte bivariée des départements (tiers de l'offre et de l'indicateur) et Moran local bivarié."""
    from .analyses import tables
    from .graphiques import classes_bivariees
    from .rapport import graphique
    ctx = (insee or {}).get("contexte") or {}
    if "dep" not in ctx or var not in ctx["dep"]:
        return []
    _n, d, _pop = tables(C.agg, C.ref, "dep", "all")
    if prof not in d:
        return []
    cl = classes_bivariees(d[prof], ctx["dep"][var].reindex(d.index))
    nom_p, nom_v = minuscule(C.lab[prof]) + "s", minuscule(ctxlab.get(var, var))
    vig, inv = int((cl == 2).sum()), int((cl == 6).sum())
    L = ["#### Offre et indicateur sur une même carte", "",
         f"{vig} départements ont à la fois "
         + NOMS_RESULTATS.get(var, f"un indicateur « {nom_v} »").replace("le taux", "un taux", 1) + " dans le tiers le plus haut et une densité de "
         f"{nom_p} dans le tiers le plus bas. {inv} sont dans la situation inverse.", "", *graphique("bivariee_sm")]
    t = C.R.get("offre_besoin_lisa")
    zones = ""
    if isinstance(t, pd.DataFrame) and len(t):
        x = t[(t["prof"] == prof) & (t["variable"] == var)]
        hl = x[x["zone"] == "HL"]
        hh = int((x["zone"] == "HH").sum())
        zones = (" Aucun département ne forme, au-delà du hasard, une zone où un indicateur élevé est entouré d'une "
                 "offre faible ou élevée." if not len(hl) and not hh else
                 f" Au-delà du hasard, {len(hl)} département{'s' if len(hl) > 1 else ''} "
                 f"{'ont' if len(hl) > 1 else 'a'} un indicateur élevé entouré de départements où l'offre est faible, "
                 f"{hh} un indicateur élevé entouré d'une offre élevée.")
        L += [zones.strip(), ""]
        if len(hl):
            noms = C.ref.deps.set_index("code")["nom"]
            h = hl.assign(nom=hl["code"].map(noms), ind=hl["code"].map(ctx["dep"][var]), dens=hl["code"].map(d[prof]))
            L += ["Départements où un indicateur élevé est entouré d'une offre faible, au-delà du hasard", "",
                  _tableau(h.sort_values("nom"), ["nom", "ind", "dens"],
                           ["Département", cap_(ctxlab.get(var, var)), f"{cap_(nom_p)} pour 10 000 habitants"],
                           {"ind": lambda v: nombre(v, 1), "dens": lambda v: nombre(v, 2)}), ""]
    L += _comment_lire(
        "Chaque département reçoit une couleur selon deux tiers à la fois. En allant vers le bleu, l'offre est plus "
        "dense. En allant vers le rouge, l'indicateur est plus élevé. Le rouge pur signale un indicateur dans le tiers le plus "
        "haut et une offre dans le tiers le plus bas. Les tiers comparent les départements entre eux et ne disent "
        "pas ce qui serait un bon niveau. Un indicateur de santé mentale mesure un besoin ou un recours, jamais les deux "
        "à la fois. Un rond ocre marqué « ! » signale une donnée fragile, les départements d'Île-de-France pour le "
        "suicide et Mayotte, écartée des tiers.", limites.phrase_md(["suicides", "mayotte"]))
    L += _plus_loin(["Tiers calculés sur les départements, Mayotte écartée. Moran local bivarié, indicateur du "
                     "département rapproché de la densité moyenne de ses voisins (densité en logarithme, poids égaux "
                     "entre voisins), 999 permutations conditionnelles, correction de Benjamini-Hochberg pour chaque "
                     "paire profession et indicateur, seuil 5 %. Toutes les paires dans offre_besoin_lisa.csv."])
    return L


# ---------------------------------------------------------------- lien avec le niveau de vie selon les régions (2.6)
def gwr_section(C, prof="psychologue"):
    """Régression géographiquement pondérée, coefficient local du niveau de vie."""
    from .rapport import graphique
    r = C.R.get("gwr_resume")
    if not isinstance(r, pd.DataFrame) or prof not in set(r["prof"]):
        return []
    x = r.set_index("prof").loc[prof]
    pl = minuscule(C.lab[prof]) + "s"
    varie = x["p_variation_niveau_de_vie"] < .05
    pos, neg = x["part_positif_net"], x["part_negatif_net"]
    detail = (f"Le lien est nettement négatif dans {pct(neg)} des intercommunalités, où les territoires plus aisés "
              f"comptent moins de professionnels. Il n'est nettement positif nulle part, et ailleurs aucun lien net "
              f"n'apparaît." if pos == 0 and neg > 0 else
              f"Le lien est nettement positif dans {pct(pos)} des intercommunalités, où les territoires plus aisés "
              f"comptent plus de professionnels. Il n'est nettement négatif nulle part, et ailleurs aucun lien net "
              f"n'apparaît." if neg == 0 and pos > 0 else
              f"Le lien est nettement positif dans {pct(pos)} des intercommunalités et nettement négatif dans "
              f"{pct(neg)}. Ailleurs, aucun lien net n'apparaît." if pos or neg else
              "Le lien n'est net dans aucune intercommunalité.")
    L = ["### Le lien avec le niveau de vie, d'une région à l'autre", "",
         f"À densité de population égale, le lien entre le niveau de vie et la densité de {pl} "
         + ("varie d'une région à l'autre plus que le hasard ne le ferait. " if varie else
            "ne varie pas d'une région à l'autre plus que le hasard ne le ferait. ")
         + detail, "", *graphique("gwr_sm")]
    L += _comment_lire(
        "Chaque intercommunalité de l'Hexagone reçoit le lien mesuré avec ses voisines les plus proches. Violet, les "
        "territoires plus aisés y ont plutôt plus de professionnels. Ocre, ils en ont plutôt moins. Gris, aucun lien "
        "net. Le lien est mesuré à densité de population égale, pour ne pas confondre niveau de vie et effet ville. "
        "Il décrit des territoires et ne dit rien d'une cause.")
    L += _plus_loin([
        f"Régression géographiquement pondérée (Fotheringham, Brunsdon et Charlton 2002) du logarithme de la densité "
        f"sur le niveau de vie médian et le logarithme de la densité de population, variables centrées et réduites, "
        f"{nombre(int(x['intercommunalites']))} intercommunalités. Noyau bicarré adaptatif à {int(x['voisines'])} voisines, "
        f"choisi par le critère AICc ({nombre(x['aicc_gwr'], 0)} contre {nombre(x['aicc_ols'], 0)} pour la régression "
        f"ordinaire, plus bas est meilleur). Coefficient global {nombre(x['coef_global_niveau_de_vie'], 2)}, coefficients "
        f"locaux de {nombre(x['coef_local_q1'], 2)} à {nombre(x['coef_local_q3'], 2)} pour la moitié centrale. Tests "
        f"locaux au seuil ajusté de da Silva et Fotheringham (2016), |t| > {nombre(x['seuil_t_ajuste'], 2)}. Test de "
        f"variation spatiale par 49 permutations des positions, p = {nombre(x['p_variation_niveau_de_vie'], 2)}. "
        "Toutes les professions présentes dans au moins une intercommunalité sur deux dans gwr_resume.csv et "
        "gwr_coefficients.csv, et dans l'atlas."])
    return L
