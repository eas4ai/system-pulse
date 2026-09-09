"""Independent KDE cancellation evidence when polkit reports generic denial."""

import json
import subprocess
import time

from performance_compare import require


def cancellation_witness(agent, authority, identity):
    messages = [row.get("MESSAGE", "") for row in agent]
    require(messages.count("Initiating authentication") == 1,
            "cancellation observation contains missing or overlapping dialogs")
    require("Completed:  true" not in messages, "authentication succeeded during cancellation")
    cancelled = [int(row["__REALTIME_TIMESTAMP"]) for row in agent
                 if row.get("MESSAGE") == "Dialog cancelled"]
    subject = f"for unix-process:{identity['pid']}:{identity['start_time_ticks']} "
    denied = [int(row["__REALTIME_TIMESTAMP"]) for row in authority
              if subject in row.get("MESSAGE", "") and
              "FAILED to authenticate" in row["MESSAGE"] and
              "org.freedesktop.policykit.exec" in row["MESSAGE"]]
    pairs = [(cancel, denial) for cancel in cancelled for denial in denied
             if abs(cancel - denial) <= 1_000_000]
    require(bool(pairs), "no OS cancellation witness for this application identity")
    cancel, denial = pairs[0]
    return {"agent": "polkit-kde-auth", "application_identity": identity,
            "dialog_cancelled_us": cancel, "authorization_failed_us": denial}


def observe_cancellation(identity, since):
    until = time.time()
    records = []
    for command in ("polkit-kde-auth", "polkitd"):
        output = subprocess.run(
            ["/usr/bin/journalctl", "--output=json", "--no-pager", "--quiet", "-n", "1000",
             "--since", f"@{since:.6f}", "--until", f"@{until:.6f}", f"_COMM={command}"],
            capture_output=True, text=True, timeout=10, check=True)
        rows = [json.loads(line) for line in output.stdout.splitlines()]
        require(len(rows) < 1000, "cancellation journal exceeded its observation bound")
        records.append(rows)
    return cancellation_witness(*records, identity)
