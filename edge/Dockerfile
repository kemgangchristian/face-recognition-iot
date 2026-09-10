# =============================================================================
# Dockerfile — Module Edge (Raspberry Pi)
# Cible : linux/arm64
# =============================================================================

# Note : Trixie (pas Bookworm) est requis spécifiquement pour cette image,
# car le dépôt Raspberry Pi (rpicam-apps) sert des paquets compilés pour
# Debian 13, incompatibles avec les bibliothèques système de Debian 12.
# Cette déviation ne concerne que l'image edge (Pi) ; Jenkins/Mac restent
# sur Bookworm, cohérent puisqu'ils n'ont pas besoin de rpicam-apps.

FROM python:3.11-slim-trixie

# Dépendances système pour OpenCV + outils de signature de dépôts.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Ajout du dépôt officiel Raspberry Pi, nécessaire pour rpicam-apps
# (absent des dépôts Debian standards). Clé copiée depuis l'hôte plutôt
# que retéléchargée, pour garantir l'authenticité exacte de la source
# déjà validée sur le système Raspberry Pi OS.
COPY raspberrypi-archive-keyring.pgp /usr/share/keyrings/raspberrypi-archive-keyring.pgp

RUN echo "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.pgp] http://archive.raspberrypi.com/debian/ trixie main" \
    > /etc/apt/sources.list.d/raspi.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends rpicam-apps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY models/ ./models/

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
