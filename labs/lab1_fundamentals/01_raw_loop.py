"""LAB 1, PART 1 — What an agent actually is.

    make lab1        (or: python labs/lab1_fundamentals/01_raw_loop.py)

No framework. No Agno. Just the Google SDK and a while loop.

Here is the whole idea, and it is smaller than the hype suggests:

    an agent is a loop that calls a language model,
    and when the model asks to run a function, runs it,
    hands back the result, and calls the model again.

That's it. Everything else — memory, teams, workflows, planning — is built on
top of this loop. Once you've seen it written out, frameworks stop being magic
and become what they actually are: a way to avoid writing this every time.

Read the LOOP section at the bottom. It is about twenty lines.

--------------------------------------------------------------------------
A note on the SDK
--------------------------------------------------------------------------
We use `client.models.generate_content` with an explicit list of messages that
we grow ourselves, one turn at a time.

Google's newer Interactions API keeps that history on their servers for you and
you pass a `previous_interaction_id` instead. It is nicer for production and
worse for learning, because the thing we want you to *see* — the conversation
accumulating, the tool results being appended — is exactly the thing it hides.

So: explicit history here, for teaching. Reach for Interactions in real code.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dotenv import load_dotenv  # noqa: E402
from google import genai  # noqa: E402  <- `from google import genai`, NOT `google.generativeai`
from google.genai import types  # noqa: E402

from college_agent.tools import check_fee_status, lookup_student  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = os.getenv("COLLEGE_AGENT_MODEL", "gemini-3.5-flash-lite")
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

TOOL_SCHEMAS = [
    {
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
    {
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
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[types.Tool(function_declarations=TOOL_SCHEMAS)],
        # The SDK will happily run your Python functions for you. We switch that
        # off, because doing it by hand is the entire point of this file.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.1,
    )

    # THE CONVERSATION. This list is the agent's entire memory. Watch it grow.
    contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=question)])]

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n\033[2m── turn {turn} ─ sending {len(contents)} message(s) ──\033[0m")

        response = client.models.generate_content(model=MODEL, contents=contents, config=config)

        parts = response.candidates[0].content.parts or []
        calls = [p.function_call for p in parts if p.function_call]

        # No tool calls means the model is done thinking and has an answer.
        # This is the loop's exit condition.
        if not calls:
            answer = response.text or "(the model returned nothing)"
            print("\033[32m  model is done — no more tools needed\033[0m")
            return answer

        # Keep the model's request in the history, or it won't remember asking.
        contents.append(response.candidates[0].content)

        # Run each requested tool and collect the results.
        result_parts = []
        for call in calls:
            args = dict(call.args or {})
            print(f"\033[33m  model wants:\033[0m {call.name}({json.dumps(args)})")

            fn = TOOL_IMPLEMENTATIONS.get(call.name)
            if fn is None:
                # The model hallucinated a tool that doesn't exist. Tell it so
                # rather than crashing — it can usually recover.
                output = f"ERROR: no such tool {call.name!r}."
            else:
                output = fn(**args)

            print(f"\033[36m  tool says:  \033[0m {output[:110]}{'…' if len(output) > 110 else ''}")
            result_parts.append(
                types.Part.from_function_response(name=call.name, response={"result": output})
            )

        # Hand the results back. Next time round the loop the model sees them.
        contents.append(types.Content(role="user", parts=result_parts))

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
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        print("\nGOOGLE_API_KEY is not set. Run `make preflight` — it'll tell you how.\n")
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
        "Things to notice:\n"
        "  · The model never ran any code. It only ever asked us to.\n"
        "  · The history list IS the memory. Nothing else remembers anything.\n"
        "  · MAX_TURNS is what stands between you and an infinite loop.\n"
        "\n"
        "Try this:\n"
        "  · Change the ticket to a roll number that doesn't exist. Watch it\n"
        "    recover instead of crashing.\n"
        "  · Set MAX_TURNS = 1 and see it give up mid-thought.\n"
        "  · Delete the 'description' from check_fee_status and see how much\n"
        "    worse its tool choice gets. Descriptions are prompts, not comments.\n"
        "\n"
        "Next: 02_first_agent.py — the same thing, in ten lines.\033[0m\n"
    )
