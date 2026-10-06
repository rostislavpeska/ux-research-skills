"""measure_r.py hard gate — tested without a browser."""
import pytest
import yaml

import measure_r

BASE = "https://app.example.com/"
FORBIDDEN = measure_r.compile_forbidden(["Watchlist"])


def step(label="Open search", status="verified", **replay):
    replay = replay or {"action": "click", "selector": "role=button[name='Search']"}
    return {"label": label, "status": status, "ops_low": "M P BB", "replay": replay}


def reasons(s, ai=False):
    return measure_r.gate_step(s, FORBIDDEN, BASE, ai)


def test_verified_read_only_click_allowed():
    assert reasons(step()) == []


def test_step_without_replay_is_ignored():
    assert reasons({"label": "Save", "status": "not_executed"}) == []


@pytest.mark.parametrize("status", ["not_verified", "not_executed", "documented", None])
def test_non_verified_status_refused(status):
    assert any("only 'verified'" in r for r in reasons(step(status=status)))


@pytest.mark.parametrize("label", [
    "Click Save", "Submit the form", "Send message", "Add to portfolio", "Star the fund",
    "Add to favourites", "Log in", "Sign up", "Import CSV", "Delete row", "Create account",
    "Uložit", "Odeslat", "Přidat do portfolia", "Přihlásit se", "Smazat", "Vytvořit účet",
    "Add to Watchlist",
])
def test_forbidden_labels_refused(label):
    assert any("forbidden action" in r for r in reasons(step(label=label)))


@pytest.mark.parametrize("label", ["Open address book", "Start screen", "Important news",
                                   "Poslední hledání", "Adresář"])
def test_harmless_lookalikes_allowed(label):
    assert [r for r in reasons(step(label=label)) if "forbidden" in r] == []


def test_forbidden_in_selector_refused():
    s = step(action="click", selector="role=button[name='Save changes']")
    assert any("selector" in r for r in reasons(s))


def test_profile_regex_item():
    pats = measure_r.compile_forbidden(["re:run\\s+and\\s+save"])
    assert measure_r.gate_step(step(label="Run and save"), pats, BASE)


@pytest.mark.parametrize("replay", [
    {"action": "fill", "selector": "input[type=password]", "text": "x"},
    {"action": "fill", "selector": "#search", "text": "jan@example.com"},
    {"action": "fill", "selector": "#search", "text": "777123456"},
])
def test_personal_data_refused(replay):
    assert any("personal" in r for r in reasons(step(**replay)))


def test_search_fill_allowed():
    assert reasons(step(action="fill", selector="#global-search", text="AAPL")) == []


def test_unknown_action_refused():
    assert any("read-only set" in r for r in reasons(step(action="dblclick_save", selector="#x")))


def test_goto_other_origin_refused():
    assert any("leaves the base_url origin" in r
               for r in reasons(step(action="goto", url="https://evil.example.org/")))
    assert reasons(step(action="goto", url="/markets")) == []


def test_ai_assistant_needs_approval():
    s = step(label="Type into the AI chat", action="fill", selector="#chat-input", text="compare funds")
    assert any("ai_assistant.messages_approved" in r for r in reasons(s))
    assert reasons(s, ai=True) == []


def model_with(steps):
    return {"tasks": [{"id": "T", "methods": [{"id": "A", "steps": steps}]}]}


def test_plan_stops_at_first_step_without_replay():
    steps = [step(), {"label": "Think", "status": "verified", "ops_low": "M"}, step(label="Open list")]
    (_, _, prefix), = measure_r.plan(model_with(steps))
    assert [s["label"] for s in prefix] == ["Open search"]


def test_gate_model_checks_every_replay_block_not_just_prefix():
    steps = [step(), {"label": "Think", "status": "verified", "ops_low": "M"},
             step(label="Save", status="not_executed")]
    violations = measure_r.gate_model(model_with(steps), {"base_url": BASE})
    # step 1 (verified, read-only) is clean; step 3 trips both status and verb rules.
    assert violations and all("step 3 (Save)" in v for v in violations)
    assert any("only 'verified'" in v for v in violations)
    assert any("forbidden action" in v for v in violations)


def test_cli_refuses_before_any_browser(tmp_path, capsys):
    model = tmp_path / "model.yaml"
    model.write_text(yaml.safe_dump(model_with([step(label="Click Save")])), encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump({"base_url": BASE}), encoding="utf-8")
    assert measure_r.main([str(model), "--profile", str(profile)]) == 3
    assert "REFUSED" in capsys.readouterr().err


def test_cli_dry_run_clean(tmp_path, capsys):
    model = tmp_path / "model.yaml"
    model.write_text(yaml.safe_dump(model_with([step()])), encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump({"base_url": BASE}), encoding="utf-8")
    assert measure_r.main([str(model), "--profile", str(profile), "--dry-run"]) == 0
    assert "T · A: Open search" in capsys.readouterr().out


def test_demo_example_has_nothing_replayable(demo_model, skill_dir, tmp_path, capsys):
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump({"base_url": BASE}), encoding="utf-8")
    assert measure_r.main([str(demo_model), "--profile", str(profile), "--dry-run"]) == 0
    assert "(no replayable prefix)" in capsys.readouterr().out


def test_viewport_parsing():
    assert measure_r.viewport({"viewport": "1440×900"}) == {"width": 1440, "height": 900}
    assert measure_r.viewport({}) == {"width": 1440, "height": 900}


@pytest.mark.parametrize("replay, fragment", [
    ({"action": "click", "selector": "#go", "until": "soon"}, "must be a {selector, state} mapping"),
    ({"action": "click", "selector": "#go", "until": {"state": "visible"}}, "until needs a selector"),
    ({"action": "click", "selector": "#go", "until": {"selector": "#r", "state": "shiny"}}, "until needs a selector"),
    ({"action": "click"}, "needs a selector"),
])
def test_bad_replay_shape_refused_before_browser(replay, fragment):
    assert any(fragment in r for r in reasons(step(**replay)))


def test_good_until_forms_allowed():
    for until in ("load", "networkidle", {"selector": "#results li", "state": "visible"},
                  {"selector": "#spinner", "state": "hidden"}):
        assert reasons(step(action="click", selector="#go", until=until)) == []