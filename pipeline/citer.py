"""Page « Citer et réutiliser » de la méthode (maquette prototypes/citer/, validée le 24 novembre 2026).

La page réunit les citations des données, des deux rapports et du site, les identifiants permanents (DOI) de chaque
dépôt, les adresses stables du site, la licence de chaque fichier, la règle des éditions, les versions archivées sur
Zenodo et ce qu'il faut pour réemployer les fichiers. Aucune date d'édition future n'y est annoncée (décision du
24 novembre 2026).

Rien n'y est recopié à la main :
- version citée et DOI, site.doi_cite (donnees/zenodo.json), les mêmes que donnees/site_citation.json ;
- citations des dépôts et du site, site.citation_donnees, site.citation et citation_site, les fonctions qui les
  écrivent ailleurs sur le site ;
- exemple de citation d'une page, fiche_indicateur.citation_page, la fonction des pages d'indicateur ;
- fichiers de l'archive de la version, lus dans l'archive zip elle-même ; fichiers à part, la liste de la page
  Fichiers à télécharger ;
- versions archivées, leurs licences et ce qui les a suivies, le relevé public de Zenodo (lecture seule, sans clé)
  gardé dans donnees/zenodo_versions.json. La construction du site ne lit jamais le réseau : le relevé est refait par
  outils/zenodo.py (étapes constater et annoter, ou commande versions). Sans relevé, la page se construit sans le
  tableau des versions et le note au journal ;
- versions parues sur le site seul, donnees/publication.json face à ce relevé."""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
import zipfile
from pathlib import Path

from . import config
from .util import JOURNAL

PAGE = "methode-citer.html"
CACHE = config.DONNEES / "zenodo_versions.json"
# recherche publique des enregistrements de Zenodo, sans clé : adresse documentée par Zenodo, lue le 24 novembre 2026
# pour la maquette (prototypes/citer/fabriquer.py) sur l'enregistrement 10.5281/zenodo.24458612. Les pages suivantes
# d'une réponse se lisent par le lien « next » que donne l'API elle-même.
API_ZENODO = "https://zenodo.org/api/records"
DEPOTS = {"donnees": "Données agrégées", "sante-mentale": "Rapport national santé mentale",
          "sante": "Rapport national santé"}
# identifiants de licence de Zenodo, noms et pages des licences (les mêmes que sur la page Méthode)
LICENCES = {"odc-odbl": ("ODbL 1.0", "https://opendatacommons.org/licenses/odbl/1-0/"),
            "etalab-2.0": ("Licence Ouverte 2.0", "https://www.etalab.gouv.fr/licence-ouverte-open-licence/")}
NB = " "
N_VISIBLES = 6          # versions archivées visibles, les autres repliées (maquette validée)


def _concepts() -> dict[str, str]:
    return {"donnees": config.DOI_DONNEES, **config.DOI_RAPPORTS}


# ---------------------------------------------------------------- relevé des versions sur Zenodo
def relire_zenodo(timeout: int = 30) -> dict:
    """Relevé public des versions des trois dépôts (lecture seule, sans clé)."""
    out = {"lu_le": dt.datetime.now().isoformat(timespec="seconds"), "depots": {}}
    for cle, doi in _concepts().items():
        concept = doi.rsplit(".", 1)[1]
        url = f"{API_ZENODO}?q=conceptrecid:{concept}&all_versions=true&sort=-version&size=25"
        L = []
        while url:
            req = urllib.request.Request(url, headers={"User-Agent": "lecture-metadonnees"})
            d = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
            for h in d["hits"]["hits"]:
                m = h["metadata"]
                tete = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.get("description", "")))).strip()[:400]
                # licences déclarées : « rights » quand Zenodo en donne plusieurs, sinon « license »
                lic = [r.get("id") for r in (m.get("rights") or []) if r.get("id")] or \
                    [x for x in [(m.get("license") or {}).get("id")] if x]
                L.append({"doi": h["doi"], "date": m["publication_date"], "version": m.get("version"),
                          "licences": lic, "cree": h["created"][:19], "tete": tete})
            suivant = (d.get("links") or {}).get("next")
            url = suivant if suivant and suivant.startswith(API_ZENODO) and len(L) < d["hits"]["total"] else None
        out["depots"][cle] = L
    return out


