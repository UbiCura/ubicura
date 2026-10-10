"""Rapport en Markdown, lisible sans formation statistique. Trois parties, la santé mentale d'abord,
puis la santé, puis un court croisement des deux. Chaque partie s'ouvre sur un « En bref » généré à
partir des résultats, chaque tableau est suivi d'un « Comment lire » avec un exemple tiré des
données, et les détails techniques sont repliés dans « Pour aller plus loin ».
Le texte décrit, il n'interprète pas."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config, indicateurs, libelles, limites, rapport_bases
from .analyses import CLASSES_DENSITE, moyenne_territoires, tables
from .lecture import (DEFINITIONS, GLOSSAIRE, date_longue, de, fois, force, minuscule, noms_classes, nombre, pct,
                      phrase_correlation, phrase_gini, pluriel, un_pour)
from .util import JOURNAL

SM, SANTE = config.SANTE_MENTALE, config.SANTE
PRINCIPALES = {
    SM: ["psychologue", "psychiatre", "pedopsychiatre", "psychotherapeute"],
    SANTE: ["medecin_generaliste", "infirmier", "masseur_kinesitherapeute", "orthophoniste", "psychomotricien",
            "pharmacien", "chirurgien_dentiste", "sage_femme", "pediatre"],
}
RETRAIT = {SM: ["psychologue", "psychiatre"], SANTE: ["medecin_generaliste", "orthophoniste"]}
POP_MIN_RETRAIT = 20000


# ---------------------------------------------------------------- outils
def _tableau(df, colonnes, entetes, fmt=None, vide=""):
    """Tableau Markdown. `vide` est le texte d'une case sans valeur, pour qu'aucune case ne reste blanche sans raison."""
    fmt = fmt or {}
    l = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    for _, r in df.iterrows():
        cells = []
        for c in colonnes:
            v = r[c]
            f = fmt.get(c)
            cells.append(f(v) if f and pd.notna(v) else (vide if pd.isna(v) else str(v)))
        l.append("| " + " | ".join(cells) + " |")
    return "\n".join(l)


def _comment_lire(*phrases):
    """Paragraphe « Comment lire », suivi des limites connues des données dans un paragraphe « À savoir » à part."""
    phrases = [p.strip() for p in phrases if p and p.strip()]
    lire = [p for p in phrases if not p.startswith(limites.A_SAVOIR)]
    savoir = [p[len(limites.A_SAVOIR):] for p in phrases if p.startswith(limites.A_SAVOIR)]
    L = ["**Comment lire.** " + " ".join(lire), ""] if lire else []
    return L + (["**À savoir.** " + " ".join(savoir), ""] if savoir else [])


def _plus_loin(lignes):
    corps = []
    for l in [x for x in lignes if x]:
        if corps and not (l.startswith(("- ", "|")) and corps[-1].startswith(("- ", "|"))):
            corps.append("")
        corps.append(l)
    return ["<details>", "<summary>Pour aller plus loin</summary>", ""] + corps + ["", "</details>", ""]


def _groupe(titre, intro, *sections, abaisser=True):
    """Grande partie d'un rapport. Les sections gardent leur ordre, leurs titres descendent d'un niveau."""
    L = []
    for s in sections:
        L += [("#" + l if abaisser and l.startswith("###") else l) for l in s]
    if not L:
        return []
    return [f"### {titre}", ""] + ([intro, ""] if intro else []) + L


def minuscule_pluriel(lib):
    return pluriel(lib)


def _liste(noms):
    noms = list(noms)
    if not noms:
        return ""
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]


class Contexte:
    """Données communes aux sections du rapport."""

    def __init__(self, agg, ref, professions, R):
        self.agg, self.ref, self.R = agg, ref, R
        self.prof = professions.set_index("id")
        self.lab = self.prof["libelle"].to_dict()
        self.pop_fr = float(ref.communes["pop"].sum())
        nat = agg.national[agg.national["mode"] == "all"].set_index("prof")["n"]
        self.nat = nat
        ineg = R.get("inegalites")
        self.ineg = (ineg[(ineg["niveau"] == "epci") & (ineg["mode"] == "all")].set_index("prof")
                     if isinstance(ineg, pd.DataFrame) and len(ineg) else pd.DataFrame())
        self.n_epci, self.d_epci, self.pop_epci = tables(agg, ref, "epci", "all")
        self.nom_epci = ref.epci.set_index("code")["nom"]
        self.elargi_personnes = professions.attrs.get("elargi_personnes")
        self.inscrits = professions.attrs.get("inscrits")
        self._moyennes = {}

    def densite(self, p):
        """Densité de la France entière, chaque personne comptée une fois, toutes activités. Chiffre national."""
        return self.nat.get(p, 0) / self.pop_fr * 1e4

    def moyenne(self, p, niveau, mode="all"):
        """Densité de référence pour comparer des territoires d'un niveau (com, piece, epci, dep, reg), calculée
        comme eux. Somme des effectifs des territoires rapportée à la population, donc sans les activités sans lieu
        ni les activités sans soins à la population, et une personne compte dans chaque territoire où elle exerce
        (décision de Lucas du 5 octobre 2026). C'est la moyenne des territoires pondérée par leur population."""
        cle = (p, niveau, mode)
        if cle not in self._moyennes:
            self._moyennes[cle] = moyenne_territoires(self.agg.effectifs.get(niveau), p, self.pop_fr, mode)
        return self._moyennes[cle]

    def present(self, p):
        return p in self.nat.index and self.nat[p] > 0

    def cmp_epci(self) -> pd.Series:
        """CMP actifs de FINESS par intercommunalité (build.cmp_et_psychiatres), vide si FINESS manque."""
        c = getattr(self.agg, "cmp", None)
        if not isinstance(c, pd.DataFrame) or c.empty:
            return pd.Series(dtype=float)
        return c.groupby("epci")["cmp"].sum()

    def phrase_cmp(self, codes=None, total=True) -> str:
        """Phrase qui nuance « aucun psychiatre ne déclare exercer » par les CMP de FINESS, pour toutes les
        intercommunalités ou pour celles d'un territoire (codes)."""
        cmp_ = self.cmp_epci()
        if cmp_.empty or "psychiatre" not in self.n_epci:
            return ""
        zero = self.n_epci.index[self.n_epci["psychiatre"] == 0]
        if codes is not None:
            zero = zero[zero.isin(codes)]
        if not len(zero):
            return ""
        avec = [c for c in zero if cmp_.get(c, 0) > 0]
        if not avec:
            return ("D'après FINESS, aucune de ces intercommunalités n'accueille de centre médico-psychologique (CMP)."
                    if len(zero) > 1 else "D'après FINESS, elle n'accueille pas de centre médico-psychologique (CMP).")
        if len(zero) == 1:
            return (f"D'après FINESS, elle accueille pourtant {nombre(int(cmp_[avec[0]]))} centre"
                    f"{'s' if cmp_[avec[0]] > 1 else ''} médico-psychologique{'s' if cmp_[avec[0]] > 1 else ''} (CMP), "
                    f"où des psychiatres peuvent consulter sans y être déclarés.")
        c = getattr(self.agg, "cmp", None)
        total = (f" Seuls {nombre(c.attrs['avec'])} des {nombre(c.attrs['total'])} CMP actifs de FINESS ont au moins "
                 f"un psychiatre déclaré à leur adresse." if total and codes is None and c is not None and "total" in c.attrs else "")
        return (f"D'après FINESS, {nombre(len(avec))} de ces {nombre(len(zero))} intercommunalités "
                f"{'accueille' if len(avec) == 1 else 'accueillent'} pourtant "
                f"au moins un centre médico-psychologique (CMP), où des psychiatres peuvent consulter sans y être "
                f"déclarés." + total)

    def ids(self, famille, nature="profession"):
        t = self.prof[(self.prof["famille"] == famille) & (self.prof["nature"] == nature)]
        return [p for p in t.index if self.present(p)]

    def sans(self, *profs):
        """Part de la population qui vit dans une intercommunalité sans aucun professionnel des
        professions données (aucune des professions citées)."""
        cols = [p for p in profs if p in self.n_epci]
        if not cols:
            return np.nan
        zero = (self.n_epci[cols] == 0).all(axis=1)
        return self.pop_epci[zero].sum() / self.pop_epci.sum()


# ---------------------------------------------------------------- sections
def _panorama(C: Contexte, famille):
    L = []
    profs = [p for p in C.ids(famille) if p in C.ineg.index]
    t = pd.DataFrame({"prof": profs})
    t["libelle"] = t["prof"].map(C.lab)
    t["effectif"] = t["prof"].map(C.nat)
    t["densite"] = t["prof"].map(C.densite)
    t["un_pour"] = t["densite"].map(lambda d: un_pour(d).replace("un pour ", ""))
    t["gini"] = t["prof"].map(C.ineg["gini"])
    t["sans"] = t["prof"].map(C.ineg["part_population_sans_professionnel"])
    t = t.sort_values("effectif", ascending=False)
    if famille == SANTE:
        t = t[t["effectif"] >= 1000]
    titre = "Les professions de santé mentale" if famille == SM else "Les professions de santé"
    L += [f"### {titre}", "",
          _tableau(t, ["libelle", "effectif", "densite", "un_pour", "gini", "sans"],
                   ["Profession", "Effectif en France", "Pour 10 000 habitants", "Soit un pour", "Inégalité (Gini)",
                    "Habitants sans ce professionnel dans leur intercommunalité"],
                   {"effectif": nombre, "densite": lambda v: nombre(v, 1), "gini": lambda v: nombre(v, 2),
                    "sans": pct}), ""]
    cle = "sm" if famille == SM else "sante"
    L += graphique(f"carte_dep_{cle}") + graphique(f"tuiles_dep_{cle}") + graphique(f"multiples_{cle}")
    L += graphique("lorenz_" + cle)
    if len(t):
        r = t.iloc[0]
        L += _comment_lire(
            f"L'effectif compte chaque personne une seule fois pour la France entière. "
            f"Par exemple, {nombre(r['effectif'])} {pluriel(r['libelle'])} pour {nombre(C.pop_fr)} habitants donnent "
            f"une densité de {nombre(r['densite'], 1)} pour 10 000 habitants, soit {un_pour(r['densite'])}.",
            f"L'indice de Gini mesure l'inégalité de répartition entre intercommunalités, de 0 (répartition "
            f"proportionnelle à la population) à 1 (tous dans un seul territoire). À {nombre(r['gini'], 2)}, la "
            f"répartition des {pluriel(r['libelle'])} est {phrase_gini(r['gini'])}.",
            "La dernière colonne donne la part des habitants dont l'intercommunalité ne compte aucun professionnel "
            "de la catégorie. Cela ne veut pas dire qu'ils n'y ont pas accès, le plus proche peut exercer juste à "
            "côté.",
            "Sur les cartes, un rond ocre marqué « ! » signale une donnée fragile, sans changer la couleur du "
            "territoire.", limites.phrase_md(["mayotte"] + (["prof:pedopsychiatre"] if famille == SM else [])))
    if famille == SM:
        L += _qualifications(C) + _elargi(C)
    L += _hors_soins(C, famille)
    return L


def _parcours(C: Contexte, famille):
    """Du répertoire aux densités, une phrase et le schéma des étapes pour la profession principale de la famille."""
    from .export import _parcours as table_parcours
    p0 = PRINC[famille]
    t = table_parcours(C.agg, C.inscrits, C.lab)
    if t is None or p0 not in set(t["prof"]):
        return []
    q = t.set_index("prof").loc[p0]
    ins = q.get("inscrits")
    ins = None if ins is None or pd.isna(ins) else int(ins)
    pl = pluriel(C.lab[p0])
    debut = (f"Sur {nombre(ins)} {pl} inscrits au répertoire, {nombre(q['avec_activite'])} déclarent une activité"
             if ins else f"Sur {nombre(q['avec_activite'])} {pl} qui déclarent une activité")
    tele = int(q["dont_teleconsultation"])
    return ["#### Du répertoire aux densités", "",
            debut + f", {nombre(q['avec_lieu'])} ont au moins un lieu d'exercice et {nombre(q['dans_densites'])} sont "
            f"comptés dans les densités des territoires. {nombre(q['sans_lieu'])} n'ont aucun lieu fixe (remplacements, "
            f"exercice sans site), {nombre(q['sans_soins_seulement'])} n'exercent qu'à des activités sans soins à la "
            f"population" + (f", dont {nombre(tele)} en téléconsultation" if tele else "") + ". Tous restent dans "
            "l'effectif national.", "", *graphique(f"parcours_{'sm' if famille == SM else 'sante'}"),
            *_comment_lire("Chaque barre compte des personnes, une seule fois. Le pointillé montre ce qui est écarté à "
                           "chaque étape, avec sa raison. Seule la dernière barre entre dans les densités et les cartes.",
                           "", "Toutes les professions dans parcours_activites.csv.")]


def _sieges(C: Contexte, famille):
    """Départements où les activités sans soins à la population pèsent le plus (effet des sièges), pour la profession
    de la famille où cet effet est le plus fort. Rien n'est montré si l'effet reste faible (moins de 5 pour 100)."""
    ap = (C.agg.particulieres or {}).get("dep")
    if not isinstance(ap, pd.DataFrame) or ap.empty:
        return []
    e = C.agg.effectifs["dep"]
    noms = C.ref.deps.set_index("code")["nom"]
    choix = None
    for p in [p for p in PRINCIPALES[famille] if C.present(p)]:
        d = ap[(ap["categorie"] == "sans_soins") & (ap["prof"] == p)].set_index("code")["n"]
        d = d[d >= config.SECRET_MIN]
        if len(d) < 3:
            continue
        ep = e[(e["prof"].astype(str) == p) & (e["mode"] == "all")].set_index("code")["n"]
        top = d.sort_values(ascending=False).head(5)
        t = pd.DataFrame({"code": top.index, "nom": top.index.map(noms), "sans": top.values,
                          "comptes": ep.reindex(top.index).fillna(0).astype(int).values})
        t["pour100"] = t["sans"] / t["comptes"].where(t["comptes"] > 0) * 100
        if choix is None or t["pour100"].max() > choix[1]["pour100"].max():
            choix = (p, t)
    if choix is None or choix[1]["pour100"].max() < 5:
        return []
    p0, t = choix
    pl = pluriel(C.lab[p0])
    return [f"Ces activités se concentrent dans quelques départements, souvent là où se trouvent les sièges. Le tableau "
            f"donne, pour les {pl}, les cinq départements où elles sont les plus nombreuses, rapportées aux {pl} "
            "comptés dans la densité du département.", "",
            _tableau(t, ["nom", "sans", "comptes", "pour100"],
                     ["Département", "Activités sans soins à la population déclarées ici",
                      f"{pl[:1].upper() + pl[1:]} comptés dans la densité", "Pour 100 comptés"],
                     {"sans": nombre, "comptes": nombre, "pour100": lambda v: nombre(v, 1)}), ""]


def _hors_soins(C: Contexte, famille):
    """Activités sans soins à la population, retirées des densités, et activités pour un public particulier."""
    ap = C.agg.particulieres
    if not ap:
        return []
    fam = set(C.ids(famille)) | set(C.ids(famille, "qualification"))
    fr = ap["france"]
    t = fr[(fr["categorie"] == "sans_soins") & fr["prof"].isin(fam) & (fr["personnes"] >= 50)].copy()
    if t.empty:
        return []
    t["libelle"] = t["prof"].map(C.lab)
    r = t.set_index("prof").loc[PRINC[famille]] if PRINC[famille] in set(t["prof"]) else t.iloc[0]
    L = _parcours(C, famille)
    L += ["#### Activités sans soins à la population", "",
         f"{nombre(r['personnes'])} {pluriel(r['libelle'])} déclarent au moins une activité sans soins à la population, "
         f"soit {pct(r['part_profession'])} de la profession"
         + (f", dont {nombre(r['dont_teleconsultation'])} pour une société de téléconsultation. " if r["dont_teleconsultation"]
            else ". ")
         + (f"{nombre(r['sans_autre_lieu_de_soins'])} d'entre eux n'ont pas d'autre activité avec un lieu "
            f"d'exercice et ne sont comptés dans aucune densité." if r["sans_autre_lieu_de_soins"] else
            "Tous ont aussi une activité comptée dans les densités."), "",
         _tableau(t, ["libelle", "personnes", "dont_teleconsultation", "sans_autre_lieu_de_soins", "part_profession"],
                  ["Profession", "Activité sans soins à la population", "Dont téléconsultation",
                   "Comptés dans aucune densité", "Part de la profession"],
                  {"personnes": nombre, "dont_teleconsultation": nombre, "sans_autre_lieu_de_soins": nombre,
                   "part_profession": pct}), ""]
    pp = fr[(fr["categorie"] == "public_particulier") & fr["prof"].isin(fam)].set_index("prof")
    ex = ""
    p0 = PRINC[famille]
    if p0 in pp.index:
        ex = (f"Les activités pour un public particulier (médecine du travail, santé scolaire, services de l'État, "
              f"pompiers, hôpitaux militaires...) restent comptées. Elles concernent "
              f"{nombre(pp.at[p0, 'personnes'])} {pluriel(C.lab[p0])}, soit {pct(pp.at[p0, 'part_profession'])} de la "
              f"profession.")
    L += _sieges(C, famille)
    L += _comment_lire(
        "Ces activités ne soignent pas les habitants d'un territoire (contrôle médical de l'Assurance Maladie, "
        "industrie du médicament, recherche, administration, sièges d'organismes, téléconsultation...). Elles sont "
        "souvent déclarées à l'adresse d'un siège, le plus souvent à Paris. Elles sont donc retirées des densités et "
        "des cartes, et comptées à part pour chaque territoire. Les personnes restent dans l'effectif national, une "
        "seule fois.", ex,
        "Détail dans activites_particulieres.csv (France) et activites_particulieres_dep.csv (par département), "
        "secteurs et catégories dans secteurs.csv.")
    return L


def _qualifications(C: Contexte):
    qs = [p for p in C.ids(SM, "qualification")]
    if not qs:
        return []
    t = pd.DataFrame({"prof": qs})
    t["libelle"] = t["prof"].map(C.lab)
    t["effectif"] = t["prof"].map(C.nat)
    t["densite"] = t["prof"].map(C.densite)
    L = ["#### Qualifications complémentaires des médecins", "",
         _tableau(t, ["libelle", "effectif", "densite"], ["Qualification", "Médecins en France", "Pour 10 000 habitants"],
                  {"effectif": nombre, "densite": lambda v: nombre(v, 2)}), ""]
    ex = []
    if "q_psychiatrie_enfant" in qs and C.present("pedopsychiatre"):
        ex.append(f"Par exemple, {nombre(C.nat['pedopsychiatre'])} médecins sont inscrits à l'Ordre comme "
                  f"pédopsychiatres, mais {nombre(C.nat['q_psychiatrie_enfant'])} psychiatres ont une qualification "
                  f"pour l'enfant et l'adolescent, toutes voies confondues.")
    L += _comment_lire(DEFINITIONS["qualification"], *ex)
    return L


