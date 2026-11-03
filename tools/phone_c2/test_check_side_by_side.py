"""Side-by-side manifest rules on hand-written manifests; no APK, device or emulator."""
import unittest

from check_side_by_side import check, manifest_facts

NS = 'xmlns:android="http://schemas.android.com/apk/res/android"'


def app(package, label, extra=""):
    return manifest_facts(f"""<manifest {NS} package="{package}">
  <uses-permission android:name="android.permission.RECORD_AUDIO"/>
  <application android:label="{label}">
    <service android:name=".DiarizationService" android:process=":diarization"/>
    <provider android:name="androidx.startup.InitializationProvider" android:authorities="{package}.androidx-startup"/>
    {extra}
  </application>
</manifest>""")


def test_apk(package, target):
    return manifest_facts(f"""<manifest {NS} package="{package}">
  <instrumentation android:name="androidx.test.runner.AndroidJUnitRunner" android:targetPackage="{target}"/>
  <application/>
</manifest>""")


MAIN = "ru.neurostenographer.app"
C2 = MAIN + ".c2"


class SideBySide(unittest.TestCase):
    def good(self):
        return app(MAIN, "Нейро-стенографист"), test_apk(MAIN + ".test", MAIN), app(C2, "Нейро-стенографист C2"), test_apk(C2 + ".test", C2)

    def test_separate_package_passes(self):
        self.assertEqual(check(*self.good()), [])

    def test_same_package_is_the_data_loss_case(self):
        main, main_test, _, _ = self.good()
        problems = check(main, main_test, app(MAIN, "Нейро-стенографист C2"), test_apk(MAIN + ".test", MAIN))
        self.assertTrue(any("is not ru.neurostenographer.app.c2" in p for p in problems))
        self.assertTrue(any("collide" in p for p in problems))

    def test_test_apk_aimed_at_the_contest_app_fails(self):
        main, main_test, prototype, _ = self.good()
        problems = check(main, main_test, prototype, test_apk(C2 + ".test", MAIN))
        self.assertTrue(any("Prototype test APK targets ru.neurostenographer.app," in p for p in problems))

    def test_hard_coded_authority_fails(self):
        main, main_test, _, prototype_test = self.good()
        fixed = '<provider android:name="x.FileProvider" android:authorities="ru.neurostenographer.files"/>'
        problems = check(app(MAIN, "A", fixed), main_test, app(C2, "B", fixed), prototype_test)
        self.assertTrue(any("Shared provider authority" in p for p in problems))

    def test_absolute_process_internet_and_label(self):
        main, main_test, _, prototype_test = self.good()
        bad = app(C2, "Нейро-стенографист", '<service android:name=".X" android:process="ru.shared"/>')
        internet = manifest_facts(f'<manifest {NS} package="{MAIN}"><uses-permission android:name="android.permission.INTERNET"/>'
                                  '<application android:label="Нейро-стенографист"/></manifest>')
        problems = check(internet, main_test, bad, prototype_test)
        self.assertTrue(any("absolute process" in p for p in problems))
        self.assertTrue(any("requests INTERNET" in p for p in problems))
        self.assertTrue(any("same launcher label" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
