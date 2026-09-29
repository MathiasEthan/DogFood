import html
from django.utils import timezone
from .models import Certificate, JudgeParticipationRecord, WebhookEndpoint
from .webhooks import dispatch_webhook


def generate_certificate_svg(certificate):
    """
    Generate an elegant, high-resolution vector SVG certificate.
    Completely self-contained with vector graphics, guilloche borders, and cryptographic verification seal.
    """
    recipient = html.escape(certificate.recipient_name)
    title = html.escape(certificate.title)
    award = html.escape(certificate.award_title or "Official Recognition")
    event_title = html.escape(certificate.event.title)
    cert_code = html.escape(certificate.certificate_code)
    issued_date = certificate.issued_at.strftime("%B %d, %Y") if certificate.issued_at else timezone.now().strftime("%B %d, %Y")
    short_sig = certificate.signature[:16] + "..." + certificate.signature[-8:] if certificate.signature else "VERIFIED"

    accent_color = "#10b981" if certificate.role == Certificate.Role.WINNER else "#3b82f6"
    seal_color = "#f59e0b" if certificate.role == Certificate.Role.WINNER else "#10b981"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" width="1000" height="700">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0a0a0c" />
      <stop offset="50%" stop-color="#121318" />
      <stop offset="100%" stop-color="#08080a" />
    </linearGradient>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fbbf24" />
      <stop offset="50%" stop-color="#f59e0b" />
      <stop offset="100%" stop-color="#b45309" />
    </linearGradient>
    <linearGradient id="accentGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent_color}" stop-opacity="0.8" />
      <stop offset="100%" stop-color="#6366f1" stop-opacity="0.8" />
    </linearGradient>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1" />
    </pattern>
  </defs>

  <!-- Background -->
  <rect width="1000" height="700" fill="url(#bgGrad)" />
  <rect width="1000" height="700" fill="url(#grid)" />

  <!-- Outer Borders -->
  <rect x="25" y="25" width="950" height="650" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="1" rx="8" />
  <rect x="35" y="35" width="930" height="630" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" rx="6" />
  <rect x="42" y="42" width="916" height="616" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1" rx="4" />

  <!-- Corner Ornaments -->
  <path d="M 45 75 L 45 45 L 75 45" fill="none" stroke="{accent_color}" stroke-width="3" />
  <path d="M 955 75 L 955 45 L 925 45" fill="none" stroke="{accent_color}" stroke-width="3" />
  <path d="M 45 625 L 45 655 L 75 655" fill="none" stroke="{accent_color}" stroke-width="3" />
  <path d="M 955 625 L 955 655 L 925 655" fill="none" stroke="{accent_color}" stroke-width="3" />

  <!-- Header Banner -->
  <text x="500" y="110" font-family="Courier, monospace" font-size="12" fill="{accent_color}" letter-spacing="6" text-anchor="middle" font-weight="bold">OFFICIAL HACKATHON CREDENTIAL</text>
  <text x="500" y="150" font-family="'Times New Roman', serif, Georgia" font-size="34" fill="#ffffff" letter-spacing="2" text-anchor="middle" font-weight="normal">{title.upper()}</text>

  <line x1="380" y1="175" x2="620" y2="175" stroke="url(#accentGrad)" stroke-width="2" />

  <!-- Recipient Section -->
  <text x="500" y="230" font-family="'Courier New', Courier, monospace" font-size="13" fill="#9ca3af" letter-spacing="3" text-anchor="middle">THIS RECOGNITION IS PROUDLY CONFERRED UPON</text>

  <text x="500" y="300" font-family="'Times New Roman', Georgia, serif" font-size="44" fill="#f3f4f6" text-anchor="middle" font-weight="bold">{recipient}</text>
  <line x1="250" y1="325" x2="750" y2="325" stroke="rgba(255,255,255,0.15)" stroke-width="1" />

  <!-- Context Statement -->
  <text x="500" y="375" font-family="'Courier New', Courier, monospace" font-size="14" fill="#d1d5db" text-anchor="middle">for distinguished participation and verified achievement in</text>
  <text x="500" y="415" font-family="'Times New Roman', Georgia, serif" font-size="28" fill="{seal_color}" font-weight="bold" text-anchor="middle">{event_title}</text>
  <text x="500" y="450" font-family="'Courier New', Courier, monospace" font-size="13" fill="#9ca3af" text-anchor="middle">Award Category: <tspan fill="#ffffff" font-weight="bold">{award}</tspan></text>

  <!-- Seal Vector Graphic -->
  <g transform="translate(500, 535)">
    <circle cx="0" cy="0" r="42" fill="none" stroke="url(#goldGrad)" stroke-width="2" stroke-dasharray="4 2" />
    <circle cx="0" cy="0" r="36" fill="rgba(245, 158, 11, 0.08)" stroke="url(#goldGrad)" stroke-width="1.5" />
    <polygon points="0,-18 5,-5 18,-5 8,4 12,17 0,9 -12,17 -8,4 -18,-5 -5,-5" fill="url(#goldGrad)" />
    <text x="0" y="27" font-family="Courier, monospace" font-size="7" fill="#fbbf24" letter-spacing="1.5" text-anchor="middle">VERIFIED CREDENTIAL</text>
  </g>

  <!-- Left: Issuer & Signature Hash -->
  <g transform="translate(100, 520)">
    <line x1="0" y1="50" x2="220" y2="50" stroke="rgba(255,255,255,0.2)" stroke-width="1" />
    <text x="110" y="40" font-family="'Courier New', Courier, monospace" font-size="11" fill="#9ca3af" text-anchor="middle">{issued_date}</text>
    <text x="110" y="68" font-family="Courier, monospace" font-size="10" fill="#6b7280" letter-spacing="1" text-anchor="middle">DATE OF ISSUANCE</text>
    <text x="110" y="90" font-family="Courier, monospace" font-size="8" fill="#4b5563" text-anchor="middle">HMAC: {short_sig}</text>
  </g>

  <!-- Right: Verification Code & Security ID -->
  <g transform="translate(680, 520)">
    <line x1="0" y1="50" x2="220" y2="50" stroke="rgba(255,255,255,0.2)" stroke-width="1" />
    <text x="110" y="40" font-family="'Courier New', Courier, monospace" font-size="12" fill="#10b981" font-weight="bold" letter-spacing="1" text-anchor="middle">{cert_code}</text>
    <text x="110" y="68" font-family="Courier, monospace" font-size="10" fill="#6b7280" letter-spacing="1" text-anchor="middle">VERIFIABLE RECORD ID</text>
    <text x="110" y="90" font-family="Courier, monospace" font-size="8" fill="#4b5563" text-anchor="middle">PUBLICLY VERIFIABLE ONLINE</text>
  </g>

  <!-- Footer Tag -->
  <text x="500" y="650" font-family="Courier, monospace" font-size="9" fill="#4b5563" letter-spacing="1" text-anchor="middle">ISSUED VIA PLATFORM REST API • CRYPTOGRAPHICALLY SECURED WITH HMAC-SHA256</text>
