import math
import random
from typing import Dict, List, Set, Tuple, Any
from django.db import transaction
from .models import Event, ProjectSubmission, JudgeAssignment, TeamMember


class JudgeAssignmentEngine:
    """
    Load-Balanced, Conflict-of-Interest-Free Bipartite Judge Allocation Algorithm.
    Ensures each submission is assigned to at least K judges while strictly enforcing
    COI boundaries and preventing reviewer fatigue.
    """

    @classmethod
    def assign_judges_for_event(
        cls,
        event: Event,
        k_per_project: int = 3,
        slack: int = 1,
        clear_existing_pending: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes assignment on the database for all non-draft submissions of the event.
        """
        submissions = list(
            ProjectSubmission.objects.filter(team__event=event, is_draft=False).select_related('team', 'track')
        )
        judges = list(event.judges.all())

        num_subs = len(submissions)
        num_judges = len(judges)

        if num_subs == 0:
            return {
                'success': False,
                'detail': 'No submitted projects found to assign. Ensure teams have submitted non-draft projects.',
            }

        if num_judges == 0:
            return {
                'success': False,
                'detail': 'No judges appointed to this event yet. Search and appoint judges before running auto-assignment.',
            }

        # Cap k_per_project if fewer judges exist than k
        effective_k = min(k_per_project, num_judges)
        total_demand = num_subs * effective_k
        max_workload = math.ceil(total_demand / num_judges) + slack

        # Build Conflict-of-Interest (COI) matrix:
        # A judge cannot evaluate their own project or any project where they belong to the team
        team_memberships = TeamMember.objects.filter(team__event=event).values('team_id', 'user_id')
        team_to_members: Dict[int, Set[int]] = {}
        for tm in team_memberships:
            team_to_members.setdefault(tm['team_id'], set()).add(tm['user_id'])

        coi_map: Dict[int, Set[int]] = {}  # submission_id -> set of forbidden judge user_ids
        for sub in submissions:
            members = team_to_members.get(sub.team_id, set())
            # Add author directly
            if sub.submitted_by_id:
                members.add(sub.submitted_by_id)
            coi_map[sub.id] = members

        # Check existing completed assignments so we don't duplicate or overwrite finished reviews
        existing_completed = set(
            JudgeAssignment.objects.filter(event=event, status=JudgeAssignment.Status.COMPLETED).values_list(
                'judge_id', 'submission_id'
            )
        )

        judge_workload: Dict[int, int] = {j.id: 0 for j in judges}
        project_assignments: Dict[int, Set[int]] = {s.id: set() for s in submissions}

        # Seed with existing completed evaluations
        for j_id, s_id in existing_completed:
            if j_id in judge_workload and s_id in project_assignments:
                project_assignments[s_id].add(j_id)
                judge_workload[j_id] += 1

        # Heuristic: Sort submissions by fewest viable conflict-free judges first (Most Constrained First)
        def get_viable(sub):
            forbidden = coi_map.get(sub.id, set())
            already_assigned = project_assignments[sub.id]
            return [
                j
                for j in judges
                if j.id not in forbidden
                and j.id not in already_assigned
                and judge_workload[j.id] < max_workload
            ]

        sorted_submissions = sorted(submissions, key=lambda s: len(get_viable(s)))
        deficits: List[Dict[str, Any]] = []

        # Run bipartite assignment
        for sub in sorted_submissions:
            while len(project_assignments[sub.id]) < effective_k:
                viable = get_viable(sub)
                if not viable:
                    # If max_workload is temporarily reached for all viable judges, relax workload cap by 1
                    relaxed = [
                        j
                        for j in judges
                        if j.id not in coi_map.get(sub.id, set())
                        and j.id not in project_assignments[sub.id]
                    ]
                    if not relaxed:
                        # Cannot assign more without violating the hard COI constraint
                        deficits.append({
                            'submission_id': sub.id,
                            'title': sub.title,
                            'assigned': len(project_assignments[sub.id]),
                            'target': effective_k,
                        })
                        break
                    viable = relaxed

                # Priority: 1) Least loaded judge, 2) Random tie-breaker
                def judge_priority(j):
                    return (judge_workload[j.id], random.random())

                chosen = min(viable, key=judge_priority)
                project_assignments[sub.id].add(chosen.id)
                judge_workload[chosen.id] += 1

        with transaction.atomic():
            if clear_existing_pending:
                # Remove only pending assignments to re-distribute cleanly
                JudgeAssignment.objects.filter(
                    event=event, status=JudgeAssignment.Status.PENDING
                ).delete()

            new_assignment_objects = []
            for sub in submissions:
                for j_id in project_assignments[sub.id]:
                    if (j_id, sub.id) not in existing_completed:
                        new_assignment_objects.append(
                            JudgeAssignment(
                                event=event,
                                judge_id=j_id,
                                submission=sub,
                                status=JudgeAssignment.Status.PENDING,
                            )
                        )
            JudgeAssignment.objects.bulk_create(new_assignment_objects, ignore_conflicts=True)

        judge_name_map = {j.id: j.username for j in judges}
        workload_distribution = {
            judge_name_map.get(j_id, f"User {j_id}"): load
            for j_id, load in judge_workload.items()
        }

        return {
            'success': True,
            'total_submissions': num_subs,
            'total_judges': num_judges,
            'target_k': effective_k,
            'total_assignments_created': len(new_assignment_objects),
            'workload_distribution': workload_distribution,
            'max_workload': max_workload,
            'fully_saturated': not deficits,
            'deficits': deficits,
            'warning': (
                f"{len(deficits)} project(s) could not reach {effective_k} conflict-free judges. "
                "Appoint more judges and re-run."
            ) if deficits else None,
        }
