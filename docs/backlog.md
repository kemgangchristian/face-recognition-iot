# Backlog — Système de Reconnaissance Faciale Edge/IoT (Raspberry Pi)

## Hypothèses d'architecture retenues
- **Edge (Raspberry Pi)** : capture, détection, reconnaissance, décision temps réel, cache local **SQLite**
- **Backend central (cloud/serveur)** : supervision multi-sites, historique, dashboard, **PostgreSQL**
- **CI/CD** : Jenkins (build multi-arch ARM64, tests, déploiement)
- **Méthodologie** : Scrum/Agile, sprints de 2 semaines, découpage fonction par fonction, fichier par fichier

Si le projet est finalement **mono-site sans backend central**, l'Epic 7 (Backend & Supervision) et les stories liées à la synchronisation peuvent être retirées ou reportées en fin de roadmap.

---

## EPIC 0 — Cadrage & Setup Projet

**Objectif** : poser les fondations techniques et organisationnelles avant tout développement fonctionnel.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 0.1 | En tant qu'équipe dev, je veux une structure de repo standardisée afin de garantir la cohérence du code entre les membres | Arborescence définie (`/edge`, `/backend`, `/infra`, `/tests`, `/docs`) ; README avec conventions de nommage |
| 0.2 | En tant que dev, je veux un environnement Docker reproductible pour le Raspberry Pi afin d'éviter les problèmes "ça marche chez moi" | Dockerfile `linux/arm64` fonctionnel ; build local réussi sur Pi 4/5 |
| 0.3 | En tant que dev, je veux un environnement Docker pour le backend (Postgres + API) afin de développer sans dépendre du matériel physique | `docker-compose.yml` avec service Postgres + service API mockée |
| 0.4 | En tant que Scrum Master, je veux un board Jira/GitHub Projects avec les epics importés afin de piloter les sprints | Board créé, epics + stories priorisées, DoD (Definition of Done) documentée |
| 0.5 | En tant qu'équipe, je veux un pipeline Jenkins minimal (hello world) afin de valider la connexion repo → Jenkins avant d'ajouter la complexité | Job Jenkins déclenché sur push, build passant, logs visibles |
| 0.6 | En tant que Product Owner, je veux une charte de conformité RGPD/biométrie documentée dès le départ afin de cadrer les choix techniques futurs | Document validé : base légale, durée de rétention, minimisation des données |

---

## EPIC 1 — Capture Vidéo & Détection de Visage (Edge)
**Statut : Terminé (sauf Story 1.4, bloquée — nécessite Raspberry Pi configuré avec caméra CSI)**

**Objectif** : obtenir un flux vidéo exploitable et détecter les visages en temps réel sur le Pi.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 1.1 | En tant que système, je veux capturer un flux vidéo depuis la caméra du Pi (CSI ou USB) afin d'avoir une source d'images à traiter | Flux stable ≥ 15 FPS affiché/loggé ; gestion des deux types de caméra |
| 1.2 | En tant que système, je veux détecter les visages présents dans chaque frame afin d'isoler les zones à analyser | Modèle YuNet/BlazeFace intégré ; bounding boxes retournées avec score de confiance |
| 1.3 | En tant que système, je veux filtrer les détections de faible qualité (flou, trop petit, angle extrême) afin d'éviter des extractions inutiles en aval | Seuils configurables (taille min, score min) ; frames rejetées loggées |
| 1.4 | En tant que dev, je veux benchmarker la latence de détection sur Pi réel afin de valider que le modèle choisi respecte le budget temps réel | Rapport de perf (ms/frame, CPU%, température) sur Pi 4 et Pi 5 |
| 1.5 | En tant que système, je veux gérer plusieurs visages simultanés dans une même frame afin de supporter les scénarios multi-personnes | Test avec 2-5 visages simultanés, toutes les boxes détectées correctement |

---

## EPIC 2 — Alignement & Extraction d'Embedding (Edge)

