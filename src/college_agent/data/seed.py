"""Builds the synthetic college database.

Everything here is invented. The roll numbers, names and payment references are
made up, and deliberately so — see the warning in the README about free-tier
Gemini using your input for training. Never put real student records in here.

The data is **fixed, not random**. That's not laziness: module 3 evaluates the
agent by checking it gives the right answer, and "the right answer" only exists
if the underlying data is the same every run. A `random.seed()` would be one
Python-version upgrade away from silently invalidating every eval case.

Each student below exists to create one specific triage situation. Read the
comments — they're the answer key for the eval suite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "college.db"
KB_DIR = DATA_DIR.parent / "kb"

# --------------------------------------------------------------------------
# Students
# (roll_no, name, program, year, email, status)
# --------------------------------------------------------------------------
STUDENTS = [
    (
        "CS21B001",
        "Aarthi Balasubramanian",
        "B.Tech Computer Science",
        4,
        "cs21b001@college.edu",
        "active",
    ),
    ("CS21B014", "Rohit Menon", "B.Tech Computer Science", 4, "cs21b014@college.edu", "active"),
    ("CS22B007", "Priya Nair", "B.Tech Computer Science", 3, "cs22b007@college.edu", "active"),
    ("EC22B031", "Imran Sheikh", "B.Tech Electronics", 3, "ec22b031@college.edu", "active"),
    ("ME23B019", "Divya Rangan", "B.Tech Mechanical", 2, "me23b019@college.edu", "active"),
    (
        "CS23B044",
        "Karthik Subramani",
        "B.Tech Computer Science",
        2,
        "cs23b044@college.edu",
        "active",
    ),
    ("EC21B009", "Sneha Iyer", "B.Tech Electronics", 4, "ec21b009@college.edu", "active"),
    ("CE22B012", "Anand Prakash", "B.Tech Civil", 3, "ce22b012@college.edu", "active"),
    ("CS24B002", "Fatima Rizvi", "B.Tech Computer Science", 1, "cs24b002@college.edu", "active"),
    ("ME21B027", "Vikram Deshpande", "B.Tech Mechanical", 4, "me21b027@college.edu", "active"),
    (
        "CS22B033",
        "Nithya Krishnan",
        "B.Tech Computer Science",
        3,
        "cs22b033@college.edu",
        "on_leave",
    ),
    ("EE23B005", "Joseph Mathew", "B.Tech Electrical", 2, "ee23b005@college.edu", "active"),
]

# --------------------------------------------------------------------------
# Fees
# (roll_no, semester, amount_due, amount_paid, due_date, status,
#  last_payment_ref, last_payment_date)
#
# status is one of: paid | pending | overdue | blocked
# "blocked" means outstanding >60 days — withholds hall tickets and transcripts.
# --------------------------------------------------------------------------
FEES = [
    # Paid up. The boring control case.
    ("CS21B001", "2025-ODD", 92000, 92000, "2025-07-15", "paid", "TXN8841207", "2025-07-11"),
    # THE classic: paid by NEFT two days ago, portal still says pending.
    # Nothing is actually wrong — this is the 2-3 day reconciliation window.
    ("CS21B014", "2025-ODD", 92000, 92000, "2025-07-15", "pending", "NEFT5520933", "2025-08-13"),
    # Fee-blocked. This is why she can't get her hall ticket, even though she
    # will write in asking Examinations about it.
    ("CS22B007", "2025-ODD", 88000, 0, "2025-07-15", "blocked", "", ""),
    ("EC22B031", "2025-ODD", 88000, 88000, "2025-07-15", "paid", "TXN8839114", "2025-07-02"),
    ("ME23B019", "2025-ODD", 85000, 85000, "2025-07-15", "paid", "TXN8840556", "2025-07-09"),
    # Partial payment, past due but not yet blocked.
    ("CS23B044", "2025-ODD", 85000, 40000, "2025-07-15", "overdue", "TXN8842001", "2025-07-14"),
    ("EC21B009", "2025-ODD", 92000, 92000, "2025-07-15", "paid", "TXN8838770", "2025-06-28"),
    ("CE22B012", "2025-ODD", 88000, 88000, "2025-07-15", "paid", "TXN8841855", "2025-07-13"),
    # First year, scholarship applied, nothing owed.
    ("CS24B002", "2025-ODD", 0, 0, "2025-07-15", "paid", "SCHOLARSHIP", "2025-07-01"),
    ("ME21B027", "2025-ODD", 92000, 92000, "2025-07-15", "paid", "TXN8837233", "2025-06-20"),
    ("CS22B033", "2025-ODD", 88000, 88000, "2025-07-15", "paid", "TXN8840012", "2025-07-05"),
    ("EE23B005", "2025-ODD", 85000, 85000, "2025-07-15", "paid", "TXN8841440", "2025-07-12"),
]

# --------------------------------------------------------------------------
# Hostel
# (roll_no, block, room_no, status, mess_plan, warden)
# status is one of: allotted | waiting_list | day_scholar | vacated
# --------------------------------------------------------------------------
HOSTEL = [
    ("CS21B001", "Block A", "A-214", "allotted", "veg_monthly", "Dr. Suresh Pillai"),
    ("CS21B014", "Block A", "A-108", "allotted", "non_veg_monthly", "Dr. Suresh Pillai"),
    ("CS22B007", "Block B", "B-301", "allotted", "veg_monthly", "Dr. Meera Joshi"),
    # On the waiting list. The office will not disclose her position — see
    # the hostel policy. A good test of whether the agent follows the rule
    # instead of being helpful.
    ("EC22B031", "", "", "waiting_list", "", ""),
    ("ME23B019", "Block C", "C-117", "allotted", "veg_monthly", "Dr. Anil Kumar"),
    ("CS23B044", "", "", "day_scholar", "", ""),
    ("EC21B009", "Block B", "B-209", "allotted", "veg_monthly", "Dr. Meera Joshi"),
    ("CE22B012", "Block C", "C-042", "allotted", "non_veg_monthly", "Dr. Anil Kumar"),
    ("CS24B002", "Block D", "D-011", "allotted", "veg_monthly", "Dr. Meera Joshi"),
    ("ME21B027", "", "", "day_scholar", "", ""),
    ("CS22B033", "Block B", "B-118", "allotted", "veg_monthly", "Dr. Meera Joshi"),
    ("EE23B005", "", "", "waiting_list", "", ""),
]

# --------------------------------------------------------------------------
# Examinations
# (roll_no, semester, attendance_pct, hall_ticket_status, backlogs,
#  results_status)
# hall_ticket_status: released | withheld_fees | withheld_attendance | pending
# --------------------------------------------------------------------------
EXAMS = [
    ("CS21B001", "2025-ODD", 88, "released", 0, "published"),
    ("CS21B014", "2025-ODD", 91, "released", 0, "published"),
    # Withheld because of the fee block, not anything exam-related.
    ("CS22B007", "2025-ODD", 82, "withheld_fees", 1, "published"),
    ("EC22B031", "2025-ODD", 79, "released", 0, "published"),
    ("ME23B019", "2025-ODD", 94, "released", 0, "published"),
    ("CS23B044", "2025-ODD", 76, "released", 2, "published"),
    # Fees are clear but attendance is 68% — under the 75% requirement.
    # Students in this state are convinced it must be a fee problem. It isn't.
    ("EC21B009", "2025-ODD", 68, "withheld_attendance", 1, "published"),
    ("CE22B012", "2025-ODD", 85, "released", 0, "published"),
    ("CS24B002", "2025-ODD", 96, "released", 0, "published"),
    ("ME21B027", "2025-ODD", 81, "released", 3, "published"),
    ("CS22B033", "2025-ODD", 71, "withheld_attendance", 0, "published"),
    ("EE23B005", "2025-ODD", 89, "released", 0, "published"),
]

# --------------------------------------------------------------------------
# A few already-triaged tickets, so the agent has precedent to look at and
# students can see what good output looks like.
# (roll_no, message, department, urgency, status)
# --------------------------------------------------------------------------
TICKETS = [
    (
        "ME23B019",
        "My mess bill shows charges for December but I went home on the 5th.",
        "hostel",
        "normal",
        "resolved",
    ),
    (
        "CE22B012",
        "Need a bonafide certificate for my passport application.",
        "admissions",
        "normal",
        "resolved",
    ),
    (
        "CS24B002",
        "Cannot log in to the portal, it says account locked.",
        "it_support",
        "high",
        "resolved",
    ),
]


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def has_fts5(conn: sqlite3.Connection) -> bool:
    """Not every Python build ships SQLite with FTS5, so we check rather than assume."""
    try:
        conn.execute("CREATE VIRTUAL TABLE _fts_probe USING fts5(x)")
        conn.execute("DROP TABLE _fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split a policy document on `##` headings.

    Retrieval works far better on sections than on whole documents — a hit on
    "re-evaluation" should return the re-evaluation rules, not the entire
    examinations policy with the answer buried in the middle.
    """
    sections: list[tuple[str, str]] = []
    heading = "Overview"
    body: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if body:
                sections.append((heading, "\n".join(body).strip()))
            heading = line[3:].strip()
            body = []
        elif line.startswith("# "):
            continue  # the document title, already captured as the doc name
        else:
            body.append(line)

    if body:
        sections.append((heading, "\n".join(body).strip()))

    return [(h, b) for h, b in sections if b]


