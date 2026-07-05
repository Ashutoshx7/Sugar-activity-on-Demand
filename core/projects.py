# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""List and reopen previously generated activity projects.

The generation pipeline writes each project to
``~/.sugar/default/aod/projects/<Name>.activity/`` with an
``aod_plan.json`` describing what was built.  The studio's home screen
uses this module to show that gallery and to rebuild the state needed
to reopen a project in the studio.
"""

import glob
import json
import os

from sugar3 import env

from core.spec import ActivitySpec


def get_projects_root(root_path=None):
    return root_path or env.get_profile_path(
        os.path.join('aod', 'projects'))


def list_generated_projects(root_path=None):
    """Return generated projects, newest first.

    A directory counts as a project when its ``aod_plan.json`` parses
    to a dict; anything unreadable or malformed is skipped so one
    damaged project cannot hide the rest.
    """
    root = get_projects_root(root_path)
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return []

    projects = []
    for entry in entries:
        project_path = os.path.join(root, entry)
        if not os.path.isdir(project_path):
            continue
        plan_path = os.path.join(project_path, 'aod_plan.json')
        try:
            with open(plan_path, encoding='utf-8') as plan_file:
                plan = json.load(plan_file)
            mtime = os.path.getmtime(plan_path)
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(plan, dict):
            continue

        name = plan.get('name') or _name_from_dirname(entry)
        icon_path = os.path.join(project_path, 'activity', 'activity.svg')
        if not os.path.isfile(icon_path):
            icon_path = ''
        bundles = sorted(
            glob.glob(os.path.join(project_path, 'dist', '*.xo')),
            key=_safe_mtime,
        )
        projects.append({
            'project_path': project_path,
            'name': name,
            'template': plan.get('template', ''),
            'category': plan.get('category', ''),
            'summary': plan.get('summary', ''),
            'license': plan.get('license', ''),
            'provider': plan.get('provider', ''),
            'model': plan.get('model', ''),
            'mtime': mtime,
            'icon_path': icon_path,
            'bundle_path': bundles[-1] if bundles else '',
            'plan': plan,
        })

    projects.sort(key=lambda project: project['mtime'], reverse=True)
    return projects


def build_spec_from_plan(plan):
    """Rebuild an ActivitySpec for a project whose session is gone.

    The plan has no prompt, so the summary (or name) stands in; that is
    enough for restore_generation_result, which never validates the
    spec.
    """
    return ActivitySpec(
        name=plan.get('name', ''),
        prompt=plan.get('summary') or plan.get('name', ''),
        category=plan.get('category', ''),
        license_id=plan.get('license', 'MIT'),
        template=plan.get('template', 'auto'),
        age_band=plan.get('age_band', 'all'),
        learner_goal=plan.get('learner_goal', ''),
    )


def find_session_for_project(project_path, sessions):
    """Return (session, revision) whose revision produced project_path.

    Walks revisions newest-first so reopening lands on the latest
    revision of the project.  Returns None when no session matches.
    """
    for session in sessions:
        for revision in reversed(list(session.revisions or [])):
            summary = getattr(revision, 'result_summary', None) or {}
            if summary.get('project_path') == project_path:
                return session, revision
    return None


def _name_from_dirname(entry):
    name = entry
    if name.endswith('.activity'):
        name = name[:-len('.activity')]
    return name


def _safe_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0
