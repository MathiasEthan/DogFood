from rest_framework import status
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db import transaction

import csv
from django.http import StreamingHttpResponse
from django.utils import timezone
from .models import (
    Event,
    Team,
    TeamMember,
    ProjectSubmission,
    EventRubric,
    ProjectEvaluation,
    EvaluationScore,
    JudgeAssignment,
    EvaluationAuditLog,
    WebhookEndpoint,
    WebhookDelivery,
)
from .normalization import NormalizationEngine
from .request_meta import client_ip, user_agent
from .community import (
    audit_settings_change, seeded_shuffle, snapshot_settings, viewer_seed, stream_csv, safe_filename,
    OrganizerOnlyMixin,
)
from .assignment import JudgeAssignmentEngine
from .webhooks import UnsafeWebhookTarget, dispatch_webhook, redeliver_webhook, send_test_ping, validate_webhook_url
from .serializers import (
    EventListSerializer,
    EventDetailSerializer,
    EventCreateSerializer,
    TeamSerializer,
    CreateTeamSerializer,
    JoinTeamSerializer,
    ProjectSubmissionSerializer,
    EventRubricSerializer,
    ProjectEvaluationSerializer,
)


class EventListCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        events = Event.objects.all().order_by('-created_at')
        filter_param = request.query_params.get('filter')
        if filter_param == 'organized' and request.user.is_authenticated:
            events = events.filter(created_by=request.user)
        elif filter_param == 'judged' and request.user.is_authenticated:
            events = events.filter(judges=request.user)
        serializer = EventListSerializer(events, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        if user.role not in ['organizer', 'admin'] and not user.is_superuser:
            return Response(
                {'detail': 'Only organizers and administrators are authorized to create hackathon events.'},
                status=status.HTTP_403_FORBIDDEN,
            )
            
        data = request.data.copy() if hasattr(request.data, 'copy') else request.data
        import json
        for field in ['phases', 'tracks', 'prizes', 'rubrics']:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = json.loads(data[field])
                except:
                    pass

        serializer = EventCreateSerializer(data=data)
        if serializer.is_valid():
            event = serializer.save(created_by=user)
            return Response(
                EventListSerializer(event, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        serializer = EventDetailSerializer(event, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        if event.is_judge(user) or event.created_by_id == user.id:
            return Response(
                {'detail': 'Judges and the organizer of this event cannot join or create a team in it (conflict of interest).'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if user is already a member of a team in this event
        existing_membership = TeamMember.objects.filter(team__event=event, user=user).first()
        if existing_membership:
            return Response(
                {
                    'detail': 'You already belong to a team for this event.',
                    'team': TeamSerializer(existing_membership.team).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CreateTeamSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        team_name = serializer.validated_data['name']

        if Team.objects.filter(event=event, name__iexact=team_name).exists():
            return Response(
                {'name': 'A team with this name already exists for this event.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            team = Team.objects.create(
                event=event,
                name=team_name,
                leader=user,
            )
            TeamMember.objects.create(team=team, user=user)

        dispatch_webhook(event, WebhookEndpoint.EventType.TEAM_CREATED, {
            'team_id': team.id,
            'team_name': team.name,
            'team_code': team.code,
            'event_id': event.id,
            'leader_username': user.username,
        })

        return Response(
            {
                'message': f'Team "{team.name}" created successfully! Share code {team.code} with friends to join.',
                'team': TeamSerializer(team).data,
            },
            status=status.HTTP_201_CREATED,
        )


class JoinTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        if event.is_judge(user) or event.created_by_id == user.id:
            return Response(
                {'detail': 'Judges and the organizer of this event cannot join or create a team in it (conflict of interest).'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if user already in a team for this event
        existing_membership = TeamMember.objects.filter(team__event=event, user=user).first()
        if existing_membership:
            return Response(
                {
                    'detail': 'You already belong to a team for this event.',
                    'team': TeamSerializer(existing_membership.team).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = JoinTeamSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data['code']
        team = Team.objects.filter(event=event, code__iexact=code).first()

        if not team:
            return Response(
                {'detail': f'No team found with code "{code}" for this event.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if team.is_full:
            return Response(
                {'detail': f'Team "{team.name}" has already reached its maximum capacity of {event.max_team_size} members.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            TeamMember.objects.create(team=team, user=user)

        dispatch_webhook(
            event,
            WebhookEndpoint.EventType.TEAM_JOINED,
            {
                'event_id': event.id,
                'team_id': team.id,
                'team_name': team.name,
                'user_id': user.id,
                'username': user.username,
            },
        )

        return Response(
            {
                'message': f'Successfully joined team "{team.name}"!',
                'team': TeamSerializer(team).data,
            },
            status=status.HTTP_200_OK,
        )


class TeamInviteLookupView(APIView):
    """
    GET /api/events/<id>/teams/lookup/?code=HACK-XXXX

    Powers invite links (/events/<id>?join=<code>): shows who invited you before you join.
    Returns only the team name and capacity - never member details. Rate limited.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'team_lookup'

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        code = (request.query_params.get('code') or '').strip().upper()
        team = Team.objects.filter(event=event, code__iexact=code).first() if code else None
        if not team:
            return Response({'detail': 'This invite link is invalid or has expired.'}, status=status.HTTP_404_NOT_FOUND)
        already = bool(
            request.user.is_authenticated and TeamMember.objects.filter(team__event=event, user=request.user).exists()
        )
        return Response(
            {
                'event_id': event.id,
                'event_title': event.title,
                'team_name': team.name,
                'code': team.code,
                'leader_username': team.leader.username,
                'member_count': team.member_count,
                'max_size': event.max_team_size,
                'is_full': team.is_full,
                'already_in_a_team': already,
            },
            status=status.HTTP_200_OK,
        )


class LeaveTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        membership = TeamMember.objects.filter(team__event=event, user=user).first()
        if not membership:
            return Response(
                {'detail': 'You are not a member of any team in this event.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = membership.team
        with transaction.atomic():
            membership.delete()

            # If the user leaving is the leader
            if team.leader == user:
                remaining_member = team.memberships.first()
                if remaining_member:
                    team.leader = remaining_member.user
                    team.save(update_fields=['leader'])
                else:
                    # No members left, disband team
                    team.delete()
                    dispatch_webhook(
                        event,
                        WebhookEndpoint.EventType.TEAM_LEFT,
                        {
                            'event_id': event.id,
                            'team_id': team.id,
                            'team_name': team.name,
                            'user_id': user.id,
                            'username': user.username,
                            'disbanded': True,
                        },
                    )
                    return Response({'message': 'You left and disbanded the team.'}, status=status.HTTP_200_OK)

        dispatch_webhook(
            event,
            WebhookEndpoint.EventType.TEAM_LEFT,
            {
                'event_id': event.id,
                'team_id': team.id,
                'team_name': team.name,
                'user_id': user.id,
                'username': user.username,
                'disbanded': False,
            },
        )

        return Response({'message': f'You have left team "{team.name}".'}, status=status.HTTP_200_OK)


class SubmitProjectView(APIView):
    """
    Allows the team leader to create or update their project submission
    until the hackathon deadline (event.end_date) passes.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        # Find user's team for this event
        membership = TeamMember.objects.filter(team__event=event, user=user).first()
        if not membership:
            return Response(
                {'detail': 'You must be part of a team for this hackathon to submit a project.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = membership.team

        # Check if user is the team leader
        if team.leader != user:
            return Response(
                {'detail': f'Only the team leader (@{team.leader.username}) can create or edit the project submission.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check deadline
        if timezone.now() > event.end_date:
            return Response(
                {'detail': 'The submission deadline for this hackathon has passed. Submissions are now locked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission = getattr(team, 'submission', None)

        # Check requirements if NOT a draft
        is_draft = request.data.get('is_draft') == 'true' or request.data.get('is_draft') is True

        if not is_draft:
            if not request.data.get('title'):
                return Response({'title': 'Project Title is required for final submission.'}, status=status.HTTP_400_BAD_REQUEST)
            if not request.data.get('tagline'):
                return Response({'tagline': 'Project Tagline is required for final submission.'}, status=status.HTTP_400_BAD_REQUEST)
            if not request.data.get('problem_statement'):
                return Response({'problem_statement': 'Problem Statement is required for final submission.'}, status=status.HTTP_400_BAD_REQUEST)
            if not request.data.get('solution_description'):
                return Response({'solution_description': 'Solution Description is required for final submission.'}, status=status.HTTP_400_BAD_REQUEST)
                
            if event.require_github_url and not request.data.get('github_url'):
                return Response({'github_url': 'GitHub URL is required for this hackathon.'}, status=status.HTTP_400_BAD_REQUEST)
                
            if event.require_demo_url and not request.data.get('demo_url'):
                return Response({'demo_url': 'A Demo Video or Deployed URL is required for this hackathon.'}, status=status.HTTP_400_BAD_REQUEST)
                
            if event.require_presentation and not request.data.get('presentation_url') and not request.FILES.get('presentation_file'):
                # Check if existing submission already has a file
                has_existing_file = submission and submission.presentation_file
                if not has_existing_file:
                    return Response({'presentation': 'A presentation (URL or file) is required for this hackathon.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ProjectSubmissionSerializer(
            instance=submission,
            data=request.data,
            partial=bool(submission) or is_draft,
            context={'request': request, 'event': event},
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        was_create = submission is None
        saved_submission = serializer.save(team=team, submitted_by=user, is_draft=is_draft)
        message = 'Project submission updated successfully!' if submission else 'Project submitted successfully!'

        dispatch_webhook(
            event,
            WebhookEndpoint.EventType.SUBMISSION_CREATED if was_create else WebhookEndpoint.EventType.SUBMISSION_UPDATED,
            {
                'submission_id': saved_submission.id,
                'team_id': team.id,
                'team_name': team.name,
                'title': saved_submission.title,
                'is_draft': saved_submission.is_draft,
                'event_id': event.id,
            },
        )

        return Response(
            {
                'message': message,
                'submission': ProjectSubmissionSerializer(saved_submission, context={'request': request}).data,
            },
            status=status.HTTP_200_OK if submission else status.HTTP_201_CREATED,
        )


class MySubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        membership = TeamMember.objects.filter(team__event=event, user=user).first()
        if not membership:
            return Response({'detail': 'Not in a team for this event.'}, status=status.HTTP_404_NOT_FOUND)

        team = membership.team
        if not hasattr(team, 'submission'):
            return Response({'detail': 'No project submission found for your team.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            ProjectSubmissionSerializer(team.submission, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )


class EventSubmissionsListView(APIView):
    """Lists all submitted projects for an event. Accessible to Organizers, Judges, and Admins."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        is_manager = event.is_managed_by(user)
        if not is_manager and not event.is_judge(user):
            return Response(
                {'detail': 'Only this event\'s organizer, its judges, and administrators can view the submissions roster.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submissions = ProjectSubmission.objects.filter(team__event=event)
        if not is_manager:
            # Judges never see drafts
            submissions = submissions.filter(is_draft=False)
        serializer = ProjectSubmissionSerializer(submissions, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)




class PublicGalleryView(APIView):
    """
    Searchable public gallery. Drafts are never listed, for anyone.
    While community voting is open, projects are shown in a per-viewer randomized order
    (stable across refreshes) so list position can't bias votes.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        from django.db.models import Q

        submissions = (
            ProjectSubmission.objects.filter(team__event=event, is_draft=False)
            .select_related('team', 'team__event', 'track', 'submitted_by')
        )

        query = request.query_params.get('q', '').strip()
        if query:
            submissions = submissions.filter(
                Q(title__icontains=query)
                | Q(tagline__icontains=query)
                | Q(tech_stack__icontains=query)
                | Q(team__name__icontains=query)
                | Q(track__title__icontains=query)
            )

        track_id = request.query_params.get('track', '')
        if track_id and track_id.isdigit():
            submissions = submissions.filter(track_id=track_id)

        submissions = list(submissions.distinct())
        ordering = request.query_params.get('ordering', '')
        if event.is_voting_active or ordering == 'random':
            submissions = seeded_shuffle(submissions, viewer_seed(event, request))
            ordering_used = 'random'
        else:
            submissions.sort(key=lambda s: s.updated_at, reverse=True)
            ordering_used = 'recent'

        serializer = ProjectSubmissionSerializer(submissions, many=True, context={'request': request})
        response = Response(serializer.data, status=status.HTTP_200_OK)
        response['X-Gallery-Ordering'] = ordering_used
        return response


class AdminEventManageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        data = request.data.copy() if hasattr(request.data, 'copy') else request.data
        import json
        for field in ['phases', 'tracks', 'prizes', 'rubrics']:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = json.loads(data[field])
                except:
                    pass
        before = snapshot_settings(event)
        serializer = EventCreateSerializer(event, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            event.refresh_from_db()
            audit_settings_change(event, before, request)
            return Response(EventDetailSerializer(event, context={'request': request}).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminAllTeamsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        teams = Team.objects.all().order_by('-created_at')
        event_id = request.query_params.get('event')
        if event_id:
            teams = teams.filter(event_id=event_id)
        serializer = TeamSerializer(teams, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AdminTeamManageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        team = get_object_or_404(Team, pk=pk)
        serializer = TeamSerializer(team)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        team = get_object_or_404(Team, pk=pk)
        team.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        team = get_object_or_404(Team, pk=pk)
        serializer = TeamSerializer(team, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminTeamMemberManageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, team_pk, user_pk):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        membership = get_object_or_404(TeamMember, team_id=team_pk, user_id=user_pk)
        team = membership.team
        membership.delete()
        if team.leader_id == user_pk:
            first_member = team.memberships.first()
            if first_member:
                team.leader = first_member.user
                team.save(update_fields=['leader'])
            else:
                team.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AdminAllSubmissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        submissions = ProjectSubmission.objects.all().order_by('-created_at')
        event_id = request.query_params.get('event')
        if event_id:
            submissions = submissions.filter(team__event_id=event_id)
        serializer = ProjectSubmissionSerializer(submissions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AdminSubmissionManageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        submission = get_object_or_404(ProjectSubmission, pk=pk)
        submission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk):
        if request.user.role != 'admin' and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)
        submission = get_object_or_404(ProjectSubmission, pk=pk)
        serializer = ProjectSubmissionSerializer(submission, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from django.contrib.auth import get_user_model
User = get_user_model()

class AdminEventJudgeManageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('user_id')
        username = request.data.get('username')
        email = request.data.get('email')

        user = None
        if user_id:
            user = get_object_or_404(User, pk=user_id)
        elif username:
            user = get_object_or_404(User, username=username)
        elif email:
            user = get_object_or_404(User, email=email)
        else:
            return Response({'error': 'user_id, username, or email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if TeamMember.objects.filter(team__event=event, user=user).exists():
            return Response(
                {'detail': f'@{user.username} is a member of a team in this event and cannot judge it (conflict of interest).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event.judges.add(user)
        # If user's role was participant, elevate to judge
        if user.role == 'participant':
            user.role = 'judge'
            user.save(update_fields=['role'])

        return Response({
            'message': f'@{user.username} added as Judge to this event.',
            'judge': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
            }
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('user_id')
        username = request.data.get('username')
        email = request.data.get('email')

        user = None
        if user_id:
            user = get_object_or_404(User, pk=user_id)
        elif username:
            user = get_object_or_404(User, username=username)
        elif email:
            user = get_object_or_404(User, email=email)
        else:
            return Response({'error': 'user_id, username, or email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        event.judges.remove(user)
        return Response({'message': f'@{user.username} removed from judges.'}, status=status.HTTP_200_OK)


class EventRubricsManageView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        rubrics = event.rubrics.all()
        serializer = EventRubricSerializer(rubrics, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(
                {'detail': 'Only the organizer or admin can configure rubrics for this event.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ProjectEvaluation.objects.filter(submission__team__event=event).exists():
            return Response(
                {'detail': 'Rubrics are locked once judging has started (evaluations exist).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = EventRubricSerializer(data=request.data)
        if serializer.is_valid():
            rubric = serializer.save(event=event)
            dispatch_webhook(
                event,
                WebhookEndpoint.EventType.RUBRICS_UPDATED,
                {
                    'event_id': event.id,
                    'action': 'created',
                    'rubric_id': rubric.id,
                    'rubric_title': rubric.title,
                },
            )
            return Response(EventRubricSerializer(rubric).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, rubric_pk=None):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(
                {'detail': 'Only the organizer or admin can remove rubrics from this event.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ProjectEvaluation.objects.filter(submission__team__event=event).exists():
            return Response(
                {'detail': 'Rubrics are locked once judging has started (evaluations exist).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rubric_id = rubric_pk or request.data.get('rubric_id')
        rubric = get_object_or_404(EventRubric, pk=rubric_id, event=event)
        rubric.delete()
        dispatch_webhook(
            event,
            WebhookEndpoint.EventType.RUBRICS_UPDATED,
            {
                'event_id': event.id,
                'action': 'deleted',
                'rubric_id': rubric_id,
            },
        )
        return Response({'message': 'Rubric removed successfully.'}, status=status.HTTP_200_OK)


def _is_platform_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == 'admin'))


class SubmitProjectEvaluationView(APIView):
    """
    Judges score a project against every rubric of the event.

    Backend-enforced rules:
      * only judges appointed to this event (or platform admins) may evaluate — organizer role alone is not enough
      * conflict of interest: never your own team's project
      * drafts cannot be evaluated; scoring locks once results are published
      * once assignments exist, judges may only score the projects assigned to them
      * every rubric must be scored exactly once, each mark within 1..rubric.max_score
    """
    permission_classes = [IsAuthenticated]

    def _load(self, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = get_object_or_404(ProjectSubmission, pk=sub_pk, team__event=event)
        return event, submission

    def _authorize(self, request, event, submission):
        user = request.user
        is_admin = _is_platform_admin(user)
        if not (event.is_judge(user) or is_admin):
            return Response(
                {'detail': 'Only judges appointed to this event can evaluate projects.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if submission.team.memberships.filter(user=user).exists() or submission.submitted_by_id == user.id:
            return Response(
                {'detail': 'Conflict of Interest: You cannot evaluate a project submitted by your own team.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not is_admin and JudgeAssignment.objects.filter(event=event).exists():
            if not JudgeAssignment.objects.filter(event=event, judge=user, submission=submission).exists():
                return Response(
                    {'detail': 'This project is not assigned to you for evaluation.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return None

    def post(self, request, event_pk, sub_pk):
        event, submission = self._load(event_pk, sub_pk)
        user = request.user

        denied = self._authorize(request, event, submission)
        if denied:
            return denied

        if submission.is_draft:
            return Response({'detail': 'Draft submissions cannot be evaluated.'}, status=status.HTTP_400_BAD_REQUEST)
        if event.results_published:
            return Response(
                {'detail': 'Results have been published; evaluations are locked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rubrics = list(event.rubrics.all())
        if not rubrics:
            return Response(
                {'detail': 'This event has no evaluation rubrics configured yet. Ask the organizer to add rubrics.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scores_input = request.data.get('scores', [])
        feedback = (request.data.get('feedback') or '').strip()

        if not scores_input or not isinstance(scores_input, list):
            return Response({'detail': 'A list of rubric scores is required.'}, status=status.HTTP_400_BAD_REQUEST)

        rubrics_dict = {r.id: r for r in rubrics}
        total_weight = sum(max(r.weight, 0) for r in rubrics)

        seen = set()
        score_entries = []
        for item in scores_input:
            if not isinstance(item, dict):
                return Response({'detail': 'Each score must be an object with rubric and score.'}, status=status.HTTP_400_BAD_REQUEST)
            rubric_id = item.get('rubric_id') or item.get('rubric')
            try:
                rubric_id = int(rubric_id)
            except (TypeError, ValueError):
                return Response({'detail': f'Invalid rubric id {rubric_id!r}.'}, status=status.HTTP_400_BAD_REQUEST)
            if rubric_id not in rubrics_dict:
                return Response(
                    {'detail': f'Rubric with id {rubric_id} does not belong to this event.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if rubric_id in seen:
                return Response({'detail': f'Rubric {rubric_id} was scored more than once.'}, status=status.HTTP_400_BAD_REQUEST)
            seen.add(rubric_id)

            try:
                score_val = float(item.get('score'))
            except (TypeError, ValueError):
                return Response({'detail': f'Score for rubric {rubric_id} must be a number.'}, status=status.HTTP_400_BAD_REQUEST)

            rubric = rubrics_dict[rubric_id]
            max_score = rubric.max_score or 10
            if score_val < 1 or score_val > max_score:
                return Response(
                    {'detail': f"Score for '{rubric.title}' must be in the range of 1 to {max_score}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            score_entries.append((rubric, score_val))

        missing = [r.title for r in rubrics if r.id not in seen]
        if missing:
            return Response(
                {'detail': 'Every rubric must be scored. Missing: ' + ', '.join(missing)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rescale each mark to /10, then apply normalized weights w_k = W_k / sum(W)
        weighted_sum = 0.0
        for rubric, score_val in score_entries:
            mark_10 = score_val / (rubric.max_score or 10) * 10
            if total_weight > 0:
                weighted_sum += mark_10 * (max(rubric.weight, 0) / total_weight)
            else:
                weighted_sum += mark_10 / len(rubrics)
        final_total = round(weighted_sum, 2)

        prev_eval = ProjectEvaluation.objects.filter(submission=submission, judge=user).first()
        prev_score = prev_eval.total_score if prev_eval else 0.0
        previous_scores = list(prev_eval.scores.values('rubric_id', 'score')) if prev_eval else None
        score_delta = round(final_total - prev_score, 2)

        # Leave-one-out consensus check: |s_j - mean(others)| >= 3.0 flags the evaluation
        other_evals = list(
            ProjectEvaluation.objects.filter(submission=submission).exclude(judge=user).values_list('total_score', flat=True)
        )
        is_outlier = False
        if other_evals:
            other_mean = sum(other_evals) / len(other_evals)
            is_outlier = abs(final_total - other_mean) >= 3.0

        now = timezone.now()
        assignment = JudgeAssignment.objects.filter(event=event, judge=user, submission=submission).first()
        dwell_seconds = None
        if assignment and assignment.opened_at:
            dwell_seconds = round((now - assignment.opened_at).total_seconds(), 1)
        flags = []
        if is_outlier:
            flags.append('LOO_OUTLIER')
        if prev_eval is None and dwell_seconds is not None and dwell_seconds < 45:
            flags.append('RAPID_SUBMISSION')

        with transaction.atomic():
            evaluation, created = ProjectEvaluation.objects.update_or_create(
                submission=submission,
                judge=user,
                defaults={'feedback': feedback, 'total_score': final_total},
            )
            evaluation.scores.all().delete()
            EvaluationScore.objects.bulk_create(
                [EvaluationScore(evaluation=evaluation, rubric=r, score=v) for r, v in score_entries]
            )
            JudgeAssignment.objects.filter(event=event, judge=user, submission=submission).update(
                status=JudgeAssignment.Status.COMPLETED, completed_at=now
            )
            action = EvaluationAuditLog.Action.FLAGGED if flags else (
                EvaluationAuditLog.Action.CREATED if created else EvaluationAuditLog.Action.UPDATED
            )
            EvaluationAuditLog.objects.create(
                evaluation=evaluation,
                judge=user,
                submission=submission,
                action=action,
                score_delta=score_delta,
                snapshot_scores=[
                    {'rubric_id': r.id, 'rubric': r.title, 'weight': r.weight, 'max_score': r.max_score, 'score': v}
                    for r, v in score_entries
                ],
                previous_scores=previous_scores,
                feedback_text=feedback,
                ip_address=client_ip(request),
                user_agent=user_agent(request),
                is_outlier=is_outlier,
                dwell_seconds=dwell_seconds,
                flags=flags,
            )

        dispatch_webhook(event, WebhookEndpoint.EventType.EVALUATION_SUBMITTED, {
            'submission_id': submission.id,
            'submission_title': submission.title,
            'event_id': event.id,
            'total_score': final_total,
            'is_outlier': is_outlier,
            'flags': flags,
        })

        return Response(
            {
                'message': 'Evaluation recorded successfully.',
                'evaluation': ProjectEvaluationSerializer(evaluation).data,
                'is_outlier': is_outlier,
                'flags': flags,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def get(self, request, event_pk, sub_pk):
        event, submission = self._load(event_pk, sub_pk)
        denied = self._authorize(request, event, submission)
        if denied:
            return denied
        # Server-side dwell-time clock: first time the judge opens their assigned project
        JudgeAssignment.objects.filter(
            event=event, judge=request.user, submission=submission, opened_at__isnull=True
        ).update(opened_at=timezone.now())
        evaluation = ProjectEvaluation.objects.filter(submission=submission, judge=request.user).first()
        if not evaluation:
            return Response({'evaluated': False, 'evaluation': None}, status=status.HTTP_200_OK)
        return Response(
            {'evaluated': True, 'evaluation': ProjectEvaluationSerializer(evaluation).data},
            status=status.HTTP_200_OK,
        )


def compute_standings(event):
    """Shared by the leaderboard, progress dashboard and CSV export."""
    submissions = list(
        ProjectSubmission.objects.filter(team__event=event, is_draft=False)
        .select_related('team', 'track')
        .prefetch_related('evaluations', 'evaluations__judge', 'evaluations__scores', 'evaluations__scores__rubric')
    )
    evaluations_payload = list(
        ProjectEvaluation.objects.filter(submission__team__event=event, submission__is_draft=False).values(
            'id', 'submission_id', 'judge_id', 'total_score'
        )
    )
    norm_scores, raw_scores, std_errs, telemetry = NormalizationEngine.calculate_normalized_scores(evaluations_payload)
    outliers = {}
    for row in (
        EvaluationAuditLog.objects.filter(submission__team__event=event, is_outlier=True)
        .values('submission_id', 'judge_id').distinct()
    ):
        outliers[row['submission_id']] = outliers.get(row['submission_id'], 0) + 1

    standings = []
    for sub in submissions:
        evals = list(sub.evaluations.all())
        norm = norm_scores.get(sub.id)
        standings.append({
            'submission': sub,
            'evaluations': evals,
            'normalized_score': norm,
            'raw_score': raw_scores.get(sub.id),
            'standard_error': std_errs.get(sub.id),
            'evaluations_count': len(evals),
            'outliers_flagged': outliers.get(sub.id, 0),
        })
    standings.sort(
        key=lambda x: (
            x['normalized_score'] is not None,
            x['normalized_score'] or 0,
            -(x['standard_error'] or 0),
        ),
        reverse=True,
    )
    return standings, telemetry


def anonymized_evaluations(evals):
    """Public view of judge feedback: 'Judge A', 'Judge B' ... per project, no identities."""
    out = []
    for idx, ev in enumerate(sorted(evals, key=lambda e: e.id)):
        label = f"Judge {chr(ord('A') + idx)}" if idx < 26 else f"Judge {idx + 1}"
        out.append({
            'judge_label': label,
            'total_score': ev.total_score,
            'feedback': ev.feedback,
            'scores': [
                {'rubric': s.rubric_id, 'rubric_title': s.rubric.title, 'rubric_weight': s.rubric.weight, 'score': s.score}
                for s in ev.scores.all()
            ],
        })
    return out


class MyAssignmentsView(APIView):
    """GET /api/events/<id>/my-assignments/ - a judge's own queue: assigned projects and their status."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if not event.is_judge(request.user) and not _is_platform_admin(request.user):
            return Response({'detail': 'Only judges of this event have an assignment queue.'}, status=status.HTTP_403_FORBIDDEN)
        rows = JudgeAssignment.objects.filter(event=event, judge=request.user).select_related('submission', 'submission__team')
        items = [
            {
                'submission_id': a.submission_id,
                'title': a.submission.title,
                'team_name': a.submission.team.name,
                'status': a.status,
                'completed_at': a.completed_at,
            }
            for a in rows.order_by('status', 'submission__title')
        ]
        done = sum(1 for i in items if i['status'] == JudgeAssignment.Status.COMPLETED)
        return Response(
            {
                'assignments_exist': JudgeAssignment.objects.filter(event=event).exists(),
                'assigned': len(items),
                'completed': done,
                'items': items,
            },
            status=status.HTTP_200_OK,
        )


class EventLeaderboardView(APIView):
    """
    Judging leaderboard. Anti-anchoring: hidden from everyone (including judges) until the
    organizer publishes results. Organizers/admins always see it; the public sees anonymized feedback.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        is_manager = event.is_managed_by(request.user)
        if not is_manager and not event.results_published:
            return Response(
                {'detail': 'Judging results are hidden until the organizer publishes them.', 'results_hidden': True},
                status=status.HTTP_403_FORBIDDEN,
            )

        standings, _ = compute_standings(event)
        leaderboard = []
        for rank, row in enumerate(standings, start=1):
            sub = row['submission']
            norm = row['normalized_score']
            entry = {
                'rank': rank,
                'submission_id': sub.id,
                'submission_title': sub.title,
                'team_name': sub.team.name,
                'tagline': sub.tagline,
                'track': sub.track_id,
                'track_title': sub.track.title if sub.track else None,
                'average_score': norm if norm is not None else row['raw_score'],
                'normalized_score': norm,
                'raw_score': row['raw_score'],
                'standard_error': row['standard_error'],
                'evaluations_count': row['evaluations_count'],
            }
            if is_manager:
                entry['outliers_flagged'] = row['outliers_flagged']
                entry['evaluations'] = ProjectEvaluationSerializer(row['evaluations'], many=True).data
            else:
                entry['evaluations'] = anonymized_evaluations(row['evaluations'])
            leaderboard.append(entry)
        return Response(leaderboard, status=status.HTTP_200_OK)


class PublishResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if not event.is_managed_by(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        published = request.data.get('published', True)
        if isinstance(published, str):
            published = published.lower() in ('1', 'true', 'yes')
        event.results_published = bool(published)
        event.save(update_fields=['results_published', 'updated_at'])
        if event.results_published:
            dispatch_webhook(event, WebhookEndpoint.EventType.RESULTS_PUBLISHED, {
                'event_id': event.id,
                'event_title': event.title,
            })
        return Response({'results_published': event.results_published}, status=status.HTTP_200_OK)


class AdminAssignJudgesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if not event.is_managed_by(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            k = int(request.data.get('k_per_project', event.judges_per_project))
        except (ValueError, TypeError):
            k = event.judges_per_project
        if k < 1 or k > 20:
            return Response({'detail': 'k_per_project must be between 1 and 20.'}, status=status.HTTP_400_BAD_REQUEST)

        result = JudgeAssignmentEngine.assign_judges_for_event(event=event, k_per_project=k, clear_existing_pending=True)
        if not result.get('success'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        if event.judges_per_project != k:
            event.judges_per_project = k
            event.save(update_fields=['judges_per_project', 'updated_at'])
        return Response(result, status=status.HTTP_200_OK)


class AdminJudgingProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if not event.is_managed_by(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        target_k = event.judges_per_project
        submissions = list(ProjectSubmission.objects.filter(team__event=event, is_draft=False).select_related('team'))
        judges = list(event.judges.all())
        assignments = list(JudgeAssignment.objects.filter(event=event).select_related('judge', 'submission'))
        standings, telemetry = compute_standings(event)
        standings_by_id = {row['submission'].id: row for row in standings}

        total_assignments = len(assignments)
        completed_assignments = sum(1 for a in assignments if a.status == JudgeAssignment.Status.COMPLETED)
        progress_pct = round(completed_assignments / total_assignments * 100, 1) if total_assignments else 0.0

        eval_scores_by_judge = {}
        for ev in ProjectEvaluation.objects.filter(submission__team__event=event, submission__is_draft=False):
            eval_scores_by_judge.setdefault(ev.judge_id, []).append(ev.total_score)

        judge_rows = {}
        for j in judges:
            t = telemetry.get(str(j.id), {})
            scores = eval_scores_by_judge.get(j.id, [])
            variance = None
            if len(scores) > 1:
                m = sum(scores) / len(scores)
                variance = round(sum((x - m) ** 2 for x in scores) / (len(scores) - 1), 3)
            judge_rows[j.id] = {
                'judge_id': j.id,
                'username': j.username,
                'assigned': 0,
                'completed': 0,
                'progress_percent': 0.0,
                'avg_review_seconds': None,
                'raw_mean': t.get('raw_mean'),
                'shrunk_mean': t.get('shrunk_mean'),
                'shrunk_std': t.get('shrunk_std'),
                'score_variance': variance,
                'flatline_warning': bool(len(scores) >= 5 and variance is not None and variance < 0.05),
            }

        review_times = {}
        for a in assignments:
            row = judge_rows.get(a.judge_id)
            if not row:
                continue
            row['assigned'] += 1
            if a.status == JudgeAssignment.Status.COMPLETED:
                row['completed'] += 1
                if a.opened_at and a.completed_at and a.completed_at >= a.opened_at:
                    review_times.setdefault(a.judge_id, []).append((a.completed_at - a.opened_at).total_seconds())
        for j_id, row in judge_rows.items():
            if row['assigned']:
                row['progress_percent'] = round(row['completed'] / row['assigned'] * 100, 1)
            times = review_times.get(j_id)
            if times:
                row['avg_review_seconds'] = round(sum(times) / len(times), 1)

        assigned_counts, completed_counts = {}, {}
        for a in assignments:
            assigned_counts[a.submission_id] = assigned_counts.get(a.submission_id, 0) + 1
            if a.status == JudgeAssignment.Status.COMPLETED:
                completed_counts[a.submission_id] = completed_counts.get(a.submission_id, 0) + 1

        project_matrix, under_reviewed = [], []
        for s in submissions:
            done = completed_counts.get(s.id, 0)
            assigned = assigned_counts.get(s.id, 0)
            if done >= target_k:
                saturation = 'SATISFIED'
            elif assigned >= target_k:
                saturation = 'IN_PROGRESS'
            else:
                saturation = 'DEFICIT'
            st = standings_by_id.get(s.id, {})
            project_matrix.append({
                'submission_id': s.id,
                'title': s.title,
                'team_name': s.team.name,
                'assigned_judges': assigned,
                'reviews_completed': done,
                'target_reviews': target_k,
                'saturation': saturation,
                'raw_score': st.get('raw_score'),
                'normalized_score': st.get('normalized_score'),
                'standard_error': st.get('standard_error'),
                'outliers_flagged': st.get('outliers_flagged', 0),
            })
            if done < target_k:
                under_reviewed.append({
                    'submission_id': s.id,
                    'title': s.title,
                    'team_name': s.team.name,
                    'reviews_completed': done,
                    'target_reviews': target_k,
                })

        satisfied = sum(1 for p in project_matrix if p['saturation'] == 'SATISFIED')
        return Response({
            'summary': {
                'total_submissions': len(submissions),
                'total_judges': len(judges),
                'target_reviews_per_project': target_k,
                'total_assignments': total_assignments,
                'completed_assignments': completed_assignments,
                'overall_progress_percent': progress_pct,
                'saturation_percent': round(satisfied / len(submissions) * 100, 1) if submissions else 0.0,
                'under_reviewed_count': len(under_reviewed),
                'flagged_evaluations': EvaluationAuditLog.objects.filter(
                    submission__team__event=event, action=EvaluationAuditLog.Action.FLAGGED
                ).count(),
                'results_published': event.results_published,
            },
            'judges': list(judge_rows.values()),
            'projects': project_matrix,
            'under_reviewed_submissions': under_reviewed,
        }, status=status.HTTP_200_OK)


class ManagerCSVView(APIView):
    """Base for organizer/admin-only streaming CSV exports."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if not event.is_managed_by(request.user):
            return Response(
                {'detail': 'Only the organizer of this event or an admin can export data.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        header, rows, suffix = self.build(event)
        return stream_csv(safe_filename(event, suffix), header, rows)

    def build(self, event):  # pragma: no cover - abstract
        raise NotImplementedError


def _fmt(value, digits=2):
    return '' if value is None else f"{value:.{digits}f}"


class AdminExportLeaderboardCSVView(ManagerCSVView):
    def build(self, event):
        standings, _ = compute_standings(event)
        rows = (
            [
                rank, r['submission'].id, r['submission'].title, r['submission'].team.name,
                r['submission'].track.title if r['submission'].track else 'General',
                _fmt(r['raw_score']), _fmt(r['normalized_score']), _fmt(r['standard_error'], 3),
                r['evaluations_count'], r['outliers_flagged'],
            ]
            for rank, r in enumerate(standings, start=1)
        )
        header = ['Rank', 'Submission ID', 'Project Title', 'Team Name', 'Track', 'Raw Score',
                  'Normalized Score', 'Standard Error', 'Completed Reviews', 'Outliers Flagged']
        return header, rows, 'leaderboard'


class AdminExportRubricsCSVView(ManagerCSVView):
    def build(self, event):
        scores = EvaluationScore.objects.filter(evaluation__submission__team__event=event).select_related(
            'evaluation', 'evaluation__submission', 'evaluation__submission__team', 'evaluation__judge', 'rubric'
        ).order_by('evaluation__submission_id', 'evaluation__judge_id', 'rubric_id')
        total_weight = sum(max(r.weight, 0) for r in event.rubrics.all()) or 1

        def rows():
            for s in scores.iterator():
                weight_share = max(s.rubric.weight, 0) / total_weight
                mark_10 = s.score / (s.rubric.max_score or 10) * 10
                yield [
                    s.evaluation.submission_id, s.evaluation.submission.title, s.evaluation.submission.team.name,
                    s.evaluation.judge.username if s.evaluation.judge else 'Anonymized',
                    s.rubric.title, round(weight_share * 100, 2), s.score, round(mark_10 * weight_share, 3),
                    s.evaluation.total_score, s.evaluation.updated_at.isoformat(),
                ]

        header = ['Submission ID', 'Project Title', 'Team Name', 'Judge Identifier', 'Rubric Name', 'Weight %',
                  'Raw Score', 'Weighted Contribution', 'Evaluation Total', 'Timestamp']
        return header, rows(), 'rubric_breakdown'


class AdminExportFeedbackCSVView(ManagerCSVView):
    def build(self, event):
        evals = ProjectEvaluation.objects.filter(submission__team__event=event).select_related(
            'submission', 'submission__team', 'judge'
        ).order_by('submission_id', 'id')
        rows = (
            [e.submission_id, e.submission.title, e.submission.team.name, e.judge.username if e.judge else '',
             e.total_score, e.feedback, e.updated_at.isoformat()]
            for e in evals.iterator()
        )
        header = ['Submission ID', 'Project Title', 'Team Name', 'Judge Identifier', 'Weighted Score',
                  'Feedback Notes', 'Submitted At']
        return header, rows, 'feedback'


class AdminExportSubmissionsCSVView(ManagerCSVView):
    def build(self, event):
        subs = ProjectSubmission.objects.filter(team__event=event).select_related('team', 'track', 'submitted_by')
        rows = (
            [s.id, s.title, s.team.name, s.team.memberships.count(), s.track.title if s.track else '',
             'draft' if s.is_draft else 'submitted', s.github_url, s.demo_url, s.presentation_url, s.tech_stack,
             s.submitted_by.username, s.created_at.isoformat(), s.updated_at.isoformat()]
            for s in subs.iterator()
        )
        header = ['Submission ID', 'Project Title', 'Team Name', 'Team Size', 'Track', 'Status', 'GitHub URL',
                  'Demo URL', 'Presentation URL', 'Tech Stack', 'Submitted By', 'Created At', 'Updated At']
        return header, rows, 'submissions'


class AdminExportAssignmentsCSVView(ManagerCSVView):
    def build(self, event):
        qs = JudgeAssignment.objects.filter(event=event).select_related('judge', 'submission', 'submission__team')
        rows = (
            [a.id, a.judge.username, a.submission_id, a.submission.title, a.submission.team.name, a.status,
             a.assigned_at.isoformat(), a.opened_at.isoformat() if a.opened_at else '',
             a.completed_at.isoformat() if a.completed_at else '']
            for a in qs.order_by('judge__username', 'submission_id').iterator()
        )
        header = ['Assignment ID', 'Judge', 'Submission ID', 'Project Title', 'Team Name', 'Status',
                  'Assigned At', 'First Opened At', 'Completed At']
        return header, rows, 'judge_assignments'


class AdminExportEvaluationAuditCSVView(ManagerCSVView):
    def build(self, event):
        qs = EvaluationAuditLog.objects.filter(submission__team__event=event).select_related('judge', 'submission')
        rows = (
            [l.id, l.timestamp.isoformat(), l.action, l.submission_id, l.submission.title,
             l.judge.username if l.judge else '', l.score_delta, 'yes' if l.is_outlier else 'no',
             '|'.join(l.flags or []), '' if l.dwell_seconds is None else l.dwell_seconds,
             l.ip_address or '', l.snapshot_scores]
            for l in qs.order_by('id').iterator()
        )
        header = ['Entry ID', 'Timestamp', 'Action', 'Submission ID', 'Project Title', 'Judge', 'Score Delta',
                  'Outlier', 'Flags', 'Dwell Seconds', 'IP Address', 'Scores Snapshot']
        return header, rows, 'evaluation_audit'


# --------------------------------------------------------------------------- T4: webhooks

def _normalize_subscriptions(value):
    """[] or ['*'] both mean 'all events'."""
    if value in (None, '', '*'):
        return []
    if isinstance(value, list):
        return [] if '*' in value else value
    return value


class WebhookEventTypesView(APIView):
    """GET /api/events/webhook-events/ - every event type a webhook can subscribe to."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {'event_types': [{'value': v, 'label': l} for v, l in WebhookEndpoint.EventType.choices]},
            status=status.HTTP_200_OK,
        )


class EventWebhookTestView(OrganizerOnlyMixin, APIView):
    """POST /api/events/<id>/webhooks/<wid>/test/ - send a signed 'ping' to one endpoint."""

    def post(self, request, pk, webhook_pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        endpoint = get_object_or_404(WebhookEndpoint, pk=webhook_pk, event=event)
        delivery = send_test_ping(endpoint)
        return Response(
            {
                'delivery_id': delivery.id,
                'status': delivery.status,
                'status_code': delivery.response_status,
                'response_body': delivery.response_body[:500],
            },
            status=status.HTTP_200_OK,
        )


def webhook_dict(endpoint, reveal_secret=False):
    return {
        'id': endpoint.id,
        'event_id': endpoint.event_id,
        'target_url': endpoint.target_url,
        'subscribed_events': endpoint.subscribed_events,
        'available_events': WebhookEndpoint.EventType.values,
        'is_active': endpoint.is_active,
        'created_at': endpoint.created_at,
        'secret': endpoint.secret if reveal_secret else f"{'*' * 8}{endpoint.secret[-4:]}",
    }


class EventWebhooksView(OrganizerOnlyMixin, APIView):
    """GET lists an event's webhooks; POST registers a new one."""

    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        endpoints = event.webhook_endpoints.all()
        return Response([webhook_dict(e) for e in endpoints], status=status.HTTP_200_OK)

    def post(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied

        target_url = (request.data.get('target_url') or '').strip()
        if not target_url:
            return Response({'target_url': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_webhook_url(target_url)
        except UnsafeWebhookTarget as exc:
            return Response({'target_url': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        subscribed_events = _normalize_subscriptions(request.data.get('subscribed_events'))
        if not isinstance(subscribed_events, list):
            return Response({'subscribed_events': 'Must be a list of event type strings.'}, status=status.HTTP_400_BAD_REQUEST)
        valid_types = set(WebhookEndpoint.EventType.values)
        invalid = [e for e in subscribed_events if e not in valid_types]
        if invalid:
            return Response(
                {'subscribed_events': f'Unknown event type(s): {", ".join(invalid)}. Valid: {", ".join(sorted(valid_types))}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        custom_secret = (request.data.get('secret') or '').strip()
        if custom_secret and not (16 <= len(custom_secret) <= 64):
            return Response({'secret': 'Custom secrets must be 16-64 characters.'}, status=status.HTTP_400_BAD_REQUEST)

        endpoint = WebhookEndpoint.objects.create(
            event=event,
            target_url=target_url,
            subscribed_events=subscribed_events,
            created_by=request.user,
            **({'secret': custom_secret} if custom_secret else {}),
        )
        # The secret is only ever readable in full at creation time - like an API key.
        return Response(webhook_dict(endpoint, reveal_secret=True), status=status.HTTP_201_CREATED)


class EventWebhookDetailView(OrganizerOnlyMixin, APIView):
    """PATCH toggles is_active / changes subscribed_events / target_url; DELETE removes it."""

    def _get_endpoint(self, event, webhook_pk):
        return get_object_or_404(WebhookEndpoint, pk=webhook_pk, event=event)

    def patch(self, request, pk, webhook_pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        endpoint = self._get_endpoint(event, webhook_pk)

        if 'target_url' in request.data:
            new_url = (request.data.get('target_url') or '').strip()
            try:
                validate_webhook_url(new_url)
            except UnsafeWebhookTarget as exc:
                return Response({'target_url': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            endpoint.target_url = new_url
        if 'is_active' in request.data:
            raw_active = request.data.get('is_active')
            endpoint.is_active = raw_active.lower() in ('1', 'true', 'yes') if isinstance(raw_active, str) else bool(raw_active)
        if 'subscribed_events' in request.data:
            subscribed_events = _normalize_subscriptions(request.data.get('subscribed_events'))
            if not isinstance(subscribed_events, list):
                return Response({'subscribed_events': 'Must be a list of event type strings.'}, status=status.HTTP_400_BAD_REQUEST)
            valid_types = set(WebhookEndpoint.EventType.values)
            invalid = [e for e in subscribed_events if e not in valid_types]
            if invalid:
                return Response({'subscribed_events': f'Unknown event type(s): {", ".join(invalid)}'}, status=status.HTTP_400_BAD_REQUEST)
            endpoint.subscribed_events = subscribed_events

        endpoint.save()
        return Response(webhook_dict(endpoint), status=status.HTTP_200_OK)

    def delete(self, request, pk, webhook_pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        endpoint = self._get_endpoint(event, webhook_pk)
        endpoint.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventWebhookDeliveriesView(OrganizerOnlyMixin, APIView):
    """Delivery log for one webhook - what we sent, what came back, when."""

    def get(self, request, pk, webhook_pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        endpoint = get_object_or_404(WebhookEndpoint, pk=webhook_pk, event=event)
        deliveries = endpoint.deliveries.all()[:200]
        return Response(
            [
                {
                    'id': d.id,
                    'event_type': d.event_type,
                    'status': d.status,
                    'response_status': d.response_status,
                    'response_body': d.response_body[:500],
                    'payload': d.payload,
                    'attempt_count': d.attempt_count,
                    'created_at': d.created_at,
                    'delivered_at': d.delivered_at,
                }
                for d in deliveries
            ],
            status=status.HTTP_200_OK,
        )


class WebhookRedeliverView(OrganizerOnlyMixin, APIView):
    """Manually retry one logged delivery (there's no background worker to retry automatically)."""

    def post(self, request, pk, webhook_pk, delivery_pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        endpoint = get_object_or_404(WebhookEndpoint, pk=webhook_pk, event=event)
        delivery = get_object_or_404(WebhookDelivery, pk=delivery_pk, endpoint=endpoint)
        redeliver_webhook(delivery)
        return Response(
            {
                'id': delivery.id,
                'status': delivery.status,
                'response_status': delivery.response_status,
                'attempt_count': delivery.attempt_count,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------------- T4 Stretch: Certificates, Records, Portability

from .certificates import generate_certificate_svg, issue_event_certificates
from .portability import export_event_archive, import_event_archive, import_teams_csv


def certificate_dict(cert, include_private=False):
    from .signing import SIGNATURE_ALGORITHM, public_key_hex
    data = {
        'id': cert.id,
        'certificate_code': cert.certificate_code,
        'code': cert.certificate_code,
        'event': cert.event_id,
        'event_title': cert.signed_payload.get('event_title', cert.event.title),
        'recipient_name': cert.recipient_name,
        'role': cert.role,
        'title': cert.title,
        'award_title': cert.award_title,
        'issued_at': cert.issued_at,
        'status': cert.status,
        'is_valid': cert.status == 'valid',
        'revoked_at': cert.revoked_at,
        'revocation_reason': cert.revocation_reason,
        'signature': cert.signature,
        'signature_algorithm': SIGNATURE_ALGORITHM,
        'public_key_hex': public_key_hex(),
        'signed_payload': cert.signed_payload,
        'download_url': f'/api/certificates/{cert.certificate_code}/download/',
        'verification_url': f'/certificates/{cert.certificate_code}',
    }
    if include_private:
        data['recipient_email'] = cert.recipient_email
    return data


def judge_record_dict(rec):
    from .signing import SIGNATURE_ALGORITHM, public_key_hex
    payload = rec.signed_payload or {}
    return {
        'record_id': rec.record_id,
        'judge_username': payload.get('judge_username', rec.judge.username),
        'event_title': payload.get('event_title', rec.event.title),
        'is_valid': rec.is_valid_signature(),
        'signature_algorithm': SIGNATURE_ALGORITHM,
        'signature': rec.signature,
        'public_key_hex': public_key_hex(),
        'canonical_digest': rec.canonical_digest,
        'record': payload,
        'verification_url': f'/verify/judge/{rec.record_id}',
        'verified_at': timezone.now().isoformat(),
    }


def _find_certificate(code):
    from .models import Certificate
    cert = Certificate.objects.filter(certificate_code__iexact=code).select_related('event').first()
    if not cert and code.isdigit():
        cert = Certificate.objects.filter(pk=int(code)).select_related('event').first()
    return cert


class GenerateCertificatesView(OrganizerOnlyMixin, APIView):
    """POST /api/events/<id>/admin/certificates/generate/ - issue certificates + sign judge records."""

    def post(self, request, pk):
        from .certificates import CertificatesNotReady
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        try:
            certs, records_signed, revoked = issue_event_certificates(event, issued_by=request.user)
        except CertificatesNotReady as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'message': f'Issued {len(certs)} certificate(s) and signed {records_signed} judge record(s).',
                'certificates_count': len(certs),
                'records_signed': records_signed,
                'revoked_count': revoked,
            },
            status=status.HTTP_201_CREATED,
        )


class EventCertificatesListView(OrganizerOnlyMixin, APIView):
    """GET /api/events/<id>/certificates/ - organizer view of every certificate (incl. revoked)."""

    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        certs = event.certificates.select_related('event').order_by('revoked_at', 'role', 'recipient_name')
        return Response([certificate_dict(c, include_private=True) for c in certs], status=status.HTTP_200_OK)


class MyCertificatesListView(APIView):
    """GET /api/events/<id>/my-certificates/ (one event) or /api/my-certificates/ (all events)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        from django.db.models import Q
        from .models import Certificate
        q = Q(recipient_user=request.user) | Q(recipient_team__memberships__user=request.user, recipient_user__isnull=True)
        certs = Certificate.objects.filter(q, revoked_at__isnull=True).select_related('event').distinct()
        if pk is not None:
            certs = certs.filter(event_id=pk)
        return Response([certificate_dict(c) for c in certs], status=status.HTTP_200_OK)


class PublicCertificateDetailView(APIView):
    """GET /api/certificates/<code>/ - public verification (valid / revoked / invalid)."""
    permission_classes = [AllowAny]

    def get(self, request, code):
        cert = _find_certificate(code)
        if not cert:
            return Response({'detail': 'Certificate not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(certificate_dict(cert), status=status.HTTP_200_OK)


class DownloadCertificateSVGView(APIView):
    """GET /api/certificates/<code>/download/ - printable standalone SVG."""
    permission_classes = [AllowAny]

    def get(self, request, code):
        from django.http import HttpResponse
        cert = _find_certificate(code)
        if not cert:
            return Response({'detail': 'Certificate not found.'}, status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(generate_certificate_svg(cert), content_type='image/svg+xml')
        resp['Content-Disposition'] = f'attachment; filename="certificate_{cert.certificate_code}.svg"'
        return resp


class PublicJudgeRecordVerifyView(APIView):
    """GET /api/judges/records/<record_id>/verify/ - public, offline-verifiable judge record."""
    permission_classes = [AllowAny]

    def get(self, request, record_id):
        from .models import JudgeParticipationRecord
        rec = JudgeParticipationRecord.objects.filter(record_id__iexact=record_id).select_related('event', 'judge').first()
        if not rec:
            return Response({'detail': 'Judge record not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(judge_record_dict(rec), status=status.HTTP_200_OK)


class MyJudgeRecordView(APIView):
    """GET /api/events/<id>/my-judge-record/ - a judge's own signed record."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        from .models import JudgeParticipationRecord
        rec = JudgeParticipationRecord.objects.filter(event=event, judge=request.user).first()
        if not rec:
            return Response({'detail': 'No judge record found for this event.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(judge_record_dict(rec), status=status.HTTP_200_OK)


class SigningKeyView(APIView):
    """GET /api/signing-key/ - the Ed25519 public key that verifies certificates and judge records."""
    permission_classes = [AllowAny]

    def get(self, request):
        from .signing import signing_key_document
        return Response(signing_key_document(), status=status.HTTP_200_OK)


class BulkEventExportView(OrganizerOnlyMixin, APIView):
    """GET /api/events/<id>/admin/export/bulk-archive/ - Lossless event JSON export with SHA-256 checksum."""

    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied

        archive = export_event_archive(event)
        if request.GET.get('download') == '1':
            from django.http import HttpResponse
            content = json.dumps(archive, indent=2, default=str)
            resp = HttpResponse(content, content_type='application/json')
            resp['Content-Disposition'] = f'attachment; filename="event_{event.id}_archive.json"'
            return resp

        return Response(archive, status=status.HTTP_200_OK)


class BulkEventImportView(APIView):
    """POST /api/events/admin/import/bulk-archive/ - Recreates an event from an exported JSON archive."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ['organizer', 'admin'] and not request.user.is_superuser:
            return Response({'detail': 'Only organizers or admins can import events.'}, status=status.HTTP_403_FORBIDDEN)

        archive_data = None
        if 'archive_file' in request.FILES:
            try:
                raw_bytes = request.FILES['archive_file'].read()
                archive_data = json.loads(raw_bytes.decode('utf-8'))
            except Exception as e:
                return Response({'detail': f'Failed to parse archive JSON file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        elif request.data:
            archive_data = request.data

        if not archive_data or not isinstance(archive_data, dict):
            return Response({'detail': 'Invalid or empty archive data.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            imported_event = import_event_archive(archive_data, request.user)
            return Response(
                {
                    'message': f'Successfully imported event "{imported_event.title}"!',
                    'event_id': imported_event.id,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response({'detail': f'Import failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


class BulkTeamImportCSVView(OrganizerOnlyMixin, APIView):
    """POST /api/events/<id>/admin/import/teams-csv/ - Bulk import teams and participants from CSV."""

    def post(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied

        csv_content = None
        if 'csv_file' in request.FILES:
            csv_content = request.FILES['csv_file'].read()
        elif 'csv_content' in request.data:
            csv_content = request.data['csv_content']

        if not csv_content:
            return Response({'detail': 'Provide csv_file or csv_content field.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            summary = import_teams_csv(event, csv_content)
            return Response(
                {
                    'message': f"Imported {summary['teams_created']} team(s) and {summary['members_added']} member(s).",
                    **summary,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({'detail': f'CSV import failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
