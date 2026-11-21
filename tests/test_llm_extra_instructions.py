from core.llm import build_system_prompt


def test_default_is_unchanged():
    # Guards every existing caller/test: default must be byte-identical to today.
    base = build_system_prompt()
    assert base == build_system_prompt(extra_instructions="")
    assert base.startswith("You are an expert patent analyst.")


def test_extra_instructions_appended():
    block = "EXTRA RULE: always quote verbatim."
    out = build_system_prompt(extra_instructions=block)
    assert out.startswith(build_system_prompt())
    assert out.endswith(block)
    assert "\n\n" + block in out
