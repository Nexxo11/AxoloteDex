from __future__ import annotations

import unittest
from pathlib import Path

import dearpygui.dearpygui as dpg

from gui.actions import GuiActions
from gui.state import GuiState


class GuiDescriptionLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = GuiState()
        cls.actions = GuiActions(cls.state, Path("config.json"))
        dpg.create_context()
        with dpg.window():
            dpg.add_input_text(tag="constant_name", default_value="")
            dpg.add_input_text(tag="species_name", default_value="")
            dpg.add_input_text(tag="description", multiline=True, default_value="")

    @classmethod
    def tearDownClass(cls) -> None:
        dpg.destroy_context()

    def setUp(self) -> None:
        dpg.set_value("constant_name", "")
        dpg.set_value("species_name", "")
        dpg.set_value("description", "")

    def test_enforce_truncates_constant_name_to_41(self) -> None:
        dpg.set_value("constant_name", "SPECIES_" + "A" * 60)

        self.actions._enforce_text_limits()

        self.assertEqual(len(str(dpg.get_value("constant_name") or "")), 41)
        self.assertTrue(bool(dpg.get_item_configuration("constant_name").get("readonly")))

    def test_enforce_truncates_species_name_to_12(self) -> None:
        dpg.set_value("species_name", "A" * 30)

        self.actions._enforce_text_limits()

        self.assertEqual(len(str(dpg.get_value("species_name") or "")), 12)
        self.assertTrue(bool(dpg.get_item_configuration("species_name").get("readonly")))

    def test_enforce_truncates_at_limit(self) -> None:
        dpg.set_value("description", "A" * 220)

        self.actions._enforce_text_limits()

        self.assertEqual(len(str(dpg.get_value("description") or "")), 180)
        self.assertTrue(bool(dpg.get_item_configuration("description").get("readonly")))

    def test_enforce_allows_shrinking_after_truncate(self) -> None:
        dpg.set_value("description", "A" * 220)
        self.actions._enforce_text_limits()

        dpg.set_value("description", "B" * 120)
        self.actions._enforce_text_limits()

        self.assertEqual(len(str(dpg.get_value("description") or "")), 120)
        self.assertFalse(bool(dpg.get_item_configuration("description").get("readonly")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
