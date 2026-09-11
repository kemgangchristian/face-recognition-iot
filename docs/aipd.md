# Analyse d'Impact relative à la Protection des Données (AIPD)
## Système de reconnaissance faciale IoT — Face Recognition IoT

**Statut du document** : Version 1.0 — Brouillon initial à valider avec un DPO (Délégué à la Protection des Données) ou un juriste spécialisé avant toute mise en production réelle.

**Méthodologie** : cette AIPD suit la structure recommandée par la CNIL (Commission Nationale de l'Informatique et des Libertés) — référence reconnue en matière d'analyse d'impact RGPD.

**Contexte du changement de portée** : ce document est rédigé suite à la décision de faire évoluer ce projet d'un cadre personnel/familial (couvert par l'exemption RGPD "activité domestique", article 2§2c) vers un cadre commercial/professionnel, qui ne bénéficie plus de cette exemption et impose les pleines obligations du RGPD, notamment pour les données biométriques (catégorie particulière, article 9).

---

## Partie 1 — Description du traitement

### 1.1 Finalité du traitement

Identification automatisée de personnes par reconnaissance faciale, dans le but de :
- Contrôler l'accès physique à un site, un local, ou une zone restreinte
- Journaliser les entrées/sorties à des fins de sécurité et d'audit

**Finalités explicitement exclues** (à ne jamais ajouter sans nouvelle analyse) : profilage comportemental, revente de données, surveillance à des fins autres que le contrôle d'accès déclaré, réutilisation des visages à des fins d'entraînement de modèles tiers.

### 1.2 Nature des données traitées

| Donnée | Nature | Catégorie RGPD |
|---|---|---|
| Embedding facial (vecteur 128 dimensions) | Donnée biométrique dérivée d'une image de visage | **Catégorie particulière (Art. 9)** — traitement interdit par défaut, sauf exception applicable |
| Nom complet de la personne enrôlée | Donnée d'identification directe | Donnée à caractère personnel standard |
| Horodatage des accès (autorisé/refusé) | Donnée d'activité | Donnée à caractère personnel standard |
| Score de confiance de la reconnaissance | Métadonnée technique | Donnée à caractère personnel standard (liée à une personne identifiée) |
| Site d'enrôlement (`site_id`) | Métadonnée organisationnelle | Non-personnelle en soi, mais contextualise une donnée personnelle |

**Base légale envisagée pour le traitement biométrique** (Art. 9§2) : **consentement explicite** de la personne concernée (Art. 9§2a) est la base la plus adaptée pour un contrôle d'accès en entreprise, sous réserve qu'une alternative non-biométrique reste proposée (voir 2.3). L'intérêt légitime de l'employeur seul est généralement jugé insuffisant par la CNIL pour ce type de traitement sans consentement, sauf contexte de sécurité renforcée démontrable (établissement sensible).

### 1.3 Personnes concernées

- Employés du site déployant le système
- Visiteurs, prestataires, ou toute personne physique amenée à accéder au site contrôlé

**Point d'attention majeur** : contrairement au contexte personnel initial, les personnes concernées en entreprise n'ont pas nécessairement de lien de confiance équivalent avec l'opérateur du système — le consentement doit être **libre**, ce qui est délicat dans une relation employeur/employé (déséquilibre de pouvoir reconnu par la CNIL). Une alternative doit impérativement être proposée pour ne pas vicier le consentement (ex : badge physique).

### 1.4 Description technique du système

- **Capture** : caméra CSI sur Raspberry Pi, traitement local (edge)
- **Détection** : YuNet (OpenCV, licence Apache-2.0)
- **Extraction d'embedding** : SFace (OpenCV, licence Apache-2.0)
- **Stockage local** : SQLite, embeddings chiffrés au repos (AES/Fernet)
- **Décision** : matching local par similarité cosinus, seuil configurable
- **Infrastructure** : conteneur Docker, déploiement automatisé via Jenkins/GitHub Container Registry
- **Réseau** : aucune dépendance Internet pour la reconnaissance elle-même (fonctionnement autonome validé, Story 6.4)

### 1.5 Durées de conservation envisagées

