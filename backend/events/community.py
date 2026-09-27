"""
T3 - Public / community layer.

Community voting, comments, hidden results, per-viewer randomized ordering, rate limiting,
duplicate / abuse detection and a hash-chained audit trail. See COMMUNITY.md for the design.
"""
import csv
import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import CommunityComment, CommunityVote, Event, ProjectSubmission, TeamMember, VoteAuditLog
from .request_meta import client_ip, user_agent

# Fields whose changes are written to the community audit trail
VOTING_SETTING_FIELDS = [
    'community_voting_start',
    'community_voting_end',
    'show_community_voting_results',
    'votes_per_user',
    'voting_eligibility',
    'allow_self_vote',
    'comments_enabled',
]

# Abuse heuristics (flag, never silently block — organizers decide via the void endpoint)
SHARED_IP_THRESHOLD = 3          # >= N distinct accounts from one IP voting for the same project
SHARED_IP_WINDOW = timedelta(hours=24)
NEW_ACCOUNT_AGE = timedelta(hours=1)
BURST_WINDOW = timedelta(seconds=60)
BURST_THRESHOLD = 5
DUPLICATE_COMMENT_WINDOW = timedelta(minutes=10)
MAX_COMMENT_LENGTH = 2000


# --------------------------------------------------------------------------- helpers

def record_audit(event, action, request=None, submission=None, voter=None, metadata=None, flagged=False):
    user = voter
    if user is None and request is not None and request.user.is_authenticated:
        user = request.user
    return VoteAuditLog.objects.create(
        event=event,
        submission=submission,
        voter=user,
        action=action,
        metadata=metadata or {},
        flagged=flagged,
        ip_address=client_ip(request) if request is not None else None,
        user_agent=user_agent(request) if request is not None else '',
    )


def audit_settings_change(event, before, request):
    """Call after an event update with a {field: old_value} snapshot."""
    changes = {}
    for field in VOTING_SETTING_FIELDS:
        old = before.get(field)
        new = getattr(event, field)
        if old != new:
            changes[field] = {'from': str(old) if old is not None else None, 'to': str(new) if new is not None else None}
    if changes:
        record_audit(event, VoteAuditLog.Action.SETTINGS_CHANGED, request, metadata={'changes': changes})
    return changes


def snapshot_settings(event):
    return {field: getattr(event, field) for field in VOTING_SETTING_FIELDS}


def viewer_seed(event, request):
    """
    Stable per-viewer seed: the same viewer sees the same order on every refresh,
    different viewers see different orders. Anonymous viewers are keyed on IP + UA.
    """
    if request.user.is_authenticated:
        identity = f"user:{request.user.pk}"
    else:
        identity = f"anon:{client_ip(request)}:{user_agent(request)}"
    raw = f"{settings.SECRET_KEY}:{event.pk}:{identity}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def seeded_shuffle(items, seed):
    return sorted(items, key=lambda obj: hashlib.sha256(f"{seed}:{obj.pk}".encode('utf-8')).hexdigest())


def voting_eligibility(event, user, submission=None):
    """Returns (eligible: bool, reason: str | None)."""
    if not user or not user.is_authenticated:
        return False, 'Sign in to vote.'
    if event.is_judge(user):
        return False, 'Judges of this event cannot take part in community voting.'
    if event.voting_eligibility == Event.VotingEligibility.REGISTERED:
        if not TeamMember.objects.filter(team__event=event, user=user).exists():
            return False, 'Only users registered on a team in this event can vote.'
    if submission is not None and not event.allow_self_vote:
        if submission.team.memberships.filter(user=user).exists():
            return False, 'You cannot vote for your own team\'s project.'
    return True, None


def votes_used(event, user):
    return CommunityVote.objects.filter(submission__team__event=event, voter=user).count()


def votes_remaining(event, user):
    if event.votes_per_user == 0:
        return None  # unlimited
    return max(0, event.votes_per_user - votes_used(event, user))


def valid_vote_counts(event):
    rows = (
        CommunityVote.objects.filter(submission__team__event=event, is_void=False)
        .values('submission_id')
        .annotate(n=Count('id'))
    )
    return {r['submission_id']: r['n'] for r in rows}


def public_submission_or_404(event, sub_pk):
    return get_object_or_404(ProjectSubmission, pk=sub_pk, team__event=event, is_draft=False)


