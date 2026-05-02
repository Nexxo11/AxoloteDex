from __future__ import annotations

import dearpygui.dearpygui as dpg
import os
import subprocess


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

LIGHT_PALETTE = {
    "background": (244, 246, 252, 255),
    "panel": (252, 253, 255, 255),
    "panel_alt": (229, 234, 245, 255),
    "input": (238, 242, 250, 255),
    "input_hover": (228, 234, 246, 255),
    "border": (170, 178, 205, 255),
    "primary": (92, 124, 215, 255),
    "primary_hover": (112, 142, 228, 255),
    "danger": (202, 52, 78, 255),
    "danger_hover": (220, 67, 94, 255),
    "text": (33, 38, 52, 255),
    "muted_text": (98, 108, 132, 255),
    "success": (52, 168, 114, 255),
    "warning": (182, 132, 34, 255),
    "error": (188, 56, 74, 255),
}


def _create_theme_from_palette(p: dict[str, tuple[int, int, int, int]]) -> int:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, p["background"])
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, p["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, p["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, p["input"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, p["input_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, p["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, p["border"])
            dpg.add_theme_color(dpg.mvThemeCol_BorderShadow, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_Button, p["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, p["primary_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, p["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_Text, p["text"])
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, p["muted_text"])
            dpg.add_theme_color(dpg.mvThemeCol_Header, p["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, p["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, p["primary_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_Tab, p["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, p["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, p["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocused, p["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocusedActive, p["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, p["panel"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, p["panel_alt"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, p["primary"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, p["primary_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, p["primary_hover"])
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


def create_dark_theme() -> int:
    return _create_theme_from_palette(PALETTE)


def create_light_theme() -> int:
    return _create_theme_from_palette(LIGHT_PALETTE)


def create_custom_theme(custom_palette: dict[str, tuple[int, int, int, int]]) -> int:
    merged = dict(PALETTE)
    merged.update(custom_palette)
    return _create_theme_from_palette(merged)


def detect_system_theme() -> str:
    if os.name == "nt":
        return "Dark"
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
    if "gnome" in desktop or "ubuntu" in desktop:
        try:
            out = subprocess.check_output(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.5,
            ).strip().lower()
            if "prefer-light" in out:
                return "Light"
            if "prefer-dark" in out:
                return "Dark"
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.5,
            ).strip().lower()
            return "Dark" if "dark" in out else "Light"
        except Exception:
            pass
    return "Dark"


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
