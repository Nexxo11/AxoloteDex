from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


def pick_latest_backup(backups_root: Path) -> Path:
    candidates = sorted([p for p in backups_root.iterdir() if p.is_dir()])
    if not candidates:
        raise FileNotFoundError(f"No hay backups en {backups_root}")
    return candidates[-1]


def load_manifest(backup_dir: Path) -> list[dict]:
    manifest = backup_dir / "backup_manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(f"No existe manifest en {manifest}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("backup_manifest.json invalido")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback rapido desde backup manifest")
    parser.add_argument("project_root", type=Path, help="Ruta de pokeemerald-expansion")
    parser.add_argument("--backup-dir", type=Path, default=None, help="Carpeta backup especifica")
    parser.add_argument("--latest", action="store_true", help="Usar ultimo backup en ./backups")
    parser.add_argument(
        "--remove-path",
        action="append",
        default=[],
        help="Ruta relativa a borrar (ej: graphics/pokemon/testmon)",
    )
    parser.add_argument("--apply", action="store_true", help="Aplica rollback real")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    backups_root = Path.cwd() / "backups"

    if args.backup_dir is not None:
        backup_dir = args.backup_dir.resolve()
    elif args.latest or args.backup_dir is None:
        backup_dir = pick_latest_backup(backups_root)
    else:
        raise ValueError("Debes indicar --backup-dir o --latest")

    entries = load_manifest(backup_dir)

    print("[ROLLBACK DRY-RUN]")
    print(f"- project_root: {project_root}")
    print(f"- backup_dir: {backup_dir}")
    print("- archivos a restaurar:")
    for item in entries:
        print(f"  - {item.get('backup')} -> {item.get('file')}")
    if args.remove_path:
        print("- rutas extra a borrar:")
        for rel in args.remove_path:
            print(f"  - {project_root / rel}")

    if not args.apply:
        print("\n[INFO] DRY-RUN: no se modifico nada")
        return

    for item in entries:
        src = Path(item["backup"])
        dst = Path(item["file"])
        if not src.exists():
            print(f"[WARN] backup faltante: {src}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for rel in args.remove_path:
        target = (project_root / rel).resolve()
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    print("\n[OK] Rollback aplicado")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
