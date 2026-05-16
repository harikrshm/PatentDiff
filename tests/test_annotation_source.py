from core.annotation import AnnotationRecord


def test_source_defaults_to_human():
    record = AnnotationRecord(
        run_id="abc",
        phase=3,
        verdict="PASS",
        comment="x",
    )
    assert record.source == "human"


def test_source_can_be_set_to_coded():
    record = AnnotationRecord(
        run_id="abc",
        phase=3,
        verdict="FAIL",
        comment="[code] ...",
        source="coded",
    )
    assert record.source == "coded"


def test_to_dict_includes_source():
    record = AnnotationRecord(
        run_id="abc",
        phase=3,
        verdict="PASS",
        comment="x",
        source="coded",
    )
    assert record.to_dict()["source"] == "coded"


def test_from_dict_defaults_source_when_missing():
    # Legacy on-disk shape: no `source` key in JSON.
    record = AnnotationRecord.from_dict({
        "run_id": "abc",
        "phase": 3,
        "verdict": "PASS",
        "comment": "x",
    })
    assert record.source == "human"


def test_from_dict_preserves_source_when_present():
    record = AnnotationRecord.from_dict({
        "run_id": "abc",
        "phase": 3,
        "verdict": "FAIL",
        "comment": "[code] ...",
        "source": "coded",
    })
    assert record.source == "coded"
