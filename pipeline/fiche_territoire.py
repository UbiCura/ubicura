"""Fiche d'un territoire en tableau de bord (présentation du 30 octobre 2026, maquette b-territoire validée).

Une page par région, département et intercommunalité, à adresse propre (territoire/<niveau>/<code>.html), imprimable.
Toutes les valeurs, leur repère, leur position, leur couleur et leur statut viennent de la règle d'affichage unique
(pipeline/affichage.py), la même pour le comparateur, Croiser et les fiches des indicateurs : aucun calcul ici. Un
indicateur publié seulement par département se lit, pour une intercommunalité, sur son département comparé aux
départements, avec le statut « donnée du département ».

En tête, la santé mentale puis l'offre de soins en santé ; autour, les sept domaines du modèle (pipeline/domaines.py),
chacun avec une phrase qui compte les indicateurs nettement écartés du repère (moins de 0,8 fois ou plus de 1,25 fois,
le seuil des couleurs et des cartes), sans score ni classement, cinq indicateurs phares et les autres à un clic. Les domaines sans base intégrée annoncent les bases décidées, sans aucune valeur.
"""
import csv
import json
from pathlib import Path

from . import affichage as AF, config, domaines as D, libelles as L
from .affichage import FINE, decimales, nombre, par_habitants

NIVEAUX = ("reg", "dep", "epci")
NOM_NIVEAU = {"reg": "Région", "dep": "Département", "epci": "Intercommunalité"}
NIV_PLURIEL = {"reg": "régions", "dep": "départements", "epci": "intercommunalités"}

# toutes les professions de la fiche, la santé mentale d'abord, puis la santé, jamais additionnées (prototype de
# l'étape 2, demande du porteur du 30 octobre 2026 : rares, absentes et petits effectifs compris)
PROFS_SM = [("psychiatre", "Psychiatres"), ("pedopsychiatre", "Pédopsychiatres"),
            ("q_psychiatrie_enfant", "Psychiatres qualifiés pour l'enfant"), ("psychologue", "Psychologues"),
            ("psychotherapeute", "Psychothérapeutes"), ("q_addictologie", "Médecins qualifiés en addictologie")]
PROFS_SANTE = [("medecin_generaliste", "Médecins généralistes"), ("infirmier", "Infirmiers"),
               ("masseur_kinesitherapeute", "Masseurs-kinésithérapeutes"), ("chirurgien_dentiste", "Chirurgiens-dentistes"),
               ("pediatre", "Pédiatres"), ("sage_femme", "Sages-femmes"), ("orthophoniste", "Orthophonistes"),
               ("psychomotricien", "Psychomotriciens"), ("pharmacien", "Pharmaciens"),
               # comptés par le répertoire et suivis par la DREES depuis 2016 : leur ligne du répertoire porte l'évolution
               # (audit du 6 novembre 2026, la fiche les disait « suivis seulement par la DREES »)
               ("gynecologue", "Gynécologues"), ("ophtalmologue", "Ophtalmologues")]
AVEC_LIBERAUX = {"psychologue", "psychiatre", "medecin_generaliste"}
QUALIFICATIONS = {
    "q_psychiatrie_enfant": "Psychiatres qualifiés pour l'enfant et l'adolescent, comptés à part : non ajoutés aux "
                            "psychiatres ni aux pédopsychiatres.",
    "q_addictologie": "Médecins qualifiés en addictologie, quelle que soit leur spécialité, comptés à part : non ajoutés "
                      "aux médecins ni aux psychiatres.",
}
DIST_SM = [("lieu_cmp_adultes", "CMP pour adultes"), ("lieu_cmp_enfants", "CMP pour enfants"),
           ("lieu_cmp", "CMP, tous publics"), ("lieu_cmpp", "CMPP"), ("lieu_csapa", "CSAPA, addictologie")]
DIST_SANTE = [("lieu_urgences", "Service d'urgences"), ("lieu_msp", "Maison de santé pluriprofessionnelle")]
STRUCT_SM = [("lieu_cmp_adultes", "CMP pour adultes"), ("lieu_cmp_enfants", "CMP pour enfants"),
             ("lieu_cmp", "CMP, tous publics"), ("lieu_cattp", "CATTP"), ("lieu_hdj_psy_adultes", "Hôpitaux de jour pour adultes"),
             ("lieu_hdj_psy_enfants", "Hôpitaux de jour pour enfants"),
             ("lieu_hc_psy_adultes", "Hospitalisation complète en psychiatrie, adultes"), ("lieu_cmpp", "CMPP"), ("lieu_camsp", "CAMSP"),
             ("lieu_csapa", "CSAPA, addictologie"), ("lieu_caarud", "CAARUD, réduction des risques")]
TYPES_ENFANTS = {"lieu_cmp_enfants", "lieu_hdj_psy_enfants", "lieu_cmpp", "lieu_camsp"}
RECOURS_DEP = [("suicides", "Décès par suicide"), ("hospit_gestes_auto_infliges", "Hospitalisations pour geste auto-infligé"),
               ("ald_23", "Affection de longue durée, troubles psychiatriques")]
DEJA_EN_TETE = {"suicides", "hospit_gestes_auto_infliges", "ald_23"} | {"dist_" + t for t, _ in DIST_SM + DIST_SANTE}


def _f(v, d=1):
    return None if v is None else float(v)


class Donnees:
    """Accès aux résultats d'une version, partagé par toutes les fiches."""

    def __init__(self, site_data: dict, dossier: Path):
        self.sd = site_data
        self.dossier = Path(dossier)
        self.niv = site_data["niveaux"]
        self.ctx = {c["id"]: (k, c) for k, c in enumerate(site_data["contexte"])}
        self.pos = {lv: {u["c"]: k for k, u in enumerate(self.niv[lv]["units"])} for lv in NIVEAUX}
        self.noms = {lv: {u["c"]: u["nm"] for u in self.niv[lv]["units"]} for lv in NIVEAUX}
        self.limites = site_data.get("limites", {})
        self.alias = site_data.get("limites_alias") or config.LIMITES_ALIAS
        self.T = AF.Affichage(site_data, dossier)
        self.evol = self._csv("evolution_offre_resume.csv")
        lieux = site_data.get("lieux", {})
        self.types = [t["id"] for t in lieux.get("types", [])]
        self.classes_conf = [c.get("classe") for c in lieux.get("confirmations", [])]
        ch = lieux.get("champs", [])
        self.ip = {c: ch.index(c) for c in ch}
        self.pts = lieux.get("pts", [])
        self.concordance = self._concordance()

    # -- valeurs élémentaires, lues dans la règle d'affichage (pipeline/affichage.py) --------------------------------
    def unite(self, lv, code):
        return self.niv[lv]["units"][self.pos[lv][code]]

    def densite(self, lv, code, prof, mode="all"):
        """Cellule d'une profession (densité dans l'unité de la profession, effectif, repère, position...) ou None."""
        return self.T.cellule(f"prof:{prof}:{mode}", lv, code)

    def contexte(self, lv, code, ind, echelle=None):
        """Cellule d'un indicateur du catalogue, ou None si le territoire n'a ni valeur ni statut."""
        c = self.T.cellule(ind, lv, code, echelle)
        return c if c and (c["v"] is not None or c["statut"]) else None

    def distance(self, lv, code, typ):
        return self.contexte(lv, code, "dist_" + typ)

    def structures(self, lv, code, typ):
        """Nombre de structures inscrites, et leurs classes de confirmation lues point par point."""
        serie = (self.niv[lv].get("lieux") or {}).get(typ)
        n = serie[self.pos[lv][code]] if serie else None
        conf = {"confirmee": 0, "recoupee": 0, "verifier": 0, "objet": 0, "meme_lieu": 0}
        if typ in self.types and lv in self.ip:
            t, il, ic, isg = self.types.index(typ), self.ip[lv], self.ip.get("confirmation"), self.ip.get("signaux")
            for p in self.pts:
                if p[0] == t and p[il] == code:
                    if isg is not None and isinstance(p[isg], int) and p[isg] & 2:
                        conf["meme_lieu"] += 1
                    c = p[ic] if ic is not None else None
                    cl = self.classes_conf[c] if isinstance(c, int) and c < len(self.classes_conf) else None
                    conf[{"confirmee": "confirmee", "recoupee": "recoupee", "a_verifier": "verifier"}.get(cl, "objet")] += 1
        return n, conf

    def limite(self, cle, lv=None, code=None):
        """Texte court d'une limite et, s'il existe, la phrase propre au territoire. La clé se lit aussi par ses alias
        (« caf_aah » sur « caf », « sae_lits_psy » sur « sae »), et la phrase courte de config.LIMITES_COURT passe avant
        celle des résultats, pour qu'une phrase ajoutée serve sans refaire les calculs."""
        k = cle if cle in self.limites else next((v for d, v in self.alias.items() if cle.startswith(d)), None)
        lim = self.limites.get(k) if k else None
        if not lim:
            return None
        terr = lim.get("territoires") or {}
        propre = terr.get(code) or terr.get(f"{lv}:{code}") or (terr.get(f"reg:{code}") if lv == "reg" else None)
        court = (config.LIMITES_COURT.get(k) or lim.get("court") or (lim.get("texte") or "").split(". ")[0].rstrip(".")
                 or lim.get("nom"))
        return {"cle": k, "court": court.rstrip(".") + ".", "territoire": propre}

    def departements_epci(self) -> dict:
        """Intercommunalités qui s'étendent sur plusieurs départements : pour chacune, ses départements et la part de ses
        habitants dans chacun (populations municipales de l'INSEE, accessibilite_communes.csv), du plus peuplé au moins
        peuplé. 89 intercommunalités en octobre 2026 (relecture des fiches B+, défaut M5)."""
        if getattr(self, "_deps_epci", None) is None:
            par, vus = {}, set()
            for l in self._csv("accessibilite_communes.csv"):
                if l["code"] in vus or not l.get("epci") or not l.get("dep"):
                    continue
                vus.add(l["code"])
                try:
                    p = float((l.get("population") or "0").replace(",", "."))
                except ValueError:
                    p = 0.0
                d = par.setdefault(l["epci"], {})
                d[l["dep"]] = d.get(l["dep"], 0.0) + p
            self._deps_epci = {e: sorted(((k, v / sum(d.values())) for k, v in d.items()), key=lambda x: -x[1])
                               for e, d in par.items() if len(d) > 1 and sum(d.values())}
        return self._deps_epci

    def attendu(self, lv, code, prof):
        """Effectif attendu selon le profil de la population (niveaux[lv]["attendu"], densité pour 10 000 habitants)
        et effectif observé, ou None. Une comparaison avec des territoires semblables, jamais un besoin de soins."""
        a = (self.niv[lv].get("attendu") or {}).get(prof)
        d = self.densite(lv, code, prof)
        if not a or d is None or d["n"] is None:
            return None
        v = a[self.pos[lv][code]]
        return None if v is None else (v * self.unite(lv, code)["pop"] / 1e4, d["n"])

    def _csv(self, nom):
        f = self.dossier / nom
        if not f.exists():
            return []
        with f.open(encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh, delimiter=";"))

    def _concordance(self):
        f = self.dossier / "concordance_effectifs_dep.csv"
        sortie = {}
        if f.exists():
            with f.open(encoding="utf-8-sig") as fh:
                for l in csv.DictReader(fh, delimiter=";"):
                    if l.get("mode") == "all" and l.get("rang_spearman"):
                        sortie[l["libelle"]] = float(l["rang_spearman"].replace(",", "."))
        return sortie


def annee_indicateur(ind: dict, site_data: dict):
    """Année d'un indicateur quand une source datée la donne (millésimes de l'INSEE, journal des sources), sinon None."""
    src = ind.get("source", "") or ""
    mil = (site_data.get("meta") or {}).get("millesimes_insee") or {}
    if src.startswith("INSEE, dossier complet"):
        return mil.get("salaire") if ind["id"] == "salaire_moyen" else mil.get("pop")
    if "Statistique annuelle des établissements" in src:
        return annee_source(site_data, "SAE")
    return None


