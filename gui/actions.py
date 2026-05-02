from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
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
        self._preview_texture_tags = {"front": "tex_front", "back": "tex_back", "icon": "tex_icon"}
        self._type_texture_tags = {"type1": "tex_type1", "type2": "tex_type2"}
        self._type_picker_texture_tags: dict[str, str] = {}
        self._icon_button_theme: int | None = None
        self._preview_throttle_seconds = 0.15
        self._last_preview_refresh = 0.0
        self._preview_pending = False
        self._icon_anim_interval = 0.33
        self._icon_anim_last = 0.0
        self._icon_anim_frame = 0
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

    def _refresh_stats_radar(self) -> None:
        if not dpg.does_item_exist(TAGS["stats_radar_drawlist"]):
            return

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

        draw_tag = TAGS["stats_radar_drawlist"]
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
        cries = _load_enum_tokens(cries_file, "CRY_")

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
        self.state.tmhm_options = sorted(set(tmhm_moves)) if tmhm_moves else ["MOVE_TACKLE"]
        self.state.tutor_options = sorted(set(tutor_moves)) if tutor_moves else ["MOVE_TACKLE"]
        self.state.cry_options = cries if cries else ["CRY_NONE"]

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
        if not self._radar_initialized and dpg.does_item_exist(TAGS["stats_radar_drawlist"]):
            self._radar_initialized = True
            self._refresh_stats_radar()
        now = time.monotonic()

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
            header_h = 108
        elif viewport_w < 1850:
            left_ratio = 0.24
            header_h = 104
        else:
            left_ratio = 0.22
            header_h = 100

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
            dpg.configure_item("cry_id", width=min(420, max(280, workspace_w - 340)))
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
        dpg.configure_item("evo_target", width=max(320, workspace_w - 190))
        dpg.configure_item("evo_friendship_param", width=120)
        dpg.configure_item("evo_item_param", width=max(220, workspace_w - 360))
        dpg.configure_item("evo_trade_item_param", width=max(220, workspace_w - 360))
        dpg.configure_item(TAGS["evo_rows"], width=workspace_w - 30)
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

        content_w = workspace_w - 32
        dpg.configure_item(TAGS["preview_warning"], wrap=max(220, general_right_w - 14))
        dpg.configure_item(TAGS["plan_summary"], width=content_w)
        dpg.configure_item(TAGS["plan_text"], width=content_w, height=max(260, row_h - 210))
        dpg.configure_item(TAGS["build_output"], width=content_w, height=max(260, row_h - 190))
        stats_panel_h = max(240, int(row_h * 0.40))
        stats_left_w = max(420, min(520, int(content_w * 0.50)))
        stats_radar_w = max(280, content_w - stats_left_w - 12)
        self._radar_last_size = (float(stats_radar_w), float(stats_panel_h))
        if dpg.does_item_exist(TAGS["stats_fields_panel"]):
            dpg.configure_item(TAGS["stats_fields_panel"], width=stats_left_w, height=stats_panel_h)
        if dpg.does_item_exist(TAGS["stats_radar_panel"]):
            dpg.configure_item(TAGS["stats_radar_panel"], width=stats_radar_w, height=stats_panel_h)
        if dpg.does_item_exist(TAGS["stats_radar_drawlist"]):
            dpg.configure_item(TAGS["stats_radar_drawlist"], width=stats_radar_w, height=stats_panel_h)
            self._refresh_stats_radar()

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

            dpg.configure_item(TAGS["preview_front_img"], texture_tag=new_front, width=fw, height=fh)
            dpg.configure_item(TAGS["preview_back_img"], texture_tag=new_back, width=bw, height=bh)
            if icon_payload is not None:
                new_icon, iw, ih = icon_payload
                dpg.configure_item(TAGS["preview_icon_img"], texture_tag=new_icon, width=iw, height=ih)

            old_tags = self._preview_texture_tags.copy()
            self._preview_texture_tags = {
                "front": new_front,
                "back": new_back,
                "icon": icon_payload[0] if icon_payload is not None else self._preview_texture_tags.get("icon", "tex_icon"),
            }
            for old_tag in old_tags.values():
                if old_tag in {"tex_front", "tex_back", "tex_icon"}:
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
        rows: list[dict[str, str]] = []
        for m in re.finditer(r"\{\s*([^,}]+)\s*,\s*([^,}]+)\s*,\s*([^}]+)\}", evolutions_raw):
            rows.append({"method": m.group(1).strip(), "param": m.group(2).strip(), "target": m.group(3).strip()})
        return rows

    def _render_evo_rows(self) -> None:
        items = [f"{r['method']} | {r['param']} -> {r['target']}" for r in self.state.evolution_rows]
        dpg.configure_item(TAGS["evo_rows"], items=items)
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
        is_level = method == "EVO_LEVEL"
        is_item = method == "EVO_ITEM"
        is_trade = method == "EVO_TRADE"
        is_friendship = method == "EVO_FRIENDSHIP"

        dpg.configure_item("evo_level_param", show=is_level)
        dpg.configure_item("evo_friendship_param", show=is_friendship)
        dpg.configure_item("evo_item_param", show=is_item)
        dpg.configure_item("evo_trade_item_param", show=is_trade)
        dpg.configure_item("evo_param", show=False)

        options = self.state.item_options or ["ITEM_NONE"]
        current = str(dpg.get_value("evo_param") or "").strip()
        if is_item:
            dpg.set_value("evo_item_param", current if current in options else options[0])
        elif is_trade:
            dpg.set_value("evo_trade_item_param", current if current in options else "ITEM_NONE")
        elif is_level:
            try:
                dpg.set_value("evo_level_param", max(1, min(100, int(current or "16"))))
            except ValueError:
                dpg.set_value("evo_level_param", 16)
        elif is_friendship:
            try:
                dpg.set_value("evo_friendship_param", max(1, min(255, int(current or "220"))))
            except ValueError:
                dpg.set_value("evo_friendship_param", 220)

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
        if method == "EVO_LEVEL":
            return str(max(1, min(100, int(dpg.get_value("evo_level_param") or 16))))
        if method == "EVO_ITEM":
            return str(dpg.get_value("evo_item_param") or "ITEM_NONE").strip() or "ITEM_NONE"
        if method == "EVO_TRADE":
            return str(dpg.get_value("evo_trade_item_param") or "ITEM_NONE").strip() or "ITEM_NONE"
        if method == "EVO_FRIENDSHIP":
            return str(max(1, min(255, int(dpg.get_value("evo_friendship_param") or 220))))
        return str(dpg.get_value("evo_param") or "1").strip() or "1"

    def _set_evolution_param_ui(self, method: str, param: str) -> None:
        dpg.set_value("evo_param", param)
        if method == "EVO_LEVEL":
            try:
                dpg.set_value("evo_level_param", max(1, min(100, int(param or "16"))))
            except ValueError:
                dpg.set_value("evo_level_param", 16)
        elif method == "EVO_ITEM":
            dpg.set_value("evo_item_param", param or "ITEM_NONE")
        elif method == "EVO_TRADE":
            dpg.set_value("evo_trade_item_param", param or "ITEM_NONE")
        elif method == "EVO_FRIENDSHIP":
            try:
                dpg.set_value("evo_friendship_param", max(1, min(255, int(param or "220"))))
            except ValueError:
                dpg.set_value("evo_friendship_param", 220)

    def select_evolution_row(self, sender=None, app_data=None, user_data=None) -> None:
        selected = dpg.get_value(TAGS["evo_rows"])
        if not selected:
            self.state.selected_evolution_index = -1
            return
        for idx, row in enumerate(self.state.evolution_rows):
            label = f"{row['method']} | {row['param']} -> {row['target']}"
            if label == selected:
                self.state.selected_evolution_index = idx
                dpg.set_value("evo_method", row["method"])
                self._set_evolution_param_ui(row["method"], row["param"])
                dpg.set_value("evo_target", row["target"])
                self._sync_evolution_param_widget()
                return
        self.state.selected_evolution_index = -1

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
            self.state.level_up_rows = []
            self.state.teachable_rows = []
            self.state.tutor_rows = []
            self._render_evo_rows()
            self._render_levelup_rows()
            self._render_teachable_rows()
            self._render_tutor_rows()
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
        self._render_evo_rows()
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
            val = str(dpg.get_value("description") or "")
            if len(val) > self.MAX_DESCRIPTION_LEN:
                self._suspend_dirty_events = True
                try:
                    dpg.set_value("description", val[: self.MAX_DESCRIPTION_LEN])
                finally:
                    self._suspend_dirty_events = False

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
        self.state.level_up_rows = []
        self.state.teachable_rows = []
        self.state.tutor_rows = []
        self._render_evo_rows()
        self._render_levelup_rows()
        self._render_teachable_rows()
        self._render_tutor_rows()
        self._sync_evolution_param_widget()
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
        target = str(dpg.get_value("evo_target") or "").strip()
        if not target:
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
        target = str(dpg.get_value("evo_target") or "").strip()
        if not target:
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
        self._render_evo_rows()
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
            dpg.set_value(TAGS["lint_status"], "✔ OK")
            dpg.configure_item(TAGS["lint_status"], color=PALETTE["success"])
        else:
            dpg.set_value(TAGS["lint_status"], "❌ errors")
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
            dpg.set_value(TAGS["build_status"], "⏳ Building project...")
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
        status_text = "✔ Build successful" if result.ok else "❌ Build failed"
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
