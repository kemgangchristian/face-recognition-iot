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

### Extraction d'embedding — SFace (OpenCV Zoo)
Alternative écartée : MobileFaceNet via InsightFace (licence recherche non-commerciale
uniquement, incompatible avec un usage professionnel/commercial).
SFace provient du même dépôt officiel qu'YuNet (OpenCV Zoo), licence Apache-2.0
permissive, et est nativement supporté par OpenCV via `cv2.FaceRecognizerSF` —
conçu par l'équipe OpenCV pour fonctionner directement avec YuNet.

### Alignement pour l'embedding — `cv2.FaceRecognizerSF.alignCrop()`
Le module maison `edge/src/recognition/face_aligner.py` (Story 2.2) utilise des
positions de référence génériques de type ArcFace/InsightFace, adaptées à
MobileFaceNet — pas garanties compatibles avec le préprocessing attendu par SFace.
Pour l'extraction d'embedding réelle, on utilise donc `alignCrop()`, natif à
`FaceRecognizerSF`, qui garantit un alignement exactement conforme à
l'entraînement du modèle. `face_aligner.py` est conservé comme utilitaire
générique et réutilisable (déjà testé visuellement), au cas où un autre modèle
d'embedding serait adopté plus tard.

### Moteur d'inférence — TensorFlow Lite / OpenCV DNN
Pour YuNet et SFace, l'inférence passe directement par le module DNN natif
d'OpenCV (`cv2.FaceDetectorYN`, `cv2.FaceRecognizerSF`) — pas besoin de
TensorFlow Lite ou ONNX Runtime séparés pour ces deux modèles spécifiquement.
TensorFlow Lite reste l'option de référence si un futur modèle (ex: modèle de
classification additionnel) nécessite un moteur d'inférence dédié.

### Stockage edge — SQLite (chiffré)
Alternative écartée : PostgreSQL en local sur le Pi (inutile : consomme des
ressources pour rien sur un device à ressources limitées, sans bénéfice
puisque le Pi fonctionne en autonome).
SQLite = zéro dépendance serveur, fonctionnement garanti hors-ligne.

### Stockage central — PostgreSQL
Utilisé uniquement côté backend (serveur), pour la supervision multi-sites :
requêtes relationnelles complexes, gestion de la concurrence multi-Pi, reporting.

### Recherche vectorielle — FAISS (mode CPU)
Alternative écartée : vector DB serveur (Milvus, Qdrant) — trop lourd pour un
device isolé. FAISS tourne en mémoire locale, suffisant jusqu'à plusieurs
milliers d'identités enrôlées.

## 3. Séparation edge / backend

| Aspect | Edge (Raspberry Pi) | Backend central |
|---|---|---|
| Architecture matérielle | ARM64 | x86_64 |
| Rôle | Traitement temps réel, décision locale | Supervision, audit, propagation identités |
| Dépendance réseau | Aucune pour fonctionner | Requise pour la synchronisation |
| Base de données | SQLite (locale, chiffrée) | PostgreSQL |
| Déploiement | Image Docker ARM64 via Jenkins + Ansible | Image Docker x86_64 via Jenkins |

## 4. Sécurité (rappel des principes, détaillés en Epic 9)

- Embeddings biométriques chiffrés au repos (edge et central)
- Pas de stockage d'images brutes après extraction de l'embedding
- Communications Pi ↔ backend chiffrées (TLS)
- Purge automatique des données selon politique de rétention définie (AIPD)

## 5. Historique des décisions

| Date | Décision | Raison |
|---|---|---|
| Sprint 0 | Architecture multi-sites confirmée | Besoin de supervision centralisée sur plusieurs Raspberry Pi |
| Sprint 0 | Caméra CSI officielle retenue (pas USB) | Meilleure intégration matérielle native au Pi |
| Sprint 0 | Inférence CPU pur pour la V1 | Pas de budget accélérateur matériel au démarrage ; benchmark prévu en Epic 6.2 avant décision finale |
| Sprint 3-4 | Seuil de netteté (QualityFilter) fixé à 5.0 sur webcam Mac | Valeur empirique mesurée en conditions réelles (webcam laptop compressée) ; à recalibrer sur caméra CSI Pi en Story 1.4, capteur/pipeline différents |
| Sprint 5-6 | Léger tremblement visuel du crop aligné accepté sans lissage temporel | Sans impact sur la qualité d'embedding (extraction frame par frame indépendante) ; lissage temporel des landmarks noté comme amélioration facultative future |
| Sprint 5-6 | MobileFaceNet (InsightFace) écarté, SFace adopté | Licence InsightFace = recherche non-commerciale uniquement (bloquant pour usage professionnel). SFace = même dépôt officiel qu'YuNet (OpenCV Zoo), licence Apache-2.0 permissive |
| Sprint 5-6 | Alignement pour l'embedding via `cv2.FaceRecognizerSF.alignCrop()` natif, pas via `FaceAligner` maison | Garantit la compatibilité exacte avec le préprocessing attendu par SFace ; `FaceAligner` conservé comme utilitaire générique réutilisable |
| Sprint 5-6 | Validation empirique SFace : score ~0.8-1.0 même personne, ~0.2-0.6 personnes différentes (webcam Mac) | Bonne séparation, confirme la fiabilité du modèle ; seuil de décision définitif à calibrer rigoureusement en Story 4.3 avec un vrai jeu de test |
| Sprint 9 | Connexion SQLite partagée protégée par threading.Lock dans l'API | FastAPI exécute chaque requête dans un thread du pool ; SQLite refuse par défaut le partage inter-thread d'une connexion. Solution pragmatique adaptée au faible volume edge ; une architecture haute-concurrence utiliserait plutôt un pool de connexions |
| Sprint 10 | Pipeline Jenkins fonctionnel : Docker agent (python:3.11-slim-bookworm), 12 tests automatisés passent | Jenkins existant réutilisé (multi-projets) ; job dédié `face-recognition-iot` créé ; correction format version opencv-python (5.0.0 -> 5.0.0.93) |
| Sprint 11-12 | Support caméra CSI Pi via rpicam-still (subprocess) plutôt que picamera2 | picamera2 est lié à la version Python système du Pi (3.13), incompatible avec notre 3.11.9 (pyenv) utilisé sur tout le projet. Un exécutable externe appelé en sous-processus n'a aucune dépendance à la version Python appelante. Compromis : léger overhead de warm-up par capture, à mesurer en Story 1.4 |
| Sprint 11-12 | Benchmark Pi réel (Story 1.4) : capture rpicam-still ~1065ms, détection YuNet ~76ms, filtre qualité <1ms, embedding SFace ~67ms — total ~1200ms | Capture domine à 88% du temps total, mesure stable sur 2 runs (écart <1%). Latence totale > objectif initial (<500ms) posé en Sprint 0. Optimisation nécessaire avant mise en production réelle |
| Sprint 11-12 | Capture Pi optimisée : rpicam-vid en flux continu (thread arrière-plan) remplace rpicam-still par-frame | Latence capture réduite de ~1069ms à ~0.4ms (gain ~2600x). Pipeline total : ~1213ms -> ~212ms, sous l'objectif de 500ms fixé en Sprint 0 |
