from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParseWarning:
    message: str
    file_path: str | None = None
    line: int | None = None
    context: str | None = None


@dataclass
class SpeciesStats:
    hp: int | None = None
    attack: int | None = None
    defense: int | None = None
    speed: int | None = None
    sp_attack: int | None = None
    sp_defense: int | None = None


@dataclass
class SpeciesGraphics:
    front_pic_symbol: str | None = None
    back_pic_symbol: str | None = None
    icon_symbol: str | None = None
    footprint_symbol: str | None = None
    palette_symbol: str | None = None
    shiny_palette_symbol: str | None = None
    front_path: str | None = None
    back_path: str | None = None
    icon_path: str | None = None
    footprint_path: str | None = None
    normal_palette_path: str | None = None
    shiny_palette_path: str | None = None


@dataclass
class SpeciesLearnsets:
    level_up_symbol: str | None = None
    level_up_learnset_raw: list[str] = field(default_factory=list)
    egg_symbol: str | None = None
    egg_moves_raw: list[str] = field(default_factory=list)
    teachable_symbol: str | None = None
    teachable_moves_raw: list[str] = field(default_factory=list)


@dataclass
class ExpansionProject:
    root: Path
    species_header: Path
    species_info_root: Path
    family_files: list[Path]
    graphics_file: Path
    level_up_files: list[Path]
    egg_moves_file: Path
    teachable_file: Path


@dataclass
class PokemonSpecies:
    species_id: int | None = None
    constant_name: str | None = None
    internal_name: str | None = None
    folder_name: str | None = None
    species_name: str | None = None
    description: str | None = None
    base_stats: SpeciesStats = field(default_factory=SpeciesStats)
    types: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    height: str | None = None
    weight: str | None = None
    gender_ratio: str | None = None
    catch_rate: str | None = None
    exp_yield: str | None = None
    ev_yields: dict[str, int] = field(default_factory=dict)
    cry_id: str | None = None
    egg_groups: list[str] = field(default_factory=list)
    evolutions_raw: str | None = None
    level_up_symbol: str | None = None
    teachable_symbol: str | None = None
    level_up_learnset_raw: list[str] = field(default_factory=list)
    level_up_moves: list[dict[str, int | str]] = field(default_factory=list)
    egg_moves_raw: list[str] = field(default_factory=list)
    teachable_moves_raw: list[str] = field(default_factory=list)
    graphics: SpeciesGraphics = field(default_factory=SpeciesGraphics)
    source_locations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
