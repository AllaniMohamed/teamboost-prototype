from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime
import re

from app.database import db
from app.models import (
    Task,
    Engineer,
    PREvent,
    Dependency,
    Investigation
)
from app.services import search_related_tasks


def to_roman(n):
    """Convert integer to Roman numeral (1–50 is sufficient)."""
    if n < 1 or n > 50:
        return str(n)
    roman_map = [
        (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
        (5, "V"), (4, "IV"), (1, "I")
    ]
    result = []
    for value, symbol in roman_map:
        while n >= value:
            result.append(symbol)
            n -= value
    return "".join(result)


def sanitize_anchor(text):
    """Create a safe anchor ID from a team name."""
    return re.sub(r'[^a-zA-Z0-9]', '_', text)


def generate_manager_report():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    heading = styles["Heading2"]
    title_style = styles["Title"]
    h1_style = styles["Heading1"]

    # Custom style for clickable TOC entries
    toc_style = ParagraphStyle(
        "TOCStyle",
        parent=normal,
        fontSize=10,
        leading=12,
        leftIndent=0,
        textColor="#0066cc"
    )

    # Title and generation info
    elements.append(Paragraph("<b>TeamBoostAI – System Bottleneck Diagnostic Report</b>", title_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        normal
    ))
    elements.append(Spacer(1, 0.4 * inch))

    # ==========================================
    # 1️⃣ Collect and group data
    # ==========================================

    # Detect stalled tasks
    all_tasks = Task.query.all()
    stalled_tasks = []
    for task in all_tasks:
        failed_pr = PREvent.query.filter_by(task_id=task.id, status="failed").first()
        is_overdue = False
        if task.due_date:
            try:
                due = datetime.strptime(task.due_date, "%Y-%m-%d")
                is_overdue = due < datetime.utcnow()
            except:
                pass
        if (
            failed_pr
            or task.status in ["blocked", "in_review"]
            or (task.status == "in_progress" and is_overdue)
        ):
            stalled_tasks.append(task)

    # Group stalled tasks by team
    tasks_by_team = {}
    for task in stalled_tasks:
        team = task.team if task.team else "Unassigned"
        tasks_by_team.setdefault(team, []).append(task)

    # Group investigations by team (via task relationship)
    investigations_query = db.session.query(Investigation, Task.team).outerjoin(
        Task, Investigation.task_id == Task.id
    ).all()
    inv_by_team = {}
    for inv, team in investigations_query:
        if not inv.task_id:
            continue  # skip investigations without a linked task
        team = team if team else "Other"
        inv_by_team.setdefault(team, []).append(inv)

    # Sort teams alphabetically
    sorted_teams = sorted(tasks_by_team.keys())
    sorted_inv_teams = sorted(inv_by_team.keys())

    # ==========================================
    # 2️⃣ Clickable summary (first page)
    # ==========================================

    elements.append(Paragraph("<b>📋 Clickable Summary</b>", h1_style))
    elements.append(Spacer(1, 0.1 * inch))

    # Stalled tasks section
    elements.append(Paragraph("<b>Stalled Tasks by Team</b>", heading))
    elements.append(Spacer(1, 0.1 * inch))
    for team in sorted_teams:
        anchor = sanitize_anchor(team)
        link = f'<a href="#team_{anchor}">{team}</a>'
        task_count = len(tasks_by_team[team])
        elements.append(Paragraph(f"• {link} – {task_count} stalled task(s)", toc_style))
    elements.append(Spacer(1, 0.2 * inch))

    # Investigations section
    if sorted_inv_teams:
        elements.append(Paragraph("<b>Investigations by Team (Appendix)</b>", heading))
        elements.append(Spacer(1, 0.1 * inch))
        for idx, team in enumerate(sorted_inv_teams, start=1):
            anchor = sanitize_anchor(team)
            roman = to_roman(idx)
            link = f'<a href="#app_{anchor}">{roman}. {team}</a>'
            inv_count = len(inv_by_team[team])
            elements.append(Paragraph(f"• {link} – {inv_count} investigation(s)", toc_style))
    elements.append(PageBreak())

    # ==========================================
    # 3️⃣ Stalled tasks – one page per team
    # ==========================================

    for team in sorted_teams:
        # Anchor for summary link
        anchor = sanitize_anchor(team)
        elements.append(Paragraph(f'<a name="team_{anchor}"/>', normal))
        elements.append(Paragraph(f"<b>Team: {team}</b>", h1_style))
        elements.append(Spacer(1, 0.2 * inch))

        for task in tasks_by_team[team]:
            owner = Engineer.query.get(task.owner_id)

            elements.append(Paragraph(f"<b>Task:</b> {task.id} — {task.title}", heading))
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(Paragraph(
                f"<b>Owner:</b> {owner.name if owner else 'Unknown'} | "
                f"<b>Status:</b> {task.status} | <b>Due:</b> {task.due_date}",
                normal
            ))
            elements.append(Spacer(1, 0.15 * inch))

            # Failed PR info
            failed_pr = PREvent.query.filter_by(task_id=task.id, status="failed").first()
            if failed_pr:
                elements.append(Paragraph(f"<b>PR Failure:</b> {failed_pr.pr_id}", normal))
                if failed_pr.ci_message:
                    elements.append(Paragraph(f"<b>CI Error:</b> {failed_pr.ci_message}", normal))
                elements.append(Spacer(1, 0.1 * inch))

            # Downstream impact
            dependencies = Dependency.query.filter_by(depends_on_task_id=task.id).all()
            if dependencies:
                blocked_tasks = [dep.task_id for dep in dependencies]
                elements.append(Paragraph(
                    f"<b>Downstream Impact:</b> Blocking tasks {blocked_tasks}",
                    normal
                ))
                elements.append(Spacer(1, 0.1 * inch))

            # Semantic related tasks
            related = search_related_tasks(
                task.id,
                k=3,
                min_score=0.4,
                filters={"exclude_task_id": task.id}
            )
            if related:
                related_ids = [r["task_id"] for r in related]
                elements.append(Paragraph(f"<b>Related Tasks (Semantic):</b> {related_ids}", normal))

            elements.append(Spacer(1, 0.3 * inch))

        # Start next team on a new page (unless it's the last team)
        if team != sorted_teams[-1]:
            elements.append(PageBreak())

    # ==========================================
    # 4️⃣ Appendix – Investigations by team (Roman chapters)
    # ==========================================

    if sorted_inv_teams:
        elements.append(PageBreak())
        elements.append(Paragraph("<b>Appendix – AI Investigation Outputs</b>", h1_style))
        elements.append(Spacer(1, 0.3 * inch))

        for idx, team in enumerate(sorted_inv_teams, start=1):
            anchor = sanitize_anchor(team)
            roman = to_roman(idx)
            # Anchor for summary link
            elements.append(Paragraph(f'<a name="app_{anchor}"/>', normal))
            elements.append(Paragraph(f"<b>{roman}. {team}</b>", h1_style))
            elements.append(Spacer(1, 0.2 * inch))

            for inv in inv_by_team[team]:
                elements.append(Paragraph(f"<b>Task ID:</b> {inv.task_id}", heading))
                elements.append(Spacer(1, 0.1 * inch))
                elements.append(Paragraph(f"<b>Classification:</b> {inv.classification}", normal))
                elements.append(Paragraph(f"<b>Notification:</b> {inv.notification}", normal))
                elements.append(Spacer(1, 0.2 * inch))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer