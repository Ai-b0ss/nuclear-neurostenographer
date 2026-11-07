"""Copy beside controller.py/config.json; launch without taking a desktop window."""
from pathlib import Path
import runpy
import sys
import traceback

root = Path(__file__).resolve().parent
with (root / "daemon.log").open("a", encoding="utf-8", buffering=1) as log:
    sys.stdout = log
    sys.stderr = log
    sys.argv = [str(root / "controller.py"), "--config", str(root / "config.json"), "watch"]
    try:
        runpy.run_path(str(root / "controller.py"), run_name="__main__")
    except SystemExit as error:
        if error.code not in (None, 0):
            traceback.print_exc()
    except BaseException:
        traceback.print_exc()
