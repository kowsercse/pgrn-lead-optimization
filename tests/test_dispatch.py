"""Stage 1 exit gate: scouts run concurrently, a slow scout degrades to a gap
rather than blocking, and a missing required scout downgrades the verdict."""
import time

import pytest

from dossier.dispatch import REQUIRED_SCOUTS, dispatch
from dossier.store import Record, connect, new_run


class StubScout:
    """A scout that returns one record after `delay` seconds."""

    def __init__(self, name, delay=0.0, boom=False):
        self.name = name
        self.deadline_s = 1
        self.delay = delay
        self.boom = boom

    def brief(self, target):
        return f"Investigate {target}."

    def run(self, target):
        time.sleep(self.delay)
        if self.boom:
            raise RuntimeError("scout exploded")
        return [Record(run_id="", scout=self.name, claim="c", value=f"v-{target}",
                       grade="inferred", query=f"q {target}")]


@pytest.fixture()
def conn(tmp_path):
    return connect(tmp_path / "d.db")


def both_required():
    return [StubScout("structures"), StubScout("bioactivity")]


def test_all_scouts_returning_yields_records_and_no_gaps(conn):
    run = new_run(conn, target="X")
    result = dispatch(conn, run, "X", both_required())
    assert len(result.records) == 2
    assert result.gaps == []
    assert result.verdict is None


def test_slow_scout_becomes_a_gap_and_does_not_block(conn):
    run = new_run(conn, target="X")
    scouts = both_required() + [StubScout("literature", delay=1)]
    scouts[-1].deadline_s = 0.1
    result = dispatch(conn, run, "X", scouts)
    assert len(result.records) == 2
    assert [g.scout for g in result.gaps] == ["literature"]
    assert "deadline" in result.gaps[0].reason


def test_dispatch_returns_promptly_even_if_a_scout_hangs(conn):
    """A hung scout must not hold the run open past its own deadline."""
    run = new_run(conn, target="X")
    scouts = both_required() + [StubScout("literature", delay=3)]
    scouts[-1].deadline_s = 0.1
    started = time.monotonic()
    dispatch(conn, run, "X", scouts)
    elapsed = time.monotonic() - started
    assert elapsed < 2, f"dispatch blocked on the hung scout for {elapsed:.1f}s"


def test_each_scout_gets_its_own_deadline(conn):
    """A short-deadline scout is gapped without waiting for a long-deadline one."""
    run = new_run(conn, target="X")
    quick, slow = StubScout("structures"), StubScout("bioactivity")
    late = StubScout("patents", delay=3)
    late.deadline_s = 0.1
    started = time.monotonic()
    result = dispatch(conn, run, "X", [quick, slow, late])
    elapsed = time.monotonic() - started
    assert [g.scout for g in result.gaps] == ["patents"]
    assert elapsed < 1, f"waited {elapsed:.1f}s for a scout with a 0.1s deadline"


def test_raising_scout_becomes_a_gap(conn):
    run = new_run(conn, target="X")
    result = dispatch(conn, run, "X", both_required() + [StubScout("assays", boom=True)])
    assert len(result.records) == 2
    assert [g.scout for g in result.gaps] == ["assays"]


def test_missing_required_scout_downgrades_the_verdict(conn):
    run = new_run(conn, target="X")
    scouts = [StubScout("structures"), StubScout("bioactivity", boom=True)]
    result = dispatch(conn, run, "X", scouts)
    assert result.verdict == "insufficient retrieval"


def test_missing_contributing_scout_does_not_downgrade_the_verdict(conn):
    run = new_run(conn, target="X")
    result = dispatch(conn, run, "X", both_required() + [StubScout("patents", boom=True)])
    assert result.verdict is None


def test_scouts_run_concurrently(conn):
    run = new_run(conn, target="X")
    scouts = [StubScout("structures", delay=0.3), StubScout("bioactivity", delay=0.3),
              StubScout("patents", delay=0.3)]
    started = time.monotonic()
    dispatch(conn, run, "X", scouts)
    assert time.monotonic() - started < 0.75, "scouts ran serially"


def test_gaps_are_persisted(conn):
    run = new_run(conn, target="X")
    dispatch(conn, run, "X", both_required() + [StubScout("assays", boom=True)])
    rows = conn.execute("SELECT scout, reason FROM gap WHERE run_id = ?", (run,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["scout"] == "assays"


def test_records_are_stamped_with_the_run(conn):
    run = new_run(conn, target="X")
    result = dispatch(conn, run, "X", both_required())
    assert {r.run_id for r in result.records} == {run}


def test_required_scouts_are_the_two_the_verdict_depends_on():
    assert set(REQUIRED_SCOUTS) == {"structures", "bioactivity"}
