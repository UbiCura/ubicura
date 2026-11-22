"""Contrôle des phrases chiffrées des rapports nationaux : chaque chiffre important est recalculé à partir des tableaux
publiés de la même version, sans passer par le code qui écrit les rapports, puis cherché dans sa phrase. Des règles
générales passent aussi sur toutes les phrases, et chaque nombre du texte est cherché dans les tableaux publiés.

Demande du 17 novembre 2026, après deux relectures indépendantes qui ont trouvé des chiffres faux que les contrôles
ne voyaient pas : ils vérifiaient que les pages étaient cohérentes entre elles, pas que chaque phrase disait ce que
dit son tableau.

Trois parties.
1. Phrases recalculées (PHRASES) : une fonction par phrase, qui lit les CSV, recalcule et compare.
2. Règles générales, sur toutes les phrases : lien sous le seuil de la règle du site, comptes de territoires
   impossibles (plus de 101 départements), « N sur M » avec N plus grand que M, part au-delà de 100 %, accords.
3. Rattachement : chaque nombre d'au moins trois chiffres écrit dans le texte est cherché parmi les valeurs des
   tableaux publiés. Les nombres non retrouvés sont listés pour la relecture, sans bloquer.

    python outils\\controle_phrases.py [resultats\\AAAA-MM-JJ]

Écrit controle_phrases.md dans le dossier de la version. Code de sortie 0 si les parties 1 et 2 ne trouvent rien,
20 sinon. Lancé aussi par outils/coherence_rapports.py, donc avant chaque publication.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import regle_lien  # noqa: E402
from pipeline.lecture import nombre, pct, un_pour  # noqa: E402

RAPPORTS = {"sm": "rapport_sante_mentale.md", "s": "rapport_sante.md"}
ESPACES = re.compile(r"[   ]")


def norm(t: str) -> str:
    """Espaces insécables en espaces simples et signe moins typographique en trait d'union, pour comparer."""
    return ESPACES.sub(" ", t).replace("−", "-")


def f(x, d=0) -> str:
    return norm(nombre(x, d))


def p(x, d=1) -> str:
    return norm(pct(x, d))


class Version:
    def __init__(self, dossier: Path):
        self.dossier = dossier
        self.textes = {k: norm((dossier / v).read_text(encoding="utf-8")) for k, v in RAPPORTS.items()
                       if (dossier / v).exists()}
        self._csv: dict[str, pd.DataFrame] = {}

    def csv(self, nom: str) -> pd.DataFrame:
        if nom not in self._csv:
            self._csv[nom] = pd.read_csv(self.dossier / f"{nom}.csv", sep=";", decimal=",", dtype={"code": str})
        return self._csv[nom]

    def prose(self, cle: str) -> list[str]:
        """Phrases hors tableaux, titres et blocs HTML, coupées sur la ponctuation finale."""
        lignes = [l for l in self.textes.get(cle, "").splitlines()
                  if l.strip() and not l.lstrip().startswith(("|", "#", "<", "```"))]
        phrases = []
        for l in lignes:
            phrases += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀÉÈÊÎÔÛ0-9«])", l) if s.strip()]
        return phrases


class Compte:
    def __init__(self):
        self.ok: list[str] = []
        self.fautes: list[str] = []

    def egal(self, ou: str, attendu: str, texte: str, quoi: str):
        """attendu (déjà formaté) doit se lire dans le texte de la phrase."""
        if attendu and attendu in texte:
            self.ok.append(f"{ou}, {quoi} : {attendu}")
        else:
            self.fautes.append(f"{ou}, {quoi} : attendu « {attendu} » d'après les tableaux, phrase « {texte[:220]} »")


def phrase(V: Version, cle: str, ancre: str) -> str | None:
    """Premier paragraphe ou point de liste du rapport qui contient l'ancre (expression régulière)."""
    for s in V.textes.get(cle, "").splitlines():
        if not s.lstrip().startswith(("|", "#", "<")) and re.search(ancre, s):
            return s
    return None


# ---------------------------------------------------------------- 1. phrases recalculées
PHRASES = []


