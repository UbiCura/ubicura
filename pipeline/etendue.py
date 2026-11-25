"""Page « Étendue des données » et liste des indicateurs en CSV (portes d'entrée, étape 6, approuvée le 14 novembre 2026,
maquette prototypes/entrees/p4_p6/). La page dit ce que couvre le site : les indicateurs par domaine et par niveau, les
sources et leurs versions, la profondeur dans le temps, les contrôles de concordance et les données annoncées.

Rien n'y est recopié à la main. Les indicateurs viennent du catalogue publié (presentation/catalogue.json, écrit par
page_indicateurs depuis le catalogue unique), leur unité et leur limite courte d'affichage.catalogue, les sources des
fiches de la page Sources (site.donnees_sources) et de config.SOURCES_INFO (rythme de publication), la concordance des
fichiers concordance_* de la version, la profondeur dans le temps d'evolution_offre.csv, les contrôles du journal de la
version et les données annoncées de contenus/a_venir.md."""
from __future__ import annotations

import csv
import io
import json
import math
import re
from collections import Counter
from pathlib import Path

from . import affichage as AF
from . import config
from . import domaines as D
from . import themes as TH

PAGE = "methode-etendue.html"
LISTE = "liste_indicateurs.csv"
NIVEAUX = ("France", "région", "département", "intercommunalité")
COLONNES = ("identifiant", "nom", "unite", "domaine", "themes", "niveaux", "annees", "source", "licence", "limite",
            "adresse")
SANTE_MENTALE = "Santé mentale"
NOM_NIVEAU_EVO = {"FR": "la France", "reg": "les régions", "dep": "les départements", "epci": "les intercommunalités"}


def catalogue(site: Path, sd: dict, dernier: Path) -> list[dict] | None:
    """Les indicateurs du catalogue publié (ceux qui ont leur page, dans l'ordre de la page Indicateurs), avec l'unité et
    la limite courte du catalogue unique. None si la page Indicateurs n'a pas encore été construite."""
    f = site / "presentation" / "catalogue.json"
    if not f.exists():
        return None
    C = json.loads(f.read_text(encoding="utf-8"))
    unique = {TH.cle(e["id"]): e for e in AF.catalogue(sd, dernier)}
    for e in C:
        u = unique.get(e["id"]) or {}
        e["unite"] = u.get("unite") or ""
        e["limite"] = u.get("limite") or ""
    return C


def liste_csv(C: list[dict]) -> str:
    """Une ligne par indicateur, point-virgule, UTF-8 avec BOM, comme les autres fichiers du site."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    w.writerow(COLONNES)
    adresse = config.ADRESSE_SITE.rstrip("/")
    for e in C:
        w.writerow([e["id"], e["nom"], e["unite"], e["domaine"], ", ".join(e["themes"]), ", ".join(e["niveaux"]),
                    e["date"], e["source_longue"], e["licence"], e["limite"], f"{adresse}/{e['page']}"])
    return "﻿" + out.getvalue()


def ecrire_liste(C: list[dict], ddir: Path) -> Path:
    cible = ddir / LISTE
    cible.write_text(liste_csv(C), encoding="utf-8", newline="")
    return cible


# ---------------------------------------------------------------- nombres en français
def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}".replace(".", ",") + " %"


def plancher(x: float, d: int) -> str:
    """Arrondi par défaut : « au moins 0,96 » reste vrai quand le plus petit coefficient vaut 0,9681."""
    return f"{math.floor(x * 10 ** d) / 10 ** d:.{d}f}".replace(".", ",")


def mediane(L: list[float]) -> float:
    L = sorted(L)
    n = len(L)
    return L[n // 2] if n % 2 else (L[n // 2 - 1] + L[n // 2]) / 2


def _lire(f: Path) -> list[dict]:
    if not f.exists():
        return []
    with open(f, encoding="utf-8-sig") as h:
        return list(csv.DictReader(h, delimiter=";"))


def _num(v: str) -> float | None:
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


# ---------------------------------------------------------------- les parties de la page
def infos(fiche: dict) -> list[tuple]:
    """Entrées de config.SOURCES_INFO des sources lues du jeu, dans l'ordre, sans doublon."""
    out = []
    for n in [x["source"] for x in fiche.get("lu", [])]:
        info = next((i for i in config.SOURCES_INFO if re.search(i[0], n)), None)
        if info and info not in out:
            out.append(info)
    if not out:   # un jeu lu sans ligne au journal des sources (données carroyées) : son motif dans SOURCES_INFO
        motif = next((m for _f, nom, _p, m, _u in config.SOURCES_SUIVIES if nom == fiche["nom"]), None)
        out = [i for i in config.SOURCES_INFO if i[0] == motif][:1]
    return out


