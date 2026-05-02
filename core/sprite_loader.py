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
    palette_variant: str = ""
    warning: str | None = None


_CACHE: dict[tuple[str, float], tuple[int, int, list[float]]] = {}


def _choose_first(folder: Path, names: list[str]) -> Path | None:
    for name in names:
        p = folder / name
        if p.exists():
            return p
    return None


def _resolve_species_folder(project_root: Path, folder_name: str) -> Path:
    base = project_root / "graphics" / "pokemon"
    raw = str(folder_name or "").strip().strip("/")
    direct = base / raw
    if direct.exists() and direct.is_dir():
        return direct

    candidates: list[Path] = []
    if "_" in raw:
        parts = raw.split("_")
        if len(parts) >= 2:
            candidates.append(base / parts[0] / "_".join(parts[1:]))
        candidates.append(base / raw.replace("_", "/"))
        for i in range(len(parts) - 1, 0, -1):
            prefix = base / "/".join(parts[:i])
            candidates.append(prefix)
        for i in range(len(parts) - 1, 0, -1):
            prefix = base / parts[0] / "_".join(parts[1:i + 1])
            candidates.append(prefix)

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return direct


def _extract_palette_variant(folder_name: str, resolved_folder: Path, project_root: Path) -> str:
    raw = str(folder_name or "").strip().lower()
    if not raw:
        return ""
    base = resolved_folder.name.lower()
    try:
        rel = resolved_folder.relative_to(project_root / "graphics" / "pokemon")
        rel_key = "_".join(part.lower() for part in rel.parts)
    except Exception:
        rel_key = base
    if raw == base:
        return ""
    if raw == rel_key:
        return ""
    if raw.startswith(rel_key + "_"):
        tail = raw[len(rel_key) + 1 :]
        return f"{base}_{tail}" if tail else ""
    if raw.startswith(base + "_"):
        return raw[len(base) + 1 :]
    return ""


