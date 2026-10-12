"""Rapports par département et par région (chantier 6), santé mentale et santé séparées, sur le modèle des
rapports nationaux. Chaque rapport compare le territoire à sa région, à la moyenne de son niveau et, pour un département, à
des départements de profil semblable. Il décrit la répartition à l'intérieur du territoire (morceaux
d'intercommunalité pour un département, départements pour une région).

Règles suivies. Aucun nom d'autre territoire dans l'« En bref ». Pas de rang, une position par rapport au
milieu et aux quartiles. Les territoires de niveau inférieur sont nommés dans les tableaux, avec le rappel
que les petits effectifs fluctuent. Les régions qui ne comptent qu'un département (outre-mer) n'ont pas de
rapport régional, leur département en tient lieu.

Tout est calculé à partir des tables déjà produites, sans nouveau téléchargement. Les rapports sont écrits
dans resultats/AAAA-MM-JJ/territoires/, leurs figures dans territoires/graphiques/."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from . import cartes, config, indicateurs, limites, rapport_bases
from .analyses import tables
from .lecture import de, nombre, pct, pluriel, un_pour
from .rapport import (EQ_PHRASE, MENTION_ODBL, PRINCIPALES, SANTE, SM, Contexte, _comment_lire, _liste,
                      _plus_loin, _tableau, graphique, ligne_source)
from .util import JOURNAL, log

CLE = {SM: "sante-mentale", SANTE: "sante"}
COURT = {SM: "sm", SANTE: "sante"}
PROFS = {SM: ["psychologue", "psychiatre", "pedopsychiatre", "psychotherapeute", "q_psychiatrie_enfant",
              "q_addictologie"],
         SANTE: PRINCIPALES[SANTE] + ["geriatre"]}
INTERNE = {SM: ["psychologue", "psychiatre"], SANTE: ["medecin_generaliste", "pediatre"]}
EQUIPEMENTS = {SM: ["psychologue_liberal", "psychiatre_liberal", "psychiatrie_ambulatoire", "etablissement_psychiatrie",
                    "addictions"],
               SANTE: ["generaliste_liberal", "pediatre_liberal", "orthophoniste_liberal", "infirmier_liberal",
                       "psychomotricien_liberal", "urgences"]}
# indicateurs INSEE de base qui définissent les départements de profil semblable (jamais l'offre de soins)
SEMBLABLES = ["densite_pop", "part_0_14", "part_65_79", "part_80p", "revenu_median", "taux_pauvrete", "taux_chomage"]
NB_SEMBLABLES = 5
PIECES_MIN = 3   # en dessous, la répartition interne d'un département est décrite par commune
UNITES = {c[0]: c[2] for c in config.CONTEXTE_VULNERABILITE}
ND_TERRITOIRE = "non publié pour ce territoire"
ND_NIVEAU = {"dep": "non publié pour les départements", "reg": "non publié pour les régions"}
EXPLICATION_ND = ("« Non publié » signifie que le producteur de la donnée ne la diffuse pas, soit pour tout ce niveau "
                  "géographique (indicateur publié seulement par département ou par région), soit pour ce territoire "
                  "(secret statistique, données incomplètes).")


def absent(niv, publie_au_niveau):
    """Mention d'une valeur manquante, selon que l'indicateur existe ou non à ce niveau."""
    return ND_TERRITOIRE if publie_au_niveau else ND_NIVEAU[niv]


def est_nd(v):
    return isinstance(v, str) and v.startswith("non publié")
NIVEAU_NOM = {"dep": "département", "reg": "région"}


def ic_poisson(n, pop, niveau=.95):
    """Intervalle de confiance exact (Garwood) d'une densité pour 10 000 habitants."""
    a = 1 - niveau
    lo = stats.chi2.ppf(a / 2, 2 * n) / 2 if n > 0 else 0.0
    hi = stats.chi2.ppf(1 - a / 2, 2 * n + 2) / 2
    return lo / pop * 1e4, hi / pop * 1e4


def part(x):
    """Pourcentage pour une phrase, « moins de 0,1 % » plutôt que « 0,0 % »."""
    return "moins de 0,1 %" if 0 < x < .0005 else pct(x)


def position(v, valeurs):
    """Position d'une valeur parmi celles des territoires comparés, en mots, sans rang."""
    v_ = np.asarray([x for x in valeurs if pd.notna(x)], float)
    if not len(v_) or v is None or not np.isfinite(v):
        return ""
    q1, me, q3 = np.percentile(v_, [25, 50, 75])
    if v <= q1:
        return "quart le moins doté"
    if v < me:
        return "sous le milieu"
    if v < q3:
        return "au-dessus du milieu"
    return "quart le mieux doté"