def libelle(ind: dict, site_data: dict) -> str:
    """Libellé, unité et année d'un indicateur, l'année seulement quand une source datée la donne (comme à l'INSEE).
    Le catalogue portera un millésime pour chaque indicateur, d'ici là l'année vient des millésimes de l'INSEE et du
    journal des sources de la version."""
    an = annee_indicateur(ind, site_data)
    return ", ".join(str(x) for x in (ind.get("label"), ind.get("unite"), an) if x)


def annee_source(site_data: dict, mot: str):
    """Année lue dans le détail du journal des sources (« année 2024, ... »), pour la source dont le nom contient mot."""
    import re
    for s in ((site_data.get("meta") or {}).get("journal") or {}).get("sources", []):
        if mot in s.get("source", ""):
            m = re.search(r"année (\d{4})", s.get("detail", ""))
            if m:
                return int(m.group(1))
    return None


def _ligne(libelle, cel, couleur=True, limite=None, sous=False, ident=None, T=None):
    """Ligne d'un tableau de fiche, à partir d'une cellule de la règle d'affichage (ou None, sans donnée). ident,
    l'identifiant de l'indicateur, écrit dans la page (data-ind) pour le contrôle de cohérence entre les pages. T, la
    règle d'affichage, pose la réglette de la ligne (affichage.Affichage.reglette)."""
    if cel is None:
        return {"id": ident, "lib": libelle, "v": None, "e": None, "n": None, "limite": limite, "sous": sous, "couleur": None,
                "offre": couleur, "statut": "", "txt": "", "n_txt": "", "ref_txt": "", "ref_lib": "", "pos_txt": "",
                "e_txt": "", "e_mots": "", "reg": None, "med_txt": "", "kind": None}
    reg = T.reglette(cel["id"], cel["lv"], cel["code"], cel) if T else None
    if reg and not couleur:
        reg["classe"] = reg["classe"] if reg["classe"] in ("sans", "petit") else ""
    return {"id": cel["id"], "lv": cel["lv"], "code": cel["code"], "lib": libelle, "v": cel["v"], "n": cel["n"], "txt": cel["v_txt"], "n_txt": cel["n_txt"],
            "ref": cel["ref"], "ref_txt": cel["ref_txt"], "ref_lib": cel["ref_lib"], "e": cel["e"], "e_txt": cel["e_txt"], "e_mots": cel["e_mots"],
            "pos_txt": cel["pos_txt"], "statut": cel["statut_txt"], "note": cel["note"], "code": cel["statut"],
            "couleur": cel["couleur"] if couleur else None, "offre": couleur, "limite": limite, "sous": sous,
            "reg": reg, "med_txt": cel["med_txt"], "med_lib": cel["med_lib"], "ref_type": cel["ref_type"], "kind": cel["kind"],
            "ancre": "l-" + "".join(ch if ch.isalnum() else "-" for ch in cel["id"].lower()).strip("-"),
            "fac": cel["fac"], "zero": _part_aucun(T, cel) if T else None,
            "pos_pc": cel["pos_txt"].split(" des ")[0] if cel["pos_txt"] else "", "med_mots": cel["med_mots"]}


def _part_aucun(T, cel) -> str | None:
    """« 83 % », part des territoires du niveau sans aucun inscrit, pour écrire « aucun inscrit, comme dans 83 % des
    intercommunalités » plutôt qu'un 0 seul."""
    if cel["statut"] != "aucun":
        return None
    # mêmes territoires et même arrondi que la réglette de la ligne (« aucun : 49 % »), qui ne compte que les territoires
    # dont la valeur est publiée : 54 % ici et 49 % sur la réglette se contredisaient (audit du 6 novembre 2026)
    S = T.serie(cel["id"], cel["lv"])
    vals = [v for v in (S.v if S else []) if v is not None]
    return f"{nombre(100 * sum(1 for v in vals if v == 0) / len(vals), 'entier')}{FINE}%" if vals else None


def avec_article(nom: str) -> str:
    """« la communauté de communes Vierzon-Sologne-Berry » pour « CC Vierzon-Sologne-Berry » (audit de contrôle du
    30 octobre 2026, point F16)."""
    for sigle, long in (("CC ", "la communauté de communes "), ("CA ", "la communauté d'agglomération "),
                        ("CU ", "la communauté urbaine "), ("Métropole ", "la métropole "), ("Métropole d'", "la métropole d'"),
                        ("Communauté de communes ", "la communauté de communes "),
                        ("Communauté d'agglomération ", "la communauté d'agglomération "), ("Eurométropole ", "l'eurométropole ")):
        if nom.startswith(sigle):
            reste = nom[len(sigle):]
            # « CA GrandSoissons Agglomération » : le nom porte déjà sa nature, « la communauté d'agglomération
            # GrandSoissons Agglomération » la dirait deux fois (relecture de clarté du 31 octobre 2026)
            nature = long.split()[-1].split("'")[-1]
            if nature and nature in reste.lower():
                return "l'intercommunalité " + reste
            return long + reste
    return nom


_LIAISON: dict = {}


def de_nom(lv: str, code: str, nom: str) -> str:
    """« de l'Aveyron », « des Yvelines », « du Gard » : la préposition et l'article du nom d'un département ou d'une
    région, d'après le type de liaison de l'INSEE (typeLiaison du référentiel, audit du 6 novembre 2026, « Fiche de
    Aveyron »). Une intercommunalité garde « de » suivi de son nom."""
    if lv in ("dep", "reg") and not _LIAISON:
        for niv, f in (("dep", "ref_departements.json"), ("reg", "ref_regions.json")):
            chemin = config.BRUT / f
            if chemin.exists():
                _LIAISON.update({(niv, r["code"]): r.get("typeLiaison") for r in json.loads(chemin.read_text(encoding="utf-8"))})
    t = _LIAISON.get((lv, code))
    if lv not in ("dep", "reg") or t is None:
        # intercommunalité : « de la communauté de communes … », « d’Orléans Métropole », « de l’Île-d’Yeu »
        # (contre-audit du 6 novembre 2026)
        n = avec_article(nom) if lv == "epci" else nom
        for art, de_art in (("Le ", "du "), ("Les ", "des "), ("La ", "de la "), ("L'", "de l’"), ("L’", "de l’")):
            if n.startswith(art):
                return de_art + n[len(art):]
        return ("d’" if n[:1].lower() in "aeiouyhâàéèêëîïôûùœ" else "de ") + n
    if nom.startswith(("La ", "Le ", "Les ", "L'", "L’")):
        return "de " + nom
    return {0: "de ", 1: "d’", 2: "du ", 3: "de la ", 4: "des ", 5: "de l’", 6: "des "}.get(t, "de ") + nom


