"""Libellés d'affichage respectueux des personnes.

Les nomenclatures officielles (FINESS, secteurs RPPS, Assurance Maladie) contiennent des formulations
datées ou stigmatisantes. Les données brutes et intermédiaires gardent le libellé d'origine, pour la
traçabilité et les appariements. Tout ce qu'un lecteur voit passe par la table libelles.csv, validée
par Lucas, qui associe chaque libellé d'origine à un libellé d'affichage. Les sigles d'usage
(EHPAD, IME, CMP...) restent toujours visibles pour que les structures soient identifiables."""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from .util import norm

TABLE = Path(__file__).with_name("libelles.csv")

# Termes à proscrire dans tout ce qu'un lecteur voit. Motifs appliqués au texte normalisé
# (minuscules, sans accents, ponctuation réduite à des espaces).
TERMES_PROSCRITS = [
    (r"\bhandicape(e)?s?\b", "handicapé(e)s, préférer « personnes en situation de handicap »"),
    (r"\bpolyhandicape(e)?s\b", "polyhandicapé(e)s, préférer « en situation de polyhandicap »"),
    (r"\bmalad(es|ies) mentales?\b|\bmalades? mentaux\b", "malades mentaux, maladies mentales"),
    (r"\bdeficients?\b|\bdeficientes?\b", "déficient(s), préférer une formulation centrée sur la personne"),
    (r"\bdeficience mentale\b", "déficience mentale, préférer « déficience intellectuelle »"),
    (r"\btoxicomanes?\b", "toxicomane(s), préférer « personnes ayant une addiction »"),
    (r"\balcooliques\b", "alcooliques, préférer « personnes ayant une addiction à l'alcool »"),
    # diagnostic employé comme nom (« les dépressifs »), l'adjectif (« épisodes dépressifs ») reste permis
    (r"\b(les|des|aux|ces) (schizophrenes|depressifs|bipolaires|psychotiques|autistes|anorexiques)\b",
     "diagnostic substantivé, préférer « personnes vivant avec... »"),
    (r"\binadapte(e)?s?\b", "inadapté(e)s"),
    (r"\bgrabataires?\b", "grabataire(s)"),
    (r"\bagees dependantes\b", "personnes âgées dépendantes, préférer « en perte d'autonomie »"),
    (r"\bdebiles?\b|\barrieres? mentaux\b|\balienes\b|\binfirmes\b", "terme péjoratif ou daté"),
]
# Vocabulaire à éviter sur le site et dans les rapports (consigne de Lucas du 4 octobre 2026), pour ne pas
# présenter les contenus comme « automatiques » ou « générés ». Vérifié avec les termes à proscrire.
VOCABULAIRE_A_EVITER = [
    (r"\bautomatique(s|ment)?\b", "vocabulaire « automatique » à éviter sur le site"),
    (r"\bgenere(e|s|es)? automatiquement\b|\bproduit automatiquement\b", "vocabulaire « généré » à éviter sur le site"),
    # consigne du 4 octobre 2026, ne pas mettre en avant l'outil qui télécharge ou calcule
    (r"\b(le|du|par le|au) programme\b", "« le programme » mis en avant, préférer une formulation centrée sur les données"),
    # remarque de Lucas du 28 octobre 2026, l'écart à l'effectif attendu n'est ni un manque ni un écart à une norme
    (r"\bil en manque\b|\bmanquent environ\b", "écart à l'effectif attendu présenté comme un manque, le décrire (« environ N de moins »)"),
    # règle 13, aucun territoire désigné comme mauvais élève (séance principale, 28 octobre 2026)
    (r"\bmal dote(e|s|es)?\b", "« mal doté » désigne un mauvais élève, préférer « peu doté » ou « moins doté »"),
    (r"\b(dans|hors de) la norme\b", "« la norme » pour un écart à l’ensemble des territoires, préférer « proche de l’ensemble » ou les limites à 95 %"),
    # tournures de présentation qui vantent le site au lieu de décrire (remarque de Lucas du 5 novembre 2026, « Le cœur
    # du site » ne fait pas professionnel)
    (r"\bc(oe| )ur du site\b|\bpierre angulaire\b|\bincontournable\b", "tournure qui vante le site, décrire ce que la page montre"),
    # rien de l'offre payante sur le site avant qu'elle soit finalisée et validée, charte du gratuit comprise ; on peut
    # préparer la place, sans aucun texte qui en parle (Lucas, 28 et 31 octobre 2026)
    (r"\boffre (payante|professionnelle)\b|\bacces (pro|professionnel)\b|\bversion (complete|professionnelle|reelle)\b"
     r"|\bservices? payants?\b|\bapi payante\b|\babonnements?\b|\bcharte du gratuit\b|\bce qui restera gratuit\b"
     r"|\brestera(ont)? (toujours )?gratuit", "allusion à l'offre payante, interdite sur le site avant sa validation"),
]

# Noms propres d'institutions conservés tels quels (validé par Lucas pour la MDPH).
EXCEPTIONS = [r"maisons? dep(artementales?)? (des )?personnes handicapees",   # forme abrégée du RPPS comprise (« GIP MAISON DEP PERSONNES HANDICAPEES »)
              # raison sociale gardée telle quelle, nom propre de l'établissement de Clermont-Ferrand (Lucas, 6 novembre 2026)
              r"centre (de )?reeducation (pour )?deficients visuels",
              # nom propre du programme de prévention du suicide, cité dans la page méthode avec sa source
              r"programme papageno"]


