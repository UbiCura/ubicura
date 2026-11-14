"""Paquet du programme. À l'import, les fichiers temporaires (profils du navigateur des contrôles et des captures,
dossiers des tests) sont placés dans un dossier voisin du projet, « offre_soins_tmp », et non sur le disque du
système, qui s'était rempli (14 novembre 2026). Les processus lancés ensuite (navigateur, sous-programmes) en héritent.
Les entrées de plus de deux jours y sont effacées."""
import os as _os
import shutil as _shutil
import tempfile as _tempfile
import time as _time
from pathlib import Path as _Path


def _dossier_temporaire() -> None:
    d = _Path(_os.environ.get("OFFRE_SOINS_TMP") or _Path(__file__).resolve().parents[2] / "offre_soins_tmp")
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    _os.environ["TEMP"] = _os.environ["TMP"] = _os.environ["TMPDIR"] = str(d)
    _tempfile.tempdir = str(d)
    limite = _time.time() - 2 * 86400
    try:
        for e in d.iterdir():
            if e.stat().st_mtime < limite:
                _shutil.rmtree(e, ignore_errors=True) if e.is_dir() else e.unlink(missing_ok=True)
    except OSError:
        pass


_dossier_temporaire()