def fiche(dn: Donnees, lv: str, code: str, version: str) -> dict:
    """Valeurs de la fiche d'un territoire, prêtes pour le gabarit fiche_territoire.html."""
    u = dn.unite(lv, code)
    dep = u.get("p") if lv == "epci" else (code if lv == "dep" else None)
    parent_nom = None
    if lv == "epci" and dep in dn.pos["dep"]:
        parent_nom = dn.noms["dep"][dep]
    elif lv == "dep":
        parent_nom = u.get("p")
    f = {"niveau": lv, "code": code, "nom": u["nm"], "nom_niveau": NOM_NIVEAU[lv], "parent": parent_nom,
         "population": u["pop"], "niv_pluriel": NIV_PLURIEL[lv], "nom_article": avec_article(u["nm"]) if lv == "epci" else u["nm"], "de_nom": de_nom(lv, code, u["nm"]), "nb_territoires": len(dn.niv[lv]["units"]), "version": version}
    # une intercommunalité sur plusieurs départements les nomme tous, avec la part de ses habitants dans chacun ; les
    # chiffres publiés au département sont ceux de son département de rattachement (défaut M5)
    f["deps"], f["parents_txt"] = [], parent_nom
    if lv == "epci" and code in dn.departements_epci():
        f["deps"] = [{"code": d, "nom": dn.noms["dep"].get(d, d), "part": nombre(100 * x, "entier") + FINE + "%",
                      "rattachement": d == dep} for d, x in dn.departements_epci()[code]]
        noms = [x["nom"] for x in f["deps"]]
        f["parents_txt"] = ", ".join(noms[:-1]) + " et " + noms[-1]

    def profs(liste):
        lignes = []
        for p, lib in liste:
            lim = dn.limite("prof:" + p, lv, code)
            if p in QUALIFICATIONS:
                # une phrase propre à chaque qualification : sous le même texte, la seconde ne gardait que son « ! »
                # (une limite déjà écrite dans le tableau n'est pas répétée), relecture de clarté du 31 octobre 2026
                lim = {"cle": "qualification", "court": QUALIFICATIONS[p], "territoire": None}
            # profession rare, pour 100 000 habitants (affichage.par_habitants, F17)
            fac = par_habitants(dn.sd, p)
            lb = lib
            lignes.append(_ligne(lb, dn.densite(lv, code, p), limite=lim, ident=f"prof:{p}:all", T=dn.T))
            if p in AVEC_LIBERAUX:
                lignes.append(_ligne("dont libéraux", dn.densite(lv, code, p, "lib"), sous=True, ident=f"prof:{p}:lib", T=dn.T))
        return lignes

    def dists(liste):
        out = []
        for t, lib in liste:
            dv = dn.distance(lv, code, t)
            lim = dn.limite("manque_sae", lv, code) if t in ("lieu_cmp_adultes", "lieu_cmp_enfants") else None
            sans = dv is None or dv["v"] is None
            out.append(_ligne(lib, dv, couleur=False, limite=lim if sans and lim and lim.get("territoire") else None,
                              ident="dist_" + t, T=dn.T))
        return out

    f["sm_pro"] = profs(PROFS_SM)
    f["sm_dist"] = dists(DIST_SM)
    f["sante_pro"] = profs(PROFS_SANTE)
    f["sante_dist"] = dists(DIST_SANTE)
    # recours, lus au département pour une intercommunalité
    lv_r, code_r = ("dep", dep) if lv == "epci" else (lv, code)
    f["recours_niveau"] = None
    if code_r in dn.pos.get(lv_r, {}):
        f["recours_niveau"] = (dn.noms[lv_r][code_r], NIV_PLURIEL[lv_r])
        f["sm_recours"] = [_ligne(lib, dn.contexte(lv_r, code_r, i, "dep" if lv == "epci" else None), couleur=False,
                                  limite=_limite_recours(dn, i, lv_r, code_r), ident=i, T=dn.T) for i, lib in RECOURS_DEP]
    else:
        f["sm_recours"] = []
    # structures de soins psychiques
    sts, tot, confirmees = [], 0, 0
    for t, lib in STRUCT_SM:
        n, conf = dn.structures(lv, code, t)
        taux = dn.contexte(lv, code, "lieux_" + t)
        sans = taux is None or taux["v"] is None
        unite = (dn.ctx.get("lieux_" + t, (None, {}))[1].get("unite") or "").replace(" hab.", " habitants")
        st = {"id": "lieux_" + t, "lib": lib, "n": n, "conf": conf, "taux": taux, "enfants": t in TYPES_ENFANTS, "unite": unite,
              "limite": dn.limite("manque_sae", lv, code) if t in ("lieu_cmp_adultes", "lieu_cmp_enfants") and sans and n else None}
        # ligne type du tableau des structures : taux pour le public, nombre et confirmation en clair, réglette
        st["ligne"] = _ligne(lib, taux, ident="lieux_" + t, T=dn.T, limite=st["limite"])
        if not st["ligne"]["txt"] and not st["ligne"]["statut"] and n:
            st["ligne"]["statut"] = AF.STATUTS["non_publie"]
            st["raison"] = "public mixte, adultes et enfants" if t == "lieu_cmp" else ""
        dist = dn.distance(lv, code, t)
        st["dist"] = dist["v_txt"] if dist and dist["v"] is not None else ""
        m = conf.get("meme_lieu", 0)
        if t == "lieu_cattp" and m:
            st["ligne"]["precision"] = (f"{m} au même lieu qu'un CMP, compté{'s' if m > 1 else ''} à part comme "
                                        f"lieu{'x' if m > 1 else ''} d'activité déclaré{'s' if m > 1 else ''}")
        sts.append(st)
        tot += n or 0
        confirmees += conf["confirmee"]
    f["structures"], f["structures_total"], f["structures_confirmees"] = sts, tot, confirmees
    # réserves des structures, sous leur tableau (inventaire des limites du 31 octobre 2026, A1, A2, A3, D7, D12) :
    # chaque phrase reprend le texte des limites « lieux » et « confirmation » (config.LIMITES)
    f["reserves_structures"] = [x for x in (
        (dn.limite("lieux") or {}).get("court"),
        "Une structure n'est pas une capacité : une antenne peut n'ouvrir que quelques demi-journées. Les structures ne "
        "s'ajoutent pas aux professionnels.",
        "Quand un CMP annonce un CATTP dans son nom et que son gestionnaire n'en a pas d'autre dans la commune, un CATTP "
        "est compté au même lieu, à part.",
        "« Recoupée » : la statistique annuelle des établissements (SAE) confirme le nombre de structures de l'hôpital, "
        "pas leur adresse.",
        (dn.limite("confirmation") or {}).get("court"),
        "Les structures pour enfants sont rapportées aux moins de 15 ans, le recensement ne publiant pas les moins de "
        "18 ans.") if x]
    # quatre chiffres clés en tête, l'effectif écrit en clair (audit de contrôle du 30 octobre 2026, point I8)
    # Chaque chiffre clé porte côte à côte l'écart à l'ensemble et la position, reliés par « mais » quand ils vont en
    # sens contraire (« 17 % sous l'ensemble, mais plus haut que 71 % des intercommunalités ») : seule, la position
    # se lisait à contresens (relecture de clarté du 31 octobre 2026, défaut 1)
    cles = []
    for p, un, plus in (("psychologue", "psychologue", "psychologues"), ("psychiatre", "psychiatre", "psychiatres")):
        d = dn.densite(lv, code, p)
        if d and d["v"] is not None:
            ecart = d["e_mots"] if d["statut"] not in ("aucun", "petit") else ""
            # « mais » sur l'écart écrit, ou, sans écart (petit effectif), sur la valeur et l'ensemble affichés
            sens = AF.contraire(d["e"], bool(ecart), d["v_txt"], d["ref_txt"], d["pos_txt"])
            lien = ", mais " if sens else ", "
            # sans écart écrit, le « mais » s'appuie sur le sens de la valeur, dit en mots (audit du 6 novembre 2026)
            sans_ecart = AF.avant_position("", False, bool(sens), d["ref_txt"], "prof", d["v_txt"]) if sens else ""
            rep = (f"{ecart} ({d['ref_lib'].lower()} : {d['ref_txt']}){lien}{d['pos_txt']}" if ecart
                   else f"{sans_ecart.split(' (')[0].replace('ensemble', d['ref_lib'].lower())} ({d['ref_txt']}){lien}{d['pos_txt']}"
                   if sans_ecart.endswith(")") else f"{d['ref_lib'].lower()} : {d['ref_txt']}{lien}{d['pos_txt']}")
            if d["statut"] == "aucun" or not d["n"]:
                # jamais un 0 seul en tête de fiche (relecture du 31 octobre 2026, 509 fiches) : « aucun psychiatre
                # inscrit », avec le repère, sans densité nulle ni position
                cles.append({"n": "aucun", "texte": f"{un} inscrit au répertoire",
                             "rep": f"{d['ref_lib'].lower()} : {d['ref_txt']} {AF.txt_unite(d['fac'])}",
                             "ecart": "", "position": "", "contraire": False, "couleur": None})
                continue
            cles.append({"n": nombre(d["n"], "entier"),
                         "texte": f"{un if d['n'] == 1 else plus}, soit {d['v_txt']} {AF.txt_unite(d['fac'])}",
                         "rep": rep, "ecart": ecart, "position": d["pos_txt"], "contraire": bool(sens), "sens": sens,
                         "couleur": d["couleur"]})
    dd = dn.distance(lv, code, "lieu_cmp_adultes")
    if dd and dd["v"] is not None:
        sens_d = AF.contraire(None, False, dd["v_txt"], dd["ref_txt"], dd["pos_txt"])
        lien_d = ", mais " if sens_d else ", "
        # une médiane qui s'arrondit à 0 : jamais « 0 km » seul (relecture v2, Nord Basse-Terre et Montluçon)
        nul = AF.distance_nulle(dd["v_txt"])
        cles.append({"n": "sur place" if nul else f"{dd['v_txt']} km", "mot": nul,
                     "texte": "un CMP pour adultes dans la commune d'au moins la moitié des habitants" if nul
                     else "la moitié des habitants vit plus près d'un CMP pour adultes",
                     "rep": (f"{AF.avant_position('', False, True, dd['ref_txt'], 'dist', dd['v_txt']).split(' (')[0].replace('ensemble', dd['ref_lib'].lower())} "
                             f"({dd['ref_txt']} km){lien_d}{dd['pos_txt']}" if sens_d
                             else f"{dd['ref_lib'].lower()} : {dd['ref_txt']} km{lien_d}{dd['pos_txt']}"), "position": dd["pos_txt"],
                     "sens": sens_d})
    if tot:
        # « 6 des 10 structures sont confirmées » : écrit « 6 … sur 10 », le chiffre se lisait comme une proportion
        if tot == 1:
            n_c, t_c = 1, "structure de soins psychiques, " + ("confirmée" if confirmees else "pas encore confirmée")
        elif confirmees:
            n_c, t_c = confirmees, f"des {tot} structures de soins psychiques {'sont confirmées' if confirmees > 1 else 'est confirmée'}"
        else:
            n_c, t_c = "aucune", f"des {tot} structures de soins psychiques n'est encore confirmée"
        cles.append({"n": n_c, "texte": t_c, "rep": "par la liste de l'établissement ou une source indépendante"})
    # la même tournure dans le bloc Confiance : « 6 des 10 structures … sont confirmées »
    f["confiance_structures"] = "" if not tot else (
        f"{n_c[:1].upper() + n_c[1:] if isinstance(n_c, str) else n_c} {t_c}" if tot > 1
        else "La structure de soins psychiques " + ("est confirmée" if confirmees else "n'est pas encore confirmée"))
    f["cles"] = cles
    f["concordance"] = {"psychologues": dn.concordance.get("Psychologues"),
                        "psychiatres": next((v for k, v in dn.concordance.items() if k.startswith("Psychiatres")), None)}
    # limites propres au territoire, écrites en tête de fiche (Mayotte partout, structures incomplètes outre-mer)
    f["limites_territoire"] = []
    mayotte = code == "976" or (lv == "epci" and dep == "976") or (lv == "reg" and code == "06")
    if mayotte and dn.limites.get("mayotte"):
        f["limites_territoire"].append(dn.limite("mayotte")["court"])
    lieux = dn.limite("lieux", lv, code) or {}
    if not lieux.get("territoire") and lv == "epci" and dep:
        lieux = dn.limite("lieux", "dep", dep) or {}
    if lieux.get("territoire"):
        f["limites_territoire"].append(lieux["territoire"])
    f["phrases"] = phrases_tableaux(f, lv)
    # la clé en mots sous un tableau, le même texte que dans les constats (affichage.CLE_CONTRAIRE)
    f["contraire"] = {k: AF.cle_contraire(ecart_contraire(lignes), lv) for k, lignes in
                      (("sm_pro", f["sm_pro"]), ("sante_pro", f["sante_pro"]),
                       ("structures", [s["ligne"] for s in f["structures"]]))}
    # la même clé, toujours écrite dans « Lire une réglette » et en tête des constats : l'ensemble tiré par les
    # territoires peuplés se comprend avant de lire le premier chiffre (relecture de clarté du 31 octobre 2026)
    f["cle_ensemble"] = AF.cle_contraire("haut", lv)
    # sous les tuiles, la clé du « mais » qu'elles montrent (une distance plus loin que l'ensemble et pourtant plus près
    # que la plupart, Ardennes, Chinon), la clé générale sinon (relecture v2 des fiches construites, mineur 4)
    sens_t = list(dict.fromkeys(t["sens"] for t in f["cles"] if t.get("sens")))
    f["cle_tuiles"] = AF.cle_contraire_plusieurs(sens_t, lv) if sens_t else f["cle_ensemble"]
    f["source_recours"] = _source_recours(dn)
    f["autour"] = _domaines(dn, lv, code, dep)
    f["sae"] = _sae(dn, lv, code, dep)
    f["evolution"] = _evolution(dn, lv, code, dep)
    f["exercice"] = _exercice(dn, lv, code, dep)
    f["parcours"] = _parcours(dn)
    f["secteurs_psy"] = _secteurs_psy(dn, lv, code, dep)
    f["sm_autres"] = _sante_mentale_autres(dn, lv, code, dep)
    f["sm_autres_n"] = sum(len(x["rows"]) for x in f["sm_autres"])
    return f


def _ecartes(lignes: list) -> tuple[list, list]:
    """Noms des lignes dont l'écart est coloré par la règle d'affichage, au-dessus puis en dessous de l'ensemble."""
    haut, bas, parent = [], [], ""
    for l in lignes:
        nom = l["lib"].split(",")[0].lower()
        if l.get("sous"):
            nom = f"{parent} libéraux"   # « dont libéraux » sous les psychologues : « psychologues libéraux »
        else:
            parent = nom
        (haut if l.get("couleur") == "haut" else bas if l.get("couleur") == "bas" else []).append(nom)
    return haut, bas


def _liste(mots: list) -> str:
    return mots[0] if len(mots) == 1 else ", ".join(mots[:-1]) + " et " + mots[-1]


def ecart_contraire(lignes: list) -> str | None:
    """« haut » quand une ligne du tableau est sous l'ensemble et pourtant plus haute que la plupart des territoires
    (l'ensemble, pesé par les habitants, est tiré vers le haut par les territoires peuplés), « bas » dans l'autre sens,
    None sinon : la clé en mots sous le tableau ne paraît que dans ces cas (31 octobre 2026)."""
    for l in lignes:
        if l.get("code") == "aucun" or not l.get("pos_txt"):
            continue
        ecrit = l.get("kind") in ("prof", "lieux") and bool(l.get("e_mots")) and l.get("code") != "petit"
        sens = AF.contraire(l.get("e"), ecrit, l.get("txt"), l.get("ref_txt"), l["pos_txt"])
        if sens:
            return sens
    return None


def phrase_professions(noms: list, sens: str, ens: str) -> str:
    """« Les psychologues sont nettement en dessous de l'ensemble des départements. » ; au-delà de deux lignes, la liste
    sans nombre ni article répété : « Nettement en dessous de l'ensemble des départements : médecins généralistes, … et
    pédiatres. » Sans nombre, parce qu'une ligne « libéraux » n'est pas une profession de plus (décision du 31 octobre
    2026, voie A : la phrase-liste reste à gauche, phrase_liste)."""
    if len(noms) <= 2:
        return f"{_liste(['les ' + n for n in noms])} sont nettement {sens} {ens}."
    return f"nettement {sens} {ens} : {_liste(noms)}."


def phrase_liste(haut: list, bas: list) -> bool:
    """Une phrase de tête qui énumère plus de deux lignes du tableau se lit comme une liste et reste à gauche : la
    direction visuelle ne justifie jamais une liste (lignes lâches de « masseurs-kinésithérapeutes, chirurgiens-dentistes,
    … », 31 octobre 2026)."""
    return len(haut) + len(bas) > 2


