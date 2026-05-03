from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GuiState:
    project_path: str = ""
    project_loaded: bool = False
    species_list: list[dict[str, Any]] = field(default_factory=list)
    selected_species_constant: str | None = None
    editor_dirty: bool = False
    editor_data: dict[str, Any] = field(default_factory=dict)
    last_change_plan_md: str = ""
    last_change_plan_json: dict[str, Any] | None = None
    last_warnings: list[str] = field(default_factory=list)
    last_errors: list[str] = field(default_factory=list)
    validation_ok: bool = False
    dry_run_valid: bool = False
    last_dry_run_signature: str = ""
    last_species_count: int = 0
    last_build_status: str = "idle"
    last_build_errors: list[str] = field(default_factory=list)
    last_build_warnings: list[str] = field(default_factory=list)
    last_build_log_path: str = ""
    last_build_summary_md: str = ""
    build_in_progress: bool = False
    build_progress_value: float = 0.0
    build_live_output: str = ""
    type_options: list[str] = field(default_factory=list)
    ability_options: list[str] = field(default_factory=list)
    item_options: list[str] = field(default_factory=list)
    move_options: list[str] = field(default_factory=list)
    map_options: list[str] = field(default_factory=list)
    nature_options: list[str] = field(default_factory=list)
    tmhm_options: list[str] = field(default_factory=list)
    tutor_options: list[str] = field(default_factory=list)
    cry_options: list[str] = field(default_factory=list)
    condition_options: list[str] = field(default_factory=list)
    evolution_rows: list[dict[str, str]] = field(default_factory=list)
    selected_evolution_index: int = -1
    evolution_condition_rows: list[dict[str, str]] = field(default_factory=list)
    selected_evolution_condition_index: int = -1
    level_up_rows: list[dict[str, int | str]] = field(default_factory=list)
    selected_level_up_index: int = -1
    teachable_rows: list[str] = field(default_factory=list)
    selected_teachable_index: int = -1
    tutor_rows: list[str] = field(default_factory=list)
    selected_tutor_index: int = -1
    preview_frame_index: int = 0
    preview_palette_mode: str = "normal"


def default_editor_data() -> dict[str, Any]:
    return {
        "mode": "add",
        "constant_name": "",
        "species_name": "",
        "description": "",
        "folder_name": "",
        "assets_folder": "",
        "hp": 45,
        "attack": 49,
        "defense": 49,
        "speed": 45,
        "sp_attack": 65,
        "sp_defense": 65,
        "type1": "TYPE_NORMAL",
        "type2": "",
        "ability1": "ABILITY_NONE",
        "ability2": "ABILITY_NONE",
        "ability_hidden": "ABILITY_NONE",
        "height": 10,
        "weight": 100,
        "gender_ratio_enabled": True,
        "gender_ratio": 50,
        "catch_rate": 45,
        "exp_yield": 64,
        "ev_hp": 0,
        "ev_attack": 0,
        "ev_defense": 0,
        "ev_speed": 0,
        "ev_sp_attack": 0,
        "ev_sp_defense": 0,
        "cry_id": "CRY_NONE",
        "evo_method": "EVO_LEVEL",
        "evo_param": "1",
        "evo_target": "",
    }


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        import json

        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(config_path: Path, data: dict[str, Any]) -> None:
    import json

    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
