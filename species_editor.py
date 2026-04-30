from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime
import json

from change_plan import ChangePlan, ChangeStep, relpath
from species_reader import SpeciesReader
from validate_species import ValidationResult


@dataclass
class ApplyResult:
    applied: bool
    backup_dir: Path | None
    messages: list[str]


class SpeciesEditor:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.reader = SpeciesReader()
        self.read_result = self.reader.read(self.project_root)
        self.species_by_constant = {
            s.constant_name: s for s in self.read_result.species if s.constant_name
        }

    def pick_fallback_folder(self) -> str | None:
        preferred = ["bulbasaur", "pikachu", "charmander", "squirtle"]
        for name in preferred:
            folder = self.project_root / "graphics" / "pokemon" / name
            if folder.exists():
                return name
        for s in self.read_result.species:
            if s.folder_name:
                folder = self.project_root / "graphics" / "pokemon" / s.folder_name
                if folder.exists():
                    return s.folder_name
        return None

    def build_plan(self, data: dict, validation: ValidationResult) -> ChangePlan:
        mode = data.get("mode", "")
        constant_name = data.get("constant_name", "")
        plan = ChangePlan(
            mode=mode,
            constant_name=constant_name,
            project_root=str(self.project_root),
        )

        plan.warnings.extend(validation.warnings)
        plan.errors.extend(validation.errors)

        if mode == "add" and constant_name in self.species_by_constant:
            plan.errors.append(f"{constant_name} ya existe y mode=add")
        if mode == "edit" and constant_name not in self.species_by_constant:
            plan.errors.append(f"{constant_name} no existe y mode=edit")
        if mode == "delete" and constant_name not in self.species_by_constant:
            plan.errors.append(f"{constant_name} no existe y mode=delete")

        if mode not in {"add", "edit", "delete"}:
            plan.errors.append("mode no soportado")

        if plan.is_blocked:
            return plan

        species_h = self.project_root / "include/constants/species.h"
        family_file = self._pick_family_file()
        graphics_h = self.project_root / "src/data/graphics/pokemon.h"
        target_asset_dir = self.project_root / "graphics/pokemon" / data["folder_name"]

        if mode == "delete":
            return self._build_delete_plan(plan, data, species_h, graphics_h)
        if mode == "edit":
            return self._build_edit_plan(plan, data)

        plan.strategy_notes.append(
            "Constante nueva insertada justo antes de SPECIES_EGG y se actualiza SPECIES_EGG para apuntar a la nueva especie."
        )
        plan.strategy_notes.append(
            f"Bloque de especie se inserta al final de {relpath(family_file, self.project_root)} antes del bloque __INTELLISENSE__."
        )
        plan.strategy_notes.append(
            f"Referencias graficas se insertan en {relpath(graphics_h, self.project_root)} antes de la declaracion de Egg."
        )

        new_define, old_egg_line, new_egg_line = self._build_species_constant_change(species_h, constant_name)
        plan.add_step(
            ChangeStep(
                target_file=relpath(species_h, self.project_root),
                action="insert",
                reason="Agregar nueva constante de especie",
                new_text=new_define,
                insert_before="#define SPECIES_EGG",
                risk_level="high",
            )
        )
        plan.add_step(
            ChangeStep(
                target_file=relpath(species_h, self.project_root),
                action="update",
                reason="Actualizar SPECIES_EGG para conservar orden",
                old_text=old_egg_line,
                new_text=new_egg_line,
                risk_level="high",
            )
        )

        family_block = self._build_species_info_block(data)
        plan.add_step(
            ChangeStep(
                target_file=relpath(family_file, self.project_root),
                action="insert",
                reason="Agregar bloque de species info",
                new_text=family_block,
                insert_before="#ifdef __INTELLISENSE__",
                risk_level="high",
            )
        )

        graphics_block = self._build_graphics_block(data)
        plan.add_step(
            ChangeStep(
                target_file=relpath(graphics_h, self.project_root),
                action="insert",
                reason="Agregar simbolos graficos de especie",
                new_text=graphics_block,
                insert_before="const u32 gMonFrontPic_Egg[]",
                risk_level="medium",
            )
        )

        for asset_name, source in validation.asset_sources.items():
            target = target_asset_dir / asset_name
            plan.add_step(
                ChangeStep(
                    target_file=relpath(target, self.project_root),
                    action="copy_asset",
                    reason=f"Copiar asset requerido ({asset_name})",
                    new_text=str(source),
                    risk_level="low",
                    warnings=[
                        "Asset copiado sin conversion; la conversion la maneja el build del proyecto"
                    ],
                )
            )

        return plan

    def _build_edit_plan(self, plan: ChangePlan, data: dict) -> ChangePlan:
        constant_name = data["constant_name"]
        species = self.species_by_constant.get(constant_name)
        if species is None:
            plan.errors.append(f"No existe la especie {constant_name}")
            return plan

        level_symbol = species.level_up_symbol
        if not level_symbol:
            plan.errors.append(f"No se detectó levelUpLearnset para {constant_name}")
            return plan

        level_file, old_block = self._find_levelup_block(level_symbol)
        if level_file is None or old_block is None:
            plan.errors.append(f"No se encontró bloque de {level_symbol}")
            return plan

        new_block = self._build_levelup_block(level_symbol, data.get("level_up_learnset", []))
        plan.add_step(
            ChangeStep(
                target_file=relpath(level_file, self.project_root),
                action="update",
                reason="Actualizar level-up learnset",
                old_text=old_block,
                new_text=new_block,
                risk_level="high",
            )
        )

        all_learnables = self.project_root / "src/data/pokemon/all_learnables.json"
        old_json = all_learnables.read_text(encoding="utf-8")
        parsed = json.loads(old_json)
        key = constant_name.replace("SPECIES_", "")
        tmhm_moves = [m for m in data.get("tmhm_learnset", []) if isinstance(m, str) and m.startswith("MOVE_")]
        existing = parsed.get(key, [])
        if not isinstance(existing, list):
            existing = []
        keep_non_tmhm = [m for m in existing if m not in tmhm_moves]
        parsed[key] = sorted(set(keep_non_tmhm + tmhm_moves))
        new_json = json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
        plan.add_step(
            ChangeStep(
                target_file=relpath(all_learnables, self.project_root),
                action="update",
                reason="Actualizar fuente de verdad de learnables (TM/HM)",
                old_text=old_json,
                new_text=new_json,
                risk_level="high",
            )
        )

        plan.add_step(
            ChangeStep(
                target_file="tools/learnset_helpers/make_teachables.py",
                action="run_script",
                reason="Regenerar teachable_learnsets.h desde all_learnables.json",
                new_text="python3 tools/learnset_helpers/make_teachables.py build",
                risk_level="medium",
            )
        )
        return plan

    def _build_delete_plan(self, plan: ChangePlan, data: dict, species_h: Path, graphics_h: Path) -> ChangePlan:
        constant_name = data["constant_name"]
        species = self.species_by_constant.get(constant_name)
        if species is None:
            plan.errors.append(f"No existe la especie {constant_name}")
            return plan

        species_h_text = species_h.read_text(encoding="utf-8")
        constant_match = re.search(rf"^\s*#define\s+{re.escape(constant_name)}\s+\d+\s*$", species_h_text, flags=re.MULTILINE)
        if not constant_match:
            plan.errors.append(f"No se pudo ubicar define de {constant_name} en species.h")
            return plan

        old_define_line = constant_match.group(0)
        new_egg_line, old_egg_line = self._build_species_egg_after_delete(species_h_text, constant_name)

        plan.add_step(
            ChangeStep(
                target_file=relpath(species_h, self.project_root),
                action="update",
                reason="Eliminar constante de especie",
                old_text=old_define_line + "\n",
                new_text="",
                risk_level="high",
            )
        )
        plan.add_step(
            ChangeStep(
                target_file=relpath(species_h, self.project_root),
                action="update",
                reason="Actualizar SPECIES_EGG tras eliminar especie",
                old_text=old_egg_line,
                new_text=new_egg_line,
                risk_level="high",
            )
        )

        family_deleted = False
        for family_file in self.read_result.project.family_files:
            family_text = family_file.read_text(encoding="utf-8")
            block = self._find_species_info_block(family_text, constant_name)
            if block:
                plan.add_step(
                    ChangeStep(
                        target_file=relpath(family_file, self.project_root),
                        action="update",
                        reason="Eliminar bloque de species info",
                        old_text=block,
                        new_text="",
                        risk_level="high",
                    )
                )
                family_deleted = True
                break
        if not family_deleted:
            plan.warnings.append(f"No se encontró bloque de species info para {constant_name}")

        internal = self._pascal_from_constant(constant_name)
        graphics_text = graphics_h.read_text(encoding="utf-8")
        graphics_block = self._find_graphics_block(graphics_text, internal)
        if graphics_block:
            plan.add_step(
                ChangeStep(
                    target_file=relpath(graphics_h, self.project_root),
                    action="update",
                    reason="Eliminar símbolos gráficos de especie",
                    old_text=graphics_block,
                    new_text="",
                    risk_level="medium",
                )
            )
        else:
            plan.warnings.append(f"No se encontró bloque gráfico para {constant_name}")

        folder_name = species.folder_name or data.get("folder_name", "")
        if folder_name:
            asset_dir = self.project_root / "graphics/pokemon" / folder_name
            plan.add_step(
                ChangeStep(
                    target_file=relpath(asset_dir, self.project_root),
                    action="delete_dir",
                    reason="Eliminar carpeta de assets de la especie",
                    new_text="",
                    risk_level="high",
                )
            )
        else:
            plan.warnings.append("No se detectó folder_name para eliminar assets")

        return plan

    def apply_plan(self, plan: ChangePlan, validation: ValidationResult) -> ApplyResult:
        if plan.is_blocked:
            return ApplyResult(applied=False, backup_dir=None, messages=["Plan bloqueado; no se aplica"]) 

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path.cwd() / "backups" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        file_steps: dict[Path, list[ChangeStep]] = {}
        for step in plan.steps:
            if step.action in {"insert", "update"}:
                abs_path = self.project_root / step.target_file
                file_steps.setdefault(abs_path, []).append(step)

        manifest: list[dict[str, str]] = []
        for abs_path in file_steps:
            self._backup_file(abs_path, backup_dir, self.project_root)
            manifest.append({
                "file": str(abs_path),
                "backup": str(backup_dir / relpath(abs_path, self.project_root)),
            })

        for abs_path, steps in file_steps.items():
            text = abs_path.read_text(encoding="utf-8")
            for step in steps:
                if step.action == "insert":
                    text = self._apply_insert(text, step)
                elif step.action == "update":
                    text = self._apply_update(text, step)
            abs_path.write_text(text, encoding="utf-8")

        for step in plan.steps:
            if step.action == "copy_asset":
                src = Path(step.new_text)
                dst = self.project_root / step.target_file
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    self._backup_file(dst, backup_dir, self.project_root)
                shutil.copy2(src, dst)
            elif step.action == "delete_dir":
                dst = self.project_root / step.target_file
                if dst.exists() and dst.is_dir():
                    self._backup_file(dst, backup_dir, self.project_root)
                    shutil.rmtree(dst)
            elif step.action == "run_script":
                subprocess.run(step.new_text, cwd=self.project_root, shell=True, check=True)

        manifest_path = backup_dir / "backup_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return ApplyResult(
            applied=True,
            backup_dir=backup_dir,
            messages=[
                f"Backup creado en {backup_dir}",
                "Cambios aplicados correctamente",
            ],
        )

    def _pick_family_file(self) -> Path:
        # Estrategia: usar el ultimo gen_*_families.h disponible para custom entries.
        return sorted(self.read_result.project.family_files)[-1]

    def _build_species_constant_change(self, species_h: Path, constant_name: str) -> tuple[str, str, str]:
        text = species_h.read_text(encoding="utf-8")
        egg_match = re.search(r"^\s*#define\s+SPECIES_EGG\s+\(([^)]+)\)\s*$", text, flags=re.MULTILINE)
        if not egg_match:
            raise ValueError("No se encontro #define SPECIES_EGG")
        old_egg_line = egg_match.group(0)

        max_id = -1
        for m in re.finditer(r"^\s*#define\s+(SPECIES_[A-Z0-9_]+)\s+(\d+)\s*$", text, flags=re.MULTILINE):
            name = m.group(1)
            value = int(m.group(2))
            if name in {"SPECIES_SHINY_TAG"}:
                continue
            max_id = max(max_id, value)
        if max_id < 0:
            raise ValueError("No se pudo determinar ultimo ID de especie")

        new_id = max_id + 1
        new_define = f"#define {constant_name:<48}{new_id}"
        new_egg_line = f"#define SPECIES_EGG                                     ({constant_name} + 1)"
        return new_define, old_egg_line, new_egg_line

    def _build_species_info_block(self, data: dict) -> str:
        const = data["constant_name"]
        name = data["species_name"]
        stats = data["base_stats"]
        types = data.get("types", [])
        abilities = data.get("abilities", [])
        type_expr = f"MON_TYPES({', '.join(types)})" if len(types) > 1 else f"MON_TYPES({types[0]})"
        abilities_expr = ", ".join(abilities[:3] + ["ABILITY_NONE"] * max(0, 3 - len(abilities[:3])))
        gender_ratio = data.get("gender_ratio", "PERCENT_FEMALE(50)")
        catch_rate = data.get("catch_rate", 45)
        exp_yield = data.get("exp_yield", 64)
        height = data.get("height", 10)
        weight = data.get("weight", 100)
        egg_groups = data.get("egg_groups", ["EGG_GROUP_MONSTER"])
        if len(egg_groups) > 1:
            egg_expr = f"MON_EGG_GROUPS({', '.join(egg_groups)})"
        else:
            egg_expr = f"MON_EGG_GROUPS({egg_groups[0]})"
        growth_rate = data.get("growth_rate", "GROWTH_MEDIUM_FAST")
        friendship = data.get("friendship", 70)
        body_color = data.get("body_color", "BODY_COLOR_GREEN")
        no_flip = "TRUE" if data.get("no_flip") else "FALSE"
        internal = self._pascal_from_constant(const)
        evolutions_field = ""
        evolutions = data.get("evolutions", [])
        if isinstance(evolutions, list) and len(evolutions) > 0:
            parts = []
            for evo in evolutions:
                method = str(evo.get("method", "EVO_LEVEL")).strip()
                param = str(evo.get("param", "1")).strip()
                target = str(evo.get("target", "SPECIES_NONE")).strip()
                parts.append(f"{{{method}, {param}, {target}}}")
            evolutions_field = f"        .evolutions = EVOLUTION({', '.join(parts)}),\\n"

        return (
            f"\n    [{const}] =\n"
            "    {\n"
            f"        .baseHP        = {stats['hp']},\n"
            f"        .baseAttack    = {stats['attack']},\n"
            f"        .baseDefense   = {stats['defense']},\n"
            f"        .baseSpeed     = {stats['speed']},\n"
            f"        .baseSpAttack  = {stats['sp_attack']},\n"
            f"        .baseSpDefense = {stats['sp_defense']},\n"
            f"        .types = {type_expr},\n"
            f"        .catchRate = {catch_rate},\n"
            f"        .expYield = {exp_yield},\n"
            f"        .genderRatio = {gender_ratio},\n"
            "        .eggCycles = 20,\n"
            f"        .friendship = {friendship},\n"
            f"        .growthRate = {growth_rate},\n"
            f"        .eggGroups = {egg_expr},\n"
            f"        .abilities = {{ {abilities_expr} }},\n"
            f"        .bodyColor = {body_color},\n"
            f"        .noFlip = {no_flip},\n"
            f"        .speciesName = _(\"{name}\"),\n"
            "        .cryId = CRY_NONE,\n"
            "        .natDexNum = NATIONAL_DEX_NONE,\n"
            "        .categoryName = _(\"Custom\"),\n"
            f"        .height = {height},\n"
            f"        .weight = {weight},\n"
            "        .description = COMPOUND_STRING(\n"
            "            \"A custom species added by tool.\\n\"\n"
            "            \"Replace this description later.\"),\n"
            "        .pokemonScale = 256,\n"
            "        .pokemonOffset = 0,\n"
            "        .trainerScale = 256,\n"
            "        .trainerOffset = 0,\n"
            f"        .frontPic = gMonFrontPic_{internal},\n"
            "        .frontPicSize = MON_COORDS_SIZE(64, 64),\n"
            "        .frontPicYOffset = 0,\n"
            "        .frontAnimFrames = sAnims_SingleFramePlaceHolder,\n"
            "        .frontAnimId = ANIM_V_SQUISH_AND_BOUNCE,\n"
            f"        .backPic = gMonBackPic_{internal},\n"
            "        .backPicSize = MON_COORDS_SIZE(64, 64),\n"
            "        .backPicYOffset = 7,\n"
            "        .backAnimId = BACK_ANIM_NONE,\n"
            f"        .palette = gMonPalette_{internal},\n"
            f"        .shinyPalette = gMonShinyPalette_{internal},\n"
            f"        .iconSprite = gMonIcon_{internal},\n"
            "        .iconPalIndex = 0,\n"
            f"        FOOTPRINT({internal})\n"
            "        .levelUpLearnset = sNoneLevelUpLearnset,\n"
            "        .teachableLearnset = sNoneTeachableLearnset,\n"
            "        .eggMoveLearnset = sNoneEggMoveLearnset,\n"
            f"{evolutions_field}"
            "    },\n"
        )

    @staticmethod
    def _find_species_info_block(text: str, constant_name: str) -> str | None:
        pattern = re.compile(
            rf"\n\s*\[{re.escape(constant_name)}\]\s*=\s*\n\s*\{{.*?\n\s*\}},\n",
            flags=re.DOTALL,
        )
        m = pattern.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _find_graphics_block(text: str, internal_name: str) -> str | None:
        pattern = re.compile(
            rf"\n\s*const\s+u32\s+gMonFrontPic_{re.escape(internal_name)}\[\]\s*=.*?\n"
            rf"\s*const\s+u16\s+gMonPalette_{re.escape(internal_name)}\[\]\s*=.*?\n"
            rf"\s*const\s+u32\s+gMonBackPic_{re.escape(internal_name)}\[\]\s*=.*?\n"
            rf"\s*const\s+u16\s+gMonShinyPalette_{re.escape(internal_name)}\[\]\s*=.*?\n"
            rf"\s*const\s+u8\s+gMonIcon_{re.escape(internal_name)}\[\]\s*=.*?\n"
            rf"(?:\s*#if\s+P_FOOTPRINTS\n\s*const\s+u8\s+gMonFootprint_{re.escape(internal_name)}\[\]\s*=.*?\n\s*#endif\s*//P_FOOTPRINTS\n)?",
            flags=re.DOTALL,
        )
        m = pattern.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _build_species_egg_after_delete(species_h_text: str, removed_constant: str) -> tuple[str, str]:
        egg_match = re.search(r"^\s*#define\s+SPECIES_EGG\s+\(([^)]+)\)\s*$", species_h_text, flags=re.MULTILINE)
        if not egg_match:
            raise ValueError("No se encontro #define SPECIES_EGG")
        old_egg_line = egg_match.group(0)

        max_name = None
        max_id = -1
        for m in re.finditer(r"^\s*#define\s+(SPECIES_[A-Z0-9_]+)\s+(\d+)\s*$", species_h_text, flags=re.MULTILINE):
            name = m.group(1)
            value = int(m.group(2))
            if name in {"SPECIES_SHINY_TAG", removed_constant}:
                continue
            if value > max_id:
                max_id = value
                max_name = name
        if not max_name:
            raise ValueError("No se pudo recomputar SPECIES_EGG")
        new_egg_line = f"#define SPECIES_EGG                                     ({max_name} + 1)"
        return new_egg_line, old_egg_line

    def _build_graphics_block(self, data: dict) -> str:
        internal = self._pascal_from_constant(data["constant_name"])
        folder = data["folder_name"]
        return (
            f"\n    const u32 gMonFrontPic_{internal}[] = INCBIN_U32(\"graphics/pokemon/{folder}/front.4bpp.smol\");\n"
            f"    const u16 gMonPalette_{internal}[] = INCBIN_U16(\"graphics/pokemon/{folder}/normal.gbapal\");\n"
            f"    const u32 gMonBackPic_{internal}[] = INCBIN_U32(\"graphics/pokemon/{folder}/back.4bpp.smol\");\n"
            f"    const u16 gMonShinyPalette_{internal}[] = INCBIN_U16(\"graphics/pokemon/{folder}/shiny.gbapal\");\n"
            f"    const u8 gMonIcon_{internal}[] = INCBIN_U8(\"graphics/pokemon/{folder}/icon.4bpp\");\n"
            "#if P_FOOTPRINTS\n"
            f"    const u8 gMonFootprint_{internal}[] = INCBIN_U8(\"graphics/pokemon/{folder}/footprint.1bpp\");\n"
            "#endif //P_FOOTPRINTS\n"
        )

    def _find_levelup_block(self, level_symbol: str) -> tuple[Path | None, str | None]:
        pattern = re.compile(
            rf"static\s+const\s+struct\s+LevelUpMove\s+{re.escape(level_symbol)}\[\]\s*=\s*\{{.*?\n\}};",
            flags=re.DOTALL,
        )
        for file_path in self.read_result.project.level_up_files:
            text = file_path.read_text(encoding="utf-8")
            m = pattern.search(text)
            if m:
                return file_path, m.group(0)
        return None, None

    @staticmethod
    def _build_levelup_block(level_symbol: str, rows: list[dict]) -> str:
        lines = [f"static const struct LevelUpMove {level_symbol}[] = {{"]
        for row in rows:
            level = int(row.get("level", 1))
            move = str(row.get("move", "MOVE_TACKLE"))
            lines.append(f"    LEVEL_UP_MOVE({level}, {move}),")
        lines.append("    LEVEL_UP_END")
        lines.append("};")
        return "\n".join(lines)

    @staticmethod
    def _pascal_from_constant(constant_name: str) -> str:
        parts = constant_name.replace("SPECIES_", "").split("_")
        return "".join(p.capitalize() for p in parts)

    @staticmethod
    def _backup_file(path: Path, backup_dir: Path, project_root: Path) -> None:
        if not path.exists():
            return
        try:
            relative = path.relative_to(project_root)
        except ValueError:
            relative = Path(path.name)
        backup_target = backup_dir / relative
        backup_target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            if backup_target.exists():
                shutil.rmtree(backup_target)
            shutil.copytree(path, backup_target)
        else:
            shutil.copy2(path, backup_target)

    @staticmethod
    def _apply_insert(text: str, step: ChangeStep) -> str:
        if step.insert_before and step.insert_before in text:
            idx = text.index(step.insert_before)
            return text[:idx] + step.new_text + "\n" + text[idx:]
        if step.insert_after and step.insert_after in text:
            idx = text.index(step.insert_after) + len(step.insert_after)
            return text[:idx] + "\n" + step.new_text + text[idx:]
        raise ValueError(f"No se encontro marcador de insercion para {step.target_file}")

    @staticmethod
    def _apply_update(text: str, step: ChangeStep) -> str:
        if not step.old_text:
            raise ValueError("Update sin old_text")
        if step.old_text not in text:
            raise ValueError(f"No se encontro old_text en {step.target_file}")
        return text.replace(step.old_text, step.new_text, 1)
