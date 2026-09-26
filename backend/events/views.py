from rest_framework import status
from rest_framework.views import APIView
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
)
from .normalization import NormalizationEngine
from .assignment import JudgeAssignmentEngine
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
        for field in ['phases', 'tracks', 'prizes']:
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

        return Response(
            {
                'message': f'Successfully joined team "{team.name}"!',
                'team': TeamSerializer(team).data,
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
                    return Response({'message': 'You left and disbanded the team.'}, status=status.HTTP_200_OK)

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
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        saved_submission = serializer.save(team=team, submitted_by=user, is_draft=is_draft)
        message = 'Project submission updated successfully!' if submission else 'Project submitted successfully!'

        return Response(
            {
                'message': message,
                'submission': ProjectSubmissionSerializer(saved_submission).data,
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

        return Response(ProjectSubmissionSerializer(team.submission).data, status=status.HTTP_200_OK)


class EventSubmissionsListView(APIView):
    """Lists all submitted projects for an event. Accessible to Organizers, Judges, and Admins."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        if user.role not in ['organizer', 'judge', 'admin'] and event.created_by != user and not user.is_superuser:
            return Response(
                {'detail': 'Only organizers, judges, and administrators can view the full submissions roster.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submissions = ProjectSubmission.objects.filter(team__event=event)
        serializer = ProjectSubmissionSerializer(submissions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)




class PublicGalleryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        
        # Search query
        query = request.query_params.get('q', '')
        track_id = request.query_params.get('track', '')

        from django.utils import timezone
        now = timezone.now()
        is_ended = event.end_date <= now

        user = request.user
        is_reviewer = (
            user.is_authenticated and (
                user.role == 'admin' or
                user.is_superuser or
                event.created_by == user or
                user.role == 'judge' or
                event.judges.filter(pk=user.pk).exists()
            )
        )

        # When the contest has concluded, or if the requester is an authorized reviewer (judge/organizer/admin),
        # all project submissions (including drafts) are visible for evaluation and public archive.
        if is_ended or is_reviewer:
            submissions = ProjectSubmission.objects.filter(team__event=event)
        else:
            submissions = ProjectSubmission.objects.filter(team__event=event, is_draft=False)
        
        if query:
            from django.db.models import Q
            submissions = submissions.filter(
                Q(title__icontains=query) |
                Q(tech_stack__icontains=query) |
                Q(team__name__icontains=query)
            )
            
        if track_id and track_id.isdigit():
            submissions = submissions.filter(track_id=track_id)

        # Randomize ordering if community voting is active and user is not searching
        is_voting_active = event.community_voting_start and event.community_voting_end and event.community_voting_start <= now <= event.community_voting_end
        if is_voting_active and not query:
            submissions = submissions.order_by('?')
        else:
            submissions = submissions.order_by('-updated_at')

        serializer = ProjectSubmissionSerializer(submissions.distinct(), many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)



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
        serializer = EventCreateSerializer(event, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(EventDetailSerializer(event).data, status=status.HTTP_200_OK)
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

        serializer = EventRubricSerializer(data=request.data)
        if serializer.is_valid():
            rubric = serializer.save(event=event)
            return Response(EventRubricSerializer(rubric).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, rubric_pk=None):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(
                {'detail': 'Only the organizer or admin can remove rubrics from this event.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        rubric_id = rubric_pk or request.data.get('rubric_id')
        rubric = get_object_or_404(EventRubric, pk=rubric_id, event=event)
        rubric.delete()
        return Response({'message': 'Rubric removed successfully.'}, status=status.HTTP_200_OK)


class SubmitProjectEvaluationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = get_object_or_404(ProjectSubmission, pk=sub_pk, team__event=event)

        user = request.user
        is_judge = event.judges.filter(pk=user.pk).exists()
        is_creator = event.created_by == user
        is_admin = user.role == 'admin' or user.is_superuser

        if not (is_judge or is_creator or is_admin):
            return Response(
                {'detail': 'Only designated judges, organizers, and administrators can evaluate projects.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Conflict of Interest (COI) Hard Guard:
        # A judge cannot evaluate their own project or any project where they belong to the team
        if submission.team.memberships.filter(user=user).exists() or submission.submitted_by_id == user.id:
            return Response(
                {'detail': 'Conflict of Interest: You cannot evaluate a project submitted by your own team.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        rubrics = list(event.rubrics.all())
        if not rubrics:
            return Response(
                {'detail': 'This event has no evaluation rubrics configured yet. Ask the organizer to add rubrics.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scores_input = request.data.get('scores', [])
        feedback = request.data.get('feedback', '').strip()

        if not scores_input or not isinstance(scores_input, list):
            return Response(
                {'detail': 'A list of rubric scores is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rubrics_dict = {r.id: r for r in rubrics}
        total_weight = sum(r.weight for r in rubrics)

        score_entries = []
        weighted_sum = 0.0

        for item in scores_input:
            rubric_id = item.get('rubric_id') or item.get('rubric')
            raw_score = item.get('score')

            if rubric_id not in rubrics_dict:
                return Response(
                    {'detail': f'Rubric with id {rubric_id} does not belong to this event.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                score_val = float(raw_score)
            except (TypeError, ValueError):
                return Response({'detail': f'Score for rubric {rubric_id} must be a number.'}, status=status.HTTP_400_BAD_REQUEST)

            if score_val < 0 or score_val > 10:
                return Response({'detail': 'Scores must be on a range of 1 to 10.'}, status=status.HTTP_400_BAD_REQUEST)

            rubric = rubrics_dict[rubric_id]
            score_entries.append((rubric, score_val))

            # Multiply marks by the percentage of the rubric (normalizing across total configured weight)
            if total_weight > 0:
                weighted_sum += score_val * (rubric.weight / total_weight)
            else:
                weighted_sum += score_val / len(rubrics)

        final_total = round(weighted_sum, 2)

        prev_eval = ProjectEvaluation.objects.filter(submission=submission, judge=user).first()
        prev_score = prev_eval.total_score if prev_eval else 0.0
        score_delta = round(final_total - prev_score, 2)

        # Check for Leave-One-Out (LOO) anomaly: deviation >= 3.0 from consensus of other judges
        other_evals = list(
            ProjectEvaluation.objects.filter(submission=submission).exclude(judge=user).values_list('total_score', flat=True)
        )
        is_outlier = False
        if len(other_evals) >= 1:
            other_mean = sum(other_evals) / len(other_evals)
            if abs(final_total - other_mean) >= 3.0:
                is_outlier = True

        evaluation, created = ProjectEvaluation.objects.update_or_create(
            submission=submission,
            judge=user,
            defaults={
                'feedback': feedback,
                'total_score': final_total,
            }
        )

        evaluation.scores.all().delete()
        for rubric, score_val in score_entries:
            EvaluationScore.objects.create(
                evaluation=evaluation,
                rubric=rubric,
                score=score_val,
            )

        # Mark any pending JudgeAssignment as completed
        JudgeAssignment.objects.filter(
            event=event, judge=user, submission=submission
        ).update(status=JudgeAssignment.Status.COMPLETED, completed_at=timezone.now())

        # Record immutable audit log
        client_ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        action = EvaluationAuditLog.Action.FLAGGED if is_outlier else (
            EvaluationAuditLog.Action.CREATED if created else EvaluationAuditLog.Action.UPDATED
        )
        EvaluationAuditLog.objects.create(
            evaluation=evaluation,
            judge=user,
            submission=submission,
            action=action,
            score_delta=score_delta,
            snapshot_scores=scores_input,
            previous_scores=list(prev_eval.scores.values('rubric_id', 'score')) if prev_eval else None,
            feedback_text=feedback,
            ip_address=client_ip,
            user_agent=user_agent,
            is_outlier=is_outlier,
        )

        return Response(
            {
                'message': 'Evaluation recorded successfully.',
                'evaluation': ProjectEvaluationSerializer(evaluation).data,
                'is_outlier': is_outlier,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def get(self, request, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = get_object_or_404(ProjectSubmission, pk=sub_pk, team__event=event)
        evaluation = ProjectEvaluation.objects.filter(submission=submission, judge=request.user).first()
        if not evaluation:
            return Response({'evaluated': False, 'evaluation': None}, status=status.HTTP_200_OK)
        return Response({'evaluated': True, 'evaluation': ProjectEvaluationSerializer(evaluation).data}, status=status.HTTP_200_OK)


class EventLeaderboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        submissions = list(
            ProjectSubmission.objects.filter(team__event=event)
            .select_related('team')
            .prefetch_related(
                'evaluations',
                'evaluations__judge',
                'evaluations__scores',
                'evaluations__scores__rubric',
            )
        )

        evaluations_payload = list(
            ProjectEvaluation.objects.filter(submission__team__event=event).values(
                'id', 'submission_id', 'judge_id', 'total_score'
            )
        )

        norm_scores, raw_scores, std_errs, telemetry = NormalizationEngine.calculate_normalized_scores(evaluations_payload)

        leaderboard = []
        for sub in submissions:
            evals = list(sub.evaluations.all())
            count = len(evals)
            norm_score = norm_scores.get(sub.id)
            raw_score = raw_scores.get(sub.id)
            se = std_errs.get(sub.id, 0.0)

            # Fall back to raw_score if normalized is not available
            final_display_score = norm_score if norm_score is not None else raw_score

            leaderboard.append({
                'submission_id': sub.id,
                'submission_title': sub.title,
                'team_name': sub.team.name,
                'tagline': sub.tagline,
                'track': sub.track_id,
                'average_score': final_display_score,
                'normalized_score': norm_score,
                'raw_score': raw_score,
                'standard_error': se,
                'evaluations_count': count,
                'evaluations': ProjectEvaluationSerializer(evals, many=True).data,
            })

        leaderboard.sort(
            key=lambda x: (
                x['average_score'] is not None,
                x['average_score'] or 0,
                -(x['standard_error'] or 0),
            ),
            reverse=True,
        )

        return Response(leaderboard, status=status.HTTP_200_OK)


class AdminAssignJudgesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            k = int(request.data.get('k_per_project', 3))
        except (ValueError, TypeError):
            k = 3

        result = JudgeAssignmentEngine.assign_judges_for_event(
            event=event,
            k_per_project=k,
            clear_existing_pending=True,
        )
        if not result.get('success'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)


class AdminJudgingProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if request.user.role != 'admin' and not request.user.is_superuser and event.created_by != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        submissions = list(ProjectSubmission.objects.filter(team__event=event, is_draft=False))
        judges = list(event.judges.all())
        assignments = list(JudgeAssignment.objects.filter(event=event).select_related('judge', 'submission'))

        total_assignments = len(assignments)
        completed_assignments = len([a for a in assignments if a.status == JudgeAssignment.Status.COMPLETED])
        progress_pct = round((completed_assignments / total_assignments * 100), 1) if total_assignments > 0 else 0.0

        judge_map = {
            j.id: {
                'judge_id': j.id,
                'username': j.username,
                'assigned': 0,
                'completed': 0,
                'progress_percent': 0.0,
            }
            for j in judges
        }
        for a in assignments:
            if a.judge_id in judge_map:
                judge_map[a.judge_id]['assigned'] += 1
                if a.status == JudgeAssignment.Status.COMPLETED:
                    judge_map[a.judge_id]['completed'] += 1

        for j_data in judge_map.values():
            if j_data['assigned'] > 0:
                j_data['progress_percent'] = round((j_data['completed'] / j_data['assigned'] * 100), 1)

        target_k = 3
        sub_review_counts = {}
        for a in assignments:
            if a.status == JudgeAssignment.Status.COMPLETED:
                sub_review_counts[a.submission_id] = sub_review_counts.get(a.submission_id, 0) + 1

        under_reviewed = []
        for s in submissions:
            reviews_done = sub_review_counts.get(s.id, 0)
            if reviews_done < target_k:
                under_reviewed.append({
                    'submission_id': s.id,
                    'title': s.title,
                    'team_name': s.team.name,
                    'reviews_completed': reviews_done,
                    'target_reviews': target_k,
                })

        return Response({
            'summary': {
                'total_submissions': len(submissions),
                'total_judges': len(judges),
                'total_assignments': total_assignments,
                'completed_assignments': completed_assignments,
                'overall_progress_percent': progress_pct,
                'under_reviewed_count': len(under_reviewed),
            },
            'judges': list(judge_map.values()),
            'under_reviewed_submissions': under_reviewed,
        }, status=status.HTTP_200_OK)


class EchoBuffer:
    def write(self, value):
        return value


class AdminExportLeaderboardCSVView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        evaluations_payload = list(
            ProjectEvaluation.objects.filter(submission__team__event=event).values(
                'id', 'submission_id', 'judge_id', 'total_score'
            )
        )
        norm_scores, raw_scores, std_errs, _ = NormalizationEngine.calculate_normalized_scores(evaluations_payload)

        submissions = list(
            ProjectSubmission.objects.filter(team__event=event).select_related('team', 'track')
        )

        ranked = []
        for s in submissions:
            eval_count = len([e for e in evaluations_payload if e['submission_id'] == s.id])
            ranked.append({
                'id': s.id,
                'title': s.title,
                'team': s.team.name,
                'track': s.track.title if s.track else 'General',
                'norm_score': norm_scores.get(s.id, 0.0),
                'raw_score': raw_scores.get(s.id, 0.0),
                'se': std_errs.get(s.id, 0.0),
                'count': eval_count,
            })
        ranked.sort(key=lambda x: (x['norm_score'], -x['se']), reverse=True)

        def row_generator():
            buffer = EchoBuffer()
            writer = csv.writer(buffer)
            yield writer.writerow([
                'Rank', 'Submission ID', 'Project Title', 'Team Name', 'Track',
                'Normalized Score (1-10)', 'Raw Average Score', 'Standard Error (SE)', 'Reviews Count'
            ])
            for idx, r in enumerate(ranked, start=1):
                yield writer.writerow([
                    idx,
                    r['id'],
                    r['title'],
                    r['team'],
                    r['track'],
                    f"{r['norm_score']:.2f}",
                    f"{r['raw_score']:.2f}",
                    f"{r['se']:.3f}",
                    r['count'],
                ])

        safe_title = "".join(c for c in event.title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        response = StreamingHttpResponse(row_generator(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{safe_title}_leaderboard.csv"'
        return response


class AdminExportRubricsCSVView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        scores = EvaluationScore.objects.filter(
            evaluation__submission__team__event=event
        ).select_related(
            'evaluation',
            'evaluation__submission',
            'evaluation__submission__team',
            'evaluation__judge',
            'rubric',
        )

        def row_generator():
            buffer = EchoBuffer()
            writer = csv.writer(buffer)
            yield writer.writerow([
                'Submission ID', 'Project Title', 'Team Name', 'Judge Username',
                'Rubric Title', 'Rubric Weight %', 'Raw Mark (1-10)', 'Evaluation Total', 'Timestamp'
            ])
            for s in scores:
                yield writer.writerow([
                    s.evaluation.submission_id,
                    s.evaluation.submission.title,
                    s.evaluation.submission.team.name,
                    s.evaluation.judge.username if s.evaluation.judge else 'Anonymized',
                    s.rubric.title,
                    s.rubric.weight,
                    s.score,
                    s.evaluation.total_score,
                    s.evaluation.created_at.isoformat(),
                ])

        safe_title = "".join(c for c in event.title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        response = StreamingHttpResponse(row_generator(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{safe_title}_rubrics_breakdown.csv"'
        return response


from rest_framework.throttling import UserRateThrottle

class VoteThrottle(UserRateThrottle):
    rate = '20/min'

class CommunityVoteView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [VoteThrottle]

    def post(self, request, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = get_object_or_404(ProjectSubmission, pk=sub_pk, team__event=event)
        
        now = timezone.now()
        is_voting_active = event.community_voting_start and event.community_voting_end and event.community_voting_start <= now <= event.community_voting_end
        
        if not is_voting_active:
            return Response({'detail': 'Voting is not active for this event.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create or delete vote
        from .models import CommunityVote, VoteAuditLog
        
        # Check if already voted
        vote = CommunityVote.objects.filter(submission=submission, voter=request.user).first()
        
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        if vote:
            vote.delete()
            VoteAuditLog.objects.create(
                submission=submission,
                voter=request.user,
                action=VoteAuditLog.Action.UNVOTED,
                ip_address=ip_address,
                user_agent=user_agent
            )
            return Response({'detail': 'Vote removed.', 'has_voted': False}, status=status.HTTP_200_OK)
        else:
            CommunityVote.objects.create(submission=submission, voter=request.user)
            VoteAuditLog.objects.create(
                submission=submission,
                voter=request.user,
                action=VoteAuditLog.Action.VOTED,
                ip_address=ip_address,
                user_agent=user_agent
            )
            return Response({'detail': 'Vote cast successfully.', 'has_voted': True}, status=status.HTTP_201_CREATED)
