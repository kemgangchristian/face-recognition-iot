"""
Authentification par clé API statique.

Réservée aux clients machine-à-machine (scripts d'automatisation, tests,
intégrations externes type Home Assistant). Le dashboard web utilise un
mécanisme séparé, par cookie de session — voir `session_auth.py` — pour
ne jamais exposer de secret dans le JavaScript envoyé au navigateur.

Story initiale : Epic 9 (sécurisation de l'API avant tout usage commercial).
"""

import os
import secrets

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def _load_api_key() -> str:
    """
    Charge la clé API depuis l'environnement au démarrage du service.

    Raises:
        RuntimeError: si la variable n'est pas définie — on préfère un
            échec explicite et immédiat au démarrage plutôt qu'une API
            qui tournerait silencieusement sans protection.
    """
    key = os.environ.get("FACE_RECOGNITION_API_KEY")
    if not key:
        raise RuntimeError(
            "FACE_RECOGNITION_API_KEY non définie. L'API ne peut pas démarrer "
            "sans clé d'authentification configurée. Génère-en une avec :\n"
            '  python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    return key


_VALID_API_KEY = _load_api_key()


def check_api_key(provided_key: str | None) -> bool:
    """
    Vérifie une clé API fournie, en temps constant (protège contre les
    attaques par mesure de timing sur la comparaison caractère par
    caractère d'une comparaison naïve `==`).
    """
    if not provided_key:
        return False
    return secrets.compare_digest(provided_key, _VALID_API_KEY)


def verify_api_key(provided_key: str = Security(api_key_header)) -> None:
    """
    Dépendance FastAPI protégeant un endpoint par clé API uniquement.
    Utilisée pour les routes d'administration technique (ex: purge des
    logs), jamais appelées depuis le dashboard web.
    """
    if not check_api_key(provided_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante.",
        )
    