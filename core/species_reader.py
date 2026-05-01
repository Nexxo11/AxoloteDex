from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from core.models import (
    ExpansionProject,
    ParseWarning,
    PokemonSpecies,
)


@dataclass
class SpeciesReadResult:
    project: ExpansionProject
    species: list[PokemonSpecies]
    warnings: list[ParseWarning]


class SpeciesReader:
    def __init__(self) -> None:
        self.warnings: list[ParseWarning] = []

    def warn(
        self,
        message: str,
        file_path: Path | None = None,
        line: int | None = None,
        context: str | None = None,
    ) -> None:
        self.warnings.append(
            ParseWarning(
                message=message,
                file_path=str(file_path) if file_path else None,
                line=line,
                context=context,
            )
        )

    def read(self, root: Path) -> SpeciesReadResult:
        project = self._validate_project(root)
        species_order = self._parse_species_constants(project.species_header)
        species_map = {s.constant_name: s for s in species_order if s.constant_name}

        self._parse_species_info([project.species_info_root] + project.family_files, species_map)
        symbol_to_path = self._parse_graphics_symbols(project.graphics_file)
        self._attach_graphics(species_order, symbol_to_path, project.root)
        level_up_map, level_up_entries = self._parse_level_up_files(project.level_up_files)
        egg_map = self._parse_move_table_file([project.egg_moves_file], is_level_up=False)
        if project.teachable_file.exists():
            teachable_map = self._parse_move_table_file([project.teachable_file], is_level_up=False)
        else:
            teachable_map = {}
            self.warn(
                "No existe teachable_learnsets.h; se continúa sin teachable map",
                file_path=project.teachable_file,
            )
        self._attach_learnsets(species_order, level_up_map, level_up_entries, egg_map, teachable_map)

        return SpeciesReadResult(project=project, species=species_order, warnings=self.warnings)

    def _validate_project(self, root: Path) -> ExpansionProject:
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Ruta invalida: {root}")

        species_header = root / "include/constants/species.h"
        species_info_root = root / "src/data/pokemon/species_info.h"
        graphics_file = root / "src/data/graphics/pokemon.h"
        egg_moves_file = root / "src/data/pokemon/egg_moves.h"
        teachable_file = root / "src/data/pokemon/teachable_learnsets.h"

        family_files = sorted((root / "src/data/pokemon/species_info").glob("gen_*_families.h"))
        level_up_files = sorted((root / "src/data/pokemon/level_up_learnsets").glob("gen_*.h"))

        required = [species_header, species_info_root, graphics_file, egg_moves_file]
        missing = [p for p in required if not p.exists()]
        if missing:
            missing_str = "\n".join(str(p) for p in missing)
            raise FileNotFoundError(f"Faltan archivos requeridos:\n{missing_str}")
        if not family_files:
            raise FileNotFoundError("No se encontraron gen_*_families.h")
        if not level_up_files:
            raise FileNotFoundError("No se encontraron level_up_learnsets/gen_*.h")

        return ExpansionProject(
            root=root,
            species_header=species_header,
            species_info_root=species_info_root,
            family_files=family_files,
            graphics_file=graphics_file,
            level_up_files=level_up_files,
            egg_moves_file=egg_moves_file,
            teachable_file=teachable_file,
        )

    def _parse_species_constants(self, species_header: Path) -> list[PokemonSpecies]:
        out: list[PokemonSpecies] = []
        line_no = 0
        define_re = re.compile(r"^\s*#define\s+(SPECIES_[A-Z0-9_]+)\s+(.+?)\s*$")
        with species_header.open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line_no += 1
                line = raw_line.split("//", 1)[0].strip()
                if not line:
                    continue
                m = define_re.match(line)
                if not m:
                    continue
                const_name, expr = m.group(1), m.group(2)
                if const_name == "NUM_SPECIES":
                    continue

                value = self._parse_int(expr)
                out.append(
                    PokemonSpecies(
                        species_id=value,
                        constant_name=const_name,
                        internal_name=self._internal_name_from_constant(const_name),
                        source_locations=[f"{species_header}:{line_no}"],
                    )
                )

        if not out:
            raise ValueError("No se pudieron extraer constantes SPECIES_*")
        return out

    def _parse_species_info(self, family_files: list[Path], species_map: dict[str, PokemonSpecies]) -> None:
        species_start = re.compile(r"\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\{")
        for family_file in family_files:
            text = family_file.read_text(encoding="utf-8", errors="ignore")
            macro_tokens = self._parse_token_macros(text)
            for match in species_start.finditer(text):
                constant = match.group(1)
                if constant not in species_map:
                    self.warn(
                        "Bloque de species info sin constante en species.h",
                        family_file,
                        self._line_from_pos(text, match.start()),
                        constant,
                    )
                    continue

                open_brace = text.find("{", match.start())
                close_brace = self._find_matching_brace(text, open_brace)
                if close_brace < 0:
                    self.warn(
                        "No se pudo cerrar bloque de especie",
                        family_file,
                        self._line_from_pos(text, match.start()),
                        constant,
                    )
                    continue

                body = text[open_brace + 1 : close_brace]
                start_line = self._line_from_pos(text, match.start())
                end_line = self._line_from_pos(text, close_brace)
                species = species_map[constant]
                species.source_locations.append(f"{family_file}:{start_line}-{end_line}")
                self._extract_species_fields(species, body, family_file, macro_tokens)

    def _extract_species_fields(
        self,
        species: PokemonSpecies,
        body: str,
        file_path: Path,
        macro_tokens: dict[str, list[str]],
    ) -> None:
        species.species_name = self._extract_string_field(body, "speciesName") or species.species_name
        species.base_stats.hp = self._extract_int_field(body, "baseHP")
        species.base_stats.attack = self._extract_int_field(body, "baseAttack")
        species.base_stats.defense = self._extract_int_field(body, "baseDefense")
        species.base_stats.speed = self._extract_int_field(body, "baseSpeed")
        species.base_stats.sp_attack = self._extract_int_field(body, "baseSpAttack")
        species.base_stats.sp_defense = self._extract_int_field(body, "baseSpDefense")

        species.height = self._extract_field_raw(body, "height")
        species.weight = self._extract_field_raw(body, "weight")
        species.gender_ratio = self._extract_field_raw(body, "genderRatio")
        species.catch_rate = self._extract_field_raw(body, "catchRate")
        species.exp_yield = self._extract_field_raw(body, "expYield")

        types_raw = self._extract_field_raw(body, "types")
        if types_raw:
            species.types = self._extract_tokens(types_raw, "TYPE_", macro_tokens)
        abilities_raw = self._extract_field_raw(body, "abilities")
        if abilities_raw:
            species.abilities = self._extract_tokens(abilities_raw, "ABILITY_", macro_tokens)
        eggs_raw = self._extract_field_raw(body, "eggGroups")
        if eggs_raw:
            species.egg_groups = self._extract_tokens(eggs_raw, "EGG_GROUP_", macro_tokens)

        species.evolutions_raw = self._extract_field_raw(body, "evolutions")

        species.graphics.front_pic_symbol = self._extract_field_raw(body, "frontPic")
        species.graphics.back_pic_symbol = self._extract_field_raw(body, "backPic")
        species.graphics.icon_symbol = self._extract_field_raw(body, "iconSprite")
        species.graphics.footprint_symbol = self._extract_field_raw(body, "footprint")
        species.graphics.palette_symbol = self._extract_field_raw(body, "palette")
        species.graphics.shiny_palette_symbol = self._extract_field_raw(body, "shinyPalette")

        level_symbol = self._extract_field_raw(body, "levelUpLearnset")
        if level_symbol:
            species.level_up_symbol = level_symbol
            species.level_up_learnset_raw = [f"SYMBOL:{level_symbol}"]
        egg_symbol = self._extract_field_raw(body, "eggMoveLearnset")
        if egg_symbol:
            species.egg_moves_raw = [f"SYMBOL:{egg_symbol}"]
        teach_symbol = self._extract_field_raw(body, "teachableLearnset")
        if teach_symbol:
            species.teachable_symbol = teach_symbol
            species.teachable_moves_raw = [f"SYMBOL:{teach_symbol}"]

        if not species.species_name:
            self.warn("speciesName no detectado", file_path, context=species.constant_name)

    def _parse_graphics_symbols(self, graphics_file: Path) -> dict[str, str]:
        text = graphics_file.read_text(encoding="utf-8", errors="ignore")
        symbol_map: dict[str, str] = {}
        pattern = re.compile(
            r"const\s+u(?:8|16|32)\s+([a-zA-Z0-9_]+)\[\]\s*=\s*INCBIN_[A-Z0-9_]+\(\"([^\"]+)\"\)"
        )
        for m in pattern.finditer(text):
            symbol_map[m.group(1)] = m.group(2)
        if not symbol_map:
            self.warn("No se pudieron extraer simbolos graficos", graphics_file)
        return symbol_map

    def _attach_graphics(
        self,
        species_list: list[PokemonSpecies],
        symbol_to_path: dict[str, str],
        root: Path,
    ) -> None:
        for s in species_list:
            g = s.graphics
            if g.front_pic_symbol in symbol_to_path:
                g.front_path = symbol_to_path[g.front_pic_symbol]
            if g.back_pic_symbol in symbol_to_path:
                g.back_path = symbol_to_path[g.back_pic_symbol]
            if g.icon_symbol in symbol_to_path:
                g.icon_path = symbol_to_path[g.icon_symbol]
            if g.footprint_symbol in symbol_to_path:
                g.footprint_path = symbol_to_path[g.footprint_symbol]
            if g.palette_symbol in symbol_to_path:
                g.normal_palette_path = symbol_to_path[g.palette_symbol]
            if g.shiny_palette_symbol in symbol_to_path:
                g.shiny_palette_path = symbol_to_path[g.shiny_palette_symbol]

            folder_from_path = self._folder_from_paths(g)
            if folder_from_path:
                s.folder_name = folder_from_path
            if not s.folder_name:
                s.folder_name = self._folder_from_constant(s.constant_name)

            if folder_from_path:
                folder = root / "graphics" / "pokemon" / s.folder_name
                if not folder.exists() and s.constant_name not in {"SPECIES_NONE", "SPECIES_EGG"}:
                    self.warn(
                        "Carpeta de assets no encontrada",
                        context=f"{s.constant_name} -> graphics/pokemon/{s.folder_name}",
                    )

    def _parse_level_up_files(self, files: list[Path]) -> tuple[dict[str, list[str]], dict[str, list[dict[str, int | str]]]]:
        moves_map: dict[str, list[str]] = {}
        entries_map: dict[str, list[dict[str, int | str]]] = {}
        table_re = re.compile(
            r"static\s+const\s+struct\s+LevelUpMove\s+(s[A-Za-z0-9_]+)\[\]\s*=\s*\{",
            re.MULTILINE,
        )
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for m in table_re.finditer(text):
                symbol = m.group(1)
                start = text.find("{", m.start())
                end = self._find_matching_brace(text, start)
                if end < 0:
                    self.warn("No se pudo cerrar tabla de learnset", file_path, context=symbol)
                    continue
                body = text[start + 1 : end]
                entries: list[dict[str, int | str]] = []
                for em in re.finditer(r"LEVEL_UP_MOVE\s*\(\s*(\d+)\s*,\s*(MOVE_[A-Z0-9_]+)\s*\)", body):
                    entries.append({"level": int(em.group(1)), "move": em.group(2)})
                entries_map[symbol] = entries
                moves_map[symbol] = [str(e["move"]) for e in entries]
        return moves_map, entries_map

    def _parse_move_table_file(self, files: list[Path], is_level_up: bool) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        table_re = re.compile(
            r"static\s+const\s+(?:struct\s+LevelUpMove|u16)\s+(s[A-Za-z0-9_]+)\[\]\s*=\s*\{",
            re.MULTILINE,
        )
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for m in table_re.finditer(text):
                symbol = m.group(1)
                start = text.find("{", m.start())
                end = self._find_matching_brace(text, start)
                if end < 0:
                    self.warn("No se pudo cerrar tabla de learnset", file_path, context=symbol)
                    continue
                body = text[start + 1 : end]
                if is_level_up:
                    moves = re.findall(r"LEVEL_UP_MOVE\s*\(\s*\d+\s*,\s*(MOVE_[A-Z0-9_]+)\s*\)", body)
                else:
                    moves = re.findall(r"\bMOVE_[A-Z0-9_]+\b", body)
                    moves = [m for m in moves if m != "MOVE_UNAVAILABLE"]
                out[symbol] = moves
        return out

    def _attach_learnsets(
        self,
        species_list: list[PokemonSpecies],
        level_up_map: dict[str, list[str]],
        level_up_entries: dict[str, list[dict[str, int | str]]],
        egg_map: dict[str, list[str]],
        teachable_map: dict[str, list[str]],
    ) -> None:
        for s in species_list:
            level_symbol = self._extract_symbol_from_placeholder(s.level_up_learnset_raw)
            egg_symbol = self._extract_symbol_from_placeholder(s.egg_moves_raw)
            teach_symbol = self._extract_symbol_from_placeholder(s.teachable_moves_raw)

            if level_symbol:
                s.level_up_learnset_raw = level_up_map.get(level_symbol, [])
                s.level_up_moves = level_up_entries.get(level_symbol, [])
                if level_symbol not in level_up_map:
                    self.warn("No se encontro level up learnset", context=f"{s.constant_name} -> {level_symbol}")
            if egg_symbol:
                s.egg_moves_raw = egg_map.get(egg_symbol, [])
                if egg_symbol not in egg_map:
                    self.warn("No se encontro egg learnset", context=f"{s.constant_name} -> {egg_symbol}")
            if teach_symbol:
                s.teachable_moves_raw = teachable_map.get(teach_symbol, [])
                if teach_symbol not in teachable_map:
                    self.warn("No se encontro teachable learnset", context=f"{s.constant_name} -> {teach_symbol}")

    @staticmethod
    def _extract_symbol_from_placeholder(values: list[str]) -> str | None:
        if len(values) == 1 and values[0].startswith("SYMBOL:"):
            return values[0].split("SYMBOL:", 1)[1]
        return None

    @staticmethod
    def _extract_string_field(body: str, name: str) -> str | None:
        m = re.search(rf"\.{name}\s*=\s*_\(\"([^\"]+)\"\)", body)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _extract_field_raw(body: str, name: str) -> str | None:
        marker = f".{name}"
        start = body.find(marker)
        if start < 0:
            return None

        eq = body.find("=", start)
        if eq < 0:
            return None

        i = eq + 1
        while i < len(body) and body[i].isspace():
            i += 1

        depth_paren = 0
        depth_brace = 0
        depth_bracket = 0
        in_string = False
        value_start = i

        while i < len(body):
            ch = body[i]
            if ch == '"' and (i == 0 or body[i - 1] != "\\"):
                in_string = not in_string
            elif not in_string:
                if ch == "(":
                    depth_paren += 1
                elif ch == ")":
                    depth_paren = max(0, depth_paren - 1)
                elif ch == "{":
                    depth_brace += 1
                elif ch == "}":
                    depth_brace = max(0, depth_brace - 1)
                elif ch == "[":
                    depth_bracket += 1
                elif ch == "]":
                    depth_bracket = max(0, depth_bracket - 1)
                elif ch == "," and depth_paren == 0 and depth_brace == 0 and depth_bracket == 0:
                    return body[value_start:i].strip()
            i += 1

        return None

    def _extract_int_field(self, body: str, name: str) -> int | None:
        raw = self._extract_field_raw(body, name)
        if raw is None:
            return None
        return self._parse_int(raw)

    @staticmethod
    def _parse_int(value: str) -> int | None:
        value = value.strip()
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        return None

    @staticmethod
    def _line_from_pos(text: str, pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    @staticmethod
    def _find_matching_brace(text: str, open_pos: int) -> int:
        if open_pos < 0 or open_pos >= len(text) or text[open_pos] != "{":
            return -1
        depth = 0
        i = open_pos
        in_string = False
        while i < len(text):
            ch = text[i]
            if ch == '"' and (i == 0 or text[i - 1] != "\\"):
                in_string = not in_string
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return i
            i += 1
        return -1

    @staticmethod
    def _internal_name_from_constant(constant_name: str | None) -> str | None:
        if not constant_name:
            return None
        name = constant_name.replace("SPECIES_", "")
        parts = name.split("_")
        return "".join(part.capitalize() for part in parts)

    @staticmethod
    def _folder_from_paths(graphics) -> str | None:
        candidates = [
            graphics.front_path,
            graphics.back_path,
            graphics.icon_path,
            graphics.footprint_path,
            graphics.normal_palette_path,
            graphics.shiny_palette_path,
        ]
        for path in candidates:
            if not path:
                continue
            m = re.search(r"graphics/pokemon/(.+)/[^/]+$", path)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _folder_from_constant(constant_name: str | None) -> str | None:
        if not constant_name:
            return None
        folder = constant_name.replace("SPECIES_", "").lower()
        return folder

    @staticmethod
    def _parse_token_macros(text: str) -> dict[str, list[str]]:
        macros: dict[str, list[str]] = {}
        for line in text.splitlines():
            m = re.match(r"\s*#define\s+([A-Z0-9_]+)\s+(.+)$", line)
            if not m:
                continue
            name, expr = m.group(1), m.group(2)
            tokens = re.findall(r"(?:TYPE|ABILITY|EGG_GROUP)_[A-Z0-9_]+", expr)
            if tokens:
                macros[name] = tokens
        return macros

    @staticmethod
    def _extract_tokens(raw: str, prefix: str, macro_tokens: dict[str, list[str]]) -> list[str]:
        direct = re.findall(rf"\b{re.escape(prefix)}[A-Z0-9_]+\b", raw)
        if direct:
            return direct
        macro_name = raw.strip()
        return macro_tokens.get(macro_name, [])
