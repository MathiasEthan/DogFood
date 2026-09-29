import csv
import io
import json
import secrets
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    Event,
    Team,
    TeamMember,
    EventRubric,
    ProjectSubmission,
    ProjectEvaluation,
    EvaluationScore,
    Certificate,
    CommunityVote,
    CommunityComment,
    WebhookEndpoint,
)
from .signing import compute_digest, canonical_json_bytes
from .webhooks import dispatch_webhook

User = get_user_model()


def export_event_archive(event):
    """
    Export the complete event and all its relational sub-resources
    into a portable, lossless JSON archive with a cryptographic checksum.
    """
    # 1. Event Core
    archive = {
        'version': '1.0',
        'exported_at': timezone.now().isoformat(),
        'platform': 'DogFood-Hackathon-Platform',
        'event': {
            'title': event.title,
            'description': event.description,
            'start_date': event.start_date.isoformat() if event.start_date else None,
            'end_date': event.end_date.isoformat() if event.end_date else None,
            'mode': event.mode,
            'location': event.location,
            'prize_pool': event.prize_pool,
            'max_team_size': event.max_team_size,
            'results_published': event.results_published,
            'voting_rules': {
                'window_start': event.community_voting_start.isoformat() if event.community_voting_start else None,
                'window_end': event.community_voting_end.isoformat() if event.community_voting_end else None,
                'votes_per_user': event.votes_per_user,
                'eligibility': event.voting_eligibility,
                'allow_self_vote': event.allow_self_vote,
                'show_community_voting_results': event.show_community_voting_results,
                'comments_enabled': event.comments_enabled,
            },
        },
        'rubrics': [
            {
                'title': r.title,
                'description': r.description,
                'weight': float(r.weight),
                'max_score': r.max_score,
            }
            for r in event.rubrics.all()
        ],
        'teams': [],
        'evaluations': [],
        'community_votes': [],
        'comments': [],
        'certificates': [],
    }

    # 2. Teams & Submissions
    for team in event.teams.all().prefetch_related('memberships__user'):
        team_data = {
            'name': team.name,
            'code': team.code,
            'created_at': team.created_at.isoformat() if team.created_at else None,
            'members': [
                {
                    'username': m.user.username,
                    'email': m.user.email,
                    'is_leader': (m.user_id == team.leader_id),
                    'joined_at': m.joined_at.isoformat() if m.joined_at else None,
                }
                for m in team.memberships.all()
            ],
            'submissions': [],
        }

        sub = getattr(team, 'submission', None)
        if sub:
            team_data['submissions'].append({
                'title': sub.title,
                'tagline': sub.tagline,
                'problem_statement': sub.problem_statement,
                'solution_description': sub.solution_description,
                'github_url': sub.github_url,
                'demo_url': sub.demo_url,
                'presentation_url': sub.presentation_url,
                'tech_stack': sub.tech_stack,
                'is_draft': sub.is_draft,
                'created_at': sub.created_at.isoformat() if sub.created_at else None,
            })

        archive['teams'].append(team_data)

    # 3. Evaluations
    for ev in ProjectEvaluation.objects.filter(submission__team__event=event).select_related('judge', 'submission__team').prefetch_related('scores__rubric'):
        archive['evaluations'].append({
            'judge_username': ev.judge.username,
            'submission_title': ev.submission.title,
            'team_name': ev.submission.team.name,
            'total_score': float(ev.total_score),
            'feedback': ev.feedback,
            'scores': [
                {
                    'rubric_title': s.rubric.title,
                    'score': float(s.score),
                }
                for s in ev.scores.all()
            ],
        })

    # 4. Community Votes
    for vote in CommunityVote.objects.filter(submission__team__event=event).select_related('voter', 'submission'):
        archive['community_votes'].append({
            'voter_username': vote.voter.username,
            'submission_title': vote.submission.title,
            'created_at': vote.created_at.isoformat(),
            'is_void': vote.is_void,
        })

    # 5. Comments
    for comm in CommunityComment.objects.filter(submission__team__event=event).select_related('author', 'submission'):
        archive['comments'].append({
            'author_username': comm.author.username,
            'submission_title': comm.submission.title,
            'text': comm.text,
            'created_at': comm.created_at.isoformat(),
        })

    # 6. Certificates
    for cert in event.certificates.all():
        archive['certificates'].append({
            'recipient_name': cert.recipient_name,
            'recipient_email': cert.recipient_email,
            'role': cert.role,
            'title': cert.title,
            'award_title': cert.award_title,
            'certificate_code': cert.certificate_code,
            'signature': cert.signature,
            'issued_at': cert.issued_at.isoformat(),
        })

    # Compute Checksum of the body
    archive['checksum'] = compute_digest(archive)

    dispatch_webhook(
        event,
        WebhookEndpoint.EventType.EVENT_EXPORTED,
        {
            'event_id': event.id,
            'event_title': event.title,
            'teams_count': len(archive['teams']),
            'checksum': archive['checksum'],
        },
    )

    return archive


