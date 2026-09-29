"""T4 integrity tests: offline-verifiable signatures, certificates vs official standings, revocation,
webhook SSRF guard, invite links, and safe bulk import."""
import json
from datetime import timedelta
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Certificate, Event, EventRubric, JudgeParticipationRecord, ProjectEvaluation, ProjectSubmission, Team,
    TeamMember, WebhookDelivery, WebhookEndpoint,
)

User = get_user_model()
PUBLIC_IP = {'93.184.216.34'}


def offline_verify(public_key_hex, payload, signature_hex):
    """What a third party does: no project code, just the published public key + canonical JSON."""
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(bytes.fromhex(signature_hex), raw)
        return True
    except Exception:
        return False


class Base(TestCase):
    def setUp(self):
        self.client = APIClient()
        mk = lambda n, role='participant': User.objects.create_user(  # noqa: E731
            username=n, email=f'{n}@t.com', password='pw', role=role
        )
        self.org = mk('org', 'organizer')
        self.other_org = mk('org2', 'organizer')
        self.lenient, self.harsh, self.idle = mk('lenient', 'judge'), mk('harsh', 'judge'), mk('idle', 'judge')
        now = timezone.now()
        self.event = Event.objects.create(
            title='Integrity Hack', description='d', start_date=now - timedelta(days=3),
            end_date=now - timedelta(days=1), created_by=self.org, max_team_size=2,
        )
        self.event.judges.add(self.lenient, self.harsh, self.idle)
        EventRubric.objects.create(event=self.event, title='Overall', weight=100, max_score=10)
        self.subs = {}
        for name in 'ABCD':
            lead = mk(f'lead{name}')
            team = Team.objects.create(event=self.event, name=f'Team {name}', leader=lead)
            TeamMember.objects.create(team=team, user=lead)
            self.subs[name] = ProjectSubmission.objects.create(team=team, title=f'Project {name}', submitted_by=lead, is_draft=False)
        self.scores = {
            ('A', self.lenient): 9.0, ('C', self.lenient): 9.8, ('D', self.lenient): 9.6,
            ('B', self.harsh): 7.5, ('C', self.harsh): 3.0, ('D', self.harsh): 2.5,
        }
        for (name, judge), value in self.scores.items():
            ProjectEvaluation.objects.create(submission=self.subs[name], judge=judge, total_score=value)

    def publish_and_issue(self):
        self.event.results_published = True
        self.event.save()
        self.client.force_authenticate(self.org)
        res = self.client.post(f'/api/events/{self.event.id}/admin/certificates/generate/')
        self.assertEqual(res.status_code, 201, res.data)
        return res


class SignatureTests(Base):
    def test_records_verify_offline_with_only_the_public_key(self):
        self.publish_and_issue()
        key = self.client.get('/api/signing-key/').data
        self.assertEqual(key['algorithm'], 'Ed25519')

        self.client.force_authenticate(None)
        cert = Certificate.objects.filter(event=self.event, role='winner').first()
        pub = self.client.get(f'/api/certificates/{cert.certificate_code}/').data
        self.assertEqual(pub['status'], 'valid')
        self.assertTrue(offline_verify(key['public_key_hex'], pub['signed_payload'], pub['signature']))

        rec = JudgeParticipationRecord.objects.get(event=self.event, judge=self.lenient)
        data = self.client.get(f'/api/judges/records/{rec.record_id}/verify/').data
        self.assertTrue(data['is_valid'])
        self.assertEqual(data['signature_algorithm'], 'Ed25519')
        self.assertTrue(offline_verify(key['public_key_hex'], data['record'], data['signature']))
        self.assertEqual(data['record']['evaluations_count'], 3)
        self.assertEqual(data['record']['average_score_given'], round((9.0 + 9.8 + 9.6) / 3, 2))

        # Any change to the claims breaks offline verification
        forged = dict(data['record'], evaluations_count=99)
        self.assertFalse(offline_verify(key['public_key_hex'], forged, data['signature']))

    def test_tampered_database_row_reports_invalid(self):
        self.publish_and_issue()
        cert = Certificate.objects.filter(event=self.event, role='winner').first()
        Certificate.objects.filter(pk=cert.pk).update(signed_payload=dict(cert.signed_payload, recipient='Mallory'))
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/certificates/{cert.certificate_code}/').data['status'], 'invalid')

    def test_renaming_the_event_later_does_not_invalidate_or_change_certificates(self):
        self.publish_and_issue()
        cert = Certificate.objects.filter(event=self.event, role='winner').first()
        self.event.title = 'Renamed'
        self.event.save()
        data = APIClient().get(f'/api/certificates/{cert.certificate_code}/').data
        self.assertEqual(data['status'], 'valid')
        self.assertEqual(data['event_title'], 'Integrity Hack')


