import pytest

from uconfig.errors import ConfigEvalError, ConfigLexError, ConfigParseError
from uconfig.evaluator import Evaluator
from uconfig.parser import parse_text


def translate(text: str):
    consts, root = parse_text(text)
    return Evaluator(consts).eval_root(root)


def test_number_scientific():
    assert translate("1e+3") == 1000
    assert translate("-2.5e-1") == -0.25


def test_string():
    assert translate("'Это строка'") == "Это строка"
    assert translate(r"'a\'b\\c\n'") == "a'b\\c\n"


def test_single_line_comment_is_ignored():
    cfg = """
" comment
x := 1e+0
{ a = $[x] }
"""
    assert translate(cfg) == {"a": 1}


def test_multiline_comment_is_ignored():
    cfg = """
/*
multi
line
*/
{ a = 1e+0 }
"""
    assert translate(cfg) == {"a": 1}


def test_array_basic_and_nested():
    cfg = "( 1e+0, 'x', (2e+0, 3e+0), { k = 4e+0 } )"
    assert translate(cfg) == [1, "x", [2, 3], {"k": 4}]


def test_dict_basic_multiple_entries_no_separators():
    # важное: записи словаря разделяются просто пробелами/переносами строки
    cfg = """
{
a = 1e+0
b = 's'
c = ( 2e+0, 3e+0 )
d = { x = 4e+0 }
}
"""
    assert translate(cfg) == {"a": 1, "b": "s", "c": [2, 3], "d": {"x": 4}}


def test_dict_allows_optional_commas_between_entries():
    cfg = "{ a = 1e+0, b = 2e+0, c = 3e+0 }"
    assert translate(cfg) == {"a": 1, "b": 2, "c": 3}


def test_const_decl_and_ref_simple():
    cfg = """
pi := 3.1415926e+0
{ p = $[pi] }
"""
    out = translate(cfg)
    assert out["p"] == pytest.approx(3.1415926)


def test_const_used_in_nested_structures():
    cfg = """
base := 1e+2
rate := 5e-2
{
price = $[base]
discounted = ( $[base], $[rate], { final = 9.5e+1 } )
}
"""
    assert translate(cfg) == {
        "price": 100,
        "discounted": [100, 0.05, {"final": 95}]
    }


def test_const_can_reference_other_const():
    cfg = """
a := 1e+1
b := ( $[a], 2e+1 )
{ v = $[b] }
"""
    assert translate(cfg) == {"v": [10, 20]}


def test_undefined_const_error():
    cfg = "{ a = $[missing] }"
    with pytest.raises(ConfigEvalError) as e:
        translate(cfg)
    assert "Undefined constant" in str(e.value)


def test_cyclic_const_error():
    cfg = """
a := $[b]
b := $[a]
{ x = $[a] }
"""
    with pytest.raises(ConfigEvalError) as e:
        translate(cfg)
    assert "Cyclic constant reference" in str(e.value)


def test_duplicate_const_decl_error():
    cfg = """
x := 1e+0
x := 2e+0
{ a = 1e+0 }
"""
    with pytest.raises(ConfigParseError) as e:
        translate(cfg)
    assert "Duplicate constant declaration" in str(e.value)


def test_syntax_error_unexpected_token():
    cfg = "{ a = }"
    with pytest.raises(ConfigParseError):
        translate(cfg)


def test_lex_error_unexpected_char():
    cfg = "{ a = @ }"
    with pytest.raises(ConfigLexError):
        translate(cfg)


def test_unterminated_multiline_comment():
    cfg = "/* nope"
    with pytest.raises(ConfigLexError) as e:
        translate(cfg)
    assert "Unterminated multiline comment" in str(e.value)


def test_unterminated_string():
    cfg = "'abc"
    with pytest.raises(ConfigLexError) as e:
        translate(cfg)
    assert "Unterminated string" in str(e.value)