def phrases_tableaux(f: dict, lv: str) -> dict:
    """Phrase de lecture en tête de chaque tableau de la fiche, descriptive, sans cause ni classement : ce qui s'écarte
    nettement de l'ensemble (règle des couleurs), sinon que rien ne s'en écarte."""
    niv = NIV_PLURIEL[lv]
    out = {}
    for cle, quoi in (("sm_pro", "professions de la santé mentale"), ("sante_pro", "professions de santé")):
        haut, bas = _ecartes([l for l in f[cle] if l.get("txt")])
        lignes = [l for l in f[cle] if not l.get("sous") and l.get("txt")]
        if not haut and not bas:
            out[cle] = (f"Aucune des {len(lignes)} {quoi} ne s'écarte nettement de l'ensemble des {niv}, compte tenu "
                        f"du hasard.") if lignes else ""
        else:
            # chaque ligne nomme une profession au pluriel : « les psychologues libéraux », en phrases séparées
            # (remarque du 31 octobre 2026)
            m, ens = [], f"de l'ensemble des {niv}"
            for noms, sens in ((bas, "en dessous"), (haut, "au-dessus")):
                if noms:
                    m.append(phrase_professions(noms, sens, ens))
                    ens = "de l'ensemble"
            reste = [l for l in lignes if l["lib"].split(",")[0].lower() not in haut + bas]
            if reste:
                qui = "les autres professions" if len(reste) > 1 else "l'autre profession"
                m.append(f"Pour {qui}, l'écart à l'ensemble reste dans la marge de 0,8 à 1,25 fois ou dans ce que le "
                         f"hasard explique.")
            out[cle] = " ".join(p[:1].upper() + p[1:] for p in m)
            if phrase_liste(haut, bas):
                out[cle + "_liste"] = True
    tot, conf = f.get("structures_total") or 0, f.get("structures_confirmees") or 0
    types = sum(1 for s in f.get("structures", []) if s.get("n"))
    out["structures"] = (f"{tot} structure{'s' if tot > 1 else ''} de soins psychiques {'sont inscrites' if tot > 1 else 'est inscrite'}, "
                         f"de {types} type{'s' if types > 1 else ''}, dont {conf} confirmée{'s' if conf > 1 else ''}."
                         if tot else "Aucune structure de soins psychiques n'est inscrite dans le territoire ; la distance à la plus proche est donnée plus bas.")
    for cle in ("sm_dist", "sante_dist"):
        l = next((x for x in f[cle] if x.get("txt")), None)
        if not l:
            out[cle] = ""
            continue
        nom = l['lib'][0].lower() + l['lib'][1:] if not l['lib'].startswith('CMP') else l['lib']
        out[cle] = (f"Un {nom} se trouve {AF.DANS_COMMUNE}, face à {l['ref_txt']} km pour l'ensemble des {niv}."
                    if AF.distance_nulle(l["txt"]) else
                    f"La moitié des habitants vit à moins de {l['txt']} km d'un {nom}, face à {l['ref_txt']} km pour l'ensemble des {niv}.")
    if f.get("sm_recours"):
        n = f.get("recours_niveau") or ("", "départements")
        if not any(l.get("txt") for l in f["sm_recours"]):
            out["recours"] = (f"Ces taux ne sont pas publiés pour les {n[1]} ; ils se lisent sur la fiche de chaque "
                              f"département.")
        else:
            out["recours"] = (f"Ces taux ne sont publiés que par département : ils sont ceux de son département, situé parmi les {n[1]}."
                              if lv == "epci" else f"Ces taux sont situés parmi les {n[1]}, à âge égal.")
    return out


def _valeur_fine(dn, lv, code, dep, ind_id):
    """Valeur au niveau du territoire, ou à son département pour une intercommunalité."""
    r = dn.contexte(lv, code, ind_id)
    if r is None and lv == "epci" and dep in dn.pos["dep"]:
        return dn.contexte("dep", dep, ind_id, "dep"), "dep"
    return r, None


def _sante_mentale_autres(dn, lv, code, dep):
    """Les autres indicateurs de santé mentale, de tous les domaines, rangés par domaine, sous la bande du haut."""
    par = {}
    for ind_id, (_, ind) in dn.ctx.items():
        if ind_id in DEJA_EN_TETE or ind_id.startswith(("lieux_", "sae_")) or not D.sante_mentale(ind):
            continue
        r, echelle = _valeur_fine(dn, lv, code, dep, ind_id)
        if r is None:
            continue
        ligne = _ligne(libelle(ind, dn.sd), r, couleur=False,
                       limite=dn.limite(ind_id, lv, code), ident=ind_id, T=dn.T)
        ligne["id"], ligne["echelle"], ligne["defn"] = ind_id, echelle, ind.get("explication")
        par.setdefault(D.classer(ind)[0], []).append(ligne)
    return [{"nom": d["nom"], "rows": par[d["id"]]} for d in D.DOMAINES if d["id"] in par]


def _domaines(dn: Donnees, lv, code, dep):
    """Sept domaines repliés : indicateurs hors santé mentale de chaque domaine, au niveau le plus fin publié."""
    lignes = {}
    for ind_id, (_, ind) in dn.ctx.items():
        if ind_id in DEJA_EN_TETE:
            continue
        dom, sous = D.classer(ind)
        if dom == "offre" or D.sante_mentale(ind):
            continue
        r, echelle = _valeur_fine(dn, lv, code, dep, ind_id)
        if r is None:
            continue
        ligne = _ligne(libelle(ind, dn.sd), r, couleur=False, limite=dn.limite(ind_id, lv, code), ident=ind_id, T=dn.T)
        ligne["id"], ligne["echelle"], ligne["defn"] = ind_id, echelle, ind.get("explication")
        lignes.setdefault(dom, []).append(ligne)
    sortie = []
    for d in D.DOMAINES:
        if d.get("centre"):
            continue
        rows = lignes.get(d["id"], [])
        phares = [r for i in d.get("phares", []) for r in rows if r["id"] == i]
        autres = [r for r in rows if r not in phares]
        haut = sum(1 for r in rows if r["e"] is not None and r["e"] + 1 > AF.PROCHE[1])
        bas = sum(1 for r in rows if r["e"] is not None and r["e"] + 1 < AF.PROCHE[0])
        sortie.append({"id": d["id"], "nom": d["nom"], "rows": rows, "phares": phares or rows[:5],
                       "autres": autres if phares else rows[5:], "synthese": synthese(len(rows), haut, bas),
                       "haut": haut, "bas": bas,
                       "croiser": d.get("croiser"), "lire": _lire_domaine(d, rows)})
    return sortie


def _lire_domaine(d, rows) -> str:
    """« Comment lire » d'un domaine du contexte (rapports territoriaux, repris le 31 octobre 2026) : ce que le domaine
    éclaire, puis ce que disent les allocations et la protection de l'enfance quand le domaine les montre."""
    ids = {r["id"] for r in rows}
    p = [d["pourquoi"], "Ces indicateurs décrivent les habitants et leurs conditions de vie, ils ne mesurent pas un "
                        "besoin de soins.", "Le comptage en tête du domaine suit la seule marge de 0,8 à 1,25 fois le "
                        "repère, sans test du hasard, et aucune couleur ne marque ces écarts."]
    if any(i.startswith("caf_") for i in ids):
        p.append("L'AAH, l'AEEH et le RSA signalent un handicap reconnu ou une situation de pauvreté.")
    if any("enfance" in i or i.startswith(("ase_", "aide_sociale")) for i in ids):
        p.append("Les chiffres de la protection de l'enfance décrivent l'activité du département, pas un besoin de soins.")
    return " ".join(p)


def _reunir(sources: list) -> str:
    """« Santé publique France, portail Odissé, d'après le CépiDc et d'après le PMSI-MCO » : le début commun de deux
    sources n'est écrit qu'une fois (coupé à la dernière virgule commune)."""
    if len(sources) < 2:
        return sources[0] if sources else ""
    import os
    pref = os.path.commonprefix(sources)
    pref = pref[:pref.rfind(", ") + 2] if ", " in pref else ""
    return pref + " et ".join(x[len(pref):] for x in sources)


def _source_recours(dn) -> str:
    """Sources du tableau des recours, chacune avec la licence que lui donne le catalogue, la même que sur la carte
    du constat : le tableau disait « Licence Ouverte 2.0 » pour les ALD, que le catalogue donne sous Licence Ouverte
    1.0 (relecture de clarté du 31 octobre 2026, défaut 5). La rediffusion des données de l'Assurance Maladie par le
    site, sous ODbL, est dite à part."""
    par_licence: dict = {}
    for i, _ in RECOURS_DEP:
        ind = (dn.ctx.get(i) or (None, {}))[1]
        if ind.get("source"):
            par_licence.setdefault(ind.get("licence") or "licence non précisée", []).append(ind["source"])
    morceaux = [f"{_reunir(list(dict.fromkeys(s)))}, {lic}" for lic, s in par_licence.items()]
    texte = "Sources : " + " ; ".join(morceaux) + "."
    if any("Assurance Maladie" in s for v in par_licence.values() for s in v):
        texte += " Le site rediffuse les données de l'Assurance Maladie sous ODbL, dans les fichiers suffixés _odbl."
    return texte


def _limite_recours(dn, i, lv, code):
    """Limite d'un indicateur de recours ; pour les ALD, la phrase courte et le champ du texte (régime général,
    reconnaissance à la demande du médecin)."""
    lim = dn.limite(i, lv, code)
    if lim and lim.get("cle") == "ald":
        lim = dict(lim, court=lim["court"] + " Elles sont reconnues à la demande du médecin et ne couvrent que le "
                                             "régime général.")
    return lim


def _niveau_dep(lv, code, dep):
    """Niveau et code où se lisent les données publiées par département : le département lui-même, celui d'une
    intercommunalité, ou la région."""
    return ("dep", dep) if lv == "epci" else (lv, code)


def _sae(dn, lv, code, dep):
    """Psychiatrie à l'hôpital (SAE), au département pour une intercommunalité, en lignes types avec la limite."""
    lv_d, code_d = _niveau_dep(lv, code, dep)
    rows = []
    for ind_id, (_, ind) in dn.ctx.items():
        if not ind_id.startswith("sae_"):
            continue
        r = dn.contexte(lv_d, code_d, ind_id, "dep" if lv == "epci" else None)
        if r is None:
            continue
        l = _ligne(libelle(ind, dn.sd), r, couleur=False, limite=dn.limite(ind_id, lv_d, code_d), ident=ind_id, T=dn.T)
        l["id"], l["defn"], l["bloc_dep"] = ind_id, ind.get("explication"), lv == "epci"   # le titre le dit déjà
        rows.append(l)
    return rows


def _signe(v):
    """Évolution en pour cent signé, écrite comme dans les rapports territoriaux (rapport_bases._signe), pour qu'un
    même chiffre soit identique sur les deux pages."""
    from .rapport_bases import _signe as signe
    return signe(v).replace("-", "−")


def _evolution(dn, lv, code, dep):
    """Évolution des densités depuis 2016 (séries de la DREES, evolution_offre_resume.csv), au département pour une
    intercommunalité, avec sa région et la France, comme dans les rapports territoriaux."""
    from .rapport_bases import EVOLUTION_FAMILLE
    SM, SANTE = config.SANTE_MENTALE, config.SANTE
    lv_d, code_d = _niveau_dep(lv, code, dep)
    reg = None
    if lv_d == "dep" and code_d in dn.pos["dep"]:
        nom_reg = dn.unite("dep", code_d).get("p")
        reg = next((u["c"] for u in dn.niv["reg"]["units"] if u["nm"] == nom_reg), None)
    idx = {(r["niveau"], r["code"], r["prof"]): r for r in dn.evol}
    out = {}
    for fam, cle in ((SM, "sm"), (SANTE, "sante")):
        lignes = []
        for p in EVOLUTION_FAMILLE[fam]:
            x, fr = idx.get((lv_d, code_d, p)), idx.get(("FR", "FR", p))
            if not x or not x.get("evolution_densite") or not fr:
                continue
            v = lambda r, c: float(r[c].replace(",", "."))   # noqa: E731
            rg = idx.get(("reg", reg, p)) if reg else None
            # densités de la DREES (pour 10 000) dans l'unité de la ligne de la profession, pour 100 000 pour une
            # profession rare comme les ophtalmologues (audit du 6 novembre 2026)
            k = par_habitants(dn.T.sd, p) / 1e4 if p in dn.T.profs else 1
            lignes.append({"lib": x["libelle"], "periode": f"{x['annee_debut']} à {x['annee_fin']}",
                           # arrondis de la règle unique (affichage.nombre), « de 3,7 à 3,9 » et non « de 3,73 à 3,92 »
                           "debut": nombre(v(x, "densite_debut") * k, "taux"), "fin": nombre(v(x, "densite_fin") * k, "taux"),
                           "ici": _signe(v(x, "evolution_densite")),
                           "region": _signe(v(rg, "evolution_densite")) if rg and rg.get("evolution_densite") else "",
                           "france": _signe(v(fr, "evolution_densite"))})
        out[cle] = lignes
    out["ou"] = dn.noms[lv_d].get(code_d, "") if lv == "epci" else ""
    out["region"] = bool(reg)
    return out


