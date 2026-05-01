from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


REQUIRED_ASSETS = [
    "front.png",
    "back.png",
    "icon.png",
    "footprint.png",
    "normal.pal",
    "shiny.pal",
]

FALLBACK_ALIASES = {
    "front.png": ["front.png", "anim_front.png"],
    "back.png": ["back.png"],
    "icon.png": ["icon.png", "icon_gba.png"],
    "footprint.png": ["footprint.png", "footprint_gba.png"],
    "normal.pal": ["normal.pal", "normal_gba.pal"],
    "shiny.pal": ["shiny.pal", "shiny_gba.pal"],
}


@dataclass
class ValidationResult:
    data: dict
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    asset_sources: dict[str, Path] = field(default_factory=dict)
    used_fallback: bool = False
    fallback_species_folder: str | None = None


def load_species_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("El JSON de especie debe ser un objeto")
    return parsed


def validate_species_definition(
    data: dict,
    json_path: Path,
    project_root: Path,
    fallback_folder: str | None,
) -> ValidationResult:
    result = ValidationResult(data=data)

    mode = data.get("mode")
    if mode not in {"add", "edit", "delete"}:
        result.errors.append("mode debe ser 'add', 'edit' o 'delete'")

    constant_name = data.get("constant_name")
    if not isinstance(constant_name, str) or not constant_name.startswith("SPECIES_"):
        result.errors.append("constant_name debe iniciar con SPECIES_")

    if mode == "delete":
        result.asset_sources = {}
        return result

    species_name = data.get("species_name")
    if not isinstance(species_name, str) or not species_name.strip():
        result.errors.append("species_name es obligatorio")
    elif len(species_name.strip()) > 12:
        result.errors.append("species_name excede límite de 12 caracteres")

    description = data.get("description")
    if description is not None:
        if not isinstance(description, str):
            result.errors.append("description debe ser texto")
        elif len(description) > 180:
            result.errors.append("description excede límite de 180 caracteres")

    folder_name = data.get("folder_name")
    if not isinstance(folder_name, str) or not folder_name.strip():
        result.errors.append("folder_name es obligatorio")

    base_stats = data.get("base_stats")
    required_stats = ["hp", "attack", "defense", "speed", "sp_attack", "sp_defense"]
    if not isinstance(base_stats, dict):
        result.errors.append("base_stats es obligatorio y debe ser objeto")
    else:
        for stat in required_stats:
            if stat not in base_stats:
                result.errors.append(f"base_stats.{stat} faltante")

    types = data.get("types")
    abilities = data.get("abilities")
    if not isinstance(types, list) or len(types) == 0:
        result.errors.append("types debe ser lista no vacia")
    if not isinstance(abilities, list) or len(abilities) == 0:
        result.errors.append("abilities debe ser lista no vacia")
    else:
        normalized_abilities = [str(a).strip() for a in abilities]
        if not any(normalized_abilities):
            result.errors.append("abilities no puede estar vacio")
        for a in normalized_abilities:
            if a and not a.startswith("ABILITY_"):
                result.errors.append(f"ability invalida: {a}")

    if isinstance(types, list):
        normalized_types = [str(t).strip() for t in types if str(t).strip()]
        if len(normalized_types) == 0:
            result.errors.append("types debe contener al menos TYPE_ valido")
        for t in normalized_types:
            if not t.startswith("TYPE_"):
                result.errors.append(f"type invalido: {t}")

    if mode == "edit":
        result.asset_sources = {}
        return result

    assets_folder_raw = data.get("assets_folder")
    assets_folder = None
    if isinstance(assets_folder_raw, str) and assets_folder_raw.strip():
        assets_folder = (json_path.parent / assets_folder_raw).resolve()
    else:
        result.warnings.append("assets_folder no provisto; se intentara fallback de assets")

    resolved_assets: dict[str, Path] = {}
    missing_assets: list[str] = []

    if assets_folder and assets_folder.exists():
        for asset in REQUIRED_ASSETS:
            candidate = assets_folder / asset
            if candidate.exists():
                resolved_assets[asset] = candidate
            else:
                missing_assets.append(asset)
    else:
        missing_assets = REQUIRED_ASSETS.copy()

    if missing_assets:
        if fallback_folder:
            fallback_root = project_root / "graphics" / "pokemon" / fallback_folder
            used_any = False
            for asset in missing_assets:
                aliases = FALLBACK_ALIASES.get(asset, [asset])
                selected = None
                for alias in aliases:
                    fallback_candidate = fallback_root / alias
                    if fallback_candidate.exists():
                        selected = fallback_candidate
                        break
                if selected is not None:
                    resolved_assets[asset] = selected
                    used_any = True
            if used_any:
                result.used_fallback = True
                result.fallback_species_folder = fallback_folder
                result.warnings.append(
                    f"Se usaron assets fallback de graphics/pokemon/{fallback_folder} para archivos faltantes"
                )

    still_missing = [a for a in REQUIRED_ASSETS if a not in resolved_assets]
    if still_missing:
        result.errors.append(
            "No se pudieron resolver todos los assets requeridos: " + ", ".join(still_missing)
        )

    result.asset_sources = resolved_assets
    return result
