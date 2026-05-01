from __future__ import annotations

import unittest

from core.species_reader import SpeciesReader


class SpeciesReaderDescriptionTests(unittest.TestCase):
    def test_extract_description_compound_string(self) -> None:
        body = (
            '    .description = COMPOUND_STRING(\n'
            '        "Line one.\\n"\n'
            '        "Line two."),\n'
        )
        out = SpeciesReader._extract_description_field(body)
        self.assertEqual(out, "Line one.\nLine two.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
