"""Independent native GPU display and persisted action semantics."""

from host_accuracy import format_sample, require, SYMBOLS
from gpu_evidence import visible


def validate_native_geometry(frame):
    """Recompute viewport clips from original native window/ancestry queries."""
    window = frame.get("native_window")
    if window:
        raw, pos = window["geometry"], window["screen_position"]
        initial = [pos["x"], pos["y"], raw["width"], raw["height"]]
        require(
            window["pid"] == frame["target_pid"]
            and type(window["id"]) is int
            and window["id"] > 0
            and window["frame"] == initial
            and raw["width"] > 0
            and raw["height"] > 0,
            "native X11 window geometry or PID differs from original query",
        )
    clips = {}
    for row in frame["elements"]:
        key, parent = row["object_key"], row["parent_key"]
        require(key not in clips, "ambiguous native object geometry")
        require(parent is None or parent in clips, "missing preceding native parent")
        bounds = row["frame"]
        expected = (
            clips[parent] if parent is not None else (initial if window else bounds)
        )
        if (
            window
            and row["role"] in ("frame", "window")
            and bounds[2] > 0
            and bounds[3] > 0
        ):
            expected = bounds
        require(
            row["clip"] == expected,
            "native clipping differs from window/viewport ancestry",
        )
        visible(
            row
        )  # validate all original numeric geometry, including structural nodes
        if row["identifier"].endswith(":viewport") or row["role"] == "AXScrollArea":
            a, b, c, d = expected
            x, y, w, h = bounds
            left, top = max(a, x), max(b, y)
            expected = [
                left,
                top,
                max(0, min(a + c, x + w) - left),
                max(0, min(b + d, y + h) - top),
            ]
        clips[key] = expected


def resolve_selector(rows, selector):
    """Resolve one actual native object, retaining optional/empty application IDs."""
    require(isinstance(selector, dict) and selector, "missing native selector")
    keys = [r["object_key"] for r in rows]
    require(len(set(keys)) == len(keys), "ambiguous native object identity")
    by_key = {r["object_key"]: r for r in rows}

    def inside(row, ancestor):
        seen = set()
        while row["parent_key"] is not None:
            key = row["parent_key"]
            require(key in by_key and key not in seen, "broken native ancestry")
            if key == ancestor:
                return True
            seen.add(key)
            row = by_key[key]
        return False

    if "identifier" in selector:
        require(
            set(selector) == {"identifier"} and selector["identifier"],
            "invalid identifier selector",
        )
        selected = [r for r in rows if r["identifier"] == selector["identifier"]]
    else:
        require(
            set(selector) <= {"label", "within", "after"}
            and selector.get("label")
            and selector.get("within"),
            "invalid scoped label selector",
        )
        scopes = [
            r for r in rows if selector["within"] in (r["identifier"], r.get("title"))
        ]
        require(len(scopes) == 1, "native scope absent or ambiguous")
        scoped = [r for r in rows if inside(r, scopes[0]["object_key"])]
        if selector.get("after"):
            anchors = [
                i for i, r in enumerate(scoped) if r["identifier"] == selector["after"]
            ]
            require(len(anchors) == 1, "native sensor anchor absent or ambiguous")
            scoped = scoped[anchors[0] + 1 :]
            prefix = selector["after"].split(":value:")[0] + ":value:"
            end = next(
                (i for i, r in enumerate(scoped) if r["identifier"].startswith(prefix)),
                len(scoped),
            )
            scoped = scoped[:end]
        selected = [
            r
            for r in scoped
            if selector["label"]
            in (r.get("title"), r.get("description"), r.get("value"))
        ]
    require(len(selected) == 1, "native target absent or ambiguous")
    require(visible(selected[0]), "native target not fully visible")
    return selected[0]


def anchored_time(stamp, anchor):
    before, after, wall = (
        anchor[k] for k in ("monotonic_before_ns", "monotonic_after_ns", "unix_ns")
    )
    require(
        all(type(v) is int and v >= 0 for v in (stamp, before, after, wall))
        and before <= after,
        "invalid native clock anchor",
    )
    return wall + stamp - after, wall + stamp - before