def rythme(fiche: dict) -> str:
    """Rythme de publication annoncé par le producteur (config.SOURCES_INFO), d'après les sources lues du jeu."""
    vus = list(dict.fromkeys(i[4] for i in infos(fiche)))
    return ", ".join(vus) if vus else config.NON_INDIQUE


def versions_texte(fiche: dict) -> str:
    """Les versions constatées, écrites comme sur la page Sources des données."""
    if fiche["versions"]:
        return "nouvelle version repérée le " + ", le ".join(fiche["versions"])
    return "aucun changement depuis le début du suivi" + (f", le {fiche['suivi_depuis']}" if fiche.get("suivi_depuis") else "")


def domaines(C: list[dict]) -> dict:
    doms = list(dict.fromkeys(e["domaine"] for e in C))
    lignes = []
    for d in doms:
        E = [e for e in C if e["domaine"] == d]
        lignes.append({"nom": d, "n": len(E), "niveaux": [sum(1 for e in E if n in e["niveaux"]) for n in NIVEAUX],
                       "sm": sum(1 for e in E if SANTE_MENTALE in e["themes"])})
    total = {"nom": "Ensemble", "n": len(C), "niveaux": [sum(1 for e in C if n in e["niveaux"]) for n in NIVEAUX],
             "sm": sum(1 for e in C if SANTE_MENTALE in e["themes"])}
    vides = [d["nom"] for d in D.DOMAINES if d["nom"] not in doms]
    return {"lignes": lignes, "total": total, "vides": ", ".join(v if i == 0 else v[0].lower() + v[1:]
                                                                  for i, v in enumerate(vides))}


def licences(C: list[dict]) -> str:
    L = [f"{n} sous {re.sub(r' [(].*$', '', l)}" for l, n in Counter(e["licence"] for e in C).most_common()]
    return L[0] if len(L) == 1 else ", ".join(L[:-1]) + " et " + L[-1]


def millesimes(C: list[dict]) -> list[dict]:
    """Nombre d'indicateurs par millésime des données, du plus récent au plus ancien."""
    par_date: dict[str, list[str]] = {}
    for e in C:
        par_date.setdefault(e["date"], [])
        if e["source"] not in par_date[e["date"]]:
            par_date[e["date"]].append(e["source"])
    n = Counter(e["date"] for e in C)

    def lib(d):
        src = " et ".join(par_date[d])
        if re.match(r"^\d{4} à \d{4}$", d):
            return f"{d}, série annuelle ({src})"
        if re.match(r"^\d{1,2}(er)? \w+ \d{4}$", d):
            return f"{src} du {d}"
        return d
    cle = lambda d: (-int(re.findall(r"\d{4}", d)[-1]) if re.findall(r"\d{4}", d) else 0, d)  # noqa: E731
    return [{"libelle": lib(d), "n": n[d]} for d in sorted(n, key=cle)]


def profondeur(C: list[dict], dernier: Path, fiches_sources: list[dict]) -> dict:
    evo = _lire(dernier / "evolution_offre.csv")
    annees = sorted({int(r["annee"]) for r in evo})
    niv = [NOM_NIVEAU_EVO[n] for n in NOM_NIVEAU_EVO if any(r["niveau"] == n for r in evo)]
    serie = [e for e in C if re.match(r"^\d{4} à \d{4}$", e["date"])]
    periodes = sorted({e["date"] for e in serie})
    sources_serie = list(dict.fromkeys(e["source_longue"] for e in serie))
    # les séries annuelles du catalogue : patientèles et médecins traitants de l'Assurance Maladie, nommées ainsi
    # seulement si c'est bien leur objet
    patient = all(e["nom"].startswith("Patient") for e in serie)
    rpps = next((f for f in fiches_sources if f["nom"].startswith("Répertoire RPPS")), None)
    debuts = sorted({annees[0]} | {int(p[:4]) for p in periodes}) if annees else []
    return {"annees": annees, "n_prof": len({r["prof"] for r in evo}), "niveaux": niv,
            "n_serie": len(serie), "periode": periodes[0] if len(periodes) == 1 else ", ".join(periodes),
            "source_serie": " ; ".join(re.sub(r"\s*\([^)]*\)", "", s.split(",")[0]).strip() for s in sources_serie),
            "patient": patient, "debuts": debuts,
            "rpps_versions": rpps["versions"] if rpps else []}


