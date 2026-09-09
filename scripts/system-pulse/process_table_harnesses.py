"""Native process-table observer dependencies, shared with receipt validation."""

HARNESSES = {
    "linux": ("process_table_linux.py", "native_driver.py", "tabbed_driver.py",
              "host_accuracy.py", "native_contract.py", "native_observations.py", "tabbed_contract.py",
              "application_replay.py"),
    "macos": ("process_table_macos.py", "performance_tree.swift", "performance_macos.py",
              "performance_preserve.py", "performance_compare.py"),
}
