from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Event, Team, ProjectSubmission, CommunityVote, VoteAuditLog

User = get_user_model()

class CommunityVotingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(username='admin', email='admin@test.com', password='password', role='admin')
        self.regular_user = User.objects.create_user(username='voter', email='voter@test.com', password='password', role='participant')
        self.team_leader = User.objects.create_user(username='leader', email='leader@test.com', password='password', role='participant')

        now = timezone.now()
        
        # Event with active voting and hidden results
        self.event = Event.objects.create(
            title="Test Hackathon",
            description="A test event",
            start_date=now - timedelta(days=2),
            end_date=now + timedelta(days=2),
            community_voting_start=now - timedelta(days=1),
            community_voting_end=now + timedelta(days=1),
            show_community_voting_results=False,
            created_by=self.admin_user
        )

        self.team = Team.objects.create(event=self.event, name="Test Team", leader=self.team_leader)
        self.submission = ProjectSubmission.objects.create(
            team=self.team,
            title="Test Project",
            submitted_by=self.team_leader,
            is_draft=False
        )

        self.vote_url = f'/api/events/{self.event.id}/submissions/{self.submission.id}/vote/'

    def test_voting_requires_authentication(self):
        response = self.client.post(self.vote_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_voting_when_inactive(self):
        self.event.community_voting_end = timezone.now() - timedelta(hours=1)
        self.event.save()
        
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.vote_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Voting is not active for this event.')

    def test_voting_when_active(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.vote_url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['detail'], 'Vote cast successfully.')
        self.assertTrue(response.data['has_voted'])
        
        # Check DB
        self.assertTrue(CommunityVote.objects.filter(submission=self.submission, voter=self.regular_user).exists())
        self.assertTrue(VoteAuditLog.objects.filter(submission=self.submission, voter=self.regular_user, action=VoteAuditLog.Action.VOTED).exists())

    def test_voting_toggle_unvote(self):
        self.client.force_authenticate(user=self.regular_user)
        # Cast vote
        self.client.post(self.vote_url)
        # Toggle vote (Unvote)
        response = self.client.post(self.vote_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Vote removed.')
        self.assertFalse(response.data['has_voted'])
        
        # Check DB
        self.assertFalse(CommunityVote.objects.filter(submission=self.submission, voter=self.regular_user).exists())
        self.assertTrue(VoteAuditLog.objects.filter(submission=self.submission, voter=self.regular_user, action=VoteAuditLog.Action.UNVOTED).exists())

    def test_hidden_vote_results_for_regular_user(self):
        # Add a vote
        CommunityVote.objects.create(submission=self.submission, voter=self.regular_user)
        
        self.client.force_authenticate(user=self.team_leader)
        response = self.client.get(f'/api/events/{self.event.id}/gallery/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission_data = response.data[0]
        self.assertIsNone(submission_data['community_vote_count'], "Vote count should be hidden during active voting for regular users")

    def test_visible_vote_results_for_admin(self):
        # Add a vote
        CommunityVote.objects.create(submission=self.submission, voter=self.regular_user)
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'/api/events/{self.event.id}/gallery/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission_data = response.data[0]
        self.assertEqual(submission_data['community_vote_count'], 1, "Vote count should be visible to admins")

    def test_visible_vote_results_after_voting_ends(self):
        # Add a vote
        CommunityVote.objects.create(submission=self.submission, voter=self.regular_user)
        
        # End voting
        self.event.community_voting_end = timezone.now() - timedelta(hours=1)
        self.event.save()
        
        self.client.force_authenticate(user=self.team_leader)
        response = self.client.get(f'/api/events/{self.event.id}/gallery/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission_data = response.data[0]
        self.assertEqual(submission_data['community_vote_count'], 1, "Vote count should be visible to everyone after voting ends")


    def test_cross_hackathon_isolation(self):
        # Create a second event
        now = timezone.now()
        event2 = Event.objects.create(
            title="Second Hackathon",
            description="Another event",
            start_date=now - timedelta(days=2),
            end_date=now + timedelta(days=2),
            community_voting_start=now - timedelta(days=1),
            community_voting_end=now + timedelta(days=1),
            show_community_voting_results=True,
            created_by=self.admin_user
        )
        team2 = Team.objects.create(event=event2, name="Team 2", leader=self.team_leader)
        submission2 = ProjectSubmission.objects.create(
            team=team2, title="Project 2", submitted_by=self.team_leader, is_draft=False
        )
        
        self.client.force_authenticate(user=self.regular_user)
        
        # User votes in event 1
        res1 = self.client.post(self.vote_url)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        
        # User votes in event 2
        vote_url2 = f'/api/events/{event2.id}/submissions/{submission2.id}/vote/'
        res2 = self.client.post(vote_url2)
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        
        # Test injection: voting for submission 2 using event 1's URL
        bad_url = f'/api/events/{self.event.id}/submissions/{submission2.id}/vote/'
        res_bad = self.client.post(bad_url)
        # Should return 404 because submission2 doesn't belong to event1
        self.assertEqual(res_bad.status_code, status.HTTP_404_NOT_FOUND)
