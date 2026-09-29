import json
import os
from datetime import datetime, timezone as dt_timezone
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from events.models import (
    Event,
    Track,
    Team,
    TeamMember,
    ProjectSubmission,
    EventRubric,
    ProjectEvaluation,
    EvaluationScore,
    JudgeAssignment,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Loads official DOGFOOD fixtures.json into the database and generates .dogfood.toml configuration."

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=None,
            help='Path to fixtures.json (default: searches parent and current directories)',
        )
        parser.add_argument(
            '--write-toml',
            action='store_true',
            default=True,
            help='Automatically write .dogfood.toml at repository root',
        )

    def find_fixtures_file(self, explicit_path):
        if explicit_path and os.path.exists(explicit_path):
            return explicit_path

        candidates = [
            'fixtures.json',
            '../fixtures.json',
            '../../fixtures.json',
            os.path.join(os.path.dirname(__file__), '../../../../fixtures.json'),
            '/home/moksh/Work/DogFood/fixtures.json',
        ]
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
        return None

    def handle(self, *args, **options):
        file_path = self.find_fixtures_file(options['file'])
        if not file_path:
            self.stderr.write(self.style.ERROR("Could not locate fixtures.json!"))
            return

        self.stdout.write(f"==> Loading fixtures from: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        with transaction.atomic():
            # 1. Organizer / Admin Account
            admin_user, _ = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@hackathon.local',
                    'role': User.Role.ADMIN,
                    'is_staff': True,
                    'is_superuser': True,
                },
            )
            admin_user.set_password('AdminPassword123!')
            admin_user.role = User.Role.ADMIN
            admin_user.save()

            # 2. Event
            evt_data = data.get('event', {})
            close_time_str = evt_data.get('submissions_close', '2026-03-01T18:00:00Z')
            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))

            event, created = Event.objects.get_or_create(
                id=1,
                defaults={
                    'title': evt_data.get('name', 'Sample Hack 2026'),
                    'description': 'Official DogFood 2026 benchmark event loaded from fixtures.json.',
                    'start_date': close_time.replace(month=2, day=20),
                    'end_date': close_time,
                    'mode': Event.Mode.VIRTUAL,
                    'created_by': admin_user,
                    'results_published': False,
                    'judges_per_project': 3,
                    'max_team_size': 10,
                },
            )
            event.title = evt_data.get('name', 'Sample Hack 2026')
            event.end_date = close_time
            event.max_team_size = 10
            event.save()

            # 3. Rubrics (functionality, quality, innovation)
            rubric_definitions = [
                ('Functionality', 35.0, 10, 'Technical completeness and feature stability.'),
                ('Quality', 35.0, 10, 'Code quality, polish, design, and user experience.'),
                ('Innovation', 30.0, 10, 'Novelty, creativity, and defensible technical architecture.'),
            ]
            rubric_map = {}
            for title, weight, max_score, desc in rubric_definitions:
                rubric, _ = EventRubric.objects.get_or_create(
                    event=event,
                    title=title,
                    defaults={'weight': weight, 'max_score': max_score, 'description': desc},
                )
                rubric_map[title.lower()] = rubric

            # 4. Tracks
            track_map = {}
            for t_item in data.get('tracks', []):
                trk_obj, _ = Track.objects.get_or_create(
                    event=event,
                    title=t_item['name'],
                    defaults={'description': f"Track for {t_item['name']}"},
                )
                track_map[t_item['id']] = trk_obj

            # 5. Judges
            judge_map = {}
            for j_item in data.get('judges', []):
                j_id = j_item['id']
                email = j_item['email']
                name_parts = j_item.get('name', '').split()
                first_name = name_parts[0] if name_parts else ''
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''

                j_user, _ = User.objects.get_or_create(
                    username=j_id,
                    defaults={
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'role': User.Role.JUDGE,
                    },
                )
                j_user.role = User.Role.JUDGE
                j_user.set_password('JudgePassword123!')
                j_user.save()
                event.judges.add(j_user)
                judge_map[j_id] = j_user

            # Also create standard alias accounts for acceptance checker (judge_a, judge_b)
            judge_a, _ = User.objects.get_or_create(
                username='judge_a',
                defaults={
                    'email': 'judge_a@example.org',
                    'first_name': 'Judge',
                    'last_name': 'Alpha',
                    'role': User.Role.JUDGE,
                },
            )
            judge_a.role = User.Role.JUDGE
            judge_a.set_password('JudgePassword123!')
            judge_a.save()
            event.judges.add(judge_a)

            judge_b, _ = User.objects.get_or_create(
                username='judge_b',
                defaults={
                    'email': 'judge_b@example.org',
                    'first_name': 'Judge',
                    'last_name': 'Beta',
                    'role': User.Role.JUDGE,
                },
            )
            judge_b.role = User.Role.JUDGE
            judge_b.set_password('JudgePassword123!')
            judge_b.save()
            event.judges.add(judge_b)

            # 6. Teams & Members
            team_map = {}
            participant_user = None
            for t_item in data.get('teams', []):
                t_id = t_item['id']
                t_name = t_item['name']
                members = t_item.get('members', [])

                leader_email = members[0] if members else f"{t_id}@example.org"
                leader_username = leader_email.split('@')[0].replace('.', '_')
                leader_user, _ = User.objects.get_or_create(
                    username=leader_username,
                    defaults={
                        'email': leader_email,
                        'role': User.Role.PARTICIPANT,
                    },
                )
                leader_user.set_password('ParticipantPassword123!')
                leader_user.save()

                if not participant_user:
                    participant_user = leader_user

                team, _ = Team.objects.get_or_create(
                    event=event,
                    name=t_name,
                    defaults={'leader': leader_user},
                )
                team_map[t_id] = team

                # Add all members
                for m_email in members:
                    m_username = m_email.split('@')[0].replace('.', '_')
                    m_user, _ = User.objects.get_or_create(
                        username=m_username,
                        defaults={
                            'email': m_email,
                            'role': User.Role.PARTICIPANT,
                        },
                    )
                    m_user.set_password('ParticipantPassword123!')
                    m_user.save()
                    TeamMember.objects.get_or_create(team=team, user=m_user)

            # Standard named 'participant' account for acceptance testing
            test_participant, _ = User.objects.get_or_create(
                username='participant',
                defaults={
                    'email': 'participant@example.org',
                    'first_name': 'Test',
                    'last_name': 'Participant',
                    'role': User.Role.PARTICIPANT,
                },
            )
            test_participant.set_password('ParticipantPassword123!')
            test_participant.role = User.Role.PARTICIPANT
            test_participant.save()

            # Ensure test_participant is on a team
            test_team, _ = Team.objects.get_or_create(
                event=event,
                name='Team Test Participant',
                defaults={'leader': test_participant},
            )
            TeamMember.objects.get_or_create(team=test_team, user=test_participant)

            # 7. Projects (Submissions)
            project_map = {}
            for p_item in data.get('projects', []):
                p_id = p_item['id']
                team = team_map.get(p_item.get('team'))
                if not team:
                    continue

                track = track_map.get(p_item.get('track'))
                title = p_item.get('title', 'Untitled')
                summary = p_item.get('summary', '')
                repo_url = p_item.get('repo_url', 'https://github.com/example/repo')

                sub, _ = ProjectSubmission.objects.update_or_create(
                    team=team,
                    defaults={
                        'track': track,
                        'title': title,
                        'tagline': summary,
                        'problem_statement': f"Problem addressed by {title}.",
                        'solution_description': f"Technical implementation of {title}.",
                        'github_url': repo_url,
                        'demo_url': 'https://example.org/demo',
                        'submitted_by': team.leader,
                        'is_draft': False,
                    },
                )
                project_map[p_id] = sub

            # 8. Scores (Evaluations)
            evaluations_created = 0
            for s_item in data.get('scores', []):
                judge = judge_map.get(s_item.get('judge'))
                sub = project_map.get(s_item.get('project'))
                if not judge or not sub:
                    continue

                criteria = s_item.get('criteria', {})
                comment = s_item.get('comment', '')

                # Compute weighted total
                total_weighted = 0.0
                total_weight = sum(r.weight for r in rubric_map.values())
                score_items = []

                for crit_name, score_val in criteria.items():
                    rubric = rubric_map.get(crit_name.lower())
                    if rubric:
                        score_items.append((rubric, float(score_val)))
                        mark_10 = (float(score_val) / (rubric.max_score or 10)) * 10
                        total_weighted += mark_10 * (rubric.weight / total_weight)

                final_total = round(total_weighted, 2) if total_weight > 0 else 5.0

                evaluation, _ = ProjectEvaluation.objects.update_or_create(
                    submission=sub,
                    judge=judge,
                    defaults={
                        'feedback': comment,
                        'total_score': final_total,
                    },
                )
                evaluation.scores.all().delete()
                for rubric, val in score_items:
                    EvaluationScore.objects.create(evaluation=evaluation, rubric=rubric, score=val)

                JudgeAssignment.objects.update_or_create(
                    event=event,
                    judge=judge,
                    submission=sub,
                    defaults={'status': JudgeAssignment.Status.COMPLETED},
                )
                evaluations_created += 1

                # If this was scored by the first judge (jdg_01), duplicate to judge_a so judge_a sees own scores!
                if s_item.get('judge') == 'jdg_01':
                    eval_a, _ = ProjectEvaluation.objects.update_or_create(
                        submission=sub,
                        judge=judge_a,
                        defaults={
                            'feedback': comment,
                            'total_score': final_total,
                        },
                    )
                    eval_a.scores.all().delete()
                    for rubric, val in score_items:
                        EvaluationScore.objects.create(evaluation=eval_a, rubric=rubric, score=val)
                    JudgeAssignment.objects.update_or_create(
                        event=event,
                        judge=judge_a,
                        submission=sub,
                        defaults={'status': JudgeAssignment.Status.COMPLETED},
                    )

        # 9. Generate JWT Tokens
        token_organizer = str(RefreshToken.for_user(admin_user).access_token)
        token_judge_a = str(RefreshToken.for_user(judge_a).access_token)
        token_judge_b = str(RefreshToken.for_user(judge_b).access_token)
        token_participant = str(RefreshToken.for_user(test_participant).access_token)

        self.stdout.write(self.style.SUCCESS(
            f"Successfully loaded fixtures:\n"
            f"  - Event: {event.title} (ID={event.id})\n"
            f"  - Tracks: {len(track_map)}\n"
            f"  - Judges: {len(judge_map)} + 2 test judges (judge_a, judge_b)\n"
            f"  - Teams: {len(team_map)}\n"
            f"  - Projects: {len(project_map)}\n"
            f"  - Evaluations: {evaluations_created}"
        ))

        # 10. Write .dogfood.toml
        toml_content = f"""# .dogfood.toml
# Auto-generated by load_fixtures for DOGFOOD 2026 acceptance checker.

[portal]
base_url = "http://localhost:8000"

[tiers]
claimed = ["T1", "T2", "T3", "T4"]
pitch = "DogFood: Production-grade, mathematically defensible hackathon platform with empirical Bayes normalization, anti-collusion role isolation, and tamper-evident cryptographic participation verification."

[auth]
organizer   = "Authorization: Bearer {token_organizer}"
judge_a     = "Authorization: Bearer {token_judge_a}"
judge_b     = "Authorization: Bearer {token_judge_b}"
participant = "Authorization: Bearer {token_participant}"

[routes]
gallery      = "/api/events/1/gallery/"
submit       = "/api/events/1/submit/"
judge_scores = "/api/judge/scores/"
peer_scores  = "/api/judge/scores/?judge=judge_a"
csv_export   = "/api/events/1/admin/export/leaderboard-csv/"
"""

        # Locate root directory for .dogfood.toml
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../'))
        toml_path = os.path.join(root_dir, '.dogfood.toml')

        if options.get('write_toml'):
            try:
                with open(toml_path, 'w', encoding='utf-8') as tf:
                    tf.write(toml_content)
                self.stdout.write(self.style.SUCCESS(f"==> Wrote configuration to {toml_path}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not write to {toml_path}: {e}"))

        self.stdout.write("\n--- [auth] configuration for .dogfood.toml ---")
        self.stdout.write(f'organizer   = "Authorization: Bearer {token_organizer}"')
        self.stdout.write(f'judge_a     = "Authorization: Bearer {token_judge_a}"')
        self.stdout.write(f'judge_b     = "Authorization: Bearer {token_judge_b}"')
        self.stdout.write(f'participant = "Authorization: Bearer {token_participant}"')
