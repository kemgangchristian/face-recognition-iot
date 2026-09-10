#!/bin/bash
# Lance le conteneur edge sur Raspberry Pi avec accès caméra CSI complet.
# --privileged : accès matériel complet (device-tree, /dev/video*, /dev/media*, vchiq)
# -v /run/udev : nécessaire pour que libcamera identifie les périphériques caméra
#                (sans udev monté, les device nodes existent mais ne sont pas
#                reconnus comme des caméras par libcamera)

docker stop face-recognition-api 2>/dev/null
docker rm face-recognition-api 2>/dev/null

docker run -d \
  --name face-recognition-api \
  --restart unless-stopped \
  --privileged \
  -p 8000:8000 \
  -v /run/udev:/run/udev:ro \
  face-recognition-edge:latest