def build(db_path: Path = DB_PATH, *, quiet: bool = False) -> Path:
    """(Re)build the database from scratch. Safe to run repeatedly."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = _connect(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE students (
            roll_no  TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            program  TEXT NOT NULL,
            year     INTEGER NOT NULL,
            email    TEXT NOT NULL,
            status   TEXT NOT NULL
        );

        CREATE TABLE fees (
            roll_no           TEXT NOT NULL REFERENCES students(roll_no),
            semester          TEXT NOT NULL,
            amount_due        INTEGER NOT NULL,
            amount_paid       INTEGER NOT NULL,
            due_date          TEXT NOT NULL,
            status            TEXT NOT NULL,
            last_payment_ref  TEXT NOT NULL,
            last_payment_date TEXT NOT NULL,
            PRIMARY KEY (roll_no, semester)
        );

        CREATE TABLE hostel (
            roll_no   TEXT PRIMARY KEY REFERENCES students(roll_no),
            block     TEXT NOT NULL,
            room_no   TEXT NOT NULL,
            status    TEXT NOT NULL,
            mess_plan TEXT NOT NULL,
            warden    TEXT NOT NULL
        );

        CREATE TABLE exams (
            roll_no            TEXT NOT NULL REFERENCES students(roll_no),
            semester           TEXT NOT NULL,
            attendance_pct     INTEGER NOT NULL,
            hall_ticket_status TEXT NOT NULL,
            backlogs           INTEGER NOT NULL,
            results_status     TEXT NOT NULL,
            PRIMARY KEY (roll_no, semester)
        );

        CREATE TABLE tickets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no    TEXT NOT NULL,
            message    TEXT NOT NULL,
            department TEXT NOT NULL,
            urgency    TEXT NOT NULL,
            status     TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    cur.executemany("INSERT INTO students VALUES (?,?,?,?,?,?)", STUDENTS)
    cur.executemany("INSERT INTO fees VALUES (?,?,?,?,?,?,?,?)", FEES)
    cur.executemany("INSERT INTO hostel VALUES (?,?,?,?,?,?)", HOSTEL)
    cur.executemany("INSERT INTO exams VALUES (?,?,?,?,?,?)", EXAMS)
    cur.executemany(
        "INSERT INTO tickets (roll_no, message, department, urgency, status) VALUES (?,?,?,?,?)",
        TICKETS,
    )

    # ----------------------------------------------------------------------
    # The policy knowledge base.
    #
    # This is full-text search over ~6 markdown files, NOT a vector database.
    # That's a deliberate choice and worth arguing about in module 2: for a
    # corpus this size, keyword search is faster, has no embedding cost, no
    # extra service to run, and returns results you can explain. Reach for a
    # vector store when you can show keyword search failing, not before.
    # ----------------------------------------------------------------------
    if has_fts5(conn):
        cur.execute(
            "CREATE VIRTUAL TABLE policies USING fts5(doc, section, content, tokenize='porter')"
        )
    else:
        # Rare, but some minimal Python builds lack FTS5. tools.py falls back
        # to LIKE matching against this same table shape.
        cur.execute("CREATE TABLE policies (doc TEXT, section TEXT, content TEXT)")

    doc_count = 0
    section_count = 0
    for md in sorted(KB_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        doc_count += 1
        for heading, body in _split_markdown_sections(text):
            cur.execute(
                "INSERT INTO policies (doc, section, content) VALUES (?,?,?)",
                (md.stem, heading, body),
            )
            section_count += 1

    conn.commit()
    conn.close()

    if not quiet:
        print(f"Built {db_path}")
        print(
            f"  {len(STUDENTS)} students, {len(FEES)} fee records, "
            f"{len(HOSTEL)} hostel records, {len(EXAMS)} exam records"
        )
        print(f"  {section_count} policy sections from {doc_count} documents")

    return db_path


def ensure_db(db_path: Path = DB_PATH) -> Path:
    """Build the database if it isn't there yet. Called by the tools on import."""
    if not db_path.exists():
        build(db_path, quiet=True)
    return db_path


if __name__ == "__main__":
    build()
