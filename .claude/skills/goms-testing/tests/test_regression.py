"""Demo-app regression cases — the operator's reference numbers (±0.05 s)."""
import pytest

import klm

NOMINALS = {
    ("M1.2", "G"): 15.1,
    ("M6.1", "D1"): 6.6,
    ("M6.1", "D2"): 15.5,
    ("M6.2", "form"): 19.4,
    ("M6.2", "chat"): 13.8,
}
TOL = 0.05 + 1e-9


@pytest.fixture(scope="module")
def result(request):
    from pathlib import Path
    model = Path(__file__).resolve().parents[1] / "examples" / "demo" / "model.yaml"
    return klm.evaluate_model(klm.load_model(model))


def method(result, task_id, method_id):
    task = next(t for t in result["tasks"] if t["id"] == task_id)
    return next(m for m in task["methods"] if m["id"] == method_id)


@pytest.mark.parametrize("key, expected", NOMINALS.items(), ids=[f"{t}-{m}" for t, m in NOMINALS])
def test_nominal_totals(result, key, expected):
    m = method(result, *key)
    assert abs(m["nominal"] - expected) <= TOL, m["nominal"]
    assert klm.fmt(m["nominal"]) == f"{expected:.1f}"


def test_form_range_15_28(result):
    assert method(result, "M6.2", "form")["range"] == [15, 28]


def test_d1_high_adds_only_the_extra_m(result):
    m = method(result, "M6.1", "D1")
    assert m["high"] - m["nominal"] == pytest.approx(1.35)


def test_chat_free_text_excluded(result):
    m = method(result, "M6.2", "chat")
    assert m["free_text_chars"] == 28
    assert m["nominal_no_free_text"] == pytest.approx(13.82 - 28 * 0.28)
    assert m["r_excluded"] == 1


@pytest.mark.parametrize("task_id, label, expected", [
    ("M6.1", "D2 / D1", 2.33),
    ("M6.2", "form / chat", 1.41),
])
def test_ratios(result, task_id, label, expected):
    task = next(t for t in result["tasks"] if t["id"] == task_id)
    ratio = next(r for r in task["ratios"] if r["label"] == label)
    assert klm.fmt(ratio["ratio"], "0.01") == f"{expected:.2f}"


def test_cli_prints_results_table(demo_model, capsysbinary):
    assert klm.main([str(demo_model), "--md"]) == 0
    out = capsysbinary.readouterr().out.decode("utf-8")
    assert "| M6.2 | form — Form dialog | 19.4 | 18.9 | 23.1 | 15–28 s |" in out
    assert "| M6.1 | D2 / D1 | 2.33 |" in out
    assert "| M6.2 | form / chat | 1.41 |" in out