def regle(fn):
    PHRASES.append(fn)
    return fn


def _effectif(V, prof):
    e = V.csv("effectifs_france")
    return int(e[(e["prof"] == prof) & (e["mode"] == "all")]["n"].iloc[0])


def _pop_france(V):
    c = V.csv("combinaisons")
    return int(c[c["niveau"] == "epci"]["population"].sum())


def _ineg(V, prof, niv="epci"):
    i = V.csv("inegalites")
    return i[(i["niveau"] == niv) & (i["mode"] == "all") & (i["prof"] == prof)].iloc[0]


@regle
def effectifs_en_bref(V, C):
    """En bref : effectifs, « un pour », Gini des psychiatres."""
    s = phrase(V, "sm", r"^- On compte .* psychologues en exercice")
    n = _effectif(V, "psychologue")
    if s:
        C.egal("SM, En bref, psychologues", f(n), s, "effectif")
        C.egal("SM, En bref, psychologues", norm(un_pour(1e4 * n / _pop_france(V))), s, "un pour")
    s = phrase(V, "sm", r"^- Les psychiatres sont")
    if s:
        C.egal("SM, En bref, psychiatres", f(_effectif(V, "psychiatre")), s, "effectif")
        C.egal("SM, En bref, psychiatres", norm(un_pour(1e4 * _effectif(V, "psychiatre") / _pop_france(V))), s,
               "un pour")
        C.egal("SM, En bref, psychiatres", f(_ineg(V, "psychiatre")["gini"], 2), s, "Gini")
    s = phrase(V, "sm", r"médecins sont inscrits comme pédopsychiatres")
    if s:
        C.egal("SM, En bref, pédopsychiatres", f(_effectif(V, "pedopsychiatre")), s, "effectif")


@regle
def sans_psychiatre(V, C):
    """Intercommunalités sans psychiatre déclaré : nombre, total, part des habitants, sans psychologue ni psychiatre,
    et celles qui accueillent un CMP (effectifs_epci_all.csv et cmp_par_public.csv)."""
    c = V.csv("combinaisons")
    e = c[c["niveau"] == "epci"]
    sans = e[e["psychiatre"].astype(str) == "False"]
    rien = e[(e["psychiatre"].astype(str) == "False") & (e["psychologue"].astype(str) == "False")]
    ee = V.csv("effectifs_epci_all")
    codes_sans = set(ee.loc[pd.to_numeric(ee["n_psychiatre"], errors="coerce").fillna(0) == 0, "code"].astype(str))
    cp = V.csv("cmp_par_public")
    avec_cmp = cp[(cp["niveau"] == "epci") & cp["code"].astype(str).isin(codes_sans)
                  & (pd.to_numeric(cp["cmp"], errors="coerce") > 0)]
    for cle in ("sm",):
        s = phrase(V, cle, r"intercommunalités \(sur .*\) où aucun psychiatre ne déclare exercer")
        if not s:
            C.fautes.append("SM, En bref : phrase des intercommunalités sans psychiatre introuvable")
            continue
        ou = "SM, En bref, sans psychiatre"
        C.egal(ou, f"{p(sans['part_population'].sum())} des habitants", s, "part des habitants")
        C.egal(ou, f"l'une des {f(sans['territoires'].sum())} intercommunalités (sur {f(e['territoires'].sum())})", s,
               "nombre et total")
        C.egal(ou, f"et {p(rien['part_population'].sum())} dans une intercommunalité sans psychologue ni psychiatre",
               s, "sans psychologue ni psychiatre")
        if len(codes_sans) != int(sans["territoires"].sum()):
            C.fautes.append(f"{ou} : {len(codes_sans)} intercommunalités sans psychiatre dans effectifs_epci_all.csv, "
                            f"{int(sans['territoires'].sum())} dans combinaisons.csv")
        C.egal(ou, f"{f(len(avec_cmp))} de ces {f(len(codes_sans))} intercommunalités accueillent pourtant", s,
               "avec un CMP")