@lru_cache(maxsize=1)
def table() -> list[dict]:
    with open(TABLE, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


@lru_cache(maxsize=1)
def _index() -> dict:
    out = {}
    for r in table():
        out[(r["source"], r["code"])] = r["libelle_affichage"]
        out[("*", norm(r["libelle_origine"]))] = r["libelle_affichage"]
    return out


def affichage(libelle: str, source: str = "", code: str = "") -> str:
    """Libellé d'affichage. Cherche d'abord par source et code, puis par libellé d'origine
    (comparaison normalisée). Un libellé absent de la table est renvoyé tel quel."""
    if libelle is None:
        return libelle
    i = _index()
    if source and code and (source, str(code)) in i:
        return i[(source, str(code))]
    return i.get(("*", norm(libelle)), libelle)


# casse de titre des raisons sociales du FINESS, écrites en capitales (relecture esthétique du 31 octobre 2026)
SIGLES = {"CH", "CHU", "CHS", "CHR", "CHM", "EPSM", "CMP", "CMPP", "CATTP", "CSAPA", "CAARUD", "CAMSP", "EHPAD", "IME",
          "ITEP", "DITEP", "SESSAD", "MAS", "FAM", "ESAT", "PMI", "GCS", "SMUR", "IRSA", "UC", "UGECAM", "HAD", "SSR",
          "USLD", "ARS", "MS", "COREDAF", "GEDHIF", "CMS", "CSE", "SAMU", "MDPH", "ESMS", "CRP", "CHI"}
PETITS_MOTS = {"de", "du", "des", "la", "le", "les", "et", "à", "en", "sur", "sous", "aux", "au", "d", "l"}
ACCENTS = {"sante": "santé", "medical": "médical", "medicale": "médicale", "medico": "médico", "itinerant": "itinérant",
           "departemental": "départemental", "departementaux": "départementaux", "departementale": "départementale",
           "education": "éducation", "academie": "académie", "prevention": "prévention", "therapeutique": "thérapeutique",
           "residences": "résidences", "residence": "résidence", "rene": "rené", "etablissement": "établissement",
           "hopital": "hôpital", "pediatrique": "pédiatrique", "geriatrique": "gériatrique", "specialise": "spécialisé",
           "coeur": "cœur", "societe": "société", "medecine": "médecine", "reeducation": "rééducation", "a": "à",
           "indifferenciee": "indifférenciée", "indifferencie": "indifférencié"}


def casse_titre(nom: str) -> str:
    """« CH GEORGE SAND BOURGES » devient « CH George Sand Bourges », « C. M. P. P. LES ANOLIS » devient « CMPP les
    Anolis » : sigles gardés (SIGLES, et sigles à points), petits mots en minuscules, accents des mots courants
    rétablis (ACCENTS). Dans un nom qui n'est pas tout en capitales, seuls les mots de quatre lettres ou plus écrits en
    capitales, hors sigles, passent en casse de titre (« Psychiatrie INDIFFERENCIEE », relecture v2 du 1er novembre)."""
    if not nom:
        return nom
    if nom != nom.upper():
        def un(m):
            w = m.group(0)
            if w in SIGLES:
                return w
            b = ACCENTS.get(w.lower(), w.lower())
            return b if b in PETITS_MOTS else b[:1].upper() + b[1:]
        return re.sub(r"\b[A-ZÀ-ÖØ-Ý]{4,}\b", un, nom)
    t = re.sub(r"\s+", " ", nom).strip()
    # sigles à points : « C. M. P. P. » ou « C.A.M.S.P. » deviennent « CMPP », « CAMSP »
    t = re.sub(r"\b(?:[A-Z]\.\s?){2,}", lambda m: m.group(0).replace(".", "").replace(" ", "") + " ", t).strip()
    t = re.sub(r"\s+", " ", t)

    def mot(m, premier):
        w = m.group(0)
        if len(w) == 1 and t[m.end():m.end() + 1] in ("'", "’"):    # l', d' : article élidé
            return w if premier else w.lower()
        if w in SIGLES or (len(w) <= 3 and not re.search(r"[AEIOUYÉÈ]", w)):
            return w
        b = w.lower()
        b = ACCENTS.get(b, b)
        if b in PETITS_MOTS and not premier:
            return b
        return b[:1].upper() + b[1:]
    sortie, premier = [], True
    for m in re.finditer(r"[A-ZÀ-ÖØ-Ý0-9]+|[^A-ZÀ-ÖØ-Ý0-9]+", t):
        if re.match(r"[A-ZÀ-ÖØ-Ý0-9]", m.group(0)):
            sortie.append(mot(m, premier))
            premier = False
        else:
            sortie.append(m.group(0))
    return "".join(sortie)


def termes_proscrits(texte: str) -> list[str]:
    """Liste des termes à proscrire présents dans un texte (vide si le texte est conforme)."""
    t = norm(re.sub(r"https?://\S+", " ", texte))   # les adresses web ne sont pas du texte lu
    for e in EXCEPTIONS:
        t = re.sub(e, " ", t)
    trouves = []
    for motif, explication in TERMES_PROSCRITS + VOCABULAIRE_A_EVITER:
        for m in re.finditer(motif, t):
            debut = max(m.start() - 40, 0)
            trouves.append(f"{explication} … {t[debut:m.end() + 40].strip()} …")
    return trouves
