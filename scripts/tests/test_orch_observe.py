import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch.claims import lane_name_for
from orch.observe import active_lane_names, build_observation, summarize


def ts(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


class ActiveLaneNamesTests(unittest.TestCase):
    """Pickup evidence is a claim/settlement interval, not updated_at.

    lane-coord refreshes a manifest's ``updated_at`` on every state
    rewrite — including post-settlement cleanup — while preserving
    ``claimed_at``, so ``updated_at`` cannot establish the lane was
    active during the observation interval.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_lane(self, name, *, state, claimed_at, updated_at, history=()):
        manifest = {
            "state": state,
            "claimed_at": claimed_at,
            "updated_at": updated_at,
        }
        (self.dir / f"{name}.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        if history:
            lines = "".join(
                f"{stamp} {event} epoch=1 worker=w\n"
                for stamp, event in history
            )
            (self.dir / f"{name}.log").write_text(lines, encoding="utf-8")

    def active(self, start="2026-01-01T02:00:00", end="2026-01-01T03:00:00"):
        return active_lane_names(self.dir, ts(start), ts(end))

    def test_cleaned_inside_window_after_release_before_it_is_not_evidence(self):
        # Regression: lane claimed 00:00, released 01:00 (before the
        # window), cleaned 02:30 (inside it). The cleanup refreshed
        # updated_at, but the lane was never active in the window.
        self.write_lane(
            "lane-x",
            state="cleaned",
            claimed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T02:30:00Z",
            history=[
                ("2026-01-01T00:00:00Z", "claimed"),
                ("2026-01-01T01:00:00Z", "released"),
                ("2026-01-01T02:30:00Z", "cleaned"),
            ],
        )
        self.assertEqual(self.active(), set())

    def test_direct_cleanup_closes_open_claim_interval(self):
        # Regression (Codex P2): an interrupted lane cleaned directly
        # — claimed, then cleaned with no intervening release (a
        # lane-coord-supported path). The cleanup closes the claim
        # interval, which intersects the window.
        self.write_lane(
            "lane-x",
            state="cleaned",
            claimed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T02:30:00Z",
            history=[
                ("2026-01-01T00:00:00Z", "claimed"),
                ("2026-01-01T02:30:00Z", "cleaned"),
            ],
        )
        self.assertEqual(self.active(), {"lane-x"})

    def test_claimed_and_cleaned_inside_window_is_evidence(self):
        self.write_lane(
            "lane-x",
            state="cleaned",
            claimed_at="2026-01-01T02:10:00Z",
            updated_at="2026-01-01T02:30:00Z",
            history=[
                ("2026-01-01T02:10:00Z", "claimed"),
                ("2026-01-01T02:30:00Z", "cleaned"),
            ],
        )
        self.assertEqual(self.active(), {"lane-x"})

    def test_claimed_and_cleaned_before_window_is_not_evidence(self):
        self.write_lane(
            "lane-x",
            state="cleaned",
            claimed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T01:00:00Z",
            history=[
                ("2026-01-01T00:00:00Z", "claimed"),
                ("2026-01-01T01:00:00Z", "cleaned"),
            ],
        )
        self.assertEqual(self.active(), set())

    def test_settled_manifest_without_history_is_not_evidence(self):
        # A settled manifest whose settlement time cannot be
        # established (no history) earns no pickup credit, however
        # recent its updated_at.
        self.write_lane(
            "lane-y",
            state="released",
            claimed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T02:30:00Z",
        )
        self.assertEqual(self.active(), set())

    def test_released_inside_window_is_evidence(self):
        self.write_lane(
            "lane-x",
            state="released",
            claimed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T02:15:00Z",
            history=[
                ("2026-01-01T00:00:00Z", "claimed"),
                ("2026-01-01T02:15:00Z", "released"),
            ],
        )
        self.assertEqual(self.active(), {"lane-x"})

    def test_claimed_and_settled_inside_window_is_evidence(self):
        self.write_lane(
            "lane-x",
            state="reaped",
            claimed_at="2026-01-01T02:10:00Z",
            updated_at="2026-01-01T02:20:00Z",
            history=[
                ("2026-01-01T02:10:00Z", "claimed"),
                ("2026-01-01T02:20:00Z", "settled-interrupted"),
                ("2026-01-01T02:20:00Z", "reaped"),
            ],
        )
        self.assertEqual(self.active(), {"lane-x"})

    def test_settled_entirely_before_window_is_not_evidence(self):
        self.write_lane(
            "lane-x",
            state="released",
            claimed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T01:00:00Z",
            history=[
                ("2026-01-01T00:00:00Z", "claimed"),
                ("2026-01-01T01:00:00Z", "released"),
            ],
        )
        self.assertEqual(self.active(), set())

    def test_still_claimed_manifest_without_history_is_evidence(self):
        self.write_lane(
            "lane-x",
            state="claimed",
            claimed_at="2026-01-01T01:00:00Z",
            updated_at="2026-01-01T01:00:00Z",
        )
        self.assertEqual(self.active(), {"lane-x"})

    def test_reclaimed_episode_inside_window_is_evidence(self):
        # First claim settled before the window; a second claim opened
        # inside it and is still active.
        self.write_lane(
            "lane-x",
            state="claimed",
            claimed_at="2026-01-01T02:05:00Z",
            updated_at="2026-01-01T02:05:00Z",
            history=[
                ("2026-01-01T00:00:00Z", "claimed"),
                ("2026-01-01T01:00:00Z", "released"),
                ("2026-01-01T02:05:00Z", "claimed"),
            ],
        )
        self.assertEqual(self.active(), {"lane-x"})

    def test_exit_after_cleanup_is_not_pickup_explained(self):
        # End to end: the issue leaves ready in the interval where the
        # lane was only cleaned; the exit stays unexplained and no
        # pickup lag is credited.
        lane = lane_name_for("X-1")
        self.write_lane(
            lane,
            state="cleaned",
            claimed_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T02:30:00Z",
            history=[
                ("2026-01-01T00:00:00Z", "claimed"),
                ("2026-01-01T01:00:00Z", "released"),
                ("2026-01-01T02:30:00Z", "cleaned"),
            ],
        )
        previous = {
            "ts": "2026-01-01T02:00:00+00:00",
            "ready": ["X-1"],
        }
        observation = build_observation(
            now=ts("2026-01-01T03:00:00"),
            tracker="beads",
            dispatch=[],
            rejections={"X-1": "STATE_NOT_ACTIVE"},
            previous=previous,
            active_lanes=self.active(),
            points_spent=None,
            fetch_count=1,
            type_excluded_count=0,
            truncated=False,
        )
        self.assertEqual(
            observation["exits"],
            [{"identifier": "X-1", "pickup_explained": False}],
        )
        summary = summarize([previous | {"ready_wait_s": {}}, observation])
        self.assertIn("pickup lag: n/a", summary)

    def test_exit_pickup_recognized_under_project_prefixed_lane(self):
        # Regression (Codex P2): the coordinator's manifest for
        # GitHub issue 42 under project proj is proj-42.json; the
        # bare-number lookup never matched it, so the pickup went
        # unrecognized.
        lane = lane_name_for("42", "proj")
        self.assertEqual(lane, "proj-42")
        self.write_lane(
            lane,
            state="claimed",
            claimed_at="2026-01-01T02:05:00Z",
            updated_at="2026-01-01T02:05:00Z",
            history=[("2026-01-01T02:05:00Z", "claimed")],
        )
        previous = {
            "ts": "2026-01-01T02:00:00+00:00",
            "ready": ["42"],
        }
        observation = build_observation(
            now=ts("2026-01-01T03:00:00"),
            tracker="github",
            dispatch=[],
            rejections={"42": "STATE_NOT_ACTIVE"},
            previous=previous,
            active_lanes=self.active(),
            points_spent=None,
            fetch_count=1,
            type_excluded_count=0,
            truncated=False,
            project_slug="proj",
        )
        self.assertEqual(
            observation["exits"],
            [{"identifier": "42", "pickup_explained": True}],
        )

    def test_exit_after_direct_cleanup_is_pickup_explained(self):
        # End to end (Codex P2): claimed and cleaned between the two
        # observations, no release — the exit is a pickup and the lag
        # is credited.
        lane = lane_name_for("X-1")
        self.write_lane(
            lane,
            state="cleaned",
            claimed_at="2026-01-01T02:10:00Z",
            updated_at="2026-01-01T02:30:00Z",
            history=[
                ("2026-01-01T02:10:00Z", "claimed"),
                ("2026-01-01T02:30:00Z", "cleaned"),
            ],
        )
        previous = {
            "ts": "2026-01-01T02:00:00+00:00",
            "ready": ["X-1"],
        }
        observation = build_observation(
            now=ts("2026-01-01T03:00:00"),
            tracker="beads",
            dispatch=[],
            rejections={"X-1": "STATE_NOT_ACTIVE"},
            previous=previous,
            active_lanes=self.active(),
            points_spent=None,
            fetch_count=1,
            type_excluded_count=0,
            truncated=False,
        )
        self.assertEqual(
            observation["exits"],
            [{"identifier": "X-1", "pickup_explained": True}],
        )
        summary = summarize([previous | {"ready_wait_s": {}}, observation])
        self.assertIn(
            "pickup lag: median 3600s over 1 pickup-explained exit", summary
        )


def make_obs(stamp, ready=(), exits=()):
    return {
        "ts": stamp,
        "tracker": "beads",
        "ready": list(ready),
        "rejected": {},
        "ready_wait_s": {},
        "ready_wait_basis": "updated_at_lb",
        "exits": [
            {"identifier": identifier, "pickup_explained": explained}
            for identifier, explained in exits
        ],
        "age_s": {},
        "points_spent": None,
        "fetch_count": 0,
        "type_excluded_count": 0,
        "truncated": False,
    }


class PickupLagBaselineTests(unittest.TestCase):
    """Pickup lag is measured over the current ready episode only.

    The baseline must clear on every exit from ready — explained or
    not — or time spent blocked/closed between episodes is counted
    as dispatch delay.
    """

    def test_unexplained_exit_resets_the_baseline(self):
        # Regression: ready 00:00, blocked (unexplained exit) 01:00,
        # ready again 10:00, picked up 11:00 — the lag is the current
        # episode's 1 hour, not 11 hours from the first-ever sighting.
        observations = [
            make_obs("2026-01-01T00:00:00+00:00", ready=["x"]),
            make_obs("2026-01-01T01:00:00+00:00", exits=[("x", False)]),
            make_obs("2026-01-01T10:00:00+00:00", ready=["x"]),
            make_obs("2026-01-01T11:00:00+00:00", exits=[("x", True)]),
        ]
        self.assertIn(
            "pickup lag: median 3600s over 1 pickup-explained exit",
            summarize(observations),
        )

    def test_explained_exit_also_resets_the_baseline(self):
        observations = [
            make_obs("2026-01-01T00:00:00+00:00", ready=["x"]),
            make_obs("2026-01-01T01:00:00+00:00", exits=[("x", True)]),
            make_obs("2026-01-01T05:00:00+00:00", ready=["x"]),
            make_obs("2026-01-01T06:00:00+00:00", exits=[("x", True)]),
        ]
        self.assertIn(
            "pickup lag: median 3600s over 2 pickup-explained exits",
            summarize(observations),
        )

    def test_uninterrupted_episode_keeps_its_baseline(self):
        observations = [
            make_obs("2026-01-01T00:00:00+00:00", ready=["x"]),
            make_obs("2026-01-01T01:00:00+00:00", ready=["x"]),
            make_obs("2026-01-01T03:00:00+00:00", exits=[("x", True)]),
        ]
        self.assertIn(
            "pickup lag: median 10800s over 1 pickup-explained exit",
            summarize(observations),
        )


if __name__ == "__main__":
    unittest.main()
