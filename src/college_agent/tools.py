"""What the agent can actually do.

A tool is just a Python function. Agno turns it into a schema the model can
call, using your **type hints** for the parameters and your **docstring** for
the descriptions. That is the whole mechanism — there is no magic layer.

Which means the docstrings below are not documentation for you. They are the
prompt the model reads when deciding whether to call this function. Write them
for the model, and write them precisely; a vague docstring is a vague tool, and
a vague tool gets called at the wrong moment.

Three rules this file follows, all of them learned by watching agents misbehave:

**Say when to use it, not just what it does.** "Look up a student" is weak.
"Look up a student by roll number. Call this first whenever a roll number is
mentioned" tells the model about *timing*.

**Never raise for ordinary misses.** An unknown roll number returns a sentence
saying so. If a tool throws, the loop breaks; if it explains, the model can
recover and try something else.

**Keep the parameters primitive.** Gemini rejects large or nested tool schemas
with unhelpful errors. Strings and ints only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .data.seed import DB_PATH, ensure_db, has_fts5

# Build the database on first import so a fresh clone just works.
ensure_db()


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------
# Read-only lookups
# --------------------------------------------------------------------------


def lookup_student(roll_no: str) -> str:
    """Look up a student's basic record by roll number.

    Call this first whenever a roll number is mentioned, before deciding
    anything else. Knowing the student's programme and year often settles the
    question on its own.

    Args:
        roll_no: The student's roll number, for example "CS21B001".
                 Case-insensitive.
    """
    roll_no = roll_no.strip().upper()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,)).fetchone()

    if row is None:
        return (
            f"No student found with roll number {roll_no!r}. "
            "Do not guess another roll number — ask the student to confirm it."
        )

    return (
        f"{row['roll_no']}: {row['name']}, {row['program']}, year {row['year']}. "
        f"Email {row['email']}. Enrolment status: {row['status']}."
    )


def check_fee_status(roll_no: str) -> str:
    """Check what a student owes, what they've paid, and whether they're fee-blocked.

    Use this for anything about money, and also whenever a student cannot get a
    hall ticket or a transcript — those are withheld for unpaid fees, so the
    real cause is often here rather than in the examinations record.

    Args:
        roll_no: The student's roll number, for example "CS21B001".
    """
    roll_no = roll_no.strip().upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM fees WHERE roll_no = ? ORDER BY semester DESC LIMIT 1",
            (roll_no,),
        ).fetchone()

    if row is None:
        return f"No fee record for {roll_no!r}. Confirm the roll number is correct."

    balance = row["amount_due"] - row["amount_paid"]
    parts = [
        f"Fees for {roll_no} ({row['semester']}): "
        f"due Rs.{row['amount_due']:,}, paid Rs.{row['amount_paid']:,}, "
        f"balance Rs.{balance:,}.",
        f"Status: {row['status']}. Due date was {row['due_date']}.",
    ]

    if row["last_payment_ref"]:
        parts.append(f"Last payment: {row['last_payment_ref']} on {row['last_payment_date']}.")
    else:
        parts.append("No payment recorded.")

    # The single most common false alarm at the accounts desk. Flagging it here
    # saves the agent from escalating a problem that will fix itself.
    if row["status"] == "pending" and row["last_payment_ref"].startswith(("NEFT", "IMPS")):
        parts.append(
            "NOTE: this was a bank transfer, which takes 2-3 working days to "
            "reconcile. A 'pending' status inside that window is expected and "
            "usually means nothing is wrong."
        )

    if row["status"] == "blocked":
        parts.append(
            "NOTE: this student is FEE-BLOCKED. Hall tickets and transcripts are "
            "withheld until the balance is cleared."
        )

    return " ".join(parts)


def check_hostel_status(roll_no: str) -> str:
    """Check a student's hostel allotment, room, mess plan and warden.

    Use this for anything about accommodation, rooms, mess or wardens.

    Args:
        roll_no: The student's roll number, for example "CS21B001".
    """
    roll_no = roll_no.strip().upper()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM hostel WHERE roll_no = ?", (roll_no,)).fetchone()

    if row is None:
        return f"No hostel record for {roll_no!r}. Confirm the roll number is correct."

    status = row["status"]

    if status == "allotted":
        return (
            f"{roll_no} is allotted {row['block']} room {row['room_no']}. "
            f"Mess plan: {row['mess_plan']}. Warden: {row['warden']}."
        )
    if status == "waiting_list":
        return (
            f"{roll_no} is on the hostel waiting list. "
            "Position on the waiting list is NOT disclosed to students — it changes "
            "constantly and quoting it creates expectations the office cannot meet. "
            "Tell the student they will be emailed if a room becomes available."
        )
    if status == "day_scholar":
        return f"{roll_no} is registered as a day scholar and has no hostel allotment."
    return f"{roll_no} hostel status: {status}."


def check_exam_status(roll_no: str) -> str:
    """Check attendance, hall ticket status, backlogs and results for a student.

    Use this for hall tickets, results, attendance and re-evaluation.

    Important: a withheld hall ticket has two possible causes — unpaid fees or
    attendance below 75%. This tool tells you which one. If it is fees, the
    ticket belongs to accounts, not examinations.

    Args:
        roll_no: The student's roll number, for example "CS21B001".
    """
    roll_no = roll_no.strip().upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM exams WHERE roll_no = ? ORDER BY semester DESC LIMIT 1",
            (roll_no,),
        ).fetchone()

    if row is None:
        return f"No examination record for {roll_no!r}. Confirm the roll number is correct."

    parts = [
        f"Examinations for {roll_no} ({row['semester']}): "
        f"attendance {row['attendance_pct']}%, {row['backlogs']} backlog(s), "
        f"results {row['results_status']}.",
        f"Hall ticket: {row['hall_ticket_status']}.",
    ]

    if row["hall_ticket_status"] == "withheld_fees":
        parts.append(
            "The hall ticket is withheld because of UNPAID FEES, not for any "
            "examination reason. This is an accounts problem — examinations cannot "
            "release it until the fee block clears."
        )
    elif row["hall_ticket_status"] == "withheld_attendance":
        parts.append(
            f"The hall ticket is withheld because attendance is {row['attendance_pct']}%, "
            "below the required 75%. Fees are not the cause. A medical exemption "
            "needs the Head of Department's approval."
        )

    return " ".join(parts)


def search_policy(query: str) -> str:
    """Search college policy documents — fees, hostel, examinations, admissions, IT.

    Use this whenever the answer depends on a rule, a deadline, a fee amount or
    a procedure. Do not answer policy questions from memory: quote the policy.

    Args:
        query: Keywords to search for, for example "re-evaluation deadline" or
               "bonafide certificate". Two or three words works better than a
               full sentence.
    """
    query = query.strip()
    if not query:
        return "Empty search. Provide two or three keywords."

    with _connect() as conn:
        rows = []
        if has_fts5(conn):
            # Quote each term so the user's punctuation can't become FTS5
            # syntax and blow up the query.
            terms = " OR ".join(f'"{t}"' for t in query.split() if t)
            try:
                rows = conn.execute(
                    "SELECT doc, section, content FROM policies "
                    "WHERE policies MATCH ? ORDER BY rank LIMIT 4",
                    (terms,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

        if not rows:
            # Either no FTS5, or the match found nothing. Fall back to LIKE.
            like = f"%{query}%"
            rows = conn.execute(
                "SELECT doc, section, content FROM policies "
                "WHERE content LIKE ? OR section LIKE ? LIMIT 4",
                (like, like),
            ).fetchall()

    if not rows:
        return (
            f"No policy section matched {query!r}. Try fewer or more general "
            "keywords, for example 'refund' instead of 'refund for withdrawal'."
        )

    out = []
    for row in rows:
        body = row["content"].strip()
        if len(body) > 700:
            body = body[:700].rsplit(" ", 1)[0] + " ..."
        out.append(f"[{row['doc']} / {row['section']}]\n{body}")

    return "\n\n".join(out)


# --------------------------------------------------------------------------
# The one tool that writes
# --------------------------------------------------------------------------


def create_ticket(roll_no: str, message: str, department: str, urgency: str) -> str:
    """File a ticket with a department so a human picks it up.

    Only call this once you have decided where the ticket belongs. Filing it in
    the wrong queue is worse than not filing it — it will sit unread.

    Args:
        roll_no: The student's roll number, or "UNKNOWN" if you could not
                 establish it.
        message: A one or two sentence summary of the problem, factual.
        department: One of accounts, hostel, examinations, admissions, it_support.
        urgency: One of low, normal, high, critical.
    """
    valid_departments = {"accounts", "hostel", "examinations", "admissions", "it_support"}
    valid_urgency = {"low", "normal", "high", "critical"}

    department = department.strip().lower()
    urgency = urgency.strip().lower()

    # Validate rather than trust. The model is usually right about these, but
    # "usually" is how you end up with tickets in a queue nobody reads.
    if department not in valid_departments:
        return (
            f"Rejected: {department!r} is not a department. "
            f"Use one of: {', '.join(sorted(valid_departments))}."
        )
    if urgency not in valid_urgency:
        return (
            f"Rejected: {urgency!r} is not a valid urgency. "
            f"Use one of: {', '.join(sorted(valid_urgency))}."
        )

    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (roll_no, message, department, urgency, status) "
            "VALUES (?,?,?,?,'open')",
            (roll_no.strip().upper() or "UNKNOWN", message.strip(), department, urgency),
        )
        conn.commit()
        ticket_id = cur.lastrowid

    return (
        f"Ticket #{ticket_id} filed with {department} at {urgency} urgency "
        f"for {roll_no.strip().upper() or 'UNKNOWN'}."
    )


# The set the triage agent gets. Six tools — Gemini's guidance is to keep the
# active set to 10-20 at most, and in practice a smaller, sharper set produces
# noticeably better tool choice than a large one.
TRIAGE_TOOLS = [
    lookup_student,
    check_fee_status,
    check_hostel_status,
    check_exam_status,
    search_policy,
    create_ticket,
]
