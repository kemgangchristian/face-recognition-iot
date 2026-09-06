# Modèles ML — Face Recognition IoT

Les fichiers de modèles (`.onnx`, `.tflite`) ne sont **pas versionnés dans Git**
(voir `.gitignore`) : trop lourds, et ce ne sont pas des fichiers source.
Ce document permet de les retélécharger à l'identique sur n'importe quelle machine.

## Détection de visage — YuNet

- **Fichier** : `face_detection_yunet.onnx`
- **Source officielle** : [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo)
- **Licence** : Apache 2.0
- **Commande de téléchargement** :

```bash
curl -L -o edge/models/face_detection_yunet.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
```

- **Utilisé dans** : `edge/src/detection/`
- **Date d'ajout au projet** : Sprint 3-4 (Epic 1, Story 1.2)

## Extraction d'embedding — SFace

- **Fichier** : `face_recognition_sface.onnx`
- **Source officielle** : [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo)
- **Licence** : Apache-2.0 (permissive, utilisable commercialement)
- **Commande de téléchargement** :

```bash
curl -L -o edge/models/face_recognition_sface.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

- **Utilisé dans** : `edge/src/recognition/`
- **Date d'ajout au projet** : Sprint 5-6 (Epic 2, Story 2.3)
- **Note** : ce modèle a été choisi à la place de MobileFaceNet (InsightFace),
  écarté pour incompatibilité de licence (recherche non-commerciale uniquement).
  Voir `docs/architecture.md`, section historique des décisions, pour le détail.
- **Alignement** : ne pas utiliser `edge/src/recognition/face_aligner.py` pour ce
  modèle — utiliser la méthode native `cv2.FaceRecognizerSF.alignCrop()`, qui
  garantit un préprocessing exactement compatible avec SFace. `face_aligner.py`
  est conservé comme utilitaire générique, réutilisable si un autre modèle
  d'embedding est adopté plus tard.