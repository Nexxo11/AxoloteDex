from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LintResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


_BASIC_MOVE_BY_TYPE = {
    "TYPE_GRASS": "MOVE_ABSORB",
    "TYPE_FIRE": "MOVE_EMBER",
    "TYPE_WATER": "MOVE_WATER_GUN",
    "TYPE_ELECTRIC": "MOVE_THUNDER_SHOCK",
    "TYPE_NORMAL": "MOVE_TACKLE",
    "TYPE_PSYCHIC": "MOVE_CONFUSION",
    "TYPE_ICE": "MOVE_POWDER_SNOW",
    "TYPE_FIGHTING": "MOVE_ROCK_SMASH",
    "TYPE_POISON": "MOVE_POISON_STING",
    "TYPE_GROUND": "MOVE_MUD_SLAP",
    "TYPE_FLYING": "MOVE_GUST",
    "TYPE_BUG": "MOVE_STRUGGLE_BUG",
    "TYPE_ROCK": "MOVE_ROCK_THROW",
    "TYPE_GHOST": "MOVE_ASTONISH",
    "TYPE_DRAGON": "MOVE_TWISTER",
    "TYPE_DARK": "MOVE_BITE",
    "TYPE_STEEL": "MOVE_METAL_CLAW",
    "TYPE_FAIRY": "MOVE_FAIRY_WIND",
}


def _load_valid_tokens(path: Path, prefix: str) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("#define ") and prefix in line:
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith(prefix):
                out.add(parts[1])
    return out


def lint_species_definition(
    data: dict[str, Any],
    project_root: Path,
    existing_constants: set[str],
    using_fallback_assets: bool,
) -> LintResult:
    result = LintResult(normalized_data=dict(data))

    mode = str(data.get("mode", "")).strip()
    const = str(data.get("constant_name", "")).strip()
    name = str(data.get("species_name", "")).strip()

    if mode == "add" and const in existing_constants:
        result.errors.append(f"constant duplicado: {const}")
    if mode == "edit" and const not in existing_constants:
        result.errors.append(f"constant no existe para edit: {const}")
    if mode == "delete" and const not in existing_constants:
        result.errors.append(f"constant no existe para delete: {const}")
    if mode == "delete":
        return result
    if not name:
        result.errors.append("nombre vacío")

    stats = data.get("base_stats", {})
    for key in ["hp", "attack", "defense", "speed", "sp_attack", "sp_defense"]:
        val = stats.get(key)
        if not isinstance(val, int) or val < 1 or val > 255:
            result.errors.append(f"stats fuera de rango: {key}={val}")

    valid_types = _load_valid_tokens(project_root / "include/constants/battle.h", "TYPE_")
    valid_abilities = _load_valid_tokens(project_root / "include/constants/abilities.h", "ABILITY_")

    types = [str(t).strip() for t in data.get("types", []) if str(t).strip()]
    if len(types) == 0:
        result.errors.append("types required: provide at least one TYPE_*")
    for t in types:
        if valid_types and t not in valid_types:
            result.errors.append(f"types invalid: {t}")

    abilities = [str(a).strip() for a in data.get("abilities", [])]
    if len([a for a in abilities if a and a != "ABILITY_NONE"]) == 0:
        result.errors.append("abilities required: provide at least one ABILITY_*")
    for a in [x for x in abilities if x]:
        if valid_abilities and a not in valid_abilities:
            result.errors.append(f"abilities invalid: {a}")

    if len(abilities) < 3:
        abilities = abilities + ["ABILITY_NONE"] * (3 - len(abilities))
        result.normalized_data["abilities"] = abilities
        result.warnings.append("hidden ability faltante autogenerada a ABILITY_NONE")
    elif not abilities[2]:
        abilities[2] = "ABILITY_NONE"
        result.normalized_data["abilities"] = abilities
        result.warnings.append("hidden ability vacía autogenerada a ABILITY_NONE")

    learnset = data.get("level_up_learnset")
    if not isinstance(learnset, list) or len(learnset) == 0:
        basic_move = _BASIC_MOVE_BY_TYPE.get(types[0] if types else "TYPE_NORMAL", "MOVE_TACKLE")
        result.normalized_data["level_up_learnset"] = [{"level": 1, "move": basic_move}]
        result.warnings.append(f"sin learnset: autogenerado básico con {basic_move}")
    else:
        for i, row in enumerate(learnset):
            if not isinstance(row, dict):
                result.errors.append(f"level_up_learnset fila invalida en indice {i}")
                continue
            level = row.get("level")
            move = str(row.get("move", "")).strip()
            if not isinstance(level, int) or level < 1 or level > 100:
                result.errors.append(f"level_up_learnset nivel invalido en indice {i}: {level}")
            if not move.startswith("MOVE_"):
                result.errors.append(f"level_up_learnset move invalido en indice {i}: {move}")

    tmhm = data.get("tmhm_learnset", [])
    if isinstance(tmhm, list):
        for i, move in enumerate(tmhm):
            m = str(move).strip()
            if not m.startswith("MOVE_"):
                result.errors.append(f"tmhm_learnset move invalido en indice {i}: {m}")

    evolutions = data.get("evolutions")
    if not isinstance(evolutions, list) or len(evolutions) == 0:
        result.warnings.append("sin evoluciones")

    if using_fallback_assets:
        result.warnings.append("usando fallback (Bulbasaur)")

    return result


def write_lint_report(output_dir: Path, lint: LintResult) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "lint_report.md"
    lines = ["# Lint Report", "", f"STATUS: {'OK' if lint.ok else 'FAILED'}", ""]
    lines.append("## Errors")
    if lint.errors:
        lines.extend([f"- {e}" for e in lint.errors])
    else:
        lines.append("- Ninguno")
    lines.append("")
    lines.append("## Warnings")
    if lint.warnings:
        lines.extend([f"- {w}" for w in lint.warnings])
    else:
        lines.append("- Ninguno")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
