"""« En bref » d'une fiche de territoire : 8 à 12 constats écrits par règles (plan de reprise de la présentation,
étape 2, idée 1 « le récit du territoire », 30 octobre 2026).

Chaque constat a un titre descriptif, trois phrases chiffrées, une petite carte (pipeline/cartes_presentation.py) et un
lien « Pourquoi on le dit » qui donne le calcul, la source et la limite. Les règles :
- les valeurs, repères, positions, couleurs et statuts viennent de la règle d'affichage (pipeline/affichage.py), rien
  n'est recalculé ici ;
- l'ordre suit les sections d'un diagnostic territorial (offre en santé mentale, offre en santé, accès, recours,
  contexte), puis l'ordre fixe de CANDIDATS, jamais la gravité : il n'y a pas de palmarès ;
- les phrases sont prises dans une liste fermée de modèles (MODELES), dont les verbes sont ceux de VERBES ; un test
  vérifie que tout mot d'un constat vient d'un modèle, d'un nom d'indicateur ou du nom du territoire ;
- aucun autre territoire n'est nommé (le département d'une intercommunalité devient « son département ») ;
- rien n'est dit sur les causes, aucun mot de MOTS_INTERDITS ;
- un écart n'est dit « net » que si la règle d'affichage le colore (hors de 0,8 à 1,25 fois le repère et au-delà du
  hasard) ; un petit effectif ou une absence ne portent aucun écart.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from . import affichage as AF

SECTIONS = [("sm", "Offre en santé mentale"), ("sante", "Offre de soins en santé"), ("acces", "Accès aux structures"),
            ("recours", "Recours aux soins"), ("contexte", "Contexte")]

# (section, indicateur, nom au pluriel, au singulier, genre « m » ou « f ») ; ordre fixe des constats
CANDIDATS = [
    ("sm", "prof:psychologue:all", "psychologues", "psychologue", "m"),
    ("sm", "prof:psychiatre:all", "psychiatres", "psychiatre", "m"),
    ("sm", "lieux_lieu_cmp_adultes", "CMP pour adultes", "CMP pour adultes", "m"),
    ("sm", "prof:q_psychiatrie_enfant:all", "psychiatres qualifiés pour l'enfant", "psychiatre qualifié pour l'enfant", "m"),
    ("sante", "prof:medecin_generaliste:all", "médecins généralistes", "médecin généraliste", "m"),
    ("sante", "prof:infirmier:all", "infirmiers", "infirmier", "m"),
    ("acces", "dist_lieu_cmp_adultes", "CMP pour adultes", "CMP pour adultes", "m"),
    ("acces", "dist_lieu_urgences", "service d'urgences", "service d'urgences", "m"),
    ("recours", "ald_23", None, None, "f"),
    ("contexte", "densite_pop", None, None, "f"),
    ("contexte", "revenu_median", None, None, "m"),
    ("contexte", "taux_pauvrete", None, None, "m"),
]
# article défini des noms d'indicateurs du contexte, pour les phrases « La densité de population ... »
ARTICLE = {"ald_23": "le taux d'", "densite_pop": "la ", "revenu_median": "le ", "taux_pauvrete": "le "}
NOM_COURT = {"ald_23": "affections psychiatriques de longue durée", "densite_pop": "densité de population",
             "revenu_median": "niveau de vie médian", "taux_pauvrete": "taux de pauvreté"}

VERBES = ("compter", "vivre", "être", "se situer", "rester", "dépasser", "sortir", "recenser")
MOTS_INTERDITS = ("cause", "à cause", "en raison", "parce que", "grâce", "faute", "manque", "retard", "mauvais",
                  "pénurie", "désert", "sous-doté", "sur-doté", "insuffisan", "carence", "déficit", "besoin",
                  "favoris", "défavoris", "inquiét", "alarm", "meilleur", "pire", "classement", "rang")

# la liste fermée des phrases ; {…} est remplacé par un nombre, un nom d'indicateur ou le nom du territoire
MODELES = {
    "t_position": "{Nom} : {position}",
    "t_position_net_bas": "{Nom} : {position}, nettement en dessous de l'ensemble",
    "t_position_net_haut": "{Nom} : {position}, nettement au-dessus de l'ensemble",
    "t_petit": "{Nom} : {n} {inscrits}, un petit effectif",
    "t_aucun": "{Nom} : aucun inscrit",
    "t_struct": "{n} {nom}, {confirmation}",
    "t_struct_aucun": "{Nom} : aucune structure inscrite",
    # pas de CMP réservé aux adultes, mais des CMP tous publics (décision de Lucas du 31 octobre 2026, M4b)
    "t_cmp_tous": "Aucun CMP réservé aux adultes, {k} CMP tous publics",
    "cmp_tous_1": "Aucun CMP réservé aux adultes n'est inscrit dans {territoire} ; {territoire} compte {k} CMP tous publics, pour les adultes et les enfants.",
    # bases incomplètes dans le département (limite manque_sae) : « aucune » ne serait pas établi (relecture du 31 octobre
    # 2026, 128 fiches)
    "t_struct_manque": "{Nom} : non publié, les bases ne les recensent pas tous ici",
    "struct_1_manque": "Aucun {nom1} n'est inscrit dans {territoire}, mais les bases n'y recensent pas tous ceux que les établissements déclarent à la statistique annuelle : leur nombre n'est pas publié.",
    "t_dist": "{Nom} : la moitié des habitants à moins de {v} km",
    "t_dist_zero": "{Nom} : dans la commune d'au moins la moitié des habitants",
    "t_ctx": "{Nom} : {position}",
    # écart et position de sens contraire, dits ensemble dans le titre (remarques de Lucas du 31 octobre 2026)
    "t_contraire": "{Nom} : {ecart}, mais {position}",
    "t_contraire_net_bas": "{Nom} : nettement en dessous de l'ensemble, mais {position}",
    "t_contraire_net_haut": "{Nom} : nettement au-dessus de l'ensemble, mais {position}",
    "prof_1": "{Territoire} compte {n} {nom}, soit {v} {unite}.",
    "prof_1_aucun": "Aucun {nom1} n'est inscrit dans {territoire}.",
    "struct_1": "{Territoire} compte {n} {nom}, soit {v} {unite}.",
    "struct_1_np": "{Territoire} compte {n} {nom} ; le taux n'est pas publié pour ce territoire.",
    "struct_1_aucun": "Aucun {nom1} n'est inscrit dans {territoire}.",
    "pos_med": "C'est {position} ; {mediane} est à {med} {unite}.",
    "pos_med_zero": "C'est {position} ; {mediane} n'en compte aucun.",
    "pos_aucun": "C'est le cas de {p} des {niveaux}.",
    "rep_net": "L'ensemble des {niveaux} en compte {ref} : l'écart, de {e}, sort de la marge de 0,8 à 1,25 fois ce repère et dépasse ce que le hasard explique.",
    "rep_proche": "L'ensemble des {niveaux} en compte {ref} : l'écart, de {e}, reste dans la marge de 0,8 à 1,25 fois ce repère.",
    "rep_hasard": "L'ensemble des {niveaux} en compte {ref} : sur {n} {quoi}, l'écart, de {e}, reste dans ce que le hasard peut produire.",
    "rep_petit": "L'ensemble des {niveaux} en compte {ref} ; sur moins de 5 {quoi}, aucun écart n'est calculé.",
    "rep_seul": "L'ensemble des {niveaux} en compte {ref} {unite}.",
    "dist_1": "La moitié des habitants {de_territoire} vit à moins de {v} km d'un {nom1}, à vol d'oiseau.",
    "dist_1_zero": "La moitié des habitants {de_territoire} au moins vit dans une commune qui a un {nom1}.",
    "dist_2": "C'est {position} ; pour {mediane}, cette distance est de {med} km.",
    "dist_3": "Pour l'ensemble des {niveaux}, la moitié des habitants vit à moins de {ref} km.",
    "ctx_1": "Pour {territoire}, {nom} est de {v} {unite}.",
    "ctx_1_dep": "Ce taux n'est publié que par département : pour son département, {nom} est de {v} {unite}.",
    "ctx_2": "C'est {position} ; {mediane} est à {med}.",
    "ctx_3_rep": "L'ensemble des {niveaux} est à {ref}.",
    "ctx_3_quart": "La moitié des {niveaux} se situe entre {q1} et {q3}.",
}


def _maj(s: str) -> str:
    return s[:1].upper() + s[1:]


def _ecrire(cle: str, **v) -> str:
    return MODELES[cle].format(**v)


def _de(terr: str) -> str:
    """« du département », « de la communauté de communes ... », « de l'eurométropole ... »."""
    if terr.startswith("le "):
        return "du " + terr[3:]
    return ("d'" if terr[:1].lower() in "aeiouyéèh" and not terr.startswith(("la ", "l'")) else "de ") + terr


