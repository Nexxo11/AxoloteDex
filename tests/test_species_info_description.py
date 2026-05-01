from __future__ import annotations

import unittest

from core.species_editor import SpeciesEditor


class SpeciesInfoDescriptionTests(unittest.TestCase):
    def test_build_species_info_uses_custom_description_lines(self) -> None:
        editor = SpeciesEditor.__new__(SpeciesEditor)
        data = {
            "constant_name": "SPECIES_TESTMON",
            "species_name": "Testmon",
            "description": "Linea uno\nLinea dos",
            "base_stats": {
                "hp": 50,
                "attack": 50,
                "defense": 50,
                "speed": 50,
                "sp_attack": 50,
                "sp_defense": 50,
            },
            "types": ["TYPE_NORMAL"],
            "abilities": ["ABILITY_NONE", "ABILITY_NONE", "ABILITY_NONE"],
            "height": 10,
            "weight": 100,
        }

        block = editor._build_species_info_block(data)
        self.assertIn('.description = COMPOUND_STRING(', block)
        self.assertIn('"Linea uno\\n"', block)
        self.assertIn('"Linea dos"),', block)

    def test_build_species_info_falls_back_when_description_empty(self) -> None:
        editor = SpeciesEditor.__new__(SpeciesEditor)
        data = {
            "constant_name": "SPECIES_TESTMON",
            "species_name": "Testmon",
            "description": "",
            "base_stats": {
                "hp": 50,
                "attack": 50,
                "defense": 50,
                "speed": 50,
                "sp_attack": 50,
                "sp_defense": 50,
            },
            "types": ["TYPE_NORMAL"],
            "abilities": ["ABILITY_NONE", "ABILITY_NONE", "ABILITY_NONE"],
            "height": 10,
            "weight": 100,
        }

        block = editor._build_species_info_block(data)
        self.assertIn('"A custom species added by tool.\\n"', block)
        self.assertIn('"Replace this description later."),', block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
