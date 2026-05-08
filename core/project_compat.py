from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CompatReport:
    level: str
    summary: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def detect_project_compatibility(root: Path) -> CompatReport:
    root = root.resolve()
    warnings: list[str] = []
    errors: list[str] = []

    if not root.exists() or not root.is_dir():
        return CompatReport(level="error", summary="invalid path", errors=[f"Invalid directory: {root}"])

    species_header = root / "include/constants/species.h"
    species_info_root = root / "src/data/pokemon/species_info.h"
    graphics_file = root / "src/data/graphics/pokemon.h"

    for p in (species_header, species_info_root, graphics_file):
        if not p.exists():
            errors.append(f"Missing required file: {p}")

    level_up_dir = root / "src/data/pokemon/level_up_learnsets"
    level_up_split = sorted(level_up_dir.glob("gen_*.h")) if level_up_dir.exists() else []
    level_up_single = root / "src/data/pokemon/level_up_learnsets.h"
    if not level_up_split and not level_up_single.exists():
        errors.append("Missing level-up learnsets (expected split gen_*.h or single level_up_learnsets.h)")
    elif not level_up_split and level_up_single.exists():
        warnings.append("Using single level_up_learnsets.h layout (legacy/variant project layout)")

    family_dir = root / "src/data/pokemon/species_info"
    family_split = sorted(family_dir.glob("gen_*_families.h")) if family_dir.exists() else []
    if not family_split:
        warnings.append("gen_*_families.h not found; using species_info.h only")

    egg_candidates = [
        root / "src/data/pokemon/egg_moves.h",
        root / "src/data/pokemon/egg_move_learnsets.h",
    ]
    if not any(p.exists() for p in egg_candidates):
        errors.append("Missing egg moves file (egg_moves.h / egg_move_learnsets.h)")

    teachable_candidates = [
        root / "src/data/pokemon/teachable_learnsets.h",
        root / "src/data/pokemon/tmhm_learnsets.h",
    ]
    if not any(p.exists() for p in teachable_candidates):
        warnings.append("Missing teachable learnsets file; TM/HM compatibility may be limited")

    if errors:
        return CompatReport(level="error", summary="incompatible", warnings=warnings, errors=errors)
    if warnings:
        return CompatReport(level="warning", summary="partial", warnings=warnings, errors=[])
    return CompatReport(level="ok", summary="compatible", warnings=[], errors=[])