def _sujet(f: dict, lv: str) -> str:
    """Le territoire de la fiche, sujet des phrases : son nom avec l'article pour une intercommunalité (« la
    communauté de communes Vierzon-Sologne-Berry »), « le département » ou « la région » sinon, faute d'article sûr
    pour chaque nom (« l'Ain », « les Hauts-de-Seine »)."""
    return f["nom_article"] if lv == "epci" else {"dep": "le département", "reg": "la région"}[lv]


def _pos_med(c: dict, niveaux: str, lv: str, unite: str) -> str:
    """Position, puis la médiane écrite comme une densité, avec son unité (« est à 7,3 pour 10 000 habitants »), et non
    comme un effectif (troisième relecture, 31 octobre 2026)."""
    return _ecrire("pos_med_zero" if c["med_txt"] == "0" else "pos_med", position=c["pos_txt"],
                   mediane=_article_mediane(lv), med=c["med_txt"], unite=unite)


REPERES_ENSEMBLE = ("somme", "ponderee", "surface")


def _sens(c: dict) -> str | None:
    """Sens contraire de l'écart et de la position, seulement quand le repère est l'ensemble calculé sur le total des
    territoires (somme des effectifs, moyenne pondérée, total rapporté à la surface) : la clé en mots ne vaut pas pour
    un repère qui est une médiane."""
    return AF.sens_contraire(c.get("e"), c.get("pos_txt", "")) if c.get("ref_type") in REPERES_ENSEMBLE else None