# professions dont la fiche montre où elles exercent (secteurs, structures de santé mentale, catégories FINESS,
# établissements), comme le bas de la page Carte de l'atlas, au département (31 octobre 2026)
EXERCICE_PROFS = {"sm": ["psychiatre", "psychologue"], "sante": ["medecin_generaliste"]}


def _barres(rows, total, k=None):
    rows = rows[:k] if k else rows
    m = max((n for _, n in rows), default=0) or 1
    return [{"lib": l, "n": nombre(n, "entier"), "pc": f"{round(n / total * 100)}{FINE}%" if total else "",
             "l": f"{n / m * 100:.1f}%"} for l, n in rows]


def _exercice(dn, lv, code, dep):
    """Où exercent les professionnels du département : secteur d'activité du RPPS, structures de santé mentale à numéro
    FINESS propre, catégorie FINESS des établissements et établissements qui en réunissent le plus. Données
    départementales (export._exercice_atlas et voisins) ; rien pour une région."""
    lv_d, code_d = _niveau_dep(lv, code, dep)
    if lv_d != "dep":
        return {}
    sd, out = dn.sd, {}
    for fam, profs in EXERCICE_PROFS.items():
        bloc = []
        for p in profs:
            # libellés d'affichage de la table unique (pipeline/libelles.csv), repassés ici pour que les formes
            # développées ajoutées à la table servent sans refaire les calculs
            sec = [(L.affichage(sd["secteurs"]["lib"][i], "RPPS secteur"), n) for i, n in (sd.get("secteurs", {}).get("v", {}).get(p, {}).get(code_d) or [])]
            ex = [(sd["exercice"]["lib"][i], n) for i, n in (sd.get("exercice", {}).get("v", {}).get(p, {}).get(code_d) or [])]
            cat = [(L.affichage(sd["categories"]["lib"][i]), n) for i, n in (sd.get("categories", {}).get("v", {}).get(p, {}).get(code_d) or [])]
            etab = sd.get("structures", {}).get(p, {}).get(code_d) or []
            if not sec and not cat:
                continue
            tc = sum(n for _, n in cat)
            bloc.append({"prof": p, "lib": dict(PROFS_SM + PROFS_SANTE).get(p, p), "secteurs": _barres(sec, sum(n for _, n in sec)),
                         "ex": _barres(ex, 0), "cat": _barres(cat, tc, 10), "cat_reste": len(cat) - 10 if len(cat) > 10 else 0,
                         "cat_reste_n": nombre(sum(n for _, n in cat[10:]), "entier") if len(cat) > 10 else "",
                         "etab": [{"rs": rs, "commune": c, "n": nombre(n, "entier")} for rs, c, n in etab]})
        out[fam] = bloc
    out["ou"] = dn.noms["dep"].get(code_d, "")
    out["intercommunalite"] = lv == "epci"
    return out


# du répertoire aux densités (France entière), étapes de l'atlas (atlas/moteur/atlas.js, ETAPES)
ETAPES = [(0, "Inscrits au répertoire", ""), (1, "Avec une activité déclarée", "sans activité déclarée"),
          (3, "Avec un lieu d'exercice", "sans lieu fixe (remplacements, exercice sans site)"),
          (6, "Comptés dans les densités", "seulement des activités non rattachées à un territoire")]


def _parcours(dn):
    """Du répertoire aux densités, pour les professions dont la fiche montre où elles exercent (France entière)."""
    out = {}
    for fam, profs in EXERCICE_PROFS.items():
        bloc = []
        for p in profs:
            v = (dn.sd.get("parcours") or {}).get(p)
            if not v:
                continue
            et = [e for e in ETAPES if v[e[0]]]
            tot, pr, etapes = v[et[0][0]], None, []
            for i, titre, raison in et:
                n = v[i]
                det = ""
                if pr is not None and pr > n:
                    det = f"− {nombre(pr - n, 'entier')} {raison}"
                    if i == 6:
                        d = [x for x in ((v[5], "en téléconsultation (soins à distance)"), (v[4], "sans soins à la population")) if x[0]]
                        if d:
                            det += ", dont " + " et ".join(f"{nombre(a, 'entier')} {b}" for a, b in d)
                etapes.append({"titre": titre, "n": nombre(n, "entier"), "l": f"{n / tot * 100:.1f}%", "det": det, "der": i == 6})
                pr = n
            bloc.append({"lib": dict(PROFS_SM + PROFS_SANTE).get(p, p), "etapes": etapes})
        out[fam] = bloc
    return out


SIGLES_ETABLISSEMENT = {"EPSM": "établissement public de santé mentale", "CHS": "centre hospitalier spécialisé",
                        "CHU": "centre hospitalier universitaire", "CH": "centre hospitalier"}


def reperes_secteurs(dn, code: str, pop_communes: dict | None = None, lv: str = "epci") -> dict:
    """Repères de la santé mentale d'une intercommunalité, là où la sectorisation est publiée
    (secteurs_psychiatrie.csv) : secteurs adultes (G) et infanto-juvéniles (I) qui couvrent ses communes, avec leur
    part des habitants (centres de population de l'INSEE, à défaut le nombre de communes), et l'établissement de
    rattachement. Un établissement est regroupé par son FINESS juridique et ne porte qu'un nom, le plus employé dans
    les arrêtés, avec la forme développée de son sigle : « EPSM Aisne » et « EPSMDA » désignaient le même
    établissement sous deux noms (relecture de clarté du 31 octobre 2026, défaut 2)."""
    toutes = dn._csv("secteurs_psychiatrie.csv")
    if lv == "epci":
        epci_de = {l["code"]: l["epci"] for l in dn._csv("accessibilite_communes.csv")}
        lignes = [l for l in toutes if epci_de.get(l["commune"]) == code]
    else:   # un département ou une région : toutes ses communes
        lignes = [l for l in toutes if l.get(lv) == code]
    out = {"publie": bool(lignes), "G": [], "I": [], "etabs": [], "source": ""}
    if not lignes:
        return out
    pop = pop_communes
    if pop is None:
        f = config.DONNEES / "intermediaire" / "centres_population_communes.parquet"
        try:
            import pandas as pd
            x = pd.read_parquet(f, columns=["code", "pop"])
            pop = dict(zip(x["code"].astype(str), x["pop"].astype(float)))
        except Exception:  # noqa: BLE001 (sans le fichier, la part des habitants n'est pas écrite)
            pop = {}
    noms: dict = {}
    fjs = {l["finess_entite_juridique"] for l in lignes}
    for l in toutes:   # le nom le plus employé dans tous les arrêtés, pas seulement pour ce territoire
        if l["finess_entite_juridique"] in fjs:
            noms.setdefault(l["finess_entite_juridique"], []).append(l["etablissement_responsable"])
    nom_de = {fj: max(sorted(set(n)), key=n.count) for fj, n in noms.items()}   # à égalité, le premier par ordre alphabétique
    tot = sum(pop.get(c, 0) for c in {l["commune"] for l in lignes})
    for t in ("G", "I"):
        sec: dict = {}
        for l in lignes:
            if l["type"] == t:
                sec.setdefault(l["secteur_psychiatrie"], {"fj": l["finess_entite_juridique"], "communes": set()})["communes"].add(l["commune"])
        # une commune partagée entre plusieurs secteurs (Lille, 3 secteurs adultes) n'est comptée dans la part d'aucun :
        # comptée en entier dans chacun, les parts dépassaient 100 % (relecture du 31 octobre 2026, M6). Sa population
        # n'est pas découpée par secteur dans les sources, on le dit sans pourcentage.
        nb_sec: dict = {}
        for x in sec.values():
            for c in x["communes"]:
                nb_sec[c] = nb_sec.get(c, 0) + 1
        partagees = {c for c, k in nb_sec.items() if k > 1}
        rangs = sorted(sec.items(), key=lambda kv: (-sum(pop.get(c, 0) for c in kv[1]["communes"] - partagees), kv[0]))
        for s, x in rangs:
            nb = len(x["communes"])
            seules, sh = x["communes"] - partagees, len(x["communes"] & partagees)
            p = sum(pop.get(c, 0) for c in seules) / tot if tot and seules else None
            part = "" if p is None else (f"moins de 1{FINE}%" if p < .01 else f"{round(100 * p)}{FINE}%")
            if sh:
                bout = f"une partie de {sh} commune{'s' if sh > 1 else ''} partagée{'s' if sh > 1 else ''} avec d'autres secteurs"
                part = f"{part}, et {bout}" if part else bout
            out[t].append({"code": s, "etab": nom_de[x["fj"]], "finess": x["fj"], "communes": f"{nb} commune{'s' if nb > 1 else ''}",
                           "part": part})
    for fj, nom in nom_de.items():
        types = [lib for t, lib in (("G", "adulte"), ("I", "infanto-juvénile")) if any(s["finess"] == fj for s in out[t])]
        sigle = nom.split()[0].rstrip(",")
        long = next((v for k, v in SIGLES_ETABLISSEMENT.items() if sigle == k or sigle.startswith(k) and k == "EPSM"), "")
        if sigle.startswith("EPSMD"):
            # EPSMD : établissement public de santé mentale départemental, du département de ses secteurs ; l'article
            # n'est écrit que devant une voyelle (« de l'Aisne »), sûr sans connaître le genre du nom
            deps = [l["dep"] for l in toutes if l["finess_entite_juridique"] == fj]
            nd = dn.noms["dep"].get(max(set(deps), key=deps.count), "") if deps else ""
            long = "établissement public de santé mentale départemental" + (
                f" de l'{nd}" if nd[:1].lower() in "aeiouyéèh" else f", {nd}" if nd else "")
        out["etabs"].append({"nom": nom, "long": long, "finess": fj, "types": " et ".join(types),
                             "secteurs": [s["code"] for t in ("G", "I") for s in out[t] if s["finess"] == fj]})
    l0 = lignes[0]
    doc, date = l0.get("document") or "", AF.date_longue(l0.get("date_document")) if l0.get("date_document") else ""
    # la date n'est ajoutée que si le titre de l'arrêté ne la porte pas déjà
    out["source"] = doc + (f", {date}" if date and date not in doc else "")
    return out


def series_courtes(resultats: Path) -> dict:
    """Effectifs de chaque profession, par territoire, aux dates des versions publiées (donnees/publication.json),
    lus dans effectifs_<niveau>_all.csv de chaque version : {(niveau, code, profession): [(date, effectif), ...]}."""
    pub = config.RACINE / "donnees" / "publication.json"
    dates = (json.loads(pub.read_text(encoding="utf-8-sig")).get("versions_publiees") or []) if pub.exists() else []
    profs = {p for p, _ in PROFS_SM + PROFS_SANTE}
    out: dict = {}
    for d in dates:
        for lv in NIVEAUX:
            f = resultats / d / f"effectifs_{lv}_all.csv"
            if not f.exists():
                continue
            with f.open(encoding="utf-8-sig") as fh:
                for l in csv.DictReader(fh, delimiter=";"):
                    for p in profs:
                        x = l.get("n_" + p)
                        if x not in (None, ""):
                            out.setdefault((lv, l["code"], p), []).append((d, int(float(x))))
    return out


