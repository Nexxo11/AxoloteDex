from __future__ import annotations

import dearpygui.dearpygui as dpg


PALETTE = {
    "background": (12, 13, 20, 255),
    "panel": (17, 18, 28, 255),
    "panel_alt": (52, 54, 69, 255),
    "input": (24, 26, 38, 255),
    "input_hover": (34, 36, 50, 255),
    "border": (73, 62, 116, 255),
    "primary": (136, 109, 219, 255),
    "primary_hover": (151, 124, 236, 255),
    "danger": (202, 52, 78, 255),
    "danger_hover": (220, 67, 94, 255),
    "text": (232, 233, 244, 255),
    "muted_text": (154, 159, 183, 255),
    "success": (94, 204, 154, 255),
    "warning": (237, 199, 88, 255),
    "error": (244, 103, 121, 255),
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
        with dpg.theme_component(dpg.mvButton, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (70, 70, 84, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (70, 70, 84, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (70, 70, 84, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (170, 170, 182, 255))
    return theme


def create_primary_button_theme() -> int:
    return _button_theme(PALETTE["primary"], PALETTE["primary_hover"])


def create_secondary_button_theme() -> int:
    return _button_theme(PALETTE["panel_alt"], PALETTE["input_hover"])


def create_disabled_button_theme() -> int:
    return _button_theme((70, 70, 84, 255), (70, 70, 84, 255))


def create_danger_button_theme() -> int:
    return _button_theme(PALETTE["danger"], PALETTE["danger_hover"])
