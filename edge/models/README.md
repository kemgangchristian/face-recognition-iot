# Modeles ML

Les poids `.onnx` ne sont pas versionnes. L'image Docker les telecharge au build.

## Detection — YuNet

Fichier : `face_detection_yunet.onnx`  
Source : https://github.com/opencv/opencv_zoo  
Licence : Apache 2.0

```bash
curl -L -o edge/models/face_detection_yunet.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
```

## Embedding — SFace (livrable)

Fichier : `face_recognition_sface.onnx`  
Source : OpenCV Zoo  
Licence : Apache-2.0

```bash
curl -L -o edge/models/face_recognition_sface.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

SFace utilise `cv2.FaceRecognizerSF.alignCrop()`.

Apres enrolement (1 photo sans masque), calibre les seuils (cible : 0,1 % d'intrus) :

```bash
cd edge && python3 -m scripts.calibrate_threshold --site-dir captures/
```
