"""cogulator_export.py and sheet.py stay consistent with klm.py."""
import re

import pytest
import yaml

import cogulator_export
import klm
import sheet

MS = re.compile(r"\((\d+) ms\)$")


@pytest.fixture(scope="module")
def model():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "examples" / "demo" / "model.yaml"
    return klm.load_model(path)


@pytest.fixture(scope="module")
def result(model):
    return klm.evaluate_model(model)


@pytest.mark.parametrize("variant, key", [("low", "nominal"), ("high", "high")])
def test_cogulator_times_sum_to_klm(model, result, variant, key):
    table = klm.load_table(None)
    for task, t_res in zip(model["tasks"], result["tasks"]):
        for m, m_res in zip(task["methods"], t_res["methods"]):
            code = cogulator_export.export_method(task, m, table, variant, "Point")
            lines = code.splitlines()
            assert lines[0].startswith("Goal: ")
            body = lines[1:]
            assert all(ln.startswith(". ") and not ln.startswith(". . ") for ln in body)
            total = sum(int(MS.search(ln).group(1)) for ln in body)
            assert total == round(m_res[key] * 1000), (task["id"], m["id"], variant)


def test_every_operator_line_forces_a_time(model):
    md, files = cogulator_export.build(model, klm.load_table(None), "low", "Point")
    for code in files.values():
        for ln in code.splitlines():
            if ln.startswith(("Goal:", "CreateState", "If ", "EndIf")) or ln.lstrip(". ").startswith("Goal:"):
                continue
            assert MS.search(ln), ln


def test_operator_names_and_forced_table(model):
    _, files = cogulator_export.build(model, klm.load_table(None), "low", "Point")
    code = files["M1_2_G.txt"]
    assert ". Point to global search field (1100 ms)" in code
    assert ". Click global search field (200 ms)" in code
    assert ". Hands to keyboard (400 ms)" in code
    assert ". Type query [6 keys] (1680 ms)" in code
    assert "Think global search field <query> (1350 ms)" in code
    assert "Click triple-click value field (600 ms)" in code


def test_drag_press_release(model):
    _, files = cogulator_export.build(model, klm.load_table(None), "low", "Point")
    code = files["M6_1_D1.txt"]
    assert "Click press on empty upload tile (100 ms)" in code
    assert "Point to empty upload tile [dragging] (1100 ms)" in code
    assert "Click release on empty upload tile (100 ms)" in code


def test_selection_block(model):
    md, files = cogulator_export.build(model, klm.load_table(None), "low", "Point")
    code = files["M6_2_selection.txt"]
    lines = code.splitlines()
    assert lines[0] == "CreateState method form"
    assert "If method form" in lines and "If method chat" in lines
    assert lines.count("EndIf") == 2
    # If / EndIf take no dot prefix; bodies are nested one level deeper.
    assert ". Goal: M6.2 chat In-app AI chat" in lines
    assert any(ln.startswith(". . Type request [28 keys]") for ln in lines)
    assert "M1_2_selection.txt" not in files  # single-method task
    # Notes live outside code blocks.
    assert "Selection rule:" in md.split("```")[0] + md.split("```")[2]


def test_default_method_flag(model):
    task = next(t for t in model["tasks"] if t["id"] == "M6.2")
    task = dict(task, methods=[dict(task["methods"][0]), dict(task["methods"][1], default=True)])
    code = cogulator_export.export_selection(task, klm.load_table(None), "low", "Point")
    assert code.splitlines()[0] == "CreateState method chat"


def test_labels_are_sanitised():
    step = {"label": "Open <menu> (top)", "status": "verified", "chunks": ["ticker"]}
    lines = cogulator_export.step_lines(step, klm.parse_ops("M P BB"), klm.load_table(None),
                                        "nominal", {"hands": "mouse", "button_down": False}, 1, "Point")
    assert lines[0] == ". Think Open 'menu' [top] <ticker> (1350 ms)"
    assert all(ln.count("<") == ln.count(">") for ln in lines)


def test_r_is_omitted_and_noted(model):
    md, files = cogulator_export.build(model, klm.load_table(None), "low", "Point")
    assert "Wait for the answer" not in files["M6_2_chat.txt"]
    assert "R omitted in: Wait for the answer." in md


def test_out_dir(tmp_path, demo_model, capsysbinary):
    assert cogulator_export.main([str(demo_model), "--out-dir", str(tmp_path)]) == 0
    names = sorted(p.name for p in tmp_path.iterdir())
    assert "M6_2_selection.txt" in names and "M1_2_G.txt" in names


# ---------------------------------------------------------------- sheet
def test_sheet_rows_and_end_block(model, result):
    md = sheet.render(model, result, "en")
    assert "| 6 | Click the confirming command [NOT VERIFIED] | 15.1 |  |  |  |" in md
    assert "| 10 | Save [NOT EXECUTED] | 19.4 |  |  |  |" in md
    assert md.count("| ☐ yes ☐ with hint ☐ no | 1 2 3 4 5 6 7 |") == 3
    assert "☐ form ☐ chat ☐ other: ____" in md
    assert "Measured R to subtract (s)" in md


def test_sheet_czech(model, result):
    md = sheet.render(model, result, "cs")
    assert "☐ ano ☐ s nápovědou ☐ ne" in md and "[NEOVĚŘENO]" in md


def test_sheet_discovery_task_has_end_block_only(tmp_path):
    model = {"app": "x", "tasks": [{"id": "D1", "title": "Explain the chart", "triage": "discovery"}]}
    klm.validate_model(model)
    md = sheet.render(model, klm.evaluate_model(model), "en")
    assert "observe only" in md and "Success" in md and "Search-cost marker" not in md


def test_sheet_cli_output_file(tmp_path, demo_model):
    out = tmp_path / "sheet.md"
    assert sheet.main([str(demo_model), "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Observer recording sheet — Demo app (fictional)")


def test_templates_parse(skill_dir):
    for rel in ("templates/app-profile.yaml", "templates/model.yaml",
                "examples/demo/app-profile.yaml"):
        data = yaml.safe_load((skill_dir / rel).read_text(encoding="utf-8"))
        assert isinstance(data, dict), rel
    klm.validate_model(yaml.safe_load((skill_dir / "templates/model.yaml").read_text(encoding="utf-8")))
