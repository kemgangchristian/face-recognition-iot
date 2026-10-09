"""
Vide la base locale : identites, embeddings, logs d'acces.

A lancer une fois, service arrete, avant la mise en service d'un site.
Ne touche pas a thresholds.json (calibration camera) ni a encryption.key
sauf si --reset-key est passe.

Usage (depuis edge/) :
    python3 -m scripts.reset_database --yes
    python3 -m scripts.reset_database --yes --reset-key
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storage.database import Database


def _remove_if_exists(path: Path) -> bool:
    if not path.is_file():
        return False
    path.unlink()
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirme la suppression. Sans ce flag, rien n'est modifie.",
    )
    parser.add_argument(
        "--reset-key",
        action="store_true",
        help="Supprime aussi encryption.key. Une nouvelle cle sera creee au prochain demarrage.",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "storage_data",
        help="Dossier des fichiers SQLite et cle (defaut : edge/storage_data).",
    )
    args = parser.parse_args()

    storage_dir = args.storage_dir.resolve()
    db_path = storage_dir / "face_recognition.sqlite"
    key_path = storage_dir / "encryption.key"

    print("Cible :", storage_dir)
    print("  base :", db_path)
    print("  cle  :", key_path)
    if not args.yes:
        sys.exit("Aucune modification. Relancer avec --yes apres avoir arrete l'API.")

    storage_dir.mkdir(parents=True, exist_ok=True)

    removed = []
    for name in (
        "face_recognition.sqlite",
        "face_recognition.sqlite-wal",
        "face_recognition.sqlite-shm",
        "face_recognition.sqlite-journal",
    ):
        if _remove_if_exists(storage_dir / name):
            removed.append(name)

    if args.reset_key and _remove_if_exists(key_path):
        removed.append("encryption.key")

    db = Database(str(db_path))
    db.connect()
    db.init_schema()
    db.close()

    print("Supprime :", ", ".join(removed) if removed else "(aucun fichier existant)")
    print("Base recree, tables vides.")
    print("thresholds.json conserve." if (storage_dir / "thresholds.json").is_file() else "Pas de thresholds.json.")
    print("Redemarrer l'API, puis enrôler les personnes de ce site.")


if __name__ == "__main__":
    main()
