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
    create_primary_button_theme,
    create_secondary_button_theme,
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
    with dpg.texture_registry(show=False, tag="tex_registry"):
        empty = [0.2, 0.2, 0.2, 1.0] * (32 * 32)
        dpg.add_static_texture(32, 32, empty, tag="tex_front")
        dpg.add_static_texture(32, 32, empty, tag="tex_back")
        dpg.add_static_texture(32, 32, empty, tag="tex_icon")
    build_layout(actions)
    dpg.bind_theme(create_dark_theme())
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
        },
    )
    dpg.destroy_context()


if __name__ == "__main__":
    main()
