"""
Authentification par session (cookie HttpOnly) pour le dashboard web.
Complète l'authentification par clé API (utilisée pour les appels
programmatiques/automatisation) sans jamais exposer de secret côté client.
"""

import os
import secrets
import time
from fastapi import Request, HTTPException, status, Response

SESSION_COOKIE_NAME = "face_recognition_session"
SESSION_DURATION_SECONDS = 8 * 60 * 60  # 8 heures

# Stockage des sessions actives en mémoire — suffisant pour un seul
# appareil edge, pas besoin d'une vraie base de données pour ça.
_active_sessions: dict[str, float] = {}


def _get_dashboard_password() -> str:
    password = os.environ.get("DASHBOARD_PASSWORD")
    if not password:
        raise RuntimeError(
            "DASHBOARD_PASSWORD non définie. Le dashboard ne peut pas démarrer "
            "sans mot de passe configuré."
        )
    return password


def create_session(response: Response, password: str) -> None:
    """Vérifie le mot de passe et pose un cookie de session HttpOnly si
    correct. Lève une exception 401 sinon."""
    valid_password = _get_dashboard_password()

    if not secrets.compare_digest(password, valid_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mot de passe incorrect.")

    token = secrets.token_urlsafe(32)
    _active_sessions[token] = time.time() + SESSION_DURATION_SECONDS

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,       # JavaScript ne peut jamais lire ce cookie
        samesite="lax",      # protège contre le CSRF basique
        secure=False,        # True obligatoire si HTTPS un jour (pas le cas en local HTTP)
        max_age=SESSION_DURATION_SECONDS,
    )


def destroy_session(request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token and token in _active_sessions:
        del _active_sessions[token]
    response.delete_cookie(SESSION_COOKIE_NAME)


def verify_session_or_api_key(request: Request) -> None:
    """
    Dépendance FastAPI acceptant SOIT un cookie de session valide (dashboard),
    SOIT la clé API en header (scripts/automatisation) — jamais les deux
    exigés en même temps.
    """
    # 1. Tente d'abord la session cookie (cas du dashboard)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        expiry = _active_sessions.get(token)
        if expiry and expiry > time.time():
            return  # session valide, accès autorisé
        if token in _active_sessions:
            del _active_sessions[token]  # session expirée, nettoyage

    # 2. Sinon, retombe sur la clé API classique (cas des scripts/curl)
    api_key = request.headers.get("X-API-Key")
    valid_key = os.environ.get("FACE_RECOGNITION_API_KEY")
    if api_key and valid_key and secrets.compare_digest(api_key, valid_key):
        return

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")
