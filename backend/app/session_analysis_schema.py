"""Provenance for explicitly supplied visual observations, never inferred from events."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisualProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["own_replay", "webvisor", "manual_capture"]
    method: Literal["manual_view", "multimodal_frames", "multimodal_video"]
    replay_id: str = Field(min_length=1, max_length=120)
    replay_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_ref: str = Field(min_length=1, max_length=500)
    captured_at: datetime
    model_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def model_provenance(self):
        if self.method.startswith("multimodal") and not self.model_id:
            raise ValueError("Multimodal observations require model_id")
        return self


class VisualObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    original_time_ms: int = Field(ge=0)
    frame_id: str = Field(min_length=1, max_length=120)
    page: str = Field(min_length=1, max_length=500)
    kind: Literal["rendered_state", "pointer_marker", "state_change", "resource_missing"]
    description: str = Field(min_length=1, max_length=1500)
    provenance: VisualProvenance


class ViewedInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Viewed interval must have positive duration")
        return self


class VisualReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["partial", "reviewed"] = "partial"
    original_duration_ms: int = Field(gt=0, le=86_400_000)
    viewed_intervals: list[ViewedInterval] = Field(default_factory=list, max_length=1000)
    observations: list[VisualObservation] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_coverage(self):
        ids = [o.observation_id for o in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate observation IDs")
        if any(o.original_time_ms > self.original_duration_ms for o in self.observations):
            raise ValueError("Observation lies outside original replay")
        if any(i.end_ms > self.original_duration_ms for i in self.viewed_intervals):
            raise ValueError("Viewed interval lies outside original replay")
        if len({o.provenance.replay_fingerprint for o in self.observations}) != 1:
            raise ValueError("A review must refer to one replay version")
        if self.status == "reviewed":
            if any(o.provenance.method == "multimodal_frames" for o in self.observations):
                raise ValueError("Isolated frames do not establish continuous visual coverage")
            end = 0
            for interval in sorted(self.viewed_intervals, key=lambda i: i.start_ms):
                if interval.start_ms > end:
                    raise ValueError("Complete review has unviewed gaps")
                end = max(end, interval.end_ms)
            if end != self.original_duration_ms:
                raise ValueError("Complete review must cover the original replay")
        return self


class AnalysisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1200)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)


class AnalysisRecommendation(AnalysisFinding):
    verification: str = Field(min_length=1, max_length=1000)


class NarrativeFindings(BaseModel):
    """Optional LLM output; factual and coverage fields remain owned by code."""
    model_config = ConfigDict(extra="forbid")
    inferences: list[AnalysisFinding] = Field(default_factory=list, max_length=10)
    recommendations: list[AnalysisRecommendation] = Field(default_factory=list, max_length=10)
