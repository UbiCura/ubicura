"""Lecture et rangement d'un secret (clé d'accès, mot de passe) dans le gestionnaire d'identifiants de Windows, jamais
dans un fichier ni dans le dépôt. Utilisé par outils/zenodo.py, outils/messagerie.py et outils/reseaux.py.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


_GENERIQUE, _PERSISTANT = 1, 2   # CRED_TYPE_GENERIC, CRED_PERSIST_LOCAL_MACHINE


def lire(cible: str) -> str | None:
    """Secret rangé sous le nom `cible`, ou None s'il n'y en a pas (ou hors de Windows)."""
    return lire_compte(cible)[1]


def lire_compte(cible: str) -> tuple[str | None, str | None]:
    """Nom d'utilisateur et secret rangés sous le nom `cible`, (None, None) s'il n'y en a pas (ou hors de Windows)."""
    if sys.platform != "win32":
        return None, None
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    p = ctypes.POINTER(_CREDENTIAL)()
    if not adv.CredReadW(cible, _GENERIQUE, 0, ctypes.byref(p)):
        return None, None
    try:
        brut = ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize)
        return p.contents.UserName, brut.decode("utf-16-le").strip() or None
    finally:
        adv.CredFree(p)


def ecrire(cible: str, secret: str, utilisateur: str, commentaire: str) -> int:
    """Range le secret, renvoie 0 ou le code d'erreur de Windows."""
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    blob = secret.encode("utf-16-le")
    tampon = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    c = _CREDENTIAL(Type=_GENERIQUE, TargetName=cible, UserName=utilisateur, Comment=commentaire,
                    CredentialBlobSize=len(blob), CredentialBlob=tampon, Persist=_PERSISTANT)
    if not adv.CredWriteW(ctypes.byref(c), 0):
        return ctypes.get_last_error() or -1
    return 0
