"""Protocol and packaging checks. Standard library only:

    python3 -m unittest discover -s tests -v

The byte strings are the examples published by the ELK-BLEDOB reference
implementation (github.com/8none1/elk-bledob), so a change that drifts from the
real protocol fails here before it reaches a controller.
"""

import json
import os
import asyncio
import re
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import elk  # noqa: E402
import cli  # noqa: E402

# The daemon imports bleak at module level; dispatch() never touches it, so a
# stub lets these tests run without the virtualenv. It is only in place for the
# import.
_stub = "bleak" not in sys.modules
if _stub:
    sys.modules["bleak"] = types.SimpleNamespace(BleakClient=None, BleakScanner=None)
try:
    import daemon  # noqa: E402
finally:
    if _stub:
        del sys.modules["bleak"]


def h(s):
    return bytes.fromhex(s)


class Frames(unittest.TestCase):
    def test_power(self):
        self.assertEqual(elk.cmd_power(True), h("7e 07 04 ff 00 01 02 01 ef"))
        self.assertEqual(elk.cmd_power(False), h("7e 07 04 00 00 00 02 01 ef"))

    def test_colour(self):
        self.assertEqual(elk.cmd_color(255, 0, 0), h("7e 07 05 03 ff 00 00 10 ef"))
        self.assertEqual(elk.cmd_color(0, 255, 0), h("7e 07 05 03 00 ff 00 10 ef"))
        self.assertEqual(elk.cmd_color(0, 0, 255), h("7e 07 05 03 00 00 ff 10 ef"))

    def test_brightness(self):
        self.assertEqual(elk.cmd_brightness(50), h("7e 04 01 32 01 ff 02 01 ef"))
        self.assertEqual(elk.cmd_brightness(100), h("7e 04 01 64 01 ff 02 01 ef"))

    def test_brightness_and_speed_are_clamped(self):
        self.assertEqual(elk.cmd_brightness(250)[3], 100)
        self.assertEqual(elk.cmd_brightness(-5)[3], 0)
        self.assertEqual(elk.cmd_speed(999)[3], 100)

    def test_effect_and_speed(self):
        self.assertEqual(elk.cmd_mode(0x93), h("7e 07 03 93 03 ff ff 00 ef"))
        self.assertEqual(elk.cmd_speed(100), h("7e 07 02 64 ff ff ff 00 ef"))

    def test_every_frame_is_9_bytes_in_the_envelope(self):
        for fr in (elk.cmd_power(True), elk.cmd_color(1, 2, 3),
                   elk.cmd_brightness(10), elk.cmd_mode(0x88), elk.cmd_speed(5)):
            self.assertEqual(len(fr), 9)
            self.assertEqual((fr[0], fr[-1]), (0x7E, 0xEF))


class Effects(unittest.TestCase):
    def test_table_is_the_contiguous_verified_range(self):
        ids = sorted(elk.NAMED_MODES.values())
        self.assertEqual(ids, list(range(0x87, 0x9C + 1)))
        self.assertEqual(len(set(elk.NAMED_MODES)), 22)


class Menu(unittest.TestCase):
    def rows(self):
        return json.loads("{" + cli.menu_snippet().rstrip(",") + "}")

    def test_snippet_is_valid_json_with_every_effect(self):
        rows = self.rows()
        actions = " ".join(r.get("action", "") for r in rows.values())
        for name in elk.NAMED_MODES:
            self.assertIn(f"mode {name}", actions)

    def test_every_parent_exists(self):
        rows = self.rows()
        for key in rows:
            if "." in key:
                self.assertIn(key.rsplit(".", 1)[0], rows, key)

    def test_actions_point_into_this_checkout(self):
        # Paths are generated from wherever the plugin is installed, never
        # hardcoded.
        for key, row in self.rows().items():
            if "action" in row:
                self.assertTrue(row["action"].startswith(ROOT + os.sep), key)


class FakeController(daemon.Controller):
    """A Controller whose writes are recorded instead of sent over BLE."""

    def __init__(self, fail=False):
        super().__init__(None)
        self.sent, self.fail = [], fail

    async def write(self, data):
        if self.fail:
            raise RuntimeError("controller not found")
        self.sent.append(data)


class PowerState(unittest.TestCase):
    def ask(self, ctl, line):
        return asyncio.run(daemon.dispatch(ctl, line.split()))

    def test_unknown_until_the_first_command(self):
        self.assertEqual(self.ask(FakeController(), "status"), "ok disconnected unknown")

    def test_on_and_off(self):
        ctl = FakeController()
        self.ask(ctl, "off")
        self.assertEqual(self.ask(ctl, "status"), "ok disconnected off")
        self.ask(ctl, "on")
        self.assertEqual(self.ask(ctl, "status"), "ok disconnected on")

    def test_colour_and_mode_mean_on(self):
        for line in ("color ff0000", "mode 135", "mode 135 40"):
            ctl = FakeController()
            self.ask(ctl, "off")
            self.ask(ctl, line)
            self.assertEqual(self.ask(ctl, "status"), "ok disconnected on", line)

    def test_brightness_and_speed_say_nothing_about_power(self):
        for line in ("speed 50", "bright 80"):
            ctl = FakeController()
            self.ask(ctl, "off")
            self.ask(ctl, line)
            self.assertEqual(self.ask(ctl, "status"), "ok disconnected off", line)
            fresh = FakeController()
            self.ask(fresh, line)
            self.assertEqual(self.ask(fresh, "status"), "ok disconnected unknown", line)

    def test_failed_write_leaves_power_alone(self):
        ctl = FakeController(fail=True)
        ctl.power = True
        with self.assertRaises(RuntimeError):   # handle() turns this into "err ..."
            self.ask(ctl, "off")
        self.assertEqual(self.ask(ctl, "status"), "ok disconnected on")

    def test_status_and_ping_do_not_write(self):
        ctl = FakeController()
        self.ask(ctl, "status"); self.ask(ctl, "ping")
        self.assertEqual(ctl.sent, [])


class Packaging(unittest.TestCase):
    def test_manifest(self):
        with open(os.path.join(ROOT, "manifest.json")) as f:
            m = json.load(f)
        self.assertEqual(m["schemaVersion"], 1)
        self.assertRegex(m["id"], r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
        self.assertFalse(m["id"].startswith("omarchy."))      # reserved namespace
        self.assertEqual(m["kinds"], ["bar-widget"])
        self.assertTrue(os.path.isfile(os.path.join(ROOT, m["entryPoints"]["barWidget"])))

    def test_manifest_version_matches_changelog(self):
        with open(os.path.join(ROOT, "manifest.json")) as f:
            version = json.load(f)["version"]
        with open(os.path.join(ROOT, "CHANGELOG.md")) as f:
            # First versioned heading, so a leading "## Unreleased" is skipped.
            top = re.search(r"^## \[?v?(\d+\.\d+\.\d+)", f.read(), re.M)
        self.assertIsNotNone(top, "CHANGELOG.md has no versioned heading")
        self.assertEqual(version, top.group(1))

    def test_no_machine_specific_values_in_tracked_sources(self):
        bad = re.compile(r"/home/darkxxx|BE:27:65")
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for name in files:
                if name.endswith((".py", ".qml", ".sh", ".json", ".md")) and name != "test_protocol.py":
                    with open(os.path.join(base, name), errors="ignore") as f:
                        self.assertIsNone(bad.search(f.read()), os.path.join(base, name))


if __name__ == "__main__":
    unittest.main()
