from __future__ import annotations

import dearpygui.dearpygui as dpg


PALETTE = {
    "background": (17, 17, 22, 255),
    "panel": (26, 26, 34, 255),
    "panel_alt": (36, 36, 49, 255),
    "input": (25, 25, 32, 255),
    "input_hover": (36, 36, 49, 255),
    "border": (75, 63, 114, 255),
    "primary": (142, 107, 232, 255),
    "primary_hover": (157, 123, 255, 255),
    "danger": (207, 51, 75, 255),
    "danger_hover": (227, 67, 92, 255),
    "text": (232, 230, 240, 255),
    "muted_text": (168, 163, 184, 255),
    "success": (88, 214, 141, 255),
    "warning": (245, 197, 66, 255),
    "error": (255, 92, 108, 255),
}


def create_dark_theme() -> int:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, PALETTE["background"])
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, PALETTE["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, PALETTE["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, PALETTE["input"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, PALETTE["input_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, PALETTE["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, PALETTE["border"])
            dpg.add_theme_color(dpg.mvThemeCol_BorderShadow, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_Button, PALETTE["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, PALETTE["primary_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, PALETTE["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_Text, PALETTE["text"])
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, PALETTE["muted_text"])
            dpg.add_theme_color(dpg.mvThemeCol_Header, PALETTE["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, PALETTE["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, PALETTE["primary_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_Tab, PALETTE["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, PALETTE["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, PALETTE["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocused, PALETTE["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocusedActive, PALETTE["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, PALETTE["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, PALETTE["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, PALETTE["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, PALETTE["primary_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, PALETTE["primary_hover"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 7)
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 7)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 10, 9)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 12, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 7)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 12)
    return theme


def _button_theme(base: tuple[int, int, int, int], hover: tuple[int, int, int, int]) -> int:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, base)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hover)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, base)
            dpg.add_theme_color(dpg.mvThemeCol_Text, PALETTE["text"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 7)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 12, 9)
    return theme


def create_primary_button_theme() -> int:
    return _button_theme(PALETTE["primary"], PALETTE["primary_hover"])


def create_secondary_button_theme() -> int:
    return _button_theme(PALETTE["panel_alt"], PALETTE["input_hover"])


def create_danger_button_theme() -> int:
    return _button_theme(PALETTE["danger"], PALETTE["danger_hover"])
