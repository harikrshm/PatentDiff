from pydantic import BaseModel


class PatentInput(BaseModel):
    label: str
    independent_claim: str
    specification: str


class AnalysisRequest(BaseModel):
    source_patent: PatentInput
    target_patent: PatentInput


class ElementMapping(BaseModel):
    element_number: int
    element_text: str
    corresponding_text: str
    novelty: str
    inventive_step: str
    verdict: str
    comment: str


class AnalysisReport(BaseModel):
    element_mappings: list[ElementMapping]
    overall_opinion: str
