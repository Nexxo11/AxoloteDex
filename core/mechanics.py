from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class MechanicsReport:
    capabilities: dict[str, bool]
    evidence: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class SpeciesMechanicsReport:
    flags: dict[str, bool]
    evidence: list[str] = field(default_factory=list)


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def detect_project_mechanics(project_root: Path) -> MechanicsReport:
    root = project_root.resolve()
    files = [
        root / "include/constants/pokemon.h",
        root / "include/constants/items.h",
        root / "include/constants/moves.h",
        root / "include/constants/hold_effects.h",
        root / "include/config/battle.h",
        root / "src/data/pokemon/species_info.h",
    ]
    files.extend(sorted((root / "src/data/pokemon/species_info").glob("gen_*_families.h")))
    file_blobs: list[tuple[Path, str]] = [(p, _read_text(p)) for p in files if p.exists()]

    checks: dict[str, list[str]] = {
        "mega": [r"\bMEGA\b", r"\bEVO_MEGA\b", r"\bITEM_[A-Z0-9_]*ITE\b", r"\bFLAG_CAN_MEGA_EVOLVE\b"],
        "gigantamax": [r"\bGIGANTAMAX\b", r"\bGMAX\b", r"\bDYNAMAX\b", r"\bEVO_GIGANTAMAX\b"],
        "z_move": [
            r"\bZ_MOVE\b",
            r"\bZMOVE\b",
            r"\bHOLD_EFFECT_Z_CRYSTAL\b",
            r"\bITEM_[A-Z0-9_]*(?:IUM_Z|Z_[A-Z0-9_]*)\b",
        ],
        "tera": [r"\bTERASTAL\b", r"\bTERA\b"],
    }

    caps: dict[str, bool] = {}
    evidence: dict[str, list[str]] = {}
    for key, patterns in checks.items():
        found: list[str] = []
        for pat in patterns:
            for fp, blob in file_blobs:
                m = re.search(pat, blob, flags=re.MULTILINE)
                if not m:
                    continue
                token = m.group(0)
                found.append(f"{fp.name}: {token}")
                break
        caps[key] = bool(found)
        evidence[key] = found

    return MechanicsReport(capabilities=caps, evidence=evidence)


def detect_species_mechanics(
    constant_name: str,
    evolutions_raw: str | None,
    all_species_constants: list[str] | None = None,
) -> SpeciesMechanicsReport:
    token = str(constant_name or "").upper()
    evo = str(evolutions_raw or "").upper()
    constants = [str(x or "").upper() for x in (all_species_constants or [])]
    mega_prefix = f"{token}_MEGA"
    has_mega_forms = any(c.startswith(mega_prefix) for c in constants)
    gmax_forms = {f"{token}_GMAX", f"{token}_GIGANTAMAX"}
    has_gmax_forms = any(c in gmax_forms for c in constants)
    flags = {
        "is_mega_form": "_MEGA" in token,
        "is_gmax_form": ("_GMAX" in token) or ("GIGANTAMAX" in token),
        "uses_mega_evo": ("EVO_MEGA" in evo) or ("MEGA" in evo and "EVO_" in evo),
        "uses_gmax_evo": ("EVO_GIGANTAMAX" in evo) or ("GMAX" in evo),
        "has_mega_forms": has_mega_forms,
        "has_gmax_forms": has_gmax_forms,
    }
    evidence: list[str] = []
    if flags["is_mega_form"]:
        evidence.append("constant contains _MEGA")
    if flags["is_gmax_form"]:
        evidence.append("constant contains _GMAX/GIGANTAMAX")
    if flags["uses_mega_evo"]:
        evidence.append("evolutions contains EVO_MEGA/MEGA pattern")
    if flags["uses_gmax_evo"]:
        evidence.append("evolutions contains EVO_GIGANTAMAX/GMAX pattern")
    if flags["has_mega_forms"]:
        evidence.append("project has species constants with <BASE>_MEGA* forms")
    if flags["has_gmax_forms"]:
        evidence.append("project has species constant <BASE>_GMAX or <BASE>_GIGANTAMAX")
    return SpeciesMechanicsReport(flags=flags, evidence=evidence)
