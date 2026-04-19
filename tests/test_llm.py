from core.llm import build_system_prompt, build_user_prompt
from core.models import PatentInput


def test_build_system_prompt_contains_role():
    prompt = build_system_prompt()
    assert "patent" in prompt.lower()
    assert "novelty" in prompt.lower()
    assert "inventive step" in prompt.lower()


def test_build_system_prompt_contains_json_schema():
    prompt = build_system_prompt()
    assert "element_mappings" in prompt
    assert "overall_opinion" in prompt
    assert "element_number" in prompt
    assert "verdict" in prompt


def test_build_system_prompt_contains_weighting_guidance():
    prompt = build_system_prompt()
    assert "technical advancement" in prompt.lower() or "technical improvement" in prompt.lower()


def test_build_user_prompt_returns_tuple():
    source = PatentInput(
        label="Patent A",
        independent_claim="A method comprising step X.",
        specification="Step X does something.",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="A method comprising step Y.",
        specification="Step Y does something else.",
    )
    result = build_user_prompt(source, target)
    assert isinstance(result, tuple)
    assert len(result) == 2
    prompt, warnings = result
    assert isinstance(prompt, str)
    assert isinstance(warnings, list)


def test_build_user_prompt_contains_both_patents():
    source = PatentInput(
        label="US-PATENT-A",
        independent_claim="A method comprising step X.",
        specification="Step X does something.",
    )
    target = PatentInput(
        label="US-PATENT-B",
        independent_claim="A method comprising step Y.",
        specification="Step Y does something else.",
    )
    prompt, warnings = build_user_prompt(source, target)
    assert "US-PATENT-A" in prompt
    assert "US-PATENT-B" in prompt
    assert "A method comprising step X." in prompt
    assert "A method comprising step Y." in prompt


def test_build_user_prompt_labels_source_and_target():
    source = PatentInput(
        label="Patent A",
        independent_claim="claim A",
        specification="spec A",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="claim B",
        specification="spec B",
    )
    prompt, warnings = build_user_prompt(source, target)
    source_idx = prompt.lower().index("source")
    target_idx = prompt.lower().index("target")
    assert source_idx < target_idx
    assert prompt.index("claim A") < prompt.index("claim B")
    assert prompt.index("spec A") < prompt.index("spec B")


def test_build_user_prompt_no_warnings_for_short_specs():
    source = PatentInput(
        label="Patent A",
        independent_claim="A method comprising step X.",
        specification="Step X does something useful.",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="A method comprising step Y.",
        specification="Step Y does something else.",
    )
    _, warnings = build_user_prompt(source, target)
    assert warnings == []


def test_build_user_prompt_warns_when_specs_truncated():
    long_spec = ("The system performs computation on data inputs. " * 1000)
    source = PatentInput(
        label="Patent A",
        independent_claim="A method comprising step X.",
        specification=long_spec,
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="A method comprising step Y.",
        specification=long_spec,
    )
    _, warnings = build_user_prompt(source, target)
    assert len(warnings) > 0
    assert any("truncated" in w.lower() for w in warnings)