def _titre_position(Nom: str, c: dict, modele: str = "t_position") -> str:
    """Titre d'un constat qui situe le territoire. Quand l'écart à l'ensemble et la position vont en sens contraire
    (« 17 % sous l'ensemble » et « plus haut que 71 % »), le titre dit les deux, reliés par « mais », au lieu de n'en
    montrer qu'un et de laisser l'autre le contredire juste dessous."""
    sens = _sens(c)
    if sens:
        cle = {"bas": "t_contraire_net_bas", "haut": "t_contraire_net_haut"}.get(c.get("couleur"), "t_contraire")
        return _ecrire(cle, Nom=Nom, ecart=c["e_mots"], position=c["pos_txt"])
    if modele == "t_position":
        modele = {"bas": "t_position_net_bas", "haut": "t_position_net_haut"}.get(c.get("couleur"), "t_position")
    return _ecrire(modele, Nom=Nom, position=c["pos_txt"])


def _avec_cle(ph: list, c: dict, lv: str) -> list:
    """Ajoute à la dernière phrase la clé en mots quand l'écart et la position vont en sens contraire."""
    cle = AF.cle_contraire(_sens(c), lv)
    if cle and ph:
        ph[-1] = ph[-1] + " " + cle
    return ph


def _article_mediane(lv: str) -> str:
    return {"epci": "l'intercommunalité médiane", "dep": "le département médian", "reg": "la région médiane"}[lv]


