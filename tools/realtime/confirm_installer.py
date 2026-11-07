"""Confirm only the task's pending HONOR package installer, from observed UI bounds.
Never touches security settings, lock screens or other applications.
"""
import argparse
import re
import subprocess
import time
import xml.etree.ElementTree as ET


def confirm(adb, expected_label, seconds=80):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        active = subprocess.check_output([*adb, 'shell', 'dumpsys', 'activity', 'activities']).decode('utf-8', 'replace')
        resumed = '\n'.join(line for line in active.splitlines() if 'mResumedActivity' in line)
        if 'com.android.packageinstaller/' not in resumed:
            time.sleep(2); continue
        path = '/data/local/tmp/nn-realtime-install.xml'
        subprocess.run([*adb, 'shell', 'uiautomator', 'dump', path], capture_output=True, timeout=15, check=True)
        raw = subprocess.check_output([*adb, 'shell', 'cat', path])
        tree = ET.fromstring(raw)
        nodes = list(tree.iter('node'))
        labels = [n.get('text', '') for n in nodes if n.get('resource-id') == 'com.android.packageinstaller:id/app_name']
        if labels and labels != [expected_label]:
            # A completed prior test-APK screen may linger while the next APK is staged.
            # Do not interact with a different package; wait for our exact label.
            time.sleep(2); continue
        for node in nodes:
            text = node.get('text', '').upper()
            is_warning = any(n.get('resource-id') == 'com.android.packageinstaller:id/install_unknow_source_confirm' for n in nodes)
            if node.get('package') != 'com.android.packageinstaller' or node.get('enabled') != 'true':
                continue
            if (text == 'ПРОДОЛЖИТЬ' and is_warning) or (text == 'УСТАНОВИТЬ' and labels == [expected_label]):
                points = [int(x) for x in re.findall(r'\d+', node.get('bounds', ''))]
                if len(points) != 4 or points[2] <= points[0] or points[3] <= points[1]:
                    raise RuntimeError('Invalid observed installer bounds')
                subprocess.run([*adb, 'shell', 'input', 'tap', str((points[0] + points[2]) // 2), str((points[1] + points[3]) // 2)], check=True)
                print('Confirmed task installer control:', text, flush=True)
                if text == 'УСТАНОВИТЬ':
                    return
                break
        time.sleep(2)
    raise RuntimeError('Installer confirmation not completed within deadline')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--adb', required=True); p.add_argument('--serial', required=True); p.add_argument('--label', required=True)
    a = p.parse_args()
    confirm([a.adb, '-s', a.serial], a.label)