def import_event_archive(archive_data, organizer_user):
    """
    Import and restore an entire event from a portable JSON archive.
    Recreates rubrics, teams, members, and project submissions under organizer_user.
    """
    event_data = archive_data.get('event')
    if not event_data or not event_data.get('title'):
        raise ValueError("Invalid event archive: missing event payload or title.")

    vr = event_data.get('voting_rules', {})

    with transaction.atomic():
        # 1. Create or Recreate Event
        imported_event = Event.objects.create(
            title=event_data['title'] + " (Imported)",
            description=event_data.get('description', ''),
            start_date=event_data.get('start_date') or timezone.now(),
            end_date=event_data.get('end_date') or (timezone.now() + timezone.timedelta(days=2)),
            mode=event_data.get('mode', 'virtual'),
            location=event_data.get('location', 'Online'),
            prize_pool=event_data.get('prize_pool', ''),
            max_team_size=event_data.get('max_team_size', 4),
            results_published=event_data.get('results_published', False),
            created_by=organizer_user,
            community_voting_start=vr.get('window_start'),
            community_voting_end=vr.get('window_end'),
            votes_per_user=vr.get('votes_per_user', 3),
            voting_eligibility=vr.get('eligibility', Event.VotingEligibility.ANY_USER),
            allow_self_vote=vr.get('allow_self_vote', False),
            show_community_voting_results=vr.get('show_community_voting_results', False),
            comments_enabled=vr.get('comments_enabled', True),
        )

        # 2. Rubrics
        for r in archive_data.get('rubrics', []):
            EventRubric.objects.create(
                event=imported_event,
                title=r.get('title') or r.get('name', 'General Criteria'),
                description=r.get('description', ''),
                weight=r.get('weight', 20.0),
                max_score=r.get('max_score', 10),
            )

        # 3. Teams & Members
        created_submissions = {}
        for t_info in archive_data.get('teams', []):
            # Find or create leader
            members_info = t_info.get('members', [])
            leader_username = next((m['username'] for m in members_info if m.get('is_leader')), None)
            if not leader_username and members_info:
                leader_username = members_info[0]['username']

            leader_user = None
            if leader_username:
                leader_user, _ = User.objects.get_or_create(
                    username=leader_username,
                    defaults={'email': f"{leader_username}@imported.local", 'role': User.Role.PARTICIPANT},
                )
            else:
                leader_user = organizer_user

            team_code = t_info.get('code')
            if not team_code or Team.objects.filter(code=team_code).exists():
                team_code = f"IMP-{secrets.token_hex(3).upper()}"
                while Team.objects.filter(code=team_code).exists():
                    team_code = f"IMP-{secrets.token_hex(3).upper()}"

            team = Team.objects.create(
                event=imported_event,
                name=t_info.get('name', 'Team'),
                leader=leader_user,
                code=team_code,
            )

            for m in members_info:
                u, _ = User.objects.get_or_create(
                    username=m['username'],
                    defaults={'email': m.get('email') or f"{m['username']}@imported.local", 'role': User.Role.PARTICIPANT},
                )
                TeamMember.objects.get_or_create(
                    team=team,
                    user=u,
                )

            # Submissions
            for s in t_info.get('submissions', []):
                sub = ProjectSubmission.objects.create(
                    team=team,
                    title=s.get('title', 'Project Submission'),
                    tagline=s.get('tagline', ''),
                    problem_statement=s.get('problem_statement', ''),
                    solution_description=s.get('solution_description', ''),
                    github_url=s.get('github_url', 'https://github.com'),
                    demo_url=s.get('demo_url', ''),
                    presentation_url=s.get('presentation_url', ''),
                    tech_stack=s.get('tech_stack', ''),
                    is_draft=s.get('is_draft', False),
                    submitted_by=leader_user,
                )
                created_submissions[sub.title] = sub

        dispatch_webhook(
            imported_event,
            WebhookEndpoint.EventType.EVENT_IMPORTED,
            {
                'event_id': imported_event.id,
                'event_title': imported_event.title,
                'teams_count': imported_event.teams.count(),
            },
        )

    return imported_event


def import_teams_csv(event, csv_content):
    """
    Bulk import teams and participants from CSV.
    Expected header: team_name, username, [email], [is_leader]
    """
    if isinstance(csv_content, bytes):
        csv_content = csv_content.decode('utf-8-sig')

    reader = csv.DictReader(io.StringIO(csv_content))
    teams_created = 0
    members_added = 0

    with transaction.atomic():
        team_cache = {}

        for row in reader:
            team_name = (row.get('team_name') or row.get('team') or '').strip()
            username = (row.get('username') or row.get('user') or '').strip()
            email = (row.get('email') or '').strip()
            is_leader_raw = (row.get('is_leader') or row.get('leader') or '').strip().lower()
            is_leader = is_leader_raw in ('1', 'true', 'yes', 'y')

            if not team_name or not username:
                continue

            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'email': email or f"{username}@hackathon.local", 'role': User.Role.PARTICIPANT},
            )

            if team_name not in team_cache:
                team, created = Team.objects.get_or_create(
                    event=event,
                    name=team_name,
                    defaults={'leader': user},
                )
                if created:
                    teams_created += 1
                team_cache[team_name] = team
            else:
                team = team_cache[team_name]

            _, member_created = TeamMember.objects.get_or_create(
                team=team,
                user=user,
            )
            if is_leader and team.leader_id != user.id:
                team.leader = user
                team.save(update_fields=['leader'])
            if member_created:
                members_added += 1

        dispatch_webhook(
            event,
            WebhookEndpoint.EventType.TEAM_CREATED,
            {
                'event_id': event.id,
                'teams_created': teams_created,
                'members_added': members_added,
            },
        )

    return {'teams_created': teams_created, 'members_added': members_added}
