# Architecture technique — Face Recognition IoT

## 1. Pipeline fonctionnel (edge)

```mermaid
flowchart LR
    A[Capture caméra CSI] --> B[Détection visage]
    B --> C[Alignement]
    C --> D[Extraction embedding]
    D --> E[Matching / recherche]
    E --> F[Décision + log]
```

Chaque étape est un module Python indépendant dans `edge/src/`, testable isolément.

## 2. Décisions techniques et justifications

### Détection de visage — YuNet (OpenCV)
Alternative écartée : MTCNN, RetinaFace (trop lourds pour CPU ARM sans accélération matérielle).
YuNet est intégré nativement à OpenCV ≥ 4.5.4, quantifié, pensé pour l'embarqué.

### Extraction d'embedding — MobileFaceNet
Alternative écartée : ArcFace sur backbone ResNet100 (précis mais ~100 Mo+, trop lourd pour un Pi).
MobileFaceNet reprend la loss ArcFace (angular margin) sur un backbone mobile : précision proche, poids ~4 Mo.

### Moteur d'inférence — TensorFlow Lite
Alternative valable : ONNX Runtime (équivalent, à réévaluer si besoin en cours de projet).
Choix motivé par le support ARM64 mature et la quantification INT8 native.

### Stockage edge — SQLite (chiffré)
Alternative écartée : PostgreSQL en local sur le Pi (inutile : consomme des ressources pour rien
sur un device à ressources limitées, sans bénéfice puisque le Pi fonctionne en autonome).
SQLite = zéro dépendance serveur, fonctionnement garanti hors-ligne.

### Stockage central — PostgreSQL
Utilisé uniquement côté backend (serveur), pour la supervision multi-sites : requêtes
relationnelles complexes, gestion de la concurrence multi-Pi, reporting.

### Recherche vectorielle — FAISS (mode CPU)
Alternative écartée : vector DB serveur (Milvus, Qdrant) — trop lourd pour un device isolé.
FAISS tourne en mémoire locale, suffisant jusqu'à plusieurs milliers d'identités enrôlées.

## 3. Séparation edge / backend

| Aspect                  | Edge (Raspberry Pi) | Backend central |
|-------------------------|------------------------------------------|-------------------------------------------|
| Architecture matérielle | ARM64                                    | x86_64                                    |
| Rôle                    | Traitement temps réel, décision locale   | Supervision, audit, propagation identités |
| Dépendance réseau       | Aucune pour fonctionner                  | Requise pour la synchronisation           |
| Base de données         | SQLite (locale, chiffrée)                | PostgreSQL                                |
| Déploiement             | Image Docker ARM64 via Jenkins + Ansible | Image Docker x86_64 via Jenkins           |

## 4. Sécurité (rappel des principes, détaillés en Epic 9)

- Embeddings biométriques chiffrés au repos (edge et central)
- Pas de stockage d'images brutes après extraction de l'embedding
- Communications Pi ↔ backend chiffrées (TLS)
- Purge automatique des données selon politique de rétention définie (AIPD)

## 5. Historique des décisions

| Date     | Décision                                | Raison                                                                                               |
|----------|-----------------------------------------|------------------------------------------------------------------------------------------------------|
| Sprint 0 | Architecture multi-sites confirmée      | Besoin de supervision centralisée sur plusieurs Raspberry Pi                                         |
| Sprint 0 | Caméra CSI officielle retenue (pas USB) | Meilleure intégration matérielle native au Pi                                                        |
| Sprint 0 | Inférence CPU pur pour la V1            | Pas de budget accélérateur matériel au démarrage ; benchmark prévu en Epic 6.2 avant décision finale |