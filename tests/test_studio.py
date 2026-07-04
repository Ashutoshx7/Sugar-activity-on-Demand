# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestStudioDecoupling(unittest.TestCase):

    def test_panel_imports_without_any_jarabe_module(self):
        code = (
            'import sys\n'
            'import aodstudio.ui.panel\n'
            'import aodstudio.ui.window\n'
            'import aodstudio.main\n'
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
        from aodstudio.ui.panel import _clean_generation_error_text

        self.assertEqual(
            'Drawing requests must use a Gtk.DrawingArea draw surface.',
            _clean_generation_error_text(
                'Provider could not generate valid activity code: '
                'Provider generated code did not pass validation: '
                'Drawing requests must use a Gtk.DrawingArea draw '
                'surface.'))
        self.assertEqual('plain message',
                         _clean_generation_error_text('plain message'))
        self.assertEqual('', _clean_generation_error_text(None))


_OFFSCREEN_SCRIPT = '''
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from aodstudio.ui.panel import CreateAIActivityPanel

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

window.destroy()
print('OFFSCREEN-OK')
'''


@unittest.skipUnless(
    os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'),
    'needs a display server')
class TestStudioOffscreen(unittest.TestCase):

    def test_panel_starts_on_chooser_and_survives_lifecycle(self):
        # Run the GTK part in a subprocess with a sanitized environment:
        # snap/IDE shells leak LD_LIBRARY_PATH/GTK_PATH values that make
        # GTK hang, and a subprocess also isolates GTK state from other
        # tests in this process.
        clean_env = {
            key: value for key, value in os.environ.items()
            if key not in ('LD_LIBRARY_PATH', 'GTK_PATH', 'GIO_MODULE_DIR',
                           'GDK_PIXBUF_MODULE_FILE', 'GTK_EXE_PREFIX',
                           'GTK_IM_MODULE_FILE')
        }
        clean_env['GDK_BACKEND'] = 'x11'
        try:
            completed = subprocess.run(
                [sys.executable, '-c', _OFFSCREEN_SCRIPT],
                cwd=REPO_ROOT,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired as expired:
            self.fail('offscreen smoke timed out:\n%s\n%s'
                      % (expired.stdout, expired.stderr))
        self.assertEqual(
            0, completed.returncode,
            'offscreen smoke failed:\n%s%s'
            % (completed.stdout, completed.stderr))
        self.assertIn('OFFSCREEN-OK', completed.stdout)


if __name__ == '__main__':
    unittest.main()