class CertificateIssuanceTests(Base):
    def test_requires_published_results_and_organizer(self):
        self.client.force_authenticate(self.org)
        self.assertEqual(self.client.post(f'/api/events/{self.event.id}/admin/certificates/generate/').status_code, 400)
        self.event.results_published = True
        self.event.save()
        self.client.force_authenticate(self.other_org)
        self.assertEqual(self.client.post(f'/api/events/{self.event.id}/admin/certificates/generate/').status_code, 403)

    def test_winner_matches_normalized_leaderboard_not_raw_average(self):
        # Raw averages put A first (9.0 from a lenient judge); normalization puts B first.
        self.publish_and_issue()
        leaderboard = APIClient().get(f'/api/events/{self.event.id}/leaderboard/').data
        self.assertEqual(leaderboard[0]['submission_title'], 'Project B')
        first = Certificate.objects.get(event=self.event, recipient_user=None, role='winner', metadata__rank=1)
        self.assertEqual(first.metadata['submission_title'], 'Project B')

    def test_reissue_revokes_superseded_certificates(self):
        self.publish_and_issue()
        old_first = Certificate.objects.get(event=self.event, recipient_user=None, metadata__rank=1)

        # Scores change (e.g. a late correction) and certificates are re-issued
        self.event.results_published = False
        self.event.save()
        ProjectEvaluation.objects.filter(submission=self.subs['B']).update(total_score=1.0)
        res = self.publish_and_issue()
        self.assertGreater(res.data['revoked_count'], 0)

        old_first.refresh_from_db()
        self.assertIsNotNone(old_first.revoked_at)
        public = APIClient().get(f'/api/certificates/{old_first.certificate_code}/').data
        self.assertEqual(public['status'], 'revoked')
        svg = APIClient().get(f'/api/certificates/{old_first.certificate_code}/download/').content
        self.assertIn(b'REVOKED', svg)
        new_first = Certificate.objects.get(event=self.event, recipient_user=None, revoked_at__isnull=True, metadata__rank=1)
        self.assertNotEqual(new_first.metadata['submission_title'], 'Project B')

    def test_reissue_is_idempotent(self):
        self.publish_and_issue()
        count = Certificate.objects.filter(event=self.event).count()
        res = self.publish_and_issue()
        self.assertEqual(res.data['revoked_count'], 0)
        self.assertEqual(Certificate.objects.filter(event=self.event).count(), count)

    def test_judges_without_evaluations_get_nothing(self):
        self.publish_and_issue()
        self.assertFalse(Certificate.objects.filter(recipient_user=self.idle).exists())
        self.assertFalse(JudgeParticipationRecord.objects.filter(judge=self.idle).exists())
        self.assertTrue(Certificate.objects.filter(recipient_user=self.lenient, role='judge').exists())

    def test_my_certificates_across_events(self):
        self.publish_and_issue()
        lead = self.subs['A'].team.leader
        self.client.force_authenticate(lead)
        res = self.client.get('/api/my-certificates/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data)
        self.assertTrue(all(c['status'] == 'valid' for c in res.data))
        self.assertNotIn('recipient_email', res.data[0])


@mock.patch('events.webhooks.requests.post')
class WebhookTests(Base):
    def url(self, suffix=''):
        return f'/api/events/{self.event.id}/webhooks/{suffix}'

    def test_rejects_internal_targets(self, post):
        self.client.force_authenticate(self.org)
        for target, resolved in [
            ('http://127.0.0.1:8000/hook', {'127.0.0.1'}),
            ('http://169.254.169.254/latest/meta-data', {'169.254.169.254'}),
            ('http://db:5432/', {'172.18.0.2'}),
            ('http://localhost/', {'::1'}),
        ]:
            with mock.patch('events.webhooks._resolve', return_value=resolved):
                res = self.client.post(self.url(), {'target_url': target}, format='json')
            self.assertEqual(res.status_code, 400, target)
        self.assertEqual(self.client.post(self.url(), {'target_url': 'ftp://x.com/'}, format='json').status_code, 400)
        post.assert_not_called()

    def test_star_means_all_events_and_test_ping(self, post):
        post.return_value = mock.Mock(status_code=200, text='ok')
        self.client.force_authenticate(self.org)
        with mock.patch('events.webhooks._resolve', return_value=PUBLIC_IP):
            res = self.client.post(self.url(), {'target_url': 'https://hooks.example.com/x', 'subscribed_events': ['*']}, format='json')
            self.assertEqual(res.status_code, 201, res.data)
            self.assertEqual(res.data['subscribed_events'], [])
            ping = self.client.post(self.url(f"{res.data['id']}/test/"))
        self.assertEqual(ping.status_code, 200)
        self.assertEqual(ping.data['status'], 'SUCCESS')
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        self.assertTrue(post.call_args.kwargs['headers']['X-DogFood-Signature'].startswith('sha256='))

    def test_blocks_at_send_time_if_dns_changes(self, post):
        endpoint = WebhookEndpoint.objects.create(event=self.event, target_url='https://rebind.example.com/', created_by=self.org)
        self.client.force_authenticate(self.org)
        with mock.patch('events.webhooks._resolve', return_value={'10.0.0.5'}):
            res = self.client.post(self.url(f'{endpoint.id}/test/'))
        self.assertEqual(res.data['status'], 'FAILED')
        self.assertIn('Blocked', WebhookDelivery.objects.get(endpoint=endpoint).response_body)
        post.assert_not_called()

    def test_event_types_listed(self, post):
        res = APIClient().get('/api/events/webhook-events/')
        values = [e['value'] for e in res.data['event_types']]
        self.assertIn('certificates.issued', values)


class InviteLinkTests(Base):
    def test_lookup_shows_team_without_member_details(self):
        team = self.subs['A'].team
        res = APIClient().get(f'/api/events/{self.event.id}/teams/lookup/', {'code': team.code.lower()})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['team_name'], 'Team A')
        self.assertNotIn('members', res.data)
        self.assertFalse(res.data['is_full'])
        self.assertEqual(APIClient().get(f'/api/events/{self.event.id}/teams/lookup/', {'code': 'NOPE'}).status_code, 404)

    def test_lookup_reports_existing_membership(self):
        team = self.subs['A'].team
        self.client.force_authenticate(team.leader)
        res = self.client.get(f'/api/events/{self.event.id}/teams/lookup/', {'code': team.code})
        self.assertTrue(res.data['already_in_a_team'])


