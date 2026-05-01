from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime
import json
import random

from core.change_plan import ChangePlan, ChangeStep, relpath
from core.species_reader import SpeciesReader
from core.validate_species import ValidationResult


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

        old_species_h, new_species_h = self._rewrite_species_h_for_add(species_h, constant_name)
        plan.add_step(
            ChangeStep(
                target_file=relpath(species_h, self.project_root),
                action="update",
                reason="Agregar constante de especie y recalcular SPECIES_EGG",
                old_text=old_species_h,
                new_text=new_species_h,
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

        if target_asset_dir.exists():
            plan.warnings.append(
                f"Folder existente detectado: graphics/pokemon/{data['folder_name']}. Se usa modo reuse (solo referencias), sin copiar assets."
            )
        else:
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

        family_updated = False
        for family_file in self.read_result.project.family_files:
            family_text = family_file.read_text(encoding="utf-8")
            old_block = self._find_species_info_block(family_text, constant_name)
            if old_block is None:
                continue
            new_block = self._update_species_info_evolutions(old_block, data.get("evolutions", []))
            if new_block != old_block:
                plan.add_step(
                    ChangeStep(
                        target_file=relpath(family_file, self.project_root),
                        action="update",
                        reason="Actualizar evoluciones de la especie",
                        old_text=old_block,
                        new_text=new_block,
                        risk_level="high",
                    )
                )
            family_updated = True
            break
        if not family_updated:
            plan.warnings.append(f"No se encontró bloque de species info para {constant_name}")

        new_folder = str(data.get("folder_name", "")).strip()
        if new_folder:
            graphics_h = self.project_root / "src/data/graphics/pokemon.h"
            graphics_text = graphics_h.read_text(encoding="utf-8")
            internal = self._pascal_from_constant(constant_name)
            old_graphics_block = self._find_graphics_block(graphics_text, internal)
            if old_graphics_block:
                new_graphics_block = self._build_graphics_block({
                    "constant_name": constant_name,
                    "folder_name": new_folder,
                })
                if old_graphics_block != new_graphics_block:
                    plan.add_step(
                        ChangeStep(
                            target_file=relpath(graphics_h, self.project_root),
                            action="update",
                            reason="Actualizar folder gráfico referenciado por la especie",
                            old_text=old_graphics_block,
                            new_text=new_graphics_block,
                            risk_level="high",
                        )
                    )
                folder_path = self.project_root / "graphics/pokemon" / new_folder
                if folder_path.exists():
                    plan.warnings.append(
                        f"Folder existente detectado: graphics/pokemon/{new_folder}. Modo reuse activo (sin copias de assets)."
                    )
                else:
                    plan.warnings.append(
                        f"El folder graphics/pokemon/{new_folder} no existe. Verifica assets antes de compilar."
                    )

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
                new_text="__RUN_TEACHABLES_REGEN__",
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

        replace_in_use_random = bool(
            data.get("replace_in_use_random", False)
            or data.get("replace_in_use_trainers_random", False)
        )
        delete_mode = str(data.get("delete_mode", "safe") or "safe").strip().lower()
        if delete_mode not in {"safe", "replace+delete", "force-delete"}:
            delete_mode = "safe"
        external_hits = self._find_external_species_reference_hits(constant_name)
        external_refs = [f"{h[0]}:{h[1]}" for h in external_hits]
        if external_refs:
            should_replace = replace_in_use_random or delete_mode == "replace+delete"
            if should_replace:
                replacement_steps, replacements_summary = self._build_global_random_replacement_steps(
                    constant_name,
                    external_hits,
                )
                residuals = self._find_residual_references_after_replacement(constant_name, replacement_steps)
                if residuals:
                    plan.errors.append("replace+delete no pudo limpiar todas las referencias de la especie")
                    for ref in residuals[:12]:
                        plan.errors.append(f"ref residual: {ref}")
                    if len(residuals) > 12:
                        plan.errors.append(f"... y {len(residuals) - 12} referencias residuales más")
                    return plan
                for step in replacement_steps:
                    plan.add_step(step)
                for msg in replacements_summary[:20]:
                    plan.warnings.append(msg)
                if len(replacements_summary) > 20:
                    plan.warnings.append(f"... y {len(replacements_summary) - 20} reemplazos más")
            elif delete_mode == "force-delete":
                plan.warnings.append("force-delete activo: se eliminará aunque existan referencias externas")
                for ref in external_refs[:12]:
                    plan.warnings.append(f"ref pendiente: {ref}")
                if len(external_refs) > 12:
                    plan.warnings.append(f"... y {len(external_refs) - 12} referencias más")
            else:
                plan.errors.append(
                    "No se puede eliminar especie: existen referencias externas fuera de species_info/graphics/species.h"
                )
                for ref in external_refs[:12]:
                    plan.errors.append(f"ref: {ref}")
                if len(external_refs) > 12:
                    plan.errors.append(f"... y {len(external_refs) - 12} referencias más")
                plan.warnings.append("Tip: usa delete_mode='replace+delete' (Advanced) para reemplazar referencias automáticamente")
                return plan

        species_h_text = species_h.read_text(encoding="utf-8")
        constant_match = re.search(rf"^\s*#define\s+{re.escape(constant_name)}\s+\d+\s*$", species_h_text, flags=re.MULTILINE)
        if not constant_match:
            plan.errors.append(f"No se pudo ubicar define de {constant_name} en species.h")
            return plan

        old_species_h, new_species_h = self._rewrite_species_h_for_delete(species_h_text, constant_name)
        plan.add_step(
            ChangeStep(
                target_file=relpath(species_h, self.project_root),
                action="update",
                reason="Eliminar constante de especie y recalcular SPECIES_EGG",
                old_text=old_species_h,
                new_text=new_species_h,
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
            graphics_lines = self._find_graphics_symbol_lines(graphics_text, internal)
            if graphics_lines:
                for line in graphics_lines:
                    plan.add_step(
                        ChangeStep(
                            target_file=relpath(graphics_h, self.project_root),
                            action="update",
                            reason="Eliminar símbolo gráfico residual de especie",
                            old_text=line + "\n",
                            new_text="",
                            risk_level="medium",
                        )
                    )
            else:
                plan.warnings.append(f"No se encontró bloque gráfico para {constant_name}")

        folder_name = species.folder_name or data.get("folder_name", "")
        if folder_name:
            if self._folder_is_shared_with_other_species(constant_name, folder_name):
                plan.warnings.append(
                    f"No se elimina graphics/pokemon/{folder_name}: está compartido por otras especies"
                )
            else:
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
            if abs_path.suffix == ".h":
                text = self._repair_preprocessor_directive_concatenation(text)
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
                if step.new_text == "__RUN_TEACHABLES_REGEN__":
                    self._run_teachables_regen()
                else:
                    subprocess.run(step.new_text, cwd=self.project_root, shell=True, check=True)

        self._post_apply_sanity_checks(plan, validation.data)

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

    def _rewrite_species_h_for_add(self, species_h: Path, constant_name: str) -> tuple[str, str]:
        text = species_h.read_text(encoding="utf-8")
        lines = text.splitlines()
        egg_idx = next((i for i, line in enumerate(lines) if re.match(r"^\s*#define\s+SPECIES_EGG\b", line)), -1)
        if egg_idx < 0:
            raise ValueError("No se encontro #define SPECIES_EGG")

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
        lines.insert(egg_idx, f"#define {constant_name:<48}{new_id}")
        egg_line_idx = next((i for i, line in enumerate(lines) if re.match(r"^\s*#define\s+SPECIES_EGG\b", line)), -1)
        if egg_line_idx < 0:
            raise ValueError("No se encontro #define SPECIES_EGG")
        lines[egg_line_idx] = f"#define SPECIES_EGG                                     ({constant_name} + 1)"
        return text, "\n".join(lines) + "\n"

    @staticmethod
    def _rewrite_species_h_for_delete(species_h_text: str, removed_constant: str) -> tuple[str, str]:
        lines = species_h_text.splitlines()
        removed = False
        out_lines: list[str] = []
        for line in lines:
            if re.match(rf"^\s*#define\s+{re.escape(removed_constant)}\s+\d+\s*$", line):
                removed = True
                continue
            out_lines.append(line)
        if not removed:
            raise ValueError(f"No se pudo ubicar define de {removed_constant} en species.h")

        max_name = None
        max_id = -1
        for line in out_lines:
            m = re.match(r"^\s*#define\s+(SPECIES_[A-Z0-9_]+)\s+(\d+)\s*$", line)
            if not m:
                continue
            name = m.group(1)
            value = int(m.group(2))
            if name in {"SPECIES_SHINY_TAG", "SPECIES_EGG"}:
                continue
            if value > max_id:
                max_id = value
                max_name = name
        if not max_name:
            raise ValueError("No se pudo recomputar SPECIES_EGG")

        egg_idx = next((i for i, line in enumerate(out_lines) if re.match(r"^\s*#define\s+SPECIES_EGG\b", line)), -1)
        if egg_idx < 0:
            raise ValueError("No se encontro #define SPECIES_EGG")
        out_lines[egg_idx] = f"#define SPECIES_EGG                                     ({max_name} + 1)"
        return species_h_text, "\n".join(out_lines) + "\n"

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
        raw_description = str(data.get("description") or "").strip()
        if not raw_description:
            raw_description = "A custom species added by tool.\nReplace this description later."
        description_lines = [line.replace("\\", "\\\\").replace('"', '\\"') for line in raw_description.splitlines() if line.strip()]
        if not description_lines:
            description_lines = ["A custom species added by tool.", "Replace this description later."]
        description_expr = "\n".join(
            f'            "{line}{"\\n" if i < len(description_lines) - 1 else ""}"'
            for i, line in enumerate(description_lines)
        )
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
            evolutions_field = f"        .evolutions = EVOLUTION({', '.join(parts)}),\n"

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
            f"{description_expr}),\n"
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
        m = re.search(rf"^\s*\[{re.escape(constant_name)}\]\s*=\s*$", text, flags=re.MULTILINE)
        if not m:
            return None
        block_start = m.start()
        open_brace = text.find("{", m.end())
        if open_brace < 0:
            return None
        close_brace = SpeciesEditor._find_matching_brace(text, open_brace)
        if close_brace < 0:
            return None

        end = close_brace + 1
        while end < len(text) and text[end] in " \t":
            end += 1
        if end < len(text) and text[end] == ',':
            end += 1
        if text[end:end + 2] == "\\n":
            end += 2
            while end < len(text) and text[end] in " \t":
                end += 1
            if end < len(text) and text[end] == '}':
                end += 1
                while end < len(text) and text[end] in " \t":
                    end += 1
                if end < len(text) and text[end] == ',':
                    end += 1
        if end < len(text) and text[end] == "\n":
            end += 1
        return text[block_start:end]

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
    def _find_graphics_symbol_lines(text: str, internal_name: str) -> list[str]:
        out: list[str] = []
        for line in text.splitlines():
            if (
                f"gMonFrontPic_{internal_name}" in line
                or f"gMonBackPic_{internal_name}" in line
                or f"gMonPalette_{internal_name}" in line
                or f"gMonShinyPalette_{internal_name}" in line
                or f"gMonIcon_{internal_name}" in line
                or f"gMonFootprint_{internal_name}" in line
            ):
                out.append(line)
        return out

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
    def _build_evolutions_line(evolutions: list[dict]) -> str:
        parts: list[str] = []
        for evo in evolutions:
            method = str(evo.get("method", "EVO_LEVEL")).strip()
            param = str(evo.get("param", "1")).strip()
            target = str(evo.get("target", "SPECIES_NONE")).strip()
            if not method or not param or not target:
                continue
            parts.append(f"{{{method}, {param}, {target}}}")
        if not parts:
            return ""
        return f"        .evolutions = EVOLUTION({', '.join(parts)}),\n"

    @classmethod
    def _update_species_info_evolutions(cls, block: str, evolutions: list[dict]) -> str:
        evol_line = cls._build_evolutions_line(evolutions)
        out = re.sub(r"^\s*\.evolutions\s*=\s*EVOLUTION\([^\n]*\),\n", "", block, flags=re.MULTILINE)
        out = re.sub(r"^\s*\.evolutions\s*=\s*EVOLUTION\([^\n]*\),\\n\s*\},\n", "    },\n", out, flags=re.MULTILINE)
        if not evol_line:
            return out
        marker = "        .levelUpLearnset ="
        idx = out.find(marker)
        if idx >= 0:
            return out[:idx] + evol_line + out[idx:]
        close_idx = out.rfind("    },")
        if close_idx >= 0:
            return out[:close_idx] + evol_line + out[close_idx:]
        return out

    @staticmethod
    def _find_matching_brace(text: str, open_pos: int) -> int:
        if open_pos < 0 or open_pos >= len(text) or text[open_pos] != "{":
            return -1
        depth = 0
        in_string = False
        i = open_pos
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
            left = text[:idx].rstrip("\n")
            right = text[idx:].lstrip("\n")
            center = step.new_text.strip("\n")
            return left + "\n\n" + center + "\n\n" + right
        if step.insert_after and step.insert_after in text:
            idx = text.index(step.insert_after) + len(step.insert_after)
            left = text[:idx].rstrip("\n")
            right = text[idx:].lstrip("\n")
            center = step.new_text.strip("\n")
            return left + "\n\n" + center + "\n\n" + right
        raise ValueError(f"No se encontro marcador de insercion para {step.target_file}")

    @staticmethod
    def _apply_update(text: str, step: ChangeStep) -> str:
        if not step.old_text:
            raise ValueError("Update sin old_text")
        if step.old_text not in text:
            raise ValueError(f"No se encontro old_text en {step.target_file}")
        return text.replace(step.old_text, step.new_text, 1)

    def _post_apply_sanity_checks(self, plan: ChangePlan, data: dict) -> None:
        touched_files = {
            self.project_root / step.target_file
            for step in plan.steps
            if step.action in {"insert", "update"}
        }
        for path in touched_files:
            if path.exists() and path.is_file() and path.suffix == ".h":
                text = path.read_text(encoding="utf-8", errors="ignore")
                self._assert_preprocessor_balance(path, text)

        species_h = self.project_root / "include/constants/species.h"
        if species_h.exists():
            stext = species_h.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\d+#define\s+SPECIES_EGG\b", stext):
                raise ValueError("Sanity check falló: SPECIES_EGG quedó pegado a otro define")
            if not re.search(r"^\s*#define\s+SPECIES_EGG\s+\([^)]+\)\s*$", stext, flags=re.MULTILINE):
                raise ValueError("Sanity check falló: falta define válido de SPECIES_EGG")

        if plan.mode == "delete":
            constant = str(data.get("constant_name", "")).strip()
            internal = self._pascal_from_constant(constant) if constant else ""
            folder_name = str(data.get("folder_name", "")).strip()

            if constant:
                species_h = self.project_root / "include/constants/species.h"
                if species_h.exists():
                    txt = species_h.read_text(encoding="utf-8", errors="ignore")
                    if re.search(rf"^\s*#define\s+{re.escape(constant)}\b", txt, flags=re.MULTILINE):
                        raise ValueError(f"Sanity check falló: sigue existiendo {constant} en species.h")

            graphics_h = self.project_root / "src/data/graphics/pokemon.h"
            if graphics_h.exists() and internal:
                gtxt = graphics_h.read_text(encoding="utf-8", errors="ignore")
                for token in [
                    f"gMonFrontPic_{internal}",
                    f"gMonBackPic_{internal}",
                    f"gMonPalette_{internal}",
                    f"gMonShinyPalette_{internal}",
                    f"gMonIcon_{internal}",
                    f"gMonFootprint_{internal}",
                ]:
                    if token in gtxt:
                        raise ValueError(f"Sanity check falló: símbolo residual detectado ({token})")

            if folder_name:
                folder = self.project_root / "graphics/pokemon" / folder_name
                if folder.exists():
                    raise ValueError(f"Sanity check falló: carpeta de assets no eliminada ({folder_name})")

    @staticmethod
    def _assert_preprocessor_balance(path: Path, text: str) -> None:
        depth = 0
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#if") or stripped.startswith("#ifdef") or stripped.startswith("#ifndef"):
                depth += 1
            elif stripped.startswith("#endif"):
                depth -= 1
                if depth < 0:
                    raise ValueError(f"Preprocessor desbalanceado en {path}")
        if depth != 0:
            raise ValueError(f"Preprocessor desbalanceado en {path}")

    @staticmethod
    def _repair_preprocessor_directive_concatenation(text: str) -> str:
        repaired = text
        repaired = re.sub(r"(#if[^\n]*)(#if\b)", r"\1\n\2", repaired)
        repaired = re.sub(r"(#if[^\n]*)(#ifdef\b)", r"\1\n\2", repaired)
        repaired = re.sub(r"(#if[^\n]*)(#ifndef\b)", r"\1\n\2", repaired)
        repaired = re.sub(r"(#endif[^\n]*)(#endif\b)", r"\1\n\2", repaired)
        return repaired

    def _find_external_species_references(self, constant_name: str) -> list[str]:
        return [f"{h[0]}:{h[1]}" for h in self._find_external_species_reference_hits(constant_name)]

    def _find_external_species_reference_hits(self, constant_name: str) -> list[tuple[str, int, str]]:
        allowed_files = {
            str((self.project_root / "include/constants/species.h").resolve()),
            str((self.project_root / "src/data/graphics/pokemon.h").resolve()),
        }
        for p in self.read_result.project.family_files:
            allowed_files.add(str(p.resolve()))

        refs: list[tuple[str, int, str]] = []
        species_token = constant_name.replace("SPECIES_", "", 1)
        species_pattern = re.compile(rf"\b{re.escape(constant_name)}\b")
        macro_pattern = re.compile(rf"\bEC_POKEMON_NATIONAL\({re.escape(species_token)}\)")
        for ext in ("*.h", "*.c", "*.inc", "*.txt", "*.json", "*.party"):
            for path in self.project_root.rglob(ext):
                if "/build/" in str(path):
                    continue
                if str(path.resolve()) in allowed_files:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if species_pattern.search(line) or macro_pattern.search(line):
                        refs.append((str(path), i, line.strip()))
        return refs

    @staticmethod
    def _is_trainer_reference_file(path: Path) -> bool:
        low = str(path).lower()
        return "trainer" in low

    def _build_global_random_replacement_steps(
        self,
        removed_constant: str,
        hits: list[tuple[str, int, str]],
    ) -> tuple[list[ChangeStep], list[str]]:
        pool = sorted(
            [
                c for c in self.species_by_constant.keys()
                if c not in {removed_constant, "SPECIES_NONE", "SPECIES_EGG"}
            ]
        )
        if not pool:
            raise ValueError("No hay especies disponibles para reemplazo aleatorio")

        by_file: dict[str, list[tuple[int, str]]] = {}
        for p, line_no, line_text in hits:
            by_file.setdefault(p, []).append((line_no, line_text))

        rng = random.Random(removed_constant)
        steps: list[ChangeStep] = []
        summary: list[str] = []
        species_token = removed_constant.replace("SPECIES_", "", 1)
        pattern_species = re.compile(rf"\b{re.escape(removed_constant)}\b")
        pattern_ec_national = re.compile(rf"\bEC_POKEMON_NATIONAL\({re.escape(species_token)}\)")

        for file_path in sorted(by_file.keys()):
            path = Path(file_path)
            old_text = path.read_text(encoding="utf-8")
            new_text = old_text
            replacement_count = 0

            def _random_species() -> str:
                return rng.choice(pool)

            while True:
                m_ec = pattern_ec_national.search(new_text)
                if not m_ec:
                    break
                replacement = _random_species().replace("SPECIES_", "", 1)
                repl_text = f"EC_POKEMON_NATIONAL({replacement})"
                new_text = new_text[:m_ec.start()] + repl_text + new_text[m_ec.end():]
                replacement_count += 1

            while True:
                m = pattern_species.search(new_text)
                if not m:
                    break
                replacement = _random_species()
                new_text = new_text[:m.start()] + replacement + new_text[m.end():]
                replacement_count += 1

            if replacement_count == 0 or new_text == old_text:
                continue

            steps.append(
                ChangeStep(
                    target_file=relpath(path, self.project_root),
                    action="update",
                    reason="Reemplazar especie eliminada en referencias externas (aleatorio)",
                    old_text=old_text,
                    new_text=new_text,
                    risk_level="high",
                )
            )
            summary.append(f"random replace: {relpath(path, self.project_root)} ({replacement_count} ocurrencias)")

        return steps, summary

    def _find_residual_references_after_replacement(self, removed_constant: str, replacement_steps: list[ChangeStep]) -> list[str]:
        species_token = removed_constant.replace("SPECIES_", "", 1)
        species_pattern = re.compile(rf"\b{re.escape(removed_constant)}\b")
        macro_pattern = re.compile(rf"\bEC_POKEMON_NATIONAL\({re.escape(species_token)}\)")
        allowed_files = {
            str((self.project_root / "include/constants/species.h").resolve()),
            str((self.project_root / "src/data/graphics/pokemon.h").resolve()),
        }
        for p in self.read_result.project.family_files:
            allowed_files.add(str(p.resolve()))
        replacement_by_file: dict[str, str] = {
            step.target_file: step.new_text
            for step in replacement_steps
            if step.action == "update"
        }
        residuals: list[str] = []
        for ext in ("*.h", "*.c", "*.inc", "*.txt", "*.json", "*.party"):
            for path in self.project_root.rglob(ext):
                path_str = str(path)
                if "/build/" in path_str:
                    continue
                if str(path.resolve()) in allowed_files:
                    continue
                rel = relpath(path, self.project_root)
                if rel in replacement_by_file:
                    text = replacement_by_file[rel]
                else:
                    try:
                        text = path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if species_pattern.search(line) or macro_pattern.search(line):
                        residuals.append(f"{path}:{i}")
                        break
        return residuals

    def _run_teachables_regen(self) -> None:
        helper_dir = self.project_root / "tools/learnset_helpers"
        build_dir = helper_dir / "build"
        build_dir.mkdir(parents=True, exist_ok=True)

        tutors_json = build_dir / "all_tutors.json"
        types_json = build_dir / "all_teaching_types.json"

        subprocess.run(
            ["python3", "tools/learnset_helpers/make_tutors.py", str(tutors_json)],
            cwd=self.project_root,
            check=True,
        )
        subprocess.run(
            ["python3", "tools/learnset_helpers/make_teaching_types.py", str(types_json)],
            cwd=self.project_root,
            check=True,
        )
        subprocess.run(
            ["python3", "tools/learnset_helpers/make_teachables.py", str(build_dir)],
            cwd=self.project_root,
            check=True,
        )

    def _folder_is_shared_with_other_species(self, current_constant: str, folder_name: str) -> bool:
        folder_key = str(folder_name).strip().lower()
        if not folder_key:
            return False
        for constant, species in self.species_by_constant.items():
            if constant == current_constant:
                continue
            other_folder = str(getattr(species, "folder_name", "") or "").strip().lower()
            if other_folder and other_folder == folder_key:
                return True
        return False
