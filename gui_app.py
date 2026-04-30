from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

from gui_actions import GuiActions
from gui_components import TAGS, build_layout
from gui_state import GuiState, default_editor_data, load_config
from themes import create_dark_theme


def main() -> None:
    config_path = Path.cwd() / "config.json"
    cfg = load_config(config_path)

    state = GuiState()
    state.editor_data = default_editor_data()
    if isinstance(cfg.get("last_project_path"), str):
        state.project_path = cfg["last_project_path"]

    actions = GuiActions(state, config_path)

    dpg.create_context()
    with dpg.texture_registry(show=False, tag="tex_registry"):
        empty = [0.2, 0.2, 0.2, 1.0] * (32 * 32)
        dpg.add_static_texture(32, 32, empty, tag="tex_front")
        dpg.add_static_texture(32, 32, empty, tag="tex_back")
        dpg.add_static_texture(32, 32, empty, tag="tex_icon")
    build_layout(actions)
    dpg.bind_theme(create_dark_theme())

    if state.project_path:
        dpg.set_value(TAGS["project_input"], state.project_path)

    dpg.create_viewport(title="Species Editor (DearPyGui)", width=1450, height=900)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    while dpg.is_dearpygui_running():
        actions.pump()
        dpg.render_dearpygui_frame()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
