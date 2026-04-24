"""
a2a/protocol.py
Minimal A2A protocol layer for AMIE.
"""
import uuid
import time
from dataclasses import dataclass, field


class TaskStatus:
    PENDING  = "pending"
    RUNNING  = "running"
    COMPLETE = "complete"
    ERROR    = "error"


@dataclass
class A2ATask:
    agent:      str
    input:      dict
    task_id:    str   = field(default_factory=lambda: str(uuid.uuid4()))
    status:     str   = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "task_id":    self.task_id,
            "agent":      self.agent,
            "input":      self.input,
            "status":     self.status,
            "created_at": self.created_at,
        }


@dataclass
class A2AResponse:
    task_id: str
    agent:   str
    status:  str
    output:  dict
    error:   str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent":   self.agent,
            "status":  self.status,
            "output":  self.output,
            "error":   self.error,
        }


@dataclass
class AgentCard:
    name:          str
    description:   str
    version:       str
    input_schema:  dict
    output_schema: dict

    def to_dict(self) -> dict:
        return {
            "name":          self.name,
            "description":   self.description,
            "version":       self.version,
            "input_schema":  self.input_schema,
            "output_schema": self.output_schema,
        }


IDCA_CARD = AgentCard(
    name        = "IDCA",
    description = "Invention Detection and Classification Agent",
    version     = "1.0.0",
    input_schema  = {"manuscript_text": "string"},
    output_schema = {
        "sd": "Present | Implied | Absent",
        "structural_synopsis": "string",
        "source_citation": "string",
        "fields_map": "list[string]",
        "reasoning": "string",
    },
)

NAA_CARD = AgentCard(
    name        = "NAA",
    description = "Novelty Assessment Agent",
    version     = "1.0.0",
    input_schema  = {"manuscript_text": "string", "idca_result": "object"},
    output_schema = {
        "ss": "list[object]",
        "ss_synopsis": "string",
        "ucs": "string",
        "ssr_criteria": "object",
        "references": "list[object]",
    },
)

AA_CARD = AgentCard(
    name        = "AA",
    description = "Aggregation Agent",
    version     = "1.0.0",
    input_schema  = {"idca_result": "object", "naa_result": "object | null"},
    output_schema = {
        "context_header": "object",
        "final_reference_table": "list[object]",
        "executive_summary": "string",
        "novelty_risk": "High | Medium | Low | Indeterminate",
    },
)

INGESTION_CARD = AgentCard(
    name        = "IngestionAgent",
    description = "Orchestrator — coordinates IDCA → NAA → AA pipeline via A2A protocol",
    version     = "1.0.0",
    input_schema  = {"s3_key": "string", "bucket": "string"},
    output_schema = {
        "task_id": "string",
        "status":  "pending | running | idca_complete | naa_complete | complete | error",
        "idca":    "object",
        "naa":     "object | null",
        "aa":      "object",
    },
)

AGENT_CARDS = {
    "idca":      IDCA_CARD,
    "naa":       NAA_CARD,
    "aa":        AA_CARD,
    "ingestion": INGESTION_CARD,
}