@regle
def cmp_par_public(V, C):
    """Nombre de CMP distincts et par public (cmp_par_public.csv, somme des départements)."""
    cp = V.csv("cmp_par_public")
    d = cp[cp["niveau"] == "dep"]
    tot = {k: int(pd.to_numeric(d[k]).sum()) for k in ("cmp", "adultes", "enfants", "les_deux", "non_precise")}
    s = phrase(V, "sm", r"recensent .* centres médico-psychologiques \(CMP\) distincts")
    if s:
        C.egal("SM, structures, CMP", f"recensent {f(tot['cmp'])} centres médico-psychologiques", s, "total")
    s2 = phrase(V, "sm", r"accueillent des adultes et .* des enfants et adolescents, dont")
    if s2:
        C.egal("SM, structures, CMP", f"{f(tot['adultes'])} accueillent des adultes et {f(tot['enfants'])} des enfants",
               s2, "par public")
        C.egal("SM, structures, CMP", f"dont {f(tot['les_deux'])} les deux publics", s2, "deux publics")
    s3 = phrase(V, "sm", r"lieux de CMP distincts")
    if s3:
        C.egal("SM, SAE", f"{f(tot['cmp'])} lieux de CMP distincts", s3, "total")


@regle
def csapa_etablissements(V, C):
    """Établissements CSAPA de FINESS, plausibles face au bilan RECAP de l'OFDT cité dans la même phrase : entre 0,6 et
    1,2 fois son nombre, et au moins la moitié des lieux (« 674 lieux de CSAPA correspondent à 6 établissements de
    FINESS », la catégorie FINESS des lignes vérifiées était effacée, relecture du 21 novembre 2026)."""
    s = phrase(V, "sm", r"lieux de CSAPA correspondent à")
    if not s:
        return
    m = re.search(r"([\d  ]+) lieux de CSAPA correspondent à ([\d  ]+) établissements de FINESS.*?des ([\d  ]+) CSAPA",
                  s)
    if not m:
        C.fautes.append(f"SM, CSAPA : phrase illisible « {s[:200]} »")
        return
    lieux_, etab, ofdt = (int(re.sub(r"\D", "", g)) for g in m.groups())
    if .6 * ofdt <= etab <= 1.2 * ofdt and etab >= lieux_ / 2:
        C.ok.append(f"SM, CSAPA, {etab} établissements pour {ofdt} au bilan de l'OFDT")
    else:
        C.fautes.append(f"SM, CSAPA : {etab} établissements de FINESS pour {lieux_} lieux et {ofdt} CSAPA au bilan de "
                        f"l'OFDT, hors de la fourchette plausible")


@regle
def classes_densite(V, C):
    """En bref : densité de psychologues des intercommunalités denses et très peu denses (classes_densite.csv)."""
    t = V.csv("classes_densite")
    t = t[(t["niveau"] == "epci") & (t["prof"] == "psychologue")]
    dense = t[t["classe"].str.startswith("Dense")]["densite_agregee"].iloc[0]
    tpd = t[t["classe"].str.startswith("Très peu dense")]["densite_agregee"].iloc[0]
    s = phrase(V, "sm", r"^- Les intercommunalités denses comptent")
    if s:
        C.egal("SM, En bref, classes de densité", f"({f(dense, 1)} contre {f(tpd, 1)} pour 10 000 habitants)", s,
               "densités")
        C.egal("SM, En bref, classes de densité", f"{f(dense / tpd, 1)} fois plus", s, "rapport")


@regle
def evolution(V, C):
    """Évolution de la densité de psychiatres depuis 2016, en France et départements en baisse."""
    e = V.csv("evolution_offre_resume")
    fr = e[(e["niveau"] == "FR") & (e["prof"] == "psychiatre")].iloc[0]
    dep = e[(e["niveau"] == "dep") & (e["prof"] == "psychiatre")]["evolution_densite"].dropna()
    s = phrase(V, "sm", r"^- D'après les séries de la DREES, de \d+ à \d+, la densité de psychiatres")
    if s:
        ev = fr["evolution_densite"]
        C.egal("SM, En bref, évolution", f"{'a augmenté' if ev > 0 else 'a baissé'} de {f(abs(ev) * 100, 1)} %", s,
               "évolution en France")
        C.egal("SM, En bref, évolution", f"baissé dans {f((dep < 0).sum())} départements sur {f(len(dep))}", s,
               "départements en baisse")


