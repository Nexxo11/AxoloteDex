from __future__ import annotations

import dearpygui.dearpygui as dpg


def create_dark_theme() -> int:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (22, 24, 29, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (27, 30, 36, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (40, 44, 53, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (56, 93, 168, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (74, 114, 194, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (43, 80, 153, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (230, 230, 235, 255))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)
    return theme
