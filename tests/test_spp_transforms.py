import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.transforms import epithet, phylum, remarks, substrate
from scripts.transforms.missing import is_missing

MISSING_VALUES = [None, float("nan")]


def _quietly(function, *args):
    """Chama a função e devolve (resultado, texto impresso), para os avisos de sigla."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = function(*args)
    return result, out.getvalue()


class MissingTests(unittest.TestCase):
    def test_none_and_nan_are_missing(self):
        for value in MISSING_VALUES:
            self.assertTrue(is_missing(value), repr(value))

    def test_empty_text_and_zero_are_not_missing(self):
        # Texto vazio não é ausência aqui: cada transform decide o que fazer com ele
        for value in ["", " ", 0, 0.0, "nan"]:
            self.assertFalse(is_missing(value), repr(value))


class PhylumTests(unittest.TestCase):
    def test_known_abbreviation_is_expanded(self):
        for abbreviation, name in config.PHYLUM_NAME_MAP.items():
            self.assertEqual(phylum.expand([abbreviation, f" {abbreviation.lower()} "]), [name, name])

    def test_missing_stays_none(self):
        self.assertEqual(phylum.expand(MISSING_VALUES), [None, None])

    def test_unknown_abbreviation_is_kept_and_reported(self):
        result, printed = _quietly(phylum.expand, [" Bryophyta "])
        self.assertEqual(result, ["Bryophyta"])
        self.assertIn("Bryophyta", printed)

    def test_keeps_order_and_length(self):
        abbreviations = list(config.PHYLUM_NAME_MAP)
        values = [abbreviations[1], None, abbreviations[0]]
        self.assertEqual(
            phylum.expand(values),
            [config.PHYLUM_NAME_MAP[abbreviations[1]], None, config.PHYLUM_NAME_MAP[abbreviations[0]]],
        )


class EpithetTests(unittest.TestCase):
    # split_epithet devolve (epíteto, qualificador de identificação) por valor

    def test_genus_abbreviation_is_removed(self):
        self.assertEqual(
            epithet.split_epithet(["B. indica", "  Bry.  argenteum "]),
            [("indica", None), ("argenteum", None)],
        )

    def test_epithet_without_abbreviation_is_kept(self):
        self.assertEqual(epithet.split_epithet([" indica "]), [("indica", None)])

    def test_any_first_token_ending_in_dot_is_removed(self):
        # A regra olha só a forma do primeiro token, não se ele é um gênero
        self.assertEqual(epithet.split_epithet(["sp.", "G."]), [(None, None), (None, None)])

    def test_sp_after_genus_abbreviation_is_genus_only(self):
        # ADR-0003: "G. sp." é gênero-só, sem epíteto, e não espécie de epíteto "sp."
        self.assertEqual(
            epithet.split_epithet(["G. sp.", "G. sp", "G. cf. sp."]),
            [(None, None), (None, None), (None, "cf.")],
        )

    def test_epithet_starting_with_sp_is_kept(self):
        self.assertEqual(epithet.split_epithet(["G. spinosa"]), [("spinosa", None)])

    def test_qualifier_after_genus_abbreviation_goes_to_the_record(self):
        self.assertEqual(
            epithet.split_epithet(["L. cf. flava", "L. aff. flava"]),
            [("flava", "cf."), ("flava", "aff.")],
        )

    def test_qualifier_without_dot_is_normalized(self):
        self.assertEqual(epithet.split_epithet(["L. cf flava"]), [("flava", "cf.")])

    def test_qualifier_without_genus_abbreviation_is_not_taken_as_abbreviation(self):
        self.assertEqual(epithet.split_epithet(["cf. indica"]), [("indica", "cf.")])

    def test_qualifier_alone_leaves_no_epithet(self):
        # Caso degenerado: o qualificador nunca vira epíteto; sobra só o gênero da linha
        self.assertEqual(
            epithet.split_epithet(["L. cf.", "aff."]),
            [(None, "cf."), (None, "aff.")],
        )

    def test_word_starting_with_qualifier_is_an_epithet(self):
        self.assertEqual(epithet.split_epithet(["B. affinis"]), [("affinis", None)])

    def test_missing_stays_none(self):
        self.assertEqual(epithet.split_epithet(MISSING_VALUES), [(None, None), (None, None)])

    def test_value_and_list_versions_agree(self):
        values = ["B. indica", None, "indica", "L. cf. flava"]
        self.assertEqual(
            epithet.split_epithet(values),
            [epithet.split_epithet_from_value(v) for v in values],
        )


class SubstrateTests(unittest.TestCase):
    def test_multivalued_is_split_and_expanded(self):
        (first, first_name), (second, second_name) = list(config.SUBSTRATE_NAME_MAP.items())[:2]
        self.assertEqual(
            substrate.expand_multivalued([f"{first} + {second.lower()}"]),
            [[first_name, second_name]],
        )

    def test_repeated_name_appears_once_in_first_order(self):
        (first, first_name), (second, second_name) = list(config.SUBSTRATE_NAME_MAP.items())[:2]
        self.assertEqual(
            substrate.expand_multivalued([f"{second}+{first}+{second}"]),
            [[second_name, first_name]],
        )

    def test_missing_and_empty_become_empty_list(self):
        self.assertEqual(substrate.expand_multivalued(MISSING_VALUES + ["", "  ", "+"]), [[]] * 5)

    def test_unknown_abbreviation_is_kept_and_reported(self):
        first, first_name = next(iter(config.SUBSTRATE_NAME_MAP.items()))
        result, printed = _quietly(substrate.expand_multivalued, [f"{first}+XYZ"])
        self.assertEqual(result, [[first_name, "XYZ"]])
        self.assertIn("'XYZ'", printed)


class RemarksTests(unittest.TestCase):
    def test_multivalued_is_split_and_trimmed(self):
        self.assertEqual(
            remarks.split_multivalued([" com esporófito ; acrocárpico "]),
            [["com esporófito", "acrocárpico"]],
        )

    def test_repeated_comment_appears_once_in_first_order(self):
        self.assertEqual(
            remarks.split_multivalued(["b; a; b"]),
            [["b", "a"]],
        )

    def test_missing_and_empty_become_empty_list(self):
        self.assertEqual(remarks.split_multivalued(MISSING_VALUES + ["", "  ", ";;"]), [[]] * 5)


if __name__ == "__main__":
    unittest.main()
