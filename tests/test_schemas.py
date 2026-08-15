"""Guards on the output schema.

These look pedantic. They are not.

Gemini rejects large or deeply nested response schemas, and the error it
returns is unhelpful enough that you can lose an afternoon to it. Agno also has
a known bug where an `Optional[X] = None` field can end up marked *required*,
which fails intermittently — the worst kind of failure, because it passes in
testing and breaks in front of a room.

So `TriageResult` is deliberately flat and deliberately free of Optionals, and
these tests fail loudly the moment someone "tidies it up" by extracting a
nested model. That someone will be you, in three weeks, with good intentions.
"""

from __future__ import annotations

import pytest

from college_agent.schemas import TriageRequest, TriageResult


class TestSchemaShape:
    def test_schema_is_flat(self):
        """No $defs means no nested models — which is what Gemini wants."""
        schema = TriageResult.model_json_schema()
        assert "$defs" not in schema, (
            "TriageResult has grown a nested model. Gemini rejects deeply nested "
            "schemas with an unhelpful error. Keep every field primitive.\n"
            "Tip: use Literal[...] rather than an Enum class — Literal inlines, "
            "Enum creates a $def."
        )

    def test_all_fields_are_primitive(self):
        schema = TriageResult.model_json_schema()
        allowed = {"string", "boolean", "integer", "number"}
        for name, prop in schema["properties"].items():
            # Literal fields carry an enum plus a type, both fine.
            kind = prop.get("type")
            assert kind in allowed, f"Field {name!r} has non-primitive type {kind!r}."

    def test_no_optional_fields(self):
        """Every field required, because Agno's schema sanitiser mishandles Optional."""
        schema = TriageResult.model_json_schema()
        assert set(schema["required"]) == set(schema["properties"]), (
            "Every TriageResult field must be required. Optional fields hit a "
            "known Agno bug where they get marked required anyway, producing "
            "intermittent failures. Use a required field with an empty-string "
            "sentinel instead."
        )

    def test_every_field_is_described(self):
        """Field descriptions are prompt text, not documentation.

        The model reads them to decide what to put in each field. An undescribed
        field is an unprompted one.
        """
        schema = TriageResult.model_json_schema()
        for name, prop in schema["properties"].items():
            assert prop.get("description"), f"Field {name!r} has no description for the model."

    def test_schema_stays_small(self):
        """A ceiling, so nobody grows this into something Gemini refuses."""
        schema = TriageResult.model_json_schema()
        assert len(schema["properties"]) <= 12, (
            "TriageResult is getting large. Gemini's tolerance for big schemas "
            "is limited and its error messages are poor. Split the use case "
            "before you split the schema."
        )


class TestSchemaSurvivesAgnoConversion:
    def test_agno_accepts_the_schema(self):
        """Run it through the exact conversion Agno does before calling Gemini."""
        from agno.models.google.gemini import prepare_response_schema

        assert prepare_response_schema(TriageResult) is not None

    def test_schema_token_cost_is_reasonable(self):
        """The schema is sent on every single call, so its size is a running cost."""
        from agno.models.google.gemini import count_schema_tokens, prepare_response_schema

        tokens = count_schema_tokens(prepare_response_schema(TriageResult))
        assert tokens < 1500, f"Schema costs {tokens} tokens on every call — too fat."


class TestValidation:
    def test_rejects_an_invented_department(self):
        with pytest.raises(ValueError):
            TriageResult(
                department="marketing",  # not a real desk
                urgency="normal",
                summary="x",
                student_id="",
                suggested_action="x",
                needs_human=False,
                reasoning="x",
            )

    def test_rejects_an_invented_urgency(self):
        with pytest.raises(ValueError):
            TriageResult(
                department="accounts",
                urgency="extremely urgent",
                summary="x",
                student_id="",
                suggested_action="x",
                needs_human=False,
                reasoning="x",
            )

    def test_accepts_a_well_formed_result(self):
        result = TriageResult(
            department="accounts",
            urgency="high",
            summary="Fee block preventing hall ticket download.",
            student_id="CS22B007",
            suggested_action="Clear the outstanding balance to release the hall ticket.",
            needs_human=False,
            reasoning="Fee record shows status blocked.",
        )
        assert result.department == "accounts"


class TestRequest:
    def test_rejects_an_empty_message(self):
        with pytest.raises(ValueError):
            TriageRequest(message="")

    def test_rejects_an_enormous_message(self):
        # A length cap at the edge is free. Discovering the limit by sending
        # 400kB to a metered API is not.
        with pytest.raises(ValueError):
            TriageRequest(message="x" * 5000)

    def test_student_id_is_optional(self):
        assert TriageRequest(message="help").student_id == ""