def bornes_legende(bo: list, g: str) -> list[str]:
    """Bornes d'une légende de classes écrites selon la règle d'affichage ; si l'arrondi en rend deux identiques
    (« 2,2 » et « 2,2 »), toutes prennent une décimale de plus, pour que chaque classe se lise."""
    txt = [nombre(b, g) for b in bo]
    if len(set(txt)) == len(txt):
        return txt
    d = max(decimales(b, g) for b in bo) + 1
    return [f"{b:,.{d}f}".replace(",", FINE).replace(".", ",") for b in bo]


def serie_courte(pts: list | None) -> dict | None:
    """Petite courbe d'encre des effectifs aux versions publiées, échelle d'au moins 10 % de la valeur (direction
    visuelle, série courte) ; « plat » quand l'effectif bouge de moins de 2 % : la page n'écrit alors que la phrase."""
    if not pts or len(pts) < 2:
        return None
    lo, hi = min(n for _, n in pts), max(n for _, n in pts)
    marge = max(0.0, (0.10 * hi - (hi - lo)) / 2)
    lo2, hi2 = lo - marge, hi + marge
    ech = (lambda n: 21 - 18 * (n - lo2) / (hi2 - lo2)) if hi2 > lo2 else (lambda n: 12)  # noqa: E731
    xs = [4 + 88 * j / (len(pts) - 1) for j in range(len(pts))]
    return {"pts": " ".join(f"{x:.1f},{ech(n):.1f}" for x, (_, n) in zip(xs, pts)),
            "debut": (AF.date_longue(pts[0][0]), pts[0][1]), "fin": (AF.date_longue(pts[-1][0]), pts[-1][1]),
            "nb": len(pts), "fin_xy": (round(xs[-1], 1), round(ech(pts[-1][1]), 1)), "plat": hi - lo <= .02 * hi}


TEMPS_BORNES = [10, 15, 20, 30]   # minutes, nombres ronds, seuils de l'INSEE (config.ACCES_ROUTE_SEUILS) compris


