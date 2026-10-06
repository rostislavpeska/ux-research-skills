import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))


@pytest.fixture
def skill_dir() -> Path:
    return SKILL


@pytest.fixture
def demo_model(skill_dir) -> Path:
    return skill_dir / "examples" / "demo" / "model.yaml"


def one_method_model(ops_low, ops_extra="", status="verified", **method):
    """Minimal valid model with one task / one method / one step per ops string."""
    lows = ops_low if isinstance(ops_low, list) else [ops_low]
    extras = ops_extra if isinstance(ops_extra, list) else [ops_extra] * len(lows)
    steps = [
        {"label": f"step {i}", "ops_low": lo, "ops_extra": ex, "status": status, "chunks": []}
        for i, (lo, ex) in enumerate(zip(lows, extras), 1)
    ]
    return {"app": "test", "tasks": [{"id": "T1", "methods": [dict({"id": "A", "steps": steps}, **method)]}]}