def stream_csv(filename, header, rows):
    class Echo:
        def write(self, value):
            return value

    writer = csv.writer(Echo())

    def generate():
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(generate(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def safe_filename(event, suffix):
    base = "".join(c for c in event.title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    return f"{base or 'event'}_{suffix}.csv"


def forbidden(detail):
    return Response({'detail': detail}, status=status.HTTP_403_FORBIDDEN)


# --------------------------------------------------------------------------- serializers

class CommunityCommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    is_edited = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_remove = serializers.SerializerMethodField()

    class Meta:
        model = CommunityComment
        fields = [
            'id', 'submission', 'author', 'author_username', 'text',
            'created_at', 'updated_at', 'is_edited', 'can_edit', 'can_remove',
        ]
        read_only_fields = fields

    def _user(self):
        request = self.context.get('request')
        return request.user if request else None

    def get_is_edited(self, obj):
        return (obj.updated_at - obj.created_at).total_seconds() > 1

    def get_can_edit(self, obj):
        user = self._user()
        return bool(user and user.is_authenticated and obj.author_id == user.id)

    def get_can_remove(self, obj):
        user = self._user()
        if not user or not user.is_authenticated:
            return False
        return obj.author_id == user.id or obj.submission.team.event.is_managed_by(user)


def clean_comment_text(raw):
    text = (raw or '').strip()
    if not text:
        raise serializers.ValidationError({'text': 'Comment cannot be empty.'})
    if len(text) > MAX_COMMENT_LENGTH:
        raise serializers.ValidationError({'text': f'Comment must be at most {MAX_COMMENT_LENGTH} characters.'})
    return text


# --------------------------------------------------------------------------- voting

class CommunityVoteView(APIView):
    """
    POST   -> cast a vote   (201; 409 if already voted — duplicate detection)
    DELETE -> withdraw vote (200; 404 if no vote) — only while voting is open
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'community_votes'

    def post(self, request, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = public_submission_or_404(event, sub_pk)
        user = request.user

        if not event.is_voting_active:
            return Response({'detail': 'Voting is not active for this event.'}, status=status.HTTP_400_BAD_REQUEST)

        eligible, reason = voting_eligibility(event, user, submission)
        if not eligible:
            record_audit(event, VoteAuditLog.Action.VOTE_REJECTED, request, submission=submission,
                         metadata={'reason': 'ineligible', 'detail': reason})
            return forbidden(reason)

        if CommunityVote.objects.filter(submission=submission, voter=user).exists():
            record_audit(event, VoteAuditLog.Action.VOTE_REJECTED, request, submission=submission,
                         metadata={'reason': 'duplicate'})
            return Response(
                {'detail': 'You have already voted for this project.', 'has_voted': True},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        ip = client_ip(request)

        try:
            with transaction.atomic():
                # Serialize concurrent votes by the same user so the quota can't be raced
                type(user).objects.select_for_update().filter(pk=user.pk).first()

                remaining = votes_remaining(event, user)
                if remaining is not None and remaining <= 0:
                    record_audit(event, VoteAuditLog.Action.VOTE_REJECTED, request, submission=submission,
                                 metadata={'reason': 'quota_exhausted', 'votes_per_user': event.votes_per_user})
                    return Response(
                        {
                            'detail': f'You have used all {event.votes_per_user} of your votes for this event. '
                                      'Withdraw a vote to vote for a different project.',
                            'votes_remaining': 0,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                flags = []
                if ip:
                    same_ip_voters = (
                        CommunityVote.objects.filter(
                            submission=submission, ip_address=ip, created_at__gte=now - SHARED_IP_WINDOW
                        )
                        .exclude(voter=user)
                        .values('voter')
                        .distinct()
                        .count()
                    )
                    if same_ip_voters + 1 >= SHARED_IP_THRESHOLD:
                        flags.append('SHARED_IP')
                # Accounts registered after voting opened and voting within the hour look like sock puppets
                joined = getattr(user, 'date_joined', None)
                if (
                    joined
                    and event.community_voting_start
                    and joined >= event.community_voting_start
                    and now - joined < NEW_ACCOUNT_AGE
                ):
                    flags.append('NEW_ACCOUNT')
                recent = CommunityVote.objects.filter(
                    submission__team__event=event, voter=user, created_at__gte=now - BURST_WINDOW
                ).count()
                if recent + 1 >= BURST_THRESHOLD:
                    flags.append('BURST')

                CommunityVote.objects.create(submission=submission, voter=user, ip_address=ip, flags=flags)
        except IntegrityError:
            # Lost a race with a concurrent identical request: the unique constraint held.
            record_audit(event, VoteAuditLog.Action.VOTE_REJECTED, request, submission=submission,
                         metadata={'reason': 'duplicate_race'})
            return Response(
                {'detail': 'You have already voted for this project.', 'has_voted': True},
                status=status.HTTP_409_CONFLICT,
            )

        record_audit(event, VoteAuditLog.Action.VOTED, request, submission=submission,
                     metadata={'flags': flags} if flags else {}, flagged=bool(flags))

        return Response(
            {
                'detail': 'Vote cast successfully.',
                'has_voted': True,
                'votes_used': votes_used(event, user),
                'votes_remaining': votes_remaining(event, user),
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = public_submission_or_404(event, sub_pk)
        user = request.user

        if not event.is_voting_active:
            return Response(
                {'detail': 'Voting is closed; votes can no longer be changed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vote = CommunityVote.objects.filter(submission=submission, voter=user).first()
        if not vote:
            return Response({'detail': 'You have not voted for this project.'}, status=status.HTTP_404_NOT_FOUND)
        if vote.is_void:
            return Response(
                {'detail': 'This vote was voided by the organizers and cannot be withdrawn.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vote.delete()
        record_audit(event, VoteAuditLog.Action.UNVOTED, request, submission=submission)
        return Response(
            {
                'detail': 'Vote removed.',
                'has_voted': False,
                'votes_used': votes_used(event, user),
                'votes_remaining': votes_remaining(event, user),
            },
            status=status.HTTP_200_OK,
        )


class VotingStatusView(APIView):
    """Public voting configuration plus the caller's own quota and ballot."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        user = request.user
        eligible, reason = voting_eligibility(event, user)

        data = {
            'event_id': event.pk,
            'is_active': event.is_voting_active,
            'has_ended': event.has_voting_ended,
            'voting_start': event.community_voting_start,
            'voting_end': event.community_voting_end,
            'votes_per_user': event.votes_per_user,
            'voting_eligibility': event.voting_eligibility,
            'allow_self_vote': event.allow_self_vote,
            'comments_enabled': event.comments_enabled,
            'results_visible': event.community_results_visible_to(user),
            'eligible': eligible,
            'ineligible_reason': reason,
            'votes_used': 0,
            'votes_remaining': event.votes_per_user or None,
            'voted_submission_ids': [],
            'own_submission_id': None,
        }
        if user.is_authenticated:
            data['votes_used'] = votes_used(event, user)
            data['votes_remaining'] = votes_remaining(event, user)
            data['voted_submission_ids'] = list(
                CommunityVote.objects.filter(submission__team__event=event, voter=user)
                .values_list('submission_id', flat=True)
            )
            own = ProjectSubmission.objects.filter(team__event=event, team__memberships__user=user).first()
            data['own_submission_id'] = own.pk if own else None
        return Response(data, status=status.HTTP_200_OK)


class CommunityResultsView(APIView):
    """Community vote ranking. Hidden (403) until voting closes unless the organizer opts in."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if not event.community_results_visible_to(request.user):
            return Response(
                {
                    'detail': 'Community results are hidden while voting is in progress.',
                    'results_hidden': True,
                    'reveal_at': event.community_voting_end,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        counts = valid_vote_counts(event)
        subs = list(
            ProjectSubmission.objects.filter(team__event=event, is_draft=False).select_related('team', 'track')
        )
        rows = sorted(
            (
                {
                    'submission_id': s.pk,
                    'submission_title': s.title,
                    'team_name': s.team.name,
                    'track': s.track.title if s.track else None,
                    'votes': counts.get(s.pk, 0),
                }
                for s in subs
            ),
            key=lambda r: (-r['votes'], r['submission_title'].lower()),
        )
        # Standard competition ranking: ties share a rank (1, 1, 3, ...)
        prev_votes, prev_rank = None, 0
        for idx, row in enumerate(rows, start=1):
            if row['votes'] != prev_votes:
                prev_rank, prev_votes = idx, row['votes']
            row['rank'] = prev_rank

        return Response(
            {
                'event_id': event.pk,
                'voting_closed': event.has_voting_ended,
                'total_votes': sum(counts.values()),
                'results': rows,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------------- comments

class CommentListCreateView(APIView):
    throttle_scope = 'community_comments'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.request.method == 'POST':
            return [ScopedRateThrottle()]
        return []

    def get(self, request, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = public_submission_or_404(event, sub_pk)
        comments = (
            CommunityComment.objects.filter(submission=submission, is_removed=False)
            .select_related('author', 'submission__team__event')
            .order_by('created_at')
        )
        return Response(
            CommunityCommentSerializer(comments, many=True, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, event_pk, sub_pk):
        event = get_object_or_404(Event, pk=event_pk)
        submission = public_submission_or_404(event, sub_pk)

        if not event.comments_enabled:
            return forbidden('Comments are disabled for this event.')

        try:
            text = clean_comment_text(request.data.get('text'))
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        # Duplicate detection: same author, same project, same text in a short window
        duplicate = CommunityComment.objects.filter(
            submission=submission,
            author=request.user,
            text__iexact=text,
            created_at__gte=timezone.now() - DUPLICATE_COMMENT_WINDOW,
        ).exists()
        if duplicate:
            record_audit(event, VoteAuditLog.Action.COMMENT_REJECTED, request, submission=submission,
                         metadata={'reason': 'duplicate'})
            return Response(
                {'detail': 'You already posted this comment on this project.'},
                status=status.HTTP_409_CONFLICT,
            )

        comment = CommunityComment.objects.create(submission=submission, author=request.user, text=text)
        record_audit(event, VoteAuditLog.Action.COMMENTED, request, submission=submission,
                     metadata={'comment_id': comment.pk, 'length': len(text)})
        return Response(
            CommunityCommentSerializer(comment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, event_pk, comment_pk):
        event = get_object_or_404(Event, pk=event_pk)
        comment = get_object_or_404(
            CommunityComment.objects.select_related('submission__team__event'),
            pk=comment_pk,
            submission__team__event=event,
            is_removed=False,
        )
        return event, comment

    def patch(self, request, event_pk, comment_pk):
        event, comment = self._get(event_pk, comment_pk)
        if comment.author_id != request.user.id:
            return forbidden('You can only edit your own comments.')
        try:
            text = clean_comment_text(request.data.get('text'))
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        previous_length = len(comment.text)
        comment.text = text
        comment.save(update_fields=['text', 'updated_at'])
        record_audit(event, VoteAuditLog.Action.COMMENT_EDITED, request, submission=comment.submission,
                     metadata={'comment_id': comment.pk, 'previous_length': previous_length, 'length': len(text)})
        return Response(CommunityCommentSerializer(comment, context={'request': request}).data)

    def delete(self, request, event_pk, comment_pk):
        event, comment = self._get(event_pk, comment_pk)
        is_author = comment.author_id == request.user.id
        if not is_author and not event.is_managed_by(request.user):
            return forbidden('Only the author or the event organizer can remove this comment.')
        comment.is_removed = True
        comment.removed_by = request.user
        comment.save(update_fields=['is_removed', 'removed_by', 'updated_at'])
        record_audit(
            event, VoteAuditLog.Action.COMMENT_REMOVED, request, submission=comment.submission,
            metadata={
                'comment_id': comment.pk,
                'removed_by': 'author' if is_author else 'moderator',
                'reason': (request.data.get('reason') or '')[:255] if hasattr(request, 'data') else '',
            },
        )
        return Response({'detail': 'Comment removed.'}, status=status.HTTP_200_OK)


# --------------------------------------------------------------------------- organizer tools

class OrganizerOnlyMixin:
    permission_classes = [IsAuthenticated]

    def get_managed_event(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if not event.is_managed_by(request.user):
            return event, forbidden('Only the organizer of this event or an admin can access this.')
        return event, None


def audit_entry_dict(entry):
    return {
        'id': entry.pk,
        'timestamp': entry.timestamp,
        'action': entry.action,
        'submission_id': entry.submission_id,
        'submission_title': entry.submission.title if entry.submission else None,
        'user_id': entry.voter_id,
        'username': entry.voter.username if entry.voter else None,
        'flagged': entry.flagged,
        'metadata': entry.metadata,
        'ip_address': entry.ip_address,
        'entry_hash': entry.entry_hash,
        'prev_hash': entry.prev_hash,
    }


class CommunityAuditView(OrganizerOnlyMixin, APIView):
    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        qs = VoteAuditLog.objects.filter(event=event).select_related('submission', 'voter')
        if request.query_params.get('flagged') in ('1', 'true'):
            qs = qs.filter(flagged=True)
        action = request.query_params.get('action')
        if action:
            qs = qs.filter(action=action.upper())
        try:
            limit = min(max(int(request.query_params.get('limit', 200)), 1), 1000)
        except ValueError:
            limit = 200
        return Response([audit_entry_dict(e) for e in qs[:limit]], status=status.HTTP_200_OK)


class CommunityAuditVerifyView(OrganizerOnlyMixin, APIView):
    """Recomputes the hash chain; any edited or deleted row breaks it."""

    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        prev = ''
        checked = 0
        for entry in VoteAuditLog.objects.filter(event=event).order_by('id').iterator():
            if entry.prev_hash != prev or entry.compute_hash() != entry.entry_hash:
                return Response(
                    {'valid': False, 'entries_checked': checked, 'first_invalid_entry_id': entry.pk},
                    status=status.HTTP_200_OK,
                )
            prev = entry.entry_hash
            checked += 1
        return Response({'valid': True, 'entries_checked': checked, 'head_hash': prev}, status=status.HTTP_200_OK)


class CommunityVotesAdminView(OrganizerOnlyMixin, APIView):
    """Organizer view of individual votes (for reviewing flagged ones)."""

    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        qs = CommunityVote.objects.filter(submission__team__event=event).select_related('voter', 'submission')
        if request.query_params.get('flagged') in ('1', 'true'):
            qs = qs.exclude(flags=[])
        return Response(
            [
                {
                    'id': v.pk,
                    'submission_id': v.submission_id,
                    'submission_title': v.submission.title,
                    'voter_id': v.voter_id,
                    'voter_username': v.voter.username,
                    'ip_address': v.ip_address,
                    'flags': v.flags,
                    'is_void': v.is_void,
                    'void_reason': v.void_reason,
                    'created_at': v.created_at,
                }
                for v in qs
            ],
            status=status.HTTP_200_OK,
        )


class VoidVoteView(OrganizerOnlyMixin, APIView):
    def post(self, request, pk, vote_pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        vote = get_object_or_404(CommunityVote, pk=vote_pk, submission__team__event=event)
        if vote.is_void:
            return Response({'detail': 'Vote is already void.'}, status=status.HTTP_400_BAD_REQUEST)
        reason = (request.data.get('reason') or '').strip()[:255]
        if not reason:
            return Response({'reason': 'A reason is required to void a vote.'}, status=status.HTTP_400_BAD_REQUEST)
        vote.is_void = True
        vote.void_reason = reason
        vote.save(update_fields=['is_void', 'void_reason'])
        record_audit(event, VoteAuditLog.Action.VOTE_VOIDED, request, submission=vote.submission,
                     metadata={'vote_id': vote.pk, 'voter_id': vote.voter_id, 'reason': reason})
        return Response({'detail': 'Vote voided.', 'vote_id': vote.pk}, status=status.HTTP_200_OK)


class ExportCommunityVotesCSVView(OrganizerOnlyMixin, APIView):
    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        votes = (
            CommunityVote.objects.filter(submission__team__event=event)
            .select_related('voter', 'submission', 'submission__team')
            .order_by('created_at')
        )
        rows = (
            [
                v.pk, v.submission_id, v.submission.title, v.submission.team.name, v.voter.username,
                v.created_at.isoformat(), v.ip_address or '', '|'.join(v.flags or []),
                'yes' if v.is_void else 'no', v.void_reason,
            ]
            for v in votes.iterator()
        )
        return stream_csv(
            safe_filename(event, 'community_votes'),
            ['Vote ID', 'Submission ID', 'Project Title', 'Team Name', 'Voter', 'Cast At (UTC)',
             'IP Address', 'Flags', 'Void', 'Void Reason'],
            rows,
        )


class ExportCommunityAuditCSVView(OrganizerOnlyMixin, APIView):
    def get(self, request, pk):
        event, denied = self.get_managed_event(request, pk)
        if denied:
            return denied
        entries = VoteAuditLog.objects.filter(event=event).select_related('submission', 'voter').order_by('id')
        rows = (
            [
                e.pk, e.timestamp.isoformat(), e.action, e.submission_id or '',
                e.submission.title if e.submission else '', e.voter.username if e.voter else '',
                'yes' if e.flagged else 'no', e.ip_address or '', e.metadata, e.prev_hash, e.entry_hash,
            ]
            for e in entries.iterator()
        )
        return stream_csv(
            safe_filename(event, 'community_audit'),
            ['Entry ID', 'Timestamp (UTC)', 'Action', 'Submission ID', 'Project Title', 'User',
             'Flagged', 'IP Address', 'Metadata', 'Prev Hash', 'Entry Hash'],
            rows,
        )
