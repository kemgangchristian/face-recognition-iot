"""
Monitoring CPU/RAM/température en fonctionnement continu.
Story 6.1 — Epic 6.

Fait tourner le pipeline de reconnaissance en boucle pendant une durée
donnée, en échantillonnant les ressources système à intervalle régulier.
Produit un rapport exploitable en fin d'exécution.

Usage : python tests/manual/test_stress_monitoring_pi.py [duree_minutes]
"""

import sys
import os
import time
import subprocess
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from capture.camera import Camera
from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter
from recognition.face_embedder import FaceEmbedder


def get_cpu_percent():
    """Lit l'utilisation CPU globale via /proc/stat (méthode légère, sans
    dépendance externe type psutil)."""
    with open("/proc/loadavg", "r") as f:
        load_1min = float(f.read().split()[0])
    return load_1min


def get_ram_usage_mb():
    """Lit la RAM utilisée via /proc/meminfo."""
    with open("/proc/meminfo", "r") as f:
        lines = f.readlines()
    total = int(lines[0].split()[1])
    available = int(lines[2].split()[1])
    used_mb = (total - available) / 1024
    return used_mb


def get_temperature_c():
    """Lit la température CPU via vcgencmd (spécifique Raspberry Pi)."""
    result = subprocess.run(
        ["vcgencmd", "measure_temp"], capture_output=True, text=True
    )
    temp_str = result.stdout.strip()  # format: "temp=45.5'C"
    return float(temp_str.split("=")[1].replace("'C", ""))


class ResourceMonitor:
    """Échantillonne les ressources système en arrière-plan, à intervalle régulier."""

    def __init__(self, interval_seconds=10):
        self.interval_seconds = interval_seconds
        self.samples = []
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def _monitor_loop(self):
        while self._running:
            sample = {
                "timestamp": time.time(),
                "load_1min": get_cpu_percent(),
                "ram_mb": get_ram_usage_mb(),
                "temp_c": get_temperature_c(),
            }
            self.samples.append(sample)
            time.sleep(self.interval_seconds)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def print_report(self):
        if not self.samples:
            print("Aucun échantillon collecté.")
            return

        temps = [s["temp_c"] for s in self.samples]
        rams = [s["ram_mb"] for s in self.samples]
        loads = [s["load_1min"] for s in self.samples]

        print("\n=== Rapport de monitoring ===")
        print(f"Échantillons collectés : {len(self.samples)}")
        print(f"Température (°C) : min={min(temps):.1f} max={max(temps):.1f} moy={sum(temps)/len(temps):.1f}")
        print(f"RAM utilisée (MB) : min={min(rams):.0f} max={max(rams):.0f} moy={sum(rams)/len(rams):.0f}")
        print(f"Load average (1min) : min={min(loads):.2f} max={max(loads):.2f} moy={sum(loads)/len(loads):.2f}")

        # Seuil de vigilance thermique connu pour le Raspberry Pi 4 :
        # throttling automatique déclenché à partir de 80°C.
        if max(temps) >= 80:
            print(" ATTENTION : température proche ou au-dessus du seuil de throttling (80°C)")
        elif max(temps) >= 70:
            print(" Température élevée mais sous le seuil critique")
        else:
            print(" Température dans une plage saine")

def main():
    duration_minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    duration_seconds = duration_minutes * 60

    print(f"=== Test de charge continue — {duration_minutes} minutes ===\n")

    camera = Camera()
    detector = FaceDetector()
    quality_filter = QualityFilter()
    embedder = FaceEmbedder()

    camera.start()

    monitor = ResourceMonitor(interval_seconds=10)
    monitor.start()

    cycles = 0
    errors = 0
    start_time = time.time()

    try:
        while time.time() - start_time < duration_seconds:
            try:
                frame = camera.read_frame()
                detections = detector.detect(frame)
                valid = quality_filter.filter(frame, detections)
                if valid:
                    embedder.extract(frame, valid[0])
                cycles += 1
            except Exception as e:
                errors += 1
                print(f"Erreur au cycle {cycles} : {e}")

            if cycles % 20 == 0:
                elapsed = time.time() - start_time
                print(f"[{elapsed:.0f}s] {cycles} cycles effectués, {errors} erreurs")

            time.sleep(0.1)  # évite de saturer le CPU à 100% en boucle serrée

    finally:
        camera.stop()
        monitor.stop()

    print(f"\nTotal : {cycles} cycles, {errors} erreurs sur {duration_minutes} minutes")
    monitor.print_report()


if __name__ == "__main__":
    main()
