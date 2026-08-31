"""中文：V5.0 Runtime 共享的不可变契约。

English: Immutable contracts shared by the V5.0 runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class ComplexityLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class ProjectStage(str, Enum):
    UNPROFILED = "UNPROFILED"
    ONBOARDING = "ONBOARDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class ExecutionProfile(str, Enum):
    LIGHT = "LIGHT"
    STANDARD = "STANDARD"
    STRICT = "STRICT"


class ReviewerBudget(str, Enum):
    ECONOMY = "economy"
    BALANCED = "balanced"
    DEEP = "deep"


class ModelProfile(str, Enum):
    LUNA_LOW = "luna-low"
    LUNA_MEDIUM = "luna-medium"
    TERRA_MEDIUM = "terra-medium"
    TERRA_HIGH = "terra-high"


class HostSurface(str, Enum):
    MAIN_SESSION = "main-session"
    SUBAGENT = "subagent"
    DIRECT_WORKSPACE = "direct-workspace"
    WORKTREE = "worktree"
    MCP = "mcp"
    LONG_RUNNING = "long-running-task"


class Environment(str, Enum):
    LOCAL = "local"
    NONPRODUCTION = "nonproduction"
    PRODUCTION = "production"


class EvidenceFreshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    NOT_CAPTURED = "NOT_CAPTURED"


@dataclass(frozen=True)
class ProjectBinding:
    project_id: str
    repo_path: Path
    profile_path: Path
    state_path: Path
    profile_sha256: str


@dataclass(frozen=True)
class ApprovalCheckResult:
    valid: bool
    reasons: Tuple[str, ...]
    approval_id: str
    operation: str
    environment: str
    consumed: bool


@dataclass(frozen=True)
class EvidenceCheckResult:
    valid: bool
    freshness: EvidenceFreshness
    reasons: Tuple[str, ...]
    evidence_id: str


@dataclass(frozen=True)
class FinalizationSurface:
    name: str
    supported: bool
    status: str
    evidence: Optional[str] = None
