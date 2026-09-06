"""Bounded memory-only summaries of existing native navigation observations."""

from collections import deque
from contextlib import contextmanager
from copy import deepcopy
import math

CAPACITY = 64
TEXT_LIMIT = 512
SAMPLE_LIMIT = 8
STAGE_LIMIT = 2
PUBLICATION_LIMIT = 6
COUNTER_MAX = (1 << 64) - 1


def bounded_text(value):
    if not isinstance(value, str):
        return None
    if len(value) <= TEXT_LIMIT:
        return value
    return value[: TEXT_LIMIT - 12] + " [truncated]"


def scalar(value):
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value if -COUNTER_MAX <= value <= COUNTER_MAX else None
    if type(value) is float:
        return value if math.isfinite(value) and abs(value) <= COUNTER_MAX else None
    return bounded_text(value)


def error_text(error):
    try:
        return bounded_text(f"{type(error).__name__}: {error}")
    except BaseException:
        return "exception text unavailable"


class Observation:
    def __init__(
        self, history=None, phase=None, deadline=None, expected=None, index=None
    ):
        self.history = history
        self.data = None
        if history is not None:
            self.data = {
                "observation_id": min(COUNTER_MAX, history.observed + 1),
                "phase": bounded_text(phase),
                "active_phase": bounded_text(phase),
                "target": history.target,
                "expected": bounded_text(expected),
                "endpoint_index": scalar(index),
                "batch_deadline_monotonic": scalar(deadline),
                "navigation_deadline_monotonic": history.deadline,
                "started_monotonic_ns": history.now(),
                "ended_monotonic_ns": None,
                "elapsed_ns": None,
                "outcome": None,
                "rejection_reason": None,
                "exception": None,
                "publications": [],
                "publication_count": 0,
                "panel_checks": [],
                "panel_check_count": 0,
                "scans": [],
                "scan_count": 0,
                "discoveries": [],
                "discovery_count": 0,
                "recovery": None,
            }

    def phase(self, phase):
        if self.data is not None:
            self.data["active_phase"] = bounded_text(phase)

    def reject(self, reason):
        if self.data is not None:
            self.data["rejection_reason"] = bounded_text(reason)

    def outcome(self, value):
        if self.data is not None:
            self.data["outcome"] = bounded_text(value)

    @property
    def number(self):
        return self.data["observation_id"] if self.data is not None else None

    def recovery(self, blocked, preparing, started, proof, blocked_at, blocked_reason):
        if self.data is not None:
            self.data["recovery"] = {
                "blocked": scalar(blocked),
                "preparing": scalar(preparing),
                "started": scalar(started),
                "proof": scalar(proof),
                "blocked_at_observation": scalar(blocked_at),
                "blocked_reason": bounded_text(blocked_reason),
            }

    def publication(self, phase, frame):
        if self.data is None:
            return
        snapshot = frame.get("snapshot") if isinstance(frame, dict) else None
        values = {
            key: scalar(frame.get(key)) if isinstance(frame, dict) else None
            for key in ("application_pid", "render_revision", "accepted_unix_ns")
        }
        values["sequence"] = (
            scalar(snapshot.get("sequence")) if isinstance(snapshot, dict) else None
        )
        self._append(
            "publications",
            "publication_count",
            {"phase": bounded_text(phase), **values},
            PUBLICATION_LIMIT,
        )

    def panel(self, outcome, phase):
        if self.data is not None:
            self._append(
                "panel_checks",
                "panel_check_count",
                {"phase": bounded_text(phase), "current": scalar(outcome)},
                SAMPLE_LIMIT,
            )
        return outcome

    def _append(self, field, counter, value, limit):
        self.data[counter] = min(COUNTER_MAX, self.data[counter] + 1)
        if len(self.data[field]) == limit:
            self.data[field].pop(0)
        self.data[field].append(value)

    @contextmanager
    def stage(self, kind):
        if self.data is None:
            yield
            return
        self.phase("selection scan" if kind == "scan" else "panel discovery")
        stage = {
            "started_monotonic_ns": self.history.now(),
            "completed_monotonic_ns": None,
            "aborted_monotonic_ns": None,
            "elapsed_ns": None,
            "complete": False,
        }
        if kind == "scan":
            stage.update(
                row_count=0,
                row_identity_sample=[],
                last_row_identity=None,
                selection_check_count=0,
                instantiated_selected_count=0,
                instantiated_selected=[],
                mapped_span=None,
                mapped_count=None,
                mapping_source=None,
                mapping_error=None,
                complete_span=None,
            )
        self._append(
            "scans" if kind == "scan" else "discoveries",
            kind + "_count",
            stage,
            STAGE_LIMIT,
        )
        try:
            yield
        except BaseException:
            if not stage["complete"]:
                stage["aborted_monotonic_ns"] = self.history.now()
                stage["elapsed_ns"] = self.history.elapsed(
                    stage["started_monotonic_ns"], stage["aborted_monotonic_ns"]
                )
            raise
        else:
            if not stage["complete"]:
                self._complete_stage(stage)

    def _complete_stage(self, stage):
        stage["complete"] = True
        stage["completed_monotonic_ns"] = self.history.now()
        stage["elapsed_ns"] = self.history.elapsed(
            stage["started_monotonic_ns"], stage["completed_monotonic_ns"]
        )

    def scan_complete(self):
        if self.data is not None and self.data["scans"]:
            self._complete_stage(self.data["scans"][-1])

    def row(self, aid):
        if self.data is None or not self.data["scans"]:
            return
        scan = self.data["scans"][-1]
        scan["row_count"] = min(COUNTER_MAX, scan["row_count"] + 1)
        value = bounded_text(aid)
        if len(scan["row_identity_sample"]) < SAMPLE_LIMIT:
            scan["row_identity_sample"].append(value)
        scan["last_row_identity"] = value

    def selection(self, aid, selected):
        if self.data is None or not self.data["scans"]:
            return
        scan = self.data["scans"][-1]
        scan["selection_check_count"] = min(
            COUNTER_MAX, scan["selection_check_count"] + 1
        )
        if selected:
            scan["instantiated_selected_count"] = min(
                COUNTER_MAX, scan["instantiated_selected_count"] + 1
            )
            if len(scan["instantiated_selected"]) < SAMPLE_LIMIT:
                scan["instantiated_selected"].append(bounded_text(aid))

    def mapping(self, mapped, complete_span, source="after selection"):
        if self.data is not None and self.data["scans"]:
            self.data["scans"][-1].update(
                mapped_span=[scalar(min(mapped)), scalar(max(mapped))]
                if mapped
                else None,
                mapped_count=scalar(len(mapped)),
                complete_span=scalar(complete_span),
                mapping_source=bounded_text(source),
            )

    def partial_mapping(self, rows, processes):
        # Only used after an interrupted scan. Derive a span from already-read
        # inputs, without retaining them or issuing a new publication/native read.
        if self.data is None or not self.data["scans"] or rows is None:
            return
        low = high = None
        count = 0
        try:
            row_ids = set(rows)
            for index, process in enumerate(processes):
                identity = process["identity"]
                if (
                    f"process:{identity['pid']}:{identity['start_time_ticks']}"
                    in row_ids
                ):
                    low = index if low is None else low
                    high = index
                    count += 1
        except BaseException as error:
            self.data["scans"][-1]["mapping_error"] = error_text(error)
            return
        self.data["scans"][-1].update(
            mapped_span=[low, high] if low is not None else None,
            mapped_count=scalar(count),
            complete_span=None,
            mapping_source="before selection; aborted observation",
        )


