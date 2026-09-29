"""Role isolation and judging-integrity tests (T1/T2 hardening)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Event, EventRubric, EvaluationAuditLog, JudgeAssignment, ProjectEvaluation, ProjectSubmission, Team,
    TeamMember, Track,
)

User = get_user_model()


class IsolationBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        mk = lambda name, role='participant': User.objects.create_user(  # noqa: E731
            username=name, email=f'{name}@t.com', password='pw', role=role
        )
        self.org = mk('org', 'organizer')
        self.other_org = mk('org2', 'organizer')
        self.admin = mk('admin', 'admin')
        self.j1, self.j2, self.j3, self.j4 = mk('j1', 'judge'), mk('j2', 'judge'), mk('j3', 'judge'), mk('j4', 'judge')
        self.outsider_judge = mk('jx', 'judge')
        self.p1, self.p2, self.p3 = mk('p1'), mk('p2'), mk('p3')

        now = timezone.now()
        self.event = Event.objects.create(
            title='Iso', description='d', start_date=now - timedelta(days=1), end_date=now + timedelta(days=1),
            created_by=self.org,
        )
        self.event.judges.add(self.j1, self.j2, self.j3, self.j4)
        self.r1 = EventRubric.objects.create(event=self.event, title='Innovation', weight=50, max_score=10)
        self.r2 = EventRubric.objects.create(event=self.event, title='Execution', weight=50, max_score=5)

        self.subs = []
        for p in (self.p1, self.p2, self.p3):
            team = Team.objects.create(event=self.event, name=f'team-{p.username}', leader=p)
            TeamMember.objects.create(team=team, user=p)
            self.subs.append(ProjectSubmission.objects.create(team=team, title=f'proj-{p.username}', submitted_by=p, is_draft=False))
        self.draft_team = Team.objects.create(event=self.event, name='drafty', leader=self.p3)
        self.draft = ProjectSubmission.objects.create(team=self.draft_team, title='draft', submitted_by=self.p3, is_draft=True)

    def eval_url(self, sub):
        return reverse('submission_evaluate', kwargs={'event_pk': self.event.pk, 'sub_pk': sub.pk})

    def score(self, user, sub, a=8, b=4):
        self.client.force_authenticate(user)
        return self.client.post(
            self.eval_url(sub),
            {'scores': [{'rubric': self.r1.id, 'score': a}, {'rubric': self.r2.id, 'score': b}], 'feedback': 'ok'},
            format='json',
        )


class ManagerScopeTests(IsolationBase):
    def test_other_organizer_blocked_from_everything(self):
        urls = [
            reverse('event_submissions', kwargs={'pk': self.event.pk}),
            reverse('admin_judging_progress', kwargs={'pk': self.event.pk}),
            reverse('admin_export_leaderboard_csv', kwargs={'pk': self.event.pk}),
            reverse('admin_export_rubrics_csv', kwargs={'pk': self.event.pk}),
            reverse('admin_export_feedback_csv', kwargs={'pk': self.event.pk}),
            reverse('admin_export_submissions_csv', kwargs={'pk': self.event.pk}),
            reverse('admin_export_assignments_csv', kwargs={'pk': self.event.pk}),
            reverse('admin_export_evaluation_audit_csv', kwargs={'pk': self.event.pk}),
            reverse('event_leaderboard', kwargs={'pk': self.event.pk}),
        ]
        self.client.force_authenticate(self.other_org)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(
            self.client.post(reverse('admin_assign_judges', kwargs={'pk': self.event.pk})).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse('admin_publish_results', kwargs={'pk': self.event.pk})).status_code, 403
        )
        self.client.force_authenticate(self.org)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_outside_judge_cannot_see_roster(self):
        self.client.force_authenticate(self.outsider_judge)
        self.assertEqual(self.client.get(reverse('event_submissions', kwargs={'pk': self.event.pk})).status_code, 403)

    def test_event_judge_roster_excludes_drafts(self):
        self.client.force_authenticate(self.j1)
        res = self.client.get(reverse('event_submissions', kwargs={'pk': self.event.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(self.draft.id, [s['id'] for s in res.data])

    def test_team_codes_and_judge_emails_hidden_from_public(self):
        url = reverse('event_detail', kwargs={'pk': self.event.pk})
        for user in (None, self.p1, self.other_org):
            self.client.force_authenticate(user)
            res = self.client.get(url)
            self.assertEqual(res.data['teams'], [])
            self.assertNotIn('email', res.data['event_judges'][0])
        self.client.force_authenticate(self.org)
        res = self.client.get(url)
        self.assertEqual(len(res.data['teams']), 4)
        self.assertIn('email', res.data['event_judges'][0])


class EvaluationRuleTests(IsolationBase):
    def test_organizer_who_is_not_a_judge_cannot_score(self):
        self.assertEqual(self.score(self.org, self.subs[0]).status_code, 403)

    def test_outside_judge_cannot_score(self):
        self.assertEqual(self.score(self.outsider_judge, self.subs[0]).status_code, 403)

    def test_draft_cannot_be_scored(self):
        self.assertEqual(self.score(self.j1, self.draft).status_code, 400)

    def test_every_rubric_required_and_scaled_by_max(self):
        self.client.force_authenticate(self.j1)
        res = self.client.post(self.eval_url(self.subs[0]), {'scores': [{'rubric': self.r1.id, 'score': 8}]}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Execution', res.data['detail'])
        # r2 is out of 5: 4/5 -> 8/10.  total = 0.5*8 + 0.5*8 = 8.0
        res = self.score(self.j1, self.subs[0], a=8, b=4)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['evaluation']['total_score'], 8.0)
        # 6 > max 5 for r2
        self.assertEqual(self.score(self.j2, self.subs[0], a=8, b=6).status_code, 400)
        # 0 is below the 1..max range
        self.assertEqual(self.score(self.j2, self.subs[0], a=0, b=3).status_code, 400)

    def test_assignment_restricts_judges(self):
        self.client.force_authenticate(self.org)
        res = self.client.post(reverse('admin_assign_judges', kwargs={'pk': self.event.pk}), {'k_per_project': 2}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['fully_saturated'])
        for sub in self.subs:
            assigned = set(JudgeAssignment.objects.filter(submission=sub).values_list('judge_id', flat=True))
            self.assertEqual(len(assigned), 2)
            unassigned = [j for j in (self.j1, self.j2, self.j3, self.j4) if j.id not in assigned]
            self.assertEqual(self.score(unassigned[0], sub).status_code, 403)
            judge = User.objects.get(pk=next(iter(assigned)))
            self.assertIn(self.score(judge, sub).status_code, (200, 201))
        self.event.refresh_from_db()
        self.assertEqual(self.event.judges_per_project, 2)

    def test_assignment_reports_deficit_when_not_enough_conflict_free_judges(self):
        # p1 becomes a judge of this event, then only p1 + j1 remain as judges
        self.event.judges.set([self.j1, self.p1])
        self.client.force_authenticate(self.org)
        res = self.client.post(reverse('admin_assign_judges', kwargs={'pk': self.event.pk}), {'k_per_project': 2}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['fully_saturated'])
        self.assertIn(self.subs[0].id, [d['submission_id'] for d in res.data['deficits']])
        # COI: p1 never assigned to their own project
        self.assertFalse(JudgeAssignment.objects.filter(judge=self.p1, submission=self.subs[0]).exists())

    def test_results_publication_locks_scoring_and_rubrics(self):
        self.assertEqual(self.score(self.j1, self.subs[0]).status_code, 201)
        self.client.force_authenticate(self.org)
        res = self.client.post(reverse('event_rubrics', kwargs={'pk': self.event.pk}), {'title': 'Late', 'weight': 10}, format='json')
        self.assertEqual(res.status_code, 400)
        self.client.post(reverse('admin_publish_results', kwargs={'pk': self.event.pk}), {'published': True}, format='json')
        self.assertEqual(self.score(self.j1, self.subs[0], a=2, b=1).status_code, 400)

    def test_single_review_has_unknown_standard_error(self):
        self.score(self.j1, self.subs[0])
        self.client.force_authenticate(self.org)
        res = self.client.get(reverse('event_leaderboard', kwargs={'pk': self.event.pk}))
        row = next(r for r in res.data if r['submission_id'] == self.subs[0].id)
        self.assertIsNone(row['standard_error'])

    def test_judge_assignment_queue(self):
        self.client.force_authenticate(self.org)
        self.client.post(reverse('admin_assign_judges', kwargs={'pk': self.event.pk}), {'k_per_project': 2}, format='json')
        self.client.force_authenticate(self.j1)
        res = self.client.get(reverse('my_assignments', kwargs={'pk': self.event.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['assignments_exist'])
        self.assertEqual(res.data['assigned'], JudgeAssignment.objects.filter(judge=self.j1).count())
        self.client.force_authenticate(self.p1)
        self.assertEqual(self.client.get(reverse('my_assignments', kwargs={'pk': self.event.pk})).status_code, 403)

    def test_rapid_submission_flagged_via_server_dwell_clock(self):
        JudgeAssignment.objects.create(event=self.event, judge=self.j1, submission=self.subs[0])
        self.client.force_authenticate(self.j1)
        self.client.get(self.eval_url(self.subs[0]))  # opens the project, starts the clock
        res = self.score(self.j1, self.subs[0])
        self.assertIn('RAPID_SUBMISSION', res.data['flags'])
        log = EvaluationAuditLog.objects.get(judge=self.j1)
        self.assertIsNotNone(log.dwell_seconds)

    def test_progress_dashboard_matrix(self):
        self.client.force_authenticate(self.org)
        self.client.post(reverse('admin_assign_judges', kwargs={'pk': self.event.pk}), {'k_per_project': 1}, format='json')
        a = JudgeAssignment.objects.filter(submission=self.subs[0]).first()
        self.score(a.judge, self.subs[0])
        self.client.force_authenticate(self.org)
        res = self.client.get(reverse('admin_judging_progress', kwargs={'pk': self.event.pk}))
        matrix = {p['submission_id']: p for p in res.data['projects']}
        self.assertEqual(matrix[self.subs[0].id]['saturation'], 'SATISFIED')
        self.assertEqual(matrix[self.subs[1].id]['saturation'], 'IN_PROGRESS')
        self.assertNotIn(self.draft.id, matrix)
        judge_row = next(j for j in res.data['judges'] if j['judge_id'] == a.judge_id)
        self.assertEqual(judge_row['completed'], 1)
        self.assertIsNotNone(judge_row['shrunk_mean'])


class ConflictOfInterestTests(IsolationBase):
    def test_judge_cannot_create_or_join_team(self):
        self.client.force_authenticate(self.j1)
        res = self.client.post(reverse('team_create', kwargs={'pk': self.event.pk}), {'name': 'judges'}, format='json')
        self.assertEqual(res.status_code, 403)
        code = self.subs[0].team.code
        res = self.client.post(reverse('team_join', kwargs={'pk': self.event.pk}), {'code': code}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_organizer_cannot_join_own_event_as_participant(self):
        self.client.force_authenticate(self.org)
        res = self.client.post(reverse('team_create', kwargs={'pk': self.event.pk}), {'name': 'org team'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_team_member_cannot_be_appointed_judge(self):
        self.client.force_authenticate(self.org)
        res = self.client.post(
            reverse('admin_event_judge_manage', kwargs={'pk': self.event.pk}), {'user_id': self.p2.id}, format='json'
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(self.event.judges.filter(pk=self.p2.pk).exists())

    def test_submission_track_must_belong_to_event(self):
        now = timezone.now()
        other = Event.objects.create(title='o', description='d', start_date=now, end_date=now + timedelta(days=1), created_by=self.org)
        foreign = Track.objects.create(event=other, title='Foreign')
        own = Track.objects.create(event=self.event, title='Own')
        self.client.force_authenticate(self.p1)
        url = reverse('project_submit', kwargs={'pk': self.event.pk})
        res = self.client.post(url, {'is_draft': True, 'track': foreign.id}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post(url, {'is_draft': True, 'track': own.id}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['submission']['track'], own.id)