def _elargi(C: Contexte):
    es = [p for p in C.ids(SM, "perimetre_elargi")]
    if not es:
        return []
    t = pd.DataFrame({"prof": es})
    t["base"] = t["prof"].map(C.prof["base"])
    t["libelle"] = t["base"].map(C.lab)
    t["effectif"] = t["prof"].map(C.nat)
    t["part"] = t["effectif"] / t["base"].map(C.nat)
    t = t.sort_values("effectif", ascending=False)
    L = ["#### Périmètre élargi, salariés des établissements psychiatriques", "",
         _tableau(t, ["libelle", "effectif", "part"],
                  ["Profession", "Salariés d'un établissement psychiatrique", "Part de la profession"],
                  {"effectif": nombre, "part": pct}), ""]
    r = t.iloc[0]
    cats = ", ".join(libelles.affichage(v, "FINESS catégorie", k).split(" (")[0]
                     for k, v in list(config.FINESS_SANTE_MENTALE.items())[:6])
    L += _comment_lire(
        f"Ce tableau compte les personnes salariées d'un établissement psychiatrique ou médico-psychologique "
        f"({cats}...). Par exemple, {nombre(r['effectif'])} {pluriel(r['libelle'])} y travaillent, soit "
        f"{pct(r['part'])} de leur profession.",
        "Ce périmètre se lit à côté du tableau précédent et ne s'y ajoute pas. Les psychologues et psychiatres "
        "qui y figurent sont aussi comptés plus haut. Les services de psychiatrie des hôpitaux généraux n'y "
        "figurent pas, faute de pouvoir les repérer dans les données.")
    return L


def _recours(C: Contexte, insee, ctxlab):
    """Recours aux soins en santé mentale (Assurance Maladie), indicateurs indirects du besoin."""
    am = (insee or {}).get("ameli")
    if not am:
        return []
    t = am["table"]
    d = t[t["niveau"] == "dep"].copy()
    noms = C.ref.deps.set_index("code")["nom"]
    lignes = []
    for _top, iid, lab, _e in config.AMELI_INDICATEURS:
        x = d[d["indicateur"] == iid]
        if x.empty:
            continue
        s = x.set_index("code")["prevalence_standardisee_pct"].dropna()
        fr = x["patients"].sum() / x["population"].sum() * 100
        lignes.append({"libelle": lab, "france": fr, "patients": x["patients"].sum(), "mediane": s.median(),
                       "vmin": s.min() if len(s) else np.nan, "vmax": s.max() if len(s) else np.nan,
                       "min": f"{nombre(s.min(), 2)} % ({noms.get(s.idxmin(), s.idxmin())})" if len(s) else "",
                       "max": f"{nombre(s.max(), 2)} % ({noms.get(s.idxmax(), s.idxmax())})" if len(s) else ""})
    if not lignes:
        return []
    T = pd.DataFrame(lignes)
    r0 = T.iloc[0]
    L = ["### Besoins et recours aux soins en santé mentale", "",
         "Aucune donnée ne mesure directement le besoin de soins en santé mentale. Le rapport en réunit plusieurs "
         "approches, présentées côte à côte et jamais combinées en un score.", "",
         "#### Personnes prises en charge par l'Assurance Maladie", "",
         f"En {am.get('annee', '')}, {nombre(r0['patients'])} personnes, soit {nombre(r0['france'], 1)} % des "
         f"assurés, sont prises en charge par l'Assurance Maladie pour un trouble psychique. Une fois l'âge de la "
         f"population pris en compte, cette part va de {nombre(r0['vmin'], 2)} % à {nombre(r0['vmax'], 2)} % selon les "
         f"départements.", "",
         _tableau(T, ["libelle", "patients", "france", "mediane", "min", "max"],
                  ["Indicateur", "Personnes en France", "Part des assurés", "Médiane des départements, à âge égal",
                   "Département le plus bas", "Département le plus haut"],
                  {"patients": nombre, "france": lambda v: nombre(v, 2) + " %", "mediane": lambda v: nombre(v, 2) + " %"}),
         ""]
    L += _comment_lire(
        "Ces chiffres comptent les personnes repérées par l'Assurance Maladie, à partir de leurs hospitalisations, "
        "de leurs affections de longue durée ou de leurs traitements. Ils mesurent le recours aux soins, pas le "
        "besoin. Ils dépendent eux-mêmes de l'offre, car un territoire bien doté repère et soigne davantage. Les "
        "lignes « sans trouble repéré » concernent des personnes qui reçoivent des psychotropes sans qu'un trouble "
        "psychique soit enregistré par ailleurs.",
        "Les comparaisons entre départements se font « à âge égal » (prévalence standardisée), pour qu'un "
        "département plus âgé ne paraisse pas plus touché du seul fait de son âge. Les valeurs basses des "
        "départements d'outre-mer peuvent tenir en partie à des différences d'accès aux soins et d'enregistrement. "
        "Ces indicateurs sont présentés côte à côte et ne sont jamais réunis en un score de besoin.")
    # lien avec l'offre, au niveau des départements (lien circulaire, à lire avec prudence)
    cc = C.R.get("correlations_contexte")
    if isinstance(cc, pd.DataFrame) and len(cc):
        f = cc[(cc["niveau"] == "dep") & (cc["mode"] == "all") & (cc["variable"] == "pec_troubles_psy")
               & cc["prof"].isin(["psychologue", "psychiatre", "medecin_generaliste"])].set_index("prof")
        if len(f):
            phr = []
            for p in ["psychiatre", "psychologue", "medecin_generaliste"]:
                if p in f.index:
                    r = f.loc[p]
                    phr.append(f"{nombre(r['rho_spearman'], 2)} pour les {pluriel(C.lab[p])}"
                               + (f" ({nombre(r['rho_partiel_densite'], 2)} à densité de population égale)"
                                  if pd.notna(r.get("rho_partiel_densite")) else ""))
            L += [f"Entre départements, la corrélation de rang entre la part des personnes prises en charge pour un "
                  f"trouble psychique et la densité de professionnels vaut {_liste(phr)}. Quand un lien existe, il "
                  f"peut aller dans les deux sens. Les besoins attirent l'offre, et l'offre augmente aussi le nombre "
                  f"de personnes repérées et soignées. Ces chiffres ne permettent donc pas de dire si l'offre répond "
                  f"au besoin.", ""]
    L += _plus_loin([
        f"Source, Assurance Maladie, cartographie des pathologies et des dépenses (data.ameli.fr), année "
        f"{am.get('annee', '')}, tous régimes, tous sexes. Prévalence standardisée par la méthode directe sur les "
        f"classes d'âge quinquennales, population de référence France entière. Les cases d'âge masquées par le "
        f"secret statistique comptent pour zéro, la valeur standardisée n'est pas calculée si elles représentent "
        f"plus de {nombre((1 - config.AMELI_COUVERTURE_MIN) * 100)} % des patients du département. Mayotte est "
        f"exclue, son régime de sécurité sociale étant très partiellement couvert par ces données. Données sous "
        f"licence ODbL, isolées dans les fichiers suffixés _odbl."])
    return L


def _besoins_spf(C: Contexte, insee):
    """Indicateurs de Santé publique France, moins dépendants de l'offre que les patients pris en charge."""
    spf = (insee or {}).get("odisse")
    if not spf:
        return []
    t = spf["table"]
    noms = {"dep": C.ref.deps.set_index("code")["nom"], "reg": C.ref.regs.set_index("code")["nom"]}
    defs = {d["id"]: d for d in spf["defs"]}
    lignes = []
    for ind in config.ODISSE:
        x = t[t["indicateur"] == ind["id"]]
        niv = ind["niveau"]
        x = x[x["code"].isin(noms[niv].index)].set_index("code")
        if x.empty:
            continue
        # Mayotte, aux données moins complètes, n'est pas retenue pour désigner les extrêmes
        v = x["valeur"].drop([c for c in config.AMELI_DEPARTEMENTS_EXCLUS + config.AMELI_REGIONS_EXCLUES
                              if c in x.index and niv == ("dep" if len(c) == 3 else "reg")], errors="ignore")
        fmt = lambda c: (f"{nombre(v[c], 1)} ({noms[niv].get(c, c)}"  # noqa: E731
                         + (f", de {nombre(x.at[c, 'ic_bas'], 1)} à {nombre(x.at[c, 'ic_haut'], 1)}"
                            if pd.notna(x.at[c, "ic_bas"]) else "") + ")")
        lignes.append({"libelle": ind["libelle"], "unite": ind["unite"], "annee": defs[ind["id"]]["annee"],
                       "niveau": "départements" if niv == "dep" else "régions", "mediane": v.median(),
                       "min": fmt(v.idxmin()), "max": fmt(v.idxmax()), "vmin": v.min(), "vmax": v.max(),
                       "source": ind["source"]})
    if not lignes:
        return []
    T = pd.DataFrame(lignes)
    s = next((l for l in lignes if l["libelle"].startswith("Décès par suicide")), lignes[0])
    L = ["#### Suicide, gestes auto-infligés et santé déclarée", "",
         f"En {s['annee']}, à structure d'âge égale, le taux de décès par suicide va de {nombre(s['vmin'], 1)} à "
         f"{nombre(s['vmax'], 1)} pour 100 000 habitants selon les départements, avec une médiane de "
         f"{nombre(s['mediane'], 1)}.", "",
         _tableau(T, ["libelle", "unite", "annee", "niveau", "mediane", "min", "max", "source"],
                  ["Indicateur", "Unité", "Année", "Comparaison entre", "Médiane", "Le plus bas", "Le plus haut", "Source"],
                  {"mediane": lambda v: nombre(v, 1)}), ""]
    L += _comment_lire(
        "Le nombre de personnes soignées pour un trouble psychique dépend en partie du nombre de soignants. Là où ils "
        "sont plus nombreux, plus de personnes sont repérées et suivies. Les décès par suicide, les gestes "
        "auto-infligés et les réponses à une enquête dépendent beaucoup moins du nombre de soignants. Ils donnent donc "
        "un second regard sur les besoins, à lire avec le premier. Les passages aux urgences sont une part de l'activité des urgences et non un taux rapporté à la population. "
        "Mayotte, dont les données sont moins complètes, n'est pas retenue pour désigner les valeurs extrêmes.",
        "Les trois dernières lignes viennent d'une enquête, le Baromètre de Santé publique France. Elles mesurent ce "
        "que les personnes déclarent, avec une marge d'incertitude (intervalle de confiance à 95 %) donnée entre "
        "parenthèses. Elles n'existent que par "
        "région et ne sont jamais attribuées aux départements.",
        limites.phrase_md(["suicides", "hospit_gestes_auto_infliges", "urgences_gestes_auto_infliges"]))
    cc = C.R.get("correlations_contexte")
    if isinstance(cc, pd.DataFrame) and len(cc):
        f = cc[(cc["niveau"] == "dep") & (cc["mode"] == "all") & (cc["variable"] == "suicides")
               & cc["prof"].isin(["psychiatre", "psychologue"])].set_index("prof")
        if len(f):
            profs = [p for p in ["psychiatre", "psychologue"] if p in f.index]
            # un lien n'est présenté comme établi que si sa fourchette plausible (intervalle à 95 %) exclut zéro
            incertains = {p for p in profs if f.at[p, "ic95_bas"] < 0 < f.at[p, "ic95_haut"]}
            phr = [f"{nombre(f.at[p, 'rho_spearman'], 2)} pour les {pluriel(C.lab[p])} (fourchette plausible de "
                   f"{nombre(f.at[p, 'ic95_bas'], 2)} à {nombre(f.at[p, 'ic95_haut'], 2)})" for p in profs]
            texte = (f"Entre départements, la corrélation de rang entre le taux de décès par suicide et la densité de "
                     f"professionnels vaut {_liste(phr)}.")
            nets = [p for p in profs if p not in incertains]
            for sens in ("moins", "mieux"):
                g = [p for p in nets if (f.at[p, "rho_spearman"] < 0) == (sens == "moins")]
                if g:
                    texte += (f" Pour les {_liste(pluriel(C.lab[p]) for p in g)}, les départements où l'on meurt "
                              f"davantage par suicide sont plutôt {sens} dotés.")
            if incertains:
                texte += (f" Pour les {_liste(pluriel(C.lab[p]) for p in profs if p in incertains)}, aucun lien net "
                          f"n'apparaît, la corrélation est trop incertaine pour conclure, elle pourrait aussi bien être nulle.")
            if nets:
                texte += (" Un lien ne dit pas que l'offre protège du suicide, d'autres facteurs comme la ruralité, l'âge "
                          "ou l'isolement jouent sur les deux.")
            L += [texte, ""]
            L += _sensibilite_idf(C, incertains)
    return L


def _sensibilite_idf(C, incertains=frozenset()):
    """Corrélation avec et sans l'Île-de-France, où les suicides sont nettement sous-déclarés."""
    t = C.R.get("sensibilite_ile_de_france")
    if not isinstance(t, pd.DataFrame) or t.empty:
        return []
    x = t[(t["variable"] == "suicides") & t["prof"].isin(["psychiatre", "psychologue"])].set_index("prof")
    if x.empty:
        return []
    profs = [p for p in ["psychiatre", "psychologue"] if p in x.index]
    phr = [f"de {nombre(x.at[p, 'rho_tous'], 2)} à {nombre(x.at[p, 'rho_sans_ile_de_france'], 2)} pour les {pluriel(C.lab[p])}"
           for p in profs]
    # la conclusion dépend des chiffres, même sens et même force, ou lien qui change de catégorie
    # lien déjà trop incertain avec tous les départements, on dit seulement si le retrait de l'Île-de-France y change
    toujours = [p for p in profs if p in incertains and abs(x.at[p, "rho_sans_ile_de_france"]) <= abs(x.at[p, "rho_tous"])]
    renforces = [p for p in profs if p in incertains and p not in toujours]
    profs_nets = [p for p in profs if p not in incertains]
    stables = [p for p in profs_nets if np.sign(x.at[p, "rho_tous"]) == np.sign(x.at[p, "rho_sans_ile_de_france"])
               and force(x.at[p, "rho_tous"]) == force(x.at[p, "rho_sans_ile_de_france"])
               and abs(x.at[p, "rho_tous"] - x.at[p, "rho_sans_ile_de_france"]) < .05]
    autres = [p for p in profs_nets if p not in stables]
    fin = []
    if stables:
        fin.append(f"Pour les {_liste(pluriel(C.lab[p]) for p in stables)}, le sens et la force du lien ne changent pas.")
    if autres:
        fin.append(f"Pour les {_liste(pluriel(C.lab[p]) for p in autres)}, le lien change nettement, une partie tient donc "
                   f"à cette région et il est à lire avec plus de prudence.")
    if toujours:
        fin.append(f"Pour les {_liste(pluriel(C.lab[p]) for p in toujours)}, il n'apparaît toujours pas de lien net.")
    if renforces:
        fin.append(f"Pour les {_liste(pluriel(C.lab[p]) for p in renforces)}, la corrélation se renforce sans cette "
                   f"région, ce qui reste à lire avec prudence.")
    return [f"Sans les départements d'Île-de-France, où les suicides sont nettement sous-déclarés, cette corrélation "
            f"passe {_liste(phr)}. " + " ".join(fin), ""]


PUBLIC = {SM: ["q_psychiatrie_enfant", "pedopsychiatre"],
          SANTE: ["pediatre", "orthophoniste", "psychomotricien", "geriatre"]}


def _public_cible(C: Contexte, famille):
    """Densité rapportée au public concerné (point 13)."""
    rs = C.R.get("public_cible")
    if not isinstance(rs, pd.DataFrame) or rs.empty:
        return []
    t = rs[(rs["niveau"] == "epci") & rs["prof"].isin(PUBLIC[famille])].set_index("prof").reindex(PUBLIC[famille])
    t = t.dropna(subset=["public"]).reset_index()
    if t.empty:
        return []
    t["libelle"] = t["prof"].map(C.lab)
    r = t.iloc[0]
    L = ["### L'offre rapportée au public concerné", "",
         f"Rapportés aux habitants de {r['public']}, on compte {nombre(r['densite_nationale_cible'], 1)} "
         f"{pluriel(r['libelle'])} pour 10 000. {pct(r['part_public_sans_professionnel']).capitalize()} d'entre eux "
         f"vivent dans une intercommunalité qui n'en compte aucun."
         + (" Pour ces professions, rapporter la densité au public concerné change peu le classement des territoires."
            if t["rho_classements"].min() >= .95 else
            " Rapporter la densité au public concerné modifie sensiblement le classement des territoires pour "
            + _liste(pluriel(x) for x in t.loc[t["rho_classements"] < .95, "libelle"]) + "."), "",
         _tableau(t, ["libelle", "public", "densite_nationale_cible", "gini_population", "gini_public",
                      "part_public_sans_professionnel", "rho_classements"],
                  ["Profession", "Public concerné", "Pour 10 000 personnes du public", "Inégalité, par habitant",
                   "Inégalité, par personne du public", "Public sans ce professionnel dans son intercommunalité",
                   "Ressemblance des classements"],
                  {"densite_nationale_cible": lambda v: nombre(v, 1), "gini_population": lambda v: nombre(v, 2),
                   "gini_public": lambda v: nombre(v, 2), "part_public_sans_professionnel": pct,
                   "rho_classements": lambda v: nombre(v, 2)}), ""]
    L += _comment_lire(
        "Une densité rapportée à toute la population peut tromper. Un territoire qui compte peu de personnes de "
        f"{r['public']} peut sembler bien doté en {pluriel(r['libelle'])} pour cette seule raison. Ici chaque "
        "profession est rapportée au public qu'elle soigne surtout.",
        "Les deux colonnes d'inégalité comparent l'indice de Gini calculé par habitant et par personne du public. La "
        "dernière colonne indique si les territoires se classent de la même façon dans les deux cas, 1 voulant dire "
        "un classement identique.")
    L += _plus_loin(["Publics tirés du recensement 2023. Le recensement publie les moins de 15 ans et non les moins de "
                     "18 ans, ce qui sous-estime le public des professions de l'enfance. Ressemblance des classements, "
                     "corrélation de rang de Spearman entre densité par habitant et densité par personne du public, "
                     "sur les intercommunalités. Détails dans public_cible.csv et public_cible_territoires.csv."])
    return L


