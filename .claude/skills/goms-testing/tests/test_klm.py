import json

import pytest
import yaml

import klm
from conftest import one_method_model


# ---------------------------------------------------------------- parsing
@pytest.mark.parametrize("ops, expected", [
    ("M P BB", [("M", 1), ("P", 1), ("B", 2)]),
    ("H 11K", [("H", 1), ("K", 11)]),
    ("K", [("K", 1)]),
    ("1K", [("K", 1)]),
    ("BBBBBB", [("B", 6)]),
    ("P B P B", [("P", 1), ("B", 1), ("P", 1), ("B", 1)]),
    ("S R", [("S", 1), ("R", 1)]),
    ("  M   K  ", [("M", 1), ("K", 1)]),
    ("", []),
    (None, []),
])
def test_parse_ops(ops, expected):
    assert klm.parse_ops(ops) == expected


@pytest.mark.parametrize("bad", ["X", "m", "0K", "KK", "P,", "BBK", "2P", "M|P", "K11", "|"])
def test_bad_token_rejected_with_clear_error(bad):
    with pytest.raises(klm.TokenError) as exc:
        klm.parse_ops(f"M {bad}", where="T1 step 3")
    msg = str(exc.value)
    assert "T1 step 3" in msg
    assert ("unknown token" in msg and repr(bad) in msg) or "must be >= 1" in msg
    if "unknown token" in msg:
        assert "allowed tokens" in msg


def test_non_string_ops_rejected():
    with pytest.raises(klm.TokenError):
        klm.parse_ops(["M", "P"])


# ---------------------------------------------------------------- totals
def evaluate(model, **kw):
    return klm.evaluate_model(model, klm.load_table(kw.pop("table", None)), **kw)


def only_method(result):
    return result["tasks"][0]["methods"][0]


def test_operator_table_defaults():
    m = only_method(evaluate(one_method_model("M P BB H K")))
    assert m["nominal"] == pytest.approx(1.35 + 1.10 + 0.20 + 0.40 + 0.28)


def test_scroll_variants_and_range():
    # nominal uses S 1.0, low S 0.5, high S 2.0 plus ops_extra.
    m = only_method(evaluate(one_method_model(["M P BB", "S"], ["", "M"])))
    assert m["nominal"] == pytest.approx(2.65 + 1.0)
    assert m["low"] == pytest.approx(2.65 + 0.5)
    assert m["high"] == pytest.approx(2.65 + 2.0 + 1.35)
    # floor(3.15 * 0.8 = 2.52) = 2 ; ceil(6.0 * 1.2 = 7.2) = 8
    assert m["range"] == [2, 8]


def test_range_exact_integer_edges_are_not_pushed_by_float_noise():
    # 10 x P at 1.0 s = 10.0 s; 10 * 1.2 = 12.000000000000002 in floats -> must stay 12.
    m = only_method(evaluate(one_method_model("P " * 10), table="P=1.0"))
    assert m["high"] == pytest.approx(10.0)
    assert m["range"] == [8, 12]


def test_r_is_always_excluded():
    m = only_method(evaluate(one_method_model("M R P BB")))
    assert m["nominal"] == pytest.approx(2.65)
    assert m["high"] == pytest.approx(2.65)
    assert m["r_excluded"] == 1


def test_free_text_runs():
    m = only_method(evaluate(one_method_model(["H 28K", "H 19K"])))
    assert m["free_text_chars"] == 28
    assert m["nominal_no_free_text"] == pytest.approx(m["nominal"] - 28 * 0.28)
    m = only_method(evaluate(one_method_model(["H 28K", "H 19K"]), free_text_min=10))
    assert m["free_text_chars"] == 47


def test_free_text_chars_mismatch_warns():
    result = evaluate(one_method_model("H 28K", free_text_chars=30))
    assert any("free_text_chars=30" in w for w in result["warnings"])


def test_operator_counts_and_cumulative():
    m = only_method(evaluate(one_method_model(["M P BB", "H 6K", "H M P BB"], ["", "", "M"])))
    assert m["counts_low"] == {"M": 2, "P": 2, "B": 4, "H": 2, "K": 6, "S": 0, "R": 0}
    assert m["counts_high"]["M"] == 3
    cums = [s["cum_nominal"] for s in m["steps"]]
    assert cums == pytest.approx([2.65, 2.65 + 2.08, 2.65 + 2.08 + 3.05])
    assert m["steps"][-1]["cum_high"] == pytest.approx(m["high"])


def test_ratios_within_task():
    model = one_method_model("M P BB")
    model["tasks"][0]["methods"].append(
        {"id": "B", "steps": [{"label": "x", "ops_low": "M P BB M P BB", "status": "verified"}]})
    ratios = evaluate(model)["tasks"][0]["ratios"]
    assert len(ratios) == 1
    assert ratios[0]["label"] == "B / A"
    assert ratios[0]["ratio"] == pytest.approx(2.0)


