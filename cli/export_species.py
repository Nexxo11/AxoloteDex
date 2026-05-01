from __future__ import annotations

import json
from pathlib import Path
import sys

from core.species_reader import SpeciesReader


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_summary_md(path: Path, species: list[dict]) -> None:
    lines = [
        "# Species Summary",
        "",
        "| ID | Constant | Name | Types | Abilities | Asset Folder |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in species:
        species_id = item.get("species_id")
        constant = item.get("constant_name") or ""
        name = item.get("species_name") or ""
        types = ", ".join(item.get("types") or [])
        abilities = ", ".join(item.get("abilities") or [])
        folder = item.get("folder_name") or ""
        lines.append(f"| {species_id if species_id is not None else ''} | {constant} | {name} | {types} | {abilities} | {folder} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_warnings_md(path: Path, warnings: list[dict]) -> None:
    lines = ["# Parse Warnings", ""]
    if not warnings:
        lines.append("Sin warnings.")
    else:
        for w in warnings:
            location = w.get("file_path") or "(sin archivo)"
            if w.get("line") is not None:
                location = f"{location}:{w['line']}"
            lines.append(f"- {w.get('message', 'warning')} - `{location}`")
            if w.get("context"):
                lines.append(f"  - context: `{w['context']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python export_species.py ./pokeemerald-expansion")
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    reader = SpeciesReader()
    result = reader.read(root)

    output_dir = Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    species_json = [s.to_dict() for s in result.species]
    warnings_json = [w.__dict__ for w in result.warnings]

    index_path = output_dir / "species_index.json"
    summary_path = output_dir / "species_summary.md"
    warnings_path = output_dir / "parse_warnings.md"

    write_json(index_path, species_json)
    write_summary_md(summary_path, species_json)
    write_warnings_md(warnings_path, warnings_json)

    print(f"[OK] Species exportadas: {len(species_json)}")
    print(f"[OK] Warnings: {len(warnings_json)}")
    print(f"[OK] {index_path}")
    print(f"[OK] {summary_path}")
    print(f"[OK] {warnings_path}")


if __name__ == "__main__":
    main()
