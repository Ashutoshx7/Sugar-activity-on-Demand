# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Sugar activity entry point for Sugar Activity Studio.

The studio is normally launched as a standalone desktop app (main.py /
ui/window.py).  This module lets the Sugar shell launch the very same UI
from the activity ring: ``exec = sugar-activity3 activity.StudioActivity``
in activity/activity.info runs the class below, which hosts the existing
CreateAIActivityPanel as the activity canvas.

Sugar puts the bundle root on sys.path, so ``ui.panel`` imports directly.
This module depends only on the Sugar *toolkit* (sugar3.activity) and never
on the Sugar shell (jarabe), matching the constraint enforced by
tests/test_studio.py and tests/test_activity_bundle.py.
"""

import logging

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk  # noqa: E402

from sugar3.activity import activity  # noqa: E402
from sugar3.activity.widgets import ActivityToolbarButton  # noqa: E402
from sugar3.activity.widgets import StopButton  # noqa: E402
from sugar3.graphics.toolbarbox import ToolbarBox  # noqa: E402

from ui.panel import CreateAIActivityPanel  # noqa: E402


class StudioActivity(activity.Activity):
    """Host the Activity Studio panel inside the Sugar shell."""

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self.max_participants = 1

        toolbar_box = ToolbarBox()
        toolbar_box.toolbar.insert(ActivityToolbarButton(self), 0)
        toolbar_box.toolbar.insert(StopButton(self), -1)
        self.set_toolbar_box(toolbar_box)
        toolbar_box.show_all()

        self._panel = CreateAIActivityPanel()
        # The panel emits 'close-requested' from its own close affordance;
        # route it to the activity's close() so it behaves like the
        # standalone window does (ui/window.py:49-56).  The toolbar's
        # StopButton already stops the activity on its own.
        self._panel.connect('close-requested', self.__close_requested_cb)
        self.set_canvas(self._panel)
        self._panel.show()
        self._panel.reset_view()

    def __close_requested_cb(self, panel):
        try:
            panel.cancel_generation()
        except Exception:
            logging.exception('Could not cancel generation on close')
        self.close()

    def read_file(self, file_path):
        # The studio persists its own projects and sessions under
        # ~/.sugar/default/aod/ (core/projects.py, service/sessions.py), so
        # there is no per-instance Journal state to restore.
        pass

    def write_file(self, file_path):
        # Nothing instance-specific to save; overriding the toolkit default
        # (which raises NotImplementedError) keeps Journal save/stop quiet.
        pass
