import hashlib
import json
import secrets
import string
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models


def generate_unique_team_code():
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    while True:
        code = f"HACK-{''.join(secrets.choice(chars) for _ in range(4))}"
        from .models import Team
        if not Team.objects.filter(code=code).exists():
            return code


class Event(models.Model):
    class Mode(models.TextChoices):
        VIRTUAL = 'virtual', 'Virtual'
        IN_PERSON = 'in_person', 'In-Person'
        HYBRID = 'hybrid', 'Hybrid'

    title = models.CharField(max_length=200)
    description = models.TextField()
    banner = models.ImageField(upload_to='event_banners/', blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.VIRTUAL)
    location = models.CharField(max_length=255, blank=True, default='')
    prize_pool = models.CharField(max_length=100, blank=True, default='')
    max_team_size = models.PositiveIntegerField(default=4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_events',
    )
    judges = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='judged_events',
        blank=True
    )
    
    # Submission Requirements
    require_github_url = models.BooleanField(default=True)
    require_demo_url = models.BooleanField(default=False)
    require_presentation = models.BooleanField(default=False)
    submission_guidelines = models.TextField(blank=True, default='')

    # Community Voting (T3)
    class VotingEligibility(models.TextChoices):
        ANY_USER = 'any', 'Any signed-in user'
        REGISTERED = 'registered', 'Only users registered on a team in this event'

    community_voting_start = models.DateTimeField(null=True, blank=True)
    community_voting_end = models.DateTimeField(null=True, blank=True)
    show_community_voting_results = models.BooleanField(
        default=False,
        help_text="If False, vote counts are hidden from the public until voting closes",
    )
    votes_per_user = models.PositiveIntegerField(
        default=3,
        help_text="Maximum community votes a single user may cast in this event (0 = unlimited)",
    )
    voting_eligibility = models.CharField(
        max_length=20,
        choices=VotingEligibility.choices,
        default=VotingEligibility.ANY_USER,
    )
    allow_self_vote = models.BooleanField(
        default=False,
        help_text="If False, team members cannot vote for their own team's project",
    )
    comments_enabled = models.BooleanField(default=True)

    # Judging (T2)
    judges_per_project = models.PositiveIntegerField(
        default=3,
        help_text="Target number of judge reviews per project (K)",
    )
    results_published = models.BooleanField(
        default=False,
        help_text="Judging leaderboard is hidden from everyone but the organizer until published",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def teams_count(self):
        return self.teams.count()

    @property
    def is_voting_active(self):
        now = timezone.now()
        return bool(
            self.community_voting_start
            and self.community_voting_end
            and self.community_voting_start <= now <= self.community_voting_end
        )

    @property
    def has_voting_ended(self):
        return bool(self.community_voting_end and timezone.now() > self.community_voting_end)

    def is_managed_by(self, user):
        """Organizer of THIS event or a platform admin. Role alone is never enough."""
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or user.role == 'admin' or self.created_by_id == user.id

    def is_judge(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.judges.filter(pk=user.pk).exists()

    def community_results_visible_to(self, user):
        if self.is_managed_by(user):
            return True
        if self.show_community_voting_results:
            return True
        # Hidden before and during voting; revealed once the window closes
        return self.has_voting_ended

    def __str__(self):
        return self.title


class EventPhase(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='phases')
    title = models.CharField(max_length=200, help_text="e.g. Sign up, Code sprint, Submission, Problem Statement Release")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return f"{self.title} ({self.event.title})"


class Track(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tracks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')

    def __str__(self):
        return self.title


class Prize(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='prizes')
    title = models.CharField(max_length=200)
    amount = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.title} - {self.amount}"


class Team(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=12, unique=True, db_index=True, default=generate_unique_team_code)
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='led_teams',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('event', 'name')

    @property
    def member_count(self):
        return self.memberships.count()

    @property
    def is_full(self):
        return self.memberships.count() >= self.event.max_team_size

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.event.title}"


class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_team_memberships',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'user')
        ordering = ['joined_at']

    def clean(self):
        # A user cannot belong to multiple teams in the same event
        existing_membership = TeamMember.objects.filter(
            team__event=self.team.event,
            user=self.user,
        ).exclude(pk=self.pk)
        if existing_membership.exists():
            raise ValidationError("You are already a member of a team for this event.")

        # Check max team capacity
        if not self.pk and self.team.is_full:
            raise ValidationError(f"This team has already reached its maximum capacity of {self.team.event.max_team_size} members.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} in {self.team.name}"


class ProjectSubmission(models.Model):
    team = models.OneToOneField(
        Team,
        on_delete=models.CASCADE,
        related_name='submission',
    )
    title = models.CharField(max_length=200, blank=True, default='')
    tagline = models.CharField(max_length=255, blank=True, default='', help_text="Short elevator pitch or 1-line overview")
    problem_statement = models.TextField(blank=True, default='', help_text="What problem does this project solve?")
    solution_description = models.TextField(blank=True, default='', help_text="Technical explanation of the solution architecture")
    github_url = models.URLField(max_length=500, blank=True, default='', help_text="GitHub repository link")
    demo_url = models.URLField(max_length=500, blank=True, default='', help_text="Live web app or demo video link")
    presentation_url = models.URLField(max_length=500, blank=True, default='', help_text="Slides, Canva, or presentation link")
    presentation_file = models.FileField(
        upload_to='submissions/presentations/',
        blank=True,
        null=True,
        help_text="Optional uploaded presentation slide deck (PDF or PPT)",
    )
    tech_stack = models.CharField(
        max_length=300,
        blank=True,
        default='',
        help_text="Comma-separated technologies used",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_projects',
    )
    is_draft = models.BooleanField(default=True, help_text="Draft submissions are not visible in the public gallery")
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True, blank=True, related_name='submissions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} - Team {self.team.name} ({self.team.event.title})"


class EventRubric(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='rubrics')
    title = models.CharField(max_length=200, help_text="e.g. Innovation, Technical Execution, UI/UX, Presentation")
    description = models.TextField(blank=True, default='', help_text="Evaluation guidelines for judges")
    weight = models.FloatField(default=20.0, help_text="Weight percentage (e.g. 25 for 25%)")
    max_score = models.PositiveIntegerField(default=10, help_text="Maximum mark (default 10)")

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.title} ({self.weight}% - {self.event.title})"


class ProjectEvaluation(models.Model):
    submission = models.ForeignKey(
        ProjectSubmission,
        on_delete=models.CASCADE,
        related_name='evaluations',
    )
    judge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='evaluations',
    )
    feedback = models.TextField(blank=True, default='', help_text="Optional remarks or feedback notes")
    total_score = models.FloatField(default=0.0, help_text="Weighted total mark (scaled 0-10)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = ('submission', 'judge')

    def __str__(self):
        return f"Score {self.total_score} by {self.judge.username} for {self.submission.title}"


class EvaluationScore(models.Model):
    evaluation = models.ForeignKey(
        ProjectEvaluation,
        on_delete=models.CASCADE,
        related_name='scores',
    )
    rubric = models.ForeignKey(
        EventRubric,
        on_delete=models.CASCADE,
        related_name='scores',
    )
    score = models.FloatField(help_text="Raw mark given by judge between 1 and 10")

    class Meta:
        unique_together = ('evaluation', 'rubric')

    def __str__(self):
        return f"{self.rubric.title}: {self.score}/10"


class JudgeAssignment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Evaluation'
        COMPLETED = 'COMPLETED', 'Evaluation Completed'
        EXCUSED = 'EXCUSED', 'Excused / Reassigned'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='judge_assignments')
    judge = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_projects')
    submission = models.ForeignKey(ProjectSubmission, on_delete=models.CASCADE, related_name='assigned_judges')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True, help_text="First time the judge opened this project (server clock)")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-assigned_at']
        unique_together = ('judge', 'submission')

    def __str__(self):
        return f"Assignment: @{self.judge.username} -> {self.submission.title} ({self.status})"