def test_three_methods_give_three_pairs():
    model = one_method_model("M")
    for mid, ops in (("B", "M M"), ("C", "M M M")):
        model["tasks"][0]["methods"].append(
            {"id": mid, "steps": [{"label": "x", "ops_low": ops, "status": "verified"}]})
    assert len(evaluate(model)["tasks"][0]["ratios"]) == 3


def test_ranking_slowest_first():
    model = one_method_model("M")
    model["tasks"].append({"id": "T2", "methods": [
        {"id": "Z", "steps": [{"label": "x", "ops_low": "M M M", "status": "verified"}]}]})
    ranking = evaluate(model)["ranking"]
    assert [r["task"] for r in ranking] == ["T2", "T1"]


# ---------------------------------------------------------------- table override
def test_table_inline_override():
    t = klm.load_table("P=1.2, S_high=3, M=1.2")
    assert t["P"] == 1.2 and t["M"] == 1.2 and t["S"]["high"] == 3.0
    assert t["K"] == 0.28  # untouched


def test_table_file_override(tmp_path):
    f = tmp_path / "table.yaml"
    f.write_text("K: 0.2\nS: {low: 0.3, nominal: 0.8, high: 1.5}\n", encoding="utf-8")
    t = klm.load_table(str(f))
    assert t["K"] == 0.2 and t["S"] == {"low": 0.3, "nominal": 0.8, "high": 1.5}


@pytest.mark.parametrize("spec", ["X=1", "R=0.5", "P_low=1", "S_max=2", "P"])
def test_table_bad_override(spec):
    with pytest.raises(klm.ModelError):
        klm.load_table(spec)


def test_default_table_not_mutated():
    klm.load_table("P=9")
    assert klm.DEFAULT_TABLE["P"] == 1.10


# ---------------------------------------------------------------- validation
def test_bad_status_rejected():
    with pytest.raises(klm.ModelError, match="status 'done'"):
        klm.validate_model(one_method_model("M", status="done"))


def test_routine_task_without_methods_rejected():
    with pytest.raises(klm.ModelError, match="at least one method"):
        klm.validate_model({"tasks": [{"id": "T", "triage": "routine", "methods": []}]})


def test_discovery_task_without_methods_allowed():
    model = one_method_model("M")
    model["tasks"].append({"id": "D", "title": "Explain the chart", "triage": "discovery"})
    klm.validate_model(model)
    md = klm.render_md(evaluate(model))
    assert "Not modelled (test only)" in md and "D Explain the chart" in md


def test_bad_token_in_model_names_location():
    with pytest.raises(klm.TokenError, match=r"method A step 1 ops_extra"):
        klm.validate_model(one_method_model("M", ops_extra="Q"))


# ---------------------------------------------------------------- display + CLI
@pytest.mark.parametrize("x, places, out", [
    (15.45, "0.1", "15.5"), (15.12, "0.1", "15.1"), (6.63, "0.1", "6.6"),
    (2.3303, "0.01", "2.33"), (1.4067, "0.01", "1.41"), (0.125, "0.01", "0.13"),
])
def test_fmt_half_up(x, places, out):
    assert klm.fmt(x, places) == out


def write_model(tmp_path, model):
    p = tmp_path / "model.yaml"
    p.write_text(yaml.safe_dump(model, allow_unicode=True), encoding="utf-8")
    return p


def test_cli_md(tmp_path, capsysbinary):
    p = write_model(tmp_path, one_method_model("M P BB"))
    assert klm.main([str(p), "--md"]) == 0
    out = capsysbinary.readouterr().out.decode("utf-8")
    assert "| Rank | Task | Method | Nominal (s)" in out
    assert "Rankings and method ratios matter more than absolute seconds" in out
    assert "ASSUMPTION" in out


def test_cli_json(tmp_path, capsysbinary):
    p = write_model(tmp_path, one_method_model("M P BB"))
    assert klm.main([str(p), "--json"]) == 0
    data = json.loads(capsysbinary.readouterr().out.decode("utf-8"))
    assert data["tasks"][0]["methods"][0]["nominal"] == 2.65
    assert data["disclaimer"].startswith("GOMS/KLM")


def test_cli_bad_token_exit_2(tmp_path, capsys):
    p = write_model(tmp_path, one_method_model("M P XX"))
    assert klm.main([str(p)]) == 2
    err = capsys.readouterr().err
    assert "unknown token 'XX'" in err and "allowed tokens" in err


def test_cli_missing_file(tmp_path, capsys):
    assert klm.main([str(tmp_path / "nope.yaml")]) == 2
    assert "file not found" in capsys.readouterr().err
