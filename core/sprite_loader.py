from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass
class SpritePreview:
    front_path: Path
    back_path: Path
    icon_path: Path
    used_fallback: bool
    warning: str | None = None


_CACHE: dict[tuple[str, float], tuple[int, int, list[float]]] = {}


def _choose_first(folder: Path, names: list[str]) -> Path | None:
    for name in names:
        p = folder / name
        if p.exists():
            return p
    return None


def resolve_preview_paths(
    project_root: Path,
    folder_name: str,
    assets_folder: str | None = None,
    palette_mode: str = "normal",
) -> SpritePreview:
    main_folder = project_root / "graphics" / "pokemon" / folder_name
    source_folder = main_folder
    used_fallback = False

    if assets_folder:
        custom = Path(assets_folder).expanduser()
        if not custom.is_absolute():
            custom = (Path.cwd() / custom).resolve()
        if custom.exists() and custom.is_dir():
            source_folder = custom

    shiny = str(palette_mode).lower() == "shiny"
    front_names = ["front.png", "anim_front.png"]
    back_names = ["back.png"]
    icon_names = ["icon.png"]
    if shiny:
        front_names = ["shiny_front.png", "front_shiny.png", "shiny_anim_front.png", "anim_front_shiny.png"] + front_names
        back_names = ["shiny_back.png", "back_shiny.png"] + back_names
        icon_names = ["shiny_icon.png", "icon_shiny.png"] + icon_names

    front = _choose_first(source_folder, front_names)
    back = _choose_first(source_folder, back_names)
    icon = _choose_first(source_folder, icon_names)

    fallback = project_root / "graphics" / "pokemon" / "bulbasaur"
    if front is None:
        front = _choose_first(fallback, ["front.png", "anim_front.png"])
        used_fallback = True
    if back is None:
        back = _choose_first(fallback, ["back.png"])
        used_fallback = True
    if icon is None:
        icon = _choose_first(fallback, ["icon.png"])
        used_fallback = True

    warning_parts: list[str] = []
    if used_fallback:
        warning_parts.append("Usando gráficos de ejemplo (Bulbasaur)")
    if shiny and not any(name in front.name for name in ["shiny_front", "front_shiny", "shiny_anim_front", "anim_front_shiny"]):
        warning_parts.append("Shiny preview: no hay PNG shiny dedicado; se muestra sprite base")
    warning = " | ".join(warning_parts) if warning_parts else None
    if front is None or back is None or icon is None:
        raise FileNotFoundError("No se pudieron resolver sprites ni fallback bulbasaur")

    return SpritePreview(
        front_path=front,
        back_path=back,
        icon_path=icon,
        used_fallback=used_fallback,
        warning=warning,
    )


def _crop_frame(img: Image.Image, kind: str, frame_index: int) -> Image.Image:
    w, h = img.size
    if kind in {"front", "icon"}:
        # Algunos sheets vienen en horizontal (2 columnas) y otros en vertical (2 filas).
        if w % 2 == 0 and w >= h * 2:
            half = w // 2
            if frame_index <= 0:
                return img.crop((0, 0, half, h))
            return img.crop((half, 0, w, h))
        if h % 2 == 0 and h >= w * 2:
            half = h // 2
            if frame_index <= 0:
                return img.crop((0, 0, w, half))
            return img.crop((0, half, w, h))
    return img


def load_texture_data(
    path: Path,
    kind: str = "generic",
    scale: int = 2,
    frame_index: int = 0,
    palette_mode: str = "normal",
) -> tuple[int, int, list[float]]:
    mtime = path.stat().st_mtime
    key = (f"{path.resolve()}::{kind}::{scale}::{frame_index}::{palette_mode}", mtime)
    if key in _CACHE:
        return _CACHE[key]

    with Image.open(path) as img:
        framed = _crop_frame(img, kind, frame_index)
        if scale > 1:
            framed = framed.resize((framed.width * scale, framed.height * scale), Image.NEAREST)
        rgba = framed.convert("RGBA")
        w, h = rgba.size
        data = []
        for r, g, b, a in rgba.getdata():
            data.extend([r / 255.0, g / 255.0, b / 255.0, a / 255.0])
    _CACHE[key] = (w, h, data)
    return _CACHE[key]