def _modes(C: Contexte, famille):
    """Libéral ou salarié, d'où viennent les inégalités (point 16)."""
    ineg = C.R.get("inegalites")
    co = C.R.get("concentration_revenu")
    if not isinstance(ineg, pd.DataFrame) or ineg.empty:
        return []
    profs = [p for p in PRINCIPALES[famille] if C.present(p)]
    g = ineg[(ineg["niveau"] == "epci")].pivot_table(index="prof", columns="mode", values="gini")
    nat = C.agg.national.pivot_table(index="prof", columns="mode", values="n", fill_value=0)
    lignes = []
    for p in profs:
        if p not in g.index or "lib" not in g or "sal" not in g:
            continue
        ci = {}
        if isinstance(co, pd.DataFrame) and "mode" in co:
            x = co[(co["niveau"] == "epci") & (co["prof"] == p)].set_index("mode")["indice_concentration"]
            ci = x.to_dict()
        lignes.append({"libelle": C.lab[p], "part_lib": nat.at[p, "lib"] / max(nat.at[p, "all"], 1),
                       "gini_lib": g.at[p, "lib"], "gini_sal": g.at[p, "sal"],
                       "ci_lib": ci.get("lib"), "ci_sal": ci.get("sal")})
    if not lignes:
        return []
    T = pd.DataFrame(lignes)
    r = T.iloc[0]
    plus = "libéral" if r["gini_lib"] > r["gini_sal"] else "salarié"
    tete = (f"Pour les {pluriel(r['libelle'])}, l'exercice {plus} est un peu plus inégalement réparti entre "
            f"intercommunalités (indice de Gini {nombre(r['gini_lib'], 2)} en libéral, {nombre(r['gini_sal'], 2)} en "
            f"salarié)." if abs(r["gini_lib"] - r["gini_sal"]) < .05 else
            f"Pour les {pluriel(r['libelle'])}, l'exercice {plus} est nettement plus inégalement réparti entre "
            f"intercommunalités (indice de Gini {nombre(r['gini_lib'], 2)} en libéral, {nombre(r['gini_sal'], 2)} en "
            f"salarié).")
    if pd.notna(r["ci_lib"]) and pd.notna(r["ci_sal"]) and abs(r["ci_lib"] - r["ci_sal"]) >= .05:
        aise = "libéral" if r["ci_lib"] > r["ci_sal"] else "salarié"
        autre = "salarié" if aise == "libéral" else "libéral"
        tete += (f" Surtout, l'exercice {aise} est davantage présent dans les territoires aisés (indice de "
                 f"concentration {nombre(max(r['ci_lib'], r['ci_sal']), 2)}) que l'exercice {autre} "
                 f"({nombre(min(r['ci_lib'], r['ci_sal']), 2)}).")
    L = ["### Libéral ou salarié", "", tete, "",
         _tableau(T, ["libelle", "part_lib", "gini_lib", "gini_sal", "ci_lib", "ci_sal"],
                  ["Profession", "Part exerçant en libéral", "Inégalité, libéral", "Inégalité, salarié",
                   "Concentration selon le niveau de vie, libéral", "Concentration selon le niveau de vie, salarié"],
                  {"part_lib": pct, "gini_lib": lambda v: nombre(v, 2), "gini_sal": lambda v: nombre(v, 2),
                   "ci_lib": lambda v: nombre(v, 2), "ci_sal": lambda v: nombre(v, 2)}, vide="non calculée"), ""]
    L += _comment_lire(
        "Les professionnels libéraux choisissent leur lieu d'installation, les salariés travaillent là où se "
        "trouvent les hôpitaux, centres et établissements. Comparer les deux montre d'où viennent les inégalités.",
        "Une concentration positive signifie une présence plus forte dans les territoires aisés, négative dans les "
        "territoires modestes. Une même personne peut exercer dans les deux modes et compte alors dans chacun.")
    L += _plus_loin(["Indices de Gini entre intercommunalités par mode d'exercice, indices de concentration selon le "
                     "niveau de vie médian avec leurs intervalles de confiance dans concentration_revenu.csv (colonne "
                     "mode)."])
    return L


def _composition(C: Contexte):
    """Combinaisons d'offre (point 14) et psychologues par psychiatre (point 15)."""
    cb, comp = C.R.get("combinaisons"), C.R.get("composition_sante_mentale")
    if not isinstance(cb, pd.DataFrame) or cb.empty:
        return []
    t = cb[cb["niveau"] == "epci"].copy()
    oui = lambda b: "oui" if b else "non"  # noqa: E731
    for c in ["medecin_generaliste", "psychologue", "psychiatre"]:
        t[c] = t[c].map(oui)
    t = t.sort_values("population", ascending=False)
    g_sans = cb[(cb["niveau"] == "epci") & cb["medecin_generaliste"] & ~cb["psychologue"] & ~cb["psychiatre"]]
    p_sans = cb[(cb["niveau"] == "epci") & cb["psychologue"] & ~cb["psychiatre"]]
    L = ["### Quelles professions sont présentes ensemble", "",
         f"{pct(p_sans['part_population'].sum()).capitalize()} des habitants vivent dans une intercommunalité qui "
         f"compte au moins un psychologue mais aucun psychiatre, et {pct(g_sans['part_population'].sum())} dans une "
         f"intercommunalité qui a un médecin généraliste mais ni psychologue ni psychiatre.", "",
         _tableau(t, ["medecin_generaliste", "psychologue", "psychiatre", "territoires", "population", "part_population"],
                  ["Médecin généraliste", "Psychologue", "Psychiatre", "Intercommunalités", "Habitants", "Part des habitants"],
                  {"territoires": nombre, "population": nombre, "part_population": pct}), ""]
    L += _comment_lire("Chaque ligne est une combinaison de présence ou d'absence des trois professions dans "
                       "l'intercommunalité. Absence ne veut pas dire absence d'accès, le professionnel le plus "
                       "proche peut exercer dans l'intercommunalité voisine.", C.phrase_cmp(),
                       limites.phrase_md(["prof:psychiatre"]))
    if isinstance(comp, pd.DataFrame) and not comp.empty:
        d = comp[comp["niveau"] == "dep"].dropna(subset=["psychologues_par_psychiatre"]).copy()
        if len(d):
            ratio_fr = C.nat.get("psychologue", 0) / max(C.nat.get("psychiatre", 1), 1)
            lo, hi = d.loc[d["psychologues_par_psychiatre"].idxmin()], d.loc[d["psychologues_par_psychiatre"].idxmax()]
            L += ["#### Psychologues pour un psychiatre", "",
                  f"En France, on compte {nombre(ratio_fr, 1)} psychologues pour un psychiatre. Selon les "
                  f"départements, ce rapport va de {nombre(lo['psychologues_par_psychiatre'], 1)} à "
                  f"{nombre(hi['psychologues_par_psychiatre'], 1)}, avec une médiane de "
                  f"{nombre(d['psychologues_par_psychiatre'].median(), 1)}.", ""]
            L += _comment_lire("Ce rapport décrit la composition de l'offre en santé mentale, pas sa quantité. Un "
                               "rapport élevé signale une offre qui repose surtout sur les psychologues. Les deux "
                               "professions ne sont pas interchangeables, ce rapport se lit à côté des densités et "
                               "ne forme pas un score.")
    L += _plus_loin(["Combinaisons aussi calculées par commune dans combinaisons.csv. Rapport par département et par "
                     "intercommunalité dans composition_sante_mentale.csv, vide quand le territoire ne compte aucun "
                     "psychiatre."])
    return L


PRINC = {SM: "psychologue", SANTE: "medecin_generaliste"}


def _zones(C: Contexte, famille):
    """Zones de désert et de concentration, Moran local (point 4)."""
    li = C.R.get("lisa")
    if not isinstance(li, pd.DataFrame) or li.empty:
        return []
    profs = [p for p in PRINCIPALES[famille] if p in set(li["prof"])]
    lignes = []
    for p in profs:
        x = li[li["prof"] == p]
        d, c = x[x["zone"] == "desert"], x[x["zone"] == "concentration"]
        lignes.append({"libelle": C.lab[p], "desert_n": len(d), "desert_pop": d["population"].sum() / C.pop_epci.sum(),
                       "conc_n": len(c), "conc_pop": c["population"].sum() / C.pop_epci.sum()})
    T = pd.DataFrame(lignes)
    p0 = PRINC[famille]
    x0 = li[(li["prof"] == p0) & (li["zone"] == "desert")].sort_values("population", ascending=False)
    dep_epci = C.ref.epci.set_index("code")["dep"]
    om = x0["code"].map(dep_epci).isin(config.DEPS_DROM)
    drom = x0[om]
    exemples = f" {nombre(len(drom))} de ces intercommunalités sont outre-mer." if len(drom) else ""
    L = ["### Zones de désert et de concentration", "",
         f"Pour les {pluriel(C.lab[p0])}, {len(x0)} intercommunalités, où vivent {pct(x0['population'].sum() / C.pop_epci.sum())} "
         f"des habitants, forment des zones peu dotées entourées de territoires eux aussi peu dotés." + exemples, "",
         _tableau(T, ["libelle", "desert_n", "desert_pop", "conc_n", "conc_pop"],
                  ["Profession", "Intercommunalités en zone peu dotée", "Habitants concernés",
                   "Intercommunalités en zone de concentration", "Habitants concernés"],
                  {"desert_n": nombre, "desert_pop": pct, "conc_n": nombre, "conc_pop": pct}), ""]
    L += _comment_lire(
        "Un territoire mal doté n'est pas forcément un désert. S'il est entouré de territoires bien dotés, ses "
        "habitants peuvent consulter à côté. Une zone peu dotée réunit au contraire des territoires voisins tous en "
        "dessous de la moyenne, ce qui rend le recours de proximité plus difficile. Une zone de concentration est "
        "l'inverse. La carte de ces zones se trouve dans l'atlas (affichage « Zones »).")
    L += _plus_loin(["Indice de Moran local (LISA) sur le logarithme de la densité, voisinage par contiguïté, poids "
                     "normalisés par ligne, p-valeur par approximation normale sous randomisation (Anselin, 1995), "
                     "correction de Benjamini-Hochberg par profession (q < 0,05). Les p-valeurs par permutations "
                     "ont un plancher (1 sur le nombre de permutations) qui empêche la correction d'aboutir sur plus "
                     "d'un millier de territoires. Les territoires qui contrastent avec leurs voisins "
                     "(bien doté entouré de peu dotés, et inversement) sont dans lisa.csv."])
    return L


# formes utilisées dans les phrases de tête, par identifiant d'équipement (config.ACCES_ROUTE)
EQ_PHRASE = {"psychologue_liberal": "d'un psychologue libéral", "psychiatre_liberal": "d'un psychiatre libéral",
             "psychiatrie_ambulatoire": "d'une structure de psychiatrie ambulatoire comme un CMP",
             "generaliste_liberal": "d'un médecin généraliste libéral", "urgences": "d'un service d'urgences",
             "orthophoniste_liberal": "d'un orthophoniste libéral", "pediatre_liberal": "d'un pédiatre libéral"}
EQ_TETE = {SM: ["psychologue_liberal", "psychiatre_liberal", "psychiatrie_ambulatoire"],
           SANTE: ["generaliste_liberal", "pediatre_liberal", "urgences"]}


def _route(C: Contexte, famille):
    """Temps de trajet par la route (INSEE), et comparaison de nos indicateurs avec ceux de l'INSEE et de la DREES."""
    ta, ar = C.R.get("temps_acces"), C.externes.get("acces_route")
    if not isinstance(ta, pd.DataFrame) or ta.empty or not ar:
        return []
    fam = {d["id"]: d["famille"] for d in ar["defs"]}
    t = ta[(ta["niveau"] == "FR") & ta["equipement"].map(fam).eq(famille)].copy()
    ordre = [d["id"] for d in ar["defs"]]
    t = t.set_index("equipement").reindex([i for i in ordre if i in set(t["equipement"])]).reset_index()
    if t.empty:
        return []
    v = t.set_index("equipement")
    tete = [e for e in EQ_TETE[famille] if e in v.index]
    phr = []
    if tete:
        e0 = tete[0]
        phr.append(f"Par la route, la moitié des habitants vit à moins de {nombre(v.at[e0, 'temps_median_min'], 0)} "
                   f"minutes {EQ_PHRASE[e0]}.")
        reste = [f"{pct(v.at[e, 'part_population_a_plus_de_20_min'])} à plus de 20 minutes {EQ_PHRASE[e]}"
                 for e in tete[1:]]
        if reste:
            phr.append(f"Ils sont {_liste(reste)}.")
    L = ["#### Temps de trajet par la route", "", " ".join(phr), ""] + graphique(
        "unites_" + ("sm" if famille == SM else "sante")) + [
         _tableau(t, ["libelle", "temps_median_min", "temps_moyen_min", "part_population_a_plus_de_15_min",
                      "part_population_a_plus_de_20_min", "part_population_a_plus_de_30_min"],
                  ["Équipement ou professionnel le plus proche", "Temps médian (min)", "Temps moyen (min)",
                   "À plus de 15 min", "À plus de 20 min", "À plus de 30 min"],
                  {"temps_median_min": lambda x: nombre(x, 0), "temps_moyen_min": lambda x: nombre(x, 0),
                   "part_population_a_plus_de_15_min": pct, "part_population_a_plus_de_20_min": pct,
                   "part_population_a_plus_de_30_min": pct}), ""]
    L += _comment_lire(
        "Ces durées sont celles d'un trajet en voiture, aux heures creuses, depuis le lieu de résidence vers "
        "l'équipement le plus proche, même s'il se trouve dans un autre département. Pour les personnes sans "
        "voiture, le trajet est souvent plus long. Les professionnels sont ceux qui exercent en libéral. Ceux qui "
        + ("sont salariés d'un hôpital ou d'un CMP sont pris en compte à travers les structures." if famille == SM else
           "sont salariés d'un hôpital sont pris en compte à travers les structures, comme les services d'urgences."),
        "Le plus proche n'est pas toujours disponible. Un professionnel peut ne plus accepter de nouveaux patients, "
        "avoir des délais longs ou pratiquer des dépassements d'honoraires. Ce tableau mesure une proximité, pas un "
        "accès effectif.",
        "Le lien entre ces temps de trajet et le taux de suicide est décrit plus bas, dans la partie sur les besoins "
        "(section [« Croisements entre bases »](#croisements-entre-bases))." if famille == SM else "")
    cr, ca = C.R.get("comparaison_route"), C.R.get("comparaison_apl")
    plus = [f"Source, INSEE, données sur la localisation et l'accès de la population aux "
            f"équipements, millésime {ar['annee']} de la base permanente des équipements, distancier Metric-OSRM "
            f"(© les contributeurs d'OpenStreetMap et du projet OSRM), Licence Ouverte. Durées calculées pour chaque "
            f"carreau habité de 200 m, pondérées par sa population (source Filosofi). La Guadeloupe, la Guyane et "
            f"Mayotte ne sont pas couvertes. Médiane estimée à partir des durées regroupées par minute. Valeurs par "
            f"région, département et intercommunalité dans temps_acces.csv."]
    if isinstance(cr, pd.DataFrame) and len(cr):
        cr = cr[cr["prof"].isin(PRINCIPALES[famille])]
        if len(cr):
            proche = "de façon très proche" if cr["rho_spearman"].min() >= .8 else "de façon assez proche"                 if cr["rho_spearman"].min() >= .6 else "de façon seulement en partie semblable"
            plus.append("Commune par commune, la distance à vol d'oiseau utilisée plus haut et le temps de trajet de "
                        f"l'INSEE se classent {proche} (corrélation de rang "
                        + _liste([f"{nombre(r['rho_spearman'], 2)} pour les {pluriel(C.lab[r['prof']])}"
                                  for _, r in cr.iterrows()])
                        + "), alors même que la distance compte tous les professionnels et le temps de trajet les "
                          "seuls libéraux.")
    if isinstance(ca, pd.DataFrame) and len(ca):
        ca = ca.sort_values("rho_epci", ascending=False)
        faible = ca[ca["rho_epci"] < .5]
        txt = ("La DREES publie l'accessibilité potentielle localisée (APL) pour cinq professions. Calculée avec les "
               f"seuls libéraux, comme l'APL ({int(ca['annee_apl'].max())}), l'accessibilité calculée ici classe les "
               "intercommunalités de façon " + ("proche" if ca["rho_epci"].min() >= .7 else "inégalement proche")
               + " (corrélation de rang "
               + _liste([f"{nombre(r['rho_epci'], 2)} pour les {pluriel(C.lab[r['prof']])}" for _, r in ca.iterrows()])
               + "). ")
        gain = ca["rho_epci"] - ca["rho_densite_epci"]
        nets = ca.loc[gain >= .1, "prof"]
        txt += ("Par rapport à la simple densité de libéraux, la prise en compte des communes voisines "
                + (f"améliore nettement l'accord pour les {_liste([pluriel(C.lab[p]) for p in nets])} et " if len(nets) else "")
                + ("change peu de chose pour " + ("les autres professions" if len(nets) else "ces professions")
                   + " (de " + nombre(gain[gain < .1].min(), 2) + " à +" + nombre(gain[gain < .1].max(), 2) + "). "
                   if (gain < .1).any() else ". "))
        if len(faible):
            txt += ("Les écarts les plus grands, pour les "
                    + _liste([pluriel(C.lab[p]) for p in faible["prof"]])
                    + ", tiennent sans doute à ce que l'APL pondère chaque professionnel par son activité réelle et "
                      "la population par ses besoins selon l'âge, ce que les données ouvertes ne permettent pas de "
                      "faire ici. ")
        txt += ("L'APL n'existe pas pour les psychologues ni pour les psychiatres. Pour eux, l'accessibilité calculée "
                "ici reste une approximation, à lire avec ces limites, et les temps de trajet de l'INSEE "
                "donnent une mesure de proximité plus robuste. Détail dans comparaison_apl.csv.")
        plus.append(txt)
    L += _plus_loin(plus)
    return L


