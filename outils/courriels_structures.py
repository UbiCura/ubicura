"""Courriels aux établissements pour confirmer leurs structures de santé mentale non confirmées (demande du
18 novembre 2026 : « est-ce qu'on va envoyer des mails pour avoir des confirmations », essai sur dix établissements).

Pour chaque établissement d'un fichier de contacts (ej, adresse électronique lue sur une page officielle, page source),
prépare un brouillon qui liste ses structures restées « non confirmées » dans la liste vérifiée (statut « bases »).
Les brouillons vont dans la fenêtre du courrier (outils/messagerie.py), où l'auteur les relit et les envoie d'un clic.
Rien n'est envoyé d'ici.

    python outils\\courriels_structures.py <contacts.csv> [--date AAAA-MM-JJ]

contacts.csv : ej;etablissement;adresse_electronique;nature;page_source;remarque (point-virgule, UTF-8). Une ligne
sans adresse électronique (formulaire seulement) est écartée et signalée.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


def structures_non_confirmees(ej: str) -> pd.DataFrame:
    s = pd.read_csv(RACINE / "contenus" / "structures_verifiees.csv", sep=";", dtype=str).fillna("")
    return s[(s["ej"] == ej) & (s["statut"] == "bases")]


def ligne(r, lab: dict, communes: dict) -> str:
    from pipeline.lieux import voie_developpee
    adr = re.sub(r"\s+", " ", r["adresse"]).strip()
    if adr.isupper():   # « R DE LA MAISON ROUGE » devient « Rue de la Maison Rouge »
        petits = {"de", "du", "des", "la", "le", "les", "aux", "au", "et", "en", "sur", "sous"}
        adr = " ".join(m if m in ("R", "AV", "AVE", "BD", "BLD", "CHE", "CH", "PL", "RTE", "IMP", "ALL", "LD", "ST",
                                  "STE") else (m.lower() if m.lower() in petits else "-".join(p.capitalize() for p in m.split("-")))
                       for m in adr.split())
        adr = re.sub(r"\b([LD])'(\w)", lambda x: x.group(1).lower() + "'" + x.group(2).upper(), adr)
    adr = voie_developpee(adr)
    com = communes.get(r["commune"], {}).get("nom", r["commune"])
    typ = lab.get(r["type"], r["type"])
    nom = r["nom"].strip()
    tete = typ if nom.upper() in (typ.upper(), typ.split(" ")[0].upper()) else f"{nom} ({typ})"
    fin = f", FINESS {r['finess'].split(',')[0]}" if r["finess"] else ""
    return f"- {tete}, {adr + ', ' if adr else ''}{com}{fin}"


def corps(etab: str, lignes: list[str]) -> str:
    return f"""Madame, Monsieur,

Je tiens Ubi Cura (https://ubicura.fr), un site de données publiques et gratuites qui décrit l'offre de soins en France, en particulier en santé mentale, territoire par territoire. Il est utilisé notamment par des chercheurs et des acteurs publics.

Pour chaque établissement, nous reprenons la liste de ses structures à partir des répertoires FINESS et ROR, puis nous la vérifions une à une sur des sources publiques récentes. Pour {etab}, les structures suivantes figurent dans ces répertoires, mais nous n'avons trouvé aucune source publique récente qui les confirme :

{chr(10).join(lignes)}

Pourriez-vous nous dire si elles accueillent toujours des patients à ces adresses, ou si certaines ont fermé, déménagé ou changé de nom ? Une réponse partielle, une liste à jour ou le lien vers une page de votre site nous aiderait déjà beaucoup.

Votre réponse servira seulement à corriger notre liste, qui ne contient que des structures et leurs adresses publiques, jamais de données personnelles. Sur notre site, ces structures sont signalées comme non confirmées tant que nous n'avons pas de source.

Je vous remercie par avance de votre aide.

Bien cordialement,

Lucas Pithon
Ubi Cura, https://ubicura.fr
contact@ubicura.fr"""


def main() -> int:
    from pipeline import config
    contacts = pd.read_csv(sys.argv[1], sep=";", dtype=str).fillna("")
    jour = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else f"{dt.date.today():%Y-%m-%d}"
    lab = {t[0]: t[1].split(",")[0] for t in config.LIEUX_TYPES}
    brut = json.loads((RACINE / "donnees" / "brut" / "ref_communes.json").read_text(encoding="utf-8"))
    communes = {c["code"]: c for c in brut if c.get("type") in ("commune-actuelle", "arrondissement-municipal")}
    for _, c in contacts.iterrows():
        adr = c["adresse_electronique"].strip()
        if not adr:
            print(f"{c['ej']} {c['etablissement']} : pas d'adresse électronique (formulaire seulement), écarté")
            continue
        st = structures_non_confirmees(c["ej"])
        if st.empty:
            print(f"{c['ej']} {c['etablissement']} : aucune structure non confirmée, écarté")
            continue
        etab = st["etablissement"].iloc[0] or c["etablissement"]
        lignes = [ligne(r, lab, communes) for _, r in st.sort_values(["type", "commune", "nom"]).iterrows()]
        b = {"id": f"{jour}-structures-{c['ej'].lower()}", "a": [adr],
             "objet": f"Ubi Cura, confirmation de structures de santé mentale de votre établissement",
             "corps": corps(etab, lignes),
             "motif": (f"Confirmer les {len(lignes)} structures de {etab} restées non confirmées après la vérification du "
                       f"18 novembre 2026 (aucune source publique de moins de trois ans). Essai sur dix établissements."),
             "sources": [f"adresse lue sur {c['page_source']} ({c['nature']})",
                         "contenus/structures_verifiees.csv, statut bases"]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(b, f, ensure_ascii=False)
        r = subprocess.run([sys.executable, str(RACINE / "outils" / "messagerie.py"), "ajouter-brouillon", f.name],
                           capture_output=True, text=True)
        print(f"{c['ej']} {etab} : {len(lignes)} structures, {(r.stdout or r.stderr).strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