def _corr(V, niv, prof, var, fichier="correlations_contexte"):
    t = V.csv(fichier)
    x = t[(t["niveau"] == niv) & (t["mode"] == "all") & (t["prof"] == prof) & (t["variable"] == var)]
    return x.iloc[0] if len(x) else None


@regle
def suicide(V, C):
    """Taux de suicide et densité de psychiatres et de psychologues, entre départements sans Mayotte, et verdict selon
    la règle du site."""
    s = phrase(V, "sm", r"la corrélation de rang entre le taux de décès par suicide et la densité")
    if not s:
        return
    for prof, lab in (("psychiatre", "psychiatres"), ("psychologue", "psychologues")):
        r = _corr(V, "dep", prof, "suicides")
        if r is None:
            C.fautes.append(f"SM, suicide : corrélation {prof} absente de correlations_contexte.csv")
            continue
        if r["n"] > 100:
            C.fautes.append(f"SM, suicide, {lab} : {int(r['n'])} départements, Mayotte comprise")
        C.egal("SM, suicide", f"{f(r['rho_spearman'], 2)} pour les {lab} (fourchette plausible de "
                              f"{f(r['ic95_bas'], 2)} à {f(r['ic95_haut'], 2)})", s, lab)
        suite = s
        lien = regle_lien.est_lien(r["rho_spearman"], r["q_bh"])
        dit_lien = re.search(rf"Pour les [^.]*{lab}[^.]*sont plutôt (moins|mieux) dotés", suite) is not None
        if lien != dit_lien:
            C.fautes.append(f"SM, suicide, {lab} : la règle du site dit {'lien' if lien else 'pas de lien'} "
                            f"(rho {r['rho_spearman']:.2f}, q {r['q_bh']:.3f}), le texte dit l'inverse")


@regle
def sensibilite_idf(V, C):
    t = V.csv("sensibilite_ile_de_france")
    s = phrase(V, "sm", r"passe de .* pour les psychiatres")
    if not s:
        return
    for prof, lab in (("psychiatre", "psychiatres"), ("psychologue", "psychologues")):
        r = t[(t["prof"] == prof) & (t["variable"] == "suicides")].iloc[0]
        if r["n_tous"] > 100:
            C.fautes.append(f"SM, sensibilité à l'Île-de-France : {int(r['n_tous'])} départements, Mayotte comprise")
        C.egal("SM, sensibilité Île-de-France", f"de {f(r['rho_tous'], 2)} à {f(r['rho_sans_ile_de_france'], 2)} "
                                              f"pour les {lab}", s, lab)


@regle
def substitution(V, C):
    """Paires de professions plutôt présentes ensemble, à densité de population égale, au seuil du site."""
    t = V.csv("substitution")
    ens = int(((t["rho_partiel_densite"] >= regle_lien.SEUIL_RHO) & (t["ic95_bas_partiel"] > 0)).sum())
    for cle, nom in (("sm", "SM"), ("s", "Santé")):
        s = phrase(V, cle, r"paires de professions sur \d+ sont plutôt présentes ensemble")
        if s:
            C.egal(f"{nom}, paires de professions", f"{f(ens)} paires de professions sur {f(len(t))}", s, "compte")


@regle
def moran(V, C):
    t = V.csv("moran_residus")
    nets = int(((t["moran_residus"] > .1) & (t["p_permutation"] < .05)).sum())
    for cle, nom in (("sm", "SM"), ("s", "Santé")):
        s = phrase(V, cle, r"restent nettement semblables entre voisins")
        if s:
            C.egal(f"{nom}, Moran", f"pour {f(nets)} professions sur {f(len(t))}", s, "compte")


