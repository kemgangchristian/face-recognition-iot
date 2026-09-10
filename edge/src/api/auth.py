"""
Authentification par clé API pour les endpoints sensibles.
Story additionnelle Epic 9 — sécurisation avant déploiement commercial.
"""

import os
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def _load_api_key() -> str:
    """
    Charge la clé API depuis une variable d'environnement.

    Raises:
        RuntimeError: si aucune clé n'est configurée — on préfère un échec
                      explicite au démarrage plutôt qu'une API non protégée
                      silencieusement.
    """
    key = os.environ.get("FACE_RECOGNITION_API_KEY")
    if not key:
        raise RuntimeError(
            "FACE_RECOGNITION_API_KEY non définie. L'API ne peut pas démarrer "
            "sans clé d'authentification configurée. Génère-en une avec : "
            "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return key


_VALID_API_KEY = _load_api_key()


def verify_api_key(provided_key: str = Security(api_key_header)) -> None:
    """
    Dépendance FastAPI vérifiant la clé API fournie dans le header.
    Utilise secrets.compare_digest pour éviter les attaques par timing.
    """
    if provided_key is None or not secrets.compare_digest(provided_key, _VALID_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante.",
        )
    