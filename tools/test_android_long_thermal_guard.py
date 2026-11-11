import unittest
from run_android_long_thermal_guard import parse_battery


class ThermalWatchdogTests(unittest.TestCase):
    def test_normal_battery(self):
        self.assertEqual(parse_battery("  level: 83\n  temperature: 368\n"),(368,83))
        self.assertEqual(parse_battery("temperature: 420\nlevel: 40"),(420,40))

    def test_unavailable_or_corrupt(self):
        for text in ("level: 90", "temperature: 420", "temperature: 999\nlevel: 85",
                     "temperature: -1\nlevel: 90", "temperature: 440\nlevel: 120"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):parse_battery(text)


if __name__=="__main__":
    unittest.main()
