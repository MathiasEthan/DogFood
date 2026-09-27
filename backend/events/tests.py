from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from .models import (
    Event,
    Team,
    TeamMember,
    EventRubric,
    ProjectSubmission,
    ProjectEvaluation,
    EvaluationScore,
    JudgeAssignment,
    EvaluationAuditLog,
)

User = get_user_model()


class EventAndTeamTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organizer = User.objects.create_user(
            username='org_user',
            email='org@example.com',
            password='Password123!',
            role=User.Role.ORGANIZER,
        )
        self.participant1 = User.objects.create_user(
            username='part1',
            email='part1@example.com',
            password='Password123!',
            role=User.Role.PARTICIPANT,
        )
        self.participant2 = User.objects.create_user(
            username='part2',
            email='part2@example.com',
            password='Password123!',
            role=User.Role.PARTICIPANT,
        )
        self.participant3 = User.objects.create_user(
            username='part3',
            email='part3@example.com',
            password='Password123!',
            role=User.Role.PARTICIPANT,
        )

        now = timezone.now()
        self.event = Event.objects.create(
            title='AI Genesis Hackathon',
            description='Build the future of artificial intelligence in 48 hours.',
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=3),
            mode='virtual',
            prize_pool='$25,000',
            max_team_size=2,  # set to 2 to test capacity
            created_by=self.organizer,
        )

        self.events_url = reverse('event_list_create')
        self.event_detail_url = reverse('event_detail', kwargs={'pk': self.event.pk})
        self.create_team_url = reverse('team_create', kwargs={'pk': self.event.pk})
        self.join_team_url = reverse('team_join', kwargs={'pk': self.event.pk})
        self.leave_team_url = reverse('team_leave', kwargs={'pk': self.event.pk})

    def test_organizer_can_create_event(self):
        self.client.force_authenticate(user=self.organizer)
        now = timezone.now()
        data = {
            'title': 'CyberDefend 2026',
            'description': 'Security & Zero-knowledge hackathon.',
            'start_date': (now + timedelta(days=5)).isoformat(),
            'end_date': (now + timedelta(days=7)).isoformat(),
            'mode': 'in_person',
            'location': 'San Francisco, CA',
            'prize_pool': '$50,000',
            'max_team_size': 4,
        }
        res = self.client.post(self.events_url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], 'CyberDefend 2026')
        self.assertEqual(res.data['created_by_username'], 'org_user')

    def test_participant_cannot_create_event(self):
        self.client.force_authenticate(user=self.participant1)
        now = timezone.now()
        data = {
            'title': 'Unauthorized Hackathon',
            'description': 'Should be rejected',
            'start_date': (now + timedelta(days=1)).isoformat(),
            'end_date': (now + timedelta(days=2)).isoformat(),
        }
        res = self.client.post(self.events_url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_events(self):
        res = self.client.get(self.events_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['title'], 'AI Genesis Hackathon')

    def test_participant_creates_team_and_gets_code(self):
        self.client.force_authenticate(user=self.participant1)
        data = {'name': 'Neural Ninjas'}
        res = self.client.post(self.create_team_url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('team', res.data)
        team = res.data['team']
        self.assertEqual(team['name'], 'Neural Ninjas')
        self.assertTrue(team['code'].startswith('HACK-'))
        self.assertEqual(team['member_count'], 1)
        self.assertEqual(team['leader_username'], 'part1')

    def test_second_participant_joins_team_with_code(self):
        # Participant 1 creates team
        self.client.force_authenticate(user=self.participant1)
        create_res = self.client.post(self.create_team_url, {'name': 'Quantum Coders'}, format='json')
        team_code = create_res.data['team']['code']

        # Participant 2 joins with code
        self.client.force_authenticate(user=self.participant2)
        join_res = self.client.post(self.join_team_url, {'code': team_code}, format='json')
        self.assertEqual(join_res.status_code, status.HTTP_200_OK)
        self.assertEqual(join_res.data['team']['member_count'], 2)

        # Verify members list
        members = [m['username'] for m in join_res.data['team']['members']]
        self.assertIn('part1', members)
        self.assertIn('part2', members)

    def test_invalid_team_code_rejected(self):
        self.client.force_authenticate(user=self.participant2)
        res = self.client.post(self.join_team_url, {'code': 'NON-EXISTENT'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_join_two_teams_in_same_event(self):
        # Participant 1 creates Team A
        self.client.force_authenticate(user=self.participant1)
        res_a = self.client.post(self.create_team_url, {'name': 'Team Alpha'}, format='json')

        # Participant 1 tries to create another team in same event
        res_dup = self.client.post(self.create_team_url, {'name': 'Team Beta'}, format='json')
        self.assertEqual(res_dup.status_code, status.HTTP_400_BAD_REQUEST)

        # Participant 2 creates Team B
        self.client.force_authenticate(user=self.participant2)
        res_b = self.client.post(self.create_team_url, {'name': 'Team Beta'}, format='json')
        team_b_code = res_b.data['team']['code']

        # Participant 1 tries to join Team B with code
        self.client.force_authenticate(user=self.participant1)
        res_join = self.client.post(self.join_team_url, {'code': team_b_code}, format='json')
        self.assertEqual(res_join.status_code, status.HTTP_400_BAD_REQUEST)

    def test_team_capacity_limit_enforced(self):
        # Event max_team_size is 2
        self.client.force_authenticate(user=self.participant1)
        create_res = self.client.post(self.create_team_url, {'name': 'Duo Team'}, format='json')
        code = create_res.data['team']['code']

        # Participant 2 joins (fills capacity to 2/2)
        self.client.force_authenticate(user=self.participant2)
        join_res = self.client.post(self.join_team_url, {'code': code}, format='json')
        self.assertEqual(join_res.status_code, status.HTTP_200_OK)

        # Participant 3 tries to join full team
        self.client.force_authenticate(user=self.participant3)
        overflow_res = self.client.post(self.join_team_url, {'code': code}, format='json')
        self.assertEqual(overflow_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('capacity', overflow_res.data['detail'])

    def test_leave_team(self):
        self.client.force_authenticate(user=self.participant1)
        create_res = self.client.post(self.create_team_url, {'name': 'Solo Team'}, format='json')
        
        leave_res = self.client.post(self.leave_team_url)
        self.assertEqual(leave_res.status_code, status.HTTP_200_OK)
        
        # Verify team deleted since leader was sole member
        self.assertFalse(Team.objects.filter(name='Solo Team').exists())

    def test_leader_can_submit_and_edit_project_before_deadline(self):
        # Participant 1 creates team
        self.client.force_authenticate(user=self.participant1)
        self.client.post(self.create_team_url, {'name': 'Devfolian Team'}, format='json')

        submit_url = reverse('project_submit', kwargs={'pk': self.event.pk})
        submission_data = {
            'title': 'AI Copilot Engine',
            'tagline': 'Autonomous developer tooling for fast prototyping',
            'problem_statement': 'Developers waste 40% of time writing boilerplate.',
            'solution_description': 'Agentic AI compiler that writes unit tests and schemas.',
            'github_url': 'https://github.com/example/ai-copilot',
            'demo_url': 'https://aicopilot.demo.app',
            'presentation_url': 'https://slides.google.com/deck123',
            'tech_stack': 'Django, Next.js, PyTorch',
        }

        # First submission
        res = self.client.post(submit_url, submission_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['submission']['title'], 'AI Copilot Engine')
        self.assertEqual(res.data['submission']['submitted_by_username'], 'part1')

        # Leader edits submission before deadline
        updated_data = dict(submission_data)
        updated_data['title'] = 'AI Copilot Engine v2'
        res_edit = self.client.post(submit_url, updated_data, format='json')
        self.assertEqual(res_edit.status_code, status.HTTP_200_OK)
        self.assertEqual(res_edit.data['submission']['title'], 'AI Copilot Engine v2')

    def test_non_leader_cannot_submit_project(self):
        # Participant 1 creates team
        self.client.force_authenticate(user=self.participant1)
        res_team = self.client.post(self.create_team_url, {'name': 'Shared Team'}, format='json')
        code = res_team.data['team']['code']

        # Participant 2 joins
        self.client.force_authenticate(user=self.participant2)
        self.client.post(self.join_team_url, {'code': code}, format='json')

        # Participant 2 (non-leader) tries to submit
        submit_url = reverse('project_submit', kwargs={'pk': self.event.pk})
        res = self.client.post(submit_url, {
            'title': 'Unauthorized Submission',
            'tagline': 'Attempt by member',
            'problem_statement': 'Test',
            'solution_description': 'Test',
            'github_url': 'https://github.com/example/test',
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only the team leader', res.data['detail'])

    def test_cannot_submit_after_deadline(self):
        # Set event end_date to the past
        self.event.end_date = timezone.now() - timedelta(hours=1)
        self.event.save()

        self.client.force_authenticate(user=self.participant1)
        self.client.post(self.create_team_url, {'name': 'Late Team'}, format='json')

        submit_url = reverse('project_submit', kwargs={'pk': self.event.pk})
        res = self.client.post(submit_url, {
            'title': 'Too Late Project',
            'tagline': 'Past deadline',
            'problem_statement': 'Test',
            'solution_description': 'Test',
            'github_url': 'https://github.com/example/test',
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('deadline', res.data['detail'])


class RubricAndJudgingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organizer = User.objects.create_user(
            username='org_judge_lead',
            email='orglead@example.com',
            password='Password123!',
            role=User.Role.ORGANIZER,
        )
        self.judge1 = User.objects.create_user(
            username='judge_ada',
            email='ada@example.com',
            password='Password123!',
            role=User.Role.JUDGE,
        )
        self.judge2 = User.objects.create_user(
            username='judge_alan',
            email='alan@example.com',
            password='Password123!',
            role=User.Role.JUDGE,
        )
        self.participant = User.objects.create_user(
            username='hacker_bob',
            email='bob@example.com',
            password='Password123!',
            role=User.Role.PARTICIPANT,
        )

        now = timezone.now()
        self.event = Event.objects.create(
            title='Web3 & AI Nexus',
            description='Build decentralized AI applications.',
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=2),
            mode='virtual',
            prize_pool='$10,000',
            max_team_size=4,
            created_by=self.organizer,
        )
        self.event.judges.add(self.judge1, self.judge2)

        self.rubric1 = EventRubric.objects.create(
            event=self.event,
            title='Innovation & Creativity',
            description='Novelty and uniqueness of the idea',
            weight=40.0,
            max_score=10,
        )
        self.rubric2 = EventRubric.objects.create(
            event=self.event,
            title='Technical Execution',
            description='Architecture and implementation depth',
            weight=30.0,
            max_score=10,
        )
        self.rubric3 = EventRubric.objects.create(
            event=self.event,
            title='UI/UX & Presentation',
            description='User journey and clarity of demo',
            weight=30.0,
            max_score=10,
        )

        self.team = Team.objects.create(
            name='Quantum Builders',
            event=self.event,
            leader=self.participant,
        )
        TeamMember.objects.create(team=self.team, user=self.participant)

        self.submission = ProjectSubmission.objects.create(
            team=self.team,
            title='NeuroMesh AI',
            tagline='Decentralized Neural Interface',
            problem_statement='Centralized AI clouds are fragile and opaque.',
            solution_description='Peer-to-peer compute lattice for local inference.',
            github_url='https://github.com/example/neuromesh',
            demo_url='https://neuromesh.demo',
            submitted_by=self.participant,
            is_draft=False,
        )

        self.rubrics_url = reverse('event_rubrics', kwargs={'pk': self.event.pk})
        self.eval_url = reverse(
            'submission_evaluate',
            kwargs={'event_pk': self.event.pk, 'sub_pk': self.submission.pk},
        )
        self.leaderboard_url = reverse('event_leaderboard', kwargs={'pk': self.event.pk})

    def test_organizer_can_create_rubric(self):
        self.client.force_authenticate(user=self.organizer)
        data = {
            'title': 'Impact & Scalability',
            'description': 'Real-world utility and adoption potential',
            'weight': 20.0,
            'max_score': 10,
        }
        res = self.client.post(self.rubrics_url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], 'Impact & Scalability')
        self.assertEqual(res.data['weight'], 20.0)

    def test_participant_cannot_create_rubric(self):
        self.client.force_authenticate(user=self.participant)
        res = self.client.post(
            self.rubrics_url,
            {'title': 'Rogue Rubric', 'weight': 50.0},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_judge_evaluates_with_weighted_score(self):
        self.client.force_authenticate(user=self.judge1)
        data = {
            'scores': [
                {'rubric': self.rubric1.id, 'score': 8},   # 8 * 40% = 3.2
                {'rubric': self.rubric2.id, 'score': 9},   # 9 * 30% = 2.7
                {'rubric': self.rubric3.id, 'score': 7},   # 7 * 30% = 2.1 => total 8.0
            ],
            'feedback': 'Great architecture and solid live demo!',
        }
        res = self.client.post(self.eval_url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['evaluation']['total_score'], 8.0)
        self.assertEqual(res.data['evaluation']['feedback'], 'Great architecture and solid live demo!')
        self.assertEqual(res.data['evaluation']['judge_username'], 'judge_ada')
        self.assertEqual(len(res.data['evaluation']['scores']), 3)

        # GET evaluation pre-fill
        get_res = self.client.get(self.eval_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(get_res.data['evaluation'])
        self.assertEqual(get_res.data['evaluation']['total_score'], 8.0)

    def test_judge_re_evaluation_updates_idempotently(self):
        self.client.force_authenticate(user=self.judge1)
        # First score: all 5s => 5.0
        self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 5},
                    {'rubric': self.rubric2.id, 'score': 5},
                    {'rubric': self.rubric3.id, 'score': 5},
                ],
                'feedback': 'Initial review',
            },
            format='json',
        )
        self.assertEqual(ProjectEvaluation.objects.filter(submission=self.submission).count(), 1)

        # Update scores: all 10s => 10.0
        update_res = self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 10},
                    {'rubric': self.rubric2.id, 'score': 10},
                    {'rubric': self.rubric3.id, 'score': 10},
                ],
                'feedback': 'Revised review: Outstanding presentation',
            },
            format='json',
        )
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_res.data['evaluation']['total_score'], 10.0)
        # Verify still only 1 ProjectEvaluation record exists for this judge-submission pair
        self.assertEqual(ProjectEvaluation.objects.filter(submission=self.submission).count(), 1)

    def test_leaderboard_aggregate_scores(self):
        # Judge 1 scores 8.0
        self.client.force_authenticate(user=self.judge1)
        self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 8},
                    {'rubric': self.rubric2.id, 'score': 9},
                    {'rubric': self.rubric3.id, 'score': 7},
                ],
            },
            format='json',
        )

        # Judge 2 scores: 10*0.4 + 8*0.3 + 9*0.3 = 4.0 + 2.4 + 2.7 = 9.1
        self.client.force_authenticate(user=self.judge2)
        self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 10},
                    {'rubric': self.rubric2.id, 'score': 8},
                    {'rubric': self.rubric3.id, 'score': 9},
                ],
            },
            format='json',
        )

        # Anti-anchoring: nobody but the organizer sees standings before publication
        self.client.force_authenticate(user=None)
        hidden = self.client.get(self.leaderboard_url)
        self.assertEqual(hidden.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.judge1)
        self.assertEqual(self.client.get(self.leaderboard_url).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.organizer)
        pub = self.client.post(reverse('admin_publish_results', kwargs={'pk': self.event.pk}), {'published': True}, format='json')
        self.assertEqual(pub.status_code, status.HTTP_200_OK)

        # Once published, the public sees standings with anonymized judges
        self.client.force_authenticate(user=None)
        res = self.client.get(self.leaderboard_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        labels = [e['judge_label'] for e in res.data[0]['evaluations']]
        self.assertEqual(labels, ['Judge A', 'Judge B'])
        self.assertNotIn('judge_username', res.data[0]['evaluations'][0])
        self.assertEqual(len(res.data), 1)

        entry = res.data[0]
        self.assertEqual(entry['submission_title'], 'NeuroMesh AI')
        self.assertEqual(entry['evaluations_count'], 2)
        self.assertEqual(entry['raw_score'], 8.55)
        self.assertIsNotNone(entry['normalized_score'])
        self.assertGreater(entry['normalized_score'], 5.0)

    def test_unauthorized_user_cannot_evaluate(self):
        self.client.force_authenticate(user=self.participant)
        res = self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 10},
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_score_outside_1_to_10_rejected(self):
        self.client.force_authenticate(user=self.judge1)
        res = self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 15},  # > 10
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('range of 1 to 10', res.data['detail'])

    def test_conflict_of_interest_blocked(self):
        # Appoint the participant (author/team leader) as a judge
        self.event.judges.add(self.participant)
        self.client.force_authenticate(user=self.participant)

        # Attempt to evaluate their own project
        res = self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 10},
                    {'rubric': self.rubric2.id, 'score': 10},
                    {'rubric': self.rubric3.id, 'score': 10},
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Conflict of Interest', res.data['detail'])

    def test_audit_log_created_and_outlier_flagged(self):
        # Judge 1 scores high: 9.0
        self.client.force_authenticate(user=self.judge1)
        self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 9},
                    {'rubric': self.rubric2.id, 'score': 9},
                    {'rubric': self.rubric3.id, 'score': 9},
                ],
            },
            format='json',
        )
        self.assertEqual(EvaluationAuditLog.objects.filter(submission=self.submission).count(), 1)
        audit1 = EvaluationAuditLog.objects.filter(submission=self.submission).first()
        self.assertFalse(audit1.is_outlier)

        # Judge 2 scores an extreme low outlier: 2.0 (difference |2.0 - 9.0| = 7.0 >= 3.0)
        self.client.force_authenticate(user=self.judge2)
        res2 = self.client.post(
            self.eval_url,
            {
                'scores': [
                    {'rubric': self.rubric1.id, 'score': 2},
                    {'rubric': self.rubric2.id, 'score': 2},
                    {'rubric': self.rubric3.id, 'score': 2},
                ],
            },
            format='json',
        )
        self.assertTrue(res2.data.get('is_outlier'))
        audit2 = EvaluationAuditLog.objects.filter(submission=self.submission, judge=self.judge2).first()
        self.assertTrue(audit2.is_outlier)
        self.assertEqual(audit2.action, EvaluationAuditLog.Action.FLAGGED)

    def test_auto_assign_judges_algorithm(self):
        assign_url = reverse('admin_assign_judges', kwargs={'pk': self.event.pk})
        self.client.force_authenticate(user=self.organizer)

        res = self.client.post(assign_url, {'k_per_project': 2}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        self.assertGreaterEqual(res.data['total_assignments_created'], 1)

        # Verify assignments in DB
        assignments = JudgeAssignment.objects.filter(event=self.event)
        self.assertGreaterEqual(assignments.count(), 1)
        # Ensure no participant is assigned to judge their own team
        for a in assignments:
            self.assertNotEqual(a.judge, self.participant)

    def test_csv_export_endpoints(self):
        # Leaderboard CSV
        lb_url = reverse('admin_export_leaderboard_csv', kwargs={'pk': self.event.pk})
        # Exports are organizer/admin only
        self.assertEqual(self.client.get(lb_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(user=self.judge1)
        self.assertEqual(self.client.get(lb_url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.organizer)
        res_lb = self.client.get(lb_url)
        self.assertEqual(res_lb.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', res_lb['Content-Type'])
        content_lb = b"".join(res_lb.streaming_content).decode('utf-8')
        self.assertIn('Rank,Submission ID,Project Title', content_lb)
        self.assertIn('NeuroMesh AI', content_lb)

        # Rubrics CSV
        rb_url = reverse('admin_export_rubrics_csv', kwargs={'pk': self.event.pk})
        res_rb = self.client.get(rb_url)
        self.assertEqual(res_rb.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', res_rb['Content-Type'])

    def test_judging_progress_endpoint(self):
        prog_url = reverse('admin_judging_progress', kwargs={'pk': self.event.pk})
        self.client.force_authenticate(user=self.organizer)
        res = self.client.get(prog_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('summary', res.data)
        self.assertIn('judges', res.data)
        self.assertEqual(res.data['summary']['total_submissions'], 1)
        self.assertEqual(res.data['summary']['total_judges'], 2)



