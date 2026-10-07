"""
Commande de la gâche / du relais de porte.

Principes de sécurité :
  - PAR DÉFAUT, aucun relais n'est piloté (NullDoorActuator : journalise
    seulement). Le matériel n'est actionné que si DOOR_RELAY_GPIO_PIN est
    défini explicitement.
  - FAIL-CLOSED : toute erreur (bibliothèque GPIO absente, broche invalide,
    exception à l'activation) laisse la porte VERROUILLÉE ; l'actionneur
    retombe sur NullDoorActuator avec un message d'erreur visible.
  - Le déverrouillage est TOUJOURS temporisé (`unlock_seconds`) : la porte se
    reverrouille seule, même si le service plante juste après. Un nouvel
    accès pendant la temporisation la repousse, sans jamais la cumuler.

⚠️ La partie GPIO n'a pas pu être testée sur du vrai matériel (voir les tests
avec périphérique simulé). À valider avec un relais réel avant toute
utilisation sur une vraie porte, et ne JAMAIS faire dépendre la sécurité
physique (issue de secours, incendie) de ce seul composant logiciel.
"""

import os
import threading


class DoorActuator:
    """Interface d'un actionneur de porte."""

    name = "none"

    def unlock(self, who=None) -> None:
        raise NotImplementedError

    def lock(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """Verrouille et libère le matériel (arrêt du service)."""
        self.lock()


class NullDoorActuator(DoorActuator):
    """Aucun matériel : journalise la décision, n'ouvre rien."""

    name = "null"

    def __init__(self):
        self.unlock_count = 0

    def unlock(self, who=None) -> None:
        self.unlock_count += 1
        print(f"[porte] ouverture autorisée pour {who or 'inconnu'} (aucun relais configuré).")

    def lock(self) -> None:
        pass


class GpioRelayActuator(DoorActuator):
    """Relais sur une broche GPIO (via gpiozero), déverrouillé pendant
    `unlock_seconds` puis reverrouillé automatiquement."""

    name = "gpio"

    def __init__(
        self,
        pin: int,
        unlock_seconds: float = 5.0,
        active_high: bool = True,
        device_factory=None,
        timer_factory=threading.Timer,
    ):
        """
        Args:
            pin: numéro de broche GPIO (BCM) du relais.
            unlock_seconds: durée pendant laquelle la porte reste déverrouillée.
            active_high: False si le relais est actif à l'état bas.
            device_factory: fabrique du périphérique de sortie
                (pin, active_high) -> objet avec on()/off()/close() ;
                par défaut gpiozero.OutputDevice. Injectable (tests).
            timer_factory: fabrique de minuteur (tests).
        """
        self.pin = pin
        self.unlock_seconds = unlock_seconds
        self._timer_factory = timer_factory
        self._lock = threading.Lock()
        self._timer = None

        if device_factory is None:
            from gpiozero import OutputDevice  # import tardif : dépendance optionnelle

            def device_factory(pin, active_high):
                return OutputDevice(pin, active_high=active_high, initial_value=False)

        self._device = device_factory(pin, active_high)
        self._device.off()  # état initial garanti : verrouillé

    def unlock(self, who=None) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            try:
                self._device.on()
            except Exception as exc:
                print(f"[porte] ERREUR à l'ouverture ({exc}) : porte maintenue verrouillée.")
                self._safe_off()
                return
            print(f"[porte] déverrouillée {self.unlock_seconds:.0f}s pour {who or 'inconnu'}.")
            self._timer = self._timer_factory(self.unlock_seconds, self.lock)
            self._timer.daemon = True
            self._timer.start()

    def _safe_off(self) -> None:
        try:
            self._device.off()
        except Exception as exc:
            print(f"[porte] ERREUR au verrouillage ({exc}) : vérifier le relais !")

    def lock(self) -> None:
        # Pas de `with self._lock` ici : appelé par le minuteur et par close().
        self._safe_off()

    def close(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._safe_off()
        try:
            self._device.close()
        except Exception:
            pass


def build_actuator_from_env(env=None) -> DoorActuator:
    """Construit l'actionneur selon l'environnement.

    Variables : DOOR_RELAY_GPIO_PIN (absente = aucun relais),
    DOOR_UNLOCK_SECONDS (défaut 5), DOOR_RELAY_ACTIVE_HIGH (défaut 1).
    """
    env = os.environ if env is None else env
    pin = env.get("DOOR_RELAY_GPIO_PIN")
    if not pin:
        return NullDoorActuator()

    try:
        return GpioRelayActuator(
            pin=int(pin),
            unlock_seconds=float(env.get("DOOR_UNLOCK_SECONDS", "5")),
            active_high=env.get("DOOR_RELAY_ACTIVE_HIGH", "1") not in ("0", "false", "False"),
        )
    except Exception as exc:
        print(f"[porte] ERREUR : relais GPIO{pin} inutilisable ({exc}). "
              f"Porte laissée verrouillée, aucun relais piloté.")
        return NullDoorActuator()
        