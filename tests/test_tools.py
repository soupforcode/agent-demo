"""The tools are plain Python, so they get plain Python tests.

This is the layer worth testing hardest. A tool that returns wrong data makes
even a perfectly reasoning agent wrong, and unlike the agent, a tool is
deterministic — so there is no excuse for not pinning its behaviour exactly.

Notice how much of this file is about *failure* cases. Tools spend most of
their production life being called with arguments the model made up.
"""

from __future__ import annotations

import pytest

from college_agent.tools import (
    check_exam_status,
    check_fee_status,
    check_hostel_status,
    create_ticket,
    lookup_student,
    search_policy,
)


class TestLookupStudent:
    def test_finds_a_real_student(self):
        assert "Priya Nair" in lookup_student("CS22B007")

    def test_is_case_insensitive(self):
        # The model will not reliably uppercase roll numbers, so the tool must.
        assert lookup_student("cs22b007") == lookup_student("CS22B007")

    def test_tolerates_whitespace(self):
        assert "Priya Nair" in lookup_student("  CS22B007 ")

    def test_unknown_roll_number_explains_rather_than_raising(self):
        # If a tool raises, the agent loop breaks. If it explains, the agent
        # can recover. Always explain.
        result = lookup_student("ZZ99Z999")
        assert "No student found" in result
        assert "Do not guess" in result


class TestFeeStatus:
    def test_reports_a_clear_balance(self):
        result = check_fee_status("CS21B001")
        assert "paid" in result
        assert "Rs.0" in result

    def test_flags_a_fee_block(self):
        # CS22B007 is the fee-blocked student the whole workshop hinges on.
        result = check_fee_status("CS22B007")
        assert "FEE-BLOCKED" in result
        assert "withheld" in result

    def test_explains_the_neft_reconciliation_window(self):
        # Without this hint the agent escalates a non-problem, wasting a
        # human's time on a payment that is simply still settling.
        result = check_fee_status("CS21B014")
        assert "2-3 working days" in result
        assert "NEFT5520933" in result

    def test_reports_a_partial_payment(self):
        result = check_fee_status("CS23B044")
        assert "overdue" in result
        assert "Rs.45,000" in result  # 85,000 due - 40,000 paid

    def test_unknown_student(self):
        assert "No fee record" in check_fee_status("ZZ99Z999")


class TestExamStatus:
    def test_distinguishes_a_fee_block_from_an_attendance_block(self):
        # These two produce the same symptom for the student and require
        # completely different routing. Getting this wrong is the single most
        # common triage error, so the tool must be explicit about which it is.
        fees = check_exam_status("CS22B007")
        assert "UNPAID FEES" in fees
        assert "accounts problem" in fees

        attendance = check_exam_status("EC21B009")
        assert "68%" in attendance
        assert "below the required 75%" in attendance
        assert "Fees are not the cause" in attendance

    def test_released_hall_ticket_has_no_warning(self):
        result = check_exam_status("CS21B001")
        assert "released" in result
        assert "withheld" not in result


class TestHostelStatus:
    def test_reports_an_allotted_room(self):
        result = check_hostel_status("CS21B001")
        assert "A-214" in result
        assert "Dr. Suresh Pillai" in result

    def test_refuses_to_disclose_waiting_list_position(self):
        # The policy forbids it. The tool has to carry that rule, because a
        # model asked directly for a number will try to be helpful.
        result = check_hostel_status("EC22B031")
        assert "waiting list" in result
        assert "NOT disclosed" in result

    def test_day_scholar_has_no_allotment(self):
        assert "day scholar" in check_hostel_status("CS23B044")


class TestSearchPolicy:
    def test_finds_the_revaluation_window(self):
        assert "fifteen days" in search_policy("re-evaluation deadline")

    def test_finds_the_bonafide_turnaround(self):
        assert "two working days" in search_policy("bonafide certificate")

    def test_returns_the_source_document(self):
        # Citations aren't decoration — an agent that can name its source can
        # be checked, and one that can't, can't.
        assert "[" in search_policy("hostel allotment")

    @pytest.mark.parametrize("query", ["", "   "])
    def test_rejects_an_empty_query(self, query):
        assert "Empty search" in search_policy(query)

    def test_survives_punctuation(self):
        # FTS5 treats several characters as query syntax. A model writing a
        # natural question must not be able to crash the tool.
        for query in ['fees "quoted"', "what's the refund policy?", "fee* AND (hostel"]:
            assert isinstance(search_policy(query), str)

    def test_no_match_suggests_what_to_do(self):
        result = search_policy("quantum chromodynamics")
        assert "No policy section matched" in result


class TestCreateTicket:
    def test_files_a_valid_ticket(self):
        result = create_ticket("CS21B001", "Test ticket", "accounts", "normal")
        assert "filed with accounts" in result
        assert "#" in result

    def test_rejects_an_invented_department(self):
        # The model will occasionally invent a plausible department. Validate
        # rather than trust — an unvalidated write puts tickets in a queue
        # nobody reads.
        result = create_ticket("CS21B001", "x", "marketing", "normal")
        assert "Rejected" in result
        assert "accounts" in result  # tells it what's valid

    def test_rejects_an_invalid_urgency(self):
        result = create_ticket("CS21B001", "x", "accounts", "extremely urgent")
        assert "Rejected" in result

    def test_accepts_unknown_student(self):
        # Better to file it with UNKNOWN than to lose the ticket entirely.
        assert "UNKNOWN" in create_ticket("", "x", "accounts", "low")
