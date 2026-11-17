from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: Literal["news", "social", "other"]
    title: str
    url: HttpUrl
    publisher: str | None = None
    published_at: str | None = None


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str
    assessment: Literal[
        "supported",
        "contradicted",
        "mixed",
        "insufficient_evidence",
    ]
    supporting_evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class EvaluationMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")
    groundedness: float = Field(ge=0, le=1)
    citation_validity: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    comparison_quality: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: str
    source_urls: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    model_identifiers: list[str] = Field(default_factory=list)
    trace_id: str


class InvestigationWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: str
    end: str
    days: int = Field(ge=1, le=365)
    interval: Literal["hour", "day"]


class DuplicateSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    published_at: str | None = None
    retrieved_at: str
    publisher: str | None = None


class InvestigationSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: Literal["news", "social"]
    platform: str
    title: str
    content: str
    url: HttpUrl
    published_at: str | None = None
    retrieved_at: str
    window_status: Literal["in_window", "outside_window", "timestamp_unavailable"]
    author: str | None = None
    publisher: str | None = None
    cluster_id: str
    duplicate_sources: list[DuplicateSource] = Field(default_factory=list)


class RumourCluster(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    record_ids: list[str]
    record_count: int = Field(ge=1)


class EarliestSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Literal["Earliest source found"]
    category: Literal["news", "social"]
    platform: str
    content: str
    published_at: str
    url: HttpUrl
    confidence_note: str


class SpreadPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: str
    social_media: int = Field(ge=0)
    news_media: int = Field(ge=0)


class SpreadStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeline: list[SpreadPoint]
    unique_records: dict[str, int]
    total_unique_records: int = Field(ge=0)
    activity_change: Literal["increasing", "decreasing", "stable"]
    record_count_outside_window: int = Field(ge=0)
    records_missing_publication_time: int = Field(ge=0)
    duplicate_records_removed: int = Field(ge=0)


class DataCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records_collected: int = Field(ge=0)
    timestamped_records_in_window: int = Field(ge=0)
    timestamp_coverage: float = Field(ge=0, le=1)
    source_errors: list[dict[str, str]] = Field(default_factory=list)


class RumourInvestigationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window: InvestigationWindow
    verification_status: Literal[
        "Supported",
        "Partially supported",
        "Contradicted",
        "Unverified",
        "Insufficient evidence",
    ] = "Insufficient evidence"
    verification_summary: str = ""
    claim_assessments: list[ClaimAssessment] = Field(default_factory=list)
    human_review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    source_records: list[InvestigationSourceRecord] = Field(default_factory=list)
    rumour_clusters: list[RumourCluster] = Field(default_factory=list)
    earliest_source: EarliestSource | None = None
    spread: SpreadStatistics
    data_coverage: DataCoverage


class SocialVerifyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: str
    query: str
    summary: str
    claim_assessments: list[ClaimAssessment] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    evaluation_metrics: EvaluationMetric
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    investigation_data: RumourInvestigationData | None = None
    verification_status: Literal[
        "Supported",
        "Partially supported",
        "Contradicted",
        "Unverified",
        "Insufficient evidence",
    ] = "Insufficient evidence"
    markdown_report: str
    human_review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    status: Literal["completed", "partial", "failed"] = "completed"
