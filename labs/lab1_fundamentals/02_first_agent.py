"""LAB 1, PART 2 — The same agent, in ten lines.

    python labs/lab1_fundamentals/02_first_agent.py

You just wrote the loop by hand. Here is the identical behaviour with Agno.

Compare the two files side by side. Everything that vanished — the message
list, the tool-call dispatch, the turn counter, the function-response
plumbing — still happens. Agno is doing exactly what you did in 01_raw_loop.py.
It has not added intelligence; it has removed typing.

That is worth being precise about, because it tells you when a framework is and
isn't worth it. You reach for one when the loop is boilerplate you've already
understood. You avoid one when the loop is the thing you're trying to learn or
change.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from agno.agent import Agent  # noqa: E402

from college_agent.config import describe_config, get_model  # noqa: E402
from college_agent.tools import check_fee_status, lookup_student  # noqa: E402

TICKET = (
    "Hi, I paid my semester fees by NEFT on the 13th but the portal still shows "
    "pending and I'm worried about my hall ticket. My roll number is CS21B014."
)


# ==========================================================================
# The whole thing.
# ==========================================================================

agent = Agent(
    name="Fee Helper",
    # The model. We import it from config.py rather than building it here —
    # see that file for why, it's a genuinely useful pattern.
    model=get_model(),
    # The instructions: who it is and how to decide. Not a description of the
    # college; the model already knows what fees are. What it doesn't know is
    # that you'd rather it looked things up than guessed.
    instructions=[
        "You triage student tickets for a college administration office.",
        "Look up the facts before answering — never guess a roll number, an amount or a date.",
        "Reply with a short summary of what is wrong and which department should handle it.",
    ],
    # The tools. Plain Python functions. Agno reads their type hints and
    # docstrings to build the schemas you wrote out by hand in part 1.
    tools=[lookup_student, check_fee_status],
    # The stopping condition — MAX_TURNS, renamed.
    tool_call_limit=6,
    markdown=True,
)


if __name__ == "__main__":
    import os

    if not os.getenv("GOOGLE_API_KEY", "").strip():
        print("\nGOOGLE_API_KEY is not set. Run `make preflight` — it'll tell you how.\n")
        raise SystemExit(1)

    print(f"\n\033[1mThe same agent, with Agno\033[0m  \033[2m({describe_config()})\033[0m\n")

    # `print_response` runs the loop and streams the result to your terminal.
    agent.print_response(TICKET, stream=True)

    print(
        "\n\033[2m" + "─" * 70 + "\n"
        "Ten lines instead of a hundred. Same loop underneath.\n"
        "\n"
        "Try this:\n"
        "  · Set debug_mode=True on the Agent and run it again. You'll see every\n"
        "    message, every tool call and the token counts. This is the single\n"
        "    most useful debugging tool you have — use it the first time an\n"
        "    agent does something you didn't expect.\n"
        "\n"
        "  · Remove `check_fee_status` from the tools list. The agent now can't\n"
        "    answer the question. Watch what it does instead — does it admit\n"
        "    that, or does it invent something? That behaviour is exactly what\n"
        "    module 3 is about measuring.\n"
        "\n"
        "  · Add a third tool from college_agent.tools — check_exam_status —\n"
        "    and change the ticket to ask about a hall ticket. You never tell\n"
        "    the agent to use it. It works out that it should.\n"
        "\n"
        "Next: lab 2 — make it produce a structured decision instead of prose.\033[0m\n"
    )