def _phrase_sensibilite(C):
    se = C.R.get("sensibilite_accessibilite")
    if not isinstance(se, pd.DataFrame) or se.empty:
        return ""
    return (f"Solidité face au choix de la portée (20 km), en la ramenant à 10 km ou en la portant à 30 km, les "
            f"intercommunalités se classent de façon semblable (corrélation de rang de {nombre(se['rho_epci'].min(), 2)} "
            f"à {nombre(se['rho_epci'].max(), 2)} selon la profession), et de {pct(se['quart_bas_conserve'].min(), 0)} à "
            f"{pct(se['quart_bas_conserve'].max(), 0)} des intercommunalités du quart le moins accessible y restent. "
            f"Détail dans sensibilite_accessibilite.csv.")


def _acces(C: Contexte, famille):
    """Accessibilité, distance au plus proche et méthode à deux étapes (points 5 et 18)."""
    ac, ae, om = C.R.get("accessibilite"), C.R.get("accessibilite_epci"), C.R.get("ombre_urbaine")
    if not isinstance(ac, pd.DataFrame) or ac.empty:
        return []
    profs = [p for p in PRINCIPALES[famille] if p in set(ac["prof"])]
    t = ac.set_index("prof").loc[profs].reset_index()
    t["libelle"] = t["prof"].map(C.lab)
    for p in profs:   # ressemblance entre densité et accessibilité, par intercommunalité
        a = ae[ae["prof"] == p].set_index("epci")["accessibilite"].reindex(C.d_epci.index)
        t.loc[t["prof"] == p, "rho"] = stats.spearmanr(C.d_epci[p], a, nan_policy="omit")[0]
    r = t.iloc[0]
    rare = t.loc[t["part_population_a_plus_de_10_km"].idxmax()]
    L = ["### Distance et accessibilité", "",
         f"{pct(r['part_population_dans_la_commune']).capitalize()} des habitants ont au moins un "
         f"{C.lab[r['prof']].lower()} dans leur commune, et {pct(r['part_population_a_plus_de_10_km'])} vivent à plus "
         f"de 10 km à vol d'oiseau du plus proche."
         + (f" Pour les {pluriel(rare['libelle'])}, c'est {pct(rare['part_population_a_plus_de_10_km'])} des habitants "
            f"qui vivent à plus de 10 km." if rare["prof"] != r["prof"] else ""), "",
         _tableau(t, ["libelle", "part_population_dans_la_commune", "part_population_a_plus_de_5_km",
                      "part_population_a_plus_de_10_km", "part_population_a_plus_de_20_km",
                      "part_population_a_plus_de_30_km", "rho"],
                  ["Profession", "Habitants avec ce professionnel dans leur commune", "À plus de 5 km", "À plus de 10 km",
                   "À plus de 20 km", "À plus de 30 km", "Ressemblance densité et accessibilité"],
                  {"part_population_dans_la_commune": pct, "part_population_a_plus_de_5_km": pct,
                   "part_population_a_plus_de_10_km": pct, "part_population_a_plus_de_20_km": pct,
                   "part_population_a_plus_de_30_km": pct, "rho": lambda v: nombre(v, 2)}), ""]
    L += graphique("distance_" + ("sm" if famille == SM else "sante"))
    L += _comment_lire(
        "La distance est mesurée à vol d'oiseau entre le centre de la commune de résidence et le centre de la "
        "commune la plus proche où exerce au moins un professionnel. Elle est nulle quand un professionnel exerce "
        "dans la commune. Les trajets réels sont plus longs.",
        "L'accessibilité tient compte à la fois de la distance et de la concurrence entre habitants pour les mêmes "
        "professionnels, y compris ceux des communes voisines. Elle s'exprime, comme une densité, en professionnels "
        "pour 10 000 habitants. La dernière colonne indique si les intercommunalités se classent de la même façon "
        "selon la densité et selon l'accessibilité, 1 voulant dire un classement identique.")
    if isinstance(om, pd.DataFrame) and not om.empty:
        p0 = PRINC[famille]
        x = om[om["prof"] == p0]
        o, d = x[x["categorie"] == "ombre_urbaine"], x[x["categorie"] == "desert"]
        if len(x):
            dep_epci = C.ref.epci.set_index("code")["dep"]
            d = d.sort_values("population", ascending=False)
            om = d["code"].map(dep_epci).isin(config.DEPS_DROM)
            ex = f" {nombre(int(om.sum()))} de ces intercommunalités sont outre-mer." if om.any() else ""
            L += [f"Parmi les intercommunalités du quart le moins bien doté en {pluriel(C.lab[p0])}, {len(o)} gardent une "
                  f"accessibilité au-dessus de la médiane, parce que des professionnels exercent juste à côté. Elles "
                  f"relèvent plutôt de l'ombre d'un pôle voisin. À l'inverse, {len(d)}, où vivent "
                  f"{nombre(d['population'].sum())} habitants, restent aussi dans le quart le moins accessible." + ex, ""]
    L += _plus_loin([
        "Accessibilité potentielle à deux étapes (méthode 2SFCA avec décroissance par paliers), inspirée de "
        "l'accessibilité potentielle localisée (APL) de la DREES, avec deux différences importantes. Les distances "
        "sont à vol d'oiseau et non en temps de trajet, avec des paliers de poids 1 jusqu'à 10 km, 0,66 de 10 à "
        "15 km, 0,33 de 15 à 20 km et 0 au-delà. L'offre est un nombre de personnes et non un volume d'activité, et "
        "la demande n'est pas pondérée par l'âge. La DREES ne publie l'APL que pour les médecins généralistes, "
        "infirmiers, masseurs-kinésithérapeutes, sages-femmes et chirurgiens-dentistes. Pour les psychologues et "
        "les psychiatres, cet indicateur est une première approche. Centres des communes calculés à partir des "
        "contours communaux (point intérieur du plus grand morceau). Valeurs par commune dans "
        "accessibilite_communes.csv, par intercommunalité dans accessibilite_epci.csv.", _phrase_sensibilite(C)])
    return L + _route(C, famille)


FINANCIER = {SM: ["psychiatre"], SANTE: ["pediatre", "gynecologue", "ophtalmologue", "medecin_generaliste"]}


def _financier(C: Contexte, famille):
    """Accès financier aux spécialistes libéraux (secteur conventionnel) et accès au médecin traitant."""
    ac = C.externes.get("ameli_acces")
    if not ac or ac.get("secteurs") is None:
        return []
    t = ac["secteurs"]
    lab = {i: l for _p, i, l, _f in config.AMELI_SECTEURS_PROFESSIONS}
    fr = t[(t["niveau"] == "FR") & t["prof"].isin(FINANCIER[famille])].set_index("prof").reindex(FINANCIER[famille]).dropna(how="all")
    if fr.empty:
        return []
    dep = t[(t["niveau"] == "dep") & ~t["code"].isin(config.AMELI_DEPARTEMENTS_EXCLUS)]
    fr["libelle"] = fr.index.map(lab)
    fr["autres"] = fr["secteur_2_sans_optam"] + fr["non_conventionnes"]
    fr["mediane"] = [dep.loc[dep["prof"] == p, "part_depassements"].median() for p in fr.index]
    p0 = fr.index[0]
    d0 = dep.loc[dep["prof"] == p0, "part_depassements"].dropna()
    L = ["### Accès financier", "",
         f"En {fr['annee'].iloc[0]}, {pct(fr.at[p0, 'part_depassements'])} des {fr.at[p0, 'libelle'].lower()} libéraux "
         f"peuvent pratiquer des dépassements d'honoraires, dont {pct(fr.at[p0, 'part_depassements_libres'])} sans "
         f"l'encadrement de l'Optam. Selon les départements, cette part va de {pct(d0.min())} à {pct(d0.max())}.", "",
         _tableau(fr.reset_index(), ["libelle", "liberaux", "secteur_1", "secteur_2_optam", "autres", "part_depassements",
                                     "mediane"],
                  ["Profession", "Libéraux conventionnés ou non", "Secteur 1", "Secteur 2 avec Optam",
                   "Secteur 2 sans Optam ou non conventionnés", "Pouvant pratiquer des dépassements",
                   "Milieu des départements"],
                  {"liberaux": nombre, "secteur_1": nombre, "secteur_2_optam": nombre, "autres": nombre,
                   "part_depassements": pct, "mediane": pct}), ""]
    L += _comment_lire(
        "En secteur 1, le médecin applique le tarif de la Sécurité sociale. En secteur 2, il peut le dépasser. "
        "L'Optam est un engagement à limiter ces dépassements. Un médecin non conventionné fixe librement ses "
        "honoraires, presque sans remboursement. Ces chiffres mesurent un obstacle financier possible, pas les "
        "dépassements réellement facturés, et ne concernent que les libéraux."
        + (" Les CMP ne facturent pas de dépassement." if famille == SM else ""))
    plus = [f"Source, Assurance Maladie, effectifs de libéraux par secteur conventionnel, année {fr['annee'].iloc[0]}, "
            f"licence ODbL. Part non calculée pour un département qui compte moins de "
            f"{config.AMELI_SECTEURS_EFFECTIF_MIN} libéraux de la profession. Mayotte est exclue. Valeurs par "
            f"département dans contexte_dep_odbl.csv."]
    ald = ac.get("ald")
    if famille == SANTE and ald is not None and not ald.empty:
        a = ald[(ald["niveau"] == "dep") & ~ald["code"].isin(config.AMELI_DEPARTEMENTS_EXCLUS)].set_index("code")["valeur"].dropna()
        v_fr = ald.loc[ald["niveau"] == "FR", "valeur"]
        n, d, _pop = tables(C.agg, C.ref, "dep", "all")
        lien = ""
        if "medecin_generaliste" in d and len(a) > 20:
            j = pd.concat([a.rename("ald"), d["medecin_generaliste"].rename("dens")], axis=1).dropna()
            rho = stats.spearmanr(j["ald"], j["dens"])[0]
            lien = (f" Entre départements, cette part et la densité de médecins généralistes ont un lien "
                    f"{force(rho)} (rho = {nombre(rho, 2)}), "
                    + ("les départements mieux dotés ayant moins de patients sans médecin traitant." if rho < -.3 else
                       "ce qui montre que la densité seule ne dit pas tout de l'accès au médecin traitant."))
        L += ["#### Patients sans médecin traitant", "",
              f"En {ald['annee'].iloc[0]}, {nombre(v_fr.iloc[0], 1) if len(v_fr) else ''} % des patients en affection "
              f"longue durée n'ont pas déclaré de médecin traitant. Selon les départements, cette part va de "
              f"{nombre(a.min(), 1)} % à {nombre(a.max(), 1)} %, avec une médiane de {nombre(a.median(), 1)} %." + lien, ""]
        L += _comment_lire("Une affection longue durée est une maladie chronique grave (diabète, cancer, trouble "
                           "psychiatrique de longue durée...). Ces patients ont particulièrement besoin d'un médecin "
                           "traitant. Ne pas en avoir peut traduire une difficulté à en trouver un, mais aussi un "
                           "suivi organisé autrement.")
        plus.append(f"Source, Assurance Maladie, part des patients en affection longue durée sans médecin traitant, "
                    f"année {ald['annee'].iloc[0]}, licence ODbL.")
    if "#### Patients sans médecin traitant" in L:
        L[0] = "### Accès financier et médecin traitant"
    L += _plus_loin(plus)
    return L


def _hopital(C: Contexte):
    """Psychiatrie à l'hôpital, d'après la SAE (lits, places, CMP, temps plein de psychiatres et psychologues)."""
    sae = C.externes.get("sae")
    if not sae:
        return []
    t = sae["table"]
    defs = {d["id"]: d for d in sae["defs"]}
    lignes = []
    for iid, d in defs.items():
        fr = t[(t["niveau"] == "FR") & (t["indicateur"] == iid)]
        x = t[(t["niveau"] == "dep") & (t["indicateur"] == iid)]["valeur"].dropna()
        if fr.empty:
            continue
        lignes.append({"id": iid, "libelle": d["libelle"], "unite": d["unite"], "nombre": fr["nombre"].iloc[0],
                       "france": fr["valeur"].iloc[0], "mediane": x.median(), "vmin": x.min(), "vmax": x.max()})
    if not lignes:
        return []
    T = pd.DataFrame(lignes).set_index("id")
    f = lambda v: nombre(v, 1)  # noqa: E731
    tete = []
    if "sae_lits_psy" in T.index:
        tete.append(f"{nombre(T.at['sae_lits_psy', 'nombre'])} lits d'hospitalisation à temps plein")
    if "sae_cmp" in T.index:
        tete.append(f"{nombre(T.at['sae_cmp', 'nombre'])} centres médico-psychologiques")
    if "sae_etp_psychiatres" in T.index:
        tete.append(f"l'équivalent de {nombre(T.at['sae_etp_psychiatres', 'nombre'])} psychiatres salariés à temps plein")
    L = ["### Psychiatrie à l'hôpital", "",
         f"En {sae.get('annee', '')}, les établissements autorisés en psychiatrie déclarent {_liste(tete)}."
         + (f" Le répertoire compte {nombre(C.nat['psychiatre'])} psychiatres, tous modes d'exercice confondus."
            if C.present("psychiatre") else ""), "",
         _tableau(T.reset_index(), ["libelle", "nombre", "france", "unite", "mediane", "vmin", "vmax"],
                  ["Indicateur", "Total en France", "Taux en France", "Unité", "Médiane des départements", "Le plus bas",
                   "Le plus haut"],
                  {"nombre": nombre, "france": f, "mediane": f, "vmin": f, "vmax": f}), ""]
    L += _comment_lire(
        "La SAE décrit les établissements, alors que le répertoire décrit les personnes. Elle compte des équivalents "
        "temps plein, ce qui corrige en partie une limite du répertoire, qui ne dit rien du temps de travail. Les deux "
        "se lisent côte à côte.",
        "Chaque établissement est rattaché au département où il est enregistré, même si certains de ses CMP ou "
        "hôpitaux de jour sont situés dans un département voisin. Un département sans établissement de psychiatrie "
        "affiche zéro, ses habitants étant suivis par un établissement voisin.")
    L += _plus_loin([f"Source, DREES, Statistique annuelle des établissements de santé {sae.get('annee', '')}, bases "
                     "statistiques (données corrigées de la non-réponse), bordereau psychiatrie, total des "
                     "disciplines générale, infanto-juvénile et pénitentiaire. Licence Ouverte. La file active compte "
                     "un patient une fois par établissement, un patient suivi par deux établissements compte deux fois. "
                     "Valeurs par département dans contexte_dep.csv."])
    return L


def _enfance_handicap(C: Contexte, famille):
    """Indicateurs sociaux départementaux de la DREES, protection de l'enfance (santé mentale) et handicap (santé)."""
    isd = C.externes.get("drees_isd")
    if not isd:
        return []
    defs = [d for d in isd["defs"] if d["famille"] == famille]
    t = isd["table"]
    lignes = []
    for d in defs:
        x = t[(t["niveau"] == "dep") & (t["indicateur"] == d["id"])].set_index("code")["valeur"]
        x = x[x.index.isin(C.ref.deps["code"])].dropna()
        if len(x):
            lignes.append({"id": d["id"], "libelle": d["libelle"], "unite": d["unite"], "annee": d.get("annee", ""),
                           "mediane": x.median(), "vmin": x.min(), "vmax": x.max()})
    if not lignes:
        return []
    T = pd.DataFrame(lignes)
    f = lambda v: nombre(v, 1 if abs(v) >= 1 else 2)  # noqa: E731
    r = T.iloc[0]
    if famille == SM:
        titre = "#### Protection de l'enfance"
        tete = (f"En {r['annee']}, la part des jeunes de 0 à 20 ans suivis par l'aide sociale à l'enfance va de "
                f"{f(r['vmin'])} % à {f(r['vmax'])} % selon les départements, avec une médiane de {f(r['mediane'])} %.")
        lire = ("Les enfants suivis par l'aide sociale à l'enfance vivent plus souvent des situations qui pèsent sur "
                "leur santé mentale. Ces chiffres décrivent l'activité de protection de l'enfance des départements, "
                "pas un besoin de soins, et dépendent aussi des pratiques de chaque département.")
    else:
        titre = "### Handicap"
        e = T.set_index("id")
        tete = (f"Selon les départements, le nombre de places en établissement pour enfants en situation de handicap "
                f"va de {f(e.at['handicap_places_enfants', 'vmin'])} à {f(e.at['handicap_places_enfants', 'vmax'])} pour "
                f"1 000 jeunes de moins de 20 ans." if "handicap_places_enfants" in e.index else "")
        lire = ("Ces indicateurs décrivent les prestations versées aux personnes en situation de handicap et l'offre "
                "médico-sociale pour les enfants. Ils se lisent à côté de l'offre en orthophonie, psychomotricité et "
                "pédiatrie, dont ces enfants ont souvent besoin.")
    L = [titre, "", tete, "",
         _tableau(T, ["libelle", "unite", "annee", "mediane", "vmin", "vmax"],
                  ["Indicateur", "Unité", "Année", "Médiane des départements", "Le plus bas", "Le plus haut"],
                  {"mediane": f, "vmin": f, "vmax": f}), ""]
    L += _comment_lire(lire)
    L += _plus_loin(["Source, DREES, indicateurs sociaux départementaux, Licence Ouverte. Valeurs par département dans "
                     "contexte_dep.csv. Ces indicateurs ne servent pas au calcul de l'effectif attendu."])
    return L


def _porte(C: Contexte, famille):
    """Qui porte l'offre, par grand secteur et classe de densité (point 9)."""
    po = C.R.get("porte_offre")
    p0 = PRINC[famille]
    if not isinstance(po, pd.DataFrame) or po.empty or p0 not in set(po["prof"]):
        return []
    t = po[po["prof"] == p0].pivot_table(index="groupe", columns="classe", values="part", fill_value=0)
    ordre = [c[2] for c in CLASSES_DENSITE if c[2] in t.columns] + (["Ensemble"] if "Ensemble" in t.columns else [])
    t = t[ordre].sort_values("Ensemble" if "Ensemble" in ordre else ordre[-1], ascending=False)
    lib = config.SECTEURS_GROUPES[0][1]
    phr = ""
    if lib in t.index and len(ordre) >= 2:
        a, b = t.at[lib, ordre[0]], t.at[lib, [o for o in ordre if o != "Ensemble"][-1]]
        phr = (f"Dans les intercommunalités très peu denses, {pct(a)} des lieux d'exercice des {pluriel(C.lab[p0])} sont "
               f"libéraux, contre {pct(b)} dans les intercommunalités denses.")
    L = ["### Qui porte l'offre", "", phr, "",
         "| Secteur | " + " | ".join(ordre) + " |", "|" + "---|" * (len(ordre) + 1)]
    for g, r in t.iterrows():
        L.append(f"| {g} | " + " | ".join(pct(v) for v in r) + " |")
    L.append("")
    L += graphique("porte_" + ("sm" if famille == SM else "sante"))
    L += _comment_lire(
        f"Chaque colonne répartit les {pluriel(C.lab[p0])} d'une classe de territoires selon le secteur où ils "
        "exercent. Une personne qui exerce dans plusieurs secteurs compte dans chacun. Le secteur est celui que le "
        "répertoire attribue à la structure d'exercice.")
    L += _plus_loin(["Secteurs d'activité du RPPS regroupés en grands secteurs (libéral, hôpital public, établissement privé, "
                     "médico-social, centre de santé), par "
                     "intercommunalité, classes de densité de population retenues ici. Détails dans porte_offre.csv."])
    return L


