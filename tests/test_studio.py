# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later

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


class TestStudioDecoupling(unittest.TestCase):

    def test_panel_imports_without_any_jarabe_module(self):
        code = (
            'import sys\n'
            'import ui.panel\n'
            'import ui.window\n'
            'import main\n'
            'bad = [m for m in sys.modules if m.startswith("jarabe")]\n'
            'assert not bad, "jarabe leaked into standalone studio: %s" '
            '% bad\n'
        )
        completed = subprocess.run(
            [sys.executable, '-c', code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            0, completed.returncode,
            'decoupling check failed:\n%s%s'
            % (completed.stdout, completed.stderr))

    def test_clean_generation_error_text_strips_pipeline_prefixes(self):
        from ui.panel import _clean_generation_error_text

        self.assertEqual(
            'Drawing requests must use a Gtk.DrawingArea draw surface.',
            _clean_generation_error_text(
                'Provider could not generate valid activity code: '
                'Provider generated code did not pass validation: '
                'Drawing requests must use a Gtk.DrawingArea draw '
                'surface.'))
        self.assertEqual(
            'attempt_limit_reached: validation still failed',
            _clean_generation_error_text(
                'Provider could not repair activity code: '
                'attempt_limit_reached: validation still failed'))
        self.assertEqual('plain message',
                         _clean_generation_error_text('plain message'))
        self.assertEqual('', _clean_generation_error_text(None))


_OFFSCREEN_SCRIPT = '''
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ui.panel import CreateAIActivityPanel

window = Gtk.OffscreenWindow()
panel = CreateAIActivityPanel()
window.add(panel)
window.show_all()
panel.reset_view()
while Gtk.events_pending():
    Gtk.main_iteration_do(False)

assert panel._stack.get_visible_child_name() == 'home', \\
    panel._stack.get_visible_child_name()

panel.append_prompt_text('a fractions quiz for kids')
panel.cancel_generation()
while Gtk.events_pending():
    Gtk.main_iteration_do(False)

# Destroy the panel before the OffscreenWindow. GTK's OffscreenWindow
# segfaults if it disposes this widget tree itself during its own
# teardown; a real Gtk.Window (and the running app) tears the same panel
# down cleanly, so this is a harness-only teardown detail, not an app bug.
panel.destroy()
window.destroy()
print('OFFSCREEN-OK')
'''


_OFFSCREEN_HOME_SCRIPT = '''
import json
import os
import tempfile

sugar_home = tempfile.mkdtemp(prefix='aod-studio-home-test-')
os.environ['SUGAR_HOME'] = sugar_home

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ui.panel import CreateAIActivityPanel


def pump():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


window = Gtk.OffscreenWindow()
panel = CreateAIActivityPanel()
window.add(panel)
window.show_all()
panel.reset_view()
pump()

assert panel._stack.get_visible_child_name() == 'home'
assert panel._home_empty_box.get_visible()
assert len(panel._home_ring_icons) == 0

assert panel._enhance_button is not None
assert panel._selected_options['enhance'] == 'on'

# "Create new" now opens the prompt directly (the MODIFY/CREATE chooser
# was removed), so the stack goes straight to the create view.
panel._CreateAIActivityPanel__home_create_new_cb(None)
pump()
assert panel._stack.get_visible_child_name() == 'create'

panel._CreateAIActivityPanel__back_to_home_cb(None)
pump()
assert panel._stack.get_visible_child_name() == 'home'

project_dir = os.path.join(
    sugar_home, 'default', 'aod', 'projects', 'Demo.activity')
os.makedirs(os.path.join(project_dir, 'activity'))
with open(os.path.join(project_dir, 'aod_plan.json'), 'w',
          encoding='utf-8') as plan_file:
    json.dump({'name': 'Demo Activity', 'template': 'grid'}, plan_file)
with open(os.path.join(project_dir, 'activity', 'activity.svg'), 'w',
          encoding='utf-8') as icon_file:
    icon_file.write('<svg xmlns="http://www.w3.org/2000/svg"/>')

panel._refresh_home_projects()
pump()
assert len(panel._home_ring_icons) == 1
assert panel._home_ring.get_visible()
assert not panel._home_empty_box.get_visible()

# Destroy the panel first: see the note in _OFFSCREEN_SCRIPT above.
panel.destroy()
window.destroy()
print('OFFSCREEN-HOME-OK')
'''


_OFFSCREEN_TARGET_SCRIPT = '''
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ui.panel import CreateAIActivityPanel

window = Gtk.OffscreenWindow()
panel = CreateAIActivityPanel()
window.add(panel)
window.show_all()
panel.reset_view()
while Gtk.events_pending():
    Gtk.main_iteration_do(False)

# A click inside a canvas maps to a named 3x3 zone plus exact percentages.
assert panel._live_edit_zone(0, 0, 200, 100)[0] == 'top-left'
assert panel._live_edit_zone(100, 50, 200, 100)[0] == 'centre'
assert panel._live_edit_zone(200, 100, 200, 100)[0] == 'bottom-right'
zone, px, py = panel._live_edit_zone(150, 25, 200, 100)
assert zone == 'top-right', zone
assert (px, py) == (75, 25), (px, py)

# The description carries the zone and clamped percentages...
desc = panel._describe_canvas_point(
    'drawing canvas', 180, 20, (0, 0), (200, 100))
assert 'drawing canvas' in desc and 'top-right' in desc, desc
assert '90%' in desc and '20%' in desc, desc
# ...and the widget origin is subtracted before measuring.
desc2 = panel._describe_canvas_point(
    'drawing canvas', 60, 60, (40, 40), (40, 40))
assert '50%, 50%' in desc2, desc2

# Target kind drives the note the refinement backend receives.
panel._set_live_edit_target('drawing canvas - centre (50%, 50%)', kind='point')
assert panel._live_edit_target_kind == 'point'
assert not panel._live_edit_target_is_region
assert 'precise spot' in panel._preview_target_note()

panel._set_live_edit_target('area 10%, 10%', is_region=True)
assert panel._live_edit_target_kind == 'region'
assert 'dragged a selection' in panel._preview_target_note()

panel._set_live_edit_target('button: Clear')
assert panel._live_edit_target_kind == 'widget'
assert 'clicked this specific part' in panel._preview_target_note()

# Picking a target now returns (desc, widget, origin, size); nothing under
# the pointer yields a clean 4-tuple of Nones rather than crashing.
result = panel._pick_live_edit_target_at(window, -100, -100)
assert isinstance(result, tuple) and len(result) == 4, result
assert result[1] is None

panel.destroy()
window.destroy()
print('OFFSCREEN-TARGET-OK')
'''


_OFFSCREEN_ASK_BAR_SCRIPT = '''
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ui.panel import CreateAIActivityPanel

window = Gtk.OffscreenWindow()
panel = CreateAIActivityPanel()
window.add(panel)
window.show_all()
panel.reset_view()
while Gtk.events_pending():
    Gtk.main_iteration_do(False)

assert panel._ask_bar_entry is not None, 'ask bar entry missing'

# The ask bar must submit without depending on the removed live-edit
# entry (which is always None now).
calls = []
panel._submit_refinement_from_prompt = (
    lambda text, source='chat': calls.append((source, text)))
send = panel._CreateAIActivityPanel__ask_bar_send_cb

panel._live_edit_enabled = False
panel._ask_bar_entry.set_text('make the score bigger')
send(None)
assert panel._ask_bar_entry.get_text() == '', 'entry not cleared after send'

panel._live_edit_enabled = True
panel._ask_bar_entry.set_text('change the button colour')
send(None)

# Blank input must not submit.
panel._ask_bar_entry.set_text('   ')
send(None)

assert calls == [
    ('chat', 'make the score bigger'),
    ('preview', 'change the button colour'),
], calls

panel.destroy()
window.destroy()
print('OFFSCREEN-ASKBAR-OK')
'''


@unittest.skipUnless(
    _gtk_display_available(), 'needs a usable display server')
class TestStudioOffscreen(unittest.TestCase):

    def _run_offscreen(self, script):
        clean_env = _clean_gtk_env()
        try:
            return subprocess.run(
                [sys.executable, '-c', script],
                cwd=REPO_ROOT,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired as expired:
            self.fail('offscreen script timed out:\n%s\n%s'
                      % (expired.stdout, expired.stderr))

    def test_home_gallery_empty_state_and_refresh(self):
        completed = self._run_offscreen(_OFFSCREEN_HOME_SCRIPT)
        self.assertEqual(
            0, completed.returncode,
            'offscreen home test failed:\n%s%s'
            % (completed.stdout, completed.stderr))
        self.assertIn('OFFSCREEN-HOME-OK', completed.stdout)

    def test_panel_starts_on_home_and_survives_lifecycle(self):
        # Sanitized-env subprocess: snap/IDE shells leak
        # LD_LIBRARY_PATH/GTK_PATH values that make GTK hang, and a
        # subprocess isolates GTK state from other tests.
        completed = self._run_offscreen(_OFFSCREEN_SCRIPT)
        self.assertEqual(
            0, completed.returncode,
            'offscreen smoke failed:\n%s%s'
            % (completed.stdout, completed.stderr))
        self.assertIn('OFFSCREEN-OK', completed.stdout)

    def test_ask_bar_submits_in_both_modes(self):
        completed = self._run_offscreen(_OFFSCREEN_ASK_BAR_SCRIPT)
        self.assertEqual(
            0, completed.returncode,
            'ask bar test failed:\n%s%s'
            % (completed.stdout, completed.stderr))
        self.assertIn('OFFSCREEN-ASKBAR-OK', completed.stdout)

    def test_live_edit_targets_a_precise_canvas_point(self):
        completed = self._run_offscreen(_OFFSCREEN_TARGET_SCRIPT)
        self.assertEqual(
            0, completed.returncode,
            'offscreen target test failed:\n%s%s'
            % (completed.stdout, completed.stderr))
        self.assertIn('OFFSCREEN-TARGET-OK', completed.stdout)


if __name__ == '__main__':
    unittest.main()