@regle
def ald_sans_medecin_traitant(V, C):
    """Part des patients en ALD sans médecin traitant, de la plus basse à la plus haute des départements."""
    t = V.csv("contexte_dep_odbl")
    if "ald_sans_medecin_traitant" not in t:
        return
    v = pd.to_numeric(t["ald_sans_medecin_traitant"], errors="coerce").dropna()
    if (t["code"].astype(str).str.lower() == "inconnu").any():
        C.fautes.append("Santé, ALD sans médecin traitant : une ligne « inconnu » dans contexte_dep_odbl.csv")
    s = phrase(V, "s", r"cette part va de .* avec une médiane de")
    if s:
        C.egal("Santé, ALD sans médecin traitant", f"cette part va de {f(v.min(), 1)} % à {f(v.max(), 1)} %, avec une "
                                                   f"médiane de {f(v.median(), 1)} %", s, "étendue et médiane")


@regle
def croisements_entre_bases(V, C):
    """Chaque croisement entre bases : rho écrit et verdict selon la règle du site (croisements.csv)."""
    for fichier in ("croisements", "croisements_odbl"):
        if not (V.dossier / f"{fichier}.csv").exists():
            continue
        t = V.csv(fichier)
        if (pd.to_numeric(t["departements"], errors="coerce") > 100).any():
            C.fautes.append(f"{fichier}.csv : un croisement compte plus de 100 départements, Mayotte comprise")
    texte = V.textes.get("sm", "")
    for m in re.finditer(r"Entre « ([^»]+) » et « ([^»]+) », (le lien est \w+|pas de lien au-delà du seuil retenu) "
                         r"\(rho = (-?\d+,\d+)", texte):
        rho = float(m.group(4).replace(",", "."))
        dit = m.group(3).startswith("le lien")
        if dit and abs(rho) < regle_lien.SEUIL_RHO:
            C.fautes.append(f"SM, croisement « {m.group(1)} » et « {m.group(2)} » : lien dit à rho {m.group(4)}")


# ---------------------------------------------------------------- 2. règles générales
TERRITOIRES_MAX = {"départements": 101, "régions": 18, "intercommunalités": 1259}


def regles_generales(V: Version, C: Compte):
    for cle, nom in (("sm", "SM"), ("s", "Santé")):
        for s in V.prose(cle):
            # lien sous le seuil de la règle du site
            for m in re.finditer(r"\(lien (?:faible|modéré|fort|négligeable), rho = (-?\d+,\d+)\)|le lien est "
                                 r"(?:faible|modéré|fort|négligeable) \(rho = (-?\d+,\d+)\)", s):
                v = float((m.group(1) or m.group(2)).replace(",", "."))
                if abs(v) < regle_lien.SEUIL_RHO:
                    C.fautes.append(f"{nom}, lien sous le seuil du site : « {s[:200]} »")
            # comptes de territoires impossibles
            for m in re.finditer(r"(?<![\d,])(\d{1,3}(?: \d{3})?) (départements|régions|intercommunalités)\b", s):
                n = int(m.group(1).replace(" ", ""))
                if n > TERRITOIRES_MAX[m.group(2)]:
                    C.fautes.append(f"{nom}, {n} {m.group(2)} : « {s[:200]} »")
            # « N sur M » et « N des M » avec N plus grand que M
            for m in re.finditer(r"(?<![\d,])(\d{1,3}(?: \d{3})*) (?:\w+ ){0,3}?(?:sur|des) (\d{1,3}(?: \d{3})*)"
                                 r"(?! ?\d|,\d| ?%)", s):
                a, b = (int(x.replace(" ", "")) for x in m.groups())
                if a > b and b > 1:
                    C.fautes.append(f"{nom}, « {m.group(0)} » ({a} plus grand que {b}) : « {s[:200]} »")
            # part des habitants, des professionnels... au-delà de 100 % (un taux de dépassement peut dépasser 100 %)
            for m in re.finditer(r"(?<![+\-\d,])(\d{3,}(?:,\d+)?) % (?:des|de la|du|d'entre)\b", s):
                if float(m.group(1).replace(",", ".")) > 100:
                    C.fautes.append(f"{nom}, part de {m.group(1)} % : « {s[:200]} »")
            # accords
            for m in re.finditer(r"(?<![\d,])\b1 (départements|régions|intercommunalités|communes)\b", s):
                C.fautes.append(f"{nom}, accord « {m.group(0)} » : « {s[:200]} »")