def _exercice(C: Contexte, famille):
    """Exercice sur plusieurs communes (point 10) et féminisation (point 11)."""
    ms, fe = C.agg.multisites, C.agg.feminisation
    if ms is None:
        return []
    profs = [p for p in PRINCIPALES[famille] if p in set(ms["prof"])]
    t = ms.set_index("prof").reindex(profs).reset_index()
    t["libelle"] = t["prof"].map(C.lab)
    if fe is not None:
        f = fe[(fe["niveau"] == "FR") & (fe["mode"] == "all")].set_index("prof")["part_femmes"]
        t["femmes"] = t["prof"].map(f)
    r = t.iloc[0]
    L = ["### Exercice sur plusieurs communes et part des femmes", "",
         f"{pct(r['part_plusieurs_communes']).capitalize()} des {pluriel(r['libelle'])} déclarent exercer dans au "
         f"moins deux communes, et {pct(r['part_plusieurs_epci'])} dans au moins deux intercommunalités."
         + (f" {pct(r['femmes']).capitalize()} sont des femmes." if "femmes" in t and pd.notna(r.get("femmes")) else ""), "",
         _tableau(t, ["libelle", "personnes", "part_plusieurs_communes", "part_plusieurs_epci"]
                  + (["femmes"] if "femmes" in t else []),
                  ["Profession", "Personnes avec un lieu d'exercice", "Dans deux communes ou plus",
                   "Dans deux intercommunalités ou plus"] + (["Part de femmes"] if "femmes" in t else []),
                  {"personnes": nombre, "part_plusieurs_communes": pct, "part_plusieurs_epci": pct, "femmes": pct}), ""]
    ex = []
    if fe is not None:
        d = fe[(fe["niveau"] == "dep") & (fe["mode"] == "all") & (fe["prof"] == PRINC[famille]) & (fe["personnes"] >= 30)]
        if len(d):
            ex.append(f"Selon les départements, la part de femmes parmi les {pluriel(C.lab[PRINC[famille]])} va de "
                      f"{pct(d['part_femmes'].min())} à {pct(d['part_femmes'].max())}.")
    L += _comment_lire(
        "Un professionnel qui exerce dans plusieurs communes compte dans chacune. Cela peut augmenter la densité "
        "apparente des territoires où il ne passe qu'une partie de son temps, car le répertoire ne dit rien du "
        "temps de travail.",
        "La part de femmes repose sur la civilité déclarée au répertoire (Madame ou Monsieur), seule information "
        "disponible.", *ex)
    lp = C.agg.liens
    if lp is not None and len(lp):
        top = lp[lp["prof"] == PRINC[famille]].head(5)
        if len(top):
            L += _plus_loin(["Liens les plus fréquents entre intercommunalités (personnes déclarant exercer dans les "
                             "deux), " + ", ".join(f"{C.nom_epci.get(a, a)} et {C.nom_epci.get(b, b)} ({n} personnes)"
                                                   for a, b, n in zip(top['epci_a'], top['epci_b'], top['n']))
                             + f". Tous les liens d'au moins {config.SECRET_MIN} personnes sont dans "
                             "liens_entre_intercommunalites.csv. Féminisation par département et par mode dans "
                             "feminisation.csv."])
    return L


def _vulnerabilite(C: Contexte, ctxlab):
    """Vulnérabilité psychosociale des territoires et offre de santé mentale (chantier 5)."""
    cc = C.R.get("correlations_contexte")
    ids = [c[0] for c in config.CONTEXTE_VULNERABILITE]
    if not isinstance(cc, pd.DataFrame) or not cc["variable"].isin(ids).any():
        return []
    f = cc[(cc["niveau"] == "epci") & (cc["mode"] == "all") & cc["variable"].isin(ids)
           & cc["prof"].isin(["psychologue", "psychiatre"])]
    piv = f.pivot_table(index="variable", columns="prof", values=["rho_spearman", "rho_partiel_densite", "ic95_bas_partiel",
                                                                  "ic95_haut_partiel"])
    lignes = []
    for v in ids:
        if v not in piv.index:
            continue
        lignes.append({"var": ctxlab.get(v, v),
                       **{f"{m}_{p}": piv.at[v, (m, p)] if (m, p) in piv.columns else np.nan
                          for m in ["rho_spearman", "rho_partiel_densite", "ic95_bas_partiel", "ic95_haut_partiel"]
                          for p in ["psychologue", "psychiatre"]}})
    if not lignes:
        return []
    T = pd.DataFrame(lignes)
    k = T["rho_partiel_densite_psychologue"].abs().idxmax()
    r = T.loc[k]
    L = ["### Vulnérabilité psychosociale et offre de santé mentale", "",
         phrase_correlation(r["rho_partiel_densite_psychologue"], r["var"], "Psychologue",
                            (r["ic95_bas_partiel_psychologue"], r["ic95_haut_partiel_psychologue"])).replace(
             "Les territoires où", "À densité de population égale, les territoires où"), "",
         _tableau(T, ["var", "rho_spearman_psychologue", "rho_partiel_densite_psychologue", "rho_spearman_psychiatre",
                      "rho_partiel_densite_psychiatre"],
                  ["Indicateur", "Psychologues, tous territoires", "Psychologues, à densité égale",
                   "Psychiatres, tous territoires", "Psychiatres, à densité égale"],
                  {c: (lambda v: nombre(v, 2)) for c in ["rho_spearman_psychologue", "rho_partiel_densite_psychologue",
                                                          "rho_spearman_psychiatre", "rho_partiel_densite_psychiatre"]}), ""]
    L += _comment_lire(
        "Ces indicateurs décrivent des conditions de vie connues pour peser sur la santé mentale (emploi, revenus, "
        "diplôme, logement, isolement). Ils ne mesurent pas le besoin de soins, et ils ne sont pas utilisés pour "
        "calculer l'effectif attendu. Le tableau donne la corrélation de rang entre chaque indicateur et la densité de "
        "professionnels, entre intercommunalités, avant et après retrait de l'effet ville. Un lien négatif signifie "
        "que les territoires les plus exposés sont plutôt moins dotés.")
    L += _plus_loin(["Indicateurs du dossier complet de l'INSEE (recensement 2023, salaires 2024, revenus 2023), "
                     "détaillés dans le glossaire. La part des minima sociaux n'est publiée que par département et "
                     "par région, elle n'apparaît donc pas dans ce tableau par intercommunalité mais dans les "
                     "croisements départementaux. Corrélations complètes, avec intervalles de confiance, dans "
                     "correlations_contexte.csv."])
    return L


def _outre_mer(C: Contexte):
    """Point 19, départements d'outre-mer comparés à l'Hexagone."""
    om = C.R.get("outre_mer")
    if not isinstance(om, pd.DataFrame) or om.empty:
        return []
    noms = C.ref.deps.set_index("code")["nom"]
    deps = [c for c in om.columns if c in config.DEPS_DROM]
    t = om.copy()
    t["libelle"] = t["prof"].map(C.lab)
    r = t.set_index("prof").loc["psychiatre"] if "psychiatre" in set(t["prof"]) else t.iloc[0]
    bas = [d for d in deps if pd.notna(r[d]) and r[d] < r["hexagone"] * .5]
    L = ["### Outre-mer", "",
         f"Pour les psychiatres, {len(bas)} départements d'outre-mer sur {len(deps)} ont une densité inférieure à la "
         f"moitié de celle de l'Hexagone ({nombre(r['hexagone'], 1)} pour 10 000 habitants)." if len(deps) else "", "",
         "| Profession | Hexagone | " + " | ".join(noms.get(d, d) for d in deps) + " |",
         "|" + "---|" * (len(deps) + 2)]
    for _, x in t.iterrows():
        dec = 2 if x[["hexagone"] + deps].max() < 1 else 1
        L.append(f"| {x['libelle']} | " + " | ".join(nombre(x[c], dec) if pd.notna(x[c]) else "" for c in ["hexagone"] + deps) + " |")
    L.append("")
    L += _comment_lire("Professionnels pour 10 000 habitants. Les départements d'outre-mer pèsent peu dans les moyennes "
                       "nationales, ce tableau les montre à part. À Mayotte, la population de référence et plusieurs "
                       "sources (recensement, Assurance Maladie) sont moins complètes, les chiffres y sont plus fragiles.")
    return L


def _chercheurs(C: Contexte):
    """Analyses complémentaires pour les chercheurs (points 7, 8, 12, 17 et 20)."""
    L = ["## Pour aller plus loin, analyses pour les chercheurs", "",
         "Cette partie s'adresse aux lecteurs qui veulent vérifier la solidité des résultats. Chaque section garde "
         "le même format, un constat, un tableau, une explication.", ""]
    L += rapport_bases.profil_egal(C) + _moran(C)
    th = C.R.get("decomposition_theil")
    if isinstance(th, pd.DataFrame) and not th.empty:
        t = th.pivot_table(index="prof", columns="groupes", values="part_entre").reset_index()
        t["libelle"] = t["prof"].map(C.lab)
        cols = [c for c in ["départements", "classes de densité"] if c in t]
        r = t.set_index("prof").loc["psychologue"] if "psychologue" in set(t["prof"]) else t.iloc[0]
        L += ["### D'où viennent les inégalités entre intercommunalités", "",
              f"Pour les psychologues, {pct(r['départements'])} de l'inégalité de répartition entre intercommunalités "
              f"tient aux écarts entre départements, le reste aux écarts à l'intérieur des départements." if "départements" in t else "",
              "", _tableau(t, ["libelle"] + cols, ["Profession"] + [f"Part entre {c}" for c in cols],
                           {c: pct for c in cols}), ""]
        L += _comment_lire("L'indice de Theil mesure l'inégalité de répartition et se décompose exactement en deux parts. "
                           "Une part faible entre départements signifie que les écarts se jouent surtout à l'intérieur de "
                           "chaque département, donc à une échelle plus fine que celle des politiques départementales.")
    su = C.R.get("substitution")
    if isinstance(su, pd.DataFrame) and not su.empty:
        t = su.copy()
        t["paire"] = t["prof_a"].map(C.lab) + " et " + t["prof_b"].map(C.lab).str.lower()
        t["lecture"] = np.where(t["rho_partiel_densite"] > .1, "plutôt ensemble",
                                np.where(t["rho_partiel_densite"] < -.1, "plutôt l'une sans l'autre", "pas de lien net"))
        ens, sub = int((t["rho_partiel_densite"] > .1).sum()), int((t["rho_partiel_densite"] < -.1).sum())
        L += ["### Professions présentes ensemble ou l'une à la place de l'autre", "",
              f"À densité de population égale, {ens} paires de professions sur {len(t)} sont plutôt présentes ensemble. "
              + ("Aucune n'apparaît comme le substitut de l'autre." if sub == 0 else
                 f"{sub} apparaissent plutôt l'une sans l'autre."), "",
              _tableau(t, ["paire", "rho", "rho_partiel_densite", "lecture"],
                       ["Professions", "rho, tous territoires", "rho, à densité de population égale", "Lecture"],
                       {"rho": lambda v: nombre(v, 2), "rho_partiel_densite": lambda v: nombre(v, 2)}), ""]
        L += _comment_lire("Un lien positif signifie que les territoires bien dotés en l'une sont aussi bien dotés en "
                           "l'autre (cumul). Un lien négatif signifierait que l'une compense l'absence de l'autre "
                           "(substitution). Le calcul à densité de population égale retire l'effet ville.")
    ro, vn = C.R.get("robustesse_gini"), C.R.get("variance_niveaux")
    if isinstance(ro, pd.DataFrame) and not ro.empty:
        t = ro.copy()
        t["libelle"] = t["prof"].map(C.lab)
        t["ic"] = t.apply(lambda r: f"de {nombre(r['ic95_bas'], 2)} à {nombre(r['ic95_haut'], 2)}", axis=1)
        if isinstance(vn, pd.DataFrame) and not vn.empty:
            t["entre_dep"] = t["prof"].map(vn.set_index("prof")["part_entre_departements"])
        L += ["### Solidité des indices d'inégalité et effet de l'échelle", "",
              "L'inégalité mesurée dépend de l'échelle choisie. Elle est toujours plus forte entre communes, où beaucoup "
              "de petites communes n'ont aucun professionnel, et plus faible entre régions.", "",
              _tableau(t, ["libelle", "gini_com", "gini_epci", "ic", "gini_dep", "gini_reg"]
                       + (["entre_dep"] if "entre_dep" in t else []),
                       ["Profession", "Gini, communes", "Gini, intercommunalités", "Fourchette (95 %)", "Gini, départements",
                        "Gini, régions"] + (["Variation entre départements"] if "entre_dep" in t else []),
                       {c: (lambda v: nombre(v, 2)) for c in ["gini_com", "gini_epci", "gini_dep", "gini_reg"]}
                       | {"entre_dep": pct}), ""]
        L += _comment_lire("La fourchette est obtenue en refaisant le calcul sur des tirages au hasard parmi les "
                           "intercommunalités. La dernière colonne donne la part de la variation de densité entre "
                           "intercommunalités qui s'explique par le département où elles se trouvent, une approche "
                           "simple des modèles à plusieurs niveaux.")
    mr = C.R.get("moran_residus")
    if isinstance(mr, pd.DataFrame) and not mr.empty:
        t = mr.assign(libelle=lambda d: d["prof"].map(C.lab))
        L += ["### Structure spatiale non expliquée par les modèles", "",
              f"Après prise en compte du profil des habitants, les écarts à l'attendu restent semblables entre voisins "
              f"pour {int(((t['moran_residus'] > .1) & (t['p_permutation'] < .05)).sum())} professions sur {len(t)}.", "",
              _tableau(t, ["libelle", "moran_residus", "p_permutation"], ["Profession", "Indice de Moran des écarts", "p"],
                       {"moran_residus": lambda v: nombre(v + 0.0, 2).replace("-0,00", "0,00"),
                        "p_permutation": lambda v: nombre(v, 3)}), ""]
        L += _comment_lire("Un indice nettement positif signifie que des facteurs géographiques non pris en compte par "
                           "le modèle jouent encore. Les incertitudes des modèles sont alors sous-estimées, et un modèle "
                           "qui intègre explicitement le voisinage (modèle spatial autorégressif) serait la suite "
                           "logique.")
    return L if len(L) > 4 else []


def _quadrants(C: Contexte, ctxlab):
    """Offre face aux indicateurs de besoin, par département."""
    qd = C.R.get("quadrants")
    if not isinstance(qd, pd.DataFrame) or qd.empty:
        return []
    noms = C.ref.deps.set_index("code")["nom"]
    var = "suicides" if "suicides" in set(qd["variable"]) else qd["variable"].iloc[0]
    L = ["#### Offre face aux indicateurs de besoin", ""]
    phrases, tableaux = [], []
    for p in ["psychiatre", "psychologue"]:
        x = qd[(qd["prof"] == p) & (qd["variable"] == var)].dropna(subset=["quadrant"])
        if x.empty:
            continue
        crit = x[x["quadrant"] == "besoin+offre-"].sort_values("valeur", ascending=False)
        if not phrases:
            phrases.append(f"{len(crit)} départements, où vivent {nombre(crit['population'].sum())} habitants, cumulent "
                           + rapport_bases.NOMS_RESULTATS.get(var, f"un indicateur « {ctxlab.get(var, var).lower()} »").replace("le taux", "un taux", 1)
                           + f" au-dessus de la médiane et une densité de "
                           f"{pluriel(C.lab[p])} au-dessous de la médiane.")
        else:
            phrases.append(f"Pour les {pluriel(C.lab[p])}, c'est le cas de {len(crit)} départements, où vivent "
                           f"{nombre(crit['population'].sum())} habitants.")
        crit = crit.assign(nom=crit["code"].map(noms)).sort_values("nom")
        tableaux += ["<details>", f"<summary>{pluriel(C.lab[p]).capitalize()}, liste des {len(crit)} départements, "
                     f"par ordre alphabétique</summary>", "",
                     _tableau(crit, ["nom", "valeur", "densite"],
                              ["Département", ctxlab.get(var, var), f"{pluriel(C.lab[p]).capitalize()} pour 10 000 hab."],
                              {"valeur": lambda v: nombre(v, 1), "densite": lambda v: nombre(v, 2)}), "", "</details>", ""]
    if not phrases:
        return []
    autres = sorted(set(qd["variable"]) - {var})
    L += [" ".join(phrases), ""] + graphique("quadrants_sm") + tableaux
    L += _comment_lire(
        "Chaque département est situé selon deux critères, sa densité de professionnels et un indicateur de besoin, "
        "chacun comparé à sa médiane (la valeur qui partage les départements en deux moitiés). On obtient quatre "
        "groupes. Les listes repliées donnent, par ordre alphabétique, les départements au-dessus de la médiane "
        "pour l'indicateur et au-dessous pour la densité.",
        "Cette position par rapport aux médianes ne dit pas que l'offre y est insuffisante au sens d'une norme. Le "
        "suicide est retenu ici parce qu'il dépend peu de l'offre de soins. Sur la figure, un rond ocre marqué « ! » "
        "signale les départements d'Île-de-France, où les suicides sont nettement sous-déclarés.",
        limites.phrase_md(["suicides"]))
    L += _plus_loin([f"Seuils, médianes des départements (Mayotte exclue des indicateurs de l'Assurance Maladie). Le "
                     f"même classement est calculé pour les {len(autres)} autres indicateurs de besoin et de recours "
                     f"et pour les psychiatres qualifiés pour l'enfant et les médecins généralistes, dans quadrants.csv "
                     f"et quadrants_odbl.csv. Un département proche d'une médiane peut changer de groupe d'une année "
                     f"à l'autre sans changement réel."])
    return L