**Objectif** : transformer chaque visage détecté en une signature numérique exploitable pour la reconnaissance.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 2.1 | En tant que système, je veux extraire les landmarks faciaux (5 ou 68 points) afin de préparer l'alignement | Landmarks extraits pour chaque visage détecté, cohérents visuellement |
| 2.2 | En tant que système, je veux aligner le visage (rotation/normalisation) afin d'améliorer la précision de l'embedding | Transformation affine appliquée ; visage recadré à taille standard (ex: 112x112) |
| 2.3 | En tant que système, je veux générer un embedding via MobileFaceNet (TFLite/ONNX) afin d'obtenir une représentation vectorielle unique du visage | Vecteur de dimension fixe (ex: 128 ou 512) retourné par visage aligné |
| 2.4 | En tant que dev, je veux quantifier le modèle (INT8) afin de réduire la taille et la latence sur le Pi | Modèle quantifié < 10 Mo ; perte de précision mesurée et documentée |
| 2.5 | En tant que dev, je veux benchmarker le temps total détection + alignement + embedding afin de valider le budget de latence global (< 500ms) | Rapport de perf end-to-end sur Pi réel |

---

## EPIC 3 — Enrôlement & Base de Visages (Edge)

**Objectif** : permettre l'ajout et la gestion des identités connues localement.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 3.1 | En tant qu'administrateur, je veux enrôler une nouvelle personne (capture + embedding + métadonnées) afin de l'ajouter à la base de reconnaissance | Fonction d'enrôlement testée, embedding + identité stockés en SQLite |
| 3.2 | En tant qu'administrateur, je veux capturer plusieurs poses lors de l'enrôlement afin d'améliorer la robustesse de la reconnaissance | Minimum 3-5 captures par personne, embeddings moyennés ou stockés individuellement |
| 3.3 | En tant qu'administrateur, je veux supprimer une identité de la base afin de respecter le droit à l'effacement (RGPD) | Suppression effective des embeddings + logs associés, testée |
| 3.4 | En tant que système, je veux chiffrer les embeddings stockés localement afin de protéger les données biométriques | Chiffrement au repos (ex: SQLCipher ou chiffrement applicatif) validé |
| 3.5 | En tant que dev, je veux structurer le schéma SQLite (identités, embeddings, logs) afin de garantir cohérence et évolutivité | Schéma documenté, migrations versionnées |

---

## EPIC 4 — Matching & Reconnaissance (Edge)

**Objectif** : comparer un visage capturé à la base connue et rendre une décision.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 4.1 | En tant que système, je veux comparer un embedding capturé à la base locale via similarité cosinus afin d'identifier la personne | Fonction de matching retourne identité + score de confiance |
| 4.2 | En tant que système, je veux intégrer FAISS pour la recherche vectorielle afin de garder de bonnes performances si la base grandit | Recherche testée avec bases de 100, 1000, 5000 identités ; temps de réponse mesuré |
| 4.3 | En tant qu'administrateur, je veux définir un seuil de confiance configurable afin d'ajuster le compromis faux positifs/faux négatifs | Seuil paramétrable en config, testé sur jeu de données de validation |
| 4.4 | En tant que système, je veux gérer le cas "visage inconnu" afin d'éviter les faux positifs sur des personnes non enrôlées | Cas testé explicitement avec dataset de visages non enrôlés |
| 4.5 | En tant que Product Owner, je veux un rapport de précision (FAR/FRR — taux de faux acceptation/rejet) afin de valider la fiabilité du système avant mise en production | Rapport chiffré sur dataset de test représentatif |

---

## EPIC 5 — Orchestration & API Locale (Edge)

**Objectif** : exposer les fonctionnalités du Pi à d'autres systèmes (badgeuse, alarme, dashboard local).

