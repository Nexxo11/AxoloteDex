from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.sprite_loader import resolve_preview_paths


class SpriteLoaderPathTests(unittest.TestCase):
    def test_resolves_unown_style_folder_with_underscore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "graphics/pokemon/unown/c").mkdir(parents=True)
            (root / "graphics/pokemon/unown").mkdir(parents=True, exist_ok=True)
            (root / "graphics/pokemon/bulbasaur").mkdir(parents=True)

            for p in [
                root / "graphics/pokemon/unown/c/front.png",
                root / "graphics/pokemon/unown/c/back.png",
                root / "graphics/pokemon/unown/c/icon.png",
                root / "graphics/pokemon/bulbasaur/front.png",
                root / "graphics/pokemon/bulbasaur/back.png",
                root / "graphics/pokemon/bulbasaur/icon.png",
            ]:
                p.write_bytes(b"\x89PNG\r\n\x1a\n")

            preview = resolve_preview_paths(root, "unown_c")
            self.assertFalse(preview.used_fallback)
            self.assertIn("graphics/pokemon/unown/c/front.png", str(preview.front_path))
            self.assertIn("graphics/pokemon/unown/c/back.png", str(preview.back_path))

    def test_resolves_parent_front_back_for_forme_folder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "graphics/pokemon/arceus").mkdir(parents=True)
            (root / "graphics/pokemon/arceus/ghost").mkdir(parents=True)
            (root / "graphics/pokemon/bulbasaur").mkdir(parents=True)

            (root / "graphics/pokemon/arceus/front.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (root / "graphics/pokemon/arceus/back.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (root / "graphics/pokemon/arceus/ghost/icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            for p in [
                root / "graphics/pokemon/bulbasaur/front.png",
                root / "graphics/pokemon/bulbasaur/back.png",
                root / "graphics/pokemon/bulbasaur/icon.png",
            ]:
                p.write_bytes(b"\x89PNG\r\n\x1a\n")

            preview = resolve_preview_paths(root, "arceus_ghost")
            self.assertFalse(preview.used_fallback)
            self.assertIn("graphics/pokemon/arceus/front.png", str(preview.front_path))
            self.assertIn("graphics/pokemon/arceus/back.png", str(preview.back_path))
            self.assertIn("graphics/pokemon/arceus/ghost/icon.png", str(preview.icon_path))

    def test_detects_variant_for_alcremie_style_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "graphics/pokemon/alcremie/berry").mkdir(parents=True)
            (root / "graphics/pokemon/bulbasaur").mkdir(parents=True)

            for p in [
                root / "graphics/pokemon/alcremie/berry/front.png",
                root / "graphics/pokemon/alcremie/berry/back.png",
                root / "graphics/pokemon/alcremie/berry/icon.png",
                root / "graphics/pokemon/bulbasaur/front.png",
                root / "graphics/pokemon/bulbasaur/back.png",
                root / "graphics/pokemon/bulbasaur/icon.png",
            ]:
                p.write_bytes(b"\x89PNG\r\n\x1a\n")

            preview = resolve_preview_paths(root, "alcremie_berry_lemon_cream")
            self.assertEqual(preview.palette_variant, "berry_lemon_cream")


if __name__ == "__main__":
    unittest.main(verbosity=2)