def expected_gpu_label(frame, entry, interval_ms):
    snapshot = frame["snapshot"]
    sid = entry["sensor_id"]
    sensor = next(s for s in snapshot["sensors"] if s["id"] == sid)
    reading = next(r for r in snapshot["readings"] if r["sensor_id"] == sid)
    monitor = next(m for m in snapshot["monitors"] if m["id"] == entry["monitor_id"])
    sample = entry["sample"]
    require(
        sample and all(sample[k] == reading[k] for k in ("value", "total", "reason")),
        "display sample changed physical reading",
    )
    status = {
        "Available": "current",
        "Unavailable": "unavailable",
        "Failed": "failed",
        "WarmingUp": "warming_up",
    }[reading["availability"]]
    if status == "current":
        at = max(o["captured_ns"] // 1_000_000 for o in reading["observations"])
        if frame["rendered_at_collector_ms"] - at > interval_ms * 2:
            status = "stale"
        text = format_sample(dict(reading, unit=sensor["unit"]))
        require(
            sample["text"] + " " + sample["unit"] == text,
            "display rounding/unit mismatch",
        )
        if status == "stale":
            text += " · Stale"
    else:
        text = (
            {
                "unavailable": "Unavailable",
                "failed": "Failed",
                "warming_up": "Warming up",
            }[status]
            + " · "
            + SYMBOLS[sensor["unit"]]
        )
    require(sample["status"] == status, "display availability/stale mismatch")
    if reading["reason"] is not None:
        text += " · " + reading["reason"]
    expected = (
        monitor["title"]
        + " · "
        + ("" if entry["element_id"].endswith(":summary") else sensor["title"] + " · ")
        + text
    )
    require(entry["label"] == expected, "independent displayed GPU label mismatch")
    return expected


def native_elements(frame):
    require(
        frame["complete"] is True and frame["elements"], "truncated/empty native census"
    )
    identified = [e for e in frame["elements"] if e.get("identifier")]
    require(
        len({e["identifier"] for e in identified}) == len(identified),
        "ambiguous native identifier",
    )
    return {e["identifier"]: e for e in identified if visible(e)}


def action_effect(action, policy):
    name = action["name"]
    before, after = native_elements(action["before"]), native_elements(action["after"])
    a, b = action["state_before"], action["state_after"]
    mid = policy["device"]["monitor_id"]
    target = action["target"]
    if name == "restore":
        require(
            a == b and action["before"]["target_pid"] != action["after"]["target_pid"],
            "restore did not restart with identical saved preferences",
        )
        return
    selected = resolve_selector(action["before"]["elements"], action["selector"])
    require(
        selected == action["resolved_element"],
        "native resolved object differs from retained census",
    )
    selector = action["selector"]
    if name in ("panel-collapse", "sensor-collapse", "meter"):
        require(
            selector.get("within")
            == mid + ("" if name == "panel-collapse" else ":viewport"),
            "native action scope is not physical GPU",
        )
    after_rows = [
        e
        for e in action["after"]["elements"]
        if e.get("object_key") == selected["object_key"] and visible(e)
    ]
    visibly_changed = len(after_rows) == 1 and any(
        selected.get(k) != after_rows[0].get(k)
        for k in ("title", "description", "value")
    )
    if name == "panel-collapse":
        require(
            target == mid + ":collapse"
            and a["panels"][mid]["collapsed"] != b["panels"][mid]["collapsed"],
            "panel collapse did not change saved panel state",
        )
        require(
            visibly_changed,
            "panel control did not visibly change",
        )
    elif name in ("sensor-collapse", "meter"):
        prefix = mid + (":row:" if name == "sensor-collapse" else ":meter:")
        require(target.startswith(prefix), "action did not target a GPU sensor")
        sid = target[len(prefix) :]
        require(
            sid in {f["sensor_id"] for f in policy["fields"]},
            "action sensor outside independent inventory",
        )
        if name == "meter":
            require(
                selector.get("after") == mid + ":value:" + sid,
                "native selector targets another GPU sensor",
            )
        else:
            rows = action["before"]["elements"]
            start = rows.index(selected) + 1
            next_value = next(
                (
                    e["identifier"]
                    for e in rows[start:]
                    if e["identifier"].startswith(mid + ":value:")
                ),
                None,
            )
            require(
                next_value == mid + ":value:" + sid,
                "native row control targets another GPU sensor",
            )
        key = "collapsed" if name == "sensor-collapse" else "meter"
        old, new = (
            a["panels"][mid]["sensors"][sid][key],
            b["panels"][mid]["sensors"][sid][key],
        )
        require(old != new, "sensor action did not change its saved preference")
        if name == "meter":
            field = next(f for f in policy["fields"] if f["sensor_id"] == sid)
            allowed = {
                "Capacity": {"number", "bar"},
                "Counter": {"number", "sparkline"},
                "Percentage": {"number", "line", "bar", "sparkline", "radial"},
                "Temperature": {"number", "sparkline", "line", "radial"},
            }.get(field["kind"], {"number", "sparkline", "line"})
            require(new in allowed, "incompatible restored meter")
            require(
                visibly_changed,
                "meter choice not visibly changed",
            )
    elif name == "interval":
        require(
            a["interval_ms"] != b["interval_ms"]
            and b["interval_ms"] in (500, 1000, 2000, 5000)
            and target == "workspace:interval:" + str(b["interval_ms"]),
            "sampling interval did not change",
        )
    elif name == "scroll":
        require(
            any(
                before[k]["frame"] != after[k]["frame"]
                for k in before.keys() & after.keys()
            )
            or before.keys() != after.keys(),
            "scroll changed no native position/visibility",
        )
    else:
        raise AssertionError("unknown native action")


def validate_display(actions, diagnostics, policy):
    required = {f["sensor_id"] for f in policy["fields"]}
    seen = set()
    require(diagnostics, "no retained consumed snapshots")
    for action in actions:
        action_effect(action, policy)
        for side in ("before", "after"):
            native = action[side]
            validate_native_geometry(native)
            require(
                native["census_monitor"] == policy["device"]["monitor_id"],
                "native census has wrong GPU scope",
            )
            for element in native["elements"]:
                if element.get("children_excluded"):
                    identifier = element["identifier"]
                    require(
                        identifier.endswith(":viewport")
                        and identifier
                        not in (
                            "workspace:viewport",
                            policy["device"]["monitor_id"] + ":viewport",
                        ),
                        "GPU/workspace subtree excluded from native census",
                    )
            elements = native_elements(native)
            clock = native["clock_anchor"]
            lo = clock["unix_ns"] + native["observed_ns"] - clock["monotonic_after_ns"]
            hi = clock["unix_ns"] + native["observed_ns"] - clock["monotonic_before_ns"]
            candidates = [
                f
                for f in diagnostics
                if f["application_pid"] == native["target_pid"]
                and 0 <= lo - f["accepted_unix_ns"]
                and hi - f["accepted_unix_ns"] <= policy["freshness_ns"]
            ]
            require(
                candidates,
                "no fresh PID-matched diagnostic for actual native observation",
            )
            for identifier, element in elements.items():
                if not identifier.startswith(
                    policy["device"]["monitor_id"] + ":value:"
                ):
                    continue
                matched = False
                for frame in candidates:
                    entries = [
                        e for e in frame["rendered"] if e["element_id"] == identifier
                    ]
                    if len(entries) != 1:
                        continue
                    entry = entries[0]
                    expected = expected_gpu_label(
                        frame, entry, action["state_" + side]["interval_ms"]
                    )
                    if expected in [
                        element.get(k) for k in ("title", "description", "value")
                    ]:
                        seen.add(entry["sensor_id"])
                        matched = True
                        break
                require(
                    matched,
                    "visible GPU value lacks independently matching consumed snapshot",
                )
    require(
        required <= seen,
        "required native GPU labels never visibly observed: "
        + str(sorted(required - seen)),
    )
    return seen
