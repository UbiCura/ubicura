"""Espaces insécables du français dans les pages du site (direction visuelle du 30 octobre 2026).

Un guillemet ne reste jamais seul en bout de ligne, un nombre ne se sépare pas de son unité ni de son signe :
- espace insécable après « et avant » ;
- espace fine insécable devant ; ! ? et devant : (deux-points) ;
- espace insécable entre un nombre et %, €, km, px, h, min, ans, pour, ‰, et entre un nombre et le mot court qui le
  suit (« 29 octobre », « 11 versions »), puis entre le mois et l'année (relecture de la planche, 30 octobre 2026) ;
- espace fine insécable entre les groupes de trois chiffres d'un nombre écrit avec des espaces (81 185).
Seul le texte lu est touché : jamais l'intérieur des balises, ni les blocs script, style, pre, code et textarea.
"""
import re

INSECABLE = " "
FINE = " "
_PROTEGES = re.compile(r"(<(script|style|pre|code|textarea)\b.*?</\2\s*>|<[^>]+>)", re.S | re.I)
_REGLES = [
    (re.compile(r"«[   ]+"), "«" + INSECABLE),
    (re.compile(r"[   ]+»"), INSECABLE + "»"),
    (re.compile(r"(?<=\S) +(?=[;!?](?:\s|$|<|&))"), FINE),
    (re.compile(r"(?<=[\w\)»%]) +(?=:(?:\s|$))"), FINE),
    (re.compile(r"(?<=\d) +(?=(?:%|‰|€|km|px|h|min|ans?|pour)\b|%|‰|€)"), INSECABLE),
    (re.compile(r"(?<=\d) (?=\d{3}\b)"), FINE),
    # un nombre ne finit jamais une ligne : il reste avec le nom court qui le suit (« 29 octobre », « 11 versions »),
    # huit lettres au plus, pour que le texte justifié du téléphone ne creuse pas de blancs (« 10 000 habitants »)
    (re.compile(r"(?<=\d) (?=[a-zàâçéèêëîïôûùüÿœæ]{1,8}\b)"), INSECABLE),
    # le mois reste avec son année (« octobre 2026 »), comme tout mot avec l'année qui le suit
    (re.compile(r"(?<=[a-zéû]) (?=(?:19|20)\d\d\b)"), INSECABLE),
    # pas d'espace devant une virgule ou un point (« mars 2023 , Annuaire santé », 7 novembre 2026)
    (re.compile(r"(?<=[\w)»]) +(?=[,.](?:\s|$))"), ""),
    # un nom de fichier long peut passer à la ligne après un trait bas (« lieux_soins_dep.csv » laissait une ligne
    # justifiée vingt fois trop espacée) ; <wbr> ne se copie pas avec le nom
    (re.compile(r"(?<=[a-z0-9])_(?=[a-z0-9][\w.]{3,})"), "_<wbr>"),
]


def texte(t: str) -> str:
    for motif, rempl in _REGLES:
        t = motif.sub(rempl, t)
    return t


def insecables(html: str) -> str:
    """Pose les espaces insécables dans le texte d'une page HTML, sans toucher aux balises ni aux scripts."""
    morceaux = _PROTEGES.split(html)
    sortie, i = [], 0
    while i < len(morceaux):
        m = morceaux[i]
        if i % 3 == 0:
            t = texte(m)
            # pas d'espace devant une virgule qui suit un lien ou une balise fermante (« (data.gouv) , FINESS »)
            if sortie and sortie[-1].startswith("</"):
                t = re.sub(r"^ +(?=[,.](?:\s|$))", "", t)
            sortie.append(t)
            i += 1
        else:
            sortie.append(m)   # balise ou bloc protégé, puis le nom capturé du bloc, sauté
            i += 2
    return "".join(sortie)