| # | User Story | Critères d'acceptation |
|---|---|---|
| 5.1 | En tant que dev, je veux une API FastAPI exposant les endpoints enrôlement/vérification/santé afin d'intégrer le module à un système externe | Endpoints `/enroll`, `/verify`, `/health` fonctionnels, documentés (OpenAPI) |
| 5.2 | En tant que système, je veux publier les événements (accès autorisé/refusé) via MQTT afin de notifier les systèmes tiers en temps réel | Broker MQTT configuré, messages publiés testés avec un client abonné |
| 5.3 | En tant qu'administrateur, je veux consulter les logs d'accès localement afin d'auditer l'activité sans dépendre du cloud | Logs consultables via endpoint ou fichier structuré, horodatés |
| 5.4 | En tant que dev, je veux gérer les erreurs et cas limites (pas de visage, caméra déconnectée, base corrompue) afin de garantir la robustesse en production | Tests unitaires couvrant les cas d'erreur principaux |

---

## EPIC 6 — Optimisation Edge & Robustesse

**Objectif** : garantir que le système tourne de façon stable et performante sur le matériel cible réel.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 6.1 | En tant que dev, je veux mesurer la consommation CPU/RAM/température en fonctionnement continu afin d'anticiper le throttling thermique | Rapport de charge sur 24h de fonctionnement continu |
| 6.2 | En tant que dev, je veux tester l'ajout d'un accélérateur (Coral Edge TPU ou Hailo-8) afin d'évaluer le gain de performance | Comparatif latence avec/sans accélérateur, décision go/no-go documentée |
| 6.3 | En tant que système, je veux redémarrer automatiquement les services en cas de crash afin de garantir la disponibilité | Supervisor/systemd configuré, testé avec kill forcé du processus |
| 6.4 | En tant que dev, je veux gérer le fonctionnement hors ligne complet afin que le Pi continue de fonctionner sans connexion réseau | Test en coupant le réseau : enrôlement/vérification toujours fonctionnels |

---

## EPIC 7 — Backend Central & Supervision (PostgreSQL)

**Objectif** : centraliser la supervision multi-sites (à activer seulement si architecture multi-Pi confirmée).

| # | User Story | Critères d'acceptation |
|---|---|---|
| 7.1 | En tant que dev, je veux un schéma PostgreSQL pour identités, sites, logs afin de centraliser les données multi-sites | Schéma versionné (migrations Alembic/Flyway), relations normalisées |
| 7.2 | En tant que système, je veux synchroniser les logs d'accès du Pi vers le backend central afin de permettre la supervision globale | Sync testée en connexion continue et en reprise après coupure réseau |
| 7.3 | En tant qu'administrateur, je veux un dashboard web affichant les accès en temps réel multi-sites afin de superviser l'ensemble du parc | Dashboard fonctionnel (liste des accès, filtrage par site/date) |
| 7.4 | En tant qu'administrateur, je veux gérer les identités de façon centralisée et les propager vers les Pi concernés afin d'éviter la ressaisie manuelle | Propagation testée vers au moins 2 devices edge simulés |
| 7.5 | En tant que RSSI, je veux que les échanges Pi ↔ backend soient chiffrés (TLS) et authentifiés afin de sécuriser les données biométriques en transit | Certificats configurés, connexion non chiffrée refusée |

---

## EPIC 8 — CI/CD avec Jenkins

**Objectif** : automatiser build, tests et déploiement pour l'edge et le backend.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 8.1 | En tant que dev, je veux un pipeline Jenkins qui lance les tests unitaires à chaque push afin de détecter les régressions rapidement | Pipeline déclenché sur PR, tests exécutés, statut visible dans le repo |
| 8.2 | En tant que dev, je veux un stage Jenkins de build Docker multi-architecture (ARM64) afin de produire une image déployable sur Pi | Image buildée et poussée sur un registry (ex: GitHub Container Registry) |
| 8.3 | En tant que dev, je veux un stage de build pour le backend (image x86_64) afin de séparer les pipelines edge/backend | Deux pipelines distincts ou un pipeline paramétré par target |
| 8.4 | En tant que Product Owner, je veux un stage de tests d'intégration avant déploiement afin d'éviter les régressions fonctionnelles en production | Suite de tests d'intégration (API, matching) exécutée en pipeline |
| 8.5 | En tant qu'administrateur, je veux un déploiement automatisé vers les Pi via Jenkins (SSH/Ansible) afin d'éviter les mises à jour manuelles sur site | Déploiement testé sur au moins un Pi physique, rollback possible |
| 8.6 | En tant que RSSI, je veux que les secrets (clés, credentials DB) soient gérés via Jenkins Credentials/Vault afin de ne jamais les exposer en clair dans le code | Aucun secret en dur dans le repo, scan de sécurité en pipeline |

