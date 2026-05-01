from __future__ import annotations

import time
import unittest
from pathlib import Path
import json

import dearpygui.dearpygui as dpg

from gui.actions import GuiActions
from gui.components import TAGS, build_layout
from gui.state import GuiState, default_editor_data


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "pokeemerald-expansion"


class GuiDryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not PROJECT.exists():
            raise unittest.SkipTest(f"Fixture project missing: {PROJECT}")
        cls.state = GuiState()
        cls.state.editor_data = default_editor_data()
        cls.actions = GuiActions(cls.state, ROOT / "config.json")
        dpg.create_context()
        with dpg.texture_registry(show=False, tag="tex_registry"):
            empty = [0.2, 0.2, 0.2, 1.0] * (32 * 32)
            dpg.add_static_texture(32, 32, empty, tag="tex_front")
            dpg.add_static_texture(32, 32, empty, tag="tex_back")
            dpg.add_static_texture(32, 32, empty, tag="tex_icon")
        build_layout(cls.actions)

    @classmethod
    def tearDownClass(cls) -> None:
        dpg.destroy_context()

    def _load_project_via_button_flow(self) -> None:
        dpg.set_value(TAGS["project_input"], str(PROJECT))
        self.actions.load_project()
        self.assertTrue(self.state.project_loaded)
        self.assertGreater(self.state.last_species_count, 0)

    def _set_common_editor_values(self, constant_name: str, mode: str = "add") -> None:
        dpg.set_value("edit_mode", mode)
        dpg.set_value("constant_name", constant_name)
        dpg.set_value("species_name", "GuiTestmon")
        dpg.set_value("folder_name", "guitestmon")
        dpg.set_value("assets_folder", "")
        dpg.set_value("hp", 60)
        dpg.set_value("attack", 61)
        dpg.set_value("defense", 62)
        dpg.set_value("speed", 63)
        dpg.set_value("sp_attack", 64)
        dpg.set_value("sp_defense", 65)
        dpg.set_value("type1", "TYPE_GRASS")
        dpg.set_value("type2", "TYPE_POISON")
        dpg.set_value("ability1", "ABILITY_OVERGROW")
        dpg.set_value("ability2", "ABILITY_NONE")
        dpg.set_value("ability_hidden", "ABILITY_CHLOROPHYLL")
        dpg.set_value("height", 7)
        dpg.set_value("weight", 69)
        dpg.set_value("gender_ratio", "PERCENT_FEMALE(12.5)")
        dpg.set_value("catch_rate", 45)
        dpg.set_value("exp_yield", 64)
        self.actions.mark_dirty()

    def test_load_project_button(self) -> None:
        self._load_project_via_button_flow()

    def test_generate_dry_run_valid_add(self) -> None:
        self._load_project_via_button_flow()
        unique = f"SPECIES_GUITEST_{int(time.time())}"
        self._set_common_editor_values(unique, mode="add")
        self.actions.generate_dry_run()

        self.assertTrue(self.state.last_change_plan_md.startswith("# Change Plan"))
        self.assertTrue(dpg.is_item_enabled(TAGS["apply_btn"]))
        self.assertTrue(self.state.dry_run_valid)
        self.assertEqual(self.state.last_errors, [])

    def test_generate_dry_run_duplicate_constant(self) -> None:
        self._load_project_via_button_flow()
        self._set_common_editor_values("SPECIES_BULBASAUR", mode="add")
        self.actions.generate_dry_run()

        self.assertFalse(self.state.dry_run_valid)
        self.assertGreater(len(self.state.last_errors), 0)
        self.assertFalse(dpg.is_item_enabled(TAGS["apply_btn"]))

    def test_generate_dry_run_edit_nonexistent(self) -> None:
        self._load_project_via_button_flow()
        self._set_common_editor_values("SPECIES_DOES_NOT_EXIST_ABC", mode="edit")
        self.actions.generate_dry_run()

        self.assertFalse(self.state.dry_run_valid)
        self.assertGreater(len(self.state.last_errors), 0)

    def test_generate_dry_run_invalid_species_name(self) -> None:
        self._load_project_via_button_flow()
        unique = f"SPECIES_GUITEST_BADNAME_{int(time.time())}"
        self._set_common_editor_values(unique, mode="add")
        dpg.set_value("species_name", "")
        self.actions.mark_dirty()
        self.actions.generate_dry_run()

        self.assertFalse(self.state.dry_run_valid)
        self.assertTrue(any(("species_name" in e) or ("nombre vacío" in e) for e in self.state.last_errors))
        self.assertFalse(dpg.is_item_enabled(TAGS["apply_btn"]))

    def test_generate_dry_run_invalid_types(self) -> None:
        self._load_project_via_button_flow()
        unique = f"SPECIES_GUITEST_BADTYPE_{int(time.time())}"
        self._set_common_editor_values(unique, mode="add")
        dpg.set_value("type1", "")
        dpg.set_value("type2", "")
        self.actions.mark_dirty()
        self.actions.generate_dry_run()

        self.assertFalse(self.state.dry_run_valid)
        self.assertTrue(any("types" in e for e in self.state.last_errors))

    def test_generate_dry_run_invalid_abilities(self) -> None:
        self._load_project_via_button_flow()
        unique = f"SPECIES_GUITEST_BADABL_{int(time.time())}"
        self._set_common_editor_values(unique, mode="add")
        dpg.set_value("ability1", "")
        dpg.set_value("ability2", "")
        dpg.set_value("ability_hidden", "")
        self.actions.mark_dirty()
        self.actions.generate_dry_run()

        self.assertFalse(self.state.dry_run_valid)
        self.assertTrue(any("abilities" in e for e in self.state.last_errors))

    def test_change_plan_json_structure(self) -> None:
        self._load_project_via_button_flow()
        unique = f"SPECIES_GUITEST_JSON_{int(time.time())}"
        self._set_common_editor_values(unique, mode="add")
        self.actions.generate_dry_run()

        self.assertTrue(self.state.dry_run_valid)
        plan_path = ROOT / "output" / "change_plan.json"
        self.assertTrue(plan_path.exists())

        data = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertIn("mode", data)
        self.assertIn("constant_name", data)
        self.assertIn("steps", data)
        self.assertIsInstance(data["steps"], list)
        self.assertGreater(len(data["steps"]), 0)

        required_step_keys = {"target_file", "action", "reason", "new_text", "risk_level", "warnings"}
        for step in data["steps"]:
            self.assertTrue(required_step_keys.issubset(set(step.keys())))


if __name__ == "__main__":
    unittest.main(verbosity=2)
