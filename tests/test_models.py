from core.models import PatentInput, AnalysisRequest, ElementMapping, AnalysisReport


def test_patent_input_creation():
    p = PatentInput(
        label="US10,123,456",
        independent_claim="A system comprising: a processor; and a memory.",
        specification="The processor executes instructions stored in memory.",
    )
    assert p.label == "US10,123,456"
    assert "processor" in p.independent_claim
    assert "processor" in p.specification


def test_analysis_request_creation():
    source = PatentInput(
        label="Patent A",
        independent_claim="A method comprising step X.",
        specification="Step X involves computing a hash.",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="A method comprising step Y.",
        specification="Step Y involves computing a checksum.",
    )
    req = AnalysisRequest(source_patent=source, target_patent=target)
    assert req.source_patent.label == "Patent A"
    assert req.target_patent.label == "Patent B"


def test_element_mapping_creation():
    em = ElementMapping(
        element_number=1,
        element_text="at least one computer processor",
        corresponding_text="a processing unit configured to execute instructions",
        novelty="Y",
        inventive_step="Y",
        verdict="Y",
        comment="Patent B discloses a processing unit that is functionally equivalent.",
    )
    assert em.element_number == 1
    assert em.novelty == "Y"
    assert em.verdict == "Y"


def test_element_mapping_verdict_novel():
    em = ElementMapping(
        element_number=2,
        element_text="a quantum entanglement module",
        corresponding_text="",
        novelty="N",
        inventive_step="N",
        verdict="N",
        comment="No corresponding disclosure found in Patent B.",
    )
    assert em.verdict == "N"
    assert em.corresponding_text == ""


def test_analysis_report_creation():
    mappings = [
        ElementMapping(
            element_number=1,
            element_text="a processor",
            corresponding_text="a CPU",
            novelty="Y",
            inventive_step="Y",
            verdict="Y",
            comment="Equivalent.",
        ),
        ElementMapping(
            element_number=2,
            element_text="a novel module",
            corresponding_text="",
            novelty="N",
            inventive_step="N",
            verdict="N",
            comment="Not found.",
        ),
    ]
    report = AnalysisReport(
        element_mappings=mappings,
        overall_opinion="Patent A's claim 1 contains a novel element (element 2) not disclosed in Patent B.",
    )
    assert len(report.element_mappings) == 2
    assert report.overall_opinion.startswith("Patent A")