def enregistrer_historique() -> str:
    """Refait le relevé et ne remplace la copie gardée qu'une fois le relevé validé (versions). Appelé par
    outils/zenodo.py, jamais par la construction du site."""
    frais = relire_zenodo()
    V = versions(frais)                  # lève ValueError si le relevé est incohérent : la copie gardée reste
    CACHE.write_text(json.dumps(frais, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"{len(V)} versions archivées relevées sur Zenodo, la plus récente du {V[0]['iso']}"


def historique() -> dict | None:
    """Relevé gardé, sans lecture du réseau. None s'il manque ou s'il est illisible."""
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def suite_version(tete: str) -> str:
    """Ce qui a suivi une version, lu en tête de sa description sur Zenodo."""
    m = re.match(r"Version remplacée\. Cette version est remplacée par la version du (\d+(?:er)? \w+ \d{4}), qui corrige "
                 r"sa mise en page sans changer ses résultats", tete)
    if m:
        return "mise en page corrigée le " + m.group(1).replace(" ", NB)
    m = re.match(r"Version remplacée\. Cette version est remplacée par la version du (\d+(?:er)? \w+ \d{4})", tete)
    if m:
        return "corrigée le " + m.group(1).replace(" ", NB)
    m = re.match(r"Correction du (\d+(?:er)? \w+ \d{4})\.", tete)
    if m:
        return "corrigée le " + m.group(1).replace(" ", NB)
    if re.match(r"Version corrigée du .*?\. Une version corrigée a été publiée le même jour", tete):
        return "corrigée le même jour"
    m = re.match(r"Précision du (\d+(?:er)? \w+ \d{4})\.", tete)
    if m:
        return "précision ajoutée le " + m.group(1).replace(" ", NB)
    return ""


def renvoie(tete: str) -> bool:
    """La tête de la description renvoie vers la version qui remplace celle-ci."""
    return bool(re.match(r"Version remplacée\. Cette version est remplacée par la version du ", tete)
                or re.search(r"\bUtiliser la version corrigée du ", tete))


def versions(hist: dict) -> list[dict]:
    """Versions archivées, la plus récente en tête. Les trois dépôts sont versés ensemble : à chaque rang, la même date.
    Lève ValueError si le relevé ne le respecte pas."""
    D = {c: sorted(hist["depots"].get(c, []), key=lambda x: (x["date"], x["cree"]), reverse=True) for c in DEPOTS}
    n = {len(v) for v in D.values()}
    if len(n) != 1 or not n or 0 in n:
        raise ValueError(f"nombres de versions différents selon les dépôts : { {c: len(v) for c, v in D.items()} }")
    out = []
    for k in range(n.pop()):
        lig = {c: D[c][k] for c in D}
        dates = {x["date"] for x in lig.values()}
        if len(dates) != 1:
            raise ValueError(f"dates différentes au même rang : {sorted(dates)}")
        tete = lig["donnees"]["tete"]
        out.append({"iso": dates.pop(), "corrigee": "version corrigée" in (lig["donnees"]["version"] or ""),
                    "doi": {c: x["doi"] for c, x in lig.items()}, "suite": suite_version(tete),
                    "renvoi": renvoie(tete),
                    # relevé ancien : une seule licence, sous « licence »
                    "licences": {c: x.get("licences") or ([x["licence"]] if x.get("licence") else [])
                                 for c, x in lig.items()}})
    return out


# ---------------------------------------------------------------- mise en forme
def adresse(href: str, texte: str) -> str:
    """Adresse affichée qui ne se coupe qu'après une barre oblique, jamais à un trait d'union ni à un point."""
    morceaux = texte.split("/")
    morceaux = [x + "/" for x in morceaux[:-1]] + [morceaux[-1]]
    return f'<a class="adr" href="{href}">' + "<wbr>".join(f'<span class="nw">{html.escape(m)}</span>'
                                                         for m in morceaux if m) + "</a>"


def coupures_doi(h: str) -> str:
    """Dans une citation déjà mise en liens, l'adresse d'un DOI ne se coupe qu'après « doi.org/ », et « doi:10.… » ne
    se coupe pas (téléphone)."""
    h = re.sub(r'>https://doi\.org/([^<]+)</a>',
               r'><span class="nw">https://doi.org/</span><wbr><span class="nw">\1</span></a>', h)
    return re.sub(r'doi:(<a href="[^"]+">[^<]+</a>)', r'<span class="nw">doi:\1</span>', h)


def liste_dates(L: list[str], date_longue) -> str:
    """« des 12, 21, 23 et 26 octobre 2026 » pour des dates d'un même mois ; sinon chaque date en entier."""
    if not L:
        return ""
    if len({x[:7] for x in L}) == 1:
        j = [date_longue(x).split(" ")[0] for x in L]
        mois_annee = " ".join(date_longue(L[0]).split(" ")[1:])
        return "des " + (j[0] if len(j) == 1 else ", ".join(j[:-1]) + " et " + j[-1]) + " " + mois_annee
    t = [date_longue(x) for x in L]
    return "du " + (t[0] if len(t) == 1 else ", du ".join(t[:-1]) + " et du " + t[-1])


def noms_licences(ids: list[str]) -> list[dict]:
    return [{"nom": LICENCES.get(i, (i, ""))[0], "url": LICENCES.get(i, ("", ""))[1]} for i in ids]


def contenu_archive(zip_: Path) -> dict:
    """Fichiers CSV de l'archive zip de la version, lus dans l'archive."""
    with zipfile.ZipFile(zip_) as z:
        noms = [Path(n).name for n in z.namelist() if n.endswith(".csv")]
    return {"noms": set(noms), "n": len(noms), "n_odbl": sum("_odbl" in n for n in noms)}


# ---------------------------------------------------------------- contenu de la page
def donnees(site: Path, dernier: Path, fichiers: list[dict], archive: dict, zip_: Path, commun: dict,
            sd: dict) -> dict:
    """Valeurs de la page, pour gabarits/methode.html (vue « citer »)."""
    from . import site as S
    from .atelier import libelle_profession
    from .fiche_indicateur import citation_page, insecable_nombres, titre_indicateur
    iso = config.VERSION_ZENODO
    ed = S.date_longue(iso)
    dois = {c: S.doi_cite(c, iso) for c in DEPOTS}
    hote = re.sub(r"^https?://", "", config.ADRESSE_SITE or "").rstrip("/")

    cits = [("Les données", S.citation_donnees(iso)),
            ("Le rapport santé mentale", S.citation("sante-mentale", "Rapport santé mentale", ed, iso)["texte"]),
            ("Le rapport santé", S.citation("sante", "Rapport santé", ed, iso)["texte"]),
            ("Le site", citation_site())]
    citations = [{"nom": n, "html": coupures_doi(str(S.liens(c)))} for n, c in cits]

    # exemple : la citation de la page d'indicateur des psychiatres, par la fonction des pages d'indicateur
    cit_figure = None
    if any(p["id"] == "psychiatre" for p in sd.get("professions", [])):
        lab, u = libelle_profession(sd, "psychiatre")
        titre = titre_indicateur(insecable_nombres(lab), insecable_nombres(u))
        cit_figure = coupures_doi(str(S.liens(citation_page(commun, titre, S.doi_cite("donnees", dernier.name)))))

    # l'archive de la version, et les fichiers du site qui n'y sont pas (liste des indicateurs d'une version figée)
    A = contenu_archive(zip_)
    a_part = [f for f in fichiers if re.search(r"\.csv(\.zip)?$", f["lien"])
              and re.sub(r"\.zip$", "", f["lien"].rsplit("/", 1)[1]) not in A["noms"]]
    from .etendue import LISTE
    a_part_noms = ["la liste des indicateurs" if f["lien"].endswith(LISTE) else f["nom"] for f in a_part]

    # versions archivées sur Zenodo, d'après le relevé gardé
    V, lu, erreur = [], None, ""
    hist = historique()
    if hist is None:
        erreur = "relevé absent (python outils\\zenodo.py versions), tableau des versions omis"
        JOURNAL.note("Zenodo, versions archivées", "erreur", erreur)
    else:
        lu = hist["lu_le"][:10]
        try:
            V = versions(hist)
        except ValueError as e:
            erreur = f"{e}, tableau des versions omis"
            JOURNAL.note("Zenodo, versions archivées", "erreur", erreur)
    # version citée dont les brouillons sont prêts mais pas encore publiés sur Zenodo : ses DOI réservés en tête
    if V and iso not in {v["iso"] for v in V}:
        V.insert(0, {"iso": iso, "corrigee": False, "doi": dois, "suite": "", "renvoi": False,
                     "licences": V[0]["licences"]})
    premiere_en_ligne = next((v for v in V if v["iso"] == iso), None)
    for v in V:
        v["date"] = S.date_longue(v["iso"])
        v["en_ligne"] = v is premiere_en_ligne
    lic = V[0]["licences"] if V else {}
    lic_rapports = lic.get("sante-mentale") if lic and lic.get("sante-mentale") == lic.get("sante") else None
    pub_f = config.DONNEES / "publication.json"
    pub = json.loads(pub_f.read_text(encoding="utf-8-sig")).get("versions_publiees", []) if pub_f.exists() else []
    seules = sorted(x for x in set(pub) - {v["iso"] for v in V} if x < iso and (site / "rapports" / x).is_dir()) \
        if V else []
    n_rapports = sum(1 for q in (site / "rapports").iterdir() if q.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}$", q.name)) \
        if (site / "rapports").is_dir() else 0
    remplacees = V[1:] if V and V[0]["en_ligne"] else V
    JOURNAL.controle("Citer et réutiliser, versions archivées lues dans le relevé de Zenodo",
                     f"{len(V)} versions, relevé du {lu}" if V else erreur)

    return {
        "page": PAGE, "edition": ed, "iso": iso, "site_iso": dernier.name, "en_ligne": dernier.name == iso,
        "dois": dois, "concepts": [{"cle": c, "nom": n, "general": _concepts()[c], "version": dois[c]}
                                   for c, n in DEPOTS.items()],
        "citations": citations, "cit_figure": cit_figure, "orcid": config.ORCID, "depot_code": S.DEPOT_CODE,
        "n_zip": A["n"], "n_zip_odbl": A["n_odbl"], "a_part": a_part_noms, "n_a_part": len(a_part),
        "taille_zip": archive["taille"], "lien_dictionnaire": f"donnees/{dernier.name}/dictionnaire.html",
        "licence_archive": noms_licences(lic.get("donnees", [])) if lic else [],
        "licence_rapports": noms_licences(lic_rapports) if lic_rapports else [],
        "adresses": {
            "fiche": adresse("territoire/dep/69.html", f"{hote}/territoire/dep/69"),
            "indicateur": adresse("indicateur/prof-psychiatre.html", f"{hote}/indicateur/prof-psychiatre"),
            "rapport": adresse(f"rapports/{dernier.name}/sante-mentale.pdf", f"{hote}/rapports/{dernier.name}/sante-mentale.pdf"),
            "fichiers": adresse("methode-fichiers.html", f"{hote}/methode-fichiers"),
        },
        "n_rapports": n_rapports,
        "versions": V, "recentes": V[:N_VISIBLES], "anciennes": V[N_VISIBLES:], "n_versions": len(V),
        "n_remplacees": len(remplacees), "n_renvoi": sum(1 for v in remplacees if v["renvoi"]),
        "premiere": V[-1]["date"] if V else "", "zenodo_lu": lu,
        "site_seul": liste_dates(seules, S.date_longue),
    }


def citation_site() -> str:
    """Citation du site par sa version archivée et son DOI, jamais par une date de consultation (décision du
    24 novembre 2026) : « Pithon L. (2026). Offre de soins et santé mentale en France, territoire par territoire. Ubi
    Cura, version du 23 novembre 2026, ubicura.fr, doi:10.5281/zenodo.24458612. » Format des citations d'encadré
    (affichage.citation)."""
    from . import affichage as AF
    from . import site as S
    iso = config.VERSION_ZENODO
    return AF.citation(config.CITATION_AUTEUR, config.SOUS_TITRE, None, config.NOM_PROJET, S.date_longue(iso),
                       config.ADRESSE_SITE, S.doi_cite("donnees", iso))