# ---------------------------------------------------------------- 3. rattachement aux tableaux
def valeurs_tableaux(V: Version) -> set[str]:
    """Écritures possibles de chaque valeur numérique des tableaux publiés : entier, une et deux décimales, et en
    pourcentage pour une proportion."""
    vus: set[str] = set()
    for fic in sorted(V.dossier.glob("*.csv")):
        try:
            t = pd.read_csv(fic, sep=";", decimal=",", nrows=200000, low_memory=False)
        except Exception:  # noqa: BLE001
            continue
        for c in t.columns:
            x = pd.to_numeric(t[c], errors="coerce").dropna()
            if x.empty:
                continue
            x = x.drop_duplicates()
            if len(x) > 50000:
                x = x.sample(50000, random_state=1)
            for v in x.to_numpy(float):
                if not math.isfinite(v):
                    continue
                vus.update({f(v), f(v, 1), f(v, 2), f(abs(v), 1), f(abs(v), 2)})
                if abs(v) <= 1:
                    vus.update({f(100 * abs(v), 1), f(100 * abs(v), 2), f(100 * abs(v))})
    return vus


def rattachement(V: Version) -> tuple[int, list[str]]:
    vus = valeurs_tableaux(V)
    total, absents = 0, []
    for cle, nom in (("sm", "SM"), ("s", "Santé")):
        for s in V.prose(cle):
            if s.startswith("- ") and ("|" in s or "contrôle" in s.lower()):
                continue
            s = re.sub(r"\[[^\]]*\]\([^)]*\)", "", s)            # sources et liens, cités tels quels
            for m in re.finditer(r"(?<![\d,/.\-])(\d{1,3}(?: \d{3})+|\d{3,}|\d+,\d+)(?![\d/])", s):
                n = m.group(1)
                if re.fullmatch(r"(19|20)\d\d", n) or n in ("1 000", "10 000", "100 000"):
                    continue
                total += 1
                if n not in vus and n.lstrip("0") not in vus:
                    absents.append(f"{nom} : {n} dans « {s[:160]} »")
    return total, absents


# ---------------------------------------------------------------- programme
def controler(version: Path, ecrire: bool = True) -> list[str]:
    V = Version(version)
    C = Compte()
    for fn in PHRASES:
        try:
            fn(V, C)
        except Exception as e:  # noqa: BLE001
            C.fautes.append(f"{fn.__name__} : contrôle impossible ({type(e).__name__}: {e})")
    regles_generales(V, C)
    if ecrire:
        total, absents = rattachement(V)
        lignes = [f"# Contrôle des phrases chiffrées, version {version.name}", "",
                  f"{len(PHRASES)} phrases recalculées depuis les tableaux, {len(C.ok)} chiffres concordants, "
                  f"{len(C.fautes)} écarts.", "", "## Écarts", ""] + [f"- {x}" for x in C.fautes or ["aucun"]]
        lignes += ["", "## Chiffres recalculés et retrouvés", ""] + [f"- {x}" for x in C.ok]
        lignes += ["", "## Nombres du texte non retrouvés dans les tableaux publiés (à relire, ne bloque pas)", "",
                   f"{total - len(absents)} nombres sur {total} retrouvés parmi les valeurs des tableaux.", ""]
        lignes += [f"- {x}" for x in absents]
        (version / "controle_phrases.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return C.fautes


def derniere_version() -> Path:
    return sorted(p for p in (RACINE / "resultats").iterdir() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))[-1]


if __name__ == "__main__":
    v = Path(sys.argv[1]) if len(sys.argv) > 1 else derniere_version()
    fautes = controler(v)
    print(f"Contrôle des phrases chiffrées ({v.name}), {len(fautes)} écart(s), détail dans {v / 'controle_phrases.md'}")
    for x in fautes:
        print("  ", x)
    sys.exit(20 if fautes else 0)
