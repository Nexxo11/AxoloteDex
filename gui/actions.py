from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback

import dearpygui.dearpygui as dpg
from PIL import Image

from core.build_check import BuildResult, parse_build_output, write_build_outputs
from gui.components import TAGS
from gui.state import GuiState, default_editor_data, load_config, save_config
from core.species_editor import SpeciesEditor
from core.species_linter import lint_species_definition, write_lint_report
from core.sprite_loader import load_texture_data, resolve_preview_paths
from core.validate_species import validate_species_definition
from gui.themes import PALETTE


class GuiActions:
    MAX_SPECIES_NAME_LEN = 12
    MAX_DESCRIPTION_LEN = 180

    def __init__(self, state: GuiState, config_path: Path) -> None:
        self.state = state
        self.editor: SpeciesEditor | None = None
        self.config_path = config_path
        self._texture_seq = 0
        self._preview_texture_tags = {"front": "tex_front", "back": "tex_back", "icon": "tex_icon", "footprint": "tex_footprint"}
        self._type_texture_tags = {"type1": "tex_type1", "type2": "tex_type2"}
        self._type_picker_texture_tags: dict[str, str] = {}
        self._icon_button_theme: int | None = None
        self._settings_button_theme: int | None = None
        self._evo_hover_index: int = -1
        self._evo_hover_texture_tag: str = "tex_front"
        self._evo_row_tags: list[str] = []
        self._evo_hover_last_seen: float = 0.0
        self._evo_last_click_label: str = ""
        self._evo_last_click_time: float = 0.0
        self._evo_tooltip_anim_interval = 0.38
        self._evo_tooltip_last_tick = 0.0
        self._evo_tooltip_frame = 0
        self._evo_tooltip_hover_idx = -1
        self._evo_tooltip_rows: dict[int, dict[str, str | bool]] = {}
        self._evo_tooltip_tex_cache: dict[tuple[str, int], tuple[str, int, int]] = {}
        self._evo_tooltip_scale_px = 192
        self._stats_radar_refresh_interval = 0.28
        self._stats_radar_last_tick = 0.0
        self._last_valid_description: str = ""
        self._theme_switcher = None
        self._cry_audio_map: dict[str, Path] = {}
        self._cry_player_proc: subprocess.Popen | None = None
        self._preview_throttle_seconds = 0.15
        self._last_preview_refresh = 0.0
        self._preview_pending = False
        self._icon_anim_interval = 0.33
        self._icon_anim_last = 0.0
        self._icon_anim_frame = 0
        self._shortcut_last_trigger: dict[str, float] = {}
        self._build_thread: threading.Thread | None = None
        self._build_result: BuildResult | None = None
        self._build_output_buffer: list[str] = []
        self._delete_thread: threading.Thread | None = None
        self._delete_error: str | None = None
        self._delete_messages: str = ""
        self._delete_in_progress: bool = False
        self._status_validation = "idle"
        self._status_dryrun = "idle"
        self._status_build = "idle"
        self._primary_button_theme: int | None = None
        self._secondary_button_theme: int | None = None
        self._disabled_button_theme: int | None = None
        self._last_layout_size: tuple[int, int] = (-1, -1)
        self._suspend_dirty_events: bool = False
        self._cached_payload_sig: str = ""
        self._cached_payload_after_lint: dict | None = None
        self._cached_validation = None
        self._cached_lint_ok: bool | None = None
        self._perf_stats: dict[str, list[float]] = {}
        self._radar_drag_index: int | None = None
        self._radar_hover_index: int | None = None
        self._radar_mouse_was_down: bool = False
        self._radar_last_size: tuple[float, float] = (520.0, 300.0)
        self._radar_debug_text: str = ""
        self._radar_drag_changed: bool = False
        self._radar_initialized: bool = False
        self._radar_drag_start_mouse: tuple[float, float] | None = None
        self._radar_drag_snapshot: dict | None = None

    def set_button_themes(self, primary_theme: int, secondary_theme: int, disabled_theme: int | None = None) -> None:
        self._primary_button_theme = primary_theme
        self._secondary_button_theme = secondary_theme
        self._disabled_button_theme = disabled_theme if disabled_theme is not None else secondary_theme
        self._refresh_apply_enabled()

    def set_theme_switcher(self, switcher) -> None:
        self._theme_switcher = switcher

    @staticmethod
    def _to_rgba255(value) -> tuple[int, int, int, int]:
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            vals = list(value)
            if any(isinstance(v, float) and 0.0 <= v <= 1.0 for v in vals[:3]):
                rgb = [int(max(0.0, min(1.0, float(v))) * 255) for v in vals[:3]]
            else:
                rgb = [int(max(0, min(255, int(v)))) for v in vals[:3]]
            a_src = vals[3] if len(vals) > 3 else 255
            if isinstance(a_src, float) and 0.0 <= a_src <= 1.0:
                a = int(max(0.0, min(1.0, a_src)) * 255)
            else:
                a = int(max(0, min(255, int(a_src))))
            return rgb[0], rgb[1], rgb[2], a
        return 0, 0, 0, 255

    def _custom_theme_palette_from_ui(self) -> dict[str, tuple[int, int, int, int]]:
        mapping = {
            "background": "settings_color_background",
            "panel": "settings_color_panel",
            "input": "settings_color_input",
            "border": "settings_color_border",
            "primary": "settings_color_primary",
            "primary_hover": "settings_color_primary_hover",
            "text": "settings_color_text",
            "muted_text": "settings_color_muted_text",
        }
        out: dict[str, tuple[int, int, int, int]] = {}
        for key, tag_name in mapping.items():
            tag = TAGS.get(tag_name)
            if tag and dpg.does_item_exist(tag):
                out[key] = self._to_rgba255(dpg.get_value(tag))
        return out

    def _persist_custom_theme(self) -> None:
        self._persist_config({"settings_custom_theme": self._custom_theme_palette_from_ui()})

    def _update_action_button_progress(self) -> None:
        if self._primary_button_theme is None or self._secondary_button_theme is None or self._disabled_button_theme is None:
            return
        if dpg.does_item_exist(TAGS["validate_btn"]):
            btn_enabled = bool(dpg.is_item_enabled(TAGS["validate_btn"]))
            dpg.bind_item_theme(TAGS["validate_btn"], self._primary_button_theme if btn_enabled else self._disabled_button_theme)
        if dpg.does_item_exist(TAGS["dryrun_btn"]):
            btn_enabled = bool(dpg.is_item_enabled(TAGS["dryrun_btn"]))
            dpg.bind_item_theme(TAGS["dryrun_btn"], self._primary_button_theme if btn_enabled else self._disabled_button_theme)
        if dpg.does_item_exist(TAGS["apply_btn"]):
            btn_enabled = bool(dpg.is_item_enabled(TAGS["apply_btn"]))
            dpg.bind_item_theme(TAGS["apply_btn"], self._primary_button_theme if btn_enabled else self._disabled_button_theme)

    def _set_message(self, message: str) -> None:
        msg = message.strip().splitlines()[-1] if message else ""
        low = msg.lower()
        color = PALETTE["muted_text"]
        if "error" in low or "traceback" in low or "fall" in low:
            color = PALETTE["error"]
        elif "ok" in low or "correct" in low or "exitosa" in low:
            color = PALETTE["success"]
        elif "warn" in low or "fallback" in low:
            color = PALETTE["warning"]
        dpg.set_value(TAGS["message_text"], msg or "Ready")
        dpg.configure_item(TAGS["message_text"], color=color)

    def _record_perf(self, name: str, elapsed_ms: float) -> None:
        bucket = self._perf_stats.setdefault(name, [])
        bucket.append(elapsed_ms)
        if len(bucket) > 40:
            del bucket[:-40]

    @staticmethod
    def _clamped_int(value, low: int, high: int, fallback: int) -> int:
        try:
            n = int(value)
        except Exception:
            n = fallback
        return max(low, min(high, n))

    @staticmethod
    def _gender_ratio_to_percent(value: str | int | None) -> int:
        if isinstance(value, int):
            return max(0, min(100, value))
        text = str(value or "").strip()
        m = re.match(r"^PERCENT_FEMALE\((\d+)\)$", text)
        if m:
            return max(0, min(100, int(m.group(1))))
        return 50

    @staticmethod
    def _int_from_raw(value: str | int | None, fallback: int) -> int:
        if isinstance(value, int):
            return value
        text = str(value or "").strip()
        m = re.match(r"^-?\d+$", text)
        if m:
            return int(text)
        return fallback

    def _refresh_stats_radar(self) -> None:
        if not dpg.does_item_exist(TAGS["stats_radar_drawlist"]):
            return

        draw_tag = TAGS["stats_radar_drawlist"]
        if not self.state.project_loaded:
            dpg.delete_item(draw_tag, children_only=True)
            return

        rect = self._safe_item_rect_min_size(TAGS["stats_radar_drawlist"])
        if rect is not None:
            _, rect_size = rect
            if float(rect_size[0]) < 260.0 or float(rect_size[1]) < 180.0:
                dpg.delete_item(draw_tag, children_only=True)
                return
            self._radar_last_size = (
                max(220.0, float(rect_size[0])),
                max(180.0, float(rect_size[1])),
            )

        labels = ["hp", "attack", "defense", "speed", "sp_defense", "sp_attack"]
        base_values = [
            self._clamped_int(dpg.get_value(tag) if dpg.does_item_exist(tag) else 1, 1, 255, 1)
            for tag in labels
        ]
        labels_text = ["HP", "Attack", "Defense", "Speed", "Sp. Def", "Sp. Atk"]
        stat_colors = [
            (120, 222, 120, 255),
            (246, 118, 118, 255),
            (120, 170, 246, 255),
            (246, 214, 120, 255),
            (162, 134, 246, 255),
            (136, 232, 246, 255),
        ]
        n = len(base_values)

        geom = self._stats_radar_geometry()
        panel_w = geom["panel_w"]
        panel_h = geom["panel_h"]
        cx = geom["cx"]
        cy = geom["cy"]
        radius = geom["radius"]

        def poly_points(values: list[int], close: bool = True) -> list[tuple[float, float]]:
            pts: list[tuple[float, float]] = []
            for i, val in enumerate(values):
                angle = (2.0 * math.pi * i / n) - (math.pi / 2.0)
                r = radius * (float(val) / 255.0)
                pts.append((cx + (r * math.cos(angle)), cy + (r * math.sin(angle))))
            if close and pts:
                pts.append(pts[0])
            return pts

        dpg.delete_item(draw_tag, children_only=True)

        ring_colors = [
            (148, 193, 232, 50),
            (148, 193, 232, 64),
            (148, 193, 232, 88),
            (210, 235, 255, 140),
        ]
        for idx, scale in enumerate((0.25, 0.5, 0.75, 1.0)):
            ring_values = [int(255 * scale)] * n
            ring_pts = poly_points(ring_values)
            for i in range(len(ring_pts) - 1):
                dpg.draw_line(ring_pts[i], ring_pts[i + 1], color=ring_colors[idx], thickness=1.5, parent=draw_tag)

        axis_pts = poly_points([255] * n, close=False)
        for i, p in enumerate(axis_pts):
            dpg.draw_line((cx, cy), p, color=(178, 210, 235, 90), thickness=1.0, parent=draw_tag)
            vx = p[0] - cx
            vy = p[1] - cy
            mag = math.sqrt(vx * vx + vy * vy) or 1.0
            tx = p[0] + (vx / mag) * 18.0
            ty = p[1] + (vy / mag) * 18.0
            if i == 0:
                text_pos = (cx - 7, ty - 12)
            elif i == 1:
                text_pos = (tx + 2, ty - 4)
            elif i == 2:
                text_pos = (tx + 2, ty + 2)
            elif i == 3:
                text_pos = (tx - 14, ty - 2)
            elif i == 4:
                text_pos = (tx - 58, ty + 2)
            else:
                text_pos = (tx - 58, ty - 6)
            dpg.draw_text(text_pos, labels_text[i], color=stat_colors[i], size=14, parent=draw_tag)

        base_pts = poly_points(base_values)
        dpg.draw_polygon(base_pts[:-1], color=(255, 255, 255, 220), fill=(231, 215, 96, 84), thickness=2.0, parent=draw_tag)
        for i in range(len(base_pts) - 1):
            dpg.draw_line(base_pts[i], base_pts[i + 1], color=(255, 255, 255, 235), thickness=2.0, parent=draw_tag)
        for i, p in enumerate(base_pts[:-1]):
            c = stat_colors[i]
            dpg.draw_circle(p, 3.3, color=(225, 235, 245, 255), fill=c, thickness=1.2, parent=draw_tag)

    def _stats_radar_geometry(self) -> dict[str, float]:
        panel_w, panel_h = self._radar_last_size
        cx = panel_w * 0.5
        cy = panel_h * 0.50
        radius = min(panel_w * 0.28, panel_h * 0.30)
        return {"panel_w": panel_w, "panel_h": panel_h, "cx": cx, "cy": cy, "radius": radius}

    @staticmethod
    def _item_rect(tag: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
        try:
            state = dpg.get_item_state(tag)
        except Exception:
            return None
        rect_min = state.get("rect_min")
        rect_size = state.get("rect_size")
        if (
            not isinstance(rect_min, (list, tuple))
            or not isinstance(rect_size, (list, tuple))
            or len(rect_min) < 2
            or len(rect_size) < 2
        ):
            return None
        return (float(rect_min[0]), float(rect_min[1])), (float(rect_size[0]), float(rect_size[1]))

    @staticmethod
    def _safe_item_rect_min_size(tag: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
        try:
            mn = dpg.get_item_rect_min(tag)
            sz = dpg.get_item_rect_size(tag)
        except Exception:
            return None
        if not mn or not sz or len(mn) < 2 or len(sz) < 2:
            return None
        return (float(mn[0]), float(mn[1])), (float(sz[0]), float(sz[1]))

    def _handle_stats_radar_drag(self) -> None:
        return

    def on_stats_radar_clicked(self, sender=None, app_data=None, user_data=None) -> None:
        return

    def on_stats_radar_released(self, sender=None, app_data=None, user_data=None) -> None:
        return

    @staticmethod
    def _payload_signature(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _invalidate_payload_cache(self) -> None:
        self._cached_payload_sig = ""
        self._cached_payload_after_lint = None
        self._cached_validation = None
        self._cached_lint_ok = None

    def _prepare_payload_validation_lint(self) -> tuple[dict, object, bool, str]:
        if not self.editor:
            raise ValueError("Load a project first")
        payload = self._editor_payload()
        sig = self._payload_signature(payload)
        if (
            sig == self._cached_payload_sig
            and self._cached_payload_after_lint is not None
            and self._cached_validation is not None
            and self._cached_lint_ok is not None
        ):
            return self._cached_payload_after_lint, self._cached_validation, self._cached_lint_ok, sig

        t0 = time.perf_counter()
        fallback_folder = self.editor.pick_fallback_folder()
        validation = validate_species_definition(payload, Path.cwd() / "gui_payload.json", Path(self.state.project_path), fallback_folder)
        payload_after_lint, lint_ok = self._run_lint(payload, validation.used_fallback)
        self._record_perf("validate+lint", (time.perf_counter() - t0) * 1000.0)

        self._cached_payload_sig = sig
        self._cached_payload_after_lint = payload_after_lint
        self._cached_validation = validation
        self._cached_lint_ok = lint_ok
        return payload_after_lint, validation, lint_ok, sig

    def _compat_text_and_color(self) -> tuple[str, tuple[int, int, int, int]]:
        if not self.state.project_loaded:
            return "no compatible", PALETTE["error"]
        if self._status_build == "error" or self._status_validation == "error" or self._status_dryrun == "error":
            return "no compatible", PALETTE["error"]
        if self._status_build == "running" or self._status_dryrun == "dirty":
            return "partial", PALETTE["warning"]
        return "compatible", PALETTE["success"]

    def _persist_config(self, updates: dict) -> None:
        cfg = load_config(self.config_path)
        cfg.update(updates)
        save_config(self.config_path, cfg)

    def _update_header_status(self) -> None:
        project = "loaded" if self.state.project_loaded else "idle"
        dpg.set_value(TAGS["status_project"], f"Project: {project}")
        dpg.set_value(TAGS["status_validation"], f"Validation: {self._status_validation}")
        dpg.set_value(TAGS["status_dryrun"], f"Dry-run: {self._status_dryrun}")
        dpg.set_value(TAGS["status_build"], f"Build: {self._status_build}")
        compat_text, compat_color = self._compat_text_and_color()
        if dpg.does_item_exist(TAGS["compat_status"]):
            dpg.set_value(TAGS["compat_status"], f"Compatibility: {compat_text}")
            dpg.configure_item(TAGS["compat_status"], color=compat_color)

    def _refresh_apply_enabled(self) -> None:
        validate_enabled = bool(self.state.project_loaded and self.state.editor_dirty)
        dryrun_enabled = bool(validate_enabled and self.state.validation_ok)
        apply_enabled = bool(self.state.dry_run_valid)
        if dpg.does_item_exist(TAGS["validate_btn"]):
            dpg.configure_item(TAGS["validate_btn"], enabled=validate_enabled)
        if dpg.does_item_exist(TAGS["dryrun_btn"]):
            dpg.configure_item(TAGS["dryrun_btn"], enabled=dryrun_enabled)
        if dpg.does_item_exist(TAGS["apply_btn"]):
            dpg.configure_item(TAGS["apply_btn"], enabled=apply_enabled)
        self._update_action_button_progress()
        if dpg.does_item_exist(TAGS["apply_hint"]):
            if apply_enabled:
                dpg.set_value(TAGS["apply_hint"], "Full flow complete: ready to apply changes")
                dpg.configure_item(TAGS["apply_hint"], color=PALETTE["success"])
            else:
                dpg.set_value(TAGS["apply_hint"], "Flow: Validate -> Generate dry-run -> Apply changes")
                dpg.configure_item(TAGS["apply_hint"], color=PALETTE["warning"])

    def _load_options_from_project(self) -> None:
        if not self.state.project_loaded:
            return
        root = Path(self.state.project_path)
        type_file = root / "include/constants/pokemon.h"
        ability_file = root / "include/constants/abilities.h"
        item_file = root / "include/constants/items.h"
        moves_file = root / "include/constants/moves.h"
        map_groups_file = root / "include/constants/map_groups.h"
        region_map_file = root / "include/constants/region_map_sections.h"
        tmhm_file = root / "include/constants/tms_hms.h"
        tutor_file = root / "src/data/tutor_moves.h"
        cries_file = root / "include/constants/cries.h"

        def _load_enum_tokens(path: Path, prefix: str) -> list[str]:
            out: list[str] = []
            seen: set[str] = set()
            if not path.exists():
                return out
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.match(rf"\s*({prefix}[A-Z0-9_]+)\s*(?:=\s*[^,]+)?\s*,", line)
                if m:
                    token = m.group(1)
                    if token not in seen:
                        seen.add(token)
                        out.append(token)
                m2 = re.match(rf"\s*#define\s+({prefix}[A-Z0-9_]+)\b", line)
                if m2:
                    token = m2.group(1)
                    if token not in seen:
                        seen.add(token)
                        out.append(token)
            return out

        types = _load_enum_tokens(type_file, "TYPE_")
        abilities = _load_enum_tokens(ability_file, "ABILITY_")
        items = _load_enum_tokens(item_file, "ITEM_")
        moves = _load_enum_tokens(moves_file, "MOVE_")
        maps = _load_enum_tokens(map_groups_file, "MAP_")
        if not maps:
            maps = _load_enum_tokens(region_map_file, "MAPSEC_")
        natures = _load_enum_tokens(type_file, "NATURE_")
        cries = _load_enum_tokens(cries_file, "CRY_")
        evo_methods = _load_enum_tokens(type_file, "EVO_")
        condition_tokens = _load_enum_tokens(type_file, "IF_")
        evo_methods = _load_enum_tokens(type_file, "EVO_")

        tmhm_moves: list[str] = []
        if tmhm_file.exists():
            text = tmhm_file.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"F\(([_A-Z0-9]+)\)", text):
                tmhm_moves.append(f"MOVE_{m.group(1)}")

        tutor_moves: list[str] = []
        if tutor_file.exists():
            text = tutor_file.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"F\(([_A-Z0-9]+)\)", text):
                tutor_moves.append(f"MOVE_{m.group(1)}")
            if not tutor_moves:
                tutor_moves = sorted({m.group(0) for m in re.finditer(r"\bMOVE_[A-Z0-9_]+\b", text)})
        tutor_moves = [m for m in tutor_moves if m != "MOVE_UNAVAILABLE"]

        self.state.type_options = types if types else ["TYPE_NORMAL"]
        self.state.ability_options = abilities if abilities else ["ABILITY_NONE"]
        self.state.item_options = items if items else ["ITEM_NONE"]
        self.state.move_options = moves if moves else ["MOVE_TACKLE"]
        self.state.map_options = maps if maps else ["MAP_NONE"]
        self.state.nature_options = natures if natures else ["NATURE_HARDY"]
        self.state.tmhm_options = sorted(set(tmhm_moves)) if tmhm_moves else ["MOVE_TACKLE"]
        self.state.tutor_options = sorted(set(tutor_moves)) if tutor_moves else ["MOVE_TACKLE"]
        self.state.cry_options = cries if cries else ["CRY_NONE"]
        self.state.condition_options = condition_tokens if condition_tokens else ["IF_KNOWS_MOVE"]

        dpg.configure_item("type1", items=self.state.type_options)
        dpg.configure_item("type2", items=[""] + self.state.type_options)
        dpg.configure_item("ability1", items=self.state.ability_options)
        dpg.configure_item("ability2", items=self.state.ability_options)
        dpg.configure_item("ability_hidden", items=self.state.ability_options)
        dpg.configure_item("evo_item_param", items=self.state.item_options)
        dpg.configure_item("evo_trade_item_param", items=["ITEM_NONE"] + self.state.item_options)
        dpg.configure_item("move_name", items=self.state.move_options)
        dpg.configure_item("tmhm_move", items=self.state.tmhm_options)
        dpg.configure_item("tutor_move", items=self.state.tutor_options)
        dpg.configure_item("cry_id", items=self.state.cry_options)
        if dpg.does_item_exist("evo_method"):
            items = evo_methods if evo_methods else ["EVO_LEVEL", "EVO_ITEM", "EVO_TRADE", "EVO_FRIENDSHIP"]
            dpg.configure_item("evo_method", items=items)
        if dpg.does_item_exist("evo_condition_type"):
            dpg.configure_item("evo_condition_type", items=self.state.condition_options)
        if dpg.does_item_exist("evo_condition_value"):
            dpg.configure_item("evo_condition_value", items=self.state.move_options)
        if dpg.does_item_exist("evo_method"):
            evo_items = evo_methods if evo_methods else ["EVO_LEVEL", "EVO_ITEM", "EVO_TRADE", "EVO_FRIENDSHIP"]
            dpg.configure_item("evo_method", items=evo_items)
            current_method = str(dpg.get_value("evo_method") or "")
            if current_method not in evo_items:
                dpg.set_value("evo_method", evo_items[0])
        if self.state.item_options:
            dpg.set_value("evo_item_param", self.state.item_options[0])
        if self.state.move_options:
            dpg.set_value("move_name", self.state.move_options[0])
        if self.state.tmhm_options:
            dpg.set_value("tmhm_move", self.state.tmhm_options[0])
        if self.state.tutor_options:
            dpg.set_value("tutor_move", self.state.tutor_options[0])
        if self.state.cry_options:
            current_cry = str(dpg.get_value("cry_id") or "CRY_NONE") if dpg.does_item_exist("cry_id") else "CRY_NONE"
            dpg.set_value("cry_id", current_cry if current_cry in self.state.cry_options else self.state.cry_options[0])
        self._rebuild_type_icon_pickers()
        self._refresh_type_icons()

    def _update_texture(
        self,
        slot: str,
        image_path: Path,
        frame_index: int,
        palette_mode: str,
        palette_variant: str,
    ) -> tuple[str, int, int]:
        w, h, data = load_texture_data(
            image_path,
            kind=slot,
            scale=2,
            frame_index=frame_index,
            palette_mode=palette_mode,
            palette_variant=palette_variant,
        )
        self._texture_seq += 1
        tag = f"tex_{slot}_{self._texture_seq}"
        dpg.add_static_texture(w, h, data, tag=tag, parent="tex_registry")
        return tag, w, h

    @staticmethod
    def _transparent_texture(size: int = 32) -> tuple[int, int, list[float]]:
        return size, size, [0.0, 0.0, 0.0, 0.0] * (size * size)

    @staticmethod
    def _empty_type_slot_texture(width: int = 64, height: int = 32) -> tuple[int, int, list[float]]:
        r, g, b, a = 0.28, 0.30, 0.34, 1.0
        return width, height, [r, g, b, a] * (width * height)

    @staticmethod
    def _rgba_to_dpg_data(img: Image.Image) -> tuple[int, int, list[float]]:
        rgba = img.convert("RGBA")
        w, h = rgba.size
        raw = rgba.tobytes()
        data: list[float] = []
        for i in range(0, len(raw), 4):
            data.extend([raw[i] / 255.0, raw[i + 1] / 255.0, raw[i + 2] / 255.0, raw[i + 3] / 255.0])
        return w, h, data

    @staticmethod
    def _apply_transparent_bg_from_corners(img: Image.Image) -> Image.Image:
        rgba = img.convert("RGBA")
        w, h = rgba.size
        px = rgba.load()
        key_colors = {
            px[0, 0][:3],
            px[max(0, w - 1), 0][:3],
            px[0, max(0, h - 1)][:3],
            px[max(0, w - 1), max(0, h - 1)][:3],
        }
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if (r, g, b) in key_colors:
                    px[x, y] = (r, g, b, 0)
        return rgba

    def _type_icon_from_sheet(self, type_token: str | None) -> tuple[int, int, list[float]]:
        if not self.state.project_loaded or not type_token:
            return self._transparent_texture()
        token = str(type_token).strip()
        if not token:
            return self._transparent_texture()
        # Coordinates from expansion menu_info.png (cell size: 32x16)
        type_coord_map = {
            "TYPE_NORMAL": (0, 16),
            "TYPE_FIRE": (32, 16),
            "TYPE_WATER": (64, 16),
            "TYPE_GRASS": (96, 16),
            "TYPE_ELECTRIC": (0, 32),
            "TYPE_ROCK": (32, 32),
            "TYPE_GROUND": (64, 32),
            "TYPE_ICE": (96, 32),
            "TYPE_FLYING": (0, 48),
            "TYPE_FIGHTING": (32, 48),
            "TYPE_GHOST": (64, 48),
            "TYPE_BUG": (96, 48),
            "TYPE_POISON": (0, 64),
            "TYPE_PSYCHIC": (32, 64),
            "TYPE_STEEL": (64, 64),
            "TYPE_DARK": (96, 64),
            "TYPE_DRAGON": (0, 80),
            "TYPE_FAIRY": (32, 0),
            "TYPE_NONE": (64, 64),
            "TYPE_MYSTERY": (64, 64),
            "TYPE_STELLAR": (64, 64),
        }
        if token in {"TYPE_NONE", "TYPE_MYSTERY", "TYPE_STELLAR"}:
            return self._transparent_texture()
        coords = type_coord_map.get(token)
        if coords is None:
            return self._transparent_texture()
        root = Path(self.state.project_path)
        menu_info = root / "graphics/interface/menu_info.png"
        if not menu_info.exists():
            return self._transparent_texture()

        frame_w = 32
        frame_h = 16
        with Image.open(menu_info) as sheet:
            x, y = coords
            if x + frame_w > sheet.width or y + frame_h > sheet.height:
                return self._transparent_texture()
            icon = sheet.crop((x, y, x + frame_w, y + frame_h))
            icon = self._apply_transparent_bg_from_corners(icon)
            icon = icon.resize((64, 32), Image.NEAREST)
            return self._rgba_to_dpg_data(icon)

    def _refresh_type_icons(self) -> None:
        slots = [("type1", TAGS["type1_icon_btn"], "tex_type1"), ("type2", TAGS["type2_icon_btn"], "tex_type2")]
        for slot, img_tag, fallback_tag in slots:
            if not dpg.does_item_exist(img_tag):
                continue
            token = str(dpg.get_value(slot) or "").strip() if dpg.does_item_exist(slot) else ""
            dpg.configure_item(img_tag, show=True)
            if token in {"", "TYPE_NONE", "TYPE_MYSTERY", "TYPE_STELLAR"}:
                w, h, data = self._empty_type_slot_texture()
            else:
                w, h, data = self._type_icon_from_sheet(token)
            self._texture_seq += 1
            tex_tag = f"tex_{slot}_{self._texture_seq}"
            dpg.add_static_texture(w, h, data, tag=tex_tag, parent="tex_registry")
            dpg.configure_item(img_tag, texture_tag=tex_tag, width=w, height=h)
            self._bind_flat_icon_theme(img_tag)
            old = self._type_texture_tags.get(slot, fallback_tag)
            self._type_texture_tags[slot] = tex_tag
            if old not in {"tex_type1", "tex_type2"} and dpg.does_item_exist(old):
                dpg.delete_item(old)

    def _bind_flat_icon_theme(self, item_tag: str) -> None:
        if self._icon_button_theme is None:
            with dpg.theme() as self._icon_button_theme:
                with dpg.theme_component(dpg.mvImageButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 0, 0, 0))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 0))
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
                    dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
        if dpg.does_item_exist(item_tag):
            dpg.bind_item_theme(item_tag, self._icon_button_theme)

    def _rebuild_type_icon_pickers(self) -> None:
        for container_tag, slot, include_empty in [
            (TAGS["type1_list"], "type1", False),
            (TAGS["type2_list"], "type2", True),
        ]:
            if not dpg.does_item_exist(container_tag):
                continue
            dpg.delete_item(container_tag, children_only=True)
            tokens = [t for t in self.state.type_options if t.startswith("TYPE_")]
            if include_empty:
                tokens = [""] + tokens
            for token in tokens:
                with dpg.group(horizontal=True, parent=container_tag):
                    if token == "":
                        dpg.add_button(label="None", width=80, height=32, callback=self._on_type_icon_pick, user_data={"slot": slot, "type": ""})
                    else:
                        w, h, data = self._type_icon_from_sheet(token)
                        self._texture_seq += 1
                        tex_tag = f"tex_picker_{slot}_{self._texture_seq}"
                        dpg.add_static_texture(w, h, data, tag=tex_tag, parent="tex_registry")
                        self._type_picker_texture_tags[tex_tag] = token
                        btn_tag = dpg.add_image_button(texture_tag=tex_tag, width=64, height=32, callback=self._on_type_icon_pick, user_data={"slot": slot, "type": token})
                        self._bind_flat_icon_theme(btn_tag)
                    dpg.add_spacer(width=8)
                    dpg.add_text(token if token else "(no secondary type)")

    def _on_type_icon_pick(self, sender=None, app_data=None, user_data=None) -> None:
        if not isinstance(user_data, dict):
            return
        slot = str(user_data.get("slot") or "")
        token = str(user_data.get("type") or "")
        if slot not in {"type1", "type2"}:
            return
        if dpg.does_item_exist(slot):
            dpg.set_value(slot, token)
        self.close_type_modals()
        self.on_type_change()

    def open_type1_modal(self, sender=None, app_data=None, user_data=None) -> None:
        if dpg.does_item_exist(TAGS["type1_modal"]):
            dpg.configure_item(TAGS["type1_modal"], show=True)

    def open_type2_modal(self, sender=None, app_data=None, user_data=None) -> None:
        if dpg.does_item_exist(TAGS["type2_modal"]):
            dpg.configure_item(TAGS["type2_modal"], show=True)

    def close_type_modals(self, sender=None, app_data=None, user_data=None) -> None:
        if dpg.does_item_exist(TAGS["type1_modal"]):
            dpg.configure_item(TAGS["type1_modal"], show=False)
        if dpg.does_item_exist(TAGS["type2_modal"]):
            dpg.configure_item(TAGS["type2_modal"], show=False)

    def request_preview_refresh(self) -> None:
        self._preview_pending = True

    def pump(self) -> None:
        self._apply_responsive_layout()
        self._enforce_text_limits()
        if not self._radar_initialized and dpg.does_item_exist(TAGS["stats_radar_drawlist"]):
            self._radar_initialized = True
            self._refresh_stats_radar()
        self._update_evolution_hover_preview()
        now = time.monotonic()

        hover_idx = -1
        for idx, meta in list(self._evo_tooltip_rows.items()):
            row_tag = str(meta.get("row_tag") or "")
            if row_tag and dpg.does_item_exist(row_tag) and dpg.is_item_hovered(row_tag):
                hover_idx = idx
                break
        self._evo_tooltip_hover_idx = hover_idx

        if hover_idx >= 0 and now - self._evo_tooltip_last_tick >= self._evo_tooltip_anim_interval:
            self._evo_tooltip_last_tick = now
            self._evo_tooltip_frame = 1 - self._evo_tooltip_frame
            self._refresh_evo_tooltip_image(hover_idx)

        self._handle_keyboard_shortcuts(now)

        if self.state.project_loaded and now - self._stats_radar_last_tick >= self._stats_radar_refresh_interval:
            self._stats_radar_last_tick = now
            self._refresh_stats_radar()

        if self.state.project_loaded and now - self._icon_anim_last >= self._icon_anim_interval:
            self._icon_anim_last = now
            self._icon_anim_frame = 1 - self._icon_anim_frame
            self.request_preview_refresh()

        if self.state.build_in_progress:
            self.state.build_progress_value += 0.03
            if self.state.build_progress_value > 0.95:
                self.state.build_progress_value = 0.05
            dpg.configure_item(TAGS["build_progress"], default_value=self.state.build_progress_value, overlay="Building...")
            dpg.set_value(TAGS["build_output"], self.state.build_live_output)
            if self._build_thread and not self._build_thread.is_alive() and self._build_result is not None:
                self._finalize_build_result(self._build_result)

        if self._delete_in_progress and self._delete_thread and not self._delete_thread.is_alive():
            self._finalize_delete_result()

        if not self._preview_pending:
            return
        if now - self._last_preview_refresh < self._preview_throttle_seconds:
            return
        self._preview_pending = False
        self._last_preview_refresh = now
        self._refresh_preview()

    def _apply_responsive_layout(self) -> None:
        viewport_w = max(1200, dpg.get_viewport_client_width())
        viewport_h = max(760, dpg.get_viewport_client_height())
        size = (viewport_w, viewport_h)
        if size == self._last_layout_size:
            return
        self._last_layout_size = size

        if viewport_w < 1400:
            left_ratio = 0.26
            header_h = 120
        elif viewport_w < 1850:
            left_ratio = 0.24
            header_h = 116
        else:
            left_ratio = 0.22
            header_h = 112

        row_h = max(400, viewport_h - header_h - 50)

        left_w = max(300, int(viewport_w * left_ratio))
        workspace_w = max(720, viewport_w - left_w - 30)

        dpg.configure_item(TAGS["header_panel"], width=viewport_w - 20, height=header_h)
        dpg.configure_item(TAGS["species_panel"], width=left_w, height=row_h)
        dpg.configure_item(TAGS["workspace_panel"], width=workspace_w, height=row_h)

        fixed_controls_w = 118 + 92 + 44
        dpg.configure_item(TAGS["project_input"], width=max(320, viewport_w - fixed_controls_w - 70))
        dpg.configure_item(TAGS["species_list"], width=left_w - 22, num_items=max(12, min(22, int((row_h - 210) / 22))))
        dpg.configure_item(TAGS["search_input"], width=left_w - 22)
        dpg.configure_item(TAGS["btn_new"], width=left_w - 22)
        dpg.configure_item(TAGS["delete_btn"], width=left_w - 22)

        editor_field_w = min(520, max(300, workspace_w - 420))
        dpg.configure_item("constant_name", width=editor_field_w)
        dpg.configure_item("species_name", width=editor_field_w)
        dpg.configure_item("description", width=min(560, max(360, workspace_w - 320)))
        dpg.configure_item("folder_name", width=editor_field_w)
        if dpg.does_item_exist("cry_id"):
            dpg.configure_item("cry_id", width=min(380, max(220, workspace_w - 420)))
        if dpg.does_item_exist("assets_folder"):
            dpg.configure_item("assets_folder", width=max(360, workspace_w - 220))
        general_left_w = max(420, int(workspace_w * 0.65))
        general_right_w = max(280, workspace_w - general_left_w - 36)
        if dpg.does_item_exist(TAGS["general_left"]):
            dpg.configure_item(TAGS["general_left"], width=general_left_w)
        if dpg.does_item_exist(TAGS["general_right"]):
            dpg.configure_item(TAGS["general_right"], width=general_right_w)
        preview_size = max(72, min(112, int((general_right_w - 44) / 3)))
        if dpg.does_item_exist(TAGS["preview_front_img"]):
            dpg.configure_item(TAGS["preview_front_img"], width=preview_size, height=preview_size)
        if dpg.does_item_exist(TAGS["preview_back_img"]):
            dpg.configure_item(TAGS["preview_back_img"], width=preview_size, height=preview_size)
        if dpg.does_item_exist(TAGS["preview_icon_img"]):
            dpg.configure_item(TAGS["preview_icon_img"], width=preview_size, height=preview_size)
        if dpg.does_item_exist(TAGS["preview_footprint_img"]):
            footprint_size = max(64, min(96, int(preview_size * 0.86)))
            dpg.configure_item(TAGS["preview_footprint_img"], width=footprint_size, height=footprint_size)
        dpg.configure_item("evo_target", width=max(320, workspace_w - 190))
        dpg.configure_item("evo_friendship_param", width=120)
        dpg.configure_item("evo_item_param", width=max(220, workspace_w - 360))
        dpg.configure_item("evo_trade_item_param", width=max(220, workspace_w - 360))
        dpg.configure_item(TAGS["evo_rows"], width=workspace_w - 30)
        stats_left_w = min(560, max(420, int(workspace_w * 0.46)))
        stats_radar_w = max(280, workspace_w - stats_left_w - 30)
        if dpg.does_item_exist(TAGS["stats_fields_panel"]):
            dpg.configure_item(TAGS["stats_fields_panel"], width=stats_left_w, height=320)
        if dpg.does_item_exist(TAGS["stats_radar_panel"]):
            dpg.configure_item(TAGS["stats_radar_panel"], width=stats_radar_w, height=320)
        if dpg.does_item_exist(TAGS["stats_radar_drawlist"]):
            dpg.configure_item(TAGS["stats_radar_drawlist"], width=stats_radar_w - 8, height=312)
        half_learnset_w = max(260, int((workspace_w - 44) / 2))
        if dpg.does_item_exist(TAGS["learnset_level_panel"]):
            dpg.configure_item(TAGS["learnset_level_panel"], width=half_learnset_w)
        if dpg.does_item_exist(TAGS["learnset_tmhm_panel"]):
            dpg.configure_item(TAGS["learnset_tmhm_panel"], width=half_learnset_w)
        dpg.configure_item(TAGS["levelup_rows"], width=max(220, half_learnset_w - 12))
        dpg.configure_item(TAGS["teachable_rows"], width=max(220, half_learnset_w - 12))
        dpg.configure_item(TAGS["tutor_rows"], width=workspace_w - 30)
        dpg.configure_item(TAGS["lint_output"], width=workspace_w - 30)
        if dpg.does_item_exist(TAGS["type1_list"]):
            dpg.configure_item(TAGS["type1_list"], width=max(300, workspace_w - 180), height=max(260, int(row_h * 0.55)))
        if dpg.does_item_exist(TAGS["type2_list"]):
            dpg.configure_item(TAGS["type2_list"], width=max(300, workspace_w - 180), height=max(260, int(row_h * 0.55)))
        self._bind_flat_icon_theme(TAGS["type1_icon_btn"])
        self._bind_flat_icon_theme(TAGS["type2_icon_btn"])
        if dpg.does_item_exist(TAGS["settings_fab"]):
            fab_w = 210
            fab_h = 92
            fab_x = max(2, viewport_w - fab_w - 6)
            fab_y = max(2, viewport_h - fab_h - 6)
            if dpg.does_item_exist(TAGS.get("settings_fab_window", "")):
                dpg.configure_item(TAGS["settings_fab_window"], pos=(fab_x, fab_y), width=fab_w, height=fab_h)
            dpg.configure_item(TAGS["shortcuts_fab"], width=92, height=fab_h)
            dpg.configure_item(TAGS["settings_fab"], width=92, height=fab_h)
            self._bind_settings_button_theme(TAGS["shortcuts_fab"])
            self._bind_settings_button_theme(TAGS["settings_fab"])
        self._refresh_stats_radar()

    def open_settings_modal(self, sender=None, app_data=None, user_data=None) -> None:
        modal = TAGS.get("settings_modal")
        if modal and dpg.does_item_exist(modal):
            dpg.configure_item(modal, show=True)

    def close_settings_modal(self, sender=None, app_data=None, user_data=None) -> None:
        modal = TAGS.get("settings_modal")
        if modal and dpg.does_item_exist(modal):
            dpg.configure_item(modal, show=False)

    def on_settings_theme_change(self, sender=None, app_data=None, user_data=None) -> None:
        choice = str(app_data or dpg.get_value(TAGS.get("settings_theme", "")) or "Dark")
        custom_group = TAGS.get("settings_custom_colors_group")
        if custom_group and dpg.does_item_exist(custom_group):
            dpg.configure_item(custom_group, show=(choice == "Custom"))
        if callable(self._theme_switcher):
            self._theme_switcher(choice, self._custom_theme_palette_from_ui())
        self._persist_config({"settings_theme": choice})
        if choice == "Custom":
            self._persist_custom_theme()

    def on_custom_theme_color_change(self, sender=None, app_data=None, user_data=None) -> None:
        theme_choice = str(dpg.get_value(TAGS.get("settings_theme", "")) or "Dark")
        if theme_choice != "Custom":
            return
        if callable(self._theme_switcher):
            self._theme_switcher("Custom", self._custom_theme_palette_from_ui())
        self._persist_custom_theme()

    def open_axolote_ow_adder(self, sender=None, app_data=None, user_data=None) -> None:
        url = "https://github.com/Nexxo11/AxoloteOwAdder"
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", url])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", url])
            else:
                os.startfile(url)  # type: ignore[attr-defined]
            self._set_message("Opened AxoloteOwAdder repository")
        except Exception:
            self._set_message("Could not open AxoloteOwAdder URL")

    @staticmethod
    def _camel_to_upper_snake(name: str) -> str:
        s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", str(name or ""))
        return s.upper()

    def _load_cry_audio_map(self) -> None:
        self._cry_audio_map = {}
        if not self.state.project_path:
            return
        inc = Path(self.state.project_path) / "sound/direct_sound_data.inc"
        if not inc.exists():
            return
        try:
            text = inc.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return
        current_symbol = ""
        for raw in text.splitlines():
            line = raw.strip()
            m_sym = re.match(r"^(Cry_[A-Za-z0-9_]+)::", line)
            if m_sym:
                current_symbol = m_sym.group(1)
                continue
            if not current_symbol:
                continue
            m_inc = re.search(r"\.incbin\s+\"([^\"]+)\"", line)
            if not m_inc:
                continue
            rel = m_inc.group(1)
            cry_id = f"CRY_{self._camel_to_upper_snake(current_symbol.replace('Cry_', '', 1))}"
            self._cry_audio_map[cry_id] = Path(self.state.project_path) / rel
            current_symbol = ""

    def play_selected_cry(self, sender=None, app_data=None, user_data=None) -> None:
        if not self.state.project_loaded or not self.state.project_path:
            self._set_message("Load a project first")
            return
        selected = str(dpg.get_value("cry_id") or "").strip()
        if not selected or selected == "CRY_NONE":
            self._set_message("Select a valid cry")
            return
        if not self._cry_audio_map:
            self._load_cry_audio_map()
        audio_path = self._cry_audio_map.get(selected)
        if audio_path is None:
            self._set_message(f"Cry sample not found for {selected}")
            return
        wav_path = audio_path.with_suffix(".wav")
        play_path = wav_path if wav_path.exists() else audio_path
        if not play_path.exists():
            self._set_message(f"Audio file missing for {selected}")
            return

        try:
            if self._cry_player_proc and self._cry_player_proc.poll() is None:
                self._cry_player_proc.terminate()
                self._cry_player_proc = None
        except Exception:
            self._cry_player_proc = None

        cmd: list[str] | None = None
        if play_path.suffix.lower() == ".wav":
            if shutil.which("ffplay"):
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(play_path)]
            elif shutil.which("paplay"):
                cmd = ["paplay", str(play_path)]
            elif shutil.which("aplay"):
                cmd = ["aplay", str(play_path)]
            elif shutil.which("play"):
                cmd = ["play", "-q", str(play_path)]

        try:
            if cmd is not None:
                self._cry_player_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._set_message(f"Playing {selected}")
                return
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", str(play_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(play_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.startfile(str(play_path))  # type: ignore[attr-defined]
            self._set_message(f"Opened {selected} in external player")
        except Exception:
            self._set_message(f"Could not play {selected}")

    def _bind_settings_button_theme(self, tag: str) -> None:
        if self._settings_button_theme is None:
            with dpg.theme() as theme:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 0, 0, 0), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 0), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0, category=dpg.mvThemeCat_Core)
            self._settings_button_theme = theme
        if dpg.does_item_exist(tag):
            dpg.bind_item_theme(tag, self._settings_button_theme)

    def _hide_evolution_hover_preview(self) -> None:
        self._evo_hover_index = -1
        preview_tag = TAGS.get("evo_hover_preview")
        if preview_tag and dpg.does_item_exist(preview_tag):
            dpg.configure_item(preview_tag, show=False)

    def _update_evolution_hover_preview(self) -> None:
        return

    @staticmethod
    def _crop_front_frame_local(img: Image.Image, frame_index: int) -> Image.Image:
        w, h = img.size
        if w % 2 == 0 and w >= h * 2:
            half = w // 2
            return img.crop((0, 0, half, h)) if frame_index <= 0 else img.crop((half, 0, w, h))
        if h % 2 == 0 and h >= w * 2:
            half = h // 2
            return img.crop((0, 0, w, half)) if frame_index <= 0 else img.crop((0, half, w, h))
        return img

    def _evo_tooltip_texture(self, folder_name: str, frame_index: int) -> tuple[str, int, int]:
        key = (folder_name, frame_index)
        if key in self._evo_tooltip_tex_cache:
            return self._evo_tooltip_tex_cache[key]

        tex_tag, w, h = "tex_front", self._evo_tooltip_scale_px, self._evo_tooltip_scale_px
        try:
            preview = resolve_preview_paths(Path(self.state.project_path), folder_name, "", palette_mode="raw")
            with Image.open(preview.front_path) as src:
                frame = self._crop_front_frame_local(src.convert("RGBA"), frame_index)
                frame = frame.resize((self._evo_tooltip_scale_px, self._evo_tooltip_scale_px), Image.NEAREST)
                frame = self._apply_transparent_bg_from_corners(frame)
                w, h, data = self._rgba_to_dpg_data(frame)
                self._texture_seq += 1
                tex_tag = f"tex_evo_tip_{self._texture_seq}"
                dpg.add_static_texture(w, h, data, tag=tex_tag, parent="tex_registry")
        except Exception:
            tex_tag, w, h = "tex_front", self._evo_tooltip_scale_px, self._evo_tooltip_scale_px

        self._evo_tooltip_tex_cache[key] = (tex_tag, w, h)
        return self._evo_tooltip_tex_cache[key]

    def _refresh_evo_tooltip_image(self, idx: int) -> None:
        meta = self._evo_tooltip_rows.get(idx)
        if not meta:
            return
        img_tag = str(meta.get("img_tag") or "")
        folder_name = str(meta.get("folder_name") or "")
        has_second_frame = bool(meta.get("has_second_frame"))
        if not img_tag or not dpg.does_item_exist(img_tag):
            return
        frame_index = self._evo_tooltip_frame if has_second_frame else 0
        tex_tag, w, h = self._evo_tooltip_texture(folder_name, frame_index)
        dpg.configure_item(img_tag, texture_tag=tex_tag, width=w, height=h)

    def _next_draft_species_constant(self) -> str:
        existing = {str(item.get("constant_name", "")).upper() for item in self.state.species_list}
        idx = 1
        while True:
            candidate = f"SPECIES_NEW_{idx}"
            if candidate not in existing:
                return candidate
            idx += 1

    def _ensure_draft_species_in_list(self, constant_name: str, species_name: str, folder_name: str) -> None:
        draft = next((x for x in self.state.species_list if x.get("constant_name") == constant_name), None)
        if draft is None:
            self.state.species_list.insert(
                0,
                {
                    "constant_name": constant_name,
                    "species_name": species_name,
                    "folder_name": folder_name,
                    "species": None,
                },
            )
            self.state.last_species_count = len(self.state.species_list)
            dpg.set_value(TAGS["species_count"], f"Species: {self.state.last_species_count}")
        else:
            draft["species_name"] = species_name
            draft["folder_name"] = folder_name

    def _refresh_preview(self) -> None:
        try:
            if not self.state.project_loaded:
                return
            folder_name = str(dpg.get_value("folder_name") or "").strip() or "bulbasaur"
            assets_folder = str(dpg.get_value("assets_folder") or "").strip()
            frame_index = int(self.state.preview_frame_index or 0)
            icon_frame_index = self._icon_anim_frame
            palette_mode = "raw"

            preview = resolve_preview_paths(Path(self.state.project_path), folder_name, assets_folder, palette_mode=palette_mode)
            back_frame_index = frame_index if palette_mode == "normal" else frame_index
            new_front, fw, fh = self._update_texture("front", preview.front_path, frame_index, palette_mode, preview.palette_variant)
            new_back, bw, bh = self._update_texture("back", preview.back_path, back_frame_index, palette_mode, preview.palette_variant)
            icon_payload: tuple[str, int, int] | None = None
            if dpg.does_item_exist(TAGS["preview_icon_img"]):
                icon_payload = self._update_texture("icon", preview.icon_path, icon_frame_index, palette_mode, preview.palette_variant)
            footprint_payload: tuple[str, int, int] | None = None
            if dpg.does_item_exist(TAGS["preview_footprint_img"]):
                footprint_payload = self._load_footprint_texture(folder_name, assets_folder)

            dpg.configure_item(TAGS["preview_front_img"], texture_tag=new_front, width=fw, height=fh)
            dpg.configure_item(TAGS["preview_back_img"], texture_tag=new_back, width=bw, height=bh)
            if icon_payload is not None:
                new_icon, iw, ih = icon_payload
                dpg.configure_item(TAGS["preview_icon_img"], texture_tag=new_icon, width=iw, height=ih)
            if footprint_payload is not None:
                new_fp, fpw, fph = footprint_payload
                dpg.configure_item(TAGS["preview_footprint_img"], texture_tag=new_fp, width=fpw, height=fph)

            old_tags = self._preview_texture_tags.copy()
            self._preview_texture_tags = {
                "front": new_front,
                "back": new_back,
                "icon": icon_payload[0] if icon_payload is not None else self._preview_texture_tags.get("icon", "tex_icon"),
                "footprint": footprint_payload[0] if footprint_payload is not None else self._preview_texture_tags.get("footprint", "tex_footprint"),
            }
            for old_tag in old_tags.values():
                if old_tag in {"tex_front", "tex_back", "tex_icon", "tex_footprint"}:
                    continue
                try:
                    if dpg.does_item_exist(old_tag):
                        dpg.delete_item(old_tag)
                except Exception:
                    pass

            pal_msg = f"Modo preview: {palette_mode}" if palette_mode in {"normal", "shiny"} else ""
            warning = preview.warning or ""
            dpg.set_value(TAGS["preview_warning"], (warning + " | " + pal_msg).strip(" |"))
            if warning:
                dpg.configure_item(TAGS["preview_warning"], color=PALETTE["warning"])
            else:
                dpg.configure_item(TAGS["preview_warning"], color=PALETTE["muted_text"])
        except Exception as exc:
            dpg.set_value(TAGS["preview_warning"], f"Preview error: {exc}")
            dpg.configure_item(TAGS["preview_warning"], color=PALETTE["error"])

    def load_project(self, sender=None, app_data=None, user_data=None) -> None:
        try:
            t0 = time.perf_counter()
            path = Path(dpg.get_value(TAGS["project_input"]).strip()).resolve()
            self.editor = SpeciesEditor(path)
            self.state.project_path = str(path)
            self.state.project_loaded = True
            self.state.species_list = [
                {
                    "constant_name": s.constant_name,
                    "species_name": s.species_name or "",
                    "folder_name": s.folder_name or "",
                    "species": s,
                }
                for s in self.editor.read_result.species
                if s.constant_name
            ]
            self.state.last_species_count = len(self.state.species_list)
            dpg.set_value(TAGS["project_status"], f"Project loaded: {path}")
            dpg.set_value(TAGS["species_count"], f"Species: {self.state.last_species_count}")
            self._load_options_from_project()
            evo_targets = sorted(
                {
                    str(item.get("constant_name") or "").strip()
                    for item in self.state.species_list
                    if str(item.get("constant_name") or "").strip()
                }
            )
            if dpg.does_item_exist("evo_target"):
                dpg.configure_item("evo_target", items=evo_targets)
            self.filter_species()
            self.state.editor_dirty = False
            self.state.validation_ok = False
            self.state.dry_run_valid = False
            dpg.configure_item(TAGS["delete_btn"], show=False)
            if self.state.selected_species_constant:
                selected_item = next((x for x in self.state.species_list if x["constant_name"] == self.state.selected_species_constant), None)
                if selected_item is not None:
                    dpg.set_value(TAGS["species_list"], self._species_label(selected_item))
                    self.select_species()
            self._persist_config({
                "last_project_path": str(path),
                "last_species_constant": self.state.selected_species_constant or "",
            })
            dpg.configure_item(TAGS["compile_btn"], enabled=True)
            self._status_validation = "idle"
            self._status_dryrun = "idle"
            self._invalidate_payload_cache()
            self._refresh_apply_enabled()
            self._update_header_status()
            self._set_message("Project loaded successfully")
            self.request_preview_refresh()
            self._record_perf("load_project", (time.perf_counter() - t0) * 1000.0)
        except Exception:
            self.state.project_loaded = False
            self.state.editor_dirty = False
            self.state.validation_ok = False
            self.state.dry_run_valid = False
            self._set_message(traceback.format_exc())
            dpg.set_value(TAGS["project_status"], "Failed to load project")
            dpg.configure_item(TAGS["compile_btn"], enabled=False)
            self._refresh_apply_enabled()
            self._update_header_status()

    def analyze_project(self, sender=None, app_data=None, user_data=None) -> None:
        self.load_project()

    def filter_species(self, sender=None, app_data=None, user_data=None) -> None:
        query = dpg.get_value(TAGS["search_input"]).strip().lower()
        items: list[str] = []
        for item in self.state.species_list:
            key = f"{item['constant_name']} {item['species_name']}".lower()
            if query and query not in key:
                continue
            items.append(self._species_label(item))
        dpg.configure_item(TAGS["species_list"], items=items)

    def _parse_evo_rows(self, evolutions_raw: str | None) -> list[dict[str, str]]:
        if not evolutions_raw:
            return []
        text = str(evolutions_raw)
        rows: list[dict[str, str]] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] != "{":
                i += 1
                continue
            i += 1
            depth_paren = 0
            token = ""
            parts: list[str] = []
            while i < n:
                ch = text[i]
                if ch == "(":
                    depth_paren += 1
                    token += ch
                elif ch == ")":
                    depth_paren = max(0, depth_paren - 1)
                    token += ch
                elif ch == "," and depth_paren == 0 and len(parts) < 2:
                    parts.append(token.strip())
                    token = ""
                elif ch == "}" and depth_paren == 0:
                    parts.append(token.strip())
                    token = ""
                    i += 1
                    break
                else:
                    token += ch
                i += 1
            if len(parts) >= 3:
                rows.append({"method": parts[0], "param": parts[1], "target": parts[2]})
        return rows

    @staticmethod
    def _extract_species_constant(text: str) -> str:
        m = re.search(r"\bSPECIES_[A-Z0-9_]+\b", str(text or ""))
        return m.group(0) if m else ""

    def _render_evo_rows(self) -> None:
        if not dpg.does_item_exist(TAGS["evo_rows"]):
            return
        dpg.delete_item(TAGS["evo_rows"], children_only=True)
        self._evo_row_tags = []
        self._evo_tooltip_rows = {}
        for idx, row in enumerate(self.state.evolution_rows):
            label = f"{row['method']} | {row['param']} -> {row['target']}"
            row_tag = f"evo_row_{idx}"
            self._evo_row_tags.append(row_tag)
            dpg.add_selectable(
                label=label,
                tag=row_tag,
                parent=TAGS["evo_rows"],
                callback=self.select_evolution_row,
                user_data=idx,
                default_value=(idx == self.state.selected_evolution_index),
            )

            target = str(row.get("target") or "").strip()
            target_constant = self._extract_species_constant(target)
            tooltip_text = target or "Unknown target"
            img_tag = f"evo_tip_img_{idx}"
            tex_tag, w, h = "tex_front", self._evo_tooltip_scale_px, self._evo_tooltip_scale_px
            folder_name = ""
            has_second_frame = False
            if self.editor and self.state.project_loaded:
                species = self.editor.species_by_constant.get(target_constant)
                if species and species.folder_name:
                    folder_name = str(species.folder_name)
                    try:
                        preview = resolve_preview_paths(Path(self.state.project_path), folder_name, "", palette_mode="raw")
                        with Image.open(preview.front_path) as src:
                            sw, sh = src.size
                            has_second_frame = (sw % 2 == 0 and sw >= sh * 2) or (sh % 2 == 0 and sh >= sw * 2)
                        tex_tag, w, h = self._evo_tooltip_texture(folder_name, 0)
                    except Exception:
                        pass
            with dpg.tooltip(row_tag):
                dpg.add_text(tooltip_text)
                dpg.add_image(tex_tag, width=w, height=h, tag=img_tag)

            self._evo_tooltip_rows[idx] = {
                "row_tag": row_tag,
                "img_tag": img_tag,
                "folder_name": folder_name,
                "has_second_frame": has_second_frame,
            }

        if self.state.selected_evolution_index >= len(self.state.evolution_rows):
            self.state.selected_evolution_index = -1

    def _render_levelup_rows(self) -> None:
        items = [f"Lv {int(r['level']):>3} -> {r['move']}" for r in self.state.level_up_rows]
        dpg.configure_item(TAGS["levelup_rows"], items=items)
        if self.state.selected_level_up_index >= len(self.state.level_up_rows):
            self.state.selected_level_up_index = -1

    def _render_teachable_rows(self) -> None:
        dpg.configure_item(TAGS["teachable_rows"], items=list(self.state.teachable_rows))
        if self.state.selected_teachable_index >= len(self.state.teachable_rows):
            self.state.selected_teachable_index = -1

    def _render_tutor_rows(self) -> None:
        dpg.configure_item(TAGS["tutor_rows"], items=list(self.state.tutor_rows))
        if self.state.selected_tutor_index >= len(self.state.tutor_rows):
            self.state.selected_tutor_index = -1

    def _sync_evolution_param_widget(self) -> None:
        method = str(dpg.get_value("evo_method") or "EVO_LEVEL")
        kind = self._evolution_param_kind(method)
        is_level = kind == "level"
        is_item = kind == "item"
        is_trade = kind == "trade"
        is_trade_item = kind == "trade_item"
        is_friendship = kind == "friendship"
        is_text = kind == "text"

        dpg.configure_item("evo_level_param", show=is_level)
        if dpg.does_item_exist("evo_level_label"):
            dpg.configure_item("evo_level_label", show=is_level)
        dpg.configure_item("evo_friendship_param", show=is_friendship)
        if dpg.does_item_exist("evo_friendship_label"):
            dpg.configure_item("evo_friendship_label", show=is_friendship)
        dpg.configure_item("evo_item_param", show=is_item)
        if dpg.does_item_exist("evo_item_label"):
            dpg.configure_item("evo_item_label", show=is_item)
        dpg.configure_item("evo_trade_item_param", show=is_trade_item)
        if dpg.does_item_exist("evo_trade_item_label"):
            dpg.configure_item("evo_trade_item_label", show=is_trade_item)
        dpg.configure_item("evo_param", show=is_text)
        if dpg.does_item_exist("evo_param_label"):
            dpg.configure_item("evo_param_label", show=is_text)

        options = self.state.item_options or ["ITEM_NONE"]
        current = str(dpg.get_value("evo_param") or "").strip()
        if is_item:
            dpg.set_value("evo_item_param", current if current in options else options[0])
        elif is_trade_item:
            dpg.set_value("evo_trade_item_param", current if current in options else "ITEM_NONE")
        elif is_level:
            try:
                dpg.set_value("evo_level_param", max(0, min(100, int(current or "16"))))
            except ValueError:
                dpg.set_value("evo_level_param", 16)
        elif is_friendship:
            try:
                dpg.set_value("evo_friendship_param", max(1, min(255, int(current or "220"))))
            except ValueError:
                dpg.set_value("evo_friendship_param", 220)
        elif not is_text and dpg.does_item_exist("evo_param"):
            dpg.set_value("evo_param", "0")

        self._sync_evolution_condition_widgets()

    @staticmethod
    def _parse_target_condition(raw_target: str) -> tuple[str, list[tuple[str, list[str]]]]:
        text = str(raw_target or "").strip()
        m_species = re.search(r"\bSPECIES_[A-Z0-9_]+\b", text)
        species = m_species.group(0) if m_species else text
        m_block = re.search(r"CONDITIONS\((.*)\)", text)
        if not m_block:
            return species, []
        body = m_block.group(1)
        clauses: list[tuple[str, list[str]]] = []
        for m in re.finditer(r"\{\s*(IF_[A-Z0-9_]+)\s*,\s*([^}]*)\}", body):
            cond = m.group(1).strip()
            args = [p.strip() for p in m.group(2).split(",") if p.strip()]
            clauses.append((cond, args))
        return species, clauses

    def _compose_target_with_condition(self, species_target: str, extra_clauses: list[tuple[str, list[str]]] | None = None) -> str:
        species = self._extract_species_constant(species_target)
        if not species:
            return str(species_target or "").strip()
        enabled = bool(dpg.get_value("evo_condition_enabled")) if dpg.does_item_exist("evo_condition_enabled") else False
        if not enabled:
            return species
        cond = str(dpg.get_value("evo_condition_type") or "").strip()
        if not cond:
            return species
        clauses: list[tuple[str, list[str]]] = []
        for row in self.state.evolution_condition_rows:
            c = str(row.get("condition") or "").strip()
            args = [a.strip() for a in str(row.get("args") or "").split(",") if a.strip()]
            if c and args:
                clauses.append((c, args))
        for c, args in (extra_clauses or []):
            if c:
                cleaned = [a for a in args if str(a or "").strip()]
                if cleaned:
                    clauses.append((c, cleaned))
        if not clauses:
            return species
        parts = ["{" + c + ", " + ", ".join(args) + "}" for c, args in clauses]
        return f"{species}, CONDITIONS({', '.join(parts)})"

    def _sync_evolution_condition_widgets(self) -> None:
        enabled = bool(dpg.get_value("evo_condition_enabled")) if dpg.does_item_exist("evo_condition_enabled") else False
        cond = str(dpg.get_value("evo_condition_type") or "").strip() if dpg.does_item_exist("evo_condition_type") else ""
        options = self._condition_value_options(cond) if enabled else []
        if dpg.does_item_exist("evo_condition_type"):
            dpg.configure_item("evo_condition_type", show=enabled)
        if dpg.does_item_exist("evo_condition_value"):
            dpg.configure_item("evo_condition_value", show=bool(options))
            if options:
                dpg.configure_item("evo_condition_value", items=options)
                current = str(dpg.get_value("evo_condition_value") or "")
                if current not in options:
                    dpg.set_value("evo_condition_value", options[0])
        if dpg.does_item_exist("evo_condition_param"):
            dpg.configure_item("evo_condition_param", show=(enabled and not options))
        if dpg.does_item_exist("evo_condition_value_int"):
            dpg.configure_item("evo_condition_value_int", show=(enabled and cond == "IF_BAG_ITEM_COUNT"))

    def _condition_value_options(self, cond: str) -> list[str]:
        token = str(cond or "").strip()
        if not token:
            return []
        if token in {"IF_KNOW_MOVE_TYPE", "IF_KNOWS_MOVE_TYPE"}:
            return list(self.state.type_options or ["TYPE_NORMAL"])
        if "MOVE" in token:
            return list(self.state.move_options or ["MOVE_TACKLE"])
        if "ITEM" in token:
            return list(self.state.item_options or ["ITEM_NONE"])
        if "TYPE" in token:
            return list(self.state.type_options or ["TYPE_NORMAL"])
        if "SPECIES" in token:
            values = [str(x.get("constant_name") or "").strip() for x in self.state.species_list]
            return [x for x in values if x]
        if "MAP" in token:
            return list(self.state.map_options or ["MAP_NONE"])
        if "NATURE" in token:
            return list(self.state.nature_options or ["NATURE_HARDY"])
        if "TIME" in token:
            return ["TIME_MORNING", "TIME_DAY", "TIME_EVENING", "TIME_NIGHT"]
        if "WEATHER" in token:
            return ["WEATHER_SUNNY", "WEATHER_RAIN", "WEATHER_SNOW", "WEATHER_SANDSTORM", "WEATHER_FOG"]
        if "GENDER" in token:
            return ["MON_MALE", "MON_FEMALE"]
        return []

    def on_evolution_condition_toggle(self, sender=None, app_data=None, user_data=None) -> None:
        if dpg.does_item_exist("evo_condition_enabled") and not bool(dpg.get_value("evo_condition_enabled")):
            self.state.evolution_condition_rows = []
            self.state.selected_evolution_condition_index = -1
            self._render_evolution_condition_rows()
        self._sync_evolution_condition_widgets()
        self.mark_dirty()

    def on_evolution_condition_type_change(self, sender=None, app_data=None, user_data=None) -> None:
        cond = str(dpg.get_value("evo_condition_type") or "").strip()
        options = self._condition_value_options(cond)
        if not options and dpg.does_item_exist("evo_condition_param"):
            dpg.set_value("evo_condition_param", "")
        if cond == "IF_BAG_ITEM_COUNT" and dpg.does_item_exist("evo_condition_value_int"):
            dpg.set_value("evo_condition_value_int", 0)
        self._sync_evolution_condition_widgets()
        self.mark_dirty()

    def _condition_row_from_ui(self) -> dict[str, str] | None:
        cond = str(dpg.get_value("evo_condition_type") or "").strip() if dpg.does_item_exist("evo_condition_type") else ""
        if not cond:
            return None
        if cond == "IF_BAG_ITEM_COUNT":
            item = str(dpg.get_value("evo_condition_value") or "ITEM_NONE").strip() or "ITEM_NONE"
            count = str(max(0, int(dpg.get_value("evo_condition_value_int") or 0)))
            return {"condition": cond, "args": f"{item}, {count}"}
        options = self._condition_value_options(cond)
        if options and dpg.does_item_exist("evo_condition_value"):
            arg = str(dpg.get_value("evo_condition_value") or options[0]).strip()
        else:
            arg = str(dpg.get_value("evo_condition_param") or "").strip()
        if not arg:
            return None
        return {"condition": cond, "args": arg}

    def _render_evolution_condition_rows(self) -> None:
        if not dpg.does_item_exist("evo_condition_rows"):
            return
        labels = [f"{row['condition']} | {row['args']}" for row in self.state.evolution_condition_rows]
        dpg.configure_item("evo_condition_rows", items=labels)
        dpg.configure_item("evo_condition_rows", show=bool(labels))
        if 0 <= self.state.selected_evolution_condition_index < len(labels):
            dpg.set_value("evo_condition_rows", labels[self.state.selected_evolution_condition_index])
        elif labels:
            self.state.selected_evolution_condition_index = 0
            dpg.set_value("evo_condition_rows", labels[0])
        else:
            self.state.selected_evolution_condition_index = -1

    def add_evolution_condition_row(self, sender=None, app_data=None, user_data=None) -> None:
        row = self._condition_row_from_ui()
        if row is None:
            self._set_message("Set a valid condition first")
            return
        self.state.evolution_condition_rows.append(row)
        self.state.selected_evolution_condition_index = len(self.state.evolution_condition_rows) - 1
        if dpg.does_item_exist("evo_condition_enabled"):
            dpg.set_value("evo_condition_enabled", True)
        self._render_evolution_condition_rows()
        self.mark_dirty()

    def update_evolution_condition_row(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_evolution_condition_index
        if idx < 0 or idx >= len(self.state.evolution_condition_rows):
            self._set_message("Select a condition row to update")
            return
        row = self._condition_row_from_ui()
        if row is None:
            self._set_message("Set a valid condition first")
            return
        self.state.evolution_condition_rows[idx] = row
        self._render_evolution_condition_rows()
        self.mark_dirty()

    def remove_evolution_condition_row(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_evolution_condition_index
        if idx < 0 or idx >= len(self.state.evolution_condition_rows):
            self._set_message("Select a condition row to remove")
            return
        del self.state.evolution_condition_rows[idx]
        self.state.selected_evolution_condition_index = min(idx, len(self.state.evolution_condition_rows) - 1)
        if not self.state.evolution_condition_rows and dpg.does_item_exist("evo_condition_enabled"):
            dpg.set_value("evo_condition_enabled", False)
        self._render_evolution_condition_rows()
        self.mark_dirty()

    def select_evolution_condition_row(self, sender=None, app_data=None, user_data=None) -> None:
        selected = str(dpg.get_value("evo_condition_rows") or "") if dpg.does_item_exist("evo_condition_rows") else ""
        if not selected:
            self.state.selected_evolution_condition_index = -1
            return
        for idx, row in enumerate(self.state.evolution_condition_rows):
            label = f"{row['condition']} | {row['args']}"
            if label != selected:
                continue
            self.state.selected_evolution_condition_index = idx
            cond = str(row.get("condition") or "")
            args = [a.strip() for a in str(row.get("args") or "").split(",") if a.strip()]
            if dpg.does_item_exist("evo_condition_type"):
                dpg.set_value("evo_condition_type", cond)
            if cond == "IF_BAG_ITEM_COUNT":
                if dpg.does_item_exist("evo_condition_value") and args:
                    dpg.set_value("evo_condition_value", args[0])
                if dpg.does_item_exist("evo_condition_value_int") and len(args) > 1:
                    try:
                        dpg.set_value("evo_condition_value_int", int(args[1]))
                    except Exception:
                        dpg.set_value("evo_condition_value_int", 0)
            else:
                options = self._condition_value_options(cond)
                if options and dpg.does_item_exist("evo_condition_value") and args:
                    dpg.configure_item("evo_condition_value", items=options)
                    dpg.set_value("evo_condition_value", args[0] if args[0] in options else options[0])
                elif dpg.does_item_exist("evo_condition_param"):
                    dpg.set_value("evo_condition_param", ", ".join(args))
            self._sync_evolution_condition_widgets()
            return

    def on_evolution_method_change(self, sender=None, app_data=None, user_data=None) -> None:
        self._sync_evolution_param_widget()
        self.mark_dirty()

    def on_type_change(self, sender=None, app_data=None, user_data=None) -> None:
        self._refresh_type_icons()
        self.mark_dirty()

    def on_evolution_item_change(self, sender=None, app_data=None, user_data=None) -> None:
        dpg.set_value("evo_param", str(dpg.get_value("evo_item_param") or "ITEM_NONE"))
        self.mark_dirty()

    def on_evolution_trade_item_change(self, sender=None, app_data=None, user_data=None) -> None:
        dpg.set_value("evo_param", str(dpg.get_value("evo_trade_item_param") or "ITEM_NONE"))
        self.mark_dirty()

    def _evolution_param_from_ui(self) -> str:
        method = str(dpg.get_value("evo_method") or "EVO_LEVEL").strip()
        kind = self._evolution_param_kind(method)
        if kind == "none":
            return "0"
        if kind == "level":
            return str(max(0, min(100, int(dpg.get_value("evo_level_param") or 16))))
        if kind == "item":
            return str(dpg.get_value("evo_item_param") or "ITEM_NONE").strip() or "ITEM_NONE"
        if kind == "trade":
            return "0"
        if kind == "trade_item":
            return str(dpg.get_value("evo_trade_item_param") or "ITEM_NONE").strip() or "ITEM_NONE"
        if kind == "friendship":
            return str(max(1, min(255, int(dpg.get_value("evo_friendship_param") or 220))))
        return str(dpg.get_value("evo_param") or "1").strip() or "1"

    def _set_evolution_param_ui(self, method: str, param: str) -> None:
        dpg.set_value("evo_param", param)
        kind = self._evolution_param_kind(method)
        if kind == "level":
            try:
                dpg.set_value("evo_level_param", max(0, min(100, int(param or "16"))))
            except ValueError:
                dpg.set_value("evo_level_param", 16)
        elif kind == "item":
            dpg.set_value("evo_item_param", param or "ITEM_NONE")
        elif kind == "trade":
            dpg.set_value("evo_trade_item_param", "ITEM_NONE")
            dpg.set_value("evo_param", "0")
        elif kind == "trade_item":
            dpg.set_value("evo_trade_item_param", param or "ITEM_NONE")
        elif kind == "friendship":
            try:
                dpg.set_value("evo_friendship_param", max(1, min(255, int(param or "220"))))
            except ValueError:
                dpg.set_value("evo_friendship_param", 220)
        elif kind == "none":
            dpg.set_value("evo_param", "0")

    @staticmethod
    def _evolution_param_kind(method: str) -> str:
        token = str(method or "").strip()
        if token in {
            "EVO_NONE",
            "EVO_SPLIT_FROM_EVO",
            "EVO_SCRIPT_TRIGGER",
            "EVO_BATTLE_END",
            "EVO_MODE_NORMAL",
            "EVO_MODE_TRADE",
            "EVO_MODE_ITEM_USE",
            "EVO_MODE_ITEM_CHECK",
            "EVO_MODE_BATTLE_SPECIAL",
        }:
            return "none"
        if token == "EVO_LEVEL" or "LEVEL" in token:
            return "level"
        if token == "EVO_FRIENDSHIP" or "FRIENDSHIP" in token:
            return "none"
        if token == "EVO_TRADE":
            return "trade"
        if "TRADE" in token and "ITEM" in token:
            return "trade_item"
        if token == "EVO_ITEM" or ("ITEM" in token and "TRADE" not in token):
            return "item"
        return "text"

    def select_evolution_row(self, sender=None, app_data=None, user_data=None) -> None:
        if user_data is None:
            self.state.selected_evolution_index = -1
            return
        try:
            idx = int(user_data)
        except Exception:
            idx = -1
        if idx < 0 or idx >= len(self.state.evolution_rows):
            self.state.selected_evolution_index = -1
            return

        self.state.selected_evolution_index = idx
        for row_idx, row_tag in enumerate(self._evo_row_tags):
            if dpg.does_item_exist(row_tag):
                dpg.set_value(row_tag, row_idx == idx)

        row = self.state.evolution_rows[idx]
        dpg.set_value("evo_method", row["method"])
        self._set_evolution_param_ui(row["method"], row["param"])
        species_target, clauses = self._parse_target_condition(str(row["target"] or ""))
        cond_type = clauses[0][0] if clauses else ""
        cond_args = clauses[0][1] if clauses else []
        self.state.evolution_condition_rows = [{"condition": c, "args": ", ".join(args)} for c, args in clauses]
        self.state.selected_evolution_condition_index = 0 if self.state.evolution_condition_rows else -1
        self._render_evolution_condition_rows()
        dpg.set_value("evo_target", species_target)
        if dpg.does_item_exist("evo_condition_enabled"):
            dpg.set_value("evo_condition_enabled", bool(cond_type))
        if dpg.does_item_exist("evo_condition_type") and cond_type:
            dpg.set_value("evo_condition_type", cond_type)
        if cond_type == "IF_BAG_ITEM_COUNT":
            if dpg.does_item_exist("evo_condition_value") and cond_args:
                item_options = self._condition_value_options(cond_type)
                if item_options:
                    dpg.configure_item("evo_condition_value", items=item_options)
                    dpg.set_value("evo_condition_value", cond_args[0] if cond_args[0] in item_options else item_options[0])
            if dpg.does_item_exist("evo_condition_value_int") and len(cond_args) > 1:
                try:
                    dpg.set_value("evo_condition_value_int", max(0, int(cond_args[1])))
                except Exception:
                    dpg.set_value("evo_condition_value_int", 0)
        elif dpg.does_item_exist("evo_condition_value") and cond_args:
            options = self._condition_value_options(cond_type)
            if options:
                dpg.configure_item("evo_condition_value", items=options)
                dpg.set_value("evo_condition_value", cond_args[0] if cond_args[0] in options else options[0])
        if dpg.does_item_exist("evo_condition_param"):
            dpg.set_value("evo_condition_param", ", ".join(cond_args) if cond_args else "")
        self._sync_evolution_param_widget()

        selected = f"{row['method']} | {row['param']} -> {row['target']}"
        now = time.monotonic()
        if self._evo_last_click_label == selected and (now - self._evo_last_click_time) <= 0.35:
            self._jump_to_species_from_evolution_target(row["target"])
        self._evo_last_click_label = selected
        self._evo_last_click_time = now

    def _jump_to_species_from_evolution_target(self, target_constant: str) -> None:
        target_constant = self._extract_species_constant(str(target_constant or "").strip())
        if not target_constant:
            return
        target_item = next((x for x in self.state.species_list if x.get("constant_name") == target_constant), None)
        if target_item is None:
            self._set_message(f"Target species not found: {target_constant}")
            return
        label = self._species_label(target_item)
        if dpg.does_item_exist(TAGS["species_list"]):
            dpg.set_value(TAGS["species_list"], label)
            self.select_species()
        if dpg.does_item_exist(TAGS.get("editor_tabs", "")) and dpg.does_item_exist(TAGS.get("tab_general", "")):
            dpg.set_value(TAGS["editor_tabs"], TAGS["tab_general"])

    def select_levelup_row(self, sender=None, app_data=None, user_data=None) -> None:
        selected = dpg.get_value(TAGS["levelup_rows"])
        if not selected:
            self.state.selected_level_up_index = -1
            return
        for idx, row in enumerate(self.state.level_up_rows):
            label = f"Lv {int(row['level']):>3} -> {row['move']}"
            if label == selected:
                self.state.selected_level_up_index = idx
                dpg.set_value("move_level", int(row["level"]))
                dpg.set_value("move_name", str(row["move"]))
                return
        self.state.selected_level_up_index = -1

    def select_teachable_row(self, sender=None, app_data=None, user_data=None) -> None:
        selected = dpg.get_value(TAGS["teachable_rows"])
        if not selected:
            self.state.selected_teachable_index = -1
            return
        try:
            self.state.selected_teachable_index = self.state.teachable_rows.index(selected)
            dpg.set_value("tmhm_move", selected)
        except ValueError:
            self.state.selected_teachable_index = -1

    def select_species(self, sender=None, app_data=None, user_data=None) -> None:
        value = dpg.get_value(TAGS["species_list"])
        if not value:
            return
        m = re.search(r"\((SPECIES_[A-Z0-9_]+)\)\s*$", value)
        if not m:
            return
        constant = m.group(1)
        selected = next((x for x in self.state.species_list if x["constant_name"] == constant), None)
        if selected is None:
            return

        species = selected.get("species")
        if species is None:
            self.state.selected_species_constant = constant
            self._persist_config({"last_project_path": self.state.project_path, "last_species_constant": constant})
            dpg.configure_item(TAGS["delete_btn"], show=False)
            data = default_editor_data()
            data["mode"] = "add"
            data["constant_name"] = constant
            data["species_name"] = str(selected.get("species_name") or "New species")
            data["folder_name"] = str(selected.get("folder_name") or "new_species")
            self._suspend_dirty_events = True
            try:
                for key, value in data.items():
                    tag = "edit_mode" if key == "mode" else key
                    if dpg.does_item_exist(tag):
                        dpg.set_value(tag, value)
            finally:
                self._suspend_dirty_events = False
            self.state.evolution_rows = []
            self.state.evolution_condition_rows = []
            self.state.selected_evolution_condition_index = -1
            self.state.level_up_rows = []
            self.state.teachable_rows = []
            self.state.tutor_rows = []
            self._render_evo_rows()
            self._render_levelup_rows()
            self._render_teachable_rows()
            self._render_tutor_rows()
            self._render_evolution_condition_rows()
            self._sync_evolution_param_widget()
            self._last_valid_description = self._normalize_description_text(str(dpg.get_value("description") or ""))
            self.state.editor_data = self._read_editor_from_ui()
            self.state.editor_dirty = False
            self.state.validation_ok = False
            self.state.dry_run_valid = False
            self._status_validation = "idle"
            self._status_dryrun = "idle"
            self._refresh_apply_enabled()
            self._refresh_type_icons()
            self._refresh_stats_radar()
            self.request_preview_refresh()
            return

        self.state.selected_species_constant = constant
        self._persist_config({"last_project_path": self.state.project_path, "last_species_constant": constant})
        dpg.configure_item(TAGS["delete_btn"], show=True)
        data = default_editor_data()
        data["mode"] = "edit"
        data["constant_name"] = species.constant_name or ""
        data["species_name"] = species.species_name or ""
        data["description"] = species.description or ""
        data["folder_name"] = species.folder_name or ""
        data["height"] = self._int_from_raw(species.height, data["height"])
        data["weight"] = self._int_from_raw(species.weight, data["weight"])
        data["catch_rate"] = self._int_from_raw(species.catch_rate, data["catch_rate"])
        data["exp_yield"] = self._int_from_raw(species.exp_yield, data["exp_yield"])
        data["gender_ratio"] = self._gender_ratio_to_percent(species.gender_ratio)
        data["cry_id"] = species.cry_id or "CRY_NONE"
        stats = species.base_stats
        data["hp"] = stats.hp or data["hp"]
        data["attack"] = stats.attack or data["attack"]
        data["defense"] = stats.defense or data["defense"]
        data["speed"] = stats.speed or data["speed"]
        data["sp_attack"] = stats.sp_attack or data["sp_attack"]
        data["sp_defense"] = stats.sp_defense or data["sp_defense"]
        if species.types:
            data["type1"] = species.types[0]
            data["type2"] = species.types[1] if len(species.types) > 1 else ""
        if species.abilities:
            data["ability1"] = species.abilities[0]
            data["ability2"] = species.abilities[1] if len(species.abilities) > 1 else "ABILITY_NONE"
            data["ability_hidden"] = species.abilities[2] if len(species.abilities) > 2 else "ABILITY_NONE"
        data["ev_hp"] = int(species.ev_yields.get("hp", 0))
        data["ev_attack"] = int(species.ev_yields.get("attack", 0))
        data["ev_defense"] = int(species.ev_yields.get("defense", 0))
        data["ev_speed"] = int(species.ev_yields.get("speed", 0))
        data["ev_sp_attack"] = int(species.ev_yields.get("sp_attack", 0))
        data["ev_sp_defense"] = int(species.ev_yields.get("sp_defense", 0))
        self._suspend_dirty_events = True
        try:
            for key, value in data.items():
                tag = "edit_mode" if key == "mode" else key
                if dpg.does_item_exist(tag):
                    dpg.set_value(tag, value)
        finally:
            self._suspend_dirty_events = False
        self.state.evolution_rows = self._parse_evo_rows(species.evolutions_raw)
        self.state.selected_evolution_index = -1
        self.state.evolution_condition_rows = []
        self.state.selected_evolution_condition_index = -1
        if dpg.does_item_exist("evo_condition_enabled"):
            dpg.set_value("evo_condition_enabled", False)
        if dpg.does_item_exist("evo_condition_param"):
            dpg.set_value("evo_condition_param", "")
        if dpg.does_item_exist("evo_condition_value_int"):
            dpg.set_value("evo_condition_value_int", 0)
        self._render_evo_rows()
        self._render_evolution_condition_rows()
        self.state.level_up_rows = list(species.level_up_moves or [])
        tmhm_set = set(self.state.tmhm_options)
        tutor_set = set(self.state.tutor_options)
        self.state.teachable_rows = [m for m in (species.teachable_moves_raw or []) if m in tmhm_set]
        self.state.tutor_rows = [m for m in (species.teachable_moves_raw or []) if m in tutor_set and m not in tmhm_set]
        self._render_levelup_rows()
        self._render_teachable_rows()
        self._render_tutor_rows()
        if dpg.does_item_exist("description"):
            dpg.set_value("description", str(species.description or ""))
            self._last_valid_description = self._normalize_description_text(str(species.description or ""))
        self._sync_evolution_param_widget()
        self.state.editor_data = self._read_editor_from_ui()
        self.state.editor_dirty = False
        self.state.validation_ok = False
        self.state.dry_run_valid = False
        self._status_validation = "idle"
        self._status_dryrun = "idle"
        self._refresh_apply_enabled()
        self._refresh_type_icons()
        self._refresh_stats_radar()
        self.request_preview_refresh()

    def _read_editor_from_ui(self) -> dict:
        data = default_editor_data()
        for key in list(data.keys()):
            tag = "edit_mode" if key == "mode" else key
            if dpg.does_item_exist(tag):
                data[key] = dpg.get_value(tag)
        return data

    def _enforce_text_limits(self) -> None:
        if dpg.does_item_exist("species_name"):
            val = str(dpg.get_value("species_name") or "")
            if len(val) > self.MAX_SPECIES_NAME_LEN:
                self._suspend_dirty_events = True
                try:
                    dpg.set_value("species_name", val[: self.MAX_SPECIES_NAME_LEN])
                finally:
                    self._suspend_dirty_events = False
        if dpg.does_item_exist("description"):
            val = self._normalize_description_text(str(dpg.get_value("description") or ""))
            if str(dpg.get_value("description") or "") != val:
                self._suspend_dirty_events = True
                try:
                    dpg.set_value("description", val)
                finally:
                    self._suspend_dirty_events = False
            self._last_valid_description = val
            self._update_description_counter()

    def _update_description_counter(self) -> None:
        counter_tag = TAGS.get("description_counter")
        if not counter_tag or not dpg.does_item_exist(counter_tag):
            return
        desc = str(dpg.get_value("description") or "") if dpg.does_item_exist("description") else ""
        used = min(len(desc), self.MAX_DESCRIPTION_LEN)
        dpg.set_value(counter_tag, f"{used}/{self.MAX_DESCRIPTION_LEN}")
        ratio = used / float(self.MAX_DESCRIPTION_LEN)
        if ratio < 0.65:
            color = PALETTE["muted_text"]
        elif ratio < 0.85:
            color = PALETTE["warning"]
        else:
            t = min(1.0, max(0.0, (ratio - 0.85) / 0.15))
            wr, wg, wb, _ = PALETTE["warning"]
            rr, rg, rb, _ = PALETTE["error"]
            color = (int(wr + (rr - wr) * t), int(wg + (rg - wg) * t), int(wb + (rb - wb) * t), 255)
        dpg.configure_item(counter_tag, color=color)

    def _load_footprint_texture(self, folder_name: str, assets_folder: str) -> tuple[str, int, int]:
        base = Path(self.state.project_path) / "graphics" / "pokemon"
        folders: list[str] = []
        for value in (folder_name, assets_folder):
            key = str(value or "").strip()
            if key and key not in folders:
                folders.append(key)
        if not folders:
            folders = ["bulbasaur"]
        for folder in folders:
            for filename in ("footprint.png", "footprint_gba.png"):
                candidate = base / folder / filename
                if not candidate.exists():
                    continue
                with Image.open(candidate) as src:
                    fp = self._apply_transparent_bg_from_corners(src.convert("RGBA"))
                    fp = fp.resize((96, 96), Image.NEAREST)
                    w, h, data = self._rgba_to_dpg_data(fp)
                    self._texture_seq += 1
                    tex_tag = f"tex_footprint_{self._texture_seq}"
                    dpg.add_static_texture(w, h, data, tag=tex_tag, parent="tex_registry")
                    return tex_tag, w, h
        return "tex_footprint", 96, 96

    @classmethod
    def _normalize_description_text(cls, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if len(text) > cls.MAX_DESCRIPTION_LEN:
            return text[: cls.MAX_DESCRIPTION_LEN]
        return text

    def on_description_change(self, sender=None, app_data=None, user_data=None) -> None:
        if self._suspend_dirty_events:
            return
        current = str(app_data if app_data is not None else dpg.get_value("description") or "")
        normalized = current.replace("\r\n", "\n").replace("\r", "\n")
        if len(normalized) > self.MAX_DESCRIPTION_LEN:
            normalized = self._last_valid_description
        else:
            self._last_valid_description = normalized
        if normalized != current:
            self._suspend_dirty_events = True
            try:
                dpg.set_value("description", normalized)
            finally:
                self._suspend_dirty_events = False
        self._update_description_counter()
        self.mark_dirty()

    def mark_dirty(self, sender=None, app_data=None, user_data=None) -> None:
        if self._suspend_dirty_events:
            return
        self._enforce_text_limits()
        self.state.editor_data = self._read_editor_from_ui()
        self._invalidate_payload_cache()
        self.state.editor_dirty = True
        self.state.validation_ok = False
        self.state.dry_run_valid = False
        self._status_validation = "idle"
        self._status_dryrun = "dirty"
        if dpg.does_item_exist(TAGS["plan_empty"]):
            dpg.configure_item(TAGS["plan_empty"], show=True)
        if dpg.does_item_exist(TAGS["plan_summary"]):
            dpg.set_value(TAGS["plan_summary"], "")
        self._refresh_apply_enabled()
        self._update_header_status()
        self._refresh_stats_radar()
        self.request_preview_refresh()

    def new_species(self, sender=None, app_data=None, user_data=None) -> None:
        data = default_editor_data()
        data["mode"] = "add"
        draft_constant = self._next_draft_species_constant()
        data["constant_name"] = draft_constant
        data["species_name"] = "New species"
        data["folder_name"] = draft_constant.replace("SPECIES_", "").lower()
        for key, value in data.items():
            tag = "edit_mode" if key == "mode" else key
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, value)
        self.state.evolution_rows = []
        self.state.evolution_condition_rows = []
        self.state.selected_evolution_condition_index = -1
        self.state.level_up_rows = []
        self.state.teachable_rows = []
        self.state.tutor_rows = []
        self._render_evo_rows()
        self._render_levelup_rows()
        self._render_teachable_rows()
        self._render_tutor_rows()
        self._render_evolution_condition_rows()
        self._sync_evolution_param_widget()
        self._last_valid_description = self._normalize_description_text(str(dpg.get_value("description") or ""))
        if dpg.does_item_exist("evo_target"):
            dpg.set_value("evo_target", "")
        dpg.configure_item(TAGS["delete_btn"], show=False)
        self._ensure_draft_species_in_list(data["constant_name"], data["species_name"], data["folder_name"])
        self.filter_species()
        dpg.set_value(TAGS["species_list"], self._species_label({
            "constant_name": data["constant_name"],
            "species_name": data["species_name"],
        }))
        self.state.validation_ok = False
        self._status_validation = "idle"
        self.state.selected_species_constant = data["constant_name"]
        self._refresh_type_icons()
        self.mark_dirty()

    @staticmethod
    def _base_without_numeric_suffix(value: str) -> str:
        text = str(value or "").strip()
        m = re.match(r"^(.*)_\d+$", text)
        return m.group(1) if m else text

    @staticmethod
    def _next_unique_with_suffix(base: str, existing: set[str], start: int = 2) -> str:
        candidate = str(base or "").strip()
        if candidate and candidate not in existing:
            return candidate
        n = max(start, 2)
        while True:
            candidate = f"{base}_{n}"
            if candidate not in existing:
                return candidate
            n += 1

    def duplicate_selected_species(self, sender=None, app_data=None, user_data=None) -> None:
        if not self.state.project_loaded:
            self._set_message("Load a project first")
            return
        if not self.state.selected_species_constant:
            self._set_message("Select a species to duplicate")
            return

        source = next(
            (x for x in self.state.species_list if x.get("constant_name") == self.state.selected_species_constant),
            None,
        )
        if source is None:
            self._set_message("Could not find selected species")
            return

        data = self._read_editor_from_ui()
        data["mode"] = "add"

        existing_constants = {str(x.get("constant_name") or "").strip() for x in self.state.species_list if str(x.get("constant_name") or "").strip()}
        existing_folders = {str(x.get("folder_name") or "").strip() for x in self.state.species_list if str(x.get("folder_name") or "").strip()}

        base_constant = self._base_without_numeric_suffix(str(source.get("constant_name") or "SPECIES_NEW"))
        new_constant = self._next_unique_with_suffix(base_constant, existing_constants, start=2)
        base_folder = self._base_without_numeric_suffix(str(source.get("folder_name") or "new_species").lower())
        new_folder = self._next_unique_with_suffix(base_folder, existing_folders, start=2)

        data["constant_name"] = new_constant
        data["folder_name"] = new_folder.lower()
        data["species_name"] = str(source.get("species_name") or data.get("species_name") or "New species")

        self._suspend_dirty_events = True
        try:
            for key, value in data.items():
                tag = "edit_mode" if key == "mode" else key
                if dpg.does_item_exist(tag):
                    dpg.set_value(tag, value)
        finally:
            self._suspend_dirty_events = False

        self._ensure_draft_species_in_list(data["constant_name"], data["species_name"], data["folder_name"])
        self.filter_species()
        dpg.set_value(
            TAGS["species_list"],
            self._species_label({"constant_name": data["constant_name"], "species_name": data["species_name"]}),
        )
        self.state.selected_species_constant = data["constant_name"]
        dpg.configure_item(TAGS["delete_btn"], show=False)
        self._last_valid_description = self._normalize_description_text(str(dpg.get_value("description") or ""))
        self.mark_dirty()
        self._set_message(f"Duplicated as {data['constant_name']}")

    def _shortcut_pressed(self, key: str, now: float, cooldown: float = 0.22) -> bool:
        last = self._shortcut_last_trigger.get(key, 0.0)
        if now - last < cooldown:
            return False
        self._shortcut_last_trigger[key] = now
        return True

    def _handle_keyboard_shortcuts(self, now: float) -> None:
        try:
            ctrl = bool(dpg.is_key_down(dpg.mvKey_LControl) or dpg.is_key_down(dpg.mvKey_RControl))
            if ctrl and dpg.is_key_pressed(dpg.mvKey_F) and self._shortcut_pressed("ctrl_f", now):
                if dpg.does_item_exist(TAGS["search_input"]):
                    dpg.focus_item(TAGS["search_input"])
            if ctrl and dpg.is_key_pressed(dpg.mvKey_N) and self._shortcut_pressed("ctrl_n", now):
                self.new_species()
            if ctrl and dpg.is_key_pressed(dpg.mvKey_D) and self._shortcut_pressed("ctrl_d", now):
                self.duplicate_selected_species()
            if ctrl and dpg.is_key_pressed(dpg.mvKey_S) and self._shortcut_pressed("ctrl_s", now):
                self.validate_species()
            if ctrl and dpg.is_key_pressed(dpg.mvKey_R) and self._shortcut_pressed("ctrl_r", now):
                self.generate_dry_run()
            if ctrl and dpg.is_key_pressed(dpg.mvKey_Return) and self._shortcut_pressed("ctrl_enter", now):
                self.show_confirm_modal()
            if dpg.is_key_pressed(dpg.mvKey_Delete) and self._shortcut_pressed("delete", now):
                self.show_delete_modal()
            if ctrl and dpg.is_key_pressed(dpg.mvKey_Comma) and self._shortcut_pressed("ctrl_comma", now):
                self.open_settings_modal()
        except Exception:
            return

    def add_levelup_move(self, sender=None, app_data=None, user_data=None) -> None:
        level = int(dpg.get_value("move_level") or 1)
        move = str(dpg.get_value("move_name") or "").strip()
        if not move:
            self._set_message("Select a move")
            return
        self.state.level_up_rows.append({"level": max(1, min(100, level)), "move": move})
        self.state.selected_level_up_index = len(self.state.level_up_rows) - 1
        self._render_levelup_rows()
        self.mark_dirty()

    def remove_levelup_move(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_level_up_index
        if idx < 0 or idx >= len(self.state.level_up_rows):
            self._set_message("Select a level-up move to remove")
            return
        del self.state.level_up_rows[idx]
        self.state.selected_level_up_index = -1
        self._render_levelup_rows()
        self.mark_dirty()

    def move_levelup_up(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_level_up_index
        if idx <= 0 or idx >= len(self.state.level_up_rows):
            return
        self.state.level_up_rows[idx - 1], self.state.level_up_rows[idx] = self.state.level_up_rows[idx], self.state.level_up_rows[idx - 1]
        self.state.selected_level_up_index = idx - 1
        self._render_levelup_rows()
        self.mark_dirty()

    def move_levelup_down(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_level_up_index
        if idx < 0 or idx >= len(self.state.level_up_rows) - 1:
            return
        self.state.level_up_rows[idx + 1], self.state.level_up_rows[idx] = self.state.level_up_rows[idx], self.state.level_up_rows[idx + 1]
        self.state.selected_level_up_index = idx + 1
        self._render_levelup_rows()
        self.mark_dirty()

    def add_teachable_move(self, sender=None, app_data=None, user_data=None) -> None:
        move = str(dpg.get_value("tmhm_move") or "").strip()
        if not move:
            return
        if move not in self.state.teachable_rows:
            self.state.teachable_rows.append(move)
            self._render_teachable_rows()
            self.mark_dirty()

    def remove_teachable_move(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_teachable_index
        if idx < 0 or idx >= len(self.state.teachable_rows):
            self._set_message("Select a TM/HM move to remove")
            return
        del self.state.teachable_rows[idx]
        self.state.selected_teachable_index = -1
        self._render_teachable_rows()
        self.mark_dirty()

    def add_tutor_move(self, sender=None, app_data=None, user_data=None) -> None:
        move = str(dpg.get_value("tutor_move") or "").strip()
        if not move:
            return
        if move not in self.state.tutor_rows:
            self.state.tutor_rows.append(move)
            self._render_tutor_rows()
            self.mark_dirty()

    def remove_tutor_move(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_tutor_index
        if idx < 0 or idx >= len(self.state.tutor_rows):
            self._set_message("Select a tutor move to remove")
            return
        del self.state.tutor_rows[idx]
        self.state.selected_tutor_index = -1
        self._render_tutor_rows()
        self.mark_dirty()

    def select_tutor_row(self, sender=None, app_data=None, user_data=None) -> None:
        selected = dpg.get_value(TAGS["tutor_rows"])
        if not selected:
            self.state.selected_tutor_index = -1
            return
        try:
            self.state.selected_tutor_index = self.state.tutor_rows.index(selected)
            dpg.set_value("tutor_move", selected)
        except ValueError:
            self.state.selected_tutor_index = -1

    def show_delete_modal(self, sender=None, app_data=None, user_data=None) -> None:
        if not self.state.selected_species_constant:
            self._set_message("Select a species to delete")
            return
        if dpg.does_item_exist(TAGS["delete_replace_trainers_random"]):
            dpg.set_value(TAGS["delete_replace_trainers_random"], False)
        if dpg.does_item_exist(TAGS["delete_mode"]):
            dpg.set_value(TAGS["delete_mode"], "safe")
        dpg.configure_item(TAGS["delete_modal"], show=True)

    def hide_delete_modal(self, sender=None, app_data=None, user_data=None) -> None:
        dpg.configure_item(TAGS["delete_modal"], show=False)

    def confirm_delete_selected(self, sender=None, app_data=None, user_data=None) -> None:
        try:
            self.hide_delete_modal()
            if self._delete_in_progress:
                self._set_message("A deletion is already in progress")
                return
            if not self.editor:
                raise ValueError("Project not loaded")
            if not self.state.selected_species_constant:
                raise ValueError("No species selected")

            selected = self.editor.species_by_constant.get(self.state.selected_species_constant)
            if selected is None:
                raise ValueError("Could not resolve selected species")

            payload = {
                "mode": "delete",
                "constant_name": selected.constant_name,
                "species_name": selected.species_name or selected.constant_name,
                "folder_name": selected.folder_name or "",
                "assets_folder": "",
                "base_stats": {
                    "hp": 1,
                    "attack": 1,
                    "defense": 1,
                    "speed": 1,
                    "sp_attack": 1,
                    "sp_defense": 1,
                },
                "types": ["TYPE_NORMAL"],
                "abilities": ["ABILITY_NONE", "ABILITY_NONE", "ABILITY_NONE"],
                "height": 1,
                "weight": 1,
                "gender_ratio": "PERCENT_FEMALE(50)",
                "catch_rate": 1,
                "exp_yield": 1,
                "evolutions": [],
                "replace_in_use_trainers_random": bool(
                    dpg.get_value(TAGS["delete_replace_trainers_random"])
                ) if dpg.does_item_exist(TAGS["delete_replace_trainers_random"]) else False,
                "replace_in_use_random": bool(
                    dpg.get_value(TAGS["delete_replace_trainers_random"])
                ) if dpg.does_item_exist(TAGS["delete_replace_trainers_random"]) else False,
                "delete_mode": str(dpg.get_value(TAGS["delete_mode"]) or "safe") if dpg.does_item_exist(TAGS["delete_mode"]) else "safe",
            }

            fallback_folder = self.editor.pick_fallback_folder()
            validation = validate_species_definition(
                payload,
                Path.cwd() / "gui_payload.json",
                Path(self.state.project_path),
                fallback_folder,
            )
            payload, lint_ok = self._run_lint(payload, validation.used_fallback)
            if not lint_ok:
                raise ValueError("Lint has errors. Cannot delete.")

            plan = self.editor.build_plan(payload, validation)
            output_dir = Path.cwd() / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            plan_md = plan.to_markdown()
            plan_json = plan.to_dict()
            (output_dir / "change_plan.md").write_text(plan_md, encoding="utf-8")
            (output_dir / "change_plan.json").write_text(json.dumps(plan_json, indent=2, ensure_ascii=False), encoding="utf-8")
            dpg.set_value(TAGS["plan_text"], plan_md)
            if plan.is_blocked:
                raise ValueError("Invalid delete dry-run; review Change Plan")

            self._delete_in_progress = True
            self._delete_error = None
            self._delete_messages = ""
            if dpg.does_item_exist(TAGS["delete_work_text"]):
                dpg.set_value(TAGS["delete_work_text"], "Processing deletion. Please wait...")
            dpg.configure_item(TAGS["delete_work_modal"], show=True)

            def _worker() -> None:
                try:
                    result = self.editor.apply_plan(plan, validation)
                    self._delete_messages = "\n".join(result.messages)
                except Exception:
                    self._delete_error = traceback.format_exc()

            self._delete_thread = threading.Thread(target=_worker, daemon=True)
            self._delete_thread.start()
        except Exception:
            self._set_message(traceback.format_exc())

    def _finalize_delete_result(self) -> None:
        self._delete_in_progress = False
        dpg.configure_item(TAGS["delete_work_modal"], show=False)
        if self._delete_error:
            self._set_message(self._delete_error)
        else:
            self._set_message(self._delete_messages or "Deletion completed")
            if self.state.project_path:
                dpg.set_value(TAGS["project_input"], self.state.project_path)
            self.analyze_project()
            self.new_species()
            self.state.selected_species_constant = None
            dpg.configure_item(TAGS["delete_btn"], show=False)
            self.state.validation_ok = False
            self.state.dry_run_valid = False
            self._status_validation = "idle"
            self._status_dryrun = "idle"
            self._refresh_apply_enabled()
            self._update_header_status()
        self._delete_thread = None
        self._delete_error = None
        self._delete_messages = ""

    def auto_use_example(self, sender=None, app_data=None, user_data=None) -> None:
        dpg.set_value("assets_folder", "")
        self.mark_dirty()
        self._set_message("Internal asset fallback will be used during validation")

    def add_evolution_row(self, sender=None, app_data=None, user_data=None) -> None:
        method = str(dpg.get_value("evo_method") or "EVO_LEVEL").strip()
        param = self._evolution_param_from_ui()
        target_raw = str(dpg.get_value("evo_target") or "").strip()
        target = self._compose_target_with_condition(target_raw, [])
        if not self._extract_species_constant(target):
            self._set_message("Evolution target species is empty")
            return
        self.state.evolution_rows.append({"method": method, "param": param, "target": target})
        self.state.selected_evolution_index = len(self.state.evolution_rows) - 1
        self._render_evo_rows()
        self.mark_dirty()

    def update_evolution_row(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_evolution_index
        if idx < 0 or idx >= len(self.state.evolution_rows):
            self._set_message("Select an evolution row to update")
            return
        method = str(dpg.get_value("evo_method") or "EVO_LEVEL").strip()
        param = self._evolution_param_from_ui()
        target_raw = str(dpg.get_value("evo_target") or "").strip()
        target = self._compose_target_with_condition(target_raw, [])
        if not self._extract_species_constant(target):
            self._set_message("Evolution target species is empty")
            return
        self.state.evolution_rows[idx] = {"method": method, "param": param, "target": target}
        self._render_evo_rows()
        self.mark_dirty()

    def remove_evolution_row(self, sender=None, app_data=None, user_data=None) -> None:
        idx = self.state.selected_evolution_index
        if idx < 0 or idx >= len(self.state.evolution_rows):
            self._set_message("Select an evolution row to remove")
            return
        del self.state.evolution_rows[idx]
        self.state.selected_evolution_index = -1
        self._render_evo_rows()
        self.mark_dirty()

    def clear_evolutions(self, sender=None, app_data=None, user_data=None) -> None:
        self.state.evolution_rows = []
        self.state.selected_evolution_index = -1
        self.state.evolution_condition_rows = []
        self.state.selected_evolution_condition_index = -1
        self._render_evo_rows()
        self._render_evolution_condition_rows()
        self.mark_dirty()

    def on_preview_mode_change(self, sender=None, app_data=None, user_data=None) -> None:
        self.request_preview_refresh()

    def toggle_preview_frame(self, sender=None, app_data=None, user_data=None) -> None:
        self.state.preview_frame_index = 1 - int(self.state.preview_frame_index or 0)
        if dpg.does_item_exist(TAGS["preview_frame_toggle"]):
            dpg.set_value(TAGS["preview_frame_toggle"], f"Frame: {self.state.preview_frame_index + 1}")
        self.request_preview_refresh()

    def _editor_payload(self) -> dict:
        e = self._read_editor_from_ui()
        types = [e["type1"].strip()] if str(e["type1"]).strip() else []
        if str(e["type2"]).strip():
            types.append(e["type2"].strip())
        abilities = [str(e["ability1"]).strip(), str(e["ability2"]).strip(), str(e["ability_hidden"]).strip()]
        return {
            "mode": e["mode"],
            "constant_name": str(e["constant_name"]).strip(),
            "species_name": str(e["species_name"]).strip(),
            "description": str(e.get("description") or "").strip(),
            "folder_name": str(e["folder_name"]).strip(),
            "assets_folder": str(e["assets_folder"]).strip(),
            "base_stats": {
                "hp": int(e["hp"]),
                "attack": int(e["attack"]),
                "defense": int(e["defense"]),
                "speed": int(e["speed"]),
                "sp_attack": int(e["sp_attack"]),
                "sp_defense": int(e["sp_defense"]),
            },
            "types": types,
            "abilities": abilities,
            "height": int(e["height"]),
            "weight": int(e["weight"]),
            "gender_ratio": f"PERCENT_FEMALE({self._clamped_int(e.get('gender_ratio', 50), 0, 100, 50)})",
            "catch_rate": int(e["catch_rate"]),
            "exp_yield": int(e["exp_yield"]),
            "ev_yields": {
                "hp": int(e["ev_hp"]),
                "attack": int(e["ev_attack"]),
                "defense": int(e["ev_defense"]),
                "speed": int(e["ev_speed"]),
                "sp_attack": int(e["ev_sp_attack"]),
                "sp_defense": int(e["ev_sp_defense"]),
            },
            "cry_id": str(e.get("cry_id") or "CRY_NONE").strip() or "CRY_NONE",
            "evolutions": list(self.state.evolution_rows),
            "level_up_learnset": list(self.state.level_up_rows),
            "tmhm_learnset": list(self.state.teachable_rows),
            "tutor_learnset": list(self.state.tutor_rows),
        }

    def _run_lint(self, payload: dict, validation_used_fallback: bool):
        if not self.editor:
            return payload, False
        lint = lint_species_definition(
            data=payload,
            project_root=Path(self.state.project_path),
            existing_constants=set(self.editor.species_by_constant.keys()),
            using_fallback_assets=validation_used_fallback,
        )
        write_lint_report(Path.cwd() / "output", lint)
        self.state.last_errors = list(lint.errors)
        self.state.last_warnings = list(lint.warnings)
        if lint.ok:
            dpg.set_value(TAGS["lint_status"], "[OK]")
            dpg.configure_item(TAGS["lint_status"], color=PALETTE["success"])
        else:
            dpg.set_value(TAGS["lint_status"], "[ERROR] errors")
            dpg.configure_item(TAGS["lint_status"], color=PALETTE["error"])
        lines = []
        if lint.errors:
            lines.append("Errores:")
            lines.extend(f"- {e}" for e in lint.errors)
        if lint.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {w}" for w in lint.warnings)
        if not lines:
            lines.append("Sin issues")
        dpg.set_value(TAGS["lint_output"], "\n".join(lines))
        return lint.normalized_data, lint.ok

    def validate_species(self, sender=None, app_data=None, user_data=None) -> None:
        try:
            t0 = time.perf_counter()
            _, _, ok, _ = self._prepare_payload_validation_lint()
            if not ok:
                self.state.dry_run_valid = False
                self.state.validation_ok = False
                self._status_validation = "error"
                self._refresh_apply_enabled()
                self._update_header_status()
                self._set_message("Lint has errors. Fix before apply.")
            else:
                self.state.validation_ok = True
                self._status_validation = "ok"
                self._refresh_apply_enabled()
                self._update_header_status()
                self._set_message("Lint OK")
            self._record_perf("validate_species", (time.perf_counter() - t0) * 1000.0)
        except Exception:
            self._set_message(traceback.format_exc())

    def generate_dry_run(self, sender=None, app_data=None, user_data=None) -> None:
        try:
            t0 = time.perf_counter()
            if not self.editor:
                raise ValueError("Load a project first")
            payload, validation, lint_ok, sig = self._prepare_payload_validation_lint()
            if not lint_ok:
                self.state.dry_run_valid = False
                self.state.validation_ok = False
                self._status_dryrun = "error"
                self._status_validation = "error"
                self._refresh_apply_enabled()
                self._update_header_status()
                self._set_message("Lint has errors. Dry-run blocked.")
                return
            plan = self.editor.build_plan(payload, validation)

            output_dir = Path.cwd() / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            plan_md = plan.to_markdown()
            plan_json = plan.to_dict()
            (output_dir / "change_plan.md").write_text(plan_md, encoding="utf-8")
            (output_dir / "change_plan.json").write_text(json.dumps(plan_json, indent=2, ensure_ascii=False), encoding="utf-8")

            self.state.last_change_plan_md = plan_md
            self.state.last_change_plan_json = plan_json
            self.state.last_dry_run_signature = sig
            self.state.validation_ok = len(plan.errors) == 0
            self._status_validation = "ok" if self.state.validation_ok else "error"
            self.state.dry_run_valid = not plan.is_blocked
            self._status_dryrun = "ok" if self.state.dry_run_valid else "error"
            dpg.set_value(TAGS["plan_text"], plan_md)
            self._update_plan_summary(plan_json, len(plan.warnings), len(plan.errors))
            dpg.configure_item(TAGS["plan_empty"], show=False)
            self._refresh_apply_enabled()
            self._update_header_status()
            self._set_message(f"DRY-RUN generado. steps={len(plan.steps)}, warnings={len(plan.warnings)}, errors={len(plan.errors)}")
            self._record_perf("generate_dry_run", (time.perf_counter() - t0) * 1000.0)
        except Exception:
            self.state.dry_run_valid = False
            self.state.validation_ok = False
            self._status_dryrun = "error"
            self._status_validation = "error"
            self._refresh_apply_enabled()
            self._update_header_status()
            self._set_message(traceback.format_exc())

    def _update_plan_summary(self, plan_json: dict, warnings_count: int, errors_count: int) -> None:
        steps = plan_json.get("steps", []) if isinstance(plan_json, dict) else []
        files = sorted({s.get("target_file", "") for s in steps if isinstance(s, dict)})
        risks = [s.get("risk_level", "low") for s in steps if isinstance(s, dict)]
        risk_order = {"low": 1, "medium": 2, "high": 3}
        max_risk = "low"
        for r in risks:
            if risk_order.get(str(r), 0) > risk_order[max_risk]:
                max_risk = str(r)
        summary = [
            f"Archivos: {len(files)}",
            f"Cambios: {len(steps)}",
            f"Max risk: {max_risk}",
            f"Warnings: {warnings_count} | Errors: {errors_count}",
        ]
        dpg.set_value(TAGS["plan_summary"], "\n".join(summary))

    def show_confirm_modal(self, sender=None, app_data=None, user_data=None) -> None:
        if not self.state.dry_run_valid:
            self._set_message("Debes generar un DRY-RUN valido antes de aplicar")
            return
        dpg.configure_item(TAGS["confirm_modal"], show=True)

    def hide_confirm_modal(self, sender=None, app_data=None, user_data=None) -> None:
        dpg.configure_item(TAGS["confirm_modal"], show=False)

    def confirm_apply(self, sender=None, app_data=None, user_data=None) -> None:
        try:
            t0 = time.perf_counter()
            self.hide_confirm_modal()
            if not self.editor:
                raise ValueError("Project not loaded")
            payload = self._editor_payload()
            current_sig = self._payload_signature(payload)
            if current_sig != self.state.last_dry_run_signature:
                self._set_message("Changes detected after dry-run; regenerating dry-run automatically...")
                self.generate_dry_run()
                if not self.state.dry_run_valid:
                    raise ValueError("Automatic dry-run invalid. Review Change Plan.")
                payload = self._editor_payload()
            payload, validation, lint_ok, _ = self._prepare_payload_validation_lint()
            if not lint_ok:
                raise ValueError("Lint has errors. Cannot apply.")
            plan = self.editor.build_plan(payload, validation)
            if plan.is_blocked:
                raise ValueError("Plan blocked by errors. Review Change Plan panel.")
            result = self.editor.apply_plan(plan, validation)
            self._set_message("\n".join(result.messages))
            self.analyze_project()
            self.generate_dry_run()
            self.request_preview_refresh()
            self._record_perf("confirm_apply", (time.perf_counter() - t0) * 1000.0)
        except Exception:
            self._set_message(traceback.format_exc())

    def show_build_modal(self, sender=None, app_data=None, user_data=None) -> None:
        if not self.state.project_loaded:
            self._set_message("Load a project before building")
            return
        dpg.configure_item(TAGS["build_modal"], show=True)

    def hide_build_modal(self, sender=None, app_data=None, user_data=None) -> None:
        dpg.configure_item(TAGS["build_modal"], show=False)

    def run_build_check(self, sender=None, app_data=None, user_data=None) -> None:
        try:
            self.hide_build_modal()
            if not self.state.project_loaded:
                raise ValueError("Project not loaded")
            if self.state.build_in_progress:
                self._set_message("A build is already in progress")
                return
            self._status_build = "running"
            self._update_header_status()
            self.state.build_in_progress = True
            self.state.build_progress_value = 0.05
            self.state.build_live_output = "Starting build...\n"
            self._build_output_buffer = ["Starting build..."]
            dpg.configure_item(TAGS["build_progress"], default_value=0.05, overlay="Building...")
            dpg.set_value(TAGS["build_status"], "[RUNNING] Building project...")
            dpg.configure_item(TAGS["build_status"], color=PALETTE["warning"])
            dpg.set_value(TAGS["build_output"], self.state.build_live_output)

            project = Path(self.state.project_path)

            def _worker() -> None:
                jobs = max(1, os.cpu_count() or 1)
                proc = subprocess.Popen(
                    ["make", f"-j{jobs}"],
                    cwd=project,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                lines: list[str] = []
                assert proc.stdout is not None
                for line in proc.stdout:
                    clean = line.rstrip("\n")
                    lines.append(clean)
                    self._build_output_buffer = lines[-400:]
                    self.state.build_live_output = "\n".join(self._build_output_buffer)
                proc.wait()
                full = "\n".join(lines)
                errors, warnings = parse_build_output(full)
                self._build_result = BuildResult(
                    ok=proc.returncode == 0,
                    returncode=proc.returncode or 0,
                    stdout=full,
                    stderr="",
                    errors=errors,
                    warnings=warnings,
                )

            self._build_result = None
            self._build_thread = threading.Thread(target=_worker, daemon=True)
            self._build_thread.start()
            self._set_message("Build started")
        except Exception:
            self._set_message(traceback.format_exc())

    def _finalize_build_result(self, result: BuildResult) -> None:
        output_dir = Path.cwd() / "output"
        log_path, summary_path = write_build_outputs(output_dir, result)
        self.state.build_in_progress = False
        self.state.build_progress_value = 1.0
        dpg.configure_item(TAGS["build_progress"], default_value=1.0, overlay="Finalizado")
        self.state.last_build_status = "ok" if result.ok else "failed"
        self.state.last_build_errors = [f"{e.file}:{e.line if e.line is not None else '?'} {e.message}" for e in result.errors]
        self.state.last_build_warnings = result.warnings
        self.state.last_build_log_path = str(log_path)
        self.state.last_build_summary_md = summary_path.read_text(encoding="utf-8")
        status_text = "[OK] Build successful" if result.ok else "[ERROR] Build failed"
        self._status_build = "ok" if result.ok else "error"
        self._update_header_status()
        dpg.set_value(TAGS["build_status"], status_text)
        if result.ok:
            dpg.configure_item(TAGS["build_status"], color=PALETTE["success"])
        else:
            dpg.configure_item(TAGS["build_status"], color=PALETTE["error"])
        dpg.set_value(TAGS["build_output"], result.stdout[-20000:] if len(result.stdout) > 20000 else result.stdout)
        self._set_message(f"Build finalizado. Ver {summary_path} y {log_path}")
        self._build_thread = None
        self._build_result = None

    def open_project_path_dialog(self, sender=None, app_data=None, user_data=None) -> None:
        dpg.configure_item(TAGS["path_dialog"], show=True)

    def on_select_project_path(self, sender, app_data, user_data=None) -> None:
        selected = app_data.get("file_path_name") if isinstance(app_data, dict) else None
        if selected:
            dpg.set_value(TAGS["project_input"], selected)

    def open_build_summary(self, sender=None, app_data=None, user_data=None) -> None:
        summary = Path.cwd() / "output" / "build_summary.md"
        if not summary.exists():
            self._set_message("No existe output/build_summary.md")
            return
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", str(summary)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(summary)])
            else:
                os.startfile(str(summary))  # type: ignore[attr-defined]
        except Exception:
            self._set_message("Could not open build_summary.md automatically")
    @staticmethod
    def _species_label(item: dict) -> str:
        return f"{item.get('species_name', '')} ({item.get('constant_name', '')})"
