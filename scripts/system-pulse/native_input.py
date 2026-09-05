"""Held and bounded-burst native input regressions with fresh-publication evidence."""

import threading
import time

from native_contract import check_input_record


def exercise(
    app, name, keys, measure, sign, burst=None, expected_identity=None, observe=None
):
    """Observe movement; optional observe(deadline) returns (value, exact identity)."""
    if observe is None:
        before = measure()
    else:
        deadline = time.monotonic() + 5
        before, before_identity = app.wait(
            lambda: observe(deadline),
            message="input baseline " + name,
            deadline=deadline,
        )
    observations = []
    stop = threading.Event()

    def watch():
        while not stop.is_set():
            try:
                frame = app.frame()
                observations.append(
                    {
                        "sequence": frame["snapshot"]["sequence"],
                        "age": (time.time_ns() - frame["accepted_unix_ns"]) / 1e9,
                    }
                )
            except Exception as error:
                observations.append({"error": str(error)})
            stop.wait(0.05)

    watcher = threading.Thread(target=watch, name="input-freshness-observer")
    watcher.start()
    started = time.monotonic_ns()
    record = {
        "keys": keys,
        "before": before,
        "sign": sign,
        "key_count": burst,
        "observations": observations,
        "expected_identity": expected_identity,
    }
    if observe is not None:
        record["before_identity"] = before_identity
    try:
        if burst is None:
            app.key(*keys, pressed=True)
            try:
                time.sleep(3)
            finally:
                app.key(*keys, pressed=False)
        else:
            for _ in range(burst):
                app.key(*keys)
        record["input_duration_ns"] = time.monotonic_ns() - started
        if expected_identity:
            app.acknowledge(expected_identity, time.monotonic() + 5)
        deadline = time.monotonic() + 5

        def moved():
            observation = (
                observe(deadline) if observe is not None else (measure(), None)
            )
            if (
                observation is None
                or observation[0] is None
                or observation[0] == before
            ):
                return None
            return observation

        after, after_identity = app.wait(
            moved,
            message="input movement " + name,
            deadline=deadline,
        )
        record["after"] = after
        if observe is not None:
            record["after_identity"] = after_identity
        app.sequences()
    finally:
        stop.set()
        watcher.join(timeout=1)
        record["observer_joined"] = not watcher.is_alive()
        app.save(name + ".json", record)
    from host_accuracy import require

    require(record["observer_joined"], "input observer failed to join")
    check_input_record(record, burst)
    return record
