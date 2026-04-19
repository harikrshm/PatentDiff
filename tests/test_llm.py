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
    prompt = build_user_prompt(source, target)
    assert "US-PATENT-A" in prompt
    assert "US-PATENT-B" in prompt
    assert "A method comprising step X." in prompt
    assert "A method comprising step Y." in prompt
    assert "Step X does something." in prompt
    assert "Step Y does something else." in prompt


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
    prompt = build_user_prompt(source, target)
    # Should clearly label which is source and which is target
    assert "source" in prompt.lower() or "patent a" in prompt.lower()
    assert "target" in prompt.lower() or "patent b" in prompt.lower()
