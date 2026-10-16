"""Contrôle que les chiffres écrits dans les rapports sont ceux des tableaux publiés (demande de Lucas du 13 octobre
2026, « aucune incohérence de chiffre entre rapport et tableau »).

Pour chaque rapport territorial (départements et régions) et pour le rapport national de santé mentale, les nombres
de structures de soins, de CMP par public et de CMP déclarés à la SAE sont relus dans le texte et confrontés aux
fichiers CSV de la même version (lieux_soins_dep.csv, lieux_soins_reg.csv, lieux_soins.csv, cmp_par_public.csv,
concordance_cmp_sae.csv). Les listes de structures sont recomptées.

    python outils\\coherence_rapports.py [resultats\\AAAA-MM-JJ]

Code de sortie 0 si tout concorde, 20 sinon. Lancé aussi par outils/comparer_versions.py avant chaque publication.
"""
import re
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
NOMBRE = r"(\d{1,3}(?:[   ]\d{3})*|\d+)"


def entier(s: str) -> int:
    return int(re.sub(r"[   ]", "", s))


def _lire(f: Path) -> pd.DataFrame | None:
    return pd.read_csv(f, sep=";", dtype=str) if f.exists() else None


def _section(md: str, titre: str) -> str:
    i = md.find(titre)
    if i < 0:
        return ""
    j = md.find("\n## ", i + len(titre))
    return md[i:j if j > 0 else len(md)]


