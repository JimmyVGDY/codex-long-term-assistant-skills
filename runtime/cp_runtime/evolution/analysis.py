"""确定性价值/复杂度分析。

分析只依据结构化快照与固定策略，不调用模型，也不产生执行授权。
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import (
    ConfidenceLevel,
    EvolutionPolicy,
    PatternSignal,
    ProposalAction,
    RiskLevel,
    SelfObservationSnapshot,
    SignalType,
    ValueComplexityAssessment,
)

_CONFIDENCE_POINTS = {
    ConfidenceLevel.L0: 0,
    ConfidenceLevel.L1: 4,
    ConfidenceLevel.L2: 10,
    ConfidenceLevel.L3: 18,
    ConfidenceLevel.L4: 25,
}
_BASE_VALUE = {
    SignalType.REPEATED_FAILURE: 35,
    SignalType.MODEL_ESCALATION: 25,
    SignalType.ROUTING_DEVIATION: 30,
    SignalType.EXCESSIVE_REPAIR: 28,
    SignalType.LOW_REVIEWER_YIELD: 20,
    SignalType.NEGATIVE_OUTCOME: 40,
    SignalType.UNUSED_CAPABILITY: 15,
}
_BASE_COMPLEXITY = {
    SignalType.REPEATED_FAILURE: 55,
    SignalType.MODEL_ESCALATION: 35,
    SignalType.ROUTING_DEVIATION: 45,
    SignalType.EXCESSIVE_REPAIR: 50,
    SignalType.LOW_REVIEWER_YIELD: 30,
    SignalType.NEGATIVE_OUTCOME: 65,
    SignalType.UNUSED_CAPABILITY: 40,
}


class AnalysisError(RuntimeError):
    """价值复杂度分析无法安全完成。"""


def _metric(signal: PatternSignal, name: str, default: float = 0.0) -> float:
    value = signal.metrics.get(name, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _risk(signal: PatternSignal, action: ProposalAction) -> RiskLevel:
    if action is ProposalAction.DEPRECATE:
        return RiskLevel.HIGH
    if signal.signal_type in {SignalType.NEGATIVE_OUTCOME, SignalType.REPEATED_FAILURE}:
        return RiskLevel.HIGH if signal.rate >= 0.50 else RiskLevel.MEDIUM
    if signal.signal_type in {SignalType.ROUTING_DEVIATION, SignalType.EXCESSIVE_REPAIR}:
        return RiskLevel.MEDIUM
    if signal.signal_type is SignalType.MODEL_ESCALATION:
        return RiskLevel.MEDIUM if signal.rate >= 0.65 else RiskLevel.LOW
    return RiskLevel.LOW


def _recommended_action(signal: PatternSignal, policy: EvolutionPolicy) -> ProposalAction:
    if signal.signal_type is SignalType.REPEATED_FAILURE:
        return ProposalAction.MODIFY
    if signal.signal_type is SignalType.MODEL_ESCALATION:
        return ProposalAction.MODIFY
    if signal.signal_type is SignalType.ROUTING_DEVIATION:
        return ProposalAction.MODIFY
    if signal.signal_type is SignalType.EXCESSIVE_REPAIR:
        return ProposalAction.MODIFY
    if signal.signal_type is SignalType.NEGATIVE_OUTCOME:
        return ProposalAction.INVESTIGATE
    if signal.signal_type is SignalType.LOW_REVIEWER_YIELD:
        invocations = int(_metric(signal, "invocations", 0))
        findings = int(_metric(signal, "findings", 0))
        window_days = int(_metric(signal, "window_days", 0))
        if (
            invocations >= policy.deprecation_min_invocations
            and findings == 0
            and window_days >= policy.deprecation_min_window_days
            and signal.confidence is ConfidenceLevel.L4
        ):
            return ProposalAction.DEPRECATE
        return ProposalAction.INVESTIGATE
    return ProposalAction.INVESTIGATE


def _scores(signal: PatternSignal) -> Tuple[int, int]:
    value = _BASE_VALUE[signal.signal_type]
    value += min(20, signal.independent_task_count * 2)
    value += min(20, int(round(signal.rate * 20)))
    value += _CONFIDENCE_POINTS[signal.confidence]
    value = max(0, min(100, value))

    complexity = _BASE_COMPLEXITY[signal.signal_type]
    if signal.independent_task_count >= 10:
        complexity += 5
    if signal.rate >= 0.60:
        complexity += 5
    complexity = max(0, min(100, complexity))
    return value, complexity


def _rationale(signal: PatternSignal, action: ProposalAction) -> str:
    if signal.signal_type is SignalType.REPEATED_FAILURE:
        return (
            "%s。重复失败已跨越多个独立任务，继续仅在任务末尾修复会累积返工；"
            "建议定位共同触发条件，并以最小规则或验证补丁降低再次发生概率。" % signal.summary
        )
    if signal.signal_type is SignalType.MODEL_ESCALATION:
        return (
            "%s。推荐模型与实际模型频繁偏离，说明复杂度判断、路由阈值或任务特征提取可能不准确；"
            "应先分析升级原因，再调整路由规则，不能直接提高全部任务默认档位。" % signal.summary
        )
    if signal.signal_type is SignalType.ROUTING_DEVIATION:
        return (
            "%s。路由偏差会造成无关上下文加载、额外 Reviewer 或遗漏关键 Skill；"
            "应通过回放样本修改触发条件并执行正反向路由回归。" % signal.summary
        )
    if signal.signal_type is SignalType.EXCESSIVE_REPAIR:
        return (
            "%s。修复轮次持续偏高通常意味着实施前约束不足、Review Packet 信息不完整或问题归并失效；"
            "应优先修正前置检查和证据包，而不是放宽停止条件。" % signal.summary
        )
    if signal.signal_type is SignalType.LOW_REVIEWER_YIELD:
        if action is ProposalAction.DEPRECATE:
            return (
                "%s。当前证据满足长窗口、足够调用量、零发现和高置信度条件，可形成退役候选；"
                "仍需人工确认该 Reviewer 是否只在少数高风险场景发挥兜底价值。" % signal.summary
            )
        return (
            "%s。低发现率不等同于无价值，可能由任务样本、职责重叠或输入不足导致；"
            "因此只建议调查、缩小默认触发范围或开展对照实验，不直接退役。" % signal.summary
        )
    if signal.signal_type is SignalType.NEGATIVE_OUTCOME:
        return (
            "%s。结果异常可能来自多个异质原因，当前聚合信号不足以直接修改单一规则；"
            "应先按失败分类、Skill、模型和项目阶段分层定位。" % signal.summary
        )
    return "%s。当前只形成调查建议，不足以直接修改运行规则。" % signal.summary


def _constraints(action: ProposalAction) -> Tuple[str, ...]:
    values = [
        "execution_authorization 必须保持为 NONE，提案本身不授予任何修改权限",
        "不得自动修改 Skill、Reviewer、模型档位、AGENTS.md、全局配置或业务仓库",
        "实施前必须重新冻结 Project ID、Task ID、Git 基线和授权范围",
        "修改应保持最小范围，并准备可验证的回滚路径",
        "修改后必须执行目标回归、负向用例和独立读回验证",
    ]
    if action is ProposalAction.DEPRECATE:
        values.append("退役只能先进入观察期；不得直接删除能力或历史记录")
    return tuple(values)


def assess_snapshot(
    snapshot: SelfObservationSnapshot,
    policy: Optional[EvolutionPolicy] = None,
) -> List[ValueComplexityAssessment]:
    policy = policy or EvolutionPolicy()
    snapshot.verify_integrity()
    if snapshot.record_count < policy.min_records or snapshot.task_count < policy.min_independent_tasks:
        return []

    assessments: List[ValueComplexityAssessment] = []
    for signal in snapshot.signals:
        if signal.confidence in {ConfidenceLevel.L0, ConfidenceLevel.L1}:
            continue
        value_score, complexity_score = _scores(signal)
        action = _recommended_action(signal, policy)
        risk = _risk(signal, action)
        assessments.append(ValueComplexityAssessment.create(
            snapshot_id=snapshot.snapshot_id,
            signal=signal,
            value_score=value_score,
            complexity_score=complexity_score,
            risk_level=risk,
            confidence=signal.confidence,
            recommended_action=action,
            rationale=_rationale(signal, action),
            constraints=_constraints(action),
            policy_version=policy.policy_version,
        ))
    return assessments
