"""
a2a/protocol.py
---------------
Minimal A2A protocol layer for AMIE.

Defines the standard message format that all agents use to
communicate with each other through the Ingestion orchestrator.

A2A Task lifecycle:
  pending → running → complete | error
"""
import uuid
import time
from dataclasses import dataclass, field
from typing import Any


# ── Task Status Constants ─────────────────────────────────────────────────────

class TaskStatus:
    PENDING  = "pending"
    RUNNING  = "running"
    COMPLETE = "complete"
    ERROR    = "error"


# ── Core A2A Data Structures ──────────────────────────────────────────────────

@dataclass
class A2ATask:
    """
    A single unit of work sent from orchestrator to an agent.
    This is what the Ingestion Agent sends to IDCA, NAA, AA.
    """
    agent:      str                        # "idca" | "naa" | "aa"
    input:      dict                       # agent-specific input payload
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

    @classmethod
    def from_dict(cls, data: dict) -> "A2ATask":
        return cls(
            agent      = data["agent"],
            input      = data["input"],
            task_id    = data.get("task_id", str(uuid.uuid4())),
            status     = data.get("status", TaskStatus.PENDING),
            created_at = data.get("created_at", time.time()),
        )


@dataclass
class A2AResponse:
    """
    Standard response returned by every agent after processing a task.
    """
    task_id: str
    agent:   str
    status:  str        # complete | error
    output:  dict       # agent-specific result payload
    error:   str = ""   # populated only if status = error

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent":   self.agent,
            "status":  self.status,
            "output":  self.output,
            "error":   self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "A2AResponse":
        return cls(
            task_id = data.get("task_id", ""),
            agent   = data.get("agent", ""),
            status  = data.get("status", TaskStatus.ERROR),
            output  = data.get("output", {}),
            error   = data.get("error", ""),
        )


@dataclass
class AgentCard:
    """
    Describes an agent's identity and capabilities.
    Exposed at /.well-known/{agent}-agent-card.json
    """
    name:         str
    description:  str
    version:      str
    input_schema: dict
    output_schema: dict

    def to_dict(self) -> dict:
        return {
            "name":          self.name,
            "description":   self.description,
            "version":       self.version,
            "input_schema":  self.input_schema,
            "output_schema": self.output_schema,
        }


# ── Agent Card Definitions ────────────────────────────────────────────────────

IDCA_CARD = AgentCard(
    name        = "IDCA",
    description = "Invention Detection and Classification Agent — determines whether a manuscript discloses a patentable invention",
    version     = "1.0.0",
    input_schema  = {"manuscript_text": "string"},
    output_schema = {
        "sd":                  "Present | Implied | Absent",
        "structural_synopsis": "string",
        "source_citation":     "string",
        "fields_map":          "list[string]",
        "reasoning":           "string",
    },
)

NAA_CARD = AgentCard(
    name        = "NAA",
    description = "Novelty Assessment Agent — builds prior art search queries and scores references against the invention structure",
    version     = "1.0.0",
    input_schema  = {
        "manuscript_text": "string",
        "idca_result":     "object",
    },
    output_schema = {
        "ss":           "list[object]",
        "ss_synopsis":  "string",
        "ucs":          "string",
        "ssr_criteria": "object",
        "references":   "list[object]",
    },
)

AA_CARD = AgentCard(
    name        = "AA",
    description = "Aggregation Agent — compiles IDCA and NAA results into a Final Reference Table and novelty risk report",
    version     = "1.0.0",
    input_schema  = {
        "idca_result": "object",
        "naa_result":  "object | null",
    },
    output_schema = {
        "context_header":       "object",
        "final_reference_table": "list[object]",
        "executive_summary":    "string",
        "novelty_risk":         "High | Medium | Low | Indeterminate",
    },
)

INGESTION_CARD = AgentCard(
    name        = "IngestionAgent",
    description = "Orchestrator — receives manuscript, coordinates IDCA → NAA → AA pipeline via A2A protocol, returns complete novelty assessment",
    version     = "1.0.0",
    input_schema  = {
        "s3_key": "string",
        "bucket": "string",
    },
    output_schema = {
        "task_id": "string",
        "status":  "pending | running | idca_complete | naa_complete | complete | error",
        "idca":    "object",
        "naa":     "object | null",
        "aa":      "object",
    },
)

# Registry — used by handler.py to serve agent cards
AGENT_CARDS = {
    "idca":      IDCA_CARD,
    "naa":       NAA_CARD,
    "aa":        AA_CARD,
    "ingestion": INGESTION_CARD,
}
