"""
Suivi positionnel minimal des visages d'une frame à l'autre.

Volontairement simple (recouvrement de bbox), adapté à un usage mono-visage
de porte d'accès. Pour plusieurs visages simultanés fréquents, remplacer par
un vrai tracker (centroïdes + association hongroise).

Sécurité : une personne autorisée ne doit pas pouvoir être « remplacée » par
une photo en conservant son autorisation. Le suivi est donc ROMPU (nouveau
numéro de suivi, donc cycle complet de reconnaissance + vivacité) dès que :
  - le visage a disparu plus de `max_gap_seconds` (main, photo qui passe devant) ;
  - sa taille change brutalement d'une frame à l'autre (`max_area_ratio`) ;
  - sa position saute brutalement (`max_center_shift_ratio`).
Aucun déplacement humain normal, à ~10 images/s, ne franchit ces seuils.
"""

import time


def bbox_iou(a, b) -> float:
    """Intersection sur union de deux bbox (x, y, w, h)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix0, iy0 = max(ax, bx), max(ay, by)
    ix1, iy1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    intersection = iw * ih
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


class FaceTracker:
    def __init__(
        self,
        iou_threshold: float = 0.3,
        timeout_seconds: float = 2.0,
        max_gap_seconds: float = 0.7,
        max_area_ratio: float = 1.8,
        max_center_shift_ratio: float = 0.5,
        clock=time.time,
    ):
        """
        Args:
            iou_threshold: recouvrement minimal pour associer une détection
                à un suivi existant.
            timeout_seconds: au-delà, un suivi non revu est supprimé (son
                état de reconnaissance/vivacité est alors libéré par l'appelant).
            max_gap_seconds: au-delà, un suivi non revu ne peut plus être
                repris (rupture de continuité).
            max_area_ratio: variation maximale de l'aire du visage entre
                deux frames consécutives (facteur, dans les deux sens).
            max_center_shift_ratio: déplacement maximal du centre entre deux
                frames, en proportion de la largeur du visage.
            clock: source de temps injectable (tests).
        """
        self.iou_threshold = iou_threshold
        self.timeout_seconds = timeout_seconds
        self.max_gap_seconds = max_gap_seconds
        self.max_area_ratio = max_area_ratio
        self.max_center_shift_ratio = max_center_shift_ratio
        self._clock = clock
        self._tracks: dict = {}  # track_id -> {"bbox": ..., "last_seen": ...}
        self._next_id = 0

    def _continuous(self, bbox, track: dict, now: float) -> bool:
        """La détection `bbox` peut-elle être la suite directe de ce suivi ?"""
        if now - track["last_seen"] > self.max_gap_seconds:
            return False

        x, y, w, h = bbox
        tx, ty, tw, th = track["bbox"]
        area, track_area = w * h, tw * th
        if area <= 0 or track_area <= 0:
            return False
        ratio = area / track_area
        if ratio > self.max_area_ratio or ratio < 1.0 / self.max_area_ratio:
            return False

        shift = ((x + w / 2 - tx - tw / 2) ** 2 + (y + h / 2 - ty - th / 2) ** 2) ** 0.5
        if shift > self.max_center_shift_ratio * max(w, tw):
            return False

        return bbox_iou(bbox, track["bbox"]) >= self.iou_threshold

    def update(self, detections: list) -> list:
        """
        Args:
            detections: liste de dicts (sortie de FaceDetector.detect()).

        Returns:
            liste de (track_id, detection) dans le même ordre que `detections`.
        """
        now = self._clock()

        stale = [tid for tid, t in self._tracks.items() if now - t["last_seen"] > self.timeout_seconds]
        for tid in stale:
            del self._tracks[tid]

        # Association gloutonne par recouvrement décroissant : un suivi ne
        # peut être attribué qu'à UNE détection par frame.
        candidates = []
        for det_index, det in enumerate(detections):
            for tid, track in self._tracks.items():
                if self._continuous(det["bbox"], track, now):
                    candidates.append((bbox_iou(det["bbox"], track["bbox"]), det_index, tid))
        candidates.sort(reverse=True)

        assigned_tracks: dict = {}   # det_index -> track_id
        used_tracks: set = set()
        for _, det_index, tid in candidates:
            if det_index in assigned_tracks or tid in used_tracks:
                continue
            assigned_tracks[det_index] = tid
            used_tracks.add(tid)

        result = []
        for det_index, det in enumerate(detections):
            tid = assigned_tracks.get(det_index)
            if tid is None:
                tid = self._next_id
                self._next_id += 1
            self._tracks[tid] = {"bbox": det["bbox"], "last_seen": now}
            result.append((tid, det))

        return result

    def active_track_ids(self) -> set:
        return set(self._tracks.keys())
        