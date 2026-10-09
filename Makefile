# Commandes du site (Pi ou machine de dev).
# make help

CONTAINER ?= face-recognition-api
IMAGE     ?= face-recognition-edge:latest
VOLUME    ?= face-recognition-data
SITE_DIR  ?= captures
EDGE      := edge

.PHONY: help test models run-local stop start restart logs run-pi \
	reset-db reset-db-docker capture calibrate calibrate-docker

help:
	@echo "Tests et modeles"
	@echo "  make test                 pytest (edge/tests, sans tests manuels)"
	@echo "  make models               telecharge YuNet + SFace dans edge/models"
	@echo ""
	@echo "API locale (hors Docker)"
	@echo "  make run-local            uvicorn sur :8000 (depuis edge/)"
	@echo "  make capture              photos genuine/impostors (webcam, API arretee)"
	@echo "  make calibrate            seuils 0,1 % d'intrus (SITE_DIR=$(SITE_DIR))"
	@echo "  make reset-db             vide identites et logs (API arretee, --yes)"
	@echo ""
	@echo "Conteneur Pi"
	@echo "  make run-pi               cree/relance le conteneur + volume $(VOLUME)"
	@echo "  make stop / start / restart / logs"
	@echo "  make calibrate-docker     copie $(SITE_DIR) dans le conteneur, calibre, restart"
	@echo "  make reset-db-docker      vide la base du volume Docker"
	@echo ""
	@echo "Ne pas utiliser docker rm a la main si tu veux garder enrolements et seuils."

test:
	cd $(EDGE) && python3 -m pytest tests/ -q

models:
	mkdir -p $(EDGE)/models
	curl -L -o $(EDGE)/models/face_detection_yunet.onnx \
	  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
	curl -L -o $(EDGE)/models/face_recognition_sface.onnx \
	  https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

run-local:
	cd $(EDGE) && python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

stop:
	docker stop $(CONTAINER)

start:
	docker start $(CONTAINER)

restart:
	docker restart $(CONTAINER)

logs:
	docker logs -f $(CONTAINER)

# Volume nomme : enrolements et thresholds.json survivent a un recreer du conteneur.
run-pi:
	docker stop $(CONTAINER) 2>/dev/null || true
	docker rm $(CONTAINER) 2>/dev/null || true
	docker volume create $(VOLUME)
	docker run -d \
	  --name $(CONTAINER) \
	  --restart unless-stopped \
	  --privileged \
	  -p 8000:8000 \
	  -v /run/udev:/run/udev:ro \
	  -v $(VOLUME):/app/storage_data \
	  $(IMAGE)

reset-db:
	cd $(EDGE) && python3 -m scripts.reset_database --yes

reset-db-docker:
	docker exec -w /app $(CONTAINER) python3 -m scripts.reset_database --yes --storage-dir /app/storage_data
	docker restart $(CONTAINER)

capture:
	cd $(EDGE) && python3 -m scripts.capture_local

calibrate:
	cd $(EDGE) && python3 -m scripts.calibrate_threshold --site-dir $(SITE_DIR)

calibrate-docker:
	test -d $(SITE_DIR) || (echo "Dossier $(SITE_DIR) introuvable." && exit 1)
	docker start $(CONTAINER)
	docker cp $(SITE_DIR)/. $(CONTAINER):/tmp/captures
	docker exec -w /app $(CONTAINER) python3 -m scripts.calibrate_threshold --site-dir /tmp/captures
	docker restart $(CONTAINER)
