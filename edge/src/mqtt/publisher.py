"""
Publication d'événements de reconnaissance via MQTT.
Story 5.2 — Epic 5.
"""

import json
from datetime import datetime, timezone
import paho.mqtt.client as mqtt


class EventPublisher:
    """Publie les événements de reconnaissance (accès autorisé/refusé) sur
    un broker MQTT, pour notification en temps réel de systèmes tiers."""

    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883, site_id: str = "site_default"):
        """
        Args:
            broker_host: adresse du broker MQTT.
            broker_port: port du broker (1883 = standard non chiffré).
            site_id: identifiant du site, utilisé dans le topic pour la
                     future architecture multi-sites (Epic 7).
        """
        self.site_id = site_id
        self.topic = f"face-recognition/{site_id}/events"

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.connect(broker_host, broker_port)
        self._client.loop_start()  # gère la connexion en arrière-plan (thread dédié)

    def publish_verification_event(self, matched: bool, full_name: str = None, confidence: float = 0.0) -> None:
        """
        Publie un événement de tentative de reconnaissance.

        Args:
            matched: True si une identité a été reconnue.
            full_name: nom de la personne reconnue, ou None si inconnu.
            confidence: score de confiance du matching.
        """
        payload = {
            "event": "verification",
            "matched": matched,
            "full_name": full_name,
            "confidence": round(confidence, 4),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "site_id": self.site_id,
        }

        self._client.publish(self.topic, json.dumps(payload))

    def close(self) -> None:
        """Ferme proprement la connexion au broker."""
        self._client.loop_stop()
        self._client.disconnect()
        