| Donnée | Durée proposée | Justification |
|---|---|---|
| Embedding + identité (personne active) | Durée du contrat/de la relation + suppression immédiate sur demande | Nécessaire uniquement tant que l'accès doit être autorisé |
| Logs d'accès (`access_logs`) | 1 à 3 mois maximum (à trancher selon le secteur) | Finalité d'audit sécurité à court terme ; conservation longue non justifiée sans contexte légal spécifique (ex : obligation sectorielle) |
| Logs après suppression d'identité | Anonymisés (identity_id → NULL), conservés indéfiniment à des fins statistiques uniquement | Cohérent avec le choix technique déjà fait (`ON DELETE SET NULL`, Story 3.3) |

**Action requise avant production** : fixer une durée précise et documentée, puis implémenter la purge automatique (Story 9.1, à faire).

---

## Partie 2 — Évaluation des principes fondamentaux

### 2.1 Proportionnalité et nécessité

**Question centrale à trancher avant tout déploiement** : la reconnaissance faciale est-elle réellement nécessaire, ou un moyen moins intrusif (badge, code, empreinte digitale) suffirait-il ?

La CNIL est explicitement restrictive sur la biométrie en contexte professionnel — elle recommande de réserver ce type de dispositif aux cas où un niveau de sécurité élevé est **objectivement justifié** (zones sensibles, données classifiées), pas comme solution de confort pour un contrôle d'accès standard.

**Recommandation** : documenter formellement, avant déploiement, pourquoi une solution non-biométrique ne suffit pas pour le cas d'usage visé.

### 2.2 Minimisation des données

- Seul l'embedding est conservé, jamais l'image brute du visage (Story 3, principe déjà appliqué)
- Pas de données superflues collectées (âge, genre, émotions — non extraites par notre pipeline)
- À faire : purge automatique selon durée de conservation définie (Story 9.1)

### 2.3 Consentement et alternative non-biométrique

**Exigence CNIL stricte** : toute personne doit pouvoir refuser la biométrie sans conséquence négative sur son accès aux locaux ou son emploi. Une alternative doit exister (badge, code PIN).

**Action requise avant production** : prévoir et documenter ce mécanisme alternatif — actuellement absent du système technique (Story à créer si le projet avance en ce sens).

### 2.4 Droits des personnes concernées

| Droit RGPD | Statut technique actuel |
|---|---|
| Droit d'accès | Non implémenté (endpoint permettant à une personne de consulter ses propres logs) |
| Droit de rectification | Non implémenté (modification du nom associé à une identité) |
| Droit à l'effacement | Implémenté (Story 3.3, suppression en cascade) |
| Droit à la portabilité | Non applicable/non implémenté (peu pertinent pour un embedding biométrique) |
| Droit d'opposition | Dépend du mécanisme de consentement à mettre en place (2.3) |

### 2.5 Information des personnes concernées

**Obligation légale** : chaque personne enrôlée doit recevoir, avant son enrôlement, une information claire sur : la finalité du traitement, la base légale, la durée de conservation, ses droits, et les coordonnées du responsable de traitement / DPO.

**Statut actuel** : ⏳ Aucune notice d'information n'existe. À rédiger avant tout déploiement réel (document séparé recommandé, pas dans ce fichier technique).

---

## Partie 3 — Évaluation des risques

### Méthodologie
Pour chaque risque : **Sources**, **Impact potentiel**, **Vraisemblance** (Négligeable/Limitée/Importante/Maximale), **Gravité** (idem), **Mesures existantes**, **Mesures complémentaires recommandées**.

### Risque 1 — Accès illégitime aux données biométriques

- **Sources de risque** : vol du Raspberry Pi, compromission du conteneur Docker, accès non autorisé à la base SQLite
- **Impact potentiel** : usurpation d'identité biométrique (contrairement à un mot de passe, un visage ne peut pas être "changé" après une fuite) — impact potentiellement **irréversible** pour la personne concernée
- **Vraisemblance** : Limitée (chiffrement en place, mais device physique accessible sur site)
- **Gravité** : Maximale (nature irréversible de la donnée biométrique compromise)
- **Mesures existantes** : chiffrement AES au repos (Story 3.4), clé de chiffrement séparée de la base, permissions fichier restreintes (0600)
- **Mesures complémentaires recommandées** :
  - Chiffrement du disque complet du Raspberry Pi (LUKS), pas seulement de la base
  - Stockage de la clé de chiffrement dans un module sécurisé (TPM/HSM) plutôt qu'en fichier local, si le budget le permet
  - Contrôle d'accès physique au boîtier du Pi (verrouillage, alarme si ouverture)