DISABLED = Observation()


class NavigationObservations:
    def __init__(self, clock, target, deadline):
        self.clock = clock
        self.target = bounded_text(target)
        self.deadline = scalar(deadline)
        self.records = deque(maxlen=CAPACITY)
        self.observed = 0
        self.evicted = 0
        self.current = None

    def now(self):
        try:
            return scalar(self.clock.monotonic_ns())
        except Exception:
            return None

    @staticmethod
    def elapsed(start, end):
        return (
            end - start
            if start is not None and end is not None and end >= start
            else None
        )

    def snapshot(self):
        return {
            "capacity": CAPACITY,
            "observed": self.observed,
            "evicted": self.evicted,
            "clock": "Python time.monotonic_ns",
            "records": deepcopy(list(self.records)),
        }


def current_observation(native):
    history = getattr(native, "navigation_observations", None)
    return (
        history.current
        if history is not None and history.current is not None
        else DISABLED
    )


@contextmanager
def navigation_observation(native, phase, deadline, expected=None, index=None):
    history = getattr(native, "navigation_observations", None)
    if history is None:
        yield DISABLED
        return
    if history.current is not None:
        yield history.current
        return
    record = Observation(history, phase, deadline, expected, index)
    context = getattr(native, "navigation_context", None)
    record.data["navigation_phase"] = (
        bounded_text(context.get("phase")) if isinstance(context, dict) else None
    )
    history.observed = min(COUNTER_MAX, history.observed + 1)
    if len(history.records) == CAPACITY:
        history.evicted = min(COUNTER_MAX, history.evicted + 1)
    history.records.append(record.data)
    history.current = record
    try:
        yield record
    except BaseException as error:
        record.data["exception"] = error_text(error)
        record.data["outcome"] = "exception"
        raise
    finally:
        record.data["ended_monotonic_ns"] = history.now()
        record.data["elapsed_ns"] = history.elapsed(
            record.data["started_monotonic_ns"], record.data["ended_monotonic_ns"]
        )
        history.current = None
