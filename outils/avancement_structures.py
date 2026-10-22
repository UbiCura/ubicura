"""Tableau d'avancement par type de structure de soins (16 octobre 2026).

Une ligne par type de config.LIEUX_TYPES, lue dans le registre (config.LIEUX_PROFIL) et dans le dernier dossier de
résultats. Écrit docs/avancement_structures.md et docs/avancement_structures.csv.

    .\\.venv\\Scripts\\python.exe outils\\avancement_structures.py [AAAA-MM-JJ]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline import config, confirmation, lieux_profil as lp  # noqa: E402

NIVEAUX_CONFIRMES = {confirmation.NIVEAUX[k] for k in ("etablissement", "source_publique", "has_sirene", "has", "sirene")}


def pct(v: float, signe: bool = False, dec: int = 0) -> str:
    """Pourcentage à la française, virgule décimale et espace avant le signe."""
    return (f"{v * 100:{'+' if signe else ''}.{dec}f}").replace(".", ",") + " %"


def _csv(d: Path, nom: str, **kw):
    f = d / nom
    return pd.read_csv(f, sep=";", decimal=",", encoding="utf-8-sig", low_memory=False, **kw) if f.exists() else None


def dossier(arg: str | None) -> Path:
    if arg:
        return config.RESULTATS / arg
    ds = [d for d in config.RESULTATS.glob("*") if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)
          and (d / "lieux_soins.csv").exists()]
    if not ds:
        sys.exit("Aucun dossier de résultats, lancer run.py --hors-ligne")
    return max(ds, key=lambda d: d.stat().st_mtime)


def construire(d: Path) -> pd.DataFrame:
    ls, cou = _csv(d, "lieux_soins.csv"), _csv(d, "lieux_couverture.csv").set_index("type")
    f = RACINE / "contenus" / "verdicts_verification.csv"
    verdicts = pd.read_csv(f, sep=";", encoding="utf-8-sig") if f.exists() else pd.DataFrame(columns=["type_reel", "verdict"])
    non_ret = _csv(d, "structures_non_retenues.csv")
    refs = _csv(d, "lieux_references.csv")
    conc = _csv(d, "concordance_cmp_sae.csv")
    a_venir = (RACINE / "contenus" / "a_venir.md").read_text(encoding="utf-8").lower()
    rapports = " ".join((d / n).read_text(encoding="utf-8").lower() for n in ("rapport_sante_mentale.md", "rapport_sante.md")
                        if (d / n).exists())
    source_rapports = " ".join((RACINE / "pipeline" / n).read_text(encoding="utf-8")
                               for n in ("rapport.py", "rapport_territoire.py"))
    lignes = []
    for tid, lib, fam, groupe, _r in config.LIEUX_TYPES:
        g = ls[ls["type"] == tid]
        p = config.LIEUX_PROFIL.get(tid)
        l_ = {"type": tid, "libelle": lib, "groupe": groupe, "statut": "activé" if p else "non activé",
              "structures": len(g), "departements": pct(cou.at[tid, 'part_departements']) if tid in cou.index else "",
              "complet": bool(cou.at[tid, "complet"]) if tid in cou.index else False}
        l_["public"] = {"grand_age": "grand âge"}.get(p["public"], p["public"]) if p else ""
        # confirmation, part des structures confirmées par une source indépendante
        src = p.get("confirmation", []) if p else []
        if src and len(g) and g["confirmation"].notna().any():
            l_["confirmation"] = f"{', '.join(src)}, {pct(g['confirmation'].isin(NIVEAUX_CONFIRMES).mean())} confirmées"
        else:
            l_["confirmation"] = "aucune source" if p else ""
        # référence et concordance
        r = (p or {}).get("reference")
        l_["reference"] = {"sae": "SAE", "publiee": r and "publiée"}.get(r and r["genre"], "") if r else ""
        l_["concordance"] = ""
        if r and r["genre"] == "publiee" and refs is not None and tid in set(refs["type"]):
            e = float(refs.loc[refs["type"] == tid, "ecart"].iloc[0])
            l_["concordance"] = f"{pct(e, True, 1)} ({'dans' if abs(e) <= r['ecart_max'] else 'hors de'} la tolérance de {pct(r['ecart_max'])})"
        elif r and conc is not None:
            fr = conc[conc["niveau"] == "fr"].iloc[0]
            e = fr[r["champ"].replace("sae_", "")] / fr[r["champ"]] - 1
            l_["concordance"] = f"{pct(e, True, 1)} ({'dans' if abs(e) <= r['ecart_max'] else 'hors de'} la tolérance de {pct(r['ecart_max'])})"
        # vérification, inscriptions rangées par verdict dans ce type et écartées
        v = verdicts[verdicts["type_reel"] == tid]
        ecart = 0 if non_ret is None or "type" not in non_ret else int((non_ret["type"] == tid).sum())
        deja = int(g["verification"].notna().sum()) if "verification" in g else 0
        morceaux = [f"{n} {lab}" for n, lab in ((deja, "vérifiées"), (len(v), "rangées dans ce type par verdict"),
                                                 (ecart, "écartées")) if n]
        l_["verification"] = ", ".join(morceaux)
        l_["analyses"] = ", ".join(p["analyses"]) if p else ""
        l_["atlas"] = "points" if groupe in config.LIEUX_ATLAS_GROUPES else "fichiers seulement"
        court = lib.split(",")[0].lower()
        l_["rapport"] = ("cité" if (court in rapports or f'"{tid}"' in source_rapports or f"'{tid}'" in source_rapports)
                         else "")
        mot = (p or {}).get("a_venir")
        l_["a_venir"] = ("annoncé" if mot and mot.lower() in a_venir else "à annoncer" if mot else "")
        lignes.append(l_)
    return pd.DataFrame(lignes)


def ecrire(t: pd.DataFrame, d: Path) -> None:
    t.to_csv(RACINE / "docs" / "avancement_structures.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    cols = ["libelle", "structures", "departements", "public", "confirmation", "reference", "concordance", "verification",
            "analyses", "atlas", "rapport", "a_venir"]
    ent = ["Type", "Structures", "Départements", "Public", "Confirmation", "Référence", "Concordance", "Vérification",
           "Analyses", "Atlas", "Rapport", "À venir"]
    act = t[t["statut"] == "activé"]
    n_act = len(act)
    out = [f"# Avancement par type de structure de soins\n",
           f"Généré par `outils/avancement_structures.py` à partir de `config.LIEUX_PROFIL` et du dossier `resultats/{d.name}`. "
           f"Ne pas modifier à la main. {n_act} types activés sur {len(t)}, {int(t['complet'].sum())} types recensés dans "
           f"au moins {pct(config.LIEUX_COUVERTURE_MIN)} des départements.\n",
           "## Types activés (testés par le registre)\n",
           "| " + " | ".join(ent) + " |", "|" + "---|" * len(ent)]
    for _, r in act.iterrows():
        out.append("| " + " | ".join(str(r[c]).replace("|", "/").replace("nan", "") for c in cols) + " |")
    out += ["", "## Autres types recensés (non activés)\n", "| Type | Structures | Départements | Atlas |", "|---|---|---|---|"]
    for _, r in t[t["statut"] != "activé"].iterrows():
        out.append(f"| {r['libelle']} | {r['structures']} | {r['departements']} | {r['atlas']} |")
    (RACINE / "docs" / "avancement_structures.md").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    dos = dossier(sys.argv[1] if len(sys.argv) > 1 else None)
    ecrire(construire(dos), dos)
    print("docs/avancement_structures.md écrit d'après", dos.name)
