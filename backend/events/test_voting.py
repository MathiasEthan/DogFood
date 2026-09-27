"""T3 acceptance-style tests: community voting, comments, hidden results, ordering, abuse controls, audit."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest import mock

from django.test import TestCase
from rest_framework.throttling import ScopedRateThrottle
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import CommunityComment, CommunityVote, Event, ProjectSubmission, Team, TeamMember, VoteAuditLog

User = get_user_model()


class CommunityBase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.organizer = User.objects.create_user(username='org', email='org@t.com', password='pw', role='organizer')
        self.other_org = User.objects.create_user(username='org2', email='org2@t.com', password='pw', role='organizer')
        self.admin_user = User.objects.create_user(username='admin', email='admin@t.com', password='pw', role='admin')
        self.voter = User.objects.create_user(username='voter', email='voter@t.com', password='pw', role='participant')
        self.voter2 = User.objects.create_user(username='voter2', email='voter2@t.com', password='pw', role='participant')
        self.leader = User.objects.create_user(username='leader', email='leader@t.com', password='pw', role='participant')
        self.judge = User.objects.create_user(username='judge', email='judge@t.com', password='pw', role='judge')

        now = timezone.now()
        self.event = Event.objects.create(
            title='Test Hackathon',
            description='A test event',
            start_date=now - timedelta(days=2),
            end_date=now - timedelta(hours=2),
            community_voting_start=now - timedelta(hours=1),
            community_voting_end=now + timedelta(days=1),
            show_community_voting_results=False,
            votes_per_user=2,
            created_by=self.organizer,
        )
        self.event.judges.add(self.judge)

        self.team = Team.objects.create(event=self.event, name='Team A', leader=self.leader)
        TeamMember.objects.create(team=self.team, user=self.leader)
        self.submission = ProjectSubmission.objects.create(
            team=self.team, title='Project A', submitted_by=self.leader, is_draft=False
        )
        self.subs = [self.submission]
        for i in range(2, 6):
            lead = User.objects.create_user(username=f'lead{i}', email=f'lead{i}@t.com', password='pw')
            team = Team.objects.create(event=self.event, name=f'Team {i}', leader=lead)
            TeamMember.objects.create(team=team, user=lead)
            self.subs.append(
                ProjectSubmission.objects.create(team=team, title=f'Project {i}', submitted_by=lead, is_draft=False)
            )
        draft_lead = User.objects.create_user(username='draftlead', email='dl@t.com', password='pw')
        draft_team = Team.objects.create(event=self.event, name='Draft Team', leader=draft_lead)
        self.draft = ProjectSubmission.objects.create(
            team=draft_team, title='Secret Draft', submitted_by=draft_lead, is_draft=True
        )

    def vote_url(self, sub, event=None):
        return f'/api/events/{(event or self.event).id}/submissions/{sub.id}/vote/'

    def comments_url(self, sub):
        return f'/api/events/{self.event.id}/submissions/{sub.id}/comments/'


class VotingTests(CommunityBase):
    def test_voting_requires_authentication(self):
        self.assertEqual(self.client.post(self.vote_url(self.submission)).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_voting_when_inactive(self):
        self.event.community_voting_end = timezone.now() - timedelta(minutes=1)
        self.event.save()
        self.client.force_authenticate(self.voter)
        res = self.client.post(self.vote_url(self.submission))
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['detail'], 'Voting is not active for this event.')

    def test_voting_before_window_opens(self):
        self.event.community_voting_start = timezone.now() + timedelta(hours=1)
        self.event.community_voting_end = timezone.now() + timedelta(hours=2)
        self.event.save()
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(self.vote_url(self.submission)).status_code, status.HTTP_400_BAD_REQUEST)

    def test_cast_and_withdraw_vote(self):
        self.client.force_authenticate(self.voter)
        res = self.client.post(self.vote_url(self.submission))
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['has_voted'])
        self.assertEqual(res.data['votes_remaining'], 1)
        self.assertTrue(VoteAuditLog.objects.filter(action='VOTED', voter=self.voter).exists())

        res = self.client.delete(self.vote_url(self.submission))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data['has_voted'])
        self.assertEqual(res.data['votes_remaining'], 2)
        self.assertFalse(CommunityVote.objects.filter(voter=self.voter).exists())
        self.assertTrue(VoteAuditLog.objects.filter(action='UNVOTED', voter=self.voter).exists())

    def test_withdraw_without_vote_is_404(self):
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.delete(self.vote_url(self.submission)).status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_vote_is_rejected_and_audited(self):
        self.client.force_authenticate(self.voter)
        self.client.post(self.vote_url(self.submission))
        res = self.client.post(self.vote_url(self.submission))
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(CommunityVote.objects.filter(voter=self.voter, submission=self.submission).count(), 1)
        rejected = VoteAuditLog.objects.get(action='VOTE_REJECTED', voter=self.voter)
        self.assertEqual(rejected.metadata['reason'], 'duplicate')

    def test_vote_quota_enforced(self):
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(self.vote_url(self.subs[1])).status_code, 201)
        self.assertEqual(self.client.post(self.vote_url(self.subs[2])).status_code, 201)
        res = self.client.post(self.vote_url(self.subs[3]))
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['votes_remaining'], 0)
        # Withdrawing frees a vote
        self.client.delete(self.vote_url(self.subs[1]))
        self.assertEqual(self.client.post(self.vote_url(self.subs[3])).status_code, 201)

    def test_unlimited_votes_when_quota_zero(self):
        self.event.votes_per_user = 0
        self.event.save()
        self.client.force_authenticate(self.voter)
        for sub in self.subs:
            self.assertEqual(self.client.post(self.vote_url(sub)).status_code, 201)

    def test_self_vote_blocked_by_default(self):
        self.client.force_authenticate(self.leader)
        res = self.client.post(self.vote_url(self.submission))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('own team', res.data['detail'])

    def test_self_vote_allowed_when_configured(self):
        self.event.allow_self_vote = True
        self.event.save()
        self.client.force_authenticate(self.leader)
        self.assertEqual(self.client.post(self.vote_url(self.submission)).status_code, 201)

    def test_judges_cannot_vote(self):
        self.client.force_authenticate(self.judge)
        self.assertEqual(self.client.post(self.vote_url(self.submission)).status_code, status.HTTP_403_FORBIDDEN)

    def test_registered_only_eligibility(self):
        self.event.voting_eligibility = Event.VotingEligibility.REGISTERED
        self.event.save()
        self.client.force_authenticate(self.voter)  # not on any team
        self.assertEqual(self.client.post(self.vote_url(self.submission)).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.leader)  # registered, votes for another team
        self.assertEqual(self.client.post(self.vote_url(self.subs[1])).status_code, 201)

    def test_cannot_vote_on_draft(self):
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(self.vote_url(self.draft)).status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_event_isolation(self):
        now = timezone.now()
        event2 = Event.objects.create(
            title='Second', description='x', start_date=now - timedelta(days=2), end_date=now - timedelta(days=1),
            community_voting_start=now - timedelta(hours=1), community_voting_end=now + timedelta(hours=1),
            created_by=self.organizer,
        )
        team2 = Team.objects.create(event=event2, name='T2', leader=self.leader)
        sub2 = ProjectSubmission.objects.create(team=team2, title='P2', submitted_by=self.leader, is_draft=False)
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(self.vote_url(sub2, event2)).status_code, 201)
        # Submission of event 2 addressed through event 1 -> 404
        self.assertEqual(self.client.post(self.vote_url(sub2, self.event)).status_code, 404)
        # Quotas are per event
        self.assertEqual(self.client.post(self.vote_url(self.subs[1])).status_code, 201)
        self.assertEqual(self.client.post(self.vote_url(self.subs[2])).status_code, 201)

    def test_voided_votes_excluded_from_results(self):
        self.client.force_authenticate(self.voter)
        self.client.post(self.vote_url(self.submission))
        vote = CommunityVote.objects.get(voter=self.voter)

        self.client.force_authenticate(self.other_org)
        void_url = f'/api/events/{self.event.id}/admin/community-votes/{vote.id}/void/'
        self.assertEqual(self.client.post(void_url, {'reason': 'x'}).status_code, 403)

        self.client.force_authenticate(self.organizer)
        self.assertEqual(self.client.post(void_url, {}).status_code, 400)  # reason required
        self.assertEqual(self.client.post(void_url, {'reason': 'sock puppet'}).status_code, 200)
        res = self.client.get(f'/api/events/{self.event.id}/community-results/')
        row = next(r for r in res.data['results'] if r['submission_id'] == self.submission.id)
        self.assertEqual(row['votes'], 0)
        self.assertTrue(VoteAuditLog.objects.filter(action='VOTE_VOIDED').exists())

    def test_abuse_flags_shared_ip(self):
        extra = [User.objects.create_user(username=f'sock{i}', email=f's{i}@t.com', password='pw') for i in range(3)]
        for u in extra:
            self.client.force_authenticate(u)
            self.client.post(self.vote_url(self.submission), REMOTE_ADDR='10.0.0.9')
        flagged = CommunityVote.objects.filter(submission=self.submission).exclude(flags=[])
        self.assertTrue(any('SHARED_IP' in v.flags for v in flagged))
        self.assertTrue(VoteAuditLog.objects.filter(flagged=True, action='VOTED').exists())
        self.client.force_authenticate(self.organizer)
        res = self.client.get(f'/api/events/{self.event.id}/admin/community-votes/?flagged=1')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data), 1)

    def test_new_account_flag_only_for_accounts_created_after_voting_opened(self):
        fresh = User.objects.create_user(username='fresh', email='fresh@t.com', password='pw')
        self.client.force_authenticate(fresh)
        self.client.post(self.vote_url(self.submission))
        self.assertIn('NEW_ACCOUNT', CommunityVote.objects.get(voter=fresh).flags)
        old = User.objects.create_user(username='old', email='old@t.com', password='pw')
        User.objects.filter(pk=old.pk).update(date_joined=timezone.now() - timedelta(days=3))
        old.refresh_from_db()
        self.client.force_authenticate(old)
        self.client.post(self.vote_url(self.submission))
        self.assertNotIn('NEW_ACCOUNT', CommunityVote.objects.get(voter=old).flags)

    @mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'community_votes': '3/min', 'community_comments': '10/min'})
    def test_vote_rate_limited(self):
        self.event.votes_per_user = 0
        self.event.save()
        self.client.force_authenticate(self.voter)
        codes = [self.client.post(self.vote_url(s)).status_code for s in self.subs[:5]]
        self.assertEqual(codes[:3], [201, 201, 201])
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codes)


class HiddenResultsTests(CommunityBase):
    def setUp(self):
        super().setUp()
        CommunityVote.objects.create(submission=self.submission, voter=self.voter)

    def gallery(self):
        return self.client.get(f'/api/events/{self.event.id}/gallery/')

    def row(self, res):
        return next(r for r in res.data if r['id'] == self.submission.id)

    def test_counts_hidden_during_voting(self):
        self.client.force_authenticate(self.leader)
        self.assertIsNone(self.row(self.gallery())['community_vote_count'])
        res = self.client.get(f'/api/events/{self.event.id}/community-results/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(res.data['results_hidden'])

    def test_counts_hidden_from_anonymous_and_other_organizers(self):
        self.assertIsNone(self.row(self.gallery())['community_vote_count'])
        self.client.force_authenticate(self.other_org)
        self.assertIsNone(self.row(self.gallery())['community_vote_count'])

    def test_counts_visible_to_event_organizer_and_admin(self):
        for user in (self.organizer, self.admin_user):
            self.client.force_authenticate(user)
            self.assertEqual(self.row(self.gallery())['community_vote_count'], 1)

    def test_counts_visible_after_voting_ends(self):
        self.event.community_voting_end = timezone.now() - timedelta(minutes=1)
        self.event.save()
        self.assertEqual(self.row(self.gallery())['community_vote_count'], 1)
        res = self.client.get(f'/api/events/{self.event.id}/community-results/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['results'][0]['submission_id'], self.submission.id)
        self.assertEqual(res.data['results'][0]['rank'], 1)

    def test_live_counts_when_organizer_opts_in(self):
        self.event.show_community_voting_results = True
        self.event.save()
        self.assertEqual(self.row(self.gallery())['community_vote_count'], 1)


class GalleryOrderingTests(CommunityBase):
    def ids(self):
        res = self.client.get(f'/api/events/{self.event.id}/gallery/')
        self.assertEqual(res.status_code, 200)
        return [r['id'] for r in res.data], res

    def test_drafts_never_listed(self):
        for user in (None, self.organizer, self.judge):
            self.client.force_authenticate(user)
            ids, _ = self.ids()
            self.assertNotIn(self.draft.id, ids)
        self.event.community_voting_end = timezone.now() - timedelta(minutes=1)
        self.event.save()
        ids, _ = self.ids()
        self.assertNotIn(self.draft.id, ids)

    def test_randomized_order_is_stable_per_viewer(self):
        self.client.force_authenticate(self.voter)
        first, res = self.ids()
        self.assertEqual(res['X-Gallery-Ordering'], 'random')
        self.assertEqual(first, self.ids()[0])
        self.assertEqual(sorted(first), sorted(s.id for s in self.subs))

    def test_randomized_order_differs_between_viewers(self):
        orders = set()
        for i in range(8):
            u = User.objects.create_user(username=f'viewer{i}', email=f'v{i}@t.com', password='pw')
            self.client.force_authenticate(u)
            orders.add(tuple(self.ids()[0]))
        self.assertGreater(len(orders), 1)

    def test_recent_order_when_voting_closed(self):
        self.event.community_voting_start = None
        self.event.community_voting_end = None
        self.event.save()
        _, res = self.ids()
        self.assertEqual(res['X-Gallery-Ordering'], 'recent')

    def test_search(self):
        res = self.client.get(f'/api/events/{self.event.id}/gallery/', {'q': 'Project 3'})
        self.assertEqual([r['title'] for r in res.data], ['Project 3'])


class CommentTests(CommunityBase):
    def test_anonymous_can_read_but_not_post(self):
        self.assertEqual(self.client.get(self.comments_url(self.submission)).status_code, 200)
        self.assertEqual(self.client.post(self.comments_url(self.submission), {'text': 'hi'}).status_code, 401)

    def test_post_edit_delete_own_comment(self):
        self.client.force_authenticate(self.voter)
        res = self.client.post(self.comments_url(self.submission), {'text': '  Great demo!  '}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['text'], 'Great demo!')
        detail = f"/api/events/{self.event.id}/comments/{res.data['id']}/"

        self.assertEqual(self.client.patch(detail, {'text': 'Great demo, nice UX'}, format='json').status_code, 200)
        self.client.force_authenticate(self.voter2)
        self.assertEqual(self.client.patch(detail, {'text': 'hijack'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(detail).status_code, 403)

        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.delete(detail).status_code, 200)
        self.assertEqual(self.client.get(self.comments_url(self.submission)).data, [])
        actions = set(VoteAuditLog.objects.values_list('action', flat=True))
        self.assertTrue({'COMMENTED', 'COMMENT_EDITED', 'COMMENT_REMOVED'} <= actions)

    def test_organizer_can_moderate_but_other_organizer_cannot(self):
        comment = CommunityComment.objects.create(submission=self.submission, author=self.voter, text='spam')
        detail = f'/api/events/{self.event.id}/comments/{comment.id}/'
        self.client.force_authenticate(self.other_org)
        self.assertEqual(self.client.delete(detail).status_code, 403)
        self.client.force_authenticate(self.organizer)
        self.assertEqual(self.client.delete(detail).status_code, 200)
        comment.refresh_from_db()
        self.assertTrue(comment.is_removed)
        self.assertEqual(comment.removed_by, self.organizer)

    def test_empty_and_too_long_comments_rejected(self):
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(self.comments_url(self.submission), {'text': '   '}).status_code, 400)
        self.assertEqual(self.client.post(self.comments_url(self.submission), {'text': 'x' * 2001}).status_code, 400)

    def test_duplicate_comment_rejected(self):
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(self.comments_url(self.submission), {'text': 'Nice'}).status_code, 201)
        self.assertEqual(self.client.post(self.comments_url(self.submission), {'text': 'nice'}).status_code, 409)

    def test_comments_disabled(self):
        self.event.comments_enabled = False
        self.event.save()
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(self.comments_url(self.submission), {'text': 'hi'}).status_code, 403)

    def test_no_comments_on_drafts(self):
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.get(self.comments_url(self.draft)).status_code, 404)
        self.assertEqual(self.client.post(self.comments_url(self.draft), {'text': 'hi'}).status_code, 404)


class AuditTrailTests(CommunityBase):
    def test_audit_log_is_append_only(self):
        entry = VoteAuditLog.objects.create(event=self.event, action='VOTED', voter=self.voter)
        entry.metadata = {'tampered': True}
        with self.assertRaises(Exception):
            entry.save()
        with self.assertRaises(Exception):
            entry.delete()

    def test_hash_chain_verifies_and_detects_tampering(self):
        self.client.force_authenticate(self.voter)
        self.client.post(self.vote_url(self.subs[1]))
        self.client.post(self.vote_url(self.subs[2]))
        self.client.delete(self.vote_url(self.subs[1]))

        verify_url = f'/api/events/{self.event.id}/admin/community-audit/verify/'
        self.client.force_authenticate(self.organizer)
        res = self.client.get(verify_url)
        self.assertTrue(res.data['valid'])
        self.assertEqual(res.data['entries_checked'], 3)

        # Tamper with a middle row directly in the DB (bypassing the model guard)
        middle = VoteAuditLog.objects.filter(event=self.event).order_by('id')[1]
        VoteAuditLog.objects.filter(pk=middle.pk).update(action='UNVOTED')
        res = self.client.get(verify_url)
        self.assertFalse(res.data['valid'])
        self.assertEqual(res.data['first_invalid_entry_id'], middle.pk)

    def test_settings_changes_audited(self):
        self.client.force_authenticate(self.organizer)
        res = self.client.patch(
            f'/api/events/admin/events/{self.event.id}/', {'votes_per_user': 5, 'allow_self_vote': True}, format='json'
        )
        self.assertEqual(res.status_code, 200)
        entry = VoteAuditLog.objects.get(action='SETTINGS_CHANGED')
        self.assertEqual(entry.metadata['changes']['votes_per_user'], {'from': '2', 'to': '5'})
        self.assertIn('allow_self_vote', entry.metadata['changes'])

    def test_audit_endpoints_are_organizer_only(self):
        urls = [
            f'/api/events/{self.event.id}/admin/community-audit/',
            f'/api/events/{self.event.id}/admin/community-audit/verify/',
            f'/api/events/{self.event.id}/admin/community-votes/',
            f'/api/events/{self.event.id}/admin/export/community-votes-csv/',
            f'/api/events/{self.event.id}/admin/export/community-audit-csv/',
        ]
        for url in urls:
            self.client.force_authenticate(None)
            self.assertEqual(self.client.get(url).status_code, 401, url)
            for user in (self.voter, self.judge, self.other_org):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.get(url).status_code, 403, url)
            self.client.force_authenticate(self.organizer)
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_csv_exports(self):
        self.client.force_authenticate(self.voter)
        self.client.post(self.vote_url(self.submission))
        self.client.force_authenticate(self.organizer)
        res = self.client.get(f'/api/events/{self.event.id}/admin/export/community-votes-csv/')
        body = b''.join(res.streaming_content).decode()
        self.assertIn('Vote ID,Submission ID', body)
        self.assertIn('voter', body)


class VotingStatusTests(CommunityBase):
    def test_status_for_anonymous(self):
        res = self.client.get(f'/api/events/{self.event.id}/voting/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['is_active'])
        self.assertFalse(res.data['eligible'])
        self.assertFalse(res.data['results_visible'])

    def test_status_for_voter(self):
        self.client.force_authenticate(self.voter)
        self.client.post(self.vote_url(self.subs[1]))
        res = self.client.get(f'/api/events/{self.event.id}/voting/')
        self.assertTrue(res.data['eligible'])
        self.assertEqual(res.data['votes_used'], 1)
        self.assertEqual(res.data['votes_remaining'], 1)
        self.assertEqual(res.data['voted_submission_ids'], [self.subs[1].id])

    def test_settings_validation(self):
        self.client.force_authenticate(self.organizer)
        now = timezone.now()
        res = self.client.patch(
            f'/api/events/admin/events/{self.event.id}/',
            {'community_voting_start': now.isoformat(), 'community_voting_end': (now - timedelta(hours=1)).isoformat()},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
