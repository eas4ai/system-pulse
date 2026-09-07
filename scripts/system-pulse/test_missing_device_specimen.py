"""Check the stopped-app specimen without starting a native session."""

import ast
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class SpecimenWritten(Exception):
    """Stop at the native launch boundary after the real specimen writer ran."""


def specimen_writer(context, app):
    source = Path(__file__).with_name("native_replay.py")
    main = next(
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    case = next(
        node
        for node in main.body
        if isinstance(node, ast.FunctionDef) and node.name == "missing_device_case"
    )
    # Retain the function's real closure, including its nonlocal app assignment.
    wrapper = ast.parse("def bind(app):\n    pass\n").body[0]
    wrapper.body = [case, ast.Return(value=ast.Name(id=case.name, ctx=ast.Load()))]
    module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
    exec(compile(module, str(source), "exec"), context)
    return context["bind"](app)


class MissingDeviceSpecimenTests(unittest.TestCase):
    def setUp(self):
        self.mid = "gpu:drm:0000:03:00.0"
        self.missing = self.mid + ":saved-absent"

        def panel(mid):
            return {
                "panel_name": "TabPanel",
                "children": [
                    {
                        "panel_name": "SystemPulseMonitor",
                        "children": [],
                        "info": {"panel": {"monitor_id": mid}},
                    }
                ],
                "info": {"tabs": {"active_index": 0}},
            }

        self.captured = {
            "schema_version": 1,
            "interval_ms": 1000,
            "dock": {
                "center": {
                    "panel_name": "StackPanel",
                    "children": [panel("cpu:host"), panel(self.mid)],
                    "info": {"stack": {"axis": 1, "sizes": [280, 280]}},
                }
            },
            "panels": {
                mid: {
                    "visible": True,
                    "collapsed": False,
                    "expanded_size": {"width": 600, "height": 280},
                    "sensors": {
                        mid + "/usage": {
                            "visible": True,
                            "collapsed": True,
                            "order": 3,
                            "meter": "sparkline",
                        }
                    },
                }
                for mid in ("cpu:host", self.mid)
            },
            "monitors": {
                "cpu:host": {"id": "cpu:host", "kind": "Cpu", "title": "CPU"},
                self.mid: {"id": self.mid, "kind": "Gpu", "title": "AMD GPU"},
            },
        }

    def write_specimen(self, later):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            state = output / "state"
            state.mkdir()
            workspace = state / "workspace.json"
            workspace.write_text(json.dumps(later))
            context = dict(
                copy=copy,
                json=json,
                state=state,
                output=output,
                # Keep the former dock-only capture to detect that regression too.
                initial_dock=copy.deepcopy(self.captured["dock"]),
                missing_device_workspace=self.captured,
                args=SimpleNamespace(binary=Path("unused")),
                progress=Mock(),
                Native=Mock(side_effect=SpecimenWritten),
            )
            with self.assertRaises(SpecimenWritten):
                specimen_writer(context, Mock())({"id": self.mid})
            specimen = json.loads((output / "missing-device-config.json").read_text())
            self.assertEqual(specimen, json.loads(workspace.read_text()))
            return specimen

    def test_later_collapsed_preferences_cannot_mix_with_pre_split_dock(self):
        later = copy.deepcopy(self.captured)
        later["panels"]["cpu:host"]["collapsed"] = True
        later["panels"]["cpu:host"]["expanded_size"]["width"] = 1506
        later["panels"]["cpu:host"]["sensors"]["cpu:host/usage"]["meter"] = "number"
        later["dock"]["center"]["info"]["stack"]["sizes"][0] = 36
        later["panels"][self.mid]["visible"] = False
        saved = self.write_specimen(later)
        self.assertEqual(saved["panels"]["cpu:host"], self.captured["panels"]["cpu:host"])
        expected_dock = copy.deepcopy(self.captured["dock"])
        expected_dock["center"]["children"][1]["children"][0]["info"]["panel"][
            "monitor_id"
        ] = self.missing
        self.assertEqual(saved["dock"], expected_dock)

    def test_only_device_identity_and_original_visibility_change(self):
        before = copy.deepcopy(self.captured)
        saved = self.write_specimen(copy.deepcopy(self.captured))
        self.assertEqual(self.captured, before)
        expected_panel = before["panels"][self.mid]
        self.assertEqual(saved["panels"][self.missing], expected_panel)
        self.assertEqual(
            saved["panels"][self.mid], dict(expected_panel, visible=False)
        )
        self.assertEqual(
            saved["monitors"][self.missing],
            dict(before["monitors"][self.mid], id=self.missing),
        )
        # Undo only the authorized substitutions; all other captured data is exact.
        del saved["panels"][self.missing]
        del saved["monitors"][self.missing]
        saved["panels"][self.mid]["visible"] = True
        saved["dock"]["center"]["children"][1]["children"][0]["info"]["panel"][
            "monitor_id"
        ] = self.mid
        self.assertEqual(saved, before)