---

## EPIC 9 — Sécurité & Conformité RGPD

**Objectif** : garantir la conformité légale et la sécurité des données biométriques sur l'ensemble du cycle de vie.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 9.1 | En tant que DPO, je veux une politique de rétention des données définie et appliquée automatiquement afin de respecter la minimisation des données | Purge automatique des logs/images après délai configuré, testée |
| 9.2 | En tant qu'utilisateur enrôlé, je veux pouvoir demander la suppression de mes données afin d'exercer mon droit RGPD | Procédure documentée + fonction technique de suppression (cf. 3.3) |
| 9.3 | En tant que RSSI, je veux un audit de sécurité (pentest léger) sur l'API et le pipeline avant mise en production afin d'identifier les vulnérabilités | Rapport d'audit, vulnérabilités critiques corrigées |
| 9.4 | En tant que Product Owner, je veux une analyse d'impact relative à la protection des données (AIPD/DPIA) afin de documenter la conformité légale du traitement biométrique | Document AIPD complété et validé (souvent obligatoire pour la biométrie) |

---

## EPIC 10 — Packaging & Mise en Production

**Objectif** : livrer un produit installable et documenté pour un déploiement client/site réel.

| # | User Story | Critères d'acceptation |
|---|---|---|
| 10.1 | En tant qu'intégrateur, je veux une image Pi préconfigurée (flashable) afin de simplifier le déploiement sur site | Image `.img` générée, testée sur Pi neuf |
| 10.2 | En tant qu'administrateur, je veux une documentation d'installation et d'exploitation afin de pouvoir opérer le système sans l'équipe dev | Guide installation + guide utilisateur rédigés |
| 10.3 | En tant que Product Owner, je veux un plan de montée en charge (combien de Pi supportés par le backend) afin d'anticiper la croissance | Test de charge backend documenté (ex: 50, 100, 500 devices simulés) |
| 10.4 | En tant qu'équipe support, je veux une procédure de mise à jour à distance des modèles IA afin de déployer des améliorations sans intervention physique | Procédure testée : nouveau modèle poussé et actif sur Pi distant |

---

## Ordre de priorisation suggéré (roadmap sprints)

1. **Sprint 1-2** : Epic 0 (setup complet)
2. **Sprint 3-4** : Epic 1 (capture + détection)
3. **Sprint 5-6** : Epic 2 (alignement + embedding)
4. **Sprint 7-8** : Epic 3 + Epic 4 (enrôlement + matching) — cœur fonctionnel, premier MVP démontrable ici
5. **Sprint 9** : Epic 5 (API + orchestration)
6. **Sprint 10** : Epic 8 partiel (CI/CD de base pour sécuriser la suite)
7. **Sprint 11-12** : Epic 6 (optimisation edge réelle sur matériel)
8. **Sprint 13-14** : Epic 7 (backend central Postgres) — *si architecture multi-sites confirmée*
9. **Sprint 15** : Epic 9 (sécurité/RGPD) — en réalité à traiter en continu dès le Sprint 1, pas en fin de projet
10. **Sprint 16** : Epic 10 (packaging/prod)

> Note méthodo : l'Epic 9 (RGPD/sécurité) est placé en fin de liste ici pour la lisibilité du document, mais dans la pratique les stories 9.1, 9.2 et 9.4 doivent être traitées **dès les premiers sprints**, en parallèle du développement — pas en fin de projet.
