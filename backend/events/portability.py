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


class ArchiveIntegrityError(ValueError):
    pass


def _unique_username(base):
    base = (base or 'imported')[:120]
    candidate = base
    n = 1
    while User.objects.filter(username=candidate).exists():
        n += 1
        candidate = f"{base}_imp{n}"
    return candidate


def _unique_email(preferred, username):
    email = (preferred or '').strip().lower()
    if not email or User.objects.filter(email__iexact=email).exists():
        email = f"{username}.{secrets.token_hex(3)}@imported.local"
    return email


def _placeholder_user(username, email=''):
    """
    Create a NEW account that cannot log in until an admin sets a password.
    Archive imports never attach existing accounts: a crafted archive could otherwise put
    real users (or judges) onto teams without their consent.
    """
    uname = _unique_username(username)
    user = User(username=uname, email=_unique_email(email, uname), role=User.Role.PARTICIPANT)
    user.set_unusable_password()
    user.save()
    return user


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

    # Integrity: the export embeds SHA-256 of its own body; reject edited or truncated archives.
    claimed = archive_data.get('checksum')
    if claimed:
        body = {k: v for k, v in archive_data.items() if k != 'checksum'}
        if compute_digest(body) != claimed:
            raise ArchiveIntegrityError('Archive checksum mismatch: the file was modified or corrupted.')

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
            results_published=False,  # evaluations are not imported, so there is nothing to publish yet
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

            # Every imported person becomes a fresh placeholder account (see _placeholder_user)
            people = {}
            for m in members_info:
                if m.get('username') and m['username'] not in people:
                    people[m['username']] = _placeholder_user(m['username'], m.get('email'))
            leader_user = people.get(leader_username) or organizer_user

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

            for u in people.values():
                TeamMember.objects.create(team=team, user=u)

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

    Existing accounts are linked by username (that is the point of a roster import), but every row
    goes through the same rules as the UI: one team per user per event, team capacity, and no
    judges/organizer of this event on a team (conflict of interest). Bad rows are skipped and reported;
    good rows are still imported.
    """
    from django.core.exceptions import ValidationError

    if isinstance(csv_content, bytes):
        csv_content = csv_content.decode('utf-8-sig')

    reader = csv.DictReader(io.StringIO(csv_content))
    teams_created = 0
    members_added = 0
    users_created = 0
    skipped = []
    judge_ids = set(event.judges.values_list('id', flat=True))

    with transaction.atomic():
        team_cache = {}

        for line_no, row in enumerate(reader, start=2):
            team_name = (row.get('team_name') or row.get('team') or '').strip()
            username = (row.get('username') or row.get('user') or '').strip()
            email = (row.get('email') or '').strip()
            is_leader = (row.get('is_leader') or row.get('leader') or '').strip().lower() in ('1', 'true', 'yes', 'y')

            if not team_name or not username:
                skipped.append({'line': line_no, 'reason': 'team_name and username are required'})
                continue

            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(username=username, email=_unique_email(email, username), role=User.Role.PARTICIPANT)
                user.set_unusable_password()
                user.save()
                users_created += 1

            if user.id in judge_ids or user.id == event.created_by_id:
                skipped.append({'line': line_no, 'username': username,
                                'reason': 'is a judge or the organizer of this event (conflict of interest)'})
                continue

            team = team_cache.get(team_name)
            if team is None:
                team = Team.objects.filter(event=event, name__iexact=team_name).first()
                if team is None:
                    team = Team.objects.create(event=event, name=team_name, leader=user)
                    teams_created += 1
                team_cache[team_name] = team

            if not TeamMember.objects.filter(team=team, user=user).exists():
                try:
                    with transaction.atomic():
                        TeamMember.objects.create(team=team, user=user)
                    members_added += 1
                except ValidationError as exc:
                    skipped.append({'line': line_no, 'username': username, 'reason': '; '.join(exc.messages)})
                    continue

            if is_leader and team.leader_id != user.id:
                team.leader = user
                team.save(update_fields=['leader'])

        # Remove teams we created that ended up with nobody in them (all rows rejected)
        for team in team_cache.values():
            if not team.memberships.exists():
                team.delete()
                teams_created -= 1

        dispatch_webhook(
            event,
            WebhookEndpoint.EventType.TEAM_CREATED,
            {
                'event_id': event.id,
                'teams_created': teams_created,
                'members_added': members_added,
            },
        )

    return {
        'teams_created': teams_created,
        'members_added': members_added,
        'users_created': users_created,
        'skipped': skipped,
    }