def semblables(ctx_dep: pd.DataFrame | None, k=NB_SEMBLABLES) -> dict:
    """Pour chaque département de l'Hexagone, les k départements de l'Hexagone les plus proches sur les
    indicateurs INSEE de base standardisés (distance euclidienne). Les départements d'outre-mer, au profil
    trop différent, n'en ont pas."""
    if ctx_dep is None:
        return {}
    cols = [c for c in SEMBLABLES if c in ctx_dep]
    x = ctx_dep.loc[~ctx_dep.index.isin(config.DEPS_DROM), cols].astype(float).copy()
    if "densite_pop" in x:
        x["densite_pop"] = np.log(x["densite_pop"].clip(lower=1))
    x = x.dropna()
    if len(x) <= k:
        return {}
    z = (x - x.mean()) / x.std(ddof=0)
    d = np.sqrt(((z.to_numpy()[:, None, :] - z.to_numpy()[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    return {c: [x.index[j] for j in np.argsort(d[i])[:k]] for i, c in enumerate(x.index)}


class Base:
    """Tables communes à tous les rapports territoriaux, calculées une seule fois."""

    def __init__(self, agg, ref, professions, insee, R):
        self.C = Contexte(agg, ref, professions, R)
        self.C.externes = insee or {}
        self.agg, self.ref, self.R, self.insee = agg, ref, R, insee or {}
        self.lab = self.C.lab
        self.t = {niv: tables(agg, ref, niv, "all") for niv in ("dep", "reg", "com")}
        self.lib = {niv: tables(agg, ref, niv, "lib")[0] for niv in ("dep", "reg")}
        self.noms = {"dep": ref.deps.set_index("code")["nom"], "reg": ref.regs.set_index("code")["nom"],
                     "com": ref.communes.set_index("code")["nom"]}
        self.dep_reg = ref.deps.set_index("code")["reg"]
        self.ctx = (insee or {}).get("contexte", {}) if insee else {}
        self.ctxlab = indicateurs.libelles(insee)
        self.semblables = semblables(self.ctx.get("dep"))
        # morceaux d'intercommunalité situés dans un département
        com = ref.communes.assign(piece=ref.communes["dep"] + "_" + ref.communes["epci"])
        self.piece_pop = com.groupby("piece")["pop"].sum()
        self.piece_dep = com.groupby("piece")["dep"].first()
        n_dep_epci = com.groupby("epci")["dep"].nunique()
        nom_epci = ref.epci.set_index("code")["nom"]
        self.piece_nom = pd.Series({p: nom_epci.get(p.split("_", 1)[1], p) + (
            ", partie située dans le département" if n_dep_epci.get(p.split("_", 1)[1], 1) > 1 else "")
            for p in self.piece_pop.index})
        e = agg.effectifs.get("piece")
        if e is not None:
            e = e[e["mode"] == "all"].pivot_table(index="code", columns="prof", values="n", aggfunc="sum", fill_value=0)
            self.piece_n = e.reindex(self.piece_pop.index).fillna(0)
        else:
            self.piece_n = pd.DataFrame(index=self.piece_pop.index)
        self.com_dep = ref.communes.set_index("code")["dep"]
        try:
            self.fonds = cartes.fonds(ref)
        except Exception as e:  # noqa: BLE001
            log.warning("fonds de carte des rapports territoriaux indisponibles (%s)", e)
            self.fonds = None
        self._communes, self._minutes = None, None
        cartes.retenir_noms(ref, self.piece_nom.to_dict())

    def communes_dep(self, dep):
        """Contours simplifiés des communes d'un département, chargés une fois pour tous les rapports."""
        if self._communes is None:
            try:
                self._communes = cartes.fonds_communes(self.ref) or {}
            except Exception as e:  # noqa: BLE001
                log.warning("contours des communes indisponibles (%s)", e)
                self._communes = {}
        return self._communes.get(dep, {})

    def minutes_communes(self, equipement):
        """Temps médian par la route de chaque commune vers l'équipement le plus proche (histogramme de l'INSEE)."""
        if self._minutes is None:
            self._minutes = {}
            ar = self.insee.get("acces_route")
            if ar:
                from .analyses import medianes_histogramme
                codes = {d["id"]: d["code"] for d in ar["defs"] if d["id"] in CARTE_TRAJET.values()}
                h = ar["histogramme"]
                h = h[h["typeeq_id"].isin(codes.values())]
                med = medianes_histogramme(h, ["depcom", "typeeq_id"])
                ids = {c: i for i, c in codes.items()}
                for (eq, g) in med.groupby("typeeq_id"):
                    self._minutes[ids[eq]] = dict(zip(g["depcom"], g["temps_median_min"]))
        return self._minutes.get(equipement, {})

    def reference(self, p, niveau):
        """Moyenne des territoires du même niveau, calculée comme eux (rapport.Contexte.moyenne)."""
        return self.C.moyenne(p, niveau)

    def profs(self, famille):
        return [p for p in PROFS[famille] if self.C.present(p) and p in self.t["dep"][1]]


# ---------------------------------------------------------------- sections
def _phrase_densite(B, T, p, avec_parent=True):
    n, d, _pop = B.t[T["niveau"]]
    if p not in n:
        return ""
    x, dx = int(n.at[T["code"], p]), d.at[T["code"], p]
    comp = []
    if avec_parent and T["niveau"] == "dep" and not T.get("reg_seul"):
        comp.append(f"{nombre(B.t['reg'][1].at[T['reg'], p], 1)} dans la région")
    comp.append(f"{nombre(B.reference(p, T['niveau']), 1)} en moyenne dans les "
                f"{'départements' if T['niveau'] == 'dep' else 'régions'}")
    lab = pluriel(B.lab[p]) if x != 1 else B.lab[p].lower()
    return (f"{nombre(x)} {lab} exercent dans {'le département' if T['niveau'] == 'dep' else 'la région'}, soit "
            f"{nombre(dx, 1)} pour 10 000 habitants ({un_pour(dx)}), contre {_liste(comp)}.")


def _sans(B, T, profs):
    """Part de la population du territoire qui vit dans un morceau d'intercommunalité sans aucun des
    professionnels cités."""
    pieces = B.piece_pop.index[B.piece_dep.reindex(B.piece_pop.index).isin(T["deps"])]
    cols = [p for p in profs if p in B.piece_n]
    if not len(pieces) or not cols:
        return np.nan
    zero = (B.piece_n.loc[pieces, cols] == 0).all(axis=1)
    pop = B.piece_pop[pieces]
    return pop[zero].sum() / pop.sum() if pop.sum() else np.nan


def cmp_pieces(B) -> pd.Series:
    """CMP actifs de FINESS par morceau d'intercommunalité situé dans un département (code dep_epci)."""
    c = getattr(B.agg, "cmp", None)
    if not isinstance(c, pd.DataFrame) or c.empty:
        return pd.Series(dtype=float)
    return c.assign(piece=c["dep"] + "_" + c["epci"]).groupby("piece")["cmp"].sum()


def _phrase_cmp(B, T) -> str:
    """Nuance « aucun psychiatre ne déclare exercer » par les CMP de FINESS situés dans ces morceaux."""
    pieces = B.piece_pop.index[B.piece_dep.reindex(B.piece_pop.index).isin(T["deps"])]
    cmp_ = cmp_pieces(B)
    if cmp_.empty or "psychiatre" not in B.piece_n or not len(pieces):
        return ""
    zero = [p for p in pieces if B.piece_n.at[p, "psychiatre"] == 0]
    if not zero:
        return ""
    avec = [p for p in zero if cmp_.get(p, 0) > 0]
    if not avec:
        return ("D'après FINESS, aucune de ces intercommunalités n'accueille de centre médico-psychologique (CMP)."
                if len(zero) > 1 else "D'après FINESS, cette intercommunalité n'accueille pas de centre "
                                      "médico-psychologique (CMP).")
    if len(zero) == 1:
        return ("D'après FINESS, cette intercommunalité accueille pourtant un centre médico-psychologique (CMP) ou "
                "plus, où des psychiatres peuvent consulter sans y être déclarés.")
    return (f"D'après FINESS, {nombre(len(avec))} de ces {nombre(len(zero))} intercommunalités "
            f"{'accueille' if len(avec) == 1 else 'accueillent'} pourtant au "
            f"moins un centre médico-psychologique (CMP), où des psychiatres peuvent consulter sans y être déclarés.")


def _route_valeurs(B, T, famille):
    ta = B.R.get("temps_acces")
    if not isinstance(ta, pd.DataFrame) or ta.empty:
        return None
    t = ta[ta["equipement"].isin(EQUIPEMENTS[famille])]
    x = t[(t["niveau"] == T["niveau"]) & (t["code"] == T["code"])].set_index("equipement")
    return x if len(x) and x["population"].sum() > 0 else None


def _en_bref(B, T, famille):
    P = []
    nom_niv = "le département" if T["niveau"] == "dep" else "la région"
    if famille == SM:
        P.append(_phrase_densite(B, T, "psychologue"))
        ph = _phrase_densite(B, T, "psychiatre")
        if ph:
            pos = position(B.t[T["niveau"]][1].at[T["code"], "psychiatre"], B.t[T["niveau"]][1]["psychiatre"])
            P.append(ph + (f" Pour les psychiatres, {nom_niv} se situe dans le {pos} des "
                           f"{'départements' if T['niveau'] == 'dep' else 'régions'}." if pos.startswith("quart") else
                           f" Pour les psychiatres, {nom_niv} se situe {pos} des "
                           f"{'départements' if T['niveau'] == 'dep' else 'régions'}." if pos else ""))
        s1, s2 = _sans(B, T, ["psychiatre"]), _sans(B, T, ["psychologue", "psychiatre"])
        if np.isfinite(s1):
            fr = pct(B.C.sans("psychiatre"))
            P.append(f"Chaque habitant vit dans une intercommunalité où au moins un psychiatre déclare exercer "
                     f"({fr} des habitants n'en ont aucun dans leur intercommunalité en France)." if s1 == 0 else
                     f"{pct(s1).capitalize()} des habitants vivent dans une intercommunalité où aucun psychiatre ne "
                     f"déclare exercer ({fr} en France)"
                     + (f", et {part(s2)} dans une intercommunalité sans psychologue ni psychiatre." if s2 > 0 else ".")
                     + (" " + _phrase_cmp(B, T) if s1 > 0 and _phrase_cmp(B, T) else ""))
        P.append(rapport_bases.territoire_phrase_evolution(B, T, "psychiatre"))
    else:
        P.append(_phrase_densite(B, T, "medecin_generaliste"))
        P.append(rapport_bases.territoire_phrase_evolution(B, T, "medecin_generaliste"))
        les = "départements" if T["niveau"] == "dep" else "régions"
        morceaux = []
        for i, p in enumerate(["infirmier", "masseur_kinesitherapeute"]):
            d = B.t[T["niveau"]][1]
            if p not in d or pd.isna(d.at[T["code"], p]):
                continue
            pos = position(d.at[T["code"], p], d[p])
            ou = (f"dans le {pos}" if pos.startswith("quart") else pos) if pos else ""
            moy = f"{nombre(B.reference(p, T['niveau']), 1)} en moyenne" + (f" dans les {les}" if i == 0 else "")
            morceaux.append(f"{nombre(d.at[T['code'], p], 1)} {pluriel(B.lab[p])} ({moy}" + (f", {ou})" if ou else ")"))
        if morceaux:
            P.append(f"Pour 10 000 habitants, {nom_niv} compte {_liste(morceaux)}.")
        s = _sans(B, T, ["pediatre"])
        if np.isfinite(s):
            fr = pct(B.C.sans("pediatre"))
            P.append(f"Chaque habitant vit dans une intercommunalité qui compte au moins un pédiatre ({fr} des "
                     f"habitants n'en ont aucun dans leur intercommunalité en France)." if s == 0 else
                     f"{part(s).capitalize()} des habitants vivent dans une intercommunalité sans pédiatre ({fr} en "
                     f"France).")
    x = _route_valeurs(B, T, famille)
    if x is not None:
        e0 = "psychologue_liberal" if famille == SM else "generaliste_liberal"
        e1 = "psychiatre_liberal" if famille == SM else "urgences"
        fr = B.R["temps_acces"]
        fr = fr[fr["niveau"] == "FR"].set_index("equipement")
        if e0 in x.index and e1 in x.index:
            v1 = x.at[e1, "part_population_a_plus_de_20_min"]
            m0 = x.at[e0, "temps_median_min"]
            P.append("Par la route, la moitié des habitants vit à "
                     + ("moins d'une minute" if m0 < 1 else f"moins de {nombre(m0, 0)} minutes") + f" {EQ_PHRASE[e0]}. "
                     + (f"Aucun habitant ne vit à plus de 20 minutes {EQ_PHRASE[e1]}" if v1 == 0 else
                        f"{part(v1).capitalize()} vivent à plus de 20 minutes {EQ_PHRASE[e1]}")
                     + f", contre {pct(fr.at[e1, 'part_population_a_plus_de_20_min'])} en France.")
    if famille == SM:
        am = B.insee.get("ameli")
        if am:
            t = am["table"]
            iid = config.AMELI_INDICATEURS[0][1]
            x = t[(t["niveau"] == T["niveau"]) & (t["indicateur"] == iid)].set_index("code")["prevalence_standardisee_pct"]
            x = x.drop(config.AMELI_DEPARTEMENTS_EXCLUS + config.AMELI_REGIONS_EXCLUES, errors="ignore")
            if T["code"] in x.index and pd.notna(x[T["code"]]):
                P.append(f"À âge égal, {nombre(x[T['code']], 1)} % des assurés sont pris en charge par l'Assurance "
                         f"Maladie pour un trouble psychique. Le milieu des "
                         f"{'départements' if T['niveau'] == 'dep' else 'régions'} se situe à "
                         f"{nombre(x.median(), 1)} %. Cette part mesure le recours aux soins, pas le besoin.")
    if famille == SM and T["niveau"] == "dep":
        v = _odisse(B, "dep").get("suicides")
        if v is not None and T["code"] in v.index and pd.notna(v.at[T["code"], "valeur"]):
            P.append(f"À âge égal, le taux de décès par suicide est de {nombre(v.at[T['code'], 'valeur'], 1)} pour "
                     f"100 000 habitants. Le milieu des départements se situe à {nombre(v['valeur'].median(), 1)}."
                     + (" " + config.LIMITES["suicides"]["territoires"][T["code"]] + " Source, "
                        + limites.sources_md(config.LIMITES["suicides"]) + "."
                        if T["code"] in config.LIMITES["suicides"].get("territoires", {}) else ""))
    return [p for p in P if p]


def _odisse(B, niveau):
    spf = B.insee.get("odisse")
    if not spf:
        return {}
    t = spf["table"]
    out = {}
    for ind in config.ODISSE:
        if ind["niveau"] != niveau:
            continue
        x = t[t["indicateur"] == ind["id"]].set_index("code")
        if len(x):
            out[ind["id"]] = x
    return out


def _professions(B, T, famille, cle_fig):
    niv, code = T["niveau"], T["code"]
    n, d, pop = B.t[niv]
    profs = B.profs(famille)
    sem = B.semblables.get(code, []) if niv == "dep" else []
    lignes, regl, ics = [], [], []
    for p in profs:
        x = int(n.at[code, p])
        r = {"libelle": B.lab[p], "effectif": x, "densite": d.at[code, p], "france": B.reference(p, niv),
             "position": position(d.at[code, p], d[p])}
        if niv == "dep":
            r["region"] = B.t["reg"][1].at[T["reg"], p]
            r["semblables"] = d.loc[sem, p].median() if sem else np.nan
        else:
            r["regions"] = d[p].median()
        lo, hi = ic_poisson(x, pop[code])
        ics.append(f"{B.lab[p]}, de {nombre(lo, 2)} à {nombre(hi, 2)}")
        lignes.append(r)
        if p in PRINCIPALES[famille][:6] or (famille == SM and p in ("psychologue", "psychiatre", "pedopsychiatre")):
            q1, q3 = np.nanpercentile(d[p], [25, 75])
            regl.append({"libelle": B.lab[p], "valeur": d.at[code, p], "reference": B.reference(p, niv), "q1": q1, "q3": q3,
                         "tous": [(c, float(v)) for c, v in d[p].items() if c != code and pd.notna(v)]})
    T_ = pd.DataFrame(lignes)
    if T_.empty:
        return []
    f1 = lambda v: "0" if v == 0 else (nombre(v, 2) if v < 1 else nombre(v, 1))  # noqa: E731
    if niv == "dep":
        cols = ["libelle", "effectif", "densite", "region", "semblables", "france", "position"]
        ents = ["Profession", "Effectif", "Pour 10 000 habitants", "Région", "Départements semblables (milieu)",
                "Moyenne des départements", "Position parmi les départements"]
        if not sem:
            cols.remove("semblables")
            ents.remove("Départements semblables (milieu)")
        if T.get("reg_seul"):
            cols.remove("region")
            ents.remove("Région")
    else:
        cols = ["libelle", "effectif", "densite", "regions", "france", "position"]
        ents = ["Profession", "Effectif", "Pour 10 000 habitants", "Milieu des régions", "Moyenne des régions",
                "Position parmi les régions"]
    titre = "Les professions de santé mentale" if famille == SM else "Les professions de santé"
    L = [f"## {titre}", "",
         _tableau(T_, cols, ents, {"effectif": nombre, "densite": f1, "region": f1, "semblables": f1, "france": f1,
                                   "regions": f1}), ""]
    if regl:
        svg = cartes.halteres(regl, f"Écart à la moyenne des {'départements' if niv == 'dep' else 'régions'}, densité "
                                    f"pour 10 000 habitants en indice (moyenne = 100)")
        if svg:
            (B.dossier_fig / f"{cle_fig}_position.svg").write_text(svg, encoding="utf-8")
            L += graphique(f"{cle_fig}_position")
    moy = ("La moyenne des départements rapporte l'ensemble des professionnels des départements à la population de "
           "la France, comptés comme ici, avec les seules activités de soins qui ont un lieu d'exercice. Elle diffère "
           "un peu du chiffre de la France entière du rapport national, qui compte aussi les remplacements et les "
           "activités sans soins à la population.") if niv == "dep" else (
           "La moyenne des régions rapporte l'ensemble des professionnels des régions à la population de la France, "
           "comptés comme ici, avec les seules activités de soins qui ont un lieu d'exercice.")
    comp = ("Les colonnes suivantes donnent la même densité pour la région, pour le milieu de cinq départements "
            "dont la population ressemble à celle du département, et en moyenne pour les départements. " + moy
            if niv == "dep" and sem else
            "Les colonnes suivantes donnent la même densité pour la région et en moyenne pour les départements. " + moy
            if niv == "dep" else
            "Les colonnes suivantes donnent la valeur du milieu parmi les régions, et la moyenne des régions. " + moy)
    L += _comment_lire(
        "L'effectif compte chaque personne une seule fois, même si elle exerce dans plusieurs communes du "
        "territoire. La densité rapporte cet effectif à la population, pour 10 000 habitants. " + comp,
        "La dernière colonne situe le territoire sans le classer. Les territoires comparés sont partagés en quatre "
        "groupes de même taille, du quart le moins doté au quart le mieux doté. La figure compare chaque densité à "
        "la moyenne (indice 100). Le gros point est le territoire de ce rapport, à gauche pour une densité plus faible, "
        "à droite pour une densité plus forte. Les petits points gris sont les autres territoires comparés, et la "
        "bande claire réunit leur moitié centrale.",
        "Les qualifications des médecins (enfant et adolescent, addictologie) se lisent à côté des spécialités et "
        "ne s'y ajoutent pas." if famille == SM else "",
        "Les activités sans soins à la population (contrôle médical, industrie, recherche, administration, "
        "téléconsultation...) ne sont pas comptées, car elles sont souvent déclarées au siège d'un organisme. Elles "
        "sont décrites plus bas quand elles sont notables.",
        limites.phrase_md((["mayotte"] if code == "976" or "976" in T.get("deps", []) else [])
                          + (["prof:pedopsychiatre"] if famille == SM else [])))
    plus = []
    if sem:
        plus.append("Départements de profil semblable, retenus parce que leur population ressemble à celle du "
                    "département (densité de population, âge, niveau de vie, pauvreté, chômage), sans tenir compte "
                    "de l'offre de soins, " + _liste(f"{B.noms['dep'].get(c, c)} ({c})" for c in sem) + ". Ils "
                    "servent de point de repère et non de norme.")
    elif niv == "dep" and code in config.DEPS_DROM:
        plus.append("Les départements d'outre-mer ont un profil trop différent de celui de l'Hexagone pour qu'on "
                    "leur associe des départements semblables. Ils sont comparés entre eux dans le rapport national.")
    plus.append("Fourchettes à 95 % des densités, qui tiennent compte des petits effectifs (loi de Poisson, "
                "intervalle exact), " + "; ".join(ics) + ". Quand la fourchette est large, une ou deux arrivées "
                "ou départs suffisent à changer nettement la densité.")
    plus += _public_particulier(B, T, famille)
    L += _plus_loin(plus)
    if famille == SM:
        L += _elargi(B, T)
    else:
        L += _specialites(B, T)
    L += _sans_soins(B, T, famille)
    return L


def _specialites(B, T) -> list[str]:
    """Toutes les spécialités médicales du territoire dans un volet replié, rangées par groupe (version 2,
    11 octobre 2026), avec les précisions qui s'imposent (exercice surtout salarié, prévention)."""
    niv, code = T["niveau"], T["code"]
    n, d, _pop = B.t[niv]
    groupe = B.C.prof["groupe"].to_dict()
    lignes, cles = [], []
    for g in config.GROUPES_SPECIALITES:
        ps = [p for p in B.C.ids(SANTE) if groupe.get(p) == g and p in n.columns and B.C.present(p)]
        if not ps:
            continue
        lignes.append(f"| **{g}** | | | | |")
        for p in sorted(ps, key=lambda x: -B.C.nat.get(x, 0)):
            x = int(n.at[code, p])
            ref = B.reference(p, niv)
            lignes.append(f"| {B.lab[p]} | {nombre(x)} | {nombre(d.at[code, p], 2)} | {nombre(ref, 2)} | "
                          f"{position(d.at[code, p], d[p])} |")
            if f"prof:{p}" in config.LIMITES:
                cles.append(f"prof:{p}")
    if not lignes:
        return []
    moy = "Moyenne des départements" if niv == "dep" else "Moyenne des régions"
    corps = ["| Spécialité | Effectif | Pour 10 000 habitants | " + moy + " | Position |", "|---|---|---|---|---|"] + lignes
    return (["<details>", "<summary>Les spécialités médicales, détail par spécialité</summary>", ""] + corps + [""]
            + _comment_lire("Chaque médecin est compté dans la spécialité de son inscription à l'Ordre. Les petits "
                            "effectifs varient beaucoup d'une année à l'autre, une ou deux arrivées suffisent à changer "
                            "la position du territoire. Les spécialités surtout exercées à l'hôpital se trouvent là où "
                            "sont les établissements, les habitants consultent souvent dans un territoire voisin.",
                            limites.phrase_specialites_md(cles))
            + ["</details>", ""])


PARTICULIERES = {SM: ["psychologue", "psychiatre"], SANTE: ["medecin_generaliste", "infirmier"]}


def _particulieres(B, T, categorie):
    ap = B.agg.particulieres
    if not ap or T["niveau"] not in ap:
        return pd.Series(dtype=float)
    x = ap[T["niveau"]]
    return x[(x["code"] == T["code"]) & (x["categorie"] == categorie)].set_index("prof")["n"]


def _sans_soins(B, T, famille):
    """Activités sans soins à la population déclarées dans le territoire, retirées du tableau."""
    x = _particulieres(B, T, "sans_soins")
    n = B.t[T["niveau"]][0]
    parts = [(p, int(x[p])) for p in PARTICULIERES[famille] if p in x.index and x[p] >= 3
             and (p not in n or x[p] >= .02 * max(n.at[T["code"], p], 1))]
    if not parts:
        return []
    lieu = "le département" if T["niveau"] == "dep" else "la région"
    return [f"{_liste(f'{nombre(k)} {pluriel(B.lab[p]) if k > 1 else B.lab[p].lower()}' for p, k in parts).capitalize()} "
            f"déclarent aussi dans {lieu} une activité sans soins à la population (contrôle médical, "
            f"administration, recherche, industrie, téléconsultation...). Ces activités ne sont pas comptées dans le "
            f"tableau, une même personne pouvant y figurer au titre d'une activité de soins.", ""]


def _public_particulier(B, T, famille):
    x = _particulieres(B, T, "public_particulier")
    n = B.t[T["niveau"]][0]
    parts = [f"{nombre(int(x[p]))} {pluriel(B.lab[p]) if x[p] > 1 else B.lab[p].lower()} sur {nombre(n.at[T['code'], p])}"
             for p in PARTICULIERES[famille] if p in x.index and p in n and x[p] > 0]
    if not parts:
        return []
    return ["Parmi les professionnels comptés, certains exercent pour un public particulier (médecine du travail, "
            "santé scolaire, services de l'État, pompiers, hôpitaux militaires...), " + _liste(parts) + ". Ils restent "
            "dans le tableau. Détail dans activites_particulieres_dep.csv et activites_particulieres_reg.csv."]


def _elargi(B, T):
    es = [p for p in B.C.ids(SM, "perimetre_elargi") if p in B.t[T["niveau"]][0]]
    if not es:
        return []
    n, _d, pop = B.t[T["niveau"]]
    tot = n.loc[T["code"], es].sum()
    ref_niv = sum(B.reference(p, T["niveau"]) for p in es)
    return [f"Environ {nombre(tot)} personnes sont salariées d'un établissement psychiatrique ou médico-psychologique "
            f"situé dans {'le département' if T['niveau'] == 'dep' else 'la région'} (CMP, hôpital de jour, "
            f"établissement spécialisé en psychiatrie...), soit {nombre(tot / pop[T['code']] * 1e4, 1)} pour 10 000 "
            f"habitants contre {nombre(ref_niv, 1)} en moyenne dans les "
            f"{'départements' if T['niveau'] == 'dep' else 'régions'}. Ce périmètre élargi se lit à côté "
            f"du tableau et ne s'y ajoute pas.", ""]


def _interne(B, T, famille, cle_fig):
    """Répartition à l'intérieur du territoire."""
    p0, p1 = INTERNE[famille]
    niv, code = T["niveau"], T["code"]
    if niv == "reg":
        deps = T["deps"]
        if len(deps) < 2:
            return []
        n, d, pop = B.t["dep"]
        t = pd.DataFrame({"code": deps, "nom": [B.noms["dep"].get(c, c) for c in deps], "pop": pop.reindex(deps).values})
        for p in (p0, p1):
            t[f"n_{p}"] = n.reindex(deps)[p].values if p in n else 0
        unite, unites, geoms = "département", "départements", (B.fonds or {}).get("dep", {})
        t["etiquette"] = t["code"]
    else:
        pieces = B.piece_pop.index[B.piece_dep.reindex(B.piece_pop.index) == code]
        if len(pieces) >= PIECES_MIN:
            t = pd.DataFrame({"code": pieces, "nom": B.piece_nom.reindex(pieces).values,
                              "pop": B.piece_pop.reindex(pieces).values})
            for p in (p0, p1):
                t[f"n_{p}"] = B.piece_n.reindex(pieces)[p].values if p in B.piece_n else 0
            unite, unites, geoms = "intercommunalité", "intercommunalités", (B.fonds or {}).get("piece", {})
        else:
            n, _d, pop = B.t["com"]
            coms = [c for c in B.com_dep.index[B.com_dep == code] if c in pop.index]
            if len(coms) < 2:
                return ["## Répartition à l'intérieur du département", "",
                        "Le département ne compte qu'une commune et une intercommunalité, la répartition interne "
                        "n'est donc pas détaillée ici.", ""]
            t = pd.DataFrame({"code": coms, "nom": [B.noms["com"].get(c, c) for c in coms], "pop": pop.reindex(coms).values})
            for p in (p0, p1):
                t[f"n_{p}"] = n.reindex(coms)[p].values if p in n else 0
            unite, unites, geoms = "commune", "communes", {}
        t = t.sort_values("pop", ascending=False).reset_index(drop=True)
        t["etiquette"] = (t.index + 1).astype(str)
    t = t[t["pop"] > 0]
    for p in (p0, p1):
        t[f"d_{p}"] = t[f"n_{p}"] / t["pop"] * 1e4
    t["num"] = t["etiquette"]
    titre = f"Répartition à l'intérieur {'du département' if niv == 'dep' else 'de la région'}"
    sans0 = t.loc[t[f"n_{p0}"] == 0, "pop"].sum() / t["pop"].sum()
    sans1 = t.loc[t[f"n_{p1}"] == 0, "pop"].sum() / t["pop"].sum()
    un = "un" if unite == "département" else "une"
    L = [f"## {titre}", "",
         f"Le territoire compte {nombre(len(t))} {unites if len(t) > 1 else unite}. "
         + (_phrase_sans(sans0, sans1, un, unite, B.lab[p0].lower(), B.lab[p1].lower()) if unite != "département" else
            f"Selon les départements, la densité {de(pluriel(B.lab[p0]))} va de {nombre(t[f'd_{p0}'].min(), 1)} à "
            f"{nombre(t[f'd_{p0}'].max(), 1)} pour 10 000 habitants."), ""]
    niv_u = {"intercommunalité": "piece", "commune": "com", "département": "dep"}[unite]
    moy_u = {"intercommunalité": "des intercommunalités", "commune": "des communes", "département": "des départements"}[unite]
    ref_u = B.reference(p0, niv_u)
    cmp_ = cmp_pieces(B) if unite == "intercommunalité" else pd.Series(dtype=float)
    if not cmp_.empty and "psychiatre" in (p0, p1):
        t["cmp"] = t["code"].map(cmp_).fillna(0).astype(int)
    if geoms:
        g = {c: geoms.get(c) for c in t["code"]}
        for k, p in enumerate((p0, p1)):
            ref_p = B.reference(p, niv_u)
            rap_p = (t.set_index("code")[f"d_{p}"] / ref_p).to_dict() if ref_p else {}
            marques = (t.loc[(t[f"n_{p}"] == 0) & (t["cmp"] > 0), "code"].tolist()
                       if p == "psychiatre" and "cmp" in t else [])
            svg = cartes.carte(g, rap_p, dict(zip(t["code"], t["etiquette"])),
                               f"{pluriel(B.lab[p]).capitalize()} pour 10 000 habitants, par {unite}, comparés à la "
                               f"moyenne {moy_u} de France", marques=marques)
            if svg:
                svg = svg.replace("<svg ", f'<svg data-variante="{pluriel(B.lab[p]).capitalize()}" ', 1)
                (B.dossier_fig / (f"{cle_fig}_carte.svg" if k == 0 else f"{cle_fig}_carte__{p}.svg")).write_text(
                    svg, encoding="utf-8")
                if k == 0:
                    L += graphique(f"{cle_fig}_carte")
    f1 = lambda v: nombre(v, 1)  # noqa: E731
    cols = (["num"] if geoms and unite != "département" else []) + ["nom", "pop", f"n_{p0}", f"d_{p0}", f"n_{p1}", f"d_{p1}"]
    ents = (["N°"] if geoms and unite != "département" else []) + [unite.capitalize(), "Habitants", pluriel(B.lab[p0]).capitalize(),
                                                                    "Pour 10 000 hab.", pluriel(B.lab[p1]).capitalize(), "Pour 10 000 hab."]
    if unite == "département":
        cols, ents = ["etiquette"] + cols, ["Code"] + ents
    if "cmp" in t:
        cols, ents = cols + ["cmp"], ents + ["CMP (FINESS)"]
    L += [_tableau(t, cols, ents, {"pop": nombre, f"n_{p0}": nombre, f"n_{p1}": nombre, f"d_{p0}": f1, f"d_{p1}": f1,
                                   "cmp": nombre}), ""]
    L += _comment_lire(
        (f"La carte colore chaque {unite} selon sa densité {de(pluriel(B.lab[p0]))} comparée à la moyenne {moy_u} "
         f"de France ({nombre(ref_u, 1)} pour 10 000 habitants). "
         + ("Les numéros renvoient au tableau, où les territoires sont rangés du plus peuplé au moins peuplé. "
            if unite != "département" else "Les codes renvoient au tableau. ")) if geoms else "",
        f"Un professionnel qui exerce dans plusieurs {unites} compte dans {'chacun' if unite == 'département' else 'chacune'} "
        f"d'{'eux' if unite == 'département' else 'elles'}. Absence ne veut pas dire "
        f"absence d'accès, le professionnel le plus proche peut exercer juste à côté.",
        "Ce tableau décrit une répartition et ne classe pas les territoires. Dans les petits territoires, une ou "
        "deux arrivées ou départs suffisent à changer fortement la densité d'une année à l'autre.",
        (f"Dans la version en ligne, des boutons au-dessus de la carte affichent aussi les "
         f"{pluriel(B.lab[p1])}." if geoms else ""),
        ("La colonne CMP donne le nombre de centres médico-psychologiques actifs de FINESS. Sur la carte des "
         "psychiatres, un petit cercle signale une intercommunalité sans psychiatre déclaré qui en accueille au "
         "moins un." if "cmp" in t else ""),
        limites.phrase_md(["prof:psychiatre"]) if "cmp" in t and "psychiatre" in (p0, p1) else "")
    if unite == "intercommunalité":
        L += _plus_loin(["Une intercommunalité qui s'étend sur plusieurs départements est découpée, seule sa partie "
                         "située dans le département est comptée ici. Contours des communes réunis par "
                         "intercommunalité, simplifiés pour l'affichage."])
    elif unite == "commune":
        L += _plus_loin(["Le département compte trop peu d'intercommunalités pour qu'elles décrivent sa répartition "
                         "interne, le tableau est donc donné par commune."])
    return L


def _phrase_sans(s0, s1, un, unite, l0, l1):
    parts = [(s, l) for s, l in ((s0, l0), (s1, l1)) if s > 0]
    if not parts:
        return f"Chaque {unite} compte au moins un {l0} et un {l1}."
    txt = " et ".join(f"{part(s)} dans {un} {unite} sans {l}" for s, l in parts)
    txt = txt[0].upper() + txt[1:]
    return txt.replace(" dans ", " des habitants vivent dans ", 1) + "."


def _route(B, T, famille):
    x = _route_valeurs(B, T, famille)
    ar = B.insee.get("acces_route")
    titre = "## Temps de trajet par la route"
    if x is None or not ar:
        return [titre, "", "Les temps de trajet de l'INSEE ne couvrent pas ce territoire (la Guadeloupe, la Guyane et "
                "Mayotte n'y figurent pas).", ""] if ar else []
    ta = B.R["temps_acces"]
    fr = ta[ta["niveau"] == "FR"].set_index("equipement")
    reg = (ta[(ta["niveau"] == "reg") & (ta["code"] == T.get("reg"))].set_index("equipement")
           if T["niveau"] == "dep" and not T.get("reg_seul") else None)
    ordre = [e for e in EQUIPEMENTS[famille] if e in x.index]
    t = x.loc[ordre].reset_index()
    t["fr20"] = t["equipement"].map(fr["part_population_a_plus_de_20_min"])
    t["fr_med"] = t["equipement"].map(fr["temps_median_min"])
    cols = ["libelle", "temps_median_min", "fr_med", "part_population_a_plus_de_20_min"]
    ents = ["Équipement ou professionnel le plus proche", "Temps médian (min)", "France, temps médian",
            "Habitants à plus de 20 min"]
    if reg is not None and len(reg):
        t["reg20"] = t["equipement"].map(reg["part_population_a_plus_de_20_min"])
        cols.append("reg20")
        ents.append("Région, à plus de 20 min")
    cols.append("fr20")
    ents.append("France, à plus de 20 min")
    m = lambda v: nombre(v, 0)  # noqa: E731
    L = [titre, ""]
    e_u, quoi = ("psychiatre_liberal", "d'un psychiatre libéral") if famille == SM else ("urgences", "d'un service d'urgences")
    if e_u in x.index and pd.notna(x.at[e_u, "part_population_a_plus_de_20_min"]):
        v = x.at[e_u, "part_population_a_plus_de_20_min"]
        svg = cartes.unites(v, "Habitants à plus de 20 minutes par la route",
                            f"Sur 100 habitants, {round(v * 100)} vivent à plus de 20 minutes {quoi}")
        cle_u = f"{T['niveau']}-{T['code']}_{COURT[famille]}_unites"
        (B.dossier_fig / f"{cle_u}.svg").write_text(svg, encoding="utf-8")
        L += graphique(cle_u)
    L += [_tableau(t, cols, ents, {"temps_median_min": m, "fr_med": m, "part_population_a_plus_de_20_min": pct,
                                   "reg20": pct, "fr20": pct}), ""]
    L += _comment_lire(
        "Durée d'un trajet en voiture, aux heures creuses, du domicile à l'équipement le plus proche, même s'il se "
        "trouve dans un autre département. Le temps médian partage les habitants en deux moitiés. Les "
        "professionnels sont ceux qui exercent en libéral, les salariés comptent à travers les structures "
        + ("(CMP, hôpitaux)." if famille == SM else "(hôpitaux, services d'urgences)."),
        "Le plus proche n'est pas toujours disponible (nouveaux patients, délais, dépassements d'honoraires). Ce "
        "tableau mesure une proximité, pas un accès effectif.")
    L += _carte_trajet(B, T, famille)
    L += _distance(B, T, famille)
    L += _plus_loin([f"Source, INSEE, données sur la localisation et l'accès de la population aux équipements, "
                     f"millésime {ar['annee']}, distancier Metric-OSRM (© les contributeurs d'OpenStreetMap et du "
                     f"projet OSRM), Licence Ouverte. Durées pondérées par la population des carreaux de 200 m. "
                     f"Valeurs par intercommunalité dans temps_acces.csv."])
    return L


def _financier(B, T, famille):
    """Part des libéraux pouvant pratiquer des dépassements d'honoraires, et patients sans médecin traitant."""
    from .rapport import FINANCIER
    ac = B.insee.get("ameli_acces")
    if not ac or ac.get("secteurs") is None:
        return []
    t = ac["secteurs"]
    niv, code = T["niveau"], T["code"]
    lab = {i: l for _p, i, l, _f in config.AMELI_SECTEURS_PROFESSIONS}
    milieu_niv = t[(t["niveau"] == niv) & ~t["code"].isin(config.AMELI_DEPARTEMENTS_EXCLUS + config.AMELI_REGIONS_EXCLUES)]
    lignes = []
    for p in FINANCIER[famille]:
        x = t[(t["prof"] == p)].set_index(["niveau", "code"])
        if (niv, code) not in x.index:
            continue
        r = {"libelle": lab[p], "liberaux": x.at[(niv, code), "liberaux"], "part": x.at[(niv, code), "part_depassements"],
             "milieu": milieu_niv.loc[milieu_niv["prof"] == p, "part_depassements"].median(),
             "france": x.at[("FR", "FR"), "part_depassements"] if ("FR", "FR") in x.index else np.nan}
        if niv == "dep" and not T.get("reg_seul") and ("reg", T["reg"]) in x.index:
            r["region"] = x.at[("reg", T["reg"]), "part_depassements"]
        lignes.append(r)
    if not lignes:
        return []
    d = pd.DataFrame(lignes)
    d = d.assign(_nc=d["part"].isna()).sort_values("_nc", kind="stable").drop(columns="_nc")
    avec_reg = "region" in d
    cols = ["libelle", "liberaux", "part"] + (["region"] if avec_reg else []) + ["milieu", "france"]
    ents = ["Profession", "Libéraux", "Pouvant pratiquer des dépassements"] + (["Région"] if avec_reg else []) + [
        f"Milieu des {'départements' if niv == 'dep' else 'régions'}", "France"]
    d["part"] = d["part"].map(lambda v: pct(v) if pd.notna(v) else "non calculée")
    L = ["## Accès financier", "",
         _tableau(d, cols, ents, {"liberaux": nombre, "region": pct, "milieu": pct, "france": pct}), ""]
    ald = ac.get("ald")
    phr = ""
    if famille == SANTE and ald is not None:
        a = ald.set_index(["niveau", "code"])["valeur"]
        if (niv, code) in a.index and pd.notna(a[(niv, code)]):
            m = ald.loc[(ald["niveau"] == niv) & ~ald["code"].isin(config.AMELI_DEPARTEMENTS_EXCLUS + config.AMELI_REGIONS_EXCLUES), "valeur"].median()
            phr = (f"{nombre(a[(niv, code)], 1)} % des patients en affection longue durée n'ont pas déclaré de médecin "
                   f"traitant, contre {nombre(a.get(('FR', 'FR')), 1)} % en France (milieu des "
                   f"{'départements' if niv == 'dep' else 'régions'}, {nombre(m, 1)} %).")
    L += _comment_lire(
        "Part des libéraux en secteur 2 (avec ou sans Optam) ou non conventionnés, qui peuvent facturer au-delà du "
        "tarif de la Sécurité sociale. C'est un obstacle financier possible, pas la mesure des dépassements réels. "
        f"Elle n'est pas calculée quand le territoire compte moins de {config.AMELI_SECTEURS_EFFECTIF_MIN} libéraux de "
        "la profession." + (" Les CMP ne facturent pas de dépassement." if famille == SM else ""),
        "Source, Assurance Maladie (Cnam), licence ODbL.")
    if phr:
        L[0] = "## Accès financier et médecin traitant"
        L += [phr, ""]
    return L


def _isd(B, T, famille):
    """Protection de l'enfance (santé mentale) et handicap (santé), indicateurs sociaux départementaux."""
    isd = B.insee.get("drees_isd")
    if not isd:
        return []
    niv, code = T["niveau"], T["code"]
    t = isd["table"]
    lignes = []
    for d in [d for d in isd["defs"] if d["famille"] == famille]:
        x = t[(t["indicateur"] == d["id"])]
        v = x[(x["niveau"] == niv) & (x["code"] == code)]["valeur"]
        m = x[(x["niveau"] == niv) & x["code"].isin(B.noms[niv].index)]["valeur"].median()
        r = {"libelle": d["libelle"], "unite": d["unite"], "valeur": v.iloc[0] if len(v) else np.nan, "milieu": m,
             "au_niveau": x.loc[x["niveau"] == niv, "valeur"].notna().any()}
        if niv == "dep" and not T.get("reg_seul"):
            rv = x[(x["niveau"] == "reg") & (x["code"] == T["reg"])]["valeur"]
            r["region"] = rv.iloc[0] if len(rv) else np.nan
        lignes.append(r)
    if not lignes:
        return []
    d = pd.DataFrame(lignes)
    if d["valeur"].isna().all():
        return []
    f = lambda v: nombre(v, 1 if abs(v) >= 1 else 2)  # noqa: E731
    d["valeur"] = [f(v) if pd.notna(v) else absent(niv, a) for v, a in zip(d["valeur"], d["au_niveau"])]
    d["milieu"] = [f(m) if a and pd.notna(m) else ("" if a else "non publié") for m, a in zip(d["milieu"], d["au_niveau"])]
    avec_reg = "region" in d and d["region"].notna().any()
    if avec_reg:
        d["region"] = d["region"].map(lambda v: f(v) if pd.notna(v) else "non publié pour les régions")
    cols = ["libelle", "unite", "valeur"] + (["region"] if avec_reg else []) + ["milieu"]
    ents = ["Indicateur", "Unité", "Ce territoire"] + (["Région"] if avec_reg else []) + [
        f"Milieu des {'départements' if niv == 'dep' else 'régions'}"]
    titre = "### Protection de l'enfance" if famille == SM else "## Handicap"
    L = [titre, "", _tableau(d, cols, ents), ""]
    L += _comment_lire(
        "Ces chiffres décrivent l'activité de protection de l'enfance du département, pas un besoin de soins. Les "
        "enfants qu'elle suit vivent plus souvent des situations qui pèsent sur leur santé mentale." if famille == SM else
        "Prestations versées aux personnes en situation de handicap et offre médico-sociale pour les enfants, à lire "
        "à côté de l'offre en orthophonie, psychomotricité et pédiatrie.",
        EXPLICATION_ND if d["valeur"].map(est_nd).any() else "",
        "Source, DREES, indicateurs sociaux départementaux, Licence Ouverte.")
    return L


def _sae(B, T):
    """Psychiatrie à l'hôpital (SAE), comparée à la région, au milieu des territoires et à la France."""
    sae = B.insee.get("sae")
    if not sae:
        return []
    niv, code = T["niveau"], T["code"]
    t = sae["table"]
    lignes = []
    for d in sae["defs"]:
        x = t[t["indicateur"] == d["id"]]
        v = x[(x["niveau"] == niv) & (x["code"] == code)]
        if v.empty or pd.isna(v["valeur"].iloc[0]):
            continue
        r = {"libelle": d["libelle"], "unite": d["unite"], "nombre": v["nombre"].iloc[0], "valeur": v["valeur"].iloc[0],
             "milieu": x[(x["niveau"] == niv) & x["code"].isin(B.noms[niv].index)]["valeur"].median(),
             "france": x.loc[x["niveau"] == "FR", "valeur"].iloc[0] if (x["niveau"] == "FR").any() else np.nan}
        if niv == "dep" and not T.get("reg_seul"):
            rv = x[(x["niveau"] == "reg") & (x["code"] == T["reg"])]["valeur"]
            r["region"] = rv.iloc[0] if len(rv) else np.nan
        lignes.append(r)
    if not lignes:
        return []
    d = pd.DataFrame(lignes)
    f = lambda v: nombre(v, 1)  # noqa: E731
    avec_reg = "region" in d
    cols = ["libelle", "nombre", "valeur", "unite"] + (["region"] if avec_reg else []) + ["milieu", "france"]
    ents = ["Indicateur", "Nombre", "Ce territoire", "Unité"] + (["Région"] if avec_reg else []) + [
        f"Milieu des {'départements' if niv == 'dep' else 'régions'}", "France"]
    L = ["## Psychiatrie à l'hôpital", "", _tableau(d, cols, ents, {"nombre": nombre, "valeur": f, "region": f, "milieu": f,
                                                                       "france": f}), ""]
    L += _comment_lire(
        "Lits, places, CMP et personnels déclarés par les établissements autorisés en psychiatrie (SAE), en "
        "équivalents temps plein pour les personnels. Chaque établissement est rattaché au département où il est "
        "enregistré, même si certains de ses CMP sont situés ailleurs, et un territoire voisin peut accueillir une "
        f"partie de ses habitants. Source, DREES, SAE {sae.get('annee', '')}, Licence Ouverte.")
    return L


CARTE_TRAJET = {SM: "psychiatrie_ambulatoire", SANTE: "urgences"}


def _carte_trajet(B, T, famille):
    """Carte des communes du département selon le temps de trajet médian vers un CMP (santé mentale) ou un service
    d'urgences (santé), audit du 4 octobre 2026, 4.6."""
    if T["niveau"] != "dep":
        return []
    eq = CARTE_TRAJET[famille]
    m = B.minutes_communes(eq)
    geoms = B.communes_dep(T["code"])
    if not m or len(geoms) < 5:   # une carte par commune n'a pas de sens à Paris (une seule commune)
        return []
    quoi = ("jusqu'à la structure de psychiatrie ambulatoire la plus proche, comme un CMP" if famille == SM else
            "jusqu'au service d'urgences le plus proche")
    svg = cartes.carte_temps(geoms, m, f"Temps de trajet médian des habitants de chaque commune {quoi}")
    if not svg:
        return []
    cle = f"{T['niveau']}-{T['code']}_{COURT[famille]}_trajet"
    (B.dossier_fig / f"{cle}.svg").write_text(svg, encoding="utf-8")
    vals = [m[c] for c in geoms if m.get(c) is not None]
    loin = sum(1 for v in vals if v >= 30)
    return ([f"Commune par commune, la carte donne le temps de trajet médian des habitants {quoi}. "
             + (f"{loin} commune{'s' if loin > 1 else ''} sur {len(vals)} {'sont' if loin > 1 else 'est'} à 30 minutes "
                f"ou plus." if loin else f"Aucune des {len(vals)} communes n'est à 30 minutes ou plus."), ""]
            + graphique(cle))


def _distance(B, T, famille):
    ac = B.R.get("accessibilite_communes")
    if not isinstance(ac, pd.DataFrame) or ac.empty:
        return []
    profs = [p for p in INTERNE[famille] + (["pedopsychiatre"] if famille == SM else ["orthophoniste"])
             if p in set(ac["prof"])]
    x = ac[ac["prof"].isin(profs)]
    dans = x["dep"].isin(T["deps"])
    lignes = []
    for p in profs:
        a, f = x[dans & (x["prof"] == p)], x[x["prof"] == p]
        if a["population"].sum() <= 0:
            continue
        lignes.append({"libelle": B.lab[p],
                       "t10": a.loc[a["distance_km"] > 10, "population"].sum() / a["population"].sum(),
                       "f10": f.loc[f["distance_km"] > 10, "population"].sum() / f["population"].sum()})
    if not lignes:
        return []
    t = pd.DataFrame(lignes)
    return ["Le tableau suivant compte tous les professionnels, salariés compris. Il mesure la distance à vol "
            "d'oiseau jusqu'à la commune la plus proche où au moins l'un d'eux exerce.", "",
            _tableau(t, ["libelle", "t10", "f10"], ["Profession", "Habitants à plus de 10 km", "France"],
                     {"t10": pct, "f10": pct}), ""]


def _modes(B, T, famille):
    niv, code = T["niveau"], T["code"]
    n = B.t[niv][0]
    nl = B.lib[niv]
    fe = B.agg.feminisation
    lignes = []
    for p in [q for q in PRINCIPALES[famille] if q in n and B.C.present(q)][:6]:
        tot = n.at[code, p]
        if tot < 1:
            continue
        # références calculées sur les départements, comme le territoire (décision de Lucas du 5 octobre 2026)
        e = B.agg.effectifs["dep"]
        e = e[e["prof"] == p].groupby("mode")["n"].sum()
        r = {"libelle": B.lab[p], "lib": nl.at[code, p] / tot if p in nl else np.nan,
             "lib_fr": e.get("lib", 0) / e["all"] if e.get("all", 0) > 0 else np.nan}
        if fe is not None:
            f = fe[(fe["mode"] == "all") & (fe["prof"] == p)]
            x = f[(f["niveau"] == niv) & (f["code"] == code)]
            r["fem"] = x["part_femmes"].iloc[0] if len(x) and x["personnes"].iloc[0] >= 10 else np.nan
            y = f[f["niveau"] == "dep"]
            r["fem_fr"] = y["femmes"].sum() / y["personnes"].sum() if y["personnes"].sum() > 0 else np.nan
        lignes.append(r)
    if not lignes:
        return []
    t = pd.DataFrame(lignes)
    fem = "fem" in t and t["fem"].notna().any()
    cols = ["libelle", "lib", "lib_fr"] + (["fem", "fem_fr"] if fem else [])
    ents = (["Profession", "Part exerçant en libéral", "Ensemble des départements"]
            + (["Part de femmes", "Ensemble des départements"] if fem else []))
    L = ["## Libéral ou salarié" + (", et part des femmes" if fem else ""), "",
         _tableau(t, cols, ents, {c: pct for c in cols[1:]}, vide="moins de 10 personnes"), ""]
    L += _comment_lire("Une même personne peut exercer en libéral et comme salariée, elle compte alors dans les deux.",
                       "La part de femmes repose sur la civilité déclarée au répertoire. Elle n'est pas donnée quand "
                       "moins de dix personnes exercent." if fem else "")
    return L


def _besoins(B, T):
    """Recours aux soins, indicateurs de Santé publique France, offre face au besoin, vulnérabilité."""
    niv, code = T["niveau"], T["code"]
    L = ["## Besoins et recours aux soins en santé mentale", "",
         "Aucune donnée ne mesure directement le besoin de soins en santé mentale. Plusieurs approches sont "
         "présentées côte à côte, sans être réunies en un score.", ""]
    lignes = []
    am = B.insee.get("ameli")
    if am:
        t = am["table"]
        d = t[t["niveau"] == niv]
        for _top, iid, lab, _e in config.AMELI_INDICATEURS:
            x = d[d["indicateur"] == iid].set_index("code")
            if code not in x.index:
                continue
            s = x["prevalence_standardisee_pct"].drop(config.AMELI_DEPARTEMENTS_EXCLUS + config.AMELI_REGIONS_EXCLUES,
                                                      errors="ignore")
            lignes.append({"libelle": lab, "valeur": x.at[code, "prevalence_standardisee_pct"], "milieu": s.median(),
                           "unite": "% des assurés, à âge égal", "source": "Assurance Maladie (Cnam), licence ODbL"})
    for niv_i in ([niv] if niv == "dep" else ["reg"]):
        for iid, x in _odisse(B, niv_i).items():
            ind = next(i for i in config.ODISSE if i["id"] == iid)
            if code not in x.index or pd.isna(x.at[code, "valeur"]):
                continue
            v = x.at[code, "valeur"]
            fourch = (f" (de {nombre(x.at[code, 'ic_bas'], 1)} à {nombre(x.at[code, 'ic_haut'], 1)})"
                      if pd.notna(x.at[code, "ic_bas"]) else "")
            lignes.append({"libelle": ind["libelle"], "valeur": v, "fourchette": fourch,
                           "milieu": x["valeur"].drop(config.AMELI_DEPARTEMENTS_EXCLUS, errors="ignore").median(),
                           "unite": ind["unite"], "source": ind["source"]})
    if lignes and not all(pd.isna(l["valeur"]) for l in lignes):
        t = pd.DataFrame(lignes)
        def cellule(r):
            if pd.isna(r["valeur"]):
                return "non calculée (secret statistique)" if str(r["source"]).startswith("Assurance") else ND_TERRITOIRE
            return (nombre(r["valeur"], 2 if r["valeur"] < 10 else 1)
                    + (r["fourchette"] if isinstance(r.get("fourchette"), str) else ""))
        t["v"] = t.apply(cellule, axis=1)
        t["m"] = t["milieu"].map(lambda v: nombre(v, 2 if v < 10 else 1))
        L += [_tableau(t, ["libelle", "unite", "v", "m", "source"],
                       ["Indicateur", "Unité", "Ce territoire", f"Milieu des {'départements' if niv == 'dep' else 'régions'}",
                        "Source"]), ""]
        L += _comment_lire(
            "Les personnes prises en charge par l'Assurance Maladie mesurent le recours aux soins, pas le besoin. Leur "
            "nombre dépend en partie du nombre de soignants, car là où ils sont plus nombreux, plus de personnes sont "
            "repérées et suivies. Les décès par suicide et les gestes auto-infligés dépendent beaucoup moins du nombre "
            "de soignants. Ils donnent donc un second regard sur les besoins, à lire avec le premier.",
            limites.phrase_md(["suicides", "hospit_gestes_auto_infliges", "urgences_gestes_auto_infliges"],
                              T["code"] if T["niveau"] == "dep" else None),
            "Les indicateurs du Baromètre de Santé publique France viennent d'une enquête, avec une marge "
            "d'incertitude entre parenthèses. Ils n'existent que par région." if niv == "reg" else "",
            EXPLICATION_ND if t["v"].map(est_nd).any() else "",
            "« Non calculée » signifie que trop de classes d'âge sont masquées par le secret statistique pour calculer "
            "une valeur à âge égal fiable." if (t["v"] == "non calculée (secret statistique)").any() else "")
    L += _quadrant(B, T)
    L += rapport_bases.territoire_ald(B, T, SM)
    L += _isd(B, T, SM)
    L += rapport_bases.territoire_caf(B, T)
    L += _vulnerabilite(B, T)
    return L if len(L) > 5 else []


def _quadrant(B, T):
    qd = B.R.get("quadrants")
    if T["niveau"] != "dep" or not isinstance(qd, pd.DataFrame) or qd.empty:
        return []
    x = qd[(qd["code"] == T["code"]) & (qd["variable"] == "suicides") & qd["prof"].isin(["psychiatre", "psychologue"])]
    x = x.dropna(subset=["quadrant"]).set_index("prof")
    if x.empty:
        return []
    b = "au-dessus" if x["quadrant"].iloc[0].startswith("besoin+") else "au-dessous"
    o = {p: "au-dessus" if q.endswith("offre+") else "au-dessous" for p, q in x["quadrant"].items()}
    if len(set(o.values())) == 1:
        offre = (f"la densité de {_liste(pluriel(B.lab[p]) for p in o)} {'est' if len(o) == 1 else 'sont toutes deux'} "
                 f"{next(iter(o.values()))}").replace("de psychiatres et psychologues", "de psychiatres et celle de psychologues")
    else:
        offre = _liste(f"la densité {de(pluriel(B.lab[p]))} {v}" for p, v in o.items())
    return [f"Par rapport au milieu des départements, le taux de décès par suicide est {b}, et {offre}. Cette position "
            f"par rapport aux médianes ne dit pas que l'offre est insuffisante au sens d'une norme. Un département proche du milieu peut changer de groupe d'une année à l'autre sans "
            f"changement réel.", ""]


def _vulnerabilite(B, T):
    niv, code = T["niveau"], T["code"]
    c = B.ctx.get(niv)
    if c is None or code not in c.index:
        return []
    ids = [i[0] for i in config.CONTEXTE_VULNERABILITE if i[0] in c]
    if not ids:
        return []
    lignes = []
    for v in ids:
        lignes.append({"var": B.ctxlab.get(v, v), "unite": UNITES.get(v, ""), "valeur": c.at[code, v],
                       "au_niveau": c[v].notna().any(),
                       "milieu": c[v].median(),
                       "region": B.ctx["reg"].at[T["reg"], v] if niv == "dep" and "reg" in B.ctx and v in B.ctx["reg"]
                       and T["reg"] in B.ctx["reg"].index else np.nan})
    t = pd.DataFrame(lignes)
    if t["valeur"].isna().all():
        return []
    f = lambda v: nombre(v, 0) if v >= 100 else nombre(v, 1)  # noqa: E731
    t["valeur"] = [f(v) if pd.notna(v) else absent(niv, a) for v, a in zip(t["valeur"], t["au_niveau"])]
    t["milieu"] = [f(m) if a and pd.notna(m) else ("" if a else "non publié") for m, a in zip(t["milieu"], t["au_niveau"])]
    avec_reg = niv == "dep" and not T.get("reg_seul")
    cols = ["var", "unite", "valeur"] + (["region"] if avec_reg else []) + ["milieu"]
    ents = ["Indicateur", "Unité", "Ce territoire"] + (["Région"] if avec_reg else []) + [
        f"Milieu des {'départements' if niv == 'dep' else 'régions'}"]
    L = ["### Conditions de vie", "", _tableau(t, cols, ents, {"region": f}), ""]
    L += _comment_lire("Ces indicateurs décrivent des conditions de vie connues pour peser sur la santé mentale "
                       "(emploi, revenus, diplôme, logement, isolement). Ils ne mesurent pas le besoin de soins. Les "
                       "unités sont détaillées dans le glossaire du rapport national.",
                       EXPLICATION_ND if t["valeur"].map(est_nd).any() else "")
    return L


def _ecarts(B, T, famille):
    ea = B.R.get("ecarts_attendu")
    if T["niveau"] != "dep" or not isinstance(ea, pd.DataFrame) or ea.empty:
        return []
    epci_dep = B.ref.epci.set_index("code")["dep"]
    nom = B.ref.epci.set_index("code")["nom"]
    L, ex = [], None
    for p in INTERNE[famille]:
        e = ea[(ea["prof"] == p) & (ea["code"].map(epci_dep) == T["code"]) & (ea["effectif_attendu"] >= 2)]
        e = e[e["rapport"] < 1].sort_values(["rapport", "manque"], ascending=[True, False]).head(8)
        if e.empty:
            continue
        e = e.assign(nom=e["code"].map(nom))
        ex = ex or (p, e.iloc[0])
        L += [f"**{pluriel(B.lab[p]).capitalize()}**, intercommunalités où l'effectif observé est en dessous de l'attendu", "",
              _tableau(e, ["nom", "pop", "effectif", "effectif_attendu", "rapport"],
                       ["Intercommunalité", "Habitants", "Observés", "Attendus d'après le profil", "Rapport"],
                       {"pop": nombre, "effectif": nombre, "effectif_attendu": lambda v: nombre(v, 1),
                        "rapport": lambda v: nombre(v, 2)}), ""]
    if not L:
        return []
    p, r = ex
    return (["## Écart à l'effectif attendu compte tenu du profil des territoires", ""] + L
            + _comment_lire(
                f"L'effectif attendu est celui d'intercommunalités de profil comparable (âge, revenus, pauvreté, "
                f"densité de population...) dans toute la France. Par exemple, la première intercommunalité du "
                f"tableau compte {nombre(r['effectif'])} {pluriel(B.lab[p]) if r['effectif'] != 1 else B.lab[p].lower()} "
                f"là où l'on en attendrait environ {nombre(r['effectif_attendu'])}.",
                "Ce n'est pas une mesure du besoin de soins, et les territoires de comparaison peuvent eux-mêmes être "
                "mal dotés. Seules les intercommunalités où l'on attendrait au moins deux professionnels figurent ici. "
                "Une intercommunalité qui s'étend sur plusieurs départements est rattachée à celui où vit la plus "
                "grande partie de sa population. Sur de petits effectifs, la liste peut changer d'une année à l'autre."))


def _sources(B):
    L = ["## Sources", ""]
    for e in JOURNAL.entrees:
        if e.statut != "ok" or e.source.startswith(("Site", "Graphiques", "Rapport")):
            continue
        L.append(ligne_source(e))
    if indicateurs.odbl(B.insee):
        L += ["", MENTION_ODBL]
    L += ["", "La méthode complète, les précautions de lecture et le glossaire se trouvent dans le rapport national et "
          "sur la page « Méthode, données et limites ».", ""]
    return L


# ---------------------------------------------------------------- écriture
def territoires(ref) -> list[dict]:
    """Liste des territoires qui ont un rapport. Les régions d'un seul département n'en ont pas."""
    deps_reg = ref.deps.groupby("reg")["code"].apply(list).to_dict()
    out = []
    for _, r in ref.regs.sort_values("code").iterrows():
        deps = sorted(deps_reg.get(r["code"], []))
        if len(deps) > 1:
            out.append({"niveau": "reg", "code": r["code"], "nom": r["nom"], "reg": r["code"], "deps": deps})
    for _, d in ref.deps.sort_values("code").iterrows():
        out.append({"niveau": "dep", "code": d["code"], "nom": d["nom"], "reg": d["reg"], "deps": [d["code"]],
                    "reg_seul": len(deps_reg.get(d["reg"], [])) == 1})
    return out


def rapport(B, T, famille, jour) -> str:
    from .lecture import date_longue
    cle_fig = f"{T['niveau']}-{T['code']}_{COURT[famille]}"
    sujet = "santé mentale" if famille == SM else "santé"
    L = [f"# Offre de soins en {sujet}, {T['nom']}, {date_longue(jour)}", "",
         f"Ce rapport décrit l'offre de soins en {sujet} dans {'le département' if T['niveau'] == 'dep' else 'la région'} "
         f"{T['nom']} ({T['code']}), à partir des répertoires publics des professionnels de santé et d'autres données "
         f"publiques. Il compare le territoire à {'sa région, à la moyenne des départements' if T['niveau'] == 'dep' else 'la moyenne des régions'}"
         f"{' et à des départements de profil semblable' if T['niveau'] == 'dep' and B.semblables.get(T['code']) else ''}. "
         f"Il décrit sans classer. Les détails techniques sont repliés sous « Pour aller plus loin ».", "",
         "## En bref", ""]
    L += [f"- {p}" for p in _en_bref(B, T, famille)] + [""]
    L += _professions(B, T, famille, cle_fig)
    L += rapport_bases.territoire_evolution(B, T, famille)
    if famille == SM:
        L += _sae(B, T)
    L += _interne(B, T, famille, cle_fig)
    L += _route(B, T, famille)
    L += _financier(B, T, famille)
    if famille == SANTE:
        L += rapport_bases.territoire_ald(B, T, famille)
        L += _isd(B, T, famille)
    L += _modes(B, T, famille)
    if famille == SM:
        L += _besoins(B, T)
    L += _ecarts(B, T, famille)
    L += _sources(B)
    return "\n".join(L)


def ecrire(out, agg, ref, professions, insee, R, jour) -> str:
    """Écrit tous les rapports territoriaux et leur index. Renvoie le texte de tous les rapports, pour le
    contrôle du langage."""
    dossier = out / "territoires"
    (dossier / "graphiques").mkdir(parents=True, exist_ok=True)
    B = Base(agg, ref, professions, insee, R)
    B.dossier_fig = dossier / "graphiques"
    index, textes, erreurs = [], [], 0
    for T in territoires(ref):
        fichiers = {}
        for famille in (SM, SANTE):
            nom = f"{T['niveau']}-{T['code']}-{CLE[famille]}.md"
            try:
                texte = rapport(B, T, famille, jour)
            except Exception as e:  # noqa: BLE001
                erreurs += 1
                log.exception("rapport territorial %s %s", T["code"], famille)
                if erreurs <= 3:
                    JOURNAL.note(f"Rapport territorial {T['code']}", "erreur", str(e)[:200])
                continue
            (dossier / nom).write_text(texte, encoding="utf-8")
            fichiers[CLE[famille]] = nom
            textes.append(texte)
        index.append({k: T[k] for k in ("niveau", "code", "nom", "reg")} | {"fichiers": fichiers})
    (dossier / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    # temps de trajet médian par commune, données des cartes des rapports départementaux (audit 4.6)
    lignes = [pd.DataFrame({"code": list(m), "equipement": eq, "temps_median_min": list(m.values())})
              for eq in CARTE_TRAJET.values() if (m := B.minutes_communes(eq))]
    if lignes:
        tc = pd.concat(lignes, ignore_index=True)
        tc.insert(1, "nom", tc["code"].map(B.noms["com"]))
        tc["temps_median_min"] = tc["temps_median_min"].round(1)
        tc.to_csv(out / "temps_acces_communes.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    n = sum(len(i["fichiers"]) for i in index)
    JOURNAL.controle("Rapports territoriaux écrits", f"{n} rapports ({erreurs} en erreur)")
    return "\n".join(textes)