def resolve_preview_paths(
    project_root: Path,
    folder_name: str,
    assets_folder: str | None = None,
    palette_mode: str = "normal",
) -> SpritePreview:
    main_folder = _resolve_species_folder(project_root, folder_name)
    source_folder = main_folder
    used_fallback = False

    if assets_folder:
        custom = Path(assets_folder).expanduser()
        if not custom.is_absolute():
            custom = (Path.cwd() / custom).resolve()
        if custom.exists() and custom.is_dir():
            source_folder = custom

    shiny = str(palette_mode).lower() == "shiny"
    palette_variant = _extract_palette_variant(folder_name, main_folder, project_root)
    front_names = ["front.png", "anim_front.png"]
    back_names = ["back.png"]
    icon_names = ["icon.png"]

    search_folders = [source_folder]
    pokemon_root = project_root / "graphics" / "pokemon"
    parent = source_folder.parent
    while parent != parent.parent and parent != pokemon_root.parent:
        if parent == pokemon_root:
            break
        search_folders.append(parent)
        parent = parent.parent

    def _pick_with_parent_fallback(names: list[str]) -> Path | None:
        for folder in search_folders:
            hit = _choose_first(folder, names)
            if hit is not None:
                return hit
        return None

    front = _pick_with_parent_fallback(front_names)
    back = _pick_with_parent_fallback(back_names)
    icon = _pick_with_parent_fallback(icon_names)

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
    if shiny:
        warning_parts.append("Shiny preview: se aplica shiny.pal sobre sprite base")
    if palette_variant:
        warning_parts.append(f"Variante detectada: {palette_variant}")
    warning = " | ".join(warning_parts) if warning_parts else None
    if front is None or back is None or icon is None:
        raise FileNotFoundError("No se pudieron resolver sprites ni fallback bulbasaur")

    return SpritePreview(
        front_path=front,
        back_path=back,
        icon_path=icon,
        used_fallback=used_fallback,
        palette_variant=palette_variant,
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


def _parse_jasc_pal(text: str) -> list[tuple[int, int, int]]:
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if len(lines) < 4 or lines[0] != "JASC-PAL":
        return []
    out: list[tuple[int, int, int]] = []
    for line in lines[3:]:
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            r, g, b = (max(0, min(255, int(parts[0]))), max(0, min(255, int(parts[1]))), max(0, min(255, int(parts[2]))))
            out.append((r, g, b))
        except ValueError:
            continue
    return out


def _parse_gba_pal_bytes(data: bytes) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    if len(data) < 2:
        return out
    for i in range(0, len(data) - 1, 2):
        v = data[i] | (data[i + 1] << 8)
        b5 = (v >> 10) & 0x1F
        g5 = (v >> 5) & 0x1F
        r5 = v & 0x1F
        out.append((r5 * 255 // 31, g5 * 255 // 31, b5 * 255 // 31))
    return out


def _read_palette_file(path: Path) -> list[tuple[int, int, int]]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    try:
        text = data.decode("utf-8", errors="ignore")
        if "JASC-PAL" in text:
            parsed = _parse_jasc_pal(text)
            if parsed:
                return parsed
    except Exception:
        pass
    return _parse_gba_pal_bytes(data)


def _load_palette(folder: Path, mode: str) -> tuple[list[tuple[int, int, int]], str]:
    mode = mode.lower()
    candidates = [
        f"{mode}.pal",
        f"{mode}.gbapal",
        f"{mode}_gba.pal",
        f"{mode}_gba.gbapal",
    ]
    search_folders = [folder]
    if folder.parent.name and folder.parent.name != "pokemon":
        search_folders.append(folder.parent)

    for current_folder in search_folders:
        for name in candidates:
            p = current_folder / name
            if not p.exists():
                continue
            pal = _read_palette_file(p)
            if pal:
                return pal, f"{p}:{p.stat().st_mtime}"
    return [], ""


def _load_palette_with_variant(folder: Path, mode: str, variant: str) -> tuple[list[tuple[int, int, int]], str]:
    mode = mode.lower()
    variant = str(variant or "").strip().lower()

    specific_candidates: list[str] = []
    if variant:
        specific_candidates.extend([
            f"{variant}.pal",
            f"{variant}.gbapal",
            f"{variant}_gba.pal",
            f"{variant}_gba.gbapal",
        ])
        head = variant.split("_", 1)[0]
        if mode == "shiny" and head:
            specific_candidates.extend([
                f"{head}_shiny.pal",
                f"{head}_shiny.gbapal",
            ])

    search_folders = [folder]
    if folder.parent.name and folder.parent.name != "pokemon":
        search_folders.append(folder.parent)

    for current_folder in search_folders:
        for name in specific_candidates:
            p = current_folder / name
            if not p.exists():
                continue
            pal = _read_palette_file(p)
            if pal:
                return pal, f"{p}:{p.stat().st_mtime}"

    return _load_palette(folder, mode)


def _nearest_index(color: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> int:
    best = 0
    best_dist = 1 << 30
    r, g, b = color
    for i, (pr, pg, pb) in enumerate(palette):
        d = (r - pr) * (r - pr) + (g - pg) * (g - pg) + (b - pb) * (b - pb)
        if d < best_dist:
            best = i
            best_dist = d
    return best


def _apply_palette_transform_back_indexed(
    rgba: Image.Image,
    source_palette: list[tuple[int, int, int]],
    target_palette: list[tuple[int, int, int]],
) -> Image.Image:
    pal_img = Image.new("P", (1, 1))
    flat: list[int] = []
    for r, g, b in source_palette[:256]:
        flat.extend([r, g, b])
    if len(flat) < 768:
        flat.extend([0] * (768 - len(flat)))
    pal_img.putpalette(flat[:768])

    rgb = rgba.convert("RGB")
    q = rgb.quantize(palette=pal_img, dither=Image.Dither.NONE)
    idx_px = q.load()
    out = rgba.copy()
    out_px = out.load()
    w, h = out.size
    tlen = len(target_palette)
    for y in range(h):
        for x in range(w):
            r, g, b, a = out_px[x, y]
            if a == 0:
                continue
            idx = int(idx_px[x, y])
            if idx >= tlen:
                idx = tlen - 1
            nr, ng, nb = target_palette[idx]
            out_px[x, y] = (nr, ng, nb, a)
    return out


def _apply_palette_transform(
    rgba: Image.Image,
    sprite_folder: Path,
    palette_mode: str,
    kind: str,
    palette_variant: str,
) -> Image.Image:
    mode = palette_mode.lower()
    if mode in {"raw", "none", "off"}:
        return rgba
    target_palette, _ = _load_palette_with_variant(sprite_folder, mode, palette_variant)
    if not target_palette:
        return rgba
    source_palette, _ = _load_palette_with_variant(sprite_folder, "normal", palette_variant)
    if not source_palette:
        source_palette = target_palette

    if kind == "back":
        return _apply_palette_transform_back_indexed(rgba, source_palette, target_palette)

    if mode == "normal":
        return rgba

    px = rgba.load()
    w, h = rgba.size
    tlen = len(target_palette)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            idx = _nearest_index((r, g, b), source_palette)
            if idx >= tlen:
                idx = tlen - 1
            nr, ng, nb = target_palette[idx]
            px[x, y] = (nr, ng, nb, a)
    return rgba


def load_texture_data(
    path: Path,
    kind: str = "generic",
    scale: int = 2,
    frame_index: int = 0,
    palette_mode: str = "normal",
    palette_variant: str = "",
) -> tuple[int, int, list[float]]:
    mtime = path.stat().st_mtime
    normal_pal, normal_stamp = _load_palette_with_variant(path.parent, "normal", palette_variant)
    shiny_pal, shiny_stamp = _load_palette_with_variant(path.parent, "shiny", palette_variant)
    pal_stamp = f"{len(normal_pal)}:{normal_stamp}|{len(shiny_pal)}:{shiny_stamp}"
    key = (f"{path.resolve()}::{kind}::{scale}::{frame_index}::{palette_mode}::{pal_stamp}", mtime)
    if key in _CACHE:
        return _CACHE[key]

    with Image.open(path) as img:
        framed = _crop_frame(img, kind, frame_index)
        if scale > 1:
            framed = framed.resize((framed.width * scale, framed.height * scale), Image.NEAREST)
        rgba = framed.convert("RGBA")
        rgba = _apply_palette_transform(rgba, path.parent, palette_mode, kind, palette_variant)
        w, h = rgba.size
        data = []
        raw = rgba.tobytes()
        for i in range(0, len(raw), 4):
            data.extend([
                raw[i] / 255.0,
                raw[i + 1] / 255.0,
                raw[i + 2] / 255.0,
                raw[i + 3] / 255.0,
            ])
    _CACHE[key] = (w, h, data)
    return _CACHE[key]
