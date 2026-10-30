"""Selector/scroll negatives; authored XML only, not Android execution."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import json
from run_android_ui import AndroidUi, verify_saved_exports

ROOT = Path(__file__).resolve().parents[1]


class UiSelectorTests(unittest.TestCase):
    def test_selector_filters_are_conjunctive_and_ambiguity_fails(self):
        node = ET.fromstring('<node text="SAVE" class="android.widget.Button" resource-id="picker:id/save"/>')
        self.assertTrue(AndroidUi.matches(node, label="Save", exact=True, class_name="android.widget.Button"))
        self.assertFalse(AndroidUi.matches(node, label="Save", exact=True, class_name="android.widget.EditText"))
        self.assertFalse(AndroidUi.matches(node, label="different", resource_suffix=":id/save"))
        root = ET.fromstring('<hierarchy><node text="SAVE"/><node text="SAVE"/></hierarchy>')
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            ui = AndroidUi(Path(tmp))
            ui.tree = lambda: root
            with self.assertRaises(AssertionError):
                ui.find(label="Save", exact=True, timeout=0)
            root = ET.fromstring('<hierarchy><node text="Recognize" bounds="[10,20][110,80]"/><node text="Click Recognize after import"/></hierarchy>')
            ui.tree = lambda: root
            commands = []
            ui.shell = lambda *args: commands.append(args)
            ui.tap(label="Recognize")
            self.assertEqual(commands, [("input", "tap", "60", "50")])
            root = ET.fromstring('<hierarchy><node text="Downloads" resource-id="picker:id/breadcrumb_text" bounds="[0,0][100,50]"/><node text="Downloads" resource-id="android:id/title" bounds="[20,200][220,280]"/></hierarchy>')
            ui.tree = lambda: root
            commands.clear()
            ui.tap(label="Downloads", resource_suffix="android:id/title", exact=True)
            self.assertEqual(commands, [("input", "tap", "120", "240")])

    def test_saved_provider_bytes_require_consistent_real_document_structure(self):
        phrase = "у лукоморья дуб зеленый"
        pin = "a" * 64
        document = {"units": "milliseconds", "audio_duration_ms": 1000,
            "warnings": ["authored test only"],
            "provenance": {"timestamp_source": "diarization_boundaries_and_input_windows", "runtime_sha256": pin},
            "segments": [{"start_ms": 100, "end_ms": 900, "speaker_id": "Speaker 1", "text": phrase,
                          "overlapping_speech": False, "attribution_reliable": True}]}
        exports = {"json": json.dumps(document).encode(),
            "txt": ("[00:00:00.100–00:00:00.900] Speaker 1: " + phrase).encode(),
            "srt": ("1\n00:00:00,100 --> 00:00:00,900\nSpeaker 1: " + phrase).encode()}
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            for format, body in exports.items():
                (root / ("neuro-qa-ui." + format)).write_bytes(body)
            self.assertEqual(set(verify_saved_exports(exports, pin, root)), {"json", "txt", "srt"})
            with self.assertRaises(AssertionError):
                verify_saved_exports(exports, "b" * 64, root)
            for format in ["txt", "srt"]:
                (root / ("neuro-qa-ui." + format)).write_bytes(b"malformed provider output")
                with self.assertRaises(AssertionError):
                    verify_saved_exports(exports, pin, root)
                (root / ("neuro-qa-ui." + format)).write_bytes(exports[format])

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