REF_TUDOR_HART = ("Tudor Hart J. The inverse care law. The Lancet, 1971. "
                  "[doi.org/10.1016/S0140-6736(71)92410-X](https://doi.org/10.1016/S0140-6736(71)92410-X)")
REF_WAGSTAFF = ("Wagstaff A, Paci P, van Doorslaer E. On the measurement of inequalities in health. Social Science & "
                "Medicine, 1991. [doi.org/10.1016/0277-9536(91)90212-U](https://doi.org/10.1016/0277-9536(91)90212-U)")


def _sens_concentration(lo, hi):
    if lo > 0:
        return "plus présents là où le besoin mesuré est élevé"
    if hi < 0:
        return "plus présents là où le besoin mesuré est faible"
    return "ni plus ni moins présents selon le besoin mesuré"


def _loi_inverse(C: Contexte, ctxlab):
    """Loi inverse des soins, indice de concentration de l'offre selon le besoin (départements)."""
    li = C.R.get("loi_inverse")
    if not isinstance(li, pd.DataFrame) or li.empty:
        return []
    t = li.assign(libelle=li["prof"].map(C.lab), besoin=li["variable"].map(lambda v: ctxlab.get(v, v)))
    t["lecture"] = [_sens_concentration(lo, hi) for lo, hi in zip(t["ic95_bas"], t["ic95_haut"])]
    t["fourchette"] = [f"de {nombre(lo, 2)} à {nombre(hi, 2)}" for lo, hi in zip(t["ic95_bas"], t["ic95_haut"])]
    r = t[(t["prof"] == "psychiatre") & (t["variable"] == "suicides")]
    tete = ""
    if len(r):
        r = r.iloc[0]
        tete = (f"Quand on classe les départements du taux de suicide le plus faible au plus fort, les psychiatres sont "
                f"{r['lecture']} (indice de concentration {nombre(r['indice_concentration'], 2)}, fourchette {r['fourchette']}).")
    L = ["#### L'offre va-t-elle là où le besoin est le plus fort ?", "", tete, "",
         _tableau(t, ["libelle", "besoin", "indice_concentration", "fourchette", "lecture"],
                  ["Profession", "Départements classés selon", "Indice de concentration", "Fourchette (95 %)", "Lecture"],
                  {"indice_concentration": lambda v: nombre(v, 2)}), ""]
    L += _comment_lire(
        "En 1971, le médecin Julian Tudor Hart a décrit une « loi inverse des soins », selon laquelle l'offre de soins "
        "tend à être plus faible là où les besoins sont les plus forts. L'indice de concentration la mesure. Il vaut "
        "0 si les professionnels suivent la population, il est négatif s'ils sont plus présents dans les départements "
        "où le besoin mesuré est faible, positif dans l'autre cas.",
        "Les personnes prises en charge par l'Assurance Maladie dépendent elles-mêmes de l'offre, un indice positif "
        "avec cet indicateur est donc attendu et ne prouve pas que l'offre répond au besoin. Le suicide en dépend "
        "beaucoup moins. Ces liens portent sur des départements, pas sur des personnes.")
    L += _plus_loin([f"Indice de concentration (méthode de Wagstaff), départements triés selon l'indicateur de besoin, "
                     f"pondérés par leur population, intervalle à 95 % par bootstrap ({config.BOOTSTRAP} tirages). "
                     f"Mayotte est exclue. Détail dans loi_inverse.csv et loi_inverse_odbl.csv. Références, "
                     f"{REF_TUDOR_HART}. {REF_WAGSTAFF}."])
    return L


def _concordance(C: Contexte, ctxlab):
    """Les indicateurs de besoin désignent-ils les mêmes départements ?"""
    co = C.R.get("concordance_besoins")
    if not isinstance(co, pd.DataFrame) or co.empty:
        return []
    t = co.assign(a=co["variable_a"].map(lambda v: ctxlab.get(v, v)), b=co["variable_b"].map(lambda v: ctxlab.get(v, v)))
    t = t.sort_values("rho", ascending=False)
    fort = int((t["rho"].abs() >= .5).sum())
    L = ["#### Les indicateurs de besoin désignent-ils les mêmes départements ?", "",
         f"Sur {len(t)} paires d'indicateurs, {fort} sont fortement liées (corrélation de rang d'au moins 0,5 en valeur "
         f"absolue), et la médiane des corrélations vaut {nombre(t['rho'].median(), 2)}. Les indicateurs ne désignent "
         f"donc pas tous les mêmes départements, d'où l'intérêt de les lire côte à côte plutôt que d'en retenir un seul.",
         "",
         _tableau(t, ["a", "b", "rho", "departements"], ["Indicateur", "Indicateur", "Corrélation de rang", "Départements"],
                  {"rho": lambda v: nombre(v, 2), "departements": nombre}), ""]
    L += _comment_lire("Une corrélation proche de 1 signifie que les deux indicateurs classent les départements de la "
                       "même façon, proche de 0 qu'ils n'ont pas de lien. Des indicateurs qui divergent mesurent des "
                       "réalités différentes (recours aux soins, décès, gestes auto-infligés, protection de l'enfance).")
    return L


THEMES_CROISEMENTS = {
    SM: {"hopital_liberal": "L'hôpital compense-t-il la faiblesse des psychiatres libéraux ?",
         "secteur2_revenu": "Dans les territoires aisés, l'offre de psychiatres est-elle plus chère ?",
         "enfance": "L'offre en psychiatrie de l'enfant suit-elle la protection de l'enfance ?",
         "trajet_suicide": "Les départements éloignés des CMP ont-ils plus de suicides, au-delà de la ruralité ?"},
    SANTE: {"reeducation": "L'offre libérale de rééducation suit-elle l'offre médico-sociale pour les enfants ?",
            "medecin_traitant": "Les patients sans médecin traitant sont-ils plus nombreux là où les généralistes "
                                "libéraux manquent, ou là où la population est âgée ?"}}
COMMENT_CROISEMENTS = {
    "hopital_liberal": "Une corrélation négative entre psychiatres libéraux et psychiatrie hospitalière indiquerait "
                       "que l'hôpital compense là où les libéraux manquent, une corrélation positive que les deux "
                       "manquent ou abondent ensemble.",
    "trajet_suicide": "Le temps de trajet est le temps médian des habitants du département jusqu'à la structure ou au "
                      "psychiatre libéral le plus proche. À densité de population égale, la comparaison porte sur des "
                      "départements aussi ruraux l'un que l'autre. Le taux de suicide est sous-déclaré, surtout en "
                      "Île-de-France.",
    "reeducation": "Les places pour enfants en situation de handicap (établissements et SESSAD) sont rapportées aux "
                   "moins de 20 ans. Une corrélation positive voudrait dire que l'offre libérale d'orthophonie et de "
                   "psychomotricité est plus dense là où l'offre médico-sociale l'est aussi.",
    "medecin_traitant": "La part des patients sans médecin traitant porte sur les personnes en affection de longue "
                        "durée, tous âges confondus. Les données ne la donnent pas par âge, ce croisement ne dit donc "
                        "pas si les plus âgés sont plus touchés que les autres.",
}


def _croisements(C: Contexte, ctxlab, famille=SM, niveau="####"):
    """Croisements entre bases (départements), corrélation brute et à densité de population égale."""
    cr = C.R.get("croisements")
    if not isinstance(cr, pd.DataFrame) or cr.empty:
        return []
    themes = THEMES_CROISEMENTS[famille]
    cr = cr[cr["theme"].isin(themes)]
    if cr.empty:
        return []
    ta = C.R.get("temps_acces")
    eq = (ta.drop_duplicates("equipement").set_index("equipement")["libelle"].to_dict()
          if isinstance(ta, pd.DataFrame) and not ta.empty else {})

    def nom(cle):
        if cle.startswith("dens_lib:"):
            return pluriel(C.lab.get(cle[9:], cle[9:])).capitalize() + " libéraux pour 10 000 habitants"
        if cle.startswith("dens:"):
            return pluriel(C.lab.get(cle[5:], cle[5:])).capitalize() + " pour 10 000 habitants"
        if cle.startswith("route:"):
            return "Temps médian par la route, " + minuscule(eq.get(cle[6:], cle[6:]))
        v = cle[4:] if cle.startswith("ctx:") else cle
        return ctxlab.get(v, v)
    t = cr.assign(x=cr["mesure"].map(nom), y=cr["variable"].map(nom))
    L = [f"{niveau} Croisements entre bases", ""]
    for theme, q in themes.items():
        g = t[t["theme"] == theme]
        if g.empty:
            continue
        phrases = []
        for _, r in g.iterrows():
            net = r["ic95_bas"] > 0 or r["ic95_haut"] < 0
            rp = r.get("rho_partiel_densite", np.nan)
            netp = pd.notna(rp) and (r.get("ic95_bas_partiel", np.nan) > 0 or r.get("ic95_haut_partiel", np.nan) < 0)
            brut = (f"le lien est {force(r['rho'])} (rho = {nombre(r['rho'], 2)})" if net else
                    f"aucun lien net n'apparaît (rho = {nombre(r['rho'], 2)}, fourchette de {nombre(r['ic95_bas'], 2)} "
                    f"à {nombre(r['ic95_haut'], 2)})")
            if pd.isna(rp):
                dens = ""
            elif net and netp:
                dens = f", et {force(rp)} à densité de population égale (rho = {nombre(rp, 2)})"
            elif net:
                dens = f", mais il disparaît à densité de population égale (rho = {nombre(rp, 2)})"
            elif netp:
                dens = f", mais un lien {force(rp)} apparaît à densité de population égale (rho = {nombre(rp, 2)})"
            else:
                dens = f", ni à densité de population égale (rho = {nombre(rp, 2)})"
            phrases.append(f"Entre « {minuscule(r['x'])} » et « {minuscule(r['y'])} », {brut}{dens}.")
        L += [f"{niveau}# {q}", "", " ".join(phrases), ""]
        if theme in COMMENT_CROISEMENTS:
            L += [f"*{COMMENT_CROISEMENTS[theme]}*", ""]
    t["ic"] = [f"de {nombre(lo, 2)} à {nombre(hi, 2)}" for lo, hi in zip(t["ic95_bas"], t["ic95_haut"])]
    partiel = "rho_partiel_densite" in t
    cols = ["x", "y", "rho", "ic"] + (["rho_partiel_densite"] if partiel else []) + ["departements"]
    ents = ["Mesure", "Croisée avec", "Corrélation de rang", "Fourchette (95 %)"] + (
        ["À densité de population égale"] if partiel else []) + ["Départements"]
    L += [_tableau(t, cols, ents, {"rho": lambda v: nombre(v, 2), "rho_partiel_densite": lambda v: nombre(v, 2)}), ""]
    L += _comment_lire(
        "Chaque ligne compare deux mesures, département par département. Une corrélation positive signifie que les deux sont "
        "élevées ou basses ensemble, une corrélation négative que l'une est haute là où l'autre est basse. Un lien net "
        "a une fourchette qui exclut zéro. La colonne à densité de population égale retire l'effet ville. Ces liens "
        "décrivent des départements et ne disent rien d'une cause.")
    L += _plus_loin(["Corrélations de rang de Spearman entre départements, intervalles à 95 % par bootstrap, corrélation "
                     "partielle de rang à densité de population égale. Sources, RPPS, SAE de la DREES, Assurance "
                     "Maladie (secteurs conventionnels et patients sans médecin traitant, ODbL), indicateurs sociaux "
                     "départementaux de la DREES, INSEE (dossier complet, temps de trajet par la route). Mayotte est "
                     "écartée. Détail dans croisements.csv et croisements_odbl.csv."])
    return L


def _correlations(C: Contexte, famille, ctxlab):
    cc = C.R.get("correlations_contexte")
    if not isinstance(cc, pd.DataFrame) or not len(cc):
        return []
    profs = [p for p in PRINCIPALES[famille] if C.present(p)]
    f = cc[(cc["niveau"] == "epci") & (cc["mode"] == "all") & (cc["rho_spearman"].abs() >= .3) & (cc["q_bh"] < .05)
           & cc["prof"].isin(profs)].copy().sort_values("rho_spearman", key=abs, ascending=False)
    L = ["### Liens avec le profil des habitants", ""]
    if not len(f):
        return L + ["Aucun lien au moins modéré n'apparaît entre ces professions et le profil des habitants.", ""]
    f["libelle"] = f["prof"].map(C.lab)
    f["var"] = f["variable"].map(ctxlab)
    f["force_lien"] = f["rho_spearman"].map(force)
    f["sens"] = np.where(f["rho_spearman"] > 0, "plus", "moins")
    f["ic"] = f.apply(lambda r: f"de {nombre(r['ic95_bas'], 2)} à {nombre(r['ic95_haut'], 2)}"
                      if pd.notna(r["ic95_bas"]) else "", axis=1)
    partiel = "rho_partiel_densite" in f
    if partiel:
        f["rp"] = f["rho_partiel_densite"]
        g = f[f["variable"] != "densite_pop"]
        restent = int((g["rp"].abs() >= .3).sum())
        L += [f"Sur {len(g)} liens au moins modérés entre ces professions et le profil des habitants, "
              f"{restent} le restent quand on compare des territoires aussi urbains l'un que l'autre. Les autres "
              f"tiennent pour l'essentiel à l'effet ville.", ""]
    cols = ["libelle", "var", "sens", "force_lien", "rho_spearman", "ic"] + (["rp"] if partiel else [])
    ents = ["Profession", "Indicateur", "Quand l'indicateur est élevé, plutôt", "Force du lien", "rho",
            "Fourchette (95 %)"] + (["rho à densité de population égale"] if partiel else [])
    t = f[f["variable"] != "densite_pop"].head(25).copy()
    t["ic"] = t["ic"].replace("", "non calculée")
    if partiel:
        t["rp"] = t["rp"].map(lambda v: "non calculée" if pd.isna(v) else nombre(v, 2))
    L += [_tableau(t, cols, ents, {"rho_spearman": lambda v: nombre(v, 2)}), ""]
    ex = ""
    if partiel:
        h = f[(f["variable"] != "densite_pop") & f["rp"].notna()]
        if len(h):
            h = h.loc[(h["rho_spearman"].abs() - h["rp"].abs()).idxmax()]
            ex = (f"Par exemple, le lien entre les {pluriel(h['libelle'])} et l'indicateur « {h['var'].lower()} » "
                  f"vaut {nombre(h['rho_spearman'], 2)} en tout, mais {nombre(h['rp'], 2)} entre territoires de même "
                  f"densité de population. La différence vient de l'effet ville.")
    L += graphique("effet_ville_" + ("sm" if famille == SM else "sante"))
    L += _comment_lire(
        "Le rho va de -1 à +1. De 0,3 à 0,5 en valeur absolue le lien est modéré, au-delà il est fort. La "
        "fourchette indique la stabilité du résultat. La densité de population elle-même n'est pas dans le tableau, "
        "c'est elle que la dernière colonne retire.",
        DEFINITIONS["effet_ville"], ex, DEFINITIONS["ecologique"])
    L += _plus_loin(["Corrélations de rang de Spearman entre la densité pour 10 000 habitants et chaque indicateur "
                     "de contexte, sur les intercommunalités, tous modes d'exercice. Intervalles de confiance à 95 % "
                     f"par bootstrap ({config.BOOTSTRAP} rééchantillonnages). Seuls les liens avec |rho| ≥ 0,3 et "
                     "une q-valeur de Benjamini-Hochberg inférieure à 0,05 sont affichés. La corrélation à densité "
                     "égale est une corrélation partielle de rang, les rangs de l'indicateur et de la densité de "
                     "professionnels étant corrigés de leur relation linéaire avec le rang de la densité de "
                     "population, avec son propre intervalle par bootstrap et sa propre correction de "
                     "Benjamini-Hochberg. Le tableau complet, avec les p-valeurs et la corrélation de Pearson pondérée "
                     "sur le logarithme de la densité, est dans correlations_contexte.csv."])
    return L


def _phrase_revenu(C, cp, densites, p):
    """Phrase de tête de l'escalier social, fondée sur l'indice de concentration et son intervalle."""
    ci, lo, hi = cp["indice_concentration"], cp["ic95_bas"], cp["ic95_haut"]
    lab = pluriel(C.lab[p])
    if lo <= 0 <= hi:
        tete = f"Les {lab} ne sont ni plus ni moins présents dans les territoires aisés que dans les territoires modestes"
    else:
        ampleur = "à peine" if abs(ci) < .05 else "un peu" if abs(ci) < .15 else "nettement"
        tete = (f"Les {lab} sont {ampleur} plus présents dans les territoires "
                f"{'aisés' if ci > 0 else 'modestes'} que dans les territoires {'modestes' if ci > 0 else 'aisés'}")
    hautd, basd = densites.idxmax(), densites.idxmin()
    return (f"{tete} (indice de concentration {nombre(ci, 2)}). L'écart n'est pas régulier d'une tranche à "
            f"l'autre. La tranche la mieux dotée est la {hautd}e, avec {nombre(densites[hautd], 1)} pour 10 000 "
            f"habitants, la moins dotée la {basd}e{'re' if basd == 1 else ''}, avec {nombre(densites[basd], 1)}."
            ).replace("la 1ere", "la première").replace("la 1e,", "la première,")


def _grande_epci(C):
    """Signale une intercommunalité assez peuplée pour remplir presque à elle seule une tranche."""
    pop = C.pop_epci
    grandes = pop[pop > .06 * pop.sum()]
    if grandes.empty:
        return ""
    noms = _liste(C.nom_epci.reindex(grandes.index).fillna(""))
    return (f"Une intercommunalité très peuplée comme {noms} remplit à elle seule une grande partie d'une tranche, ce "
            f"qui explique les ruptures dans l'escalier.")


