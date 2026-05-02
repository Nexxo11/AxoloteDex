from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

from gui.actions import GuiActions
from gui.components import TAGS, build_layout
from gui.state import GuiState, default_editor_data, load_config, save_config
from gui.themes import (
    create_disabled_button_theme,
    create_dark_theme,
    create_danger_button_theme,
    create_light_theme,
    create_primary_button_theme,
    create_secondary_button_theme,
    detect_system_theme,
)


def main() -> None:
    config_path = Path.cwd() / "config.json"
    cfg = load_config(config_path)

    state = GuiState()
    state.editor_data = default_editor_data()
    if isinstance(cfg.get("last_project_path"), str):
        state.project_path = cfg["last_project_path"]
    if isinstance(cfg.get("last_species_constant"), str) and cfg.get("last_species_constant"):
        state.selected_species_constant = cfg["last_species_constant"]

    actions = GuiActions(state, config_path)

    dpg.create_context()
    font_candidates = [
        Path.cwd() / "gui/fonts/FiraCode-Regular.ttf",
        Path("/usr/share/fonts/truetype/firacode/FiraCode-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ]
    default_font = None
    settings_icon_font = None
    for font_path in font_candidates:
        if not font_path.exists():
            continue
        with dpg.font_registry():
            default_font = dpg.add_font(str(font_path), 16)
        break

    symbol_font_path = Path.cwd() / "gui/fonts/NotoSansSymbols-Regular.ttf"
    if symbol_font_path.exists():
        with dpg.font_registry():
            settings_icon_font = dpg.add_font(str(symbol_font_path), 54)

    with dpg.texture_registry(show=False, tag="tex_registry"):
        empty = [0.2, 0.2, 0.2, 1.0] * (32 * 32)
        dpg.add_static_texture(32, 32, empty, tag="tex_front")
        dpg.add_static_texture(32, 32, empty, tag="tex_back")
        dpg.add_static_texture(32, 32, empty, tag="tex_icon")
        dpg.add_static_texture(32, 32, empty, tag="tex_type1")
        dpg.add_static_texture(32, 32, empty, tag="tex_type2")
    build_layout(actions)
    dark_theme = create_dark_theme()
    light_theme = create_light_theme()

    def apply_theme_choice(choice: str) -> None:
        selected = str(choice or "Dark")
        resolved = detect_system_theme() if selected == "System" else selected
        dpg.bind_theme(light_theme if resolved == "Light" else dark_theme)

    apply_theme_choice(str(cfg.get("settings_theme") or "Dark"))
    actions.set_theme_switcher(apply_theme_choice)
    if default_font is not None:
        dpg.bind_font(default_font)
    if settings_icon_font is not None and dpg.does_item_exist(TAGS["settings_fab"]):
        dpg.bind_item_font(TAGS["settings_fab"], settings_icon_font)
    primary_btn = create_primary_button_theme()
    secondary_btn = create_secondary_button_theme()
    disabled_btn = create_disabled_button_theme()
    danger_btn = create_danger_button_theme()
    actions.set_button_themes(primary_btn, secondary_btn, disabled_btn)

    for tag in [
        TAGS["btn_load"],
        TAGS["compile_btn"],
        TAGS["btn_new"],
        TAGS["btn_project_select"],
    ]:
        if dpg.does_item_exist(tag):
            dpg.bind_item_theme(tag, primary_btn)

    for tag in [TAGS["btn_delete_cancel"]]:
        if dpg.does_item_exist(tag):
            dpg.bind_item_theme(tag, secondary_btn)

    for tag in [TAGS["delete_btn"], TAGS["btn_delete_confirm"]]:
        if dpg.does_item_exist(tag):
            dpg.bind_item_theme(tag, danger_btn)

    if state.project_path:
        dpg.set_value(TAGS["project_input"], state.project_path)

    if dpg.does_item_exist(TAGS["settings_language"]) and isinstance(cfg.get("settings_language"), str):
        dpg.set_value(TAGS["settings_language"], cfg["settings_language"])
    if dpg.does_item_exist(TAGS["settings_theme"]) and isinstance(cfg.get("settings_theme"), str):
        dpg.set_value(TAGS["settings_theme"], cfg["settings_theme"])
        apply_theme_choice(cfg["settings_theme"])
    if dpg.does_item_exist(TAGS["settings_backup_auto"]) and isinstance(cfg.get("settings_backup_auto"), bool):
        dpg.set_value(TAGS["settings_backup_auto"], cfg["settings_backup_auto"])
    if dpg.does_item_exist(TAGS["settings_backup_keep"]) and isinstance(cfg.get("settings_backup_keep"), int):
        dpg.set_value(TAGS["settings_backup_keep"], cfg["settings_backup_keep"])
    if dpg.does_item_exist(TAGS["settings_notify_success"]) and isinstance(cfg.get("settings_notify_success"), bool):
        dpg.set_value(TAGS["settings_notify_success"], cfg["settings_notify_success"])
    if dpg.does_item_exist(TAGS["settings_notify_warning"]) and isinstance(cfg.get("settings_notify_warning"), bool):
        dpg.set_value(TAGS["settings_notify_warning"], cfg["settings_notify_warning"])

    viewport_w = int(cfg.get("window_width", 1560)) if isinstance(cfg.get("window_width"), int) else 1560
    viewport_h = int(cfg.get("window_height", 880)) if isinstance(cfg.get("window_height"), int) else 880
    dpg.create_viewport(title="AxoloteDex", width=viewport_w, height=viewport_h)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    while dpg.is_dearpygui_running():
        actions.pump()
        dpg.render_dearpygui_frame()
    save_config(
        config_path,
        {
            "last_project_path": state.project_path,
            "last_species_constant": state.selected_species_constant or "",
            "window_width": dpg.get_viewport_client_width(),
            "window_height": dpg.get_viewport_client_height(),
            "settings_language": dpg.get_value(TAGS["settings_language"]) if dpg.does_item_exist(TAGS["settings_language"]) else "English",
            "settings_theme": dpg.get_value(TAGS["settings_theme"]) if dpg.does_item_exist(TAGS["settings_theme"]) else "Dark",
            "settings_backup_auto": bool(dpg.get_value(TAGS["settings_backup_auto"])) if dpg.does_item_exist(TAGS["settings_backup_auto"]) else True,
            "settings_backup_keep": int(dpg.get_value(TAGS["settings_backup_keep"])) if dpg.does_item_exist(TAGS["settings_backup_keep"]) else 15,
            "settings_notify_success": bool(dpg.get_value(TAGS["settings_notify_success"])) if dpg.does_item_exist(TAGS["settings_notify_success"]) else True,
            "settings_notify_warning": bool(dpg.get_value(TAGS["settings_notify_warning"])) if dpg.does_item_exist(TAGS["settings_notify_warning"]) else True,
        },
    )
    dpg.destroy_context()


if __name__ == "__main__":
    main()