def couches_carte(dernier: Path, site: Path) -> int:
    """Couches de la carte du territoire, un fichier par département dans presentation/couches/, chargé par la fiche
    avec les contours des communes (presentation/zone_fond) : l'intercommunalité de chaque commune, le temps de route
    médian de ses habitants vers le psychiatre libéral le plus proche (INSEE, temps_acces_communes.csv), et, là où la
    sectorisation est publiée, les contours des secteurs de psychiatrie (communes réunies, dans la projection des
    cartes) avec le point où écrire leur code."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from . import cartes_presentation as CP
    fond = site / "presentation" / "zone_fond"
    if not fond.exists():
        return 0

    def lire(nom):
        f = dernier / nom
        if not f.exists():
            return []
        with f.open(encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh, delimiter=";"))
    epci = {l["code"]: l["epci"] for l in lire("accessibilite_communes.csv")}
    temps = {l["code"]: round(float(l["temps_median_min"].replace(",", ".")), 1) for l in lire("temps_acces_communes.csv")
             if l.get("equipement") == "psychiatre_liberal" and l.get("temps_median_min")}
    sect: dict = {}
    for l in lire("secteurs_psychiatrie.csv"):
        sect.setdefault(l["dep"], {}).setdefault((l["type"], l["secteur_psychiatrie"]), set()).add(l["commune"])
    proj = CP.projection()
    sortie = site / "presentation" / "couches"
    sortie.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(fond.glob("*.json")):
        dep = f.stem
        Z = json.loads(f.read_text(encoding="utf-8"))
        coms = list(Z["c"])
        out = {"e": {c: epci[c] for c in coms if c in epci}, "t": {c: temps[c] for c in coms if c in temps}, "s": {}}
        if dep in sect:
            ox, oy = Z["o"]
            poly = {}
            for c, anneaux in Z["c"].items():
                ps = []
                for a in anneaux:
                    x, y = a[0], a[1]
                    pts = [proj(ox + x / 1e4, oy + y / 1e4)]
                    for j in range(2, len(a), 2):
                        x += a[j]
                        y += a[j + 1]
                        pts.append(proj(ox + x / 1e4, oy + y / 1e4))
                    if len(pts) >= 3:
                        ps.append(Polygon(pts).buffer(0))
                poly[c] = ps
            for (t, code), cs in sorted(sect[dep].items()):
                g = unary_union([q for c in cs for q in poly.get(c, [])]).buffer(.15).buffer(-.15)
                if g.is_empty:
                    continue
                g = g.simplify(.2)
                parts = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
                d = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in q.exterior.coords) + "Z" for q in parts if q.area > .05)
                pt = g.representative_point()
                out["s"].setdefault(t, []).append([code, d, round(pt.x, 1), round(pt.y, 1)])
        (sortie / f"{dep}.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        n += 1
    return n


def _secteurs_psy(dn, lv, code, dep):
    """Les secteurs de psychiatrie ne sont publiés que pour quelques régions (secteurs_psychiatrie.csv) : la fiche dit
    s'ils le sont pour ce territoire (plan des structures de l'atlas, 31 octobre 2026)."""
    deps = {r["dep"] for r in dn._csv("secteurs_psychiatrie.csv")}
    if lv == "reg":
        return any(dn.unite("dep", d).get("p") == dn.noms["reg"][code] for d in deps if d in dn.pos["dep"])
    return (dep if lv == "epci" else code) in deps


def synthese(n, haut, bas):
    """Phrase de tête d'un domaine du contexte, sans score ni classement : combien d'indicateurs sortent de la marge de
    0,8 à 1,25 fois le repère (pipeline/affichage.PROCHE). Ces indicateurs ne portent pas de couleur et le hasard n'y
    est pas testé : la phrase nomme la marge, et non un écart « net », mot réservé à la règle des couleurs de l'offre
    (synthese_offre ; relecture du prototype de fiche resserrée, 31 octobre 2026, M5)."""
    if not n:
        return "Aucune base n'est encore intégrée dans ce domaine."
    debut = f"Sur les {n} indicateurs du domaine, " if n > 1 else "Sur l'indicateur du domaine, "
    marge = "la marge de 0,8 à 1,25 fois l'ensemble"   # le mot qui nomme le repère, partout (règles du projet, partie 5)
    e = haut + bas
    if not e:
        return debut + f"aucun ne sort de {marge}." if n > 1 else debut + f"la valeur reste dans {marge}."
    if haut and bas:
        return debut + f"{e} sortent de {marge}, {haut} au-dessus et {bas} en dessous."
    qui = "la valeur" if n == 1 else "tous" if e == n else str(e)
    return debut + f"{qui} {'sont' if e > 1 else 'est'} {'au-dessus' if haut else 'en dessous'} de {marge}."


def synthese_offre(lignes: list, quoi: str) -> dict:
    """Comptage des écarts nets d'un tableau de l'offre : les lignes que la règle d'affichage colore (hors de 0,8 à
    1,25 fois l'ensemble et au-delà du hasard), parmi celles qui portent une valeur. Rend le nombre de lignes, ceux
    au-dessus et en dessous, et la phrase (« Sur les 18 professions et structures du tableau, 1 est nettement en
    dessous de l'ensemble. »), sans score ni classement."""
    offre = [l for l in lignes if l.get("offre") and l.get("txt")]
    haut, bas = (len(x) for x in _ecartes(offre))
    n, e = len(offre), haut + bas
    debut = f"Sur les {n} {quoi} du tableau, "
    if not n:
        phrase = ""
    elif not e:
        phrase = debut + "aucun ne s'écarte nettement de l'ensemble."
    elif haut and bas:
        phrase = debut + f"{e} s'écartent nettement de l'ensemble, {haut} au-dessus et {bas} en dessous."
    else:
        phrase = debut + f"{e} {'sont' if e > 1 else 'est'} nettement {'au-dessus' if haut else 'en dessous'} de l'ensemble."
    return {"n": n, "haut": haut, "bas": bas, "phrase": phrase}


# -- mise en forme et construction des pages ----------------------------------------------------------------------
# nombres écrits par la règle d'affichage (pipeline/affichage.nombre), anciens genres de ce module conservés
_GENRES = {"densite": "taux", "ctx": "taux", "ctx2": "taux"}


def ecart(e) -> str:
    return AF.ecart_txt(e)


def _nombre_filtre(v, genre="taux"):
    return nombre(v, _GENRES.get(genre, genre))


def confirmation(conf: dict) -> str:
    """Confirmation d'un type de structure, en peu de mots : « confirmée », « toutes confirmées », « dont 3 confirmées,
    1 à vérifier ». « Sans source de confirmation » est expliqué dans « Comment lire »."""
    noms = (("confirmee", "confirmée", "confirmées"), ("recoupee", "recoupée", "recoupées"),
            ("verifier", "à vérifier", "à vérifier"), ("objet", "sans source de confirmation", "sans source de confirmation"))
    tot = sum(conf.get(c, 0) for c, _, _ in noms)
    for cle, un, plus in noms:
        if tot and conf.get(cle, 0) == tot:
            return un if tot == 1 else ("toutes " + plus if cle != "objet" else plus)
    morceaux = [f"{conf[c]} {plus if conf[c] > 1 else un}" for c, un, plus in noms if conf.get(c)]
    return ("dont " + ", ".join(morceaux)) if morceaux else "aucune confirmée"


def filtres(env):
    env.filters["nombre"] = _nombre_filtre
    env.filters["entier"] = lambda n: nombre(n, "entier")   # espace des milliers (« 11 179 inscrits »)
    from .lecture import minuscule
    env.filters["minuscule"] = minuscule
    env.filters["ecart"] = ecart
    env.filters["confirmation"] = confirmation
    from .libelles import casse_titre
    env.filters["casse"] = casse_titre


def _pourquoi(dn: Donnees, k: dict, cat: dict, date_rpps: str | None) -> dict:
    """Ce que dit « Pourquoi on le dit » d'un constat : le calcul avec ses nombres, le repère, le hasard, la source
    datée avec sa licence, la limite."""
    c, lv = k["cel"], k["lv"]
    niv = NIV_PLURIEL[lv]
    e = cat.get(k["id"]) or {}
    calcul = []
    if c["kind"] in ("prof", "lieux"):
        S = dn.T.serie(k["id"], lv)
        base = S.base[dn.pos[lv][k["code"]]] if S else None
        un = c["n"] is not None and c["n"] < 2   # accord au singulier pour 0 et 1
        if c["kind"] == "prof":
            qui = ("inscrit" if un else "inscrits") + " au répertoire RPPS" + (f" du {date_rpps}" if date_rpps else "")
        else:
            qui = "structure inscrite" if un else "structures inscrites"
        rapporte = ("rapporté" if un else "rapportés") if c["kind"] == "prof" else ("rapportée" if un else "rapportées")
        # la base nommée telle qu'elle est : tous les habitants, ou le public d'une structure à part (moins de 15 ans,
        # 80 ans et plus) ; « public concerné » se lisait pour les CMP pour adultes, rapportés à tous les habitants
        # (relecture des fiches construites du 1er novembre 2026, mineur 5)
        from . import lieux_profil
        lab = lieux_profil.denominateur(k["id"][6:])[1] if c["kind"] == "lieux" else ""
        public = f"habitants de {lab}" if lab else "habitants"
        unite = AF.txt_unite(c['fac']) if c['kind'] == 'prof' else 'pour 100 000'
        if c["n"] == 0 and base:
            # jamais un 0 seul (règles du projet, partie 4, défaut M3) : « aucun inscrit », sans densité nulle
            calcul.append(f"{'Aucun inscrit au répertoire RPPS' + (f' du {date_rpps}' if date_rpps else '') if c['kind'] == 'prof' else 'Aucune structure inscrite'} "
                          f"pour {nombre(base, 'entier')} {public}.")
        elif c["n"] is not None and base:
            calcul.append(f"{nombre(c['n'], 'entier')} {qui}, {rapporte} à {nombre(base, 'entier')} {public} : "
                          f"{c['v_txt']} {unite}.")
        calcul.append(f"Le repère, « {c['ref_lib']} », est la {AF.NATURE_REPERE[c['ref_type']]} ({c['ref_txt']}). "
                      f"La position compte les {niv} dont la valeur est plus basse ; {c['med_lib'].lower()} : "
                      # jamais un 0 seul (relecture du prototype resserré, m6) : « aucun inscrit », comme la réglette
                      f"{('aucun inscrit' if c['kind'] == 'prof' else 'aucune structure') if c['med'] == 0 else c['med_txt']}.")
        if c["statut"] in ("petit", "aucun"):
            calcul.append(f"Sous {AF.PETIT_EFFECTIF}, aucun écart n'est calculé ni coloré.")
        elif c["ref"] and base:
            a, b = AF._poisson_bornes(c["ref"] / c["fac"] * base)
            calcul.append(f"Si seul le hasard jouait, au taux de l'ensemble, l'effectif se trouverait 95 fois sur 100 entre "
                          f"{nombre(a, 'entier')} et {nombre(b, 'entier')}. Un écart n'est coloré que hors de cet intervalle "
                          f"et hors de 0,8 à 1,25 fois l'ensemble.")
    elif c["kind"] == "dist":
        calcul.append("Distance à vol d'oiseau entre le centre de la commune de chaque habitant et la structure la plus "
                      "proche, médiane des habitants du territoire.")
        calcul.append(f"Le repère, « {c['ref_lib']} », est la {AF.NATURE_REPERE[c['ref_type']]} ({c['ref_txt']} km). "
                      f"La position compte les {niv} plus proches.")
    else:
        calcul.append("Valeur publiée par la source pour le territoire" + (", lue au département" if k["echelle"] else "") + ".")
        calcul.append(f"Le repère, « {c['ref_lib']} », est la {AF.NATURE_REPERE[c['ref_type']]} ({c['ref_txt']}). La "
                      f"position compte les {niv} dont la valeur est plus basse.")
    date = AF.date_longue(e.get("date")) if e.get("date") else None
    source = ", ".join(x for x in (e.get("source"), f"données du {date}" if date else None, e.get("licence")) if x)
    from .constats import limite_retenue
    lim = k.get("limite") or e.get("limite")
    return {"calcul": calcul, "source": source, "limite": lim if limite_retenue(dn, lim, c) else None}


def construire(env, commun: dict, dernier: Path, site_data: dict, site: Path, registre: Path, adresse: str,
               citation_auteur: str, seulement: set | None = None) -> list[Path]:
    """Écrit la fiche de chaque région, département et intercommunalité dans site/territoire/<niveau>/<code>.html.
    seulement, un ensemble de (niveau, code), limite la construction à ces fiches (constructions partielles)."""
    filtres(env)
    dn = Donnees(site_data, dernier)
    from . import cartes_presentation as CP
    from .typographie import insecables
    from . import constats as K
    from . import bandes_fiche as BF
    from .libelles import casse_titre
    from .atelier import ENCARTS, _fond
    # fond de l'atelier et structures de soins psychiques projetées, pour la carte de situation et le plan (métropole ;
    # les départements d'outre-mer sont en encarts à une autre échelle et n'ont que les aplats)
    A, points_dep = None, {}
    f_fond = site / "explorer" / "fond.js"
    if f_fond.exists():
        A = {"geo": _fond(f_fond, site_data), "units": {lv: site_data["niveaux"][lv]["units"] for lv in NIVEAUX}}
        proj, sm = CP.projection(), {t for t, _ in STRUCT_SM}
        ip, noms_types, noms_lieux = dn.ip, dict(STRUCT_SM), (site_data.get("lieux") or {}).get("noms", [])
        for pt in dn.pts:
            typ = dn.types[pt[0]] if pt[0] < len(dn.types) else None
            if typ not in sm or pt[ip["dep"]] in ENCARTS or pt[ip["lat"]] is None:
                continue
            x, y = proj(pt[ip["lon"]] / 1e4, pt[ip["lat"]] / 1e4)   # coordonnées au dix-millième de degré
            c = pt[ip["confirmation"]] if "confirmation" in ip else None
            cl = dn.classes_conf[c] if isinstance(c, int) and c < len(dn.classes_conf) else None
            nom = noms_lieux[pt[ip["nom"]]] if isinstance(pt[ip["nom"]], int) and pt[ip["nom"]] < len(noms_lieux) else ""
            # raisons sociales en casse de titre partout, comme les listes (relecture du 1er novembre 2026, mineur 4)
            titre = f"{noms_types[typ]}, {casse_titre(nom)}".replace("&", "&amp;").replace("<", "&lt;")
            points_dep.setdefault(pt[ip["dep"]], []).append((round(x, 2), round(y, 2), cl, titre, pt[ip["epci"]]))
    tous_deps = [u["c"] for u in site_data["niveaux"]["dep"]["units"]]
    fonds_communes = {f.stem for f in (site / "presentation" / "zone_fond").glob("*.json")}
    reg_code = {r["nm"]: r["c"] for r in site_data["niveaux"]["reg"]["units"]}
    drom = {"01": "971", "02": "972", "03": "973", "04": "974", "06": "976"}
    deps_de_reg: dict = {}
    for u in site_data["niveaux"]["dep"]["units"]:
        deps_de_reg.setdefault(reg_code.get(u.get("p")), []).append(u["c"])
    epcis_de_dep: dict = {}
    for u in site_data["niveaux"]["epci"]["units"]:
        epcis_de_dep.setdefault(u.get("p"), []).append(u["c"])
    venir = D.bases_a_venir(registre)
    cat = {e["id"]: e for e in AF.catalogue(site_data, dernier)}
    gabarit = env.get_template("fiche_territoire.html")
    # part des structures de soins psychiques confirmées en France, sur les mêmes types
    tot = conf = 0
    for t, _ in STRUCT_SM:
        for code in dn.pos["reg"]:
            n, c = dn.structures("reg", code, t)
            tot += n or 0
            conf += c["confirmee"]
    # part des structures confirmées sur tout le territoire national, nommée comme le repère de chaque niveau
    # (« pour l'ensemble des intercommunalités »), jamais « en France » (règle de nommage du repère ; relecture de clarté du
    # 31 octobre 2026, défaut 6) : chaque structure y compte une fois, la valeur est celle de l'ensemble
    part_conf = round(conf / tot * 100) if tot else None

    def confiance_ensemble(lv):
        return (f"Pour l'ensemble des {NIV_PLURIEL[lv]}, {part_conf}{FINE}% des structures sont confirmées."
                if part_conf is not None else "")
    date_rpps = _date_rpps(dernier)
    millesime = (site_data["meta"].get("millesimes_insee") or {}).get("pop")
    sources = (f"répertoire RPPS{(' du ' + date_rpps) if date_rpps else ''}, FINESS et Répertoire "
               f"opérationnel des ressources{(', recensement ' + str(millesime) + " de l'INSEE") if millesime else ''}.")
    from . import config
    from .site import doi_cite
    doi = doi_cite("donnees", dernier.name)
    classes: dict = {}

    def bornes(ident, lv):
        """Valeurs et bornes des cinq classes d'un indicateur à un niveau, pour les petites cartes."""
        if (ident, lv) not in classes:
            S = dn.T.serie(ident, lv)
            b = CP.classes_densite(S.v) if S else None
            classes[(ident, lv)] = (dict(zip(S.codes, S.v)) if S else {}, b, S.genre if S else "taux")
        return classes[(ident, lv)]

    def cadre_local(F, lv, code, dep):
        """Cadre des petites cartes : le département d'une intercommunalité, la région d'un département, la France
        pour une région (outre-mer, son encart), et le contour du territoire qui l'entoure."""
        if lv == "epci":
            if dep in ENCARTS:
                x, y, w, h = ENCARTS[dep]
                return (x, y, x + w, y + h), None
            b = F.boite("dep", dep) or F.boite("epci", code)
            return CP.cadre_autour([b], .04), ("dep", dep) if F.boite("dep", dep) else None
        if lv == "dep":
            if code in ENCARTS:
                x, y, w, h = ENCARTS[code]
                return (x, y, x + w, y + h), None
            r = reg_code.get(dn.unite("dep", code).get("p"))
            b = [F.boite("dep", d) for d in deps_de_reg.get(r, [code]) if F.boite("dep", d)]
            return CP.cadre_autour(b, .04), ("reg", r) if r and F.boite("reg", r) else None
        if code in drom:
            x, y, w, h = ENCARTS[drom[code]]
            return (x, y, x + w, y + h), None
        b = [F.boite("reg", r) for r in reg_code.values() if r not in drom and F.boite("reg", r)]
        return CP.cadre_autour(b, .02), None

    semblables = _semblables(dernier)
    couches_carte(dernier, site)
    series = series_courtes(dernier.parent)
    try:   # part des habitants de chaque secteur (centres de population de l'INSEE)
        import pandas as pd
        x = pd.read_parquet(config.DONNEES / "intermediaire" / "centres_population_communes.parquet", columns=["code", "pop"])
        pop_com = dict(zip(x["code"].astype(str), x["pop"].astype(float)))
    except Exception:  # noqa: BLE001 (sans le fichier, la part des habitants n'est pas écrite)
        pop_com = {}
    pages = []
    for lv in NIVEAUX:
        dossier = site / "territoire" / lv
        dossier.mkdir(parents=True, exist_ok=True)
        for u in site_data["niveaux"][lv]["units"]:
            if seulement is not None and (lv, u["c"]) not in seulement:
                continue
            f = fiche(dn, lv, u["c"], dernier.name)
            lim_sae = dn.limite("manque_sae", lv, u["c"])
            dep = u.get("p") if lv == "epci" else (u["c"] if lv == "dep" else None)
            if lv == "epci" and not (lim_sae and lim_sae.get("territoire")) and dep:
                lim_sae = dn.limite("manque_sae", "dep", dep)
            comp = f"{lv}:{u['c']}"
            comparer = [(f"D'autres {NIV_PLURIEL[lv]} ou territoires", f"../../comparer.html#t={comp}")]
            if lv == "epci" and dep:
                comparer.append(("Son département", f"../../comparer.html#t={comp},dep:{dep}"))
            sem = semblables.get(u["c"], []) if lv == "dep" else []
            if sem:
                comparer.append((f"Départements de profil semblable : {', '.join(dn.noms['dep'].get(s, s) for s in sem)}",
                                 f"../../comparer.html#t={comp}," + ",".join(f"dep:{s}" for s in sem)))
            liens = [("Toutes les cartes de l'atlas", f"../../atlas.html#?niv={lv}&terr={lv}:{u['c']}")]
            if lv in ("dep", "reg"):
                for cle, titre in (("sante-mentale", "Rapport santé mentale du territoire"), ("sante", "Rapport santé du territoire")):
                    if (site / "territoires" / f"{lv}-{u['c']}-{cle}.html").exists():
                        liens.append((titre, f"../../territoires/{dernier.name}/{lv}-{u['c']}-{cle}.html"))
            # constats, petites cartes et réglettes
            ks = K.constats(dn, f, lv, u["c"], dep if lv == "epci" else None)
            F = CP.Formes(A) if A else None
            carte = None
            if F:
                for k in ks:
                    vals, bo, g = bornes(k["id"], k["lv"])
                    if not bo or F.boite(k["lv"], k["code"]) is None:
                        continue
                    cad, contour = cadre_local(F, k["lv"], k["code"], dep if k["lv"] == "epci" else None)
                    nom_ind = (cat.get(k["id"]) or {}).get("nom_court") or k["id"]
                    k["carte"] = CP.mini_carte(F, k["lv"], k["code"], vals, bo, cad,
                                               f"{nom_ind}, par {NOM_NIVEAU[k['lv']].lower()}, en cinq classes de même "
                                               f"effectif, autour du territoire", contour)
                    n = len(bo) + 1
                    k["bornes"] = [(t, f"{100 * (j + 1) / n:.2f}%") for j, t in enumerate(bornes_legende(bo, g))]
                    k["cases"] = CP.legende_classes(bo)
                    k["nom_ind"] = k.get("nom") or nom_ind
                    k["unite_leg"] = ((k["cel"]["kind"] == "prof" and AF.txt_unite(k["cel"]["fac"])) or
                                      (cat.get(k["id"]) or {}).get("unite") or "").replace(" hab.", " habitants")
                    bk = F.boite(k["lv"], k["code"])
                    k["situe"] = CP.situer(F, cad, ((bk[0] + bk[2]) / 2, (bk[1] + bk[3]) / 2) if bk else None)
                # carte de situation et plan des structures de soins psychiques
                b = F.boite(lv, u["c"])
                pts, deps_fond, sous, parent = [], [], [], None
                if b:
                    if lv == "epci":
                        cad = CP.cadre_autour([b], .22, 1.75, mini=36)
                        deps_fond = sorted(d for d in F.dans("dep", cad) if d in fonds_communes and d not in ENCARTS)
                        for d in deps_fond:
                            pts += [(x, y, cl, ti, e == u["c"]) for x, y, cl, ti, e in points_dep.get(d, [])]
                        parent = ("dep", dep) if F.boite("dep", dep or "") else None
                    elif lv == "dep":
                        cad = CP.cadre_autour([b], .08, 1.4)
                        pts = [(x, y, cl, ti, True) for x, y, cl, ti, e in points_dep.get(u["c"], [])]
                        deps_fond = [u["c"]] if u["c"] in fonds_communes and u["c"] not in ENCARTS else []
                        sous = [("epci", e) for e in epcis_de_dep.get(u["c"], []) if F.boite("epci", e)]
                    else:
                        cad = CP.cadre_autour([b], .06, 1.1)
                        sous = [("dep", d) for d in deps_de_reg.get(u["c"], []) if F.boite("dep", d)]
                    carte = CP.plan(F, lv, u["c"], sous, pts, deps_fond, cad, parent)
                    f["carte_situe"] = CP.situer(F, cad, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
                    f["carte_couches"] = bool(deps_fond)
                    f["carte_outremer"] = (dep if lv == "epci" else u["c"]) in ENCARTS or (lv == "reg" and u["c"] in drom)
                    f["carte_points"] = any(p[4] for p in pts)
                    f["carte_points_autour"] = any(not p[4] for p in pts)
                    f["carte_communes"] = bool(deps_fond)
            for k in ks:
                # pas d'intervalle annoncé pour un effectif nul ou un statut (relecture du 31 octobre 2026)
                k["intervalle"] = AF.intervalle_prevu(k["id"], k["cel"]["kind"]) and bool(k["cel"].get("n"))                     and k["cel"].get("statut") not in ("aucun", "non_recense", "non_publie")
                k["unite"] = (AF.txt_unite(k["cel"]["fac"]) if k["cel"]["kind"] == "prof" else "km, médiane des habitants"
                              if k["cel"]["kind"] == "dist" else ((cat.get(k["id"]) or {}).get("unite") or "")).replace(" hab.", " habitants")
                prof = k["id"].split(":")[1] if k["id"].startswith("prof:") else None
                k["serie"] = serie_courte(series.get((k["lv"], k["code"], prof))) if prof else None
                k["attendu"] = _phrase_attendu(dn, k)
                k["pourquoi"] = _pourquoi(dn, k, cat, date_rpps)
                k["reglette"] = dn.T.reglette(k["id"], k["lv"], k["code"], k["cel"])
                if k["reglette"] and k["cel"]["kind"] not in ("prof", "lieux"):
                    k["reglette"]["classe"] = k["reglette"]["classe"] if k["reglette"]["classe"] in ("sans", "petit") else ""
                for x in K.interdits(k["titre"] + " " + " ".join(k["phrases"])):
                    raise ValueError(f"mot interdit « {x} » dans un constat de {f['nom']}")
            f["reperes"] = reperes_secteurs(dn, u["c"], pop_com, lv)
            st_cmp = next((s for s in f["structures"] if s["id"] == "lieux_lieu_cmp_adultes"), None)
            d_cmp = next((l for l in f["sm_dist"] if l.get("id") == "dist_lieu_cmp_adultes"), None)
            conf_cmp = confirmation(st_cmp["conf"]) if st_cmp and st_cmp["n"] else ""
            for a, b2 in (("toutes ", "tous "), ("confirmées", "confirmés"), ("confirmée", "confirmé"), ("recoupées", "recoupés"),
                          ("recoupée", "recoupé")):
                conf_cmp = conf_cmp.replace(a, b2)   # accord au masculin : un CMP
            st_tous = next((s for s in f["structures"] if s["id"] == "lieux_lieu_cmp"), None)
            f["reperes"]["cmp"] = {"n": st_cmp["n"] if st_cmp else None, "conf": conf_cmp,
                                   "tous": (st_tous or {}).get("n") or 0,
                                   "dist": d_cmp["txt"] if d_cmp and d_cmp.get("txt") else "",
                                   "dist_nulle": bool(d_cmp and d_cmp.get("txt") and AF.distance_nulle(d_cmp["txt"])),
                                   "ref": d_cmp["ref_txt"] if d_cmp else "", "pos": d_cmp["pos_txt"] if d_cmp else "",
                                   "mais": bool(d_cmp and AF.contraire(None, False, d_cmp["txt"], d_cmp["ref_txt"], d_cmp["pos_txt"]))}
            f["n_section"] = {sec: sum(1 for k in ks if k["section"] == sec) for sec, _ in K.SECTIONS}
            limites_papier = sorted({f"{l['lib']}, {l['limite']['court']}." for key in ("sm_pro", "sante_pro", "sm_dist", "sm_recours")
                                     for l in f[key] if l.get("limite") and l["limite"].get("court")})
            # fiche resserrée (validée par Lucas le 31 octobre 2026) : bandes de domaine et « En bref » en matrice, rangés
            # par bandes_fiche à partir de ce qui précède ; effectif attendu des constats de profession ; cartes de bloc
            # d'un département d'outre-mer sur toute la France ; carte des départements d'une région
            extras = {"attendu": {}, "cartes_france": {}, "carte_region": None}
            for k in ks:
                if k["cel"]["kind"] == "prof":
                    a_ = dn.attendu(k["lv"], k["code"], k["id"].split(":")[1])
                    if a_:
                        extras["attendu"][k["id"]] = nombre(round(a_[0]), "entier")
            if F and lv == "dep" and u["c"] in ENCARTS:
                cadre_fr = CP.cadre_autour([F.boite("dep", d) for d in tous_deps if F.boite("dep", d)], .02)
                for k in ks:
                    vals, bo, _g = bornes(k["id"], k["lv"])
                    if bo and F.boite(k["lv"], k["code"]):
                        extras["cartes_france"][k["id"]] = BF.carte_france(
                            F, k["lv"], k["code"], vals, bo, cadre_fr,
                            f"{k.get('nom_ind') or k['id']}, par département, France et départements d'outre-mer, en cinq "
                            f"classes de même effectif")
            if F and lv == "reg":
                deps_r = [d for d in deps_de_reg.get(u["c"], []) if F.boite("dep", d)]
                vals, bo, g_ = bornes("prof:psychologue:all", "dep")
                if deps_r and bo:
                    extras["carte_region"] = BF.carte_region(F, u["c"], deps_r, vals, bo, g_, dn.noms["dep"])
            ctx_b = {"f": f, "constats": ks, "extras": extras, "date_rpps": date_rpps, "venir": venir,
                     "confiance_france": confiance_ensemble(lv), "limite_sae": (lim_sae or {}).get("territoire")}
            bandes_f, bord_f = BF.bandes(ctx_b), BF.tableau_de_bord(ctx_b)
            titre = f"{f['nom']}, offre de soins et santé mentale"
            adr = f"{adresse.replace('https://', '').rstrip('/')}/territoire/{lv}/{u['c']}"
            html = gabarit.render(commun, f=f, racine="../../", titre=titre, page="territoires", classe_main="fiche",
                                  carte_situation=carte, constats=ks, bandes=bandes_f, bord=bord_f, extras=extras,
                                  phares_absents=BF.phares_absents(ks), nb_phares=len(K.CANDIDATS),
                                  formes=F.defs() if F else "",
                                  sections=[s for s in K.SECTIONS if any(k["section"] == s[0] for k in ks)],
                                  description=f"Fiche {f['de_nom']}, professionnels, structures de soins psychiques et profil "
                                              f"des habitants, situés parmi les {f['niv_pluriel']}.",
                                  liens_fiche=liens, comparer=comparer, confiance_france=confiance_ensemble(lv), sources_fiche=sources,
                                  zone=f"../../zone.html#epci={u['c']}" if lv == "epci" else None,
                                  limite_sae=(lim_sae or {}).get("territoire"), venir=venir, limites_papier=limites_papier,
                                  doi_donnees=doi, doi_toutes=doi == config.DOI_DONNEES, terr_id=comp, adresse_fiche=adr, menu_six=True, temps_bornes=TEMPS_BORNES,
                                  src_route=config.SRC_INSEE_ROUTE[0], lim_route=config.LIMITES_COURT.get("route"),
                                  lim_route_cmp=config.LIMITES_COURT.get("route_psychiatrie_ambulatoire"),
                                  doi_general=config.DOI_DONNEES if config.DOI_DONNEES != doi else None,
                                  citation_fiche=f"{citation_auteur} ({dernier.name[:4]}). Fiche {f['de_nom']}. Ubi Cura, "
                                                 f"version du {commun['date_longue']}, {adr}"
                                                 + ((f", toutes les versions doi:{doi}" if doi == config.DOI_DONNEES else f", doi:{doi}") if doi else "") + ".")
            # espaces insécables du français, comme les pages rendues par site.rendre
            (dossier / f"{u['c']}.html").write_text(insecables(html), encoding="utf-8")
            pages.append(dossier / f"{u['c']}.html")
    return pages


def _semblables(dernier: Path) -> dict:
    """Départements de profil semblable, calculés comme dans les rapports départementaux (rapport_territoire.semblables,
    indicateurs de l'INSEE seulement, jamais l'offre de soins), sur contexte_dep.csv."""
    import pandas as pd
    from .rapport_territoire import SEMBLABLES, semblables
    f = dernier / "contexte_dep.csv"
    if not f.exists():
        return {}
    x = pd.read_csv(f, sep=";", decimal=",", dtype={"code": str}, encoding="utf-8-sig")
    if "code" not in x:
        return {}
    x = x.set_index("code")
    cols = [c for c in SEMBLABLES if c in x]
    return semblables(x[cols].apply(pd.to_numeric, errors="coerce")) if cols else {}


def _phrase_attendu(dn, k) -> str:
    """Phrase de l'effectif attendu sous un constat de profession (fiche de l'atlas) : comparaison avec des territoires
    semblables, jamais une mesure du besoin."""
    if k["cel"]["kind"] != "prof":
        return ""
    prof = k["id"].split(":")[1]
    a = dn.attendu(k["lv"], k["code"], prof)
    if not a:
        return ""
    e, n = a
    diff = e - n
    suite = (", l'effectif observé y correspond" if abs(diff) < 1 else
             f", on en compte environ {nombre(round(diff), 'entier')} de moins" if diff > 0 else
             f", on en compte environ {nombre(round(-diff), 'entier')} de plus")
    return (f"Compte tenu du profil de sa population, l'effectif attendu est d'environ {nombre(round(e), 'entier')}{suite}. "
            "C'est une comparaison avec des territoires semblables, pas une mesure du besoin.")


def _date_rpps(dernier: Path) -> str | None:
    """Date de l'extraction du répertoire, lue dans le seul fichier qui date les sources (affichage.date_rpps)."""
    return AF.date_rpps(dernier)
