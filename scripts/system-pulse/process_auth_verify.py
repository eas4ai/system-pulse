"""Validate native authentication outcomes and their source provenance."""

from performance_compare import require
from performance_verify import check_harness, same_production
from process_table_harnesses import HARNESSES


def validate_authentication(record, platform):
    require(record.get("status") == "PASS" and record.get("platform") == platform,
            "native authentication did not pass on the required platform")
    require(type(record.get("ui_uid")) is int and record["ui_uid"] > 0 and
            type(record.get("ui_pid")) is int and record["ui_pid"] > 1,
            "native authentication did not verify an unprivileged UI")
    require(record.get("remaining_bounded_fixtures") == [] and
            not record.get("cleanup_errors") and not record.get("error"),
            "native authentication left fixtures or failed cleanup")
    cases = record["cases"]
    require([case["case"] for case in cases] == ["cancel", "terminate", "kill", "expired"],
            "missing native authentication cases")
    for case in cases:
        identity = case["identity"]
        require(type(identity.get("pid")) is int and identity["pid"] > 1 and
                type(identity.get("start_time_ticks")) is int and identity["start_time_ticks"] > 0 and
                identity.get("uid") == 0 and identity["pid"] != record["ui_pid"],
                "authentication target is not an independently observed root process")
        require(case["ordinary_exit"] == 11, "ordinary action was not denied")
        cancelled = case["case"] == "cancel"
        require(case["alive"] is cancelled, "authentication outcome disagrees with target lifetime")
        prefix = ("Authentication was cancelled." if cancelled else
                  "The selected process exited" if case["case"] == "expired" else "Request sent to ")
        require(case["notice"].startswith(prefix), "native authentication notice disagrees with outcome")
        if case["case"] in ("terminate", "kill"):
            require(f"(PID {identity['pid']})" in case["notice"],
                    "native success notice names another process")
    require(cases[0]["identity"] == cases[1]["identity"],
            "cancellation and End did not observe the same fixture")
    require(len({(case["identity"]["pid"], case["identity"]["start_time_ticks"])
                 for case in cases[1:]}) == 3, "authentication reused a finished fixture")


def validate_authentication_source(record, build, platform):
    same_production(record["source_commit"])
    require(build["source_commit"] == record["source_commit"] and
            build["binary_sha256"] == record["binary_sha256"] and build["exit_code"] == 0,
            "native authentication does not match its build")
    check_harness(record["harness_sha256"],
                  {*HARNESSES[platform], "process_auth_native.py", "performance_macos.py",
                   "performance_preserve.py", "performance_compare.py", "process_table_harnesses.py"})