def _revenu(C: Contexte, famille):
    co, es = C.R.get("concentration_revenu"), C.R.get("escalier_social")
    if not isinstance(co, pd.DataFrame) or co.empty:
        return []
    profs = [p for p in PRINCIPALES[famille] if p in set(co["prof"])]
    e = es[(es["niveau"] == "epci") & es["prof"].isin(profs)]
    piv = e.pivot_table(index="decile", columns="prof", values="densite")[profs]
    bornes = e[e["prof"] == profs[0]].set_index("decile")[["niveau_de_vie_min", "niveau_de_vie_max"]]
    c = co[(co["niveau"] == "epci") & (co["mode"] == "all")].set_index("prof")
    p0 = profs[0]
    L = ["### Offre selon le niveau de vie des territoires", "", _phrase_revenu(C, c.loc[p0], piv[p0], p0), ""]
    L += ["| Dixième de la population | Niveau de vie médian du territoire | "
         + " | ".join(C.lab[p] for p in profs) + " |", "|" + "---|" * (len(profs) + 2)]
    for d, r in piv.iterrows():
        nom = "1 (plus modestes)" if d == 1 else "10 (plus aisés)" if d == 10 else str(d)
        L.append(f"| {nom} | {nombre(bornes.at[d, 'niveau_de_vie_min'])} à {nombre(bornes.at[d, 'niveau_de_vie_max'])} € | "
                 + " | ".join(nombre(v, 2 if r.max() < 1 else 1) for v in r) + " |")
    L.append("| Indice de concentration | | " + " | ".join(nombre(c.at[p, "indice_concentration"], 2) for p in profs) + " |")
    fourchettes = ", ".join(f"{minuscule_pluriel(C.lab[p])} de {nombre(c.at[p, 'ic95_bas'], 2)} à "
                            f"{nombre(c.at[p, 'ic95_haut'], 2)}" for p in profs)
    L.append("")
    cp = c.loc[p0]
    L += graphique("escalier_" + ("sm" if famille == SM else "sante"))
    L += _comment_lire(
        "Les intercommunalités sont classées de la plus modeste à la plus aisée selon le niveau de vie médian de "
        "leurs habitants, puis regroupées en dix tranches qui réunissent chacune un dixième de la population. "
        "Chaque case donne le nombre de professionnels pour 10 000 habitants dans la tranche.",
        f"L'indice de concentration résume ce gradient. Il vaut 0 si les professionnels suivent la population, il "
        f"est positif s'ils sont plus présents dans les territoires aisés, négatif s'ils le sont dans les territoires "
        f"modestes. Pour les {pluriel(C.lab[p0])}, il vaut {nombre(cp['indice_concentration'], 2)}.",
        _grande_epci(C),
        "Le niveau de vie décrit le territoire, pas les personnes qui consultent. Les territoires aisés sont aussi "
        "souvent plus urbains.")
    L += _plus_loin([f"Indice de concentration calculé sur les intercommunalités dont le niveau de vie médian est "
                     f"connu, territoires triés par niveau de vie croissant, pondérés par la population. Il vaut 1 "
                     f"moins deux fois l'aire sous la courbe de concentration. Intervalle de confiance à 95 % par "
                     f"bootstrap sur les territoires ({config.BOOTSTRAP} tirages), {fourchettes}. Détails dans "
                     f"concentration_revenu.csv et escalier_social.csv."])
    return L


def _entonnoir(C: Contexte, famille):
    rs = C.R.get("entonnoir_resume")
    if not isinstance(rs, pd.DataFrame) or rs.empty:
        return []
    profs = [p for p in PRINCIPALES[famille] if p in set(rs["prof"])]
    t = rs[(rs["niveau"] == "epci")].set_index("prof").reindex(profs).reset_index().dropna(subset=["part_hors_95"])
    t["libelle"] = t["prof"].map(C.lab)
    r0 = t.iloc[0]
    hasard = ("Les écarts entre territoires dépassent donc largement ce que le hasard produirait."
              if r0["part_hors_95"] > .1 else "Les écarts restent du même ordre que ce que le hasard produirait.")
    L = ["### Écarts qui dépassent le hasard", "",
         f"{pct(r0['part_population_nettement_en_dessous']).capitalize()} des habitants vivent dans une "
         f"intercommunalité nettement en dessous de la moyenne des intercommunalités pour les {pluriel(r0['libelle'])}, au-delà "
         f"de ce que le hasard pourrait expliquer.", "",
         _tableau(t, ["libelle", "part_nettement_en_dessous", "part_population_nettement_en_dessous", "part_hors_95"],
                  ["Profession", "Intercommunalités nettement en dessous", "Habitants concernés",
                   "Intercommunalités hors de la norme (au-dessus ou en dessous)"],
                  {"part_nettement_en_dessous": pct, "part_population_nettement_en_dessous": pct,
                   "part_hors_95": pct}), ""]
    L += graphique("entonnoir_" + ("sm" if famille == SM else "sante"))
    L += _comment_lire(
        "Dans un petit territoire, quelques arrivées ou départs suffisent à faire varier fortement la densité. Le "
        "diagramme en entonnoir de l'atlas tient compte de la taille de chaque territoire. Il trace autour de la "
        "moyenne des intercommunalités deux limites qui se resserrent quand la population augmente. Un territoire sous la "
        "limite la plus large est dit nettement en dessous, ce que le hasard expliquerait au plus deux fois sur "
        "mille.",
        f"Si seul le hasard jouait, environ 5 % des territoires seraient hors de la norme. Pour les "
        f"{pluriel(r0['libelle'])}, c'est {pct(r0['part_hors_95'])}. {hasard}",
        "Pour une profession rare comme la pédopsychiatrie, les limites sont si larges que presque aucun "
        "territoire n'en sort. Cela ne signifie pas que l'offre est homogène, seulement que les effectifs sont trop "
        "faibles pour conclure." if "pedopsychiatre" in profs else "")
    L += _plus_loin(["Limites de Poisson à 95 % et 99,8 % autour du taux national (effectif total des "
                     "intercommunalités rapporté à leur population), calculées pour l'effectif attendu au taux "
                     "national. La forte proportion de territoires hors des limites traduit une surdispersion par "
                     "rapport au modèle de Poisson. Les limites ne sont pas élargies pour en tenir compte, elles "
                     "repèrent donc les écarts au hasard, pas les seuls territoires exceptionnels. Statut de chaque "
                     "territoire dans entonnoir.csv (-2 nettement en dessous, -1 en dessous, 0 dans la norme, 1 "
                     "au-dessus, 2 nettement au-dessus)."])
    return L


def _gradient(C: Contexte, famille):
    cd, td = C.R.get("classes_densite"), C.R.get("tests_classes_densite")
    if not isinstance(cd, pd.DataFrame) or not len(cd):
        return []
    profs = [p for p in PRINCIPALES[famille] if C.present(p)]
    t = cd[(cd["niveau"] == "epci") & cd["prof"].isin(profs)]
    piv = t.pivot_table(index="prof", columns="classe", values="densite_agregee")
    classes = [c[2] for c in CLASSES_DENSITE if c[2] in piv.columns]
    piv = piv[classes]
    L = ["### Écart entre territoires ruraux et urbains", "",
         "Professionnels pour 10 000 habitants selon la densité de population de l'intercommunalité.", "",
         "| Profession | " + " | ".join(classes) + " | Écart |", "|" + "---|" * (len(classes) + 2)]
    ecarts = {}
    for p, r in piv.iterrows():
        e = fois(r[classes[-1]], r[classes[0]])
        ecarts[p] = r[classes[-1]] / r[classes[0]] if r[classes[0]] else np.inf
        dec = 2 if r.max() < 1 else 1
        L.append(f"| {C.lab.get(p, p)} | " + " | ".join(nombre(v, dec) if pd.notna(v) else "" for v in r)
                 + f" | {e} |")
    L.append("")
    p0 = profs[0]
    if p0 in piv.index:
        r = piv.loc[p0]
        L += _comment_lire(
            f"La dernière colonne compare les territoires denses aux territoires très peu denses. Par exemple, les "
            f"intercommunalités denses comptent {nombre(r[classes[-1]], 1)} {pluriel(C.lab[p0])} pour 10 000 "
            f"habitants, contre {nombre(r[classes[0]], 1)} dans les très peu denses, soit "
            f"{fois(r[classes[-1]], r[classes[0]])}.",
            "Les classes de densité sont définies ici, en attendant la grille communale de densité de "
            "l'INSEE.")
    if isinstance(td, pd.DataFrame) and len(td):
        t2 = td[(td["niveau"] == "epci") & td["prof"].isin(profs)].copy()
        t2["libelle"] = t2["prof"].map(C.lab)
        L += _plus_loin([
            "Test de Kruskal-Wallis entre classes, taille d'effet epsilon², corrélation bisériale de rang entre "
            "les territoires très peu denses et denses, q-valeur de Benjamini-Hochberg.", "",
            _tableau(t2, ["libelle", "epsilon2", "biserial_extremes", "q_bh"],
                     ["Profession", "Epsilon²", "Bisériale (très peu dense, dense)", "q"],
                     {"epsilon2": lambda v: nombre(v, 3), "biserial_extremes": lambda v: nombre(v, 2),
                      "q_bh": lambda v: "< 0,001" if v < .001 else nombre(v, 3)})])
    return L


def _phrase_nb(q):
    """Contrôle de solidité par une régression binomiale négative (surdispersion)."""
    if "rho_rapports_poisson_nb" not in q or q.empty:
        return ""
    r = q.iloc[0]
    return (f"Contrôle de solidité, une régression binomiale négative, qui tient compte de cette dispersion, donne des "
            f"effectifs attendus très proches pour les {pluriel(r['libelle'])} (corrélation de rang des rapports "
            f"observé sur attendu {nombre(r['rho_rapports_poisson_nb'], 2)}). Parmi les {nombre(r['retrait_poisson'])} "
            f"intercommunalités sous la moitié de l'attendu avec le premier modèle, {nombre(r['retrait_communs'])} le "
            f"restent avec le second. Ce dernier s'ajuste mieux aux données (critère d'Akaike "
            f"{nombre(r['aic_nb'])} contre {nombre(r['aic_poisson'])}). Détail dans modeles_qualite.csv."
            if r["aic_nb"] < r["aic_poisson"] else
            f"Contrôle de solidité, une régression binomiale négative donne des effectifs attendus proches (corrélation "
            f"de rang {nombre(r['rho_rapports_poisson_nb'], 2)}). Détail dans modeles_qualite.csv.")


def _retrait(C: Contexte, famille):
    q, ea = C.R.get("modeles_qualite"), C.R.get("ecarts_attendu")
    if not isinstance(ea, pd.DataFrame) or not len(ea):
        return []
    L = ["### Écart à l'effectif attendu compte tenu du profil des territoires", ""]
    exemple = None
    for p in RETRAIT[famille]:
        e = ea[(ea["prof"] == p) & (ea["pop"] >= POP_MIN_RETRAIT)].sort_values(["rapport", "manque"],
                                                                                ascending=[True, False]).head(10)
        if not len(e):
            continue
        e = e.assign(nom=e["code"].map(C.nom_epci))
        exemple = exemple or (p, e.iloc[0])
        L += [f"**{pluriel(C.lab.get(p, p)).capitalize()}**, intercommunalités de plus de "
              f"{nombre(POP_MIN_RETRAIT)} habitants où l'effectif observé est le plus en dessous de l'attendu", "",
              _tableau(e, ["nom", "pop", "effectif", "effectif_attendu", "rapport"],
                       ["Intercommunalité", "Habitants", "Observés", "Attendus d'après le profil", "Rapport"],
                       {"pop": nombre, "effectif": nombre, "effectif_attendu": lambda v: nombre(v, 1),
                        "rapport": lambda v: nombre(v, 2)}), ""]
    if exemple:
        p, r = exemple
        L += _comment_lire(
            f"Par exemple, la première intercommunalité du tableau compte {nombre(r['effectif'])} {pluriel(C.lab[p]) if r['effectif'] != 1 else C.lab[p].lower()} "
            f"pour {nombre(r['pop'])} habitants. Des intercommunalités de profil comparable (âge, revenus, "
            f"pauvreté, densité de population...) en comptent environ {nombre(r['effectif_attendu'])}. Le rapport "
            f"de {nombre(r['rapport'], 2)} se lit « {nombre(r['rapport'] * 100)} % de l'effectif attendu ».",
            "Ce n'est pas une mesure du besoin de soins. C'est une comparaison avec des territoires semblables, "
            "qui peuvent eux-mêmes être mal dotés. Ces tableaux décrivent un écart et ne classent pas les "
            "territoires. Sur de petits effectifs, quelques arrivées ou départs suffisent à changer la liste d'une "
            "année à l'autre.")
    if isinstance(q, pd.DataFrame) and len(q):
        q = q[q["prof"].isin(PRINCIPALES[famille])].assign(libelle=lambda d: d["prof"].map(C.lab))
        L += _plus_loin([
            "Régression de Poisson par profession, avec la population en offset et des erreurs standard robustes "
            "(sandwich). Variables explicatives, les indicateurs sociodémographiques de l'INSEE, standardisés, la "
            "densité de population étant prise en logarithme. Une dispersion nettement supérieure à 1 signale une "
            "hétérogénéité que le modèle n'explique pas. Coefficients dans modeles_coefficients.csv.",
            _phrase_nb(q), "",
            _tableau(q, ["libelle", "n", "pseudo_r2", "dispersion"],
                     ["Profession", "Territoires", "Part de la déviance expliquée", "Dispersion"],
                     {"pseudo_r2": lambda v: nombre(v, 2), "n": nombre, "dispersion": lambda v: nombre(v, 1)})])
    return L


# ---------------------------------------------------------------- « En bref »
def _plus_et_moins_inegales(C, famille, effectif_min):
    ps = [p for p in C.ids(famille) if p in C.ineg.index and C.nat.get(p, 0) >= effectif_min]
    if len(ps) < 2:
        return ""
    g = C.ineg.loc[ps, "gini"].sort_values()
    lo, hi = g.index[0], g.index[-1]
    return (f"Parmi les professions qui comptent au moins {nombre(effectif_min)} personnes, les "
            f"{pluriel(C.lab[hi])} sont les plus inégalement répartis entre "
            f"intercommunalités (indice de Gini {nombre(g[hi], 2)}), les {pluriel(C.lab[lo])} les moins "
            f"({nombre(g[lo], 2)}).")


def _phrase_gradient(C, p):
    cd = C.R.get("classes_densite")
    if not isinstance(cd, pd.DataFrame) or not len(cd):
        return ""
    t = cd[(cd["niveau"] == "epci") & (cd["prof"] == p)].set_index("classe")["densite_agregee"]
    a, b = CLASSES_DENSITE[-1][2], CLASSES_DENSITE[0][2]
    if a not in t or b not in t or not t[b]:
        return ""
    return (f"Les intercommunalités denses comptent {fois(t[a], t[b])} {de(pluriel(C.lab[p]))} par habitant que "
            f"les très peu denses ({nombre(t[a], 1)} contre {nombre(t[b], 1)} pour 10 000 habitants).")


def _ic(r):
    """Intervalle de confiance à 95 % d'une ligne de corrélations, s'il est publié."""
    return (float(r["ic95_bas"]), float(r["ic95_haut"])) if "ic95_bas" in r.index and "ic95_haut" in r.index else None


def _phrase_lien(C, p, ctxlab):
    cc = C.R.get("correlations_contexte")
    if not isinstance(cc, pd.DataFrame) or not len(cc):
        return ""
    f = cc[(cc["niveau"] == "epci") & (cc["mode"] == "all") & (cc["prof"] == p) & (cc["variable"] != "densite_pop")]
    if "rho_partiel_densite" not in f or not len(f):
        return ""
    f = f[(f["q_bh_partiel"] < .05) & f["rho_partiel_densite"].notna()]
    if not len(f):
        return ""
    r = f.loc[f["rho_partiel_densite"].abs().idxmax()]
    ph = phrase_correlation(r["rho_partiel_densite"], ctxlab.get(r["variable"], r["variable"]), C.lab[p],
                            (r["ic95_bas_partiel"], r["ic95_haut_partiel"]))
    return ("À densité de population égale, l" + ph[1:] + " Ce lien décrit des territoires et ne dit rien d'une cause."
            if ph.startswith("Les territoires") else "")


def _phrase_retrait(C, p):
    ea = C.R.get("ecarts_attendu")
    if not isinstance(ea, pd.DataFrame) or not len(ea):
        return ""
    e = ea[(ea["prof"] == p) & (ea["effectif_attendu"] >= 5) & (ea["rapport"] < .5)]
    if not len(e):
        return ""
    return (f"{nombre(len(e)).capitalize()} intercommunalités, où vivent {pct(e['pop'].sum() / C.pop_epci.sum())} des "
            f"habitants, comptent moins de la moitié des {pluriel(C.lab[p])} observés dans des territoires de profil "
            f"comparable (parmi celles où l'on en attendrait au moins cinq).")


def _en_bref_sm(C, ctxlab):
    P = []
    if C.present("psychologue"):
        d = C.densite("psychologue")
        P.append(f"On compte {nombre(C.nat['psychologue'])} psychologues en exercice en France, soit "
                 f"{un_pour(d)}.")
    if C.present("psychiatre"):
        g = C.ineg["gini"].get("psychiatre", np.nan)
        P.append(f"Les psychiatres sont {nombre(C.nat['psychiatre'])}, soit {un_pour(C.densite('psychiatre'))}. "
                 f"Leur répartition est {phrase_gini(g)} (indice de Gini {nombre(g, 2)}).")
    if C.present("pedopsychiatre") and C.present("q_psychiatrie_enfant"):
        P.append(f"{nombre(C.nat['pedopsychiatre'])} médecins sont inscrits comme pédopsychiatres, et "
                 f"{nombre(C.nat['q_psychiatrie_enfant'])} psychiatres ont une qualification pour l'enfant et "
                 f"l'adolescent, toutes voies confondues.")
    s1, s2 = C.sans("psychiatre"), C.sans("psychologue", "psychiatre")
    if np.isfinite(s1):
        P.append(f"{pct(s1).capitalize()} des habitants vivent dans une intercommunalité où aucun psychiatre ne "
                 f"déclare exercer, et {pct(s2)} dans une intercommunalité sans psychologue ni psychiatre. "
                 + C.phrase_cmp(total=False))
    P += [_phrase_gradient(C, "psychologue"), _phrase_lien(C, "psychologue", ctxlab), _phrase_retrait(C, "psychologue"),
          rapport_bases.phrase_evolution(C, "psychiatre")]
    es = C.ids(SM, "perimetre_elargi")
    if es:
        tot = C.elargi_personnes or sum(C.nat[p] for p in es)
        inf = config.PREFIXE_ELARGI + "infirmier"
        P.append(f"{nombre(tot, 0)} personnes sont salariées d'un établissement psychiatrique ou "
                 f"médico-psychologique" + (f", dont {nombre(C.nat[inf])} infirmiers" if inf in C.nat else "")
                 + ". Ce périmètre élargi se lit à côté des chiffres précédents, il ne s'y ajoute pas.")
    return [p for p in P if p]


