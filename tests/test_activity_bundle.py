# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The studio is itself a launchable Sugar activity.

These tests guard the bundle metadata, icon, entry class, and — crucially —
that every runtime package is git-tracked so bundlebuilder ships it in the
.xo (an untracked file silently drops out and the ring shows "Failed to
start").
"""

import configparser
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_GTK_SANITIZED_VARS = (
    'LD_LIBRARY_PATH', 'GTK_PATH', 'GIO_MODULE_DIR',
    'GDK_PIXBUF_MODULE_FILE', 'GTK_EXE_PREFIX', 'GTK_IM_MODULE_FILE',
)


def _clean_gtk_env():
    return {
        key: value for key, value in os.environ.items()
        if key not in _GTK_SANITIZED_VARS
    }


def _gtk_display_available():
    if not (os.environ.get('DISPLAY') or
            os.environ.get('WAYLAND_DISPLAY')):
        return False
    probe = (
        'import gi\n'
        'gi.require_version("Gtk", "3.0")\n'
        'from gi.repository import Gtk\n'
        'result = Gtk.init_check()\n'
        'available = result[0] if isinstance(result, tuple) else result\n'
        'raise SystemExit(0 if available else 1)\n'
    )
    try:
        completed = subprocess.run(
            [sys.executable, '-c', probe],
            cwd=REPO_ROOT,
            env=_clean_gtk_env(),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


class TestActivityInfo(unittest.TestCase):

    def _read_info(self):
        parser = configparser.ConfigParser()
        parser.read(os.path.join(REPO_ROOT, 'activity', 'activity.info'))
        return parser

    def test_activity_info_parses_with_activity_section(self):
        parser = self._read_info()
        self.assertTrue(parser.has_section('Activity'))

    def test_exec_launches_the_studio_activity_class(self):
        parser = self._read_info()
        exec_line = parser.get('Activity', 'exec')
        self.assertTrue(
            exec_line.startswith('sugar-activity3 '),
            'exec must launch through sugar-activity3: %r' % exec_line)
        self.assertEqual('sugar-activity3 activity.StudioActivity',
                         exec_line)

    def test_required_metadata_fields(self):
        parser = self._read_info()
        self.assertEqual('org.sugarlabs.SugarActivityStudio',
                         parser.get('Activity', 'bundle_id'))
        self.assertEqual('activity', parser.get('Activity', 'icon'))
        self.assertEqual('1', parser.get('Activity', 'max_participants'))
        self.assertTrue(parser.get('Activity', 'name').strip())
        self.assertTrue(parser.get('Activity', 'summary').strip())
        self.assertTrue(parser.getint('Activity', 'activity_version') >= 1)


class TestActivityIcon(unittest.TestCase):

    def test_icon_is_a_recolorable_sugar_icon(self):
        with open(os.path.join(REPO_ROOT, 'activity', 'activity.svg'),
                  encoding='utf-8') as icon:
            svg = icon.read()
        # Sugar recolors activity icons through these two entities; without
        # them the icon renders in fixed colors and looks wrong in the ring.
        self.assertIn('&stroke_color;', svg)
        self.assertIn('&fill_color;', svg)
        self.assertIn('!ENTITY stroke_color', svg)
        self.assertIn('!ENTITY fill_color', svg)
        self.assertIn('viewBox="0 0 55 55"', svg)


class TestBundleContents(unittest.TestCase):

    def test_all_runtime_files_are_git_tracked(self):
        # bundlebuilder packages exactly `git ls-files`; anything untracked
        # never reaches the .xo and the activity fails to start.
        tracked = set(subprocess.run(
            ['git', 'ls-files'],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.split())
        required = [
            'activity.py',
            'setup.py',
            'main.py',
            os.path.join('activity', 'activity.info'),
            os.path.join('activity', 'activity.svg'),
        ]
        for path in required:
            self.assertIn(path, tracked,
                          '%s must be committed to ship in the .xo' % path)
        # Every runtime package the entry point imports must be present.
        for package in ('ui', 'core', 'service', 'llm', 'generation',
                        'preview', 'exports', 'data'):
            self.assertTrue(
                any(f.startswith(package + '/') for f in tracked),
                'no tracked files under %s/ — bundle would miss it' % package)


_INSTANTIATE_SCRIPT = '''
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

# Replace the real Activity base (needs D-Bus/the shell) and the toolbar
# widgets with lightweight stubs BEFORE importing the entry module, so we
# can build StudioActivity headless. This mirrors preview/runner.py.
import sugar3.activity.activity as _act
import sugar3.activity.widgets as _widgets


class _StubActivity(Gtk.Window):
    def __init__(self, handle):
        Gtk.Window.__init__(self)
        self._canvas = None
        self._toolbar_box = None
        self.max_participants = 1

    def set_canvas(self, canvas):
        self._canvas = canvas

    def get_canvas(self):
        return self._canvas

    def set_toolbar_box(self, toolbar_box):
        self._toolbar_box = toolbar_box

    def close(self):
        pass


_act.Activity = _StubActivity
_widgets.ActivityToolbarButton = lambda activity_: Gtk.ToolButton()
_widgets.StopButton = lambda activity_: Gtk.ToolButton()

import activity as studio  # the new bundle entry module

instance = studio.StudioActivity(handle=None)
while Gtk.events_pending():
    Gtk.main_iteration_do(False)

assert instance.get_canvas() is not None, 'StudioActivity set no canvas'

bad = [m for m in sys.modules if m.startswith('jarabe')]
assert not bad, 'jarabe leaked into the activity entry: %s' % bad

print('ACTIVITY-OK')
'''


@unittest.skipUnless(
    _gtk_display_available(), 'needs a usable display server')
class TestStudioActivityInstantiation(unittest.TestCase):

    def test_studio_activity_builds_canvas_without_jarabe(self):
        completed = subprocess.run(
            [sys.executable, '-c', _INSTANTIATE_SCRIPT],
            cwd=REPO_ROOT,
            env=_clean_gtk_env(),
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.assertEqual(
            0, completed.returncode,
            'activity instantiation failed:\n%s%s'
            % (completed.stdout, completed.stderr))
        self.assertIn('ACTIVITY-OK', completed.stdout)


if __name__ == '__main__':
    unittest.main()