### Risque 2 — Modification non désirée des données

- **Sources de risque** : altération malveillante ou accidentelle de la base d'identités (ex : ajout d'une fausse identité autorisée)
- **Impact potentiel** : contournement du contrôle d'accès, accès non autorisé à des locaux physiques
- **Vraisemblance** : Négligeable à Limitée (API protégée, pas d'exposition publique directe démontrée à ce stade)
- **Gravité** : Importante (impact sécurité physique du site)
- **Mesures existantes** : API non exposée publiquement par défaut, réseau local
- **Mesures complémentaires recommandées** :
  - Authentification de l'API elle-même (actuellement absente — Story à créer, priorité élevée avant production)
  - Journalisation des modifications d'identités (qui a enrôlé/supprimé qui, quand)
  - Chiffrement TLS des communications si le système est un jour exposé au-delà du réseau local (cohérent avec Epic 7 si activé)

### Risque 3 — Disparition des données (perte de disponibilité)

- **Sources de risque** : panne matérielle du Pi, corruption de la carte SD, perte de la clé de chiffrement
- **Impact potentiel** : perte d'accès légitime pour les personnes enrôlées (impact opérationnel, pas de confidentialité)
- **Vraisemblance** : Limitée à Importante (matériel edge, cartes SD reconnues comme peu fiables sur la durée)
- **Gravité** : Limitée (récupérable par réenrôlement, pas de préjudice irréversible pour la personne)
- **Mesures existantes** : `--restart unless-stopped` (Story 6.3), image reconstructible via CI/CD
- **Mesures complémentaires recommandées** :
  - Sauvegarde régulière et chiffrée de la base de données (actuellement absente)
  - Sauvegarde séparée et sécurisée de la clé de chiffrement (perte de la clé = perte irrémédiable des données malgré leur présence physique)

---

## Partie 4 — Plan d'action et validation

### Actions requises avant toute mise en production commerciale

| # | Action | Priorité | Story associée |
|---|---|---|---|
| 1 | Définir et justifier la nécessité réelle de la biométrie vs alternative | **Bloquant** | Nouvelle story à créer |
| 2 | Mettre en place une alternative non-biométrique au contrôle d'accès | **Bloquant** | Nouvelle story à créer |
| 3 | Rédiger la notice d'information RGPD pour les personnes enrôlées | **Bloquant** | Nouvelle story à créer |
| 4 | Recueillir un consentement explicite, libre, et documenté | **Bloquant** | Nouvelle story à créer |
| 5 | Implémenter la purge automatique selon durée de conservation | Élevée | Story 9.1 |
| 6 | Ajouter l'authentification à l'API (actuellement absente) | ~~Élevée~~ **Traité** | Nouvelle story à créer |
| 7 | Chiffrement disque complet du Raspberry Pi (LUKS) | Élevée | Nouvelle story à créer |
| 8 | Sauvegarde chiffrée régulière de la base + clé | Moyenne | Nouvelle story à créer |
| 9 | Droit d'accès/rectification pour les personnes concernées | Moyenne | Nouvelle story à créer |
| 10 | Validation finale de cette AIPD par un DPO/juriste | **Bloquant** | — |

### Avertissement final

**Ce document a été rédigé par un système d'assistance IA dans le cadre d'un projet de développement technique, et ne constitue pas un conseil juridique.** Avant tout déploiement commercial réel impliquant de la biométrie, une validation par un Délégué à la Protection des Données (DPO) qualifié ou un avocat spécialisé en droit du numérique est **indispensable**, en particulier pour :
- Confirmer la base légale appropriée selon la juridiction exacte de déploiement
- Vérifier les obligations sectorielles spécifiques (certains secteurs ont des règles renforcées)
- Valider le mécanisme de consentement au regard de la jurisprudence CNIL/CJUE la plus récente
- Réaliser, le cas échéant, la consultation préalable de l'autorité de contrôle si l'AIPD révèle un risque résiduel élevé (Art. 36 RGPD)

---

**Historique des versions**
| Date | Version | Modification |
|---|---|---|
| Sprint 15 | 1.0 | Rédaction initiale suite au changement de contexte personnel -> commercial |