from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.change_plan import ChangePlan, ChangeStep
from core.species_editor import SpeciesEditor


class SpeciesEditorSafetyTests(unittest.TestCase):
    def test_apply_insert_keeps_boundaries(self) -> None:
        text = "A\nMARK\nB\n"
        step = ChangeStep(
            target_file="x.h",
            action="insert",
            reason="t",
            new_text="NEW1\nNEW2",
            insert_before="MARK",
        )
        out = SpeciesEditor._apply_insert(text, step)
        self.assertIn("A\n\nNEW1\nNEW2\n\nMARK\nB", out)

    def test_preprocessor_balance_detects_errors(self) -> None:
        with self.assertRaises(ValueError):
            SpeciesEditor._assert_preprocessor_balance(Path("x.h"), "#endif //oops\n")

    def test_find_graphics_symbol_lines(self) -> None:
        txt = "const u8 gMonIcon_Testmon[] = X;\nconst u8 foo[] = Y;\n"
        lines = SpeciesEditor._find_graphics_symbol_lines(txt, "Testmon")
        self.assertEqual(len(lines), 1)
        self.assertIn("gMonIcon_Testmon", lines[0])

    def test_post_apply_sanity_delete_detects_residuals(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "include/constants").mkdir(parents=True)
            (root / "src/data/graphics").mkdir(parents=True)
            (root / "graphics/pokemon/testmon").mkdir(parents=True)
            (root / "include/constants/species.h").write_text("#define SPECIES_TESTMON 999\n", encoding="utf-8")
            (root / "src/data/graphics/pokemon.h").write_text("const u8 gMonIcon_Testmon[] = X;\n", encoding="utf-8")

            editor = SpeciesEditor.__new__(SpeciesEditor)
            editor.project_root = root

            plan = ChangePlan(mode="delete", constant_name="SPECIES_TESTMON", project_root=str(root))
            plan.add_step(ChangeStep(target_file="include/constants/species.h", action="update", reason="r", new_text=""))

            with self.assertRaises(ValueError):
                editor._post_apply_sanity_checks(plan, {"constant_name": "SPECIES_TESTMON", "folder_name": "testmon"})

    def test_update_species_info_evolutions_replaces_existing(self) -> None:
        old_block = (
            "    [SPECIES_FOO] =\n"
            "    {\n"
            "        .types = MON_TYPES(TYPE_GRASS),\n"
            "        .evolutions = EVOLUTION({EVO_LEVEL, 16, SPECIES_BAR}),\n"
            "        .levelUpLearnset = sFooLevelUpLearnset,\n"
            "    },\n"
        )
        new_evos = [
            {"method": "EVO_LEVEL", "param": "20", "target": "SPECIES_BAZ"},
            {"method": "EVO_ITEM", "param": "ITEM_FIRE_STONE", "target": "SPECIES_QUX"},
        ]
        out = SpeciesEditor._update_species_info_evolutions(old_block, new_evos)
        self.assertIn(".evolutions = EVOLUTION({EVO_LEVEL, 20, SPECIES_BAZ}, {EVO_ITEM, ITEM_FIRE_STONE, SPECIES_QUX}),", out)
        self.assertIn(".levelUpLearnset = sFooLevelUpLearnset,", out)
        self.assertNotIn("SPECIES_BAR", out)

    def test_update_species_info_evolutions_removes_when_empty(self) -> None:
        old_block = (
            "    [SPECIES_FOO] =\n"
            "    {\n"
            "        .types = MON_TYPES(TYPE_GRASS),\n"
            "        .evolutions = EVOLUTION({EVO_LEVEL, 16, SPECIES_BAR}),\n"
            "        .levelUpLearnset = sFooLevelUpLearnset,\n"
            "    },\n"
        )
        out = SpeciesEditor._update_species_info_evolutions(old_block, [])
        self.assertNotIn(".evolutions = EVOLUTION(", out)
        self.assertIn(".levelUpLearnset = sFooLevelUpLearnset,", out)

    def test_delete_plan_blocks_external_references(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "include/constants").mkdir(parents=True)
            (root / "src/data/graphics").mkdir(parents=True)
            (root / "src/data/pokemon").mkdir(parents=True)
            (root / "graphics/pokemon/glimmora_mega").mkdir(parents=True)

            (root / "include/constants/species.h").write_text(
                "#define SPECIES_BULBASAUR                              1\n"
                "#define SPECIES_GLIMMORA_MEGA                          1000\n"
                "#define SPECIES_EGG                                     (SPECIES_GLIMMORA_MEGA + 1)\n",
                encoding="utf-8",
            )
            (root / "src/data/graphics/pokemon.h").write_text("", encoding="utf-8")
            (root / "src/data/pokemon/form_species_tables.h").write_text(
                "static const u16 sX[] = { SPECIES_GLIMMORA_MEGA };\n",
                encoding="utf-8",
            )

            editor = SpeciesEditor.__new__(SpeciesEditor)
            editor.project_root = root
            editor.read_result = SimpleNamespace(project=SimpleNamespace(family_files=[]), species=[])
            editor.species_by_constant = {
                "SPECIES_GLIMMORA_MEGA": SimpleNamespace(folder_name="glimmora_mega")
            }

            plan = ChangePlan(mode="delete", constant_name="SPECIES_GLIMMORA_MEGA", project_root=str(root))
            data = {"constant_name": "SPECIES_GLIMMORA_MEGA", "folder_name": "glimmora_mega"}
            out = editor._build_delete_plan(plan, data, root / "include/constants/species.h", root / "src/data/graphics/pokemon.h")

            self.assertTrue(out.is_blocked)
            self.assertTrue(any("referencias externas" in err for err in out.errors))
            self.assertTrue(any("form_species_tables.h" in err for err in out.errors))

    def test_rewrite_species_h_for_add_delete_keeps_valid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "include/constants").mkdir(parents=True)
            species_h = root / "include/constants/species.h"
            species_h.write_text(
                "#define SPECIES_NONE                                    0\n"
                "#define SPECIES_TEST_A                                  1\n"
                "#define SPECIES_EGG                                     (SPECIES_TEST_A + 1)\n",
                encoding="utf-8",
            )

            editor = SpeciesEditor.__new__(SpeciesEditor)
            old_text, added_text = editor._rewrite_species_h_for_add(species_h, "SPECIES_TEST_B")
            self.assertIn("#define SPECIES_TEST_B", added_text)
            self.assertIn("#define SPECIES_EGG                                     (SPECIES_TEST_B + 1)", added_text)
            self.assertNotIn("#define SPECIES_TEST_B                                  2#define SPECIES_EGG", added_text)

            _, deleted_text = SpeciesEditor._rewrite_species_h_for_delete(added_text, "SPECIES_TEST_B")
            self.assertNotIn("#define SPECIES_TEST_B", deleted_text)
            self.assertIn("#define SPECIES_EGG                                     (SPECIES_TEST_A + 1)", deleted_text)
            self.assertNotIn("1#define SPECIES_EGG", deleted_text)
            self.assertTrue(deleted_text.endswith("\n"))

    def test_delete_plan_replaces_trainer_refs_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "include/constants").mkdir(parents=True)
            (root / "src/data/graphics").mkdir(parents=True)
            (root / "src/data/pokemon").mkdir(parents=True)
            (root / "graphics/pokemon/glimmora_mega").mkdir(parents=True)

            (root / "include/constants/species.h").write_text(
                "#define SPECIES_GLIMMORA_MEGA                          1000\n"
                "#define SPECIES_BULBASAUR                              1\n"
                "#define SPECIES_CHARMANDER                             4\n"
                "#define SPECIES_EGG                                     (SPECIES_GLIMMORA_MEGA + 1)\n",
                encoding="utf-8",
            )
            (root / "src/data/graphics/pokemon.h").write_text("", encoding="utf-8")
            (root / "src/data/pokemon/trainer_parties.h").write_text(
                "{ .species = SPECIES_GLIMMORA_MEGA },\n{ .species = SPECIES_GLIMMORA_MEGA },\n",
                encoding="utf-8",
            )

            editor = SpeciesEditor.__new__(SpeciesEditor)
            editor.project_root = root
            editor.read_result = SimpleNamespace(project=SimpleNamespace(family_files=[]), species=[])
            editor.species_by_constant = {
                "SPECIES_GLIMMORA_MEGA": SimpleNamespace(folder_name="glimmora_mega"),
                "SPECIES_BULBASAUR": SimpleNamespace(folder_name="bulbasaur"),
                "SPECIES_CHARMANDER": SimpleNamespace(folder_name="charmander"),
            }

            plan = ChangePlan(mode="delete", constant_name="SPECIES_GLIMMORA_MEGA", project_root=str(root))
            data = {
                "constant_name": "SPECIES_GLIMMORA_MEGA",
                "folder_name": "glimmora_mega",
                "replace_in_use_trainers_random": True,
            }
            out = editor._build_delete_plan(plan, data, root / "include/constants/species.h", root / "src/data/graphics/pokemon.h")

            self.assertFalse(out.is_blocked)
            trainer_steps = [s for s in out.steps if s.target_file.endswith("trainer_parties.h")]
            self.assertEqual(len(trainer_steps), 1)
            self.assertNotIn("SPECIES_GLIMMORA_MEGA", trainer_steps[0].new_text)

    def test_delete_plan_replaces_non_trainer_refs_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "include/constants").mkdir(parents=True)
            (root / "src/data/graphics").mkdir(parents=True)
            (root / "src/data/pokemon").mkdir(parents=True)
            (root / "graphics/pokemon/glimmora_mega").mkdir(parents=True)

            (root / "include/constants/species.h").write_text(
                "#define SPECIES_GLIMMORA_MEGA                          1000\n"
                "#define SPECIES_BULBASAUR                              1\n"
                "#define SPECIES_CHARMANDER                             4\n"
                "#define SPECIES_EGG                                     (SPECIES_GLIMMORA_MEGA + 1)\n",
                encoding="utf-8",
            )
            (root / "src/data/graphics/pokemon.h").write_text("", encoding="utf-8")
            (root / "src/data/pokemon/form_species_tables.h").write_text(
                "static const u16 sX[] = { SPECIES_GLIMMORA_MEGA };\n",
                encoding="utf-8",
            )

            editor = SpeciesEditor.__new__(SpeciesEditor)
            editor.project_root = root
            editor.read_result = SimpleNamespace(project=SimpleNamespace(family_files=[]), species=[])
            editor.species_by_constant = {
                "SPECIES_GLIMMORA_MEGA": SimpleNamespace(folder_name="glimmora_mega"),
                "SPECIES_BULBASAUR": SimpleNamespace(folder_name="bulbasaur"),
                "SPECIES_CHARMANDER": SimpleNamespace(folder_name="charmander"),
            }

            plan = ChangePlan(mode="delete", constant_name="SPECIES_GLIMMORA_MEGA", project_root=str(root))
            data = {
                "constant_name": "SPECIES_GLIMMORA_MEGA",
                "folder_name": "glimmora_mega",
                "replace_in_use_random": True,
            }
            out = editor._build_delete_plan(plan, data, root / "include/constants/species.h", root / "src/data/graphics/pokemon.h")

            self.assertFalse(out.is_blocked)
            steps = [s for s in out.steps if s.target_file.endswith("form_species_tables.h")]
            self.assertEqual(len(steps), 1)
            self.assertNotIn("SPECIES_GLIMMORA_MEGA", steps[0].new_text)

    def test_delete_plan_replaces_easy_chat_macro_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "include/constants").mkdir(parents=True)
            (root / "src/data/graphics").mkdir(parents=True)
            (root / "src/data/easy_chat").mkdir(parents=True)
            (root / "graphics/pokemon/charizard").mkdir(parents=True)

            (root / "include/constants/species.h").write_text(
                "#define SPECIES_BULBASAUR                              1\n"
                "#define SPECIES_CHARIZARD                              6\n"
                "#define SPECIES_EGG                                     (SPECIES_CHARIZARD + 1)\n",
                encoding="utf-8",
            )
            (root / "src/data/graphics/pokemon.h").write_text("", encoding="utf-8")
            (root / "src/data/easy_chat/easy_chat_words_by_letter.h").write_text(
                "EC_POKEMON_NATIONAL(CHARIZARD),\n",
                encoding="utf-8",
            )

            editor = SpeciesEditor.__new__(SpeciesEditor)
            editor.project_root = root
            editor.read_result = SimpleNamespace(project=SimpleNamespace(family_files=[]), species=[])
            editor.species_by_constant = {
                "SPECIES_CHARIZARD": SimpleNamespace(folder_name="charizard"),
                "SPECIES_BULBASAUR": SimpleNamespace(folder_name="bulbasaur"),
            }

            plan = ChangePlan(mode="delete", constant_name="SPECIES_CHARIZARD", project_root=str(root))
            data = {
                "constant_name": "SPECIES_CHARIZARD",
                "folder_name": "charizard",
                "delete_mode": "replace+delete",
            }
            out = editor._build_delete_plan(plan, data, root / "include/constants/species.h", root / "src/data/graphics/pokemon.h")

            self.assertFalse(out.is_blocked)
            steps = [s for s in out.steps if s.target_file.endswith("easy_chat_words_by_letter.h")]
            self.assertEqual(len(steps), 1)
            self.assertNotIn("EC_POKEMON_NATIONAL(CHARIZARD)", steps[0].new_text)

    def test_delete_plan_force_delete_allows_external_refs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "include/constants").mkdir(parents=True)
            (root / "src/data/graphics").mkdir(parents=True)
            (root / "src/data/pokemon").mkdir(parents=True)
            (root / "graphics/pokemon/glimmora_mega").mkdir(parents=True)

            (root / "include/constants/species.h").write_text(
                "#define SPECIES_BULBASAUR                              1\n"
                "#define SPECIES_GLIMMORA_MEGA                          1000\n"
                "#define SPECIES_EGG                                     (SPECIES_GLIMMORA_MEGA + 1)\n",
                encoding="utf-8",
            )
            (root / "src/data/graphics/pokemon.h").write_text("", encoding="utf-8")
            (root / "src/data/pokemon/form_species_tables.h").write_text(
                "static const u16 sX[] = { SPECIES_GLIMMORA_MEGA };\n",
                encoding="utf-8",
            )

            editor = SpeciesEditor.__new__(SpeciesEditor)
            editor.project_root = root
            editor.read_result = SimpleNamespace(project=SimpleNamespace(family_files=[]), species=[])
            editor.species_by_constant = {
                "SPECIES_GLIMMORA_MEGA": SimpleNamespace(folder_name="glimmora_mega")
            }

            plan = ChangePlan(mode="delete", constant_name="SPECIES_GLIMMORA_MEGA", project_root=str(root))
            data = {
                "constant_name": "SPECIES_GLIMMORA_MEGA",
                "folder_name": "glimmora_mega",
                "delete_mode": "force-delete",
            }
            out = editor._build_delete_plan(plan, data, root / "include/constants/species.h", root / "src/data/graphics/pokemon.h")
            self.assertFalse(out.is_blocked)
            self.assertTrue(any("force-delete" in w for w in out.warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