def _en_bref_sante(C, ctxlab):
    P = []
    if C.present("medecin_generaliste"):
        P.append(f"On compte {nombre(C.nat['medecin_generaliste'])} médecins généralistes en exercice, soit "
                 f"{un_pour(C.densite('medecin_generaliste'))}.")
    P.append(_plus_et_moins_inegales(C, SANTE, 5000))
    if "pediatre" in C.n_epci:
        P.append(f"{pct(C.sans('pediatre')).capitalize()} des habitants vivent dans une intercommunalité sans "
                 f"pédiatre.")
    P += [_phrase_gradient(C, "medecin_generaliste"), _phrase_lien(C, "medecin_generaliste", ctxlab),
          _phrase_retrait(C, "medecin_generaliste"), rapport_bases.phrase_evolution(C, "medecin_generaliste")]
    return [p for p in P if p]


# ---------------------------------------------------------------- croisement
def _croisement(C: Contexte):
    L = ["## Santé et santé mentale ensemble", ""]
    cp = C.R.get("correlations_professions", {}).get("epci")
    P = []
    if isinstance(cp, pd.DataFrame) and "medecin_generaliste" in cp:
        for p in ["psychologue", "psychiatre"]:
            if p in cp:
                rho = cp.at["medecin_generaliste", p]
                P.append(f"D'une intercommunalité à l'autre, la densité de médecins généralistes et celle de "
                         f"{pluriel(C.lab[p])} varient dans le même sens, avec un lien {force(rho)} "
                         f"(rho = {nombre(rho, 2)}).")
    d, pop = C.d_epci, C.pop_epci
    for p in ["psychologue", "psychiatre"]:
        if p in d and "medecin_generaliste" in d:
            bas = (d[p] <= d[p].quantile(.25)) & (d["medecin_generaliste"] <= d["medecin_generaliste"].quantile(.25))
            P.append(f"{nombre(bas.sum())} intercommunalités, où vivent {nombre(pop[bas].sum())} habitants "
                     f"({pct(pop[bas].sum() / pop.sum())} de la population), font partie du quart le moins bien "
                     f"doté à la fois en médecins généralistes et en {pluriel(C.lab[p])}.")
    if P:
        L += [f"- {x}" for x in P] + [""]
        L += _comment_lire("Le « quart le moins bien doté » regroupe les 25 % d'intercommunalités qui ont la "
                           "densité la plus faible pour la profession. Un territoire peut y figurer pour les deux "
                           "professions sans que l'une explique l'autre.")
    # le croisement ne garde que ce qui rapproche les deux familles, l'outre-mer a sa partie, la ressemblance entre
    # voisins et les coefficients du modèle vont avec les analyses pour les chercheurs
    L += _composition(C) + _typologie(C, "tout")
    om = _outre_mer(C)
    if om:
        L += [l[1:] if l.startswith("###") else l for l in om]   # « ### Outre-mer » devient une partie
    return L


def _typologie(C: Contexte, fam="tout"):
    """Profils d'offre des intercommunalités (CAH de Ward), avec le résumé de l'ACP, pour une famille."""
    tp, q, ch, ine = (C.R.get(k) for k in ("typologie_profils", "typologie_qualite", "acp_charges", "acp_inertie"))
    if not isinstance(tp, pd.DataFrame) or not len(tp) or "famille" not in tp:
        return []
    tp = tp[tp["famille"] == fam]
    if tp.empty:
        return []
    piv = tp.pivot_table(index="classe", columns="prof", values="indice_vs_national")
    info = tp.drop_duplicates("classe").set_index("classe")
    noms = noms_classes({k: {C.lab.get(p, p): v for p, v in r.items()} for k, r in piv.iterrows()})
    qq = q[q["famille"] == fam].iloc[0]
    part = ine[ine["famille"] == fam].sort_values("axe")["part_inertie"].to_numpy()
    c = ch[(ch["famille"] == fam)].pivot_table(index="prof", columns="axe", values="correlation")
    objet = {"sm": "leur offre de santé mentale", "sante": "leur offre de soins générale",
             "tout": "l'ensemble de leur offre, santé et santé mentale"}[fam]
    tete = (f"Selon {objet}, les intercommunalités se répartissent en {int(qq['classes'])} groupes. "
            f"Le premier axe de l'analyse en composantes principales résume {pct(part[0])} des différences entre "
            f"intercommunalités, et toutes les professions y vont dans le même sens. Il distingue les territoires où "
            f"l'offre est élevée dans l'ensemble de ceux où elle est faible." if (c[1] > 0).all() else
            f"Selon {objet}, les intercommunalités se répartissent en {int(qq['classes'])} groupes.")
    pos = [C.lab.get(p, p) for p in c[2].sort_values(ascending=False).index if c.at[p, 2] >= .3]
    neg = [C.lab.get(p, p) for p in c[2].sort_values().index if c.at[p, 2] <= -.3]
    if pos and neg:
        tete += (f" Le deuxième axe ({pct(part[1])}) oppose, à niveau d'offre égal, les territoires relativement mieux "
                 f"dotés en {_liste(pluriel(x) for x in pos)} à ceux relativement mieux dotés en "
                 f"{_liste(pluriel(x) for x in neg)}.")
    if qq["silhouette"] < .25:
        tete += " Les groupes sont peu séparés, ils découpent un continuum plutôt que des types bien distincts."
    titre = {"sm": "### Profils d'offre de santé mentale des intercommunalités",
             "sante": "### Profils d'offre de soins des intercommunalités",
             "tout": "### Profils d'offre des intercommunalités, santé et santé mentale ensemble"}[fam]
    L = [titre, "", tete, "",
         "| Groupe | Intercommunalités | Habitants | " + " | ".join(C.lab.get(x, x) for x in piv.columns) + " |",
         "|" + "---|" * (len(piv.columns) + 3)]
    for k, r in piv.iterrows():
        L.append(f"| {noms[k]} | {info.at[k, 'territoires']} | {nombre(info.at[k, 'population'])} | "
                 + " | ".join(nombre(v) for v in r) + " |")
    L.append("")
    k0, p0 = piv.index[0], piv.columns[0]
    L += _comment_lire(
        DEFINITIONS["indice100"],
        f"Par exemple, dans le groupe « {noms[k0]} », l'indice des {pluriel(C.lab.get(p0, p0))} vaut "
        f"{nombre(piv.at[k0, p0])}. Le nom de chaque groupe résume ses indices, en dessous de 80 le groupe est dit "
        f"moins doté, au-dessus de 120 mieux doté.")
    L += _plus_loin([
        "Analyse en composantes principales sur le logarithme des densités, centrées et réduites, puis classification "
        "ascendante hiérarchique (méthode de Ward) sur les mêmes données. Nombre de groupes choisi par la silhouette "
        f"moyenne entre 3 et 6 ({int(qq['classes'])} groupes, silhouette {nombre(qq['silhouette'], 2)}, groupes qui "
        f"réunissent {pct(qq['part_inertie_classes'])} des différences). Une silhouette inférieure à 0,25 signale des "
        f"groupes peu séparés. Part des différences résumée par les axes, "
        + ", ".join(f"axe {i + 1} {pct(v)}" for i, v in enumerate(part[:4]))
        + ". Corrélation des professions avec les axes 1 et 2, "
        + ", ".join(f"{C.lab.get(x, x).lower()} {nombre(c.at[x, 1], 2)} et {nombre(c.at[x, 2], 2)}" for x in c.index)
        + ". Affectation de chaque intercommunalité dans typologie_affectation.csv."])
    return L


def _moran(C: Contexte):
    sp = C.R.get("spatial")
    if not isinstance(sp, pd.DataFrame) or not len(sp):
        return []
    t = sp[sp["niveau"] == "epci"].assign(libelle=lambda d: d["prof"].map(C.lab)).sort_values("moran_I", ascending=False)
    bas, haut = t.iloc[-1], t.iloc[0]
    L = ["### Ressemblance entre territoires voisins", "",
         f"L'indice de Moran entre intercommunalités va de {nombre(bas['moran_I'], 2)} pour les "
         f"{pluriel(bas['libelle'])} à {nombre(haut['moran_I'], 2)} pour les {pluriel(haut['libelle'])}."
         + (" Pour toutes les professions, les territoires voisins se ressemblent plus que le hasard ne le ferait."
            if (t["moran_I"] > 0).all() and (t["p_permutation"] < .05).all() else ""), "",
         _tableau(t, ["libelle", "moran_I"], ["Profession", "Indice de Moran (intercommunalités)"],
                  {"moran_I": lambda v: nombre(v, 2)}), ""]
    r = t.iloc[0]
    L += _comment_lire("L'indice de Moran i" + DEFINITIONS["moran"][1:],
                       f"Par exemple, l'indice de {nombre(r['moran_I'], 2)} pour les {pluriel(r['libelle'])} indique "
                       f"que les intercommunalités voisines ont souvent des densités proches.")
    t2 = sp.assign(libelle=lambda d: d["prof"].map(C.lab),
                   niveau=lambda d: d["niveau"].map({"epci": "Intercommunalités", "dep": "Départements"}))
    L += _plus_loin(["Indice de Moran sur le logarithme de la densité, voisinage par contiguïté, pondération "
                     "normalisée par ligne, p-valeur par 999 permutations.", "",
                     _tableau(t2, ["libelle", "niveau", "moran_I", "p_permutation"],
                              ["Profession", "Niveau", "I de Moran", "p"],
                              {"moran_I": lambda v: nombre(v, 2),
                               "p_permutation": lambda v: "< 0,001" if v < .001 else nombre(v, 3)})])
    return L


# ---------------------------------------------------------------- rapport complet
INTRO = ("Ce rapport s'appuie sur les répertoires publics des professionnels de santé et sur d'autres données "
         "publiques (INSEE, Assurance Maladie, Santé publique France). Il décrit l'offre de soins, il ne "
         "conclut pas. Toutes les analyses portent sur des territoires, jamais sur des personnes.")
LECTURE = ("Chaque partie commence par un résumé « En bref ». Chaque tableau est suivi d'un paragraphe « Comment "
           "lire ». Les détails techniques sont repliés sous « Pour aller plus loin ». Un glossaire termine le document.")


def graphique(nom):
    """Emplacement d'un graphique, invisible dans le Markdown, remplacé par la figure dans le site."""
    return [f"<!--GRAPHIQUE {nom}-->", ""]


def ecrire(out, agg, ref, professions, insee, R, jour):
    """Écrit rapport.md (complet), rapport_sante_mentale.md et rapport_sante.md. Renvoie le texte des trois,
    pour le contrôle du langage."""
    C = Contexte(agg, ref, professions, R)
    C.externes = insee or {}
    ctxlab = indicateurs.libelles(insee)
    # chaque rapport suit le même ordre, l'offre, sa répartition, l'offre et le profil des habitants, l'offre et les
    # besoins, puis les profils d'intercommunalités (relecture du 8 octobre 2026, demande de Lucas)
    intro_offre = "Combien de professionnels exercent, comment l'offre évolue et dans quels cadres elle s'exerce."
    intro_repart = "Comment l'offre se répartit entre les territoires, et à quelle distance des habitants."
    intro_profil = ("Ce qui accompagne la présence des professionnels dans les territoires. Ces liens décrivent des "
                    "territoires et ne disent pas ce qui cause la présence ou l'absence de l'offre.")
    partie_sm = (["## Santé mentale", "", "### En bref", ""]
                 + [f"- {p}" for p in _en_bref_sm(C, ctxlab)] + [""]
                 + _groupe("L'offre de soins en santé mentale", intro_offre, _panorama(C, SM), rapport_bases.evolution(C, SM),
                           _hopital(C), _public_cible(C, SM), _modes(C, SM), _porte(C, SM), _exercice(C, SM))
                 + _groupe("La répartition de l'offre sur le territoire", intro_repart, _gradient(C, SM), _entonnoir(C, SM),
                           _zones(C, SM), _acces(C, SM), _financier(C, SM))
                 + _groupe("L'offre et le profil des habitants", intro_profil, _correlations(C, SM, ctxlab),
                           _vulnerabilite(C, ctxlab), _revenu(C, SM), rapport_bases.gwr_section(C), _retrait(C, SM))
                 + _recours(C, insee, ctxlab) + rapport_bases.ald(C, SM) + _besoins_spf(C, insee) + _enfance_handicap(C, SM)
                 + rapport_bases.allocations(C, SM) + _quadrants(C, ctxlab) + rapport_bases.offre_besoin_carte(C, insee, ctxlab)
                 + _loi_inverse(C, ctxlab) + rapport_bases.indicateurs_entre_eux(C, ctxlab) + _croisements(C, ctxlab, SM)
                 + _typologie(C, "sm"))
    partie_sante = (["## Santé", "", "### En bref", ""]
                    + [f"- {p}" for p in _en_bref_sante(C, ctxlab)] + [""]
                    + _groupe("L'offre de soins générale", intro_offre, _panorama(C, SANTE), rapport_bases.evolution(C, SANTE),
                              _public_cible(C, SANTE), _modes(C, SANTE), _porte(C, SANTE), _exercice(C, SANTE))
                    + _groupe("La répartition de l'offre sur le territoire", intro_repart, _gradient(C, SANTE),
                              _entonnoir(C, SANTE), _zones(C, SANTE), _acces(C, SANTE), _financier(C, SANTE))
                    + _groupe("L'offre et le profil des habitants", intro_profil, _correlations(C, SANTE, ctxlab),
                              _revenu(C, SANTE), _retrait(C, SANTE))
                    + _groupe("Maladies chroniques et handicap", "Ces indicateurs décrivent des personnes reconnues "
                              "malades ou en situation de handicap. Ils dépendent aussi du recours aux soins et ne "
                              "mesurent pas à eux seuls un besoin.", rapport_bases.ald(C, SANTE), _enfance_handicap(C, SANTE),
                              _croisements(C, ctxlab, SANTE, "###"))
                    + _typologie(C, "sante"))
    croisement = _croisement(C) + _chercheurs(C)

    versions = {
        "rapport.md": ([f"# {config.NOM_PROJET}, rapport du {date_longue(jour)}", "", INTRO, "",
                        "Il se lit en trois parties. La santé mentale vient d'abord, puis l'offre de soins générale, "
                        "puis un court croisement des deux. " + LECTURE, ""]
                       + partie_sm + partie_sante + croisement, None),
        "rapport_sante_mentale.md": ([f"# Offre de soins en santé mentale, rapport du {date_longue(jour)}", "", INTRO, "",
                                      "Ce rapport porte sur la santé mentale, puis croise brièvement avec l'offre de "
                                      "soins générale. Un rapport distinct porte sur la santé. " + LECTURE, ""]
                                     + partie_sm + croisement, SM),
        "rapport_sante.md": ([f"# Offre de soins en santé, rapport du {date_longue(jour)}", "", INTRO, "",
                              "Ce rapport porte sur l'offre de soins générale, puis croise brièvement avec la santé "
                              "mentale. Un rapport distinct porte sur la santé mentale. " + LECTURE, ""]
                             + partie_sante + croisement, SANTE),
    }
    textes = []
    for nom, (L, famille) in versions.items():
        L = L + _fin(insee, famille)
        texte = "\n".join(L)
        (out / nom).write_text(texte, encoding="utf-8")
        textes.append(texte)
    return "\n".join(textes)


MENTION_ODBL = ("Ce document contient des informations issues de bases de l'Assurance Maladie (Cnam, data.ameli.fr, "
                "cartographie des pathologies, secteurs conventionnels, patients sans médecin traitant), mises à "
                "disposition sous "
                "[licence ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Les bases qui en dérivent sont publiées sous la "
                "même licence, dans les fichiers suffixés _odbl.")


def _date(d) -> str:
    """Date longue quand la date est au format AAAA-MM-JJ, sinon telle quelle."""
    import re
    return date_longue(d) if re.match(r"^\d{4}-\d{2}-\d{2}", str(d)) else str(d)


def ligne_source(e) -> str:
    """Référence d'une source du journal, avec lien vers la page du jeu de données, producteur, licence et date."""
    nom = f"[{e.source}]({e.page or e.url})" if (getattr(e, "page", "") or e.url) else e.source
    morceaux = [x for x in (getattr(e, "producteur", ""), getattr(e, "licence", ""),
                            f"données du {_date(e.date_donnees)}" if e.date_donnees else "") if x]
    return f"- {nom}" + (", " + ", ".join(morceaux) if morceaux else "") + "."


def _fin(insee, famille):
    """Sources, précautions et glossaire, filtrés selon la famille du rapport (None pour le rapport complet)."""
    L = ["## Sources et contrôles", "",
          "Les libellés de certaines nomenclatures officielles (FINESS, secteurs du RPPS) sont remplacés à "
          "l'affichage par des formulations respectueuses des personnes, en gardant les sigles d'usage. La table "
          "de correspondance est publiée avec les résultats (libelles.csv), et les fichiers CSV gardent les deux "
          "libellés.", ""]
    for e in [e for e in JOURNAL.entrees if e.statut != "ignoré"]:
        L.append(ligne_source(e) + (f" {e.detail[0].upper()}{e.detail[1:].rstrip('.')}." if e.detail and e.statut == "ok" else
                                    f" Statut, {e.statut}. {e.detail}" if e.statut != "ok" else ""))
    L.append("")
    if insee and indicateurs.odbl(insee):
        L += [MENTION_ODBL, ""]
    L += _plus_loin([f"- {nom}, {res}" for nom, res in JOURNAL.controles])

    L += ["## Précautions de lecture", "", DEFINITIONS["rpps"], "",
          "Un professionnel qui exerce dans plusieurs territoires compte dans chacun, mais une seule fois pour la "
          "France entière. Les effectifs attendus comparent des territoires semblables et ne disent rien d'un "
          "besoin de soins. Les psychologues, psychiatres et autres professions sont présentés côte à côte, sans "
          "être additionnés, car ils ne sont pas interchangeables.", ""]

    garder = lambda fam: famille is None or not fam or fam == famille  # noqa: E731
    L += ["## Glossaire", ""]
    for _id, terme, definition, fam in GLOSSAIRE:
        if garder(fam):
            L += [f"**{terme}.** {definition}", ""]
    L += ["### Indicateurs de contexte", ""]
    for d in indicateurs.liste(insee):
        if garder(d["famille"]):
            L += [f"**{d['label']}** ({d['unite']}). {d['explication']} Source, {d['source']}.", ""]
    if insee:
        L += ["Millésimes INSEE, " + ", ".join(sorted({str(v) for v in insee["millesimes"].values() if v})) + ".", ""]
    return L