</svg>"""
    return svg


def issue_event_certificates(event, issued_by=None):
    """
    Issue certificates for all eligible participants, winners, and judges.
    Also updates and cryptographically signs JudgeParticipationRecords for all active judges.
    """
    created_certificates = []

    # 1. PARTICIPANTS & WINNERS
    # Look up submissions and compute leaderboard placement
    from .models import ProjectSubmission, ProjectEvaluation
    submissions = ProjectSubmission.objects.filter(team__event=event, is_draft=False)
    
    # Simple rank calculation if results exist
    ranked_submissions = []
    for sub in submissions:
        evals = sub.evaluations.all()
        avg_score = sum(e.total_score for e in evals) / len(evals) if evals else 0.0
        ranked_submissions.append((sub, avg_score))

    ranked_submissions.sort(key=lambda item: item[1], reverse=True)

    for rank, (sub, score) in enumerate(ranked_submissions, start=1):
        team = sub.team
        is_winner = rank <= 3
        award_title = "Participation"
        role = Certificate.Role.PARTICIPANT

        if rank == 1:
            award_title = "1st Place Champion"
            role = Certificate.Role.WINNER
        elif rank == 2:
            award_title = "2nd Place Runner-Up"
            role = Certificate.Role.WINNER
        elif rank == 3:
            award_title = "3rd Place Winner"
            role = Certificate.Role.WINNER

        title_text = f"{award_title} - {event.title}" if is_winner else f"Certificate of Participation - {event.title}"

        # Team level certificate
        team_cert, _ = Certificate.objects.get_or_create(
            event=event,
            recipient_user=None,
            role=role,
            award_title=f"{award_title} (Team: {team.name})",
            defaults={
                'recipient_team': team,
                'recipient_name': f"Team {team.name}",
                'title': title_text,
                'metadata': {
                    'team_id': team.id,
                    'team_name': team.name,
                    'submission_title': sub.title,
                    'rank': rank if is_winner else None,
                    'score': score,
                },
            },
        )
        created_certificates.append(team_cert)

        # Member individual certificates
        for member in team.memberships.select_related('user'):
            user = member.user
            user_display_name = f"{user.first_name} {user.last_name}".strip() or user.username
            member_cert, _ = Certificate.objects.get_or_create(
                event=event,
                recipient_user=user,
                role=role,
                award_title=f"{award_title} ({team.name})",
                defaults={
                    'recipient_team': team,
                    'recipient_name': user_display_name,
                    'recipient_email': user.email or '',
                    'title': title_text,
                    'metadata': {
                        'team_id': team.id,
                        'team_name': team.name,
                        'submission_title': sub.title,
                        'rank': rank if is_winner else None,
                        'score': score,
                    },
                },
            )
            created_certificates.append(member_cert)

    # 2. JUDGES: Issue Recognition Certificates & Signed Participation Records
    judge_users = set(event.judges.all()) | {ev.judge for ev in ProjectEvaluation.objects.filter(submission__team__event=event)}

    for judge in judge_users:
        judge_name = f"{judge.first_name} {judge.last_name}".strip() or judge.username
        judge_evals = ProjectEvaluation.objects.filter(submission__team__event=event, judge=judge)
        evals_count = judge_evals.count()
        first_eval = judge_evals.order_by('created_at').first()
        last_eval = judge_evals.order_by('-created_at').first()

        # Generate / Update Signed Judge Participation Record
        jpr, _ = JudgeParticipationRecord.objects.get_or_create(
            event=event,
            judge=judge,
        )
        jpr.evaluations_count = evals_count
        jpr.rubrics_scored_count = sum(e.scores.count() for e in judge_evals)
        jpr.first_evaluation_at = first_eval.created_at if first_eval else None
        jpr.last_evaluation_at = last_eval.created_at if last_eval else None
        jpr.sign_and_save()

        # Judge Certificate
        jcert, _ = Certificate.objects.get_or_create(
            event=event,
            recipient_user=judge,
            role=Certificate.Role.JUDGE,
            award_title="Distinguished Judge",
            defaults={
                'recipient_name': judge_name,
                'recipient_email': judge.email or '',
                'title': f"Excellence in Hackathon Evaluation - {event.title}",
                'metadata': {
                    'record_id': jpr.record_id,
                    'evaluations_completed': evals_count,
                },
            },
        )
        created_certificates.append(jcert)

    # 3. Fire Webhook
    dispatch_webhook(
        event,
        WebhookEndpoint.EventType.CERTIFICATES_ISSUED,
        {
            'event_id': event.id,
            'event_title': event.title,
            'certificates_count': len(created_certificates),
            'issued_at': timezone.now().isoformat(),
        },
    )

    return created_certificates
