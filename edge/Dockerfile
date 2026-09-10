# =============================================================================
# Dockerfile — Module Edge (Raspberry Pi)
# Cible : linux/arm64
# =============================================================================

FROM python:3.11-slim-bookworm

# Dépendances système nécessaires à OpenCV.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie et installation des dépendances Python d'abord, pour profiter
# du cache Docker (rebuild plus rapide si seul le code change).
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copie du code source et des modèles.
COPY src/ ./src/
COPY models/ ./models/

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
