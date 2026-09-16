"""
Authentification par session (cookie HttpOnly) pour le dashboard web.

Pourquoi une session plutôt qu'une clé API embarquée dans le JavaScript :
toute clé présente dans le bundle envoyé au navigateur est consultable par
quiconque ouvre les outils de développement — inacceptable pour un secret
d'accès. Le pattern standard 2026 pour un tableau de bord local d'appareil
IoT (routeurs, NAS, caméras IP) est un cookie de session HttpOnly, que
JavaScript ne peut jamais lire, combiné à un stockage des sessions actives
côté serveur (permet une déconnexion réellement immédiate, contrairement à
un token auto-signé sans état qui reste valide jusqu'à expiration).

Complète `auth.py` (clé API), sans le remplacer : les scripts
d'automatisation continuent d'utiliser la clé API, le dashboard utilise
cette session.
"""

import os
import secrets
import time

from fastapi import Request, Response, HTTPException, status

SESSION_COOKIE_NAME = "face_recognition_session"
SESSION_DURATION_SECONDS = 8 * 60 * 60  # 8 heures — durée d'une session de travail

# Stockage des sessions actives en mémoire : {token: expiration_unix_timestamp}.
# Suffisant pour un seul appareil edge avec un unique processus API — pas
# besoin d'une vraie base de données pour ça. Limite connue et acceptée :
# les sessions sont perdues au redémarrage du conteneur (chaque déploiement
# Jenkins déconnecte les utilisateurs actifs du dashboard).
_active_sessions: dict[str, float] = {}


def _get_dashboard_password() -> str:
    """Charge le mot de passe du dashboard depuis l'environnement."""
    password = os.environ.get("DASHBOARD_PASSWORD")
    if not password:
        raise RuntimeError(
            "DASHBOARD_PASSWORD non définie. Le dashboard ne peut pas "
            "démarrer sans mot de passe configuré."
        )
    return password


def create_session(response: Response, password: str) -> None:
    """
    Vérifie le mot de passe fourni et, si correct, pose un cookie de
    session HttpOnly sur la réponse.

    Raises:
        HTTPException: 401 si le mot de passe est incorrect.
    """
    valid_password = _get_dashboard_password()

    if not secrets.compare_digest(password, valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect.",
        )

    token = secrets.token_urlsafe(32)
    _active_sessions[token] = time.time() + SESSION_DURATION_SECONDS

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,   # inaccessible depuis JavaScript, protège contre le vol par script
        samesite="lax",  # protection CSRF de base
        secure=False,    # à passer à True dès que le dashboard est servi en HTTPS
        max_age=SESSION_DURATION_SECONDS,
        path="/",
    )


def destroy_session(request: Request, response: Response) -> None:
    """Invalide la session en cours (déconnexion) : suppression immédiate
    du stockage serveur, contrairement à un token auto-signé qui resterait
    valide jusqu'à expiration naturelle."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token and token in _active_sessions:
        del _active_sessions[token]
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def is_session_valid(request: Request) -> bool:
    """
    Vérifie si la requête porte un cookie de session valide et non expiré.
    Nettoie automatiquement les sessions expirées rencontrées au passage.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False

    expiry = _active_sessions.get(token)
    if not expiry:
        return False

    if expiry <= time.time():
        del _active_sessions[token]
        return False

    return True


def verify_session_or_api_key(request: Request) -> None:
    """
    Dépendance FastAPI acceptant SOIT un cookie de session valide
    (dashboard web), SOIT la clé API en header (scripts/automatisation) —
    jamais les deux exigés simultanément. Utilisée sur les routes
    consultées à la fois par le dashboard et par des clients externes.
    """
    if is_session_valid(request):
        return

    # Import différé pour éviter une dépendance circulaire entre les deux
    # modules d'authentification.
    from api.auth import check_api_key

    api_key = request.headers.get("X-API-Key")
    if check_api_key(api_key):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise.",
    )
