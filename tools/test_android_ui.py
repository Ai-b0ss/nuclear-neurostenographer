"""Selector/scroll negatives; authored XML only, not Android execution."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from run_android_ui import AndroidUi

ROOT = Path(__file__).resolve().parents[1]


class UiSelectorTests(unittest.TestCase):
    def test_bounds_and_tree_derived_swipe(self):
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            ui = AndroidUi(Path(tmp))
            root = ET.fromstring('<hierarchy><node scrollable="true" bounds="[100,200][900,1800]" /></hierarchy>')
            commands = []
            ui.shell = lambda *args: commands.append(args)
            self.assertTrue(ui.scroll(root, True))
            self.assertEqual(commands, [("input", "swipe", "500", "1400", "500", "600", "350")])
            for bounds in ["", "[0,0][0,10]", "[-1,0][2,4]", "bad"]:
                with self.assertRaises(ValueError):
                    ui.bounds(ET.fromstring(f'<node bounds="{bounds}"/>'))

    def test_missing_label_scrolls_before_explicit_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            ui = AndroidUi(Path(tmp))
            root = ET.fromstring('<hierarchy><node scrollable="true" bounds="[100,200][900,1800]" /></hierarchy>')
            ui.find = lambda **kwargs: (root, None)
            commands = []
            ui.shell = lambda *args: commands.append(args)
            with self.assertRaises(AssertionError):
                ui.visible("missing authored control")
            self.assertEqual(len(commands), 11)


if __name__ == "__main__":
    unittest.main()
