from rest_framework import serializers
from .models import (
    Event,
    Team,
    TeamMember,
    ProjectSubmission,
    Track,
    Prize,
    EventPhase,
    EventRubric,
    ProjectEvaluation,
    EvaluationScore,
)


class EventRubricSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = EventRubric
        fields = ['id', 'title', 'description', 'weight', 'max_score']


class EvaluationScoreSerializer(serializers.ModelSerializer):
    rubric_title = serializers.CharField(source='rubric.title', read_only=True)
    rubric_weight = serializers.FloatField(source='rubric.weight', read_only=True)

    class Meta:
        model = EvaluationScore
        fields = ['id', 'rubric', 'rubric_title', 'rubric_weight', 'score']


class ProjectEvaluationSerializer(serializers.ModelSerializer):
    judge_username = serializers.CharField(source='judge.username', read_only=True)
    scores = EvaluationScoreSerializer(many=True, read_only=True)
    team_name = serializers.CharField(source='submission.team.name', read_only=True)
    submission_title = serializers.CharField(source='submission.title', read_only=True)

    class Meta:
        model = ProjectEvaluation
        fields = [
            'id',
            'submission',
            'submission_title',
            'team_name',
            'judge',
            'judge_username',
            'feedback',
            'total_score',
            'scores',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'submission', 'judge', 'total_score', 'created_at', 'updated_at']


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = ['id', 'title', 'description']

class EventPhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventPhase
        fields = ['id', 'title', 'start_date', 'end_date']

class PrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prize
        fields = ['id', 'title', 'amount', 'description']

class ProjectSubmissionSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    submitted_by_username = serializers.CharField(source='submitted_by.username', read_only=True)
    community_vote_count = serializers.SerializerMethodField()
    has_voted = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    track = serializers.PrimaryKeyRelatedField(queryset=Track.objects.all(), required=False, allow_null=True)
    track_title = serializers.CharField(source='track.title', read_only=True, default=None)

    class Meta:
        model = ProjectSubmission
        fields = [
            'id',
            'team',
            'team_name',
            'title',
            'tagline',
            'problem_statement',
            'solution_description',
            'github_url',
            'demo_url',
            'presentation_url',
            'presentation_file',
            'tech_stack',
            'is_draft',
            'track',
            'submitted_by',
            'submitted_by_username',
            'created_at',
            'updated_at',
            'community_vote_count',
            'has_voted',
            'comment_count',
            'track_title',
        ]
        read_only_fields = ['id', 'team', 'submitted_by', 'created_at', 'updated_at']

    def validate_track(self, value):
        event = self.context.get('event')
        if value is not None and event is not None and value.event_id != event.id:
            raise serializers.ValidationError("This track does not belong to this event.")
        return value

    def get_community_vote_count(self, obj):
        # Hidden results: null until voting closes, unless the organizer opts in (or is viewing)
        request = self.context.get('request')
        user = request.user if request else None
        if not obj.team.event.community_results_visible_to(user):
            return None
        return obj.community_votes.filter(is_void=False).count()

    def get_comment_count(self, obj):
        return obj.community_comments.filter(is_removed=False).count()

    def get_has_voted(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.community_votes.filter(voter=request.user).exists()
        return False

    def validate_github_url(self, value):
        val = value.strip()
        if not val.startswith(('http://', 'https://')):
            raise serializers.ValidationError("GitHub URL must start with http:// or https://")
        return val


class TeamMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    is_leader = serializers.SerializerMethodField()

    class Meta:
        model = TeamMember
        fields = ['id', 'user_id', 'username', 'email', 'is_leader', 'joined_at']

    def get_is_leader(self, obj):
        return obj.user == obj.team.leader


class TeamSerializer(serializers.ModelSerializer):
    leader_username = serializers.CharField(source='leader.username', read_only=True)
    members = TeamMemberSerializer(source='memberships', many=True, read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    max_size = serializers.IntegerField(source='event.max_team_size', read_only=True)
    submission = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'code',
            'event',
            'leader',
            'leader_username',
            'created_at',
            'members',
            'member_count',
            'max_size',
            'submission',
        ]
        read_only_fields = ['id', 'code', 'leader', 'created_at']

    def get_submission(self, obj):
        if hasattr(obj, 'submission'):
            return ProjectSubmissionSerializer(obj.submission).data
        return None


class CreateTeamSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=True)

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Team name cannot be empty.")
        return name


class JoinTeamSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20, required=True)

    def validate_code(self, value):
        code = value.strip().upper()
        if not code:
            raise serializers.ValidationError("Team code cannot be empty.")
        return code


class EventListSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    teams_count = serializers.IntegerField(read_only=True)
    rubrics = EventRubricSerializer(many=True, read_only=True)
    event_judges = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'description',
            'banner',
            'start_date',
            'end_date',
            'mode',
            'location',
            'prize_pool',
            'max_team_size',
            'created_by',
            'created_by_username',
            'created_at',
            'teams_count',
            'rubrics',
            'event_judges',
            'require_github_url',
            'require_demo_url',
            'require_presentation',
            'submission_guidelines',
            'community_voting_start',
            'community_voting_end',
            'show_community_voting_results',
            'votes_per_user',
            'voting_eligibility',
            'allow_self_vote',
            'comments_enabled',
            'judges_per_project',
            'results_published',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

    def get_event_judges(self, obj):
        # Judge emails are only shown to the event's organizer / admins
        request = self.context.get('request')
        show_email = bool(request and obj.is_managed_by(request.user))
        return [
            {'id': j.id, 'username': j.username, **({'email': j.email} if show_email else {})}
            for j in obj.judges.all()
        ]


class EventDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    teams_count = serializers.IntegerField(read_only=True)
    my_team = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()
    phases = EventPhaseSerializer(many=True, read_only=True)
    tracks = TrackSerializer(many=True, read_only=True)
    prizes = PrizeSerializer(many=True, read_only=True)
    rubrics = EventRubricSerializer(many=True, read_only=True)
    event_judges = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'description',
            'banner',
            'start_date',
            'end_date',
            'mode',
            'location',
            'prize_pool',
            'max_team_size',
            'created_by',
            'created_by_username',
            'created_at',
            'teams_count',
            'my_team',
            'teams',
            'phases',
            'tracks',
            'prizes',
            'rubrics',
            'event_judges',
            'require_github_url',
            'require_demo_url',
            'require_presentation',
            'submission_guidelines',
            'community_voting_start',
            'community_voting_end',
            'show_community_voting_results',
            'votes_per_user',
            'voting_eligibility',
            'allow_self_vote',
            'comments_enabled',
            'judges_per_project',
            'results_published',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

    def get_event_judges(self, obj):
        # Judge emails are only shown to the event's organizer / admins
        request = self.context.get('request')
        show_email = bool(request and obj.is_managed_by(request.user))
        return [
            {'id': j.id, 'username': j.username, **({'email': j.email} if show_email else {})}
            for j in obj.judges.all()
        ]

    def get_my_team(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        membership = TeamMember.objects.filter(team__event=obj, user=request.user).first()
        if membership:
            return TeamSerializer(membership.team).data
        return None

    def get_teams(self, obj):
        # Provide team list for organizers and admins
        # Team list (incl. join codes) only for this event's organizer / admins
        request = self.context.get('request')
        if request and obj.is_managed_by(request.user):
            return TeamSerializer(obj.teams.all(), many=True).data
        return []


class EventCreateSerializer(serializers.ModelSerializer):
    phases = EventPhaseSerializer(many=True, required=False)
    tracks = TrackSerializer(many=True, required=False)
    prizes = PrizeSerializer(many=True, required=False)
    rubrics = EventRubricSerializer(many=True, required=False)

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'description',
            'banner',
            'start_date',
            'end_date',
            'mode',
            'location',
            'prize_pool',
            'max_team_size',
            'phases',
            'tracks',
            'prizes',
            'rubrics',
            'require_github_url',
            'require_demo_url',
            'require_presentation',
            'submission_guidelines',
            'community_voting_start',
            'community_voting_end',
            'show_community_voting_results',
            'votes_per_user',
            'voting_eligibility',
            'allow_self_vote',
            'comments_enabled',
            'judges_per_project',
            'results_published',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        inst = self.instance
        start = attrs.get('start_date', inst.start_date if inst else None)
        end = attrs.get('end_date', inst.end_date if inst else None)
        if start and end and end <= start:
            raise serializers.ValidationError({'end_date': "End date must be after the start date."})

        v_start = attrs.get('community_voting_start', inst.community_voting_start if inst else None)
        v_end = attrs.get('community_voting_end', inst.community_voting_end if inst else None)
        if bool(v_start) != bool(v_end):
            raise serializers.ValidationError(
                {'community_voting_end': "Set both the voting start and end, or neither."}
            )
        if v_start and v_end and v_end <= v_start:
            raise serializers.ValidationError({'community_voting_end': "Voting must end after it starts."})

        k = attrs.get('judges_per_project')
        if k is not None and not (1 <= k <= 20):
            raise serializers.ValidationError({'judges_per_project': "Must be between 1 and 20."})

        rubrics = attrs.get('rubrics')
        if rubrics:
            for r in rubrics:
                if r.get('weight', 0) < 0:
                    raise serializers.ValidationError({'rubrics': "Rubric weights cannot be negative."})
                if r.get('max_score', 10) < 1:
                    raise serializers.ValidationError({'rubrics': "Rubric max score must be at least 1."})
            if sum(r.get('weight', 0) for r in rubrics) <= 0:
                raise serializers.ValidationError({'rubrics': "Rubric weights must add up to more than 0."})
        return attrs

    def create(self, validated_data):
        phases_data = validated_data.pop('phases', [])
        tracks_data = validated_data.pop('tracks', [])
        prizes_data = validated_data.pop('prizes', [])
        rubrics_data = validated_data.pop('rubrics', [])
        
        event = Event.objects.create(**validated_data)
        
        for phase_data in phases_data:
            EventPhase.objects.create(event=event, **phase_data)
        for track_data in tracks_data:
            Track.objects.create(event=event, **track_data)
        for prize_data in prizes_data:
            Prize.objects.create(event=event, **prize_data)
        for rubric_data in rubrics_data:
            EventRubric.objects.create(event=event, **rubric_data)
            
        return event

    @staticmethod
    def _rubrics_changed(instance, rubrics_data):
        current = {
            r.id: (r.title, float(r.weight), int(r.max_score)) for r in instance.rubrics.all()
        }
        incoming = {}
        for r in rubrics_data:
            rid = r.get('id')
            if not rid or rid not in current:
                return True
            incoming[rid] = (
                r.get('title', current[rid][0]),
                float(r.get('weight', current[rid][1])),
                int(r.get('max_score', current[rid][2])),
            )
        return incoming != current

    def update(self, instance, validated_data):
        phases_data = validated_data.pop('phases', None)
        tracks_data = validated_data.pop('tracks', None)
        prizes_data = validated_data.pop('prizes', None)
        rubrics_data = validated_data.pop('rubrics', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if phases_data is not None:
            instance.phases.all().delete()
            for phase_data in phases_data:
                EventPhase.objects.create(event=instance, **phase_data)
                
        if tracks_data is not None:
            instance.tracks.all().delete()
            for track_data in tracks_data:
                Track.objects.create(event=instance, **track_data)
                
        if prizes_data is not None:
            instance.prizes.all().delete()
            for prize_data in prizes_data:
                Prize.objects.create(event=instance, **prize_data)

        if rubrics_data is not None and self._rubrics_changed(instance, rubrics_data):
            if ProjectEvaluation.objects.filter(submission__team__event=instance).exists():
                raise serializers.ValidationError(
                    {'rubrics': "Rubrics are locked once judging has started (evaluations exist)."}
                )
        if rubrics_data is not None:
            existing_rubrics = {r.id: r for r in instance.rubrics.all()}
            kept_ids = []
            for rubric_data in rubrics_data:
                rubric_id = rubric_data.get('id')
                if rubric_id and rubric_id in existing_rubrics:
                    r = existing_rubrics[rubric_id]
                    r.title = rubric_data.get('title', r.title)
                    r.description = rubric_data.get('description', r.description)
                    r.weight = rubric_data.get('weight', r.weight)
                    r.max_score = rubric_data.get('max_score', r.max_score)
                    r.save()
                    kept_ids.append(r.id)
                else:
                    new_r = EventRubric.objects.create(event=instance, **rubric_data)
                    kept_ids.append(new_r.id)
            instance.rubrics.exclude(id__in=kept_ids).delete()
        
        return instance