class EvaluationAuditLog(models.Model):
    class Action(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        UPDATED = 'UPDATED', 'Updated'
        FLAGGED = 'FLAGGED', 'Flagged Outlier'

    evaluation = models.ForeignKey(
        ProjectEvaluation,
        on_delete=models.CASCADE,
        related_name='audit_trail',
    )
    judge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluation_audits',
    )
    submission = models.ForeignKey(
        ProjectSubmission,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=20, choices=Action.choices, default=Action.CREATED)
    score_delta = models.FloatField(default=0.0, help_text="Difference between new score and previous score")
    snapshot_scores = models.JSONField(default=list, help_text="List of rubric scores at time of submission")
    previous_scores = models.JSONField(null=True, blank=True)
    feedback_text = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    is_outlier = models.BooleanField(default=False, help_text="Flagged if score diverges > 3.0 pts from consensus")
    dwell_seconds = models.FloatField(null=True, blank=True, help_text="Seconds between first opening the project and scoring it")
    flags = models.JSONField(default=list, blank=True, help_text="e.g. LOO_OUTLIER, RAPID_SUBMISSION")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Audit [{self.action}] on {self.submission.title} by {self.judge.username if self.judge else 'Unknown'} at {self.timestamp}"



class CommunityVote(models.Model):
    submission = models.ForeignKey(ProjectSubmission, on_delete=models.CASCADE, related_name='community_votes')
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_votes')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    flags = models.JSONField(default=list, blank=True, help_text="Abuse heuristics raised when the vote was cast")
    is_void = models.BooleanField(default=False, help_text="Voided by an organizer; excluded from tallies")
    void_reason = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Duplicate detection at the database level: one vote per user per project
        unique_together = ('submission', 'voter')
        ordering = ['-created_at']

    def __str__(self):
        return f"Vote by {self.voter.username} on {self.submission.title}"


