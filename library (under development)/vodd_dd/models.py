"""
vODD-DD Protocol — Data Models
Dataclasses for all protocol sections.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Literal


# ── Enums / Literals ──────────────────────────────────────────────────────────

DataFrequency = Literal["STATIC", "DYNAMIC"]


# ── Data Inputs ───────────────────────────────────────────────────────────────

@dataclass
class Dataset:
    name: str
    description: str
    how_used: str
    frequency: DataFrequency = "STATIC"


@dataclass
class DataPipeline:
    collection: List[str] = field(default_factory=list)   # e.g. ["GPS API", "Census download"]
    preprocessing: List[str] = field(default_factory=list) # e.g. ["Multiple imputation", "QC checks"]
    analysis: List[str] = field(default_factory=list)      # e.g. ["Statistical estimation"]


# ── ABM Core ──────────────────────────────────────────────────────────────────

@dataclass
class Submodel:
    name: str
    description: str


@dataclass
class Agents:
    n_expression: str                          # e.g. "N=10,000"
    types: List[str] = field(default_factory=list)
    state_variables: List[str] = field(default_factory=list)
    data_source: Optional[str] = None
    submodels: List[Submodel] = field(default_factory=list)


@dataclass
class Interactions:
    agent_agent: List[str] = field(default_factory=list)
    agent_environment: List[str] = field(default_factory=list)
    topology: List[str] = field(default_factory=list)
    data_source: Optional[str] = None   # dataset(s) that parameterise interaction rules


@dataclass
class Environment:
    grid: str = ""
    resolution: str = ""
    layers: List[str] = field(default_factory=list)
    data_source: Optional[str] = None   # dataset(s) that parameterise the environment


@dataclass
class ABMCore:
    model_name: str
    agents: Agents
    interactions: Interactions
    environment: Environment
    temporal_unit: str = "1 day"
    duration: str = ""
    stop_condition: str = ""


# ── Observations ──────────────────────────────────────────────────────────────

@dataclass
class OutputPattern:
    name: str
    what_measured: str
    pattern_type: str
    emergent: Optional[str] = None
    has_chart: bool = False       # placeholder for chart area


# ── Model Evaluation ──────────────────────────────────────────────────────────

@dataclass
class Calibration:
    method: str
    target_params: List[str] = field(default_factory=list)
    data_source: str = ""
    result: str = ""


@dataclass
class Validation:
    approaches: List[str] = field(default_factory=list)
    result: str = ""


@dataclass
class ModelEvaluation:
    calibration: Calibration
    validation: Validation


# ── Scenarios ─────────────────────────────────────────────────────────────────

@dataclass
class Scenario:
    name: str
    description: str
    highlighted: bool = False     # draws dark border


# ── Top-level Protocol ────────────────────────────────────────────────────────

@dataclass
class VODDProtocol:
    purpose: str
    datasets: List[Dataset]
    pipeline: DataPipeline
    abm_core: ABMCore
    output_patterns: List[OutputPattern]
    evaluation: ModelEvaluation
    scenarios: List[Scenario]
