# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from core.projects import build_spec_from_plan
from core.projects import find_session_for_project
from core.projects import get_projects_root
from core.projects import list_generated_projects
from service.sessions import AODRevision
from service.sessions import AODSession
from core.spec import ActivitySpec


def _write_project(root, dirname, plan, with_icon=True, with_bundle=False):
    project_path = os.path.join(root, dirname)
    os.makedirs(os.path.join(project_path, 'activity'), exist_ok=True)
    with open(os.path.join(project_path, 'aod_plan.json'), 'w',
              encoding='utf-8') as plan_file:
        json.dump(plan, plan_file)
    if with_icon:
        with open(os.path.join(project_path, 'activity', 'activity.svg'),
                  'w', encoding='utf-8') as icon_file:
            icon_file.write('<svg xmlns="http://www.w3.org/2000/svg"/>')
    if with_bundle:
        dist = os.path.join(project_path, 'dist')
        os.makedirs(dist, exist_ok=True)
        with open(os.path.join(dist, 'Demo-1.xo'), 'wb') as bundle:
            bundle.write(b'xo')
    return project_path


class TestListGeneratedProjects(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='aod-projects-test-')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_missing_root_returns_empty(self):
        self.assertEqual(
            [], list_generated_projects(os.path.join(self.root, 'nope')))

    def test_skips_corrupt_and_non_project_entries(self):
        valid = _write_project(self.root, 'Good.activity', {
            'name': 'Good Activity',
            'template': 'quiz',
            'category': 'games',
            'summary': 'A quiz about games.',
            'license': 'MIT',
        }, with_bundle=True)

        corrupt = os.path.join(self.root, 'Corrupt.activity')
        os.makedirs(corrupt)
        with open(os.path.join(corrupt, 'aod_plan.json'), 'w',
                  encoding='utf-8') as broken:
            broken.write('{not json')

        os.makedirs(os.path.join(self.root, 'NotAProject'))
        with open(os.path.join(self.root, 'stray.txt'), 'w',
                  encoding='utf-8') as stray:
            stray.write('stray')

        listed = list_generated_projects(self.root)
        self.assertEqual(1, len(listed))
        project = listed[0]
        self.assertEqual(valid, project['project_path'])
        self.assertEqual('Good Activity', project['name'])
        self.assertEqual('quiz', project['template'])
        self.assertTrue(project['icon_path'].endswith('activity.svg'))
        self.assertTrue(project['bundle_path'].endswith('.xo'))
        self.assertIsInstance(project['plan'], dict)

    def test_newest_project_first(self):
        old = _write_project(self.root, 'Old.activity', {'name': 'Old'})
        new = _write_project(self.root, 'New.activity', {'name': 'New'})
        os.utime(os.path.join(old, 'aod_plan.json'), (1000, 1000))
        os.utime(os.path.join(new, 'aod_plan.json'), (2000, 2000))

        names = [p['name'] for p in list_generated_projects(self.root)]
        self.assertEqual(['New', 'Old'], names)

    def test_name_falls_back_to_directory(self):
        _write_project(self.root, 'Fallback.activity', {}, with_icon=False)
        listed = list_generated_projects(self.root)
        self.assertEqual('Fallback', listed[0]['name'])
        self.assertEqual('', listed[0]['icon_path'])
        self.assertEqual('', listed[0]['bundle_path'])

    def test_projects_root_honors_sugar_home(self):
        with mock.patch.dict(os.environ, {'SUGAR_HOME': self.root}):
            root = get_projects_root()
        self.assertTrue(root.startswith(self.root))
        self.assertTrue(root.endswith(os.path.join('aod', 'projects')))


class TestBuildSpecFromPlan(unittest.TestCase):

    def test_full_plan(self):
        spec = build_spec_from_plan({
            'name': 'Star Counter',
            'summary': 'Count the stars.',
            'category': 'logic_math',
            'license': 'GPL-3.0-or-later',
            'template': 'grid',
            'age_band': 'ages 6-9',
            'learner_goal': 'Count to ten.',
        })
        self.assertEqual('Star Counter', spec.name)
        self.assertEqual('Count the stars.', spec.prompt)
        self.assertEqual('logic_math', spec.category)
        self.assertEqual('GPL-3.0-or-later', spec.license_id)
        self.assertEqual('grid', spec.template)

    def test_prompt_falls_back_to_name(self):
        spec = build_spec_from_plan({'name': 'Just A Name'})
        self.assertEqual('Just A Name', spec.prompt)
        self.assertEqual('MIT', spec.license_id)


class TestFindSessionForProject(unittest.TestCase):

    def _session_with_revisions(self, project_paths):
        spec = ActivitySpec(
            name='Demo', prompt='Make a demo.',
            category='games', license_id='MIT')
        session = AODSession.create(spec)
        for path in project_paths:
            session.revisions.append(AODRevision.create(
                job_id='job', prompt='p',
                result_summary={'project_path': path}))
        return session

    def test_finds_latest_matching_revision(self):
        session = self._session_with_revisions(['/a', '/b', '/b'])
        other = self._session_with_revisions(['/c'])

        match = find_session_for_project('/b', [other, session])
        self.assertIsNotNone(match)
        found_session, revision = match
        self.assertIs(session, found_session)
        self.assertIs(session.revisions[-1], revision)

    def test_no_match_returns_none(self):
        session = self._session_with_revisions(['/a'])
        self.assertIsNone(find_session_for_project('/missing', [session]))


if __name__ == '__main__':
    unittest.main()
