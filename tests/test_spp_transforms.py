import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.transforms import epiteto_especifico, filo, observacoes, substrato
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


class FiloTests(unittest.TestCase):
    def test_known_abbreviation_is_expanded(self):
        for sigla, nome in config.FILO_NOME_MAP.items():
            self.assertEqual(filo.expand([sigla, f" {sigla.lower()} "]), [nome, nome])

    def test_missing_stays_none(self):
        self.assertEqual(filo.expand(MISSING_VALUES), [None, None])

    def test_unknown_abbreviation_is_kept_and_reported(self):
        result, printed = _quietly(filo.expand, [" Bryophyta "])
        self.assertEqual(result, ["Bryophyta"])
        self.assertIn("Bryophyta", printed)

    def test_keeps_order_and_length(self):
        siglas = list(config.FILO_NOME_MAP)
        values = [siglas[1], None, siglas[0]]
        self.assertEqual(
            filo.expand(values),
            [config.FILO_NOME_MAP[siglas[1]], None, config.FILO_NOME_MAP[siglas[0]]],
        )


class EpitetoTests(unittest.TestCase):
    def test_genus_abbreviation_is_removed(self):
        self.assertEqual(
            epiteto_especifico.strip_genero_abbreviation(["B. indica", "  Bry.  argenteum "]),
            ["indica", "argenteum"],
        )

    def test_epithet_without_abbreviation_is_kept(self):
        self.assertEqual(epiteto_especifico.strip_genero_abbreviation([" indica "]), ["indica"])

    def test_any_first_token_ending_in_dot_is_removed(self):
        # A regra olha só a forma do primeiro token, não se ele é um gênero
        self.assertEqual(
            epiteto_especifico.strip_genero_abbreviation(["sp.", "cf. indica"]),
            ["", "indica"],
        )

    def test_missing_stays_none(self):
        self.assertEqual(epiteto_especifico.strip_genero_abbreviation(MISSING_VALUES), [None, None])

    def test_value_and_list_versions_agree(self):
        values = ["B. indica", None, "indica"]
        self.assertEqual(
            epiteto_especifico.strip_genero_abbreviation(values),
            [epiteto_especifico.strip_genero_abbreviation_from_value(v) for v in values],
        )


class SubstratoTests(unittest.TestCase):
    def test_multivalued_is_split_and_expanded(self):
        (first, first_name), (second, second_name) = list(config.SUBSTRATO_NOME_MAP.items())[:2]
        self.assertEqual(
            substrato.expand_multivalued([f"{first} + {second.lower()}"]),
            [[first_name, second_name]],
        )

    def test_repeated_name_appears_once_in_first_order(self):
        (first, first_name), (second, second_name) = list(config.SUBSTRATO_NOME_MAP.items())[:2]
        self.assertEqual(
            substrato.expand_multivalued([f"{second}+{first}+{second}"]),
            [[second_name, first_name]],
        )

    def test_missing_and_empty_become_empty_list(self):
        self.assertEqual(substrato.expand_multivalued(MISSING_VALUES + ["", "  ", "+"]), [[]] * 5)

    def test_unknown_abbreviation_is_kept_and_reported(self):
        first, first_name = next(iter(config.SUBSTRATO_NOME_MAP.items()))
        result, printed = _quietly(substrato.expand_multivalued, [f"{first}+XYZ"])
        self.assertEqual(result, [[first_name, "XYZ"]])
        self.assertIn("'XYZ'", printed)


class ObservacoesTests(unittest.TestCase):
    def test_multivalued_is_split_and_trimmed(self):
        self.assertEqual(
            observacoes.split_multivalued([" com esporófito ; acrocárpico "]),
            [["com esporófito", "acrocárpico"]],
        )

    def test_repeated_comment_appears_once_in_first_order(self):
        self.assertEqual(
            observacoes.split_multivalued(["b; a; b"]),
            [["b", "a"]],
        )

    def test_missing_and_empty_become_empty_list(self):
        self.assertEqual(observacoes.split_multivalued(MISSING_VALUES + ["", "  ", ";;"]), [[]] * 5)


if __name__ == "__main__":
    unittest.main()