def controler(version: Path) -> list[str]:
    """Liste des écarts entre le texte des rapports et les tableaux de la version, vide si tout concorde."""
    sys.path.insert(0, str(RACINE))
    from pipeline import config
    lib_type = {t[1]: t[0] for t in config.LIEUX_TYPES}
    pb: list[str] = []
    tab = {n: _lire(version / f"lieux_soins_{n}.csv") for n in ("dep", "reg")}
    pub = _lire(version / "cmp_par_public.csv")
    sae = _lire(version / "concordance_cmp_sae.csv")
    dossier = version / "territoires"
    nb_rapports = 0
    for f in sorted(dossier.glob("*.md")) if dossier.exists() else []:
        m = re.match(r"(dep|reg)-([0-9AB]+)-(sante-mentale|sante)\.md$", f.name)
        if not m:
            continue
        niv, code, fam = m.groups()
        md = f.read_text(encoding="utf-8")
        nb_rapports += 1
        t = tab.get(niv)
        ligne = t[t["code"] == code] if t is not None else None
        sec = _section(md, "## Structures de soins")
        # tableau des structures, nombre de chaque type
        for lib, n in re.findall(r"^\| ([^|]+?) \| " + NOMBRE + r" \|", sec, flags=re.M):
            tid = lib_type.get(lib)
            if tid is None or ligne is None or ligne.empty or f"n_{tid}" not in ligne:
                continue
            attendu = int(float(ligne.iloc[0][f"n_{tid}"]))
            if entier(n) != attendu:
                pb.append(f"{f.name}, tableau des structures, {lib} {n} dans le texte, {attendu} dans "
                          f"lieux_soins_{niv}.csv")
        # listes nominatives, nombre annoncé, nombre de noms et nombre du tableau
        for lib, n, noms in re.findall(r"^- \*\*(.+?)\*\* \(" + NOMBRE + r"\)\. (.*)$", sec, flags=re.M):
            compte = len(noms.split("; "))
            if compte != entier(n):
                pb.append(f"{f.name}, liste « {lib} », {n} annoncés et {compte} noms")
            tid = lib_type.get(lib)
            if tid and ligne is not None and not ligne.empty and f"n_{tid}" in ligne:
                attendu = int(float(ligne.iloc[0][f"n_{tid}"]))
                if entier(n) != attendu:
                    pb.append(f"{f.name}, liste « {lib} », {n} annoncés, {attendu} dans lieux_soins_{niv}.csv")
        # CMP par public
        mp = re.search(r"Sur les " + NOMBRE + r" CMP du territoire, " + NOMBRE + r" accueillent des adultes et "
                       + NOMBRE + r" des enfants et adolescents(?:, dont " + NOMBRE + r" les deux publics)?", md)
        if mp and pub is not None:
            r = pub[(pub["niveau"] == niv) & (pub["code"] == code)]
            if r.empty:
                pb.append(f"{f.name}, CMP par public absents de cmp_par_public.csv")
            else:
                r = r.iloc[0]
                lu = [entier(mp.group(i)) for i in (1, 2, 3)] + [entier(mp.group(4)) if mp.group(4) else 0]
                vu = [int(r["cmp"]), int(r["adultes"]), int(r["enfants"]), int(r["les_deux"])]
                if lu != vu:
                    pb.append(f"{f.name}, CMP par public {lu} dans le texte, {vu} dans cmp_par_public.csv")
                np_ = re.search(r"Pour " + NOMBRE + r" d'entre eux, connus de FINESS seul", md)
                n_np = entier(np_.group(1)) if np_ else (1 if "Pour l'un d'eux, connu de FINESS seul" in md else 0)
                if n_np != int(r["non_precise"]):
                    pb.append(f"{f.name}, CMP au public non précisé {n_np} dans le texte, {r['non_precise']} dans "
                              f"cmp_par_public.csv")
                if vu[1] + vu[2] - vu[3] + int(r["non_precise"]) != vu[0]:
                    pb.append(f"{f.name}, adultes, enfants et public non précisé ne refont pas le total des CMP")
                if ligne is not None and not ligne.empty:
                    for col, v in (("n_lieu_cmp", vu[0]), ("n_lieu_cmp_adultes", vu[1]), ("n_lieu_cmp_enfants", vu[2])):
                        if int(float(ligne.iloc[0][col])) != v:
                            pb.append(f"{f.name}, {v} dans cmp_par_public.csv, {ligne.iloc[0][col]} pour {col} dans "
                                      f"lieux_soins_{niv}.csv")
        # CMP de la SAE, phrase de la partie hôpital et phrase de concordance
        if sae is not None:
            r = sae[(sae["niveau"] == niv) & (sae["code"] == code)]
            ms = re.search(r"déclarent " + NOMBRE + r" CMP à la SAE, alors que la partie « Structures de soins » compte "
                           + NOMBRE + r" CMP(?:.*?le ROR y décrit " + NOMBRE + r" unités)?", md)
            mc = re.search(r"\(" + NOMBRE + r" structures recensées ici(?:, dont [^,]+)?, " + NOMBRE
                           + r" CMP déclarés à la SAE", md)
            # antennes et permanences annoncées, comparées à cmp_par_public.csv
            ma = re.search(r"structures recensées ici, dont " + NOMBRE + r" antennes? ou permanences?", md)
            if pub is not None:
                rp = pub[(pub["niveau"] == niv) & (pub["code"] == code)]
                if not rp.empty and "antennes" in rp:
                    lu_a = entier(ma.group(1)) if ma else 0
                    if mc and lu_a != int(rp.iloc[0]["antennes"]):
                        pb.append(f"{f.name}, antennes et permanences {lu_a} dans le texte, {rp.iloc[0]['antennes']} "
                                  f"dans cmp_par_public.csv")
            for nom_, mm, champs in (("phrase de la partie hôpital", ms, ["sae_cmp", "cmp", "unites_ror"]),
                                     ("phrase de concordance", mc, ["cmp", "sae_cmp"])):
                if not mm:
                    continue
                if r.empty:
                    pb.append(f"{f.name}, {nom_} sans ligne dans concordance_cmp_sae.csv")
                    continue
                for i, ch in enumerate(champs, start=1):
                    if mm.group(i) is None or pd.isna(r.iloc[0][ch]):
                        continue
                    if entier(mm.group(i)) != int(float(r.iloc[0][ch])):
                        pb.append(f"{f.name}, {nom_}, {ch} {mm.group(i)} dans le texte, {r.iloc[0][ch]} dans "
                                  f"concordance_cmp_sae.csv")
            # tableau de la psychiatrie à l'hôpital, nombre de CMP déclarés
            mt = re.search(r"^\| Centres médico-psychologiques \(CMP\)[^|]*\| " + NOMBRE + r" \|", md, flags=re.M)
            if mt and not r.empty and pd.notna(r.iloc[0]["sae_cmp"]) and entier(mt.group(1)) != int(float(r.iloc[0]["sae_cmp"])):
                pb.append(f"{f.name}, tableau de la psychiatrie à l'hôpital, {mt.group(1)} CMP, "
                          f"{r.iloc[0]['sae_cmp']} dans concordance_cmp_sae.csv")
    # rapport national, tableau des structures par provenance
    nat = version / "rapport_sante_mentale.md"
    lieux = _lire(version / "lieux_soins.csv")
    if nat.exists() and lieux is not None:
        md = _section(nat.read_text(encoding="utf-8"), "#### Structures de soins")
        fin_ = md.find("\n#### ", 10)
        md = md[:fin_] if fin_ > 0 else md
        for lib, n, d, fi, ro, so in re.findall(r"^\| ([^|]+?) \| " + NOMBRE + r" \| " + NOMBRE + r" \| " + NOMBRE
                                                + r" \| " + NOMBRE + r" \| " + NOMBRE + r" \|", md, flags=re.M):
            tid = lib_type.get(lib)
            if tid is None:
                continue
            g = lieux[lieux["type"] == tid]
            p = g["provenance"].value_counts()
            src = [k for k in p.index if k.startswith("Absente des deux bases")]
            vu = [len(g), int(p.get("FINESS et ROR", 0)), int(p.get("FINESS seul", 0)),
                  int(p.get("ROR seul", 0)) + int(p.get("ROR, type que FINESS ne distingue pas", 0)),
                  int(p[src].sum()) if src else 0]
            lu = [entier(v) for v in (n, d, fi, ro, so)]
            if lu != vu:
                pb.append(f"rapport_sante_mentale.md, {lib} {lu} dans le texte, {vu} dans lieux_soins.csv")
            if lu[1] + lu[2] + lu[3] + lu[4] != lu[0]:
                pb.append(f"rapport_sante_mentale.md, {lib}, les provenances ne refont pas le total")
        # phrase de tête, CMP par public de la France
        mh = re.search(r"recensent " + NOMBRE + r" centres médico-psychologiques \(CMP\) distincts\. " + NOMBRE
                       + r" accueillent des adultes et " + NOMBRE + r" des enfants", nat.read_text(encoding="utf-8"))
        if mh:
            lu = [entier(mh.group(i)) for i in (1, 2, 3)]
            vu = [int((lieux["type"] == t_).sum()) for t_ in ("lieu_cmp", "lieu_cmp_adultes", "lieu_cmp_enfants")]
            if pub is not None:
                fr = pub[pub["niveau"] == "fr"]
                if not fr.empty and [int(fr.iloc[0][c]) for c in ("cmp", "adultes", "enfants")] != lu:
                    pb.append(f"rapport_sante_mentale.md, phrase de tête {lu}, cmp_par_public.csv "
                              f"{[int(fr.iloc[0][c]) for c in ('cmp', 'adultes', 'enfants')]}")
            if vu != lu:
                pb.append(f"rapport_sante_mentale.md, phrase de tête {lu} (CMP, adultes, enfants), {vu} dans lieux_soins.csv")
        else:
            pb.append("rapport_sante_mentale.md, phrase de tête sur les CMP introuvable")
    # atlas, structures de chaque type par département (points de site_data.json) et tableau publié
    sd, t = version / "site_data.json", tab.get("dep")
    if sd.exists() and t is not None:
        import json
        lx = json.loads(sd.read_text(encoding="utf-8")).get("lieux") or {}
        if lx.get("pts"):
            ids = [x["id"] for x in lx["types"]]
            pts = pd.DataFrame([(ids[p[0]], p[9]) for p in lx["pts"]], columns=["type", "dep"])
            atlas = pts.groupby(["dep", "type"]).size()
            tt = t.set_index("code")
            n_ecarts = 0
            # l'atlas ne montre en points que les groupes de config.LIEUX_ATLAS_GROUPES
            montres = {x["id"] for x in lx["types"] if x.get("groupe") in config.LIEUX_ATLAS_GROUPES}
            for tid in ids:
                col = f"n_{tid}"
                if tid not in montres:
                    continue
                if col not in tt:
                    continue
                for dep, v in tt[col].items():
                    if int(float(v)) != int(atlas.get((dep, tid), 0)):
                        n_ecarts += 1
                        if n_ecarts <= 5:
                            pb.append(f"atlas, {tid} dans le département {dep}, {atlas.get((dep, tid), 0)} points, {v} "
                                      f"dans lieux_soins_dep.csv")
            if n_ecarts > 5:
                pb.append(f"atlas, {n_ecarts} écarts en tout entre les points et lieux_soins_dep.csv")
    # page méthode du site, tableau des structures par provenance, les trois colonnes refont le total
    meth = RACINE / "site" / "methode.html"
    if meth.exists():
        h = meth.read_text(encoding="utf-8")
        for cells in re.findall(r"<tr>((?:<td>[^<]*</td>){8})</tr>", h):
            v = re.findall(r"<td>([^<]*)</td>", cells)
            try:
                n, d, fi, ro, so = (entier(x) for x in v[1:6])
            except ValueError:
                continue
            if d + fi + ro + so != n:
                pb.append(f"site/methode.html, {v[0]}, {d} + {fi} + {ro} ne font pas {n}")
    if nb_rapports == 0:
        pb.append("aucun rapport territorial trouvé")
    return pb


def main():
    if len(sys.argv) > 1:
        version = Path(sys.argv[1])
    else:
        version = sorted(p for p in (RACINE / "resultats").iterdir() if re.match(r"\d{4}-\d{2}-\d{2}$", p.name))[-1]
    pb = controler(version)
    for p in pb:
        print("écart |", p)
    print(f"{version.name}, {len(pb)} écart(s) entre les rapports et les tableaux")
    sys.exit(20 if pb else 0)


if __name__ == "__main__":
    main()
