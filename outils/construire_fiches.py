"""Construit quelques fiches de territoire dans le site déjà construit, sans refaire tout le site : pour contrôler un
échantillon avant la construction complète (exécution lourde), après un changement de la fiche.

Écrit site/territoire/<niveau>/<code>.html pour chaque territoire demandé, et recopie gabarits/style.css dans le site.
Les données sont celles de la dernière version de resultats/.

    $env:PYTHONUTF8=1
    .\\.venv\\Scripts\\python.exe outils\\construire_fiches.py epci:200090561 dep:971 reg:24
"""
import json
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from pipeline import config, fiche_territoire as FT, limites  # noqa: E402
from pipeline import site as S  # noqa: E402


def main(argv=None) -> int:
    demandes = {tuple(a.split(":", 1)) for a in (argv if argv is not None else sys.argv[1:])}
    if not demandes:
        print(__doc__)
        return 1
    r = max(p for p in config.RESULTATS.glob("20*") if (p / "site_data.json").exists())
    sd = json.loads((r / "site_data.json").read_text(encoding="utf-8"))
    limites.completer(sd.get("limites"))
    env = S._environnement()
    pages = FT.construire(env, S._commun(r, sd), r, sd, S.SITE, config.RACINE / "docs" / "veille" / "registre_bases.csv",
                          config.ADRESSE_SITE, config.CITATION_AUTEUR, demandes)
    shutil.copy(S.GABARITS / "style.css", S.SITE / "style.css")
    # balises de référencement de chaque page, comme referencement.appliquer à la construction complète
    from pipeline import referencement as rf
    avec_image = (S.SITE / "apercu.png").exists()
    for p in pages:
        p.write_text(rf._injecter(rf._sans_bloc(p.read_text(encoding="utf-8")), rf.balises_page(rf._chemin(S.SITE, p), avec_image)),
                     encoding="utf-8")
    for p in pages:
        print(p.relative_to(S.SITE).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