class CommunityComment(models.Model):
    submission = models.ForeignKey(ProjectSubmission, on_delete=models.CASCADE, related_name='community_comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_comments')
    text = models.TextField()
    is_removed = models.BooleanField(default=False)
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='removed_comments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.author.username} on {self.submission.title}"


class ImmutableAuditError(Exception):
    pass


class VoteAuditLog(models.Model):
    """
    Append-only, hash-chained audit trail for all community (T3) actions.

    Every entry stores sha256(prev_hash + canonical payload). Rewriting or deleting any
    historic row breaks every later hash in the same event's chain, which
    CommunityAuditVerifyView detects.
    """

    class Action(models.TextChoices):
        VOTED = 'VOTED', 'Voted'
        UNVOTED = 'UNVOTED', 'Vote removed'
        VOTE_REJECTED = 'VOTE_REJECTED', 'Vote rejected'
        VOTE_VOIDED = 'VOTE_VOIDED', 'Vote voided by organizer'
        COMMENTED = 'COMMENTED', 'Comment posted'
        COMMENT_EDITED = 'COMMENT_EDITED', 'Comment edited'
        COMMENT_REMOVED = 'COMMENT_REMOVED', 'Comment removed'
        COMMENT_REJECTED = 'COMMENT_REJECTED', 'Comment rejected'
        SETTINGS_CHANGED = 'SETTINGS_CHANGED', 'Voting settings changed'

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='community_audit_logs', null=True, blank=True
    )
    submission = models.ForeignKey(
        ProjectSubmission, on_delete=models.SET_NULL, related_name='vote_audit_logs', null=True, blank=True
    )
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=Action.choices, default=Action.VOTED)
    metadata = models.JSONField(default=dict, blank=True)
    flagged = models.BooleanField(default=False, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    prev_hash = models.CharField(max_length=64, blank=True, default='')
    entry_hash = models.CharField(max_length=64, blank=True, default='')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp', '-id']

    def canonical_payload(self):
        return json.dumps(
            {
                'event': self.event_id,
                'submission': self.submission_id,
                'voter': self.voter_id,
                'action': self.action,
                'metadata': self.metadata,
                'flagged': self.flagged,
                'ip': self.ip_address,
                'timestamp': self.timestamp.isoformat(),
            },
            sort_keys=True,
            separators=(',', ':'),
            default=str,
        )

    def compute_hash(self):
        return hashlib.sha256((self.prev_hash + self.canonical_payload()).encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableAuditError('Audit log entries are append-only and cannot be modified.')
        if self.event_id is None and self.submission_id is not None:
            self.event_id = self.submission.team.event_id
        last = (
            VoteAuditLog.objects.filter(event_id=self.event_id)
            .order_by('-id')
            .values_list('entry_hash', flat=True)
            .first()
        )
        self.prev_hash = last or ''
        self.entry_hash = self.compute_hash()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableAuditError('Audit log entries are append-only and cannot be deleted.')

    def __str__(self):
        who = self.voter.username if self.voter else 'Unknown'
        return f"Audit [{self.action}] by {who} at {self.timestamp}"


def generate_webhook_secret():
    return secrets.token_hex(32)


class WebhookEndpoint(models.Model):
    """
    A URL an organizer registers to receive signed POST notifications
    whenever something happens in one of their events (T4).
    """

    class EventType(models.TextChoices):
        TEAM_CREATED = 'team.created', 'Team created'
        TEAM_JOINED = 'team.joined', 'Team joined'
        TEAM_LEFT = 'team.left', 'Team left'
        SUBMISSION_CREATED = 'submission.created', 'Submission created'
        SUBMISSION_UPDATED = 'submission.updated', 'Submission updated'
        RUBRICS_UPDATED = 'rubrics.updated', 'Rubrics updated'
        JUDGES_ASSIGNED = 'judges.assigned', 'Judges assigned'
        EVALUATION_SUBMITTED = 'evaluation.submitted', 'Evaluation submitted'
        RESULTS_PUBLISHED = 'results.published', 'Results published'
        VOTE_CAST = 'vote.cast', 'Community vote cast'
        VOTE_VOIDED = 'vote.voided', 'Community vote voided'
        COMMENT_POSTED = 'comment.posted', 'Comment posted'
        COMMENT_MODERATED = 'comment.moderated', 'Comment moderated'
        CERTIFICATES_ISSUED = 'certificates.issued', 'Certificates issued'
        EVENT_EXPORTED = 'event.exported', 'Event exported'
        EVENT_IMPORTED = 'event.imported', 'Event imported'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='webhook_endpoints')
    target_url = models.URLField(max_length=500, help_text="Where we POST the event payload")
    secret = models.CharField(
        max_length=64,
        default=generate_webhook_secret,
        help_text="Used to HMAC-sign every delivery so the receiver can verify it came from us",
    )
    subscribed_events = models.JSONField(
        default=list,
        blank=True,
        help_text="List of EventType values to receive; empty list means 'all events'",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_webhooks',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_subscribed_to(self, event_type):
        return not self.subscribed_events or event_type in self.subscribed_events

    def __str__(self):
        return f"Webhook -> {self.target_url} ({self.event.title})"


class WebhookDelivery(models.Model):
    """One attempted (or retried) POST to a WebhookEndpoint. Kept as a log for debugging/redelivery."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Delivered'
        FAILED = 'FAILED', 'Failed'

    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='deliveries')
    event_type = models.CharField(max_length=40)
    payload = models.JSONField(default=dict, help_text="Exact JSON body that was (or will be) sent")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default='')
    attempt_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Delivery [{self.status}] {self.event_type} -> {self.endpoint.target_url}"


class Certificate(models.Model):
    """
    Issued verifiable credentials for participants, winners, judges, and organizers.
    Includes a unique verification code and HMAC-SHA256 signature for tamper-proof public verification.
    """

    class Role(models.TextChoices):
        PARTICIPANT = 'participant', 'Participant'
        WINNER = 'winner', 'Winner'
        JUDGE = 'judge', 'Judge'
        ORGANIZER = 'organizer', 'Organizer'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='certificates')
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='certificates',
    )
    recipient_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='certificates',
    )
    recipient_name = models.CharField(max_length=200)
    recipient_email = models.CharField(max_length=255, blank=True, default='')
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.PARTICIPANT)
    title = models.CharField(max_length=200, help_text="e.g. Certificate of Participation, 1st Place Winner")
    award_title = models.CharField(max_length=200, blank=True, default='')
    certificate_code = models.CharField(max_length=64, unique=True, db_index=True)
    issued_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)
    signature = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        ordering = ['-issued_at']
        unique_together = [('event', 'recipient_user', 'role', 'award_title')]

    def save(self, *args, **kwargs):
        if not self.certificate_code:
            self.certificate_code = f"CERT-{self.event_id}-{secrets.token_hex(6).upper()}"
        if not self.signature:
            from .signing import sign_data
            payload = {
                'code': self.certificate_code,
                'event_id': self.event_id,
                'event_title': self.event.title,
                'recipient': self.recipient_name,
                'role': self.role,
                'award': self.award_title,
                'issued_at': self.issued_at.isoformat() if self.issued_at else '',
            }
            self.signature = sign_data(payload)
        super().save(*args, **kwargs)

    def is_valid_signature(self):
        from .signing import verify_signature
        payload = {
            'code': self.certificate_code,
            'event_id': self.event_id,
            'event_title': self.event.title,
            'recipient': self.recipient_name,
            'role': self.role,
            'award': self.award_title,
            'issued_at': self.issued_at.isoformat() if self.issued_at else '',
        }
        return verify_signature(payload, self.signature)

    def __str__(self):
        return f"{self.title} -> {self.recipient_name} ({self.certificate_code})"


class JudgeParticipationRecord(models.Model):
    """
    Cryptographically signed, publicly verifiable judge participation record.
    Summarizes the judge's scoring workload, timestamps, and evaluation commitment.
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='judge_records')
    judge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='judge_participation_records',
    )
    record_id = models.CharField(max_length=64, unique=True, db_index=True)
    evaluations_count = models.PositiveIntegerField(default=0)
    rubrics_scored_count = models.PositiveIntegerField(default=0)
    first_evaluation_at = models.DateTimeField(null=True, blank=True)
    last_evaluation_at = models.DateTimeField(null=True, blank=True)
    canonical_digest = models.CharField(max_length=64, blank=True, default='')
    signature = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('event', 'judge')]

    def build_canonical_payload(self):
        return {
            'record_id': self.record_id,
            'event_id': self.event_id,
            'event_title': self.event.title,
            'event_start': self.event.start_date.isoformat() if self.event.start_date else '',
            'event_end': self.event.end_date.isoformat() if self.event.end_date else '',
            'judge_id': self.judge_id,
            'judge_username': self.judge.username,
            'judge_name': f"{self.judge.first_name} {self.judge.last_name}".strip() or self.judge.username,
            'evaluations_count': self.evaluations_count,
            'rubrics_scored_count': self.rubrics_scored_count,
            'first_evaluation_at': self.first_evaluation_at.isoformat() if self.first_evaluation_at else '',
            'last_evaluation_at': self.last_evaluation_at.isoformat() if self.last_evaluation_at else '',
        }

    def sign_and_save(self, *args, **kwargs):
        from .signing import compute_digest, sign_data
        if not self.record_id:
            self.record_id = f"JPR-{self.event_id}-{self.judge_id}-{secrets.token_hex(4).upper()}"
        payload = self.build_canonical_payload()
        self.canonical_digest = compute_digest(payload)
        self.signature = sign_data(payload)
        self.save(*args, **kwargs)

    def is_valid_signature(self):
        from .signing import compute_digest, verify_signature
        payload = self.build_canonical_payload()
        if compute_digest(payload) != self.canonical_digest:
            return False
        return verify_signature(payload, self.signature)

    def __str__(self):
        return f"JudgeRecord {self.record_id} ({self.judge.username} @ {self.event.title})"

