from unittest import mock

from django.test import TestCase
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
    WebhookEndpoint,
    WebhookDelivery,
    Certificate,
    JudgeParticipationRecord,
)

User = get_user_model()


class T4StretchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organizer = User.objects.create_user(
            username='org_t4',
            email='org_t4@example.com',
            password='Password123!',
            role=User.Role.ORGANIZER,
        )
        self.judge = User.objects.create_user(
            username='judge_t4',
            email='judge_t4@example.com',
            password='Password123!',
            role=User.Role.JUDGE,
        )
        self.participant1 = User.objects.create_user(
            username='part_t4_1',
            email='part1@example.com',
            password='Password123!',
            role=User.Role.PARTICIPANT,
        )
        self.participant2 = User.objects.create_user(
            username='part_t4_2',
            email='part2@example.com',
            password='Password123!',
            role=User.Role.PARTICIPANT,
        )

        now = timezone.now()
        self.event = Event.objects.create(
            title='T4 Stretch Hackathon',
            description='Testing T4 Stretch features.',
            start_date=now - timedelta(days=2),
            end_date=now + timedelta(days=2),
            mode='virtual',
            prize_pool='$50,000',
            max_team_size=4,
            created_by=self.organizer,
        )
        self.event.judges.add(self.judge)

        self.rubric = EventRubric.objects.create(
            event=self.event,
            title='Innovation',
            description='How creative is this?',
            weight=50.0,
            max_score=10,
        )

        self.team = Team.objects.create(
            event=self.event,
            name='Alpha Builders',
            leader=self.participant1,
            code='T4-ALPHA',
        )
        TeamMember.objects.create(team=self.team, user=self.participant1)

        self.submission = ProjectSubmission.objects.create(
            team=self.team,
            title='Autonomous Agent OS',
            tagline='AI Operating System',
            problem_statement='AI agent coordination is fractured.',
            solution_description='Unified multi-agent protocol.',
            github_url='https://github.com/alpha/os',
            demo_url='https://alpha.os.demo',
            tech_stack='Python, Django, Next.js',
            is_draft=False,
            submitted_by=self.participant1,
        )

    @mock.patch('events.webhooks.requests.post')
    @mock.patch('events.webhooks._resolve', return_value={'93.184.216.34'})
    def test_webhooks_dispatched_on_team_join_and_leave(self, _resolve, post):
        post.return_value = mock.Mock(status_code=200, text='ok')
        # Register a webhook endpoint
        endpoint = WebhookEndpoint.objects.create(
            event=self.event,
            target_url='https://example.com/webhook',
            created_by=self.organizer,
        )

        # Participant 2 joins team
        self.client.force_authenticate(user=self.participant2)
        res_join = self.client.post(f'/api/events/{self.event.id}/teams/join/', {'code': 'T4-ALPHA'}, format='json')
        self.assertEqual(res_join.status_code, status.HTTP_200_OK)

        join_delivery = WebhookDelivery.objects.filter(
            endpoint=endpoint,
            event_type=WebhookEndpoint.EventType.TEAM_JOINED,
        ).first()
        self.assertIsNotNone(join_delivery)
        self.assertEqual(join_delivery.payload['username'], 'part_t4_2')

        # Participant 2 leaves team
        res_leave = self.client.post(f'/api/events/{self.event.id}/teams/leave/')
        self.assertEqual(res_leave.status_code, status.HTTP_200_OK)

        leave_delivery = WebhookDelivery.objects.filter(
            endpoint=endpoint,
            event_type=WebhookEndpoint.EventType.TEAM_LEFT,
        ).first()
        self.assertIsNotNone(leave_delivery)
        self.assertEqual(leave_delivery.payload['username'], 'part_t4_2')

    def test_certificate_generation_and_public_verification(self):
        # Judge evaluates project first
        eval_obj = ProjectEvaluation.objects.create(
            submission=self.submission,
            judge=self.judge,
            total_score=9.5,
            feedback='Outstanding architecture!',
        )
        EvaluationScore.objects.create(
            evaluation=eval_obj,
            rubric=self.rubric,
            score=9.5,
        )

        # Organizer generates certificates (only allowed once results are published)
        self.client.force_authenticate(user=self.organizer)
        res = self.client.post(f'/api/events/{self.event.id}/admin/certificates/generate/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.event.results_published = True
        self.event.save()
        res = self.client.post(f'/api/events/{self.event.id}/admin/certificates/generate/')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(res.data['certificates_count'], 2)

        # Retrieve certificates list as organizer
        res_list = self.client.get(f'/api/events/{self.event.id}/certificates/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertGreater(len(res_list.data), 0)

        cert_item = res_list.data[0]
        cert_code = cert_item['code']
        self.assertTrue(cert_item['is_valid'])

        # Public verification endpoint (unauthenticated)
        self.client.force_authenticate(user=None)
        res_pub = self.client.get(f'/api/certificates/{cert_code}/')
        self.assertEqual(res_pub.status_code, status.HTTP_200_OK)
        self.assertTrue(res_pub.data['is_valid'])
        self.assertEqual(res_pub.data['event_title'], self.event.title)

        # Download SVG certificate
        res_svg = self.client.get(f'/api/certificates/{cert_code}/download/')
        self.assertEqual(res_svg.status_code, status.HTTP_200_OK)
        self.assertEqual(res_svg['Content-Type'], 'image/svg+xml')
        self.assertIn(b'<svg', res_svg.content)

    def test_signed_judge_participation_record_and_verification(self):
        # Create evaluation
        ProjectEvaluation.objects.create(
            submission=self.submission,
            judge=self.judge,
            total_score=8.5,
            feedback='Great demo.',
        )

        # Trigger certificate generation which signs the judge record
        self.event.results_published = True
        self.event.save()
        self.client.force_authenticate(user=self.organizer)
        self.client.post(f'/api/events/{self.event.id}/admin/certificates/generate/')

        # Judge views their own signed record
        self.client.force_authenticate(user=self.judge)
        res_my_record = self.client.get(f'/api/events/{self.event.id}/my-judge-record/')
        self.assertEqual(res_my_record.status_code, status.HTTP_200_OK)
        record_id = res_my_record.data['record_id']
        self.assertTrue(res_my_record.data['is_valid'])

        # Public verification without login
        self.client.force_authenticate(user=None)
        res_pub = self.client.get(f'/api/judges/records/{record_id}/verify/')
        self.assertEqual(res_pub.status_code, status.HTTP_200_OK)
        self.assertTrue(res_pub.data['is_valid'])
        self.assertEqual(res_pub.data['signature_algorithm'], 'Ed25519')
        self.assertEqual(res_pub.data['record']['evaluations_count'], 1)

    def test_bulk_event_export_and_import(self):
        self.client.force_authenticate(user=self.organizer)

        # 1. Export Archive
        res_export = self.client.get(f'/api/events/{self.event.id}/admin/export/bulk-archive/')
        self.assertEqual(res_export.status_code, status.HTTP_200_OK)
        archive_data = res_export.data

        self.assertIn('checksum', archive_data)
        self.assertEqual(len(archive_data['teams']), 1)
        self.assertEqual(archive_data['teams'][0]['name'], 'Alpha Builders')

        # 2. Import into a new Event
        res_import = self.client.post('/api/events/admin/import/bulk-archive/', archive_data, format='json')
        self.assertEqual(res_import.status_code, status.HTTP_201_CREATED)
        new_event_id = res_import.data['event_id']

        imported_event = Event.objects.get(id=new_event_id)
        self.assertIn('(Imported)', imported_event.title)
        self.assertEqual(imported_event.teams.count(), 1)
        self.assertEqual(imported_event.rubrics.count(), 1)

    def test_bulk_team_import_csv(self):
        self.client.force_authenticate(user=self.organizer)

        csv_content = """team_name,username,email,is_leader
Beta Squad,beta_alice,alice@beta.com,1
Beta Squad,beta_bob,bob@beta.com,0
Gamma Labs,gamma_lead,lead@gamma.com,true
"""
        res = self.client.post(
            f'/api/events/{self.event.id}/admin/import/teams-csv/',
            {'csv_content': csv_content},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['teams_created'], 2)
        self.assertEqual(res.data['members_added'], 3)

        # Verify created teams in database
        self.assertTrue(Team.objects.filter(event=self.event, name='Beta Squad').exists())
        self.assertTrue(Team.objects.filter(event=self.event, name='Gamma Labs').exists())
