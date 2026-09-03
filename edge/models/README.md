# Modèles ML - Face Recognition IoT

Les fichiers de modèles (`.onnx`, `.tflite`) ne sont **pas versionnés dans Git**
(voir `.gitignore`) : trop lourds, et ce ne sont pas des fichiers source.
Ce document permet de les retélécharger à l'identique sur n'importe quelle machine.

## Détection de visage - YuNet

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

## Extraction d'embedding - MobileFaceNet

À documenter lors de l'Epic 2 (pas encore téléchargé à ce stade du projet).