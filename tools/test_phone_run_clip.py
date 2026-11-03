"""Parsing of the app status line used by phone_run_clip.py (authored text, not a device run)."""
import unittest

import phone_run_clip


class TimingTests(unittest.TestCase):
    def test_finished_run_message_is_parsed(self):
        message = ("ASR вернул 4 фрагментов. Аудио: 42237 мс; загрузка 6269 мс; обработка 16219 мс. "
                   "Диаризация: 2 кластеров, 63522 мс; неопределённость и перекрытия сохраняются.")
        timings = phone_run_clip.parse_timings(message)
        self.assertEqual((timings["fragments"], timings["clusters"], timings["total_ms"]), (4, 2, 86010))
        self.assertEqual(timings["rtf"], 2.04)

    def test_progress_and_error_messages_are_not_finished_runs(self):
        for text in ("Распознавание 3/5. Отмена — после текущего фрагмента.", "Недостаточно RAM. Попробуйте более короткую запись.", ""):
            self.assertIsNone(phone_run_clip.parse_timings(text))

    def test_done_pattern_stops_on_errors_too(self):
        self.assertTrue(phone_run_clip.DONE.match("Недостаточно RAM. Попробуйте более короткую запись."))
        self.assertFalse(phone_run_clip.DONE.match("Распознавание 1/5."))


if __name__ == "__main__":
    unittest.main()