def concordance(dernier: Path) -> dict | None:
    eff = _lire(dernier / "concordance_effectifs.csv")
    if not eff:
        return None
    dep = _lire(dernier / "concordance_effectifs_dep.csv")
    cmp_ = [r for r in _lire(dernier / "concordance_cmp_sae.csv") if r.get("niveau") == "dep" and r.get("ecart_relatif")]
    ecarts = [abs(_num(r["ecart"])) for r in eff if r["ecart"]]
    # l'écart à la tendance n'a de sens, et n'est montré sur la page Contrôles, que pour les professions que la DREES
    # compte aussi à partir du RPPS (site._concordance)
    rpps = [r for r in eff if "rpps" in r["fichier_drees"].lower() and r["ecart_a_l_attendu"]]
    rangs = [_num(r["rang_spearman"]) for r in dep if r["rang_spearman"]]
    ec_cmp = [abs(_num(r["ecart_relatif"])) for r in cmp_]
    return {"n_prof": len(ecarts), "ecart_med": pct(mediane(ecarts)), "n_sous_5": sum(1 for x in ecarts if x < 0.05),
            "n_rpps": len(rpps), "tend_med": pct(mediane([abs(_num(r["ecart_a_l_attendu"])) for r in rpps])) if rpps else "",
            "rang_min": plancher(min(rangs), 2) if rangs else "", "rang_med": f"{mediane(rangs):.3f}".replace(".", ",") if rangs else "",
            "n_dep_cmp": len(ec_cmp), "cmp_med": pct(mediane(ec_cmp)) if ec_cmp else "",
            "cmp_egal": sum(1 for x in ec_cmp if x == 0)}


def a_venir(fichier: Path) -> list[str]:
    """Les titres de la partie « Données » de contenus/a_venir.md."""
    if not fichier.exists():
        return []
    t = fichier.read_text(encoding="utf-8")
    m = re.search(r"^## Données\s*$(.*?)(?=^## |\Z)", t, flags=re.S | re.M)
    return [x.strip().rstrip(".") for x in re.findall(r"^\*\*(.+?)\*\*", m.group(1), flags=re.M)] if m else []


def donnees(C: list[dict], dernier: Path, fiches_sources: list[dict], n_controles: int, lien_liste: str) -> dict:
    """Tout ce que la page montre, chaque nombre calculé ici."""
    sources = [{"nom": f["nom"], "producteur": re.sub(r"\s+", " ", f["producteur"]).strip(),
                "licence": " ; ".join(f["licences"]) or "non renseignée", "version": f["version"] or "–",
                "recupere": f["recupere"] or "–", "rythme": rythme(f)} for f in fiches_sources]
    sans_date = [f"{f['nom']} : date de récupération non enregistrée, {versions_texte(f)}"
                 for f in fiches_sources if not f["recupere"]]
    # un rythme qui n'est pas celui que le producteur annonce pour le jeu (FINESS) est expliqué sous le tableau
    notes_rythme = list(dict.fromkeys(config.RYTHME_NOTES[i[0]] for f in fiches_sources for i in infos(f)
                                      if i[0] in config.RYTHME_NOTES))
    return {"n": len(C), "n_domaines": len({e["domaine"] for e in C}), "n_sources": len(fiches_sources),
            "n_sm": sum(1 for e in C if SANTE_MENTALE in e["themes"]),
            "n_epci": sum(1 for e in C if "intercommunalité" in e["niveaux"]),
            "n_reg_seul": sum(1 for e in C if e["niveaux"] == ["région"]),
            "licences": licences(C), "domaines": domaines(C), "sources": sources,
            "par_source": ", ".join(f"{s} {n}" for s, n in Counter(e["source"] for e in C).most_common()),
            "sans_date": sans_date, "notes_rythme": notes_rythme, "millesimes": millesimes(C), "temps": profondeur(C, dernier, fiches_sources),
            "concordance": concordance(dernier), "n_controles": n_controles,
            "a_venir": a_venir(config.RACINE / "contenus" / "a_venir.md"), "lien_liste": lien_liste}
