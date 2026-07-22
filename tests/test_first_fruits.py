"""First Fruits founders view — public-plane only, no tracking.

Verifies that `community.first_fruits`:
  * counts only contributors who have ENTERED WISDOM (bare registrations excluded),
  * ranks by fruit borne, earliest-to-testify winning ties,
  * respects the limit and annotates founder_rank / fruit.
"""
import json

from api import community


def _write(dir_, handle, *, join_seq, stats):
    rec = {
        "handle": handle,
        "display_name": handle,
        "bio": "",
        "tier": "brother" if community.has_entered_wisdom(stats) else "visitor",
        "join_seq": join_seq,
        "joined_at": 1_700_000_000 + join_seq,
        "joined_iso": "",
        "user_pubkey": f"pk_{handle}",
        "curator": False,
        "stats": stats,
        "badges": [],
    }
    (dir_ / f"{handle}.json").write_text(json.dumps(rec), encoding="utf-8")


def _stats(**kw):
    base = {"proposals_submitted": 0, "proposals_accepted": 0,
            "polymathic_runs": 0, "witnesses_given": 0,
            "witnesses_received": 0, "confessions": 0}
    base.update(kw)
    return base


def test_first_fruits(tmp_path, monkeypatch):
    cdir = tmp_path / "contributors"
    cdir.mkdir()
    monkeypatch.setattr(community, "_CONTRIB_DIR", cdir)

    # a bare registration — a claimed name, no testimony → excluded
    _write(cdir, "lurker", join_seq=1, stats=_stats())
    # three who entered wisdom, differing fruit
    _write(cdir, "ada",   join_seq=2, stats=_stats(witnesses_given=3, proposals_accepted=1))  # fruit = 3 + 2 = 5
    _write(cdir, "boaz",  join_seq=3, stats=_stats(polymathic_runs=2, witnesses_given=1))     # fruit = 3
    _write(cdir, "cyrus", join_seq=4, stats=_stats(confessions=3))                            # fruit = 3

    res = community.first_fruits(limit=3)

    handles = [f["handle"] for f in res["founders"]]
    assert "lurker" not in handles, "bare registration must be excluded"
    assert res["entered_wisdom_total"] == 3
    assert res["count"] == 3

    # ada leads on fruit; boaz and cyrus tie on fruit(3) → earlier join_seq wins
    assert handles == ["ada", "boaz", "cyrus"]
    assert res["founders"][0]["fruit"] == 5
    assert res["founders"][0]["founder_rank"] == 1
    assert res["founders"][1]["founder_rank"] == 2


def test_first_fruits_limit(tmp_path, monkeypatch):
    cdir = tmp_path / "contributors"
    cdir.mkdir()
    monkeypatch.setattr(community, "_CONTRIB_DIR", cdir)
    _write(cdir, "ada",  join_seq=1, stats=_stats(witnesses_given=2))
    _write(cdir, "boaz", join_seq=2, stats=_stats(witnesses_given=1))
    res = community.first_fruits(limit=1)
    assert res["count"] == 1
    assert res["founders"][0]["handle"] == "ada"
    assert res["entered_wisdom_total"] == 2  # total is honest even when limited


def test_first_fruits_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(community, "_CONTRIB_DIR", tmp_path / "nope")
    res = community.first_fruits()
    assert res == {"founders": [], "count": 0, "entered_wisdom_total": 0,
                   "note": res["note"]}
