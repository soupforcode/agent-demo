"""LAB 1, PART 1 (OpenAI) — What an agent actually is.

    COLLEGE_AGENT_PROVIDER=openai make lab1

This is `01_raw_loop.py` against OpenAI instead of Gemini. Open the two side by
side — that comparison is worth more than either file alone.

What differs: the SDK. `client.chat.completions.create` instead of
`client.models.generate_content`. Tool schemas wrapped in `{"type": "function"}`.
Tool results appended as `{"role": "tool"}` messages rather than
`functionResponse` parts. Arguments arrive as a JSON *string* you have to parse,
where Gemini hands you a dict.

What doesn't differ — and this is the point:

    send the conversation, plus the list of tools
    if the model asked for a tool, run it and append the result
    repeat until it stops asking

**The loop is the invariant. The SDK is incidental.** Every agent framework you
will ever use is a wrapper around those three lines. Once you have seen the same
loop in two different SDKs, no third one can surprise you.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dotenv import load_dotenv  # noqa: E402
from openai import OpenAI  # noqa: E402

from college_agent.tools import check_fee_status, lookup_student  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = os.getenv("COLLEGE_AGENT_MODEL", "gpt-5.4-mini")
MAX_TURNS = 6  # a stopping condition is not optional — see the note at the bottom


# ==========================================================================
# 1. THE TOOLS
#
# A tool is a normal Python function plus a description of how to call it.
# The model never runs your code — it can only *ask* you to, by name, with
# arguments. You are the one who decides whether to actually do it.
#
# That distinction is the whole security model of agents. Hold onto it.
# ==========================================================================

TOOL_IMPLEMENTATIONS = {
    "lookup_student": lookup_student,
    "check_fee_status": check_fee_status,
}

# Same descriptions as the Gemini version, wrapped in OpenAI's envelope. The
# envelope is the only difference; the descriptions are what actually steer the
# model, and they are identical.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_student",
            "description": (
                "Look up a student's record by roll number. Call this first whenever "
                "a roll number is mentioned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "roll_no": {
                        "type": "string",
                        "description": "The roll number, for example 'CS21B001'.",
                    }
                },
                "required": ["roll_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_fee_status",
            "description": (
                "Check what a student owes, what they have paid, and whether they are "
                "fee-blocked. Use this for anything about money, and also when a "
                "student cannot get a hall ticket or transcript."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "roll_no": {
                        "type": "string",
                        "description": "The roll number, for example 'CS21B001'.",
                    }
                },
                "required": ["roll_no"],
            },
        },
    },
]

SYSTEM_INSTRUCTION = (
    "You triage student tickets for a college administration office. "
    "Look up the facts before answering — never guess a roll number, an amount "
    "or a date. When you have enough information, reply with a short plain-text "
    "summary of what is wrong and which department should handle it."
)


# ==========================================================================
# 2. THE LOOP
# ==========================================================================


def run_agent(question: str) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # THE CONVERSATION. This list is the agent's entire memory. Watch it grow.
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": question},
    ]

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n\033[2m── turn {turn} ─ sending {len(messages)} message(s) ──\033[0m")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.1,
        )

        reply = response.choices[0].message
        calls = reply.tool_calls or []

        # No tool calls means the model is done thinking and has an answer.
        # This is the loop's exit condition.
        if not calls:
            print("\033[32m  model is done — no more tools needed\033[0m")
            return reply.content or "(the model returned nothing)"

        # Keep the model's request in the history, or it won't remember asking.
        messages.append(reply.model_dump(exclude_none=True))

        # Run each requested tool and append the result.
        for call in calls:
            # Note: OpenAI hands you arguments as a JSON *string*, so you parse
            # it yourself. Gemini gives you a dict. A small difference that has
            # confused a great many people.
            args = json.loads(call.function.arguments or "{}")
            print(f"\033[33m  model wants:\033[0m {call.function.name}({json.dumps(args)})")

            fn = TOOL_IMPLEMENTATIONS.get(call.function.name)
            if fn is None:
                # The model hallucinated a tool that doesn't exist. Tell it so
                # rather than crashing — it can usually recover.
                output = f"ERROR: no such tool {call.function.name!r}."
            else:
                output = fn(**args)

            print(f"\033[36m  tool says:  \033[0m {output[:110]}{'…' if len(output) > 110 else ''}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

    return (
        f"Stopped after {MAX_TURNS} turns without a final answer.\n"
        "That limit is a feature. Without it, a confused agent loops until your "
        "quota is gone."
    )


# ==========================================================================
# 3. TRY IT
# ==========================================================================

TICKET = (
    "Hi, I paid my semester fees by NEFT on the 13th but the portal still shows "
    "pending and I'm worried about my hall ticket. My roll number is CS21B014."
)

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY", "").strip():
        print("\nOPENAI_API_KEY is not set. Run `make preflight` — it'll tell you how.\n")
        raise SystemExit(1)

    print(f"\n\033[1mThe agent loop, by hand\033[0m  \033[2m({MODEL})\033[0m")
    print(f"\n\033[1mTicket:\033[0m {TICKET}")

    answer = run_agent(TICKET)

    print(f"\n\033[1mAnswer:\033[0m\n{answer}\n")

    print("\033[2m" + "─" * 70)
    print(
        "What just happened:\n"
        "  1. We sent the ticket plus a list of tools the model may ask for.\n"
        "  2. It asked for one. We ran it and appended the result.\n"
        "  3. We called it again, now with the result in the history.\n"
        "  4. Repeat until it stops asking for tools.\n"
        "\n"
        "That's an agent. About twenty lines.\n"
        "\n"
        "Now open 01_raw_loop.py — the Gemini version — beside this one.\n"
        "The SDK calls differ. The loop is character-for-character the same\n"
        "idea. That is the whole lesson: frameworks and SDKs come and go, the\n"
        "loop doesn't.\n"
        "\n"
        "Things to notice:\n"
        "  · The model never ran any code. It only ever asked us to.\n"
        "  · The messages list IS the memory. Nothing else remembers anything.\n"
        "  · MAX_TURNS is what stands between you and an infinite loop.\n"
        "\n"
        "Next: 02_first_agent.py — the same thing, in ten lines.\033[0m\n"
    )
