#!/usr/bin/env python3
"""Regression tests for the #28 CTX energy-axis removal.

Issue #28 — the energy axis was dead: no writer ever produced the
`energy` field on album tags, so every CTX profile shipped
`energy: null` and the ENERGY_MODIFIERS path never fired. The axis was
removed honestly rather than left as a dead promise:

- `bin/ctx_profiles.py` has no ENERGY_MODIFIERS attribute; its fit()
  takes (session, duration_tier) only and returns the table value;
- profiles carry no "energy" field and the committed envelope carries no
  "energy_modifiers" key;
- `sampler/rollup.py::session_fit_scores` is duration-only: a profile
  that still carries a stale "energy" field cannot change the scores
  (the schema no longer promises the field, so nothing may read it).

Run: python3 bin/tests/test_ctx.py  (stdlib only)
"""
import inspect
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sampler"))

import ctx_profiles
from rollup import session_fit_scores

REPO = os.path.join(os.path.dirname(__file__), "..", "..")


def check_fit_signature():
    params = list(inspect.signature(ctx_profiles.fit).parameters)
    assert params == ["session", "duration_tier_"], params
    assert not hasattr(ctx_profiles, "ENERGY_MODIFIERS"), \
        "ENERGY_MODIFIERS must stay deleted (#28)"


def check_fit_values():
    assert ctx_profiles.fit("morning", "short") == 2.0
    assert ctx_profiles.fit("afternoon", "medium") == 2.0
    assert ctx_profiles.fit("evening", "epic") == 1.75
    assert ctx_profiles.fit("morning", "unknown-tier") is None
    assert ctx_profiles.fit("unknown-session", "short") is None
    assert ctx_profiles.fit("morning", None) is None


def check_envelope_shape():
    """The committed consumer contract: no energy anywhere."""
    with open(os.path.join(REPO, "engine", "ctx_profiles.json")) as f:
        env = json.load(f)
    assert "energy_modifiers" not in env, \
        "envelope must not promise an energy axis (#28)"
    assert env["profiles"], "expected at least one profile"
    for p in env["profiles"]:
        assert "energy" not in p, \
            "profile %s/%s still carries an energy field" % (
                p.get("artist"), p.get("album"))
        assert "duration_tier" in p


def check_fit_ignores_stale_energy():
    """A profile that (stale-ly) carries energy must not change fit."""
    ctx = {"fit_table": ctx_profiles.FIT_TABLE}
    plain = {"duration_tier": "long"}
    stale = {"duration_tier": "long", "energy": "high"}
    stale_low = {"duration_tier": "long", "energy": "low"}
    a = session_fit_scores(ctx, plain)
    assert a == session_fit_scores(ctx, stale) == session_fit_scores(ctx, stale_low)
    assert a == {"morning": 0.75, "afternoon": 1.0, "evening": 2.0}
    assert session_fit_scores(ctx, {"duration_tier": None}) is None


def main():
    for check in (check_fit_signature, check_fit_values,
                  check_envelope_shape, check_fit_ignores_stale_energy):
        check()
        print("ok - %s" % check.__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