def _pc(p) -> str:
    """« 71 % », arrondi comme la position de la règle d'affichage (affichage.position_txt). Une part non nulle qui
    s'arrondirait à 0 s'écrit « moins de 1 % » : « C'est le cas de 0 % des intercommunalités » laissait un 0 trompeur
    (Île-de-Sein, relecture indépendante du 9 novembre 2026)."""
    v = int(Decimal(p * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return f"moins de 1{AF.FINE}%" if v == 0 and p > 0 else f"{v}{AF.FINE}%"


def _confirmation(n: int, conf: dict) -> str:
    c = conf.get("confirmee", 0)
    if n == 1:
        return "confirmé" if c == 1 else "à confirmer"
    if c == n:
        return "tous confirmés"
    return f"{c} confirmé{'s' if c > 1 else ''}" if c else "aucun confirmé"


def limite_retenue(dn, texte: str | None, c: dict) -> bool:
    """Faux pour la limite des structures absentes des bases (« distance et nombre non publiés ») posée sur une valeur
    publiée : elle ne vaut que là où la valeur est retirée, comme sur la ligne du tableau (fiche_territoire.fiche).
    Elle arrivait sous un nombre publié par l'alias des types de structures, au constat comme dans « Pourquoi on le
    dit » (relecture du prototype de fiche resserrée, 31 octobre 2026, M1)."""
    sae = (dn.limite("manque_sae") or {}).get("court")
    if not texte or not sae or texte.rstrip(".") != sae.rstrip("."):
        return True
    return c.get("v") is None or c.get("statut") == "non_publie"


def _manque(dn, lv: str, code: str, dep: str | None, plur: str) -> bool:
    """Vrai quand les bases recensent moins de la moitié des structures de ce type que la SAE dans le territoire ou,
    pour une intercommunalité, dans son département (limite manque_sae, qui nomme les types touchés)."""
    for niv, c in ((lv, code), ("dep", dep)):
        lim = dn.limite("manque_sae", niv, c) if c else None
        if lim and lim.get("territoire") and plur in lim["territoire"]:
            return True
    return False


def _part_zero(dn, ident: str, lv: str) -> float | None:
    S = dn.T.serie(ident, lv)
    if S is None:
        return None
    n = [k for k in S.n if k is not None]
    return sum(1 for k in n if k == 0) / len(n) if n else None


def _repere(c: dict, niveaux: str, unite: str) -> str:
    """Troisième phrase d'un constat d'offre : le repère, puis l'écart selon la règle des couleurs."""
    ref = f"{c['ref_txt']} {unite}"
    quoi = "structures" if c["kind"] == "lieux" else "inscrits"
    if c["statut"] == "petit":
        return _ecrire("rep_petit", niveaux=niveaux, ref=ref, quoi=quoi)
    if c["e"] is None:
        return _ecrire("rep_seul", niveaux=niveaux, ref=c["ref_txt"], unite=unite)
    if c["couleur"]:
        return _ecrire("rep_net", niveaux=niveaux, ref=ref, e=c["e_txt"])
    rapport = c["v"] / c["ref"] if c["ref"] else 1   # valeurs pleines, comme la couleur et l'écart
    if AF.PROCHE[0] <= rapport <= AF.PROCHE[1]:
        return _ecrire("rep_proche", niveaux=niveaux, ref=ref, e=c["e_txt"])
    return _ecrire("rep_hasard", niveaux=niveaux, ref=ref, e=c["e_txt"], n=c["n_txt"], quoi=quoi)


def constats(dn, f: dict, lv: str, code: str, dep: str | None) -> list[dict]:
    """Constats de la fiche du territoire (lv, code), dans l'ordre des sections. Chaque constat porte l'indicateur et le
    niveau de sa carte, sa cellule (pour la réglette) et ce que dit « Pourquoi on le dit »."""
    niveaux = AF.NIV_PLURIEL[lv]
    terr = _sujet(f, lv)
    sortie = []
    structures = {s["id"]: s for s in f.get("structures", [])}
    for section, ident, plur, sing, _genre in CANDIDATS:
        lv_c, code_c, echelle = lv, code, None
        if ident.startswith("prof:"):
            c = dn.T.cellule(ident, lv, code)
            if c is None:
                continue
            unite = AF.txt_unite(c["fac"])
            Nom = _maj(plur)
            if c["statut"] == "aucun":
                titre = _ecrire("t_aucun", Nom=Nom)
                p0 = _part_zero(dn, ident, lv)
                ph = [_ecrire("prof_1_aucun", nom1=sing, territoire=terr)]
                if p0 is not None:
                    ph.append(_ecrire("pos_aucun", p=_pc(p0), niveaux=niveaux))
                ph.append(_ecrire("rep_seul", niveaux=niveaux, ref=c["ref_txt"], unite=unite))
            else:
                if c["statut"] == "petit":
                    titre = _ecrire("t_petit", Nom=Nom, n=c["n_txt"], inscrits="inscrit" if c["n"] == 1 else "inscrits")
                else:
                    titre = _titre_position(Nom, c)
                ph = [_ecrire("prof_1", Territoire=_maj(terr), n=c["n_txt"], nom=plur if c["n"] != 1 else sing,
                              v=c["v_txt"], unite=unite),
                      _pos_med(c, niveaux, lv, unite), _repere(c, niveaux, unite)]
                if c["statut"] != "petit":
                    ph = _avec_cle(ph, c, lv)
        elif ident.startswith("lieux_"):
            c = dn.T.cellule(ident, lv, code)
            s = structures.get(ident)
            if c is None or s is None or c["statut"] in ("non_recense",):
                continue
            n = s["n"] or 0
            unite = s["unite"] or "pour 100 000 habitants"
            if n == 0 and _manque(dn, lv, code, dep, plur):
                titre = _ecrire("t_struct_manque", Nom=_maj(plur))
                ph = [_ecrire("struct_1_manque", nom1=sing, territoire=terr)]
            elif n == 0 and ident == "lieux_lieu_cmp_adultes" and (structures.get("lieux_lieu_cmp") or {}).get("n"):
                k_tous = structures["lieux_lieu_cmp"]["n"]
                titre = _ecrire("t_cmp_tous", k=k_tous)
                ph = [_ecrire("cmp_tous_1", territoire=terr, k=k_tous)]
            elif n == 0:
                titre = _ecrire("t_struct_aucun", Nom=_maj(plur))
                ph = [_ecrire("struct_1_aucun", nom1=sing, territoire=terr)]
                p0 = _part_zero(dn, ident, lv)
                if p0 is not None:
                    ph.append(_ecrire("pos_aucun", p=_pc(p0), niveaux=niveaux))
                ph.append(_ecrire("rep_seul", niveaux=niveaux, ref=c["ref_txt"], unite=unite))
            else:
                titre = _ecrire("t_struct", n=n, nom=plur, confirmation=_confirmation(n, s["conf"]))
                if c["v"] is None:
                    ph = [_ecrire("struct_1_np", Territoire=_maj(terr), n=n, nom=plur)]
                else:
                    ph = [_ecrire("struct_1", Territoire=_maj(terr), n=n, nom=plur, v=c["v_txt"], unite=unite),
                          _pos_med(c, niveaux, lv, unite)]
                ph.append(_repere(c, niveaux, unite))
                if c["v"] is not None and c["statut"] != "petit":
                    ph = _avec_cle(ph, c, lv)
        elif ident.startswith("dist_"):
            c = dn.T.cellule(ident, lv, code)
            if c is None or c["v"] is None or c["statut"]:
                continue
            Nom = _maj(plur)
            if c["va"] == 0:
                titre = _ecrire("t_dist_zero", Nom=Nom)
                ph = [_ecrire("dist_1_zero", de_territoire=_de(terr), nom1=sing)]
            else:
                titre = _ecrire("t_dist", Nom=Nom, v=c["v_txt"])
                ph = [_ecrire("dist_1", de_territoire=_de(terr), v=c["v_txt"], nom1=sing)]
            ph += [_ecrire("dist_2", position=c["pos_txt"], mediane=_article_mediane(lv), med=c["med_txt"]),
                   _ecrire("dist_3", niveaux=niveaux, ref=c["ref_txt"])]
        else:
            ctx = dn.ctx.get(ident)
            if ctx is None:
                continue
            c = dn.T.cellule(ident, lv, code)
            if (c is None or c["v"] is None) and lv == "epci" and dep in dn.pos["dep"]:
                lv_c, code_c, echelle = "dep", dep, "dep"
                c = dn.T.cellule(ident, "dep", dep, "dep")
            if c is None or c["v"] is None:
                continue
            niv_c = AF.NIV_PLURIEL[lv_c]
            unite = (ctx[1].get("unite") or "").replace(" hab.", " habitants").replace("hab./km²", "habitants par km²")
            unite = re.sub(r"pour 100 000\s*\(standardisé\)", "pour 100 000 habitants, à âge égal", unite)
            nom = ARTICLE.get(ident, "") + NOM_COURT.get(ident, (ctx[1].get("label") or ident).lower())
            v_unite = unite if unite not in ("%", "€") else ""
            v = c["v_txt"] + (" " + unite if unite in ("%", "€") else "")
            Nom_ctx = _maj(NOM_COURT.get(ident, ctx[1].get("label") or ident))
            titre = _titre_position(Nom_ctx, c, "t_ctx")
            ph = [_ecrire("ctx_1_dep" if echelle else "ctx_1", territoire=terr, nom=nom, v=v, unite=v_unite).replace("  ", " ").replace(" .", ".")]
            sep = " " if unite in ("%", "€") else " "
            med = c["med_txt"] + sep + unite
            ph.append(_ecrire("ctx_2", position=c["pos_txt"], mediane=_article_mediane(lv_c), med=med))
            if c["ref_type"] == "mediane_territoires":
                e = dn.T.echelle(ident, lv_c)
                if e:
                    q1 = AF.nombre(e["q1"], c["genre"]) + (sep + unite if unite in ("%", "€") else "")
                    ph.append(_ecrire("ctx_3_quart", niveaux=niv_c, q1=q1, q3=AF.nombre(e["q3"], c["genre"]) + sep + unite))
            else:
                ph.append(_ecrire("ctx_3_rep", niveaux=niv_c, ref=c["ref_txt"] + sep + unite))
                ph = _avec_cle(ph, c, lv_c)
        lim = dn.limite(ident if not ident.startswith("prof:") else "prof:" + ident.split(":")[1], lv_c, code_c)
        if lim and not limite_retenue(dn, lim.get("court"), c):
            lim = None
        nom_carte = _maj(plur) if plur else _maj(NOM_COURT.get(ident, ident))
        if ident.startswith("prof:"):
            nom_carte += ", " + AF.txt_unite(c["fac"])
        sortie.append({"section": section, "id": ident, "lv": lv_c, "code": code_c, "echelle": echelle, "titre": titre, "nom": nom_carte,
                       "phrases": ph, "cel": c, "limite": (lim or {}).get("court"), "ancre": "k-" + re.sub(r"[^a-z0-9]+", "-", ident.lower()).strip("-")})
    noms = dict(SECTIONS)
    for k in sortie:
        k["section_nom"] = noms[k["section"]]
    return sortie


def interdits(texte: str) -> list[str]:
    """Mots interdits présents dans un texte de constat (contrôle de la construction et test)."""
    t = texte.lower()
    return [m for m in MOTS_INTERDITS if re.search(r"(?<![a-zà-ÿ])" + re.escape(m), t)]