class BulkImportSafetyTests(Base):
    def test_archive_import_never_attaches_existing_accounts(self):
        self.client.force_authenticate(self.org)
        archive = self.client.get(f'/api/events/{self.event.id}/admin/export/bulk-archive/').data
        victim = self.subs['A'].team.leader
        res = self.client.post('/api/events/admin/import/bulk-archive/', archive, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        imported = Event.objects.get(pk=res.data['event_id'])
        self.assertFalse(TeamMember.objects.filter(team__event=imported, user=victim).exists())
        placeholder = TeamMember.objects.filter(team__event=imported, team__name='Team A').first().user
        self.assertTrue(placeholder.username.startswith(victim.username))
        self.assertFalse(placeholder.has_usable_password())
        self.assertFalse(imported.results_published)

    def test_tampered_archive_rejected(self):
        self.client.force_authenticate(self.org)
        archive = dict(self.client.get(f'/api/events/{self.event.id}/admin/export/bulk-archive/').data)
        archive['event'] = dict(archive['event'], title='Evil')
        res = self.client.post('/api/events/admin/import/bulk-archive/', archive, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('checksum', res.data['detail'])

    def test_archive_survives_a_javascript_json_round_trip(self):
        """Browsers serialize 7.0 as 7; the checksum must not depend on that."""
        self.client.force_authenticate(self.org)
        archive = json.loads(json.dumps(self.client.get(f'/api/events/{self.event.id}/admin/export/bulk-archive/').data, default=str))

        def js_like(v):
            if isinstance(v, float) and v.is_integer():
                return int(v)
            if isinstance(v, dict):
                return {k: js_like(x) for k, x in v.items()}
            if isinstance(v, list):
                return [js_like(x) for x in v]
            return v

        res = self.client.post('/api/events/admin/import/bulk-archive/', js_like(archive), format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_csv_import_enforces_conflict_of_interest_and_capacity(self):
        self.client.force_authenticate(self.org)
        csv_content = 'team_name,username,is_leader\nNew Team,fresh1,1\nNew Team,lenient,0\nNew Team,fresh2,0\nNew Team,fresh3,0\n'
        res = self.client.post(f'/api/events/{self.event.id}/admin/import/teams-csv/', {'csv_content': csv_content}, format='json')
        self.assertEqual(res.status_code, 200)
        team = Team.objects.get(event=self.event, name='New Team')
        members = set(team.memberships.values_list('user__username', flat=True))
        self.assertEqual(members, {'fresh1', 'fresh2'})  # max_team_size=2, judge rejected
        reasons = ' '.join(s['reason'] for s in res.data['skipped'])
        self.assertIn('conflict of interest', reasons)
        self.assertIn('capacity', reasons)
        self.assertFalse(User.objects.get(username='fresh1').has_usable_password())
