"""根据确定性评估生成只读优化提案。"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import (
    ConfidenceLevel,
    OptimizationProposal,
    PatternSignal,
    ProposalAction,
    SelfObservationSnapshot,
    SignalType,
    ValueComplexityAssessment,
)


class ProposalGenerationError(RuntimeError):
    pass


def _recommendation(signal: PatternSignal, assessment: ValueComplexityAssessment) -> str:
    if signal.signal_type is SignalType.REPEATED_FAILURE:
        return (
            "对该失败模式关联的任务样本进行共同因子分析；将根因定位到输入合同、路由、实施步骤、验证或复审中的单一责任边界；"
            "优先增加前置校验、负向测试或精确触发条件，不扩大默认模型档位和 Reviewer 数量。"
        )
    if signal.signal_type is SignalType.MODEL_ESCALATION:
        return (
            "对比推荐档位与实际升级任务的复杂度、风险、上下文长度和修复结果；修订复杂度特征或升级阈值；"
            "通过历史样本回放验证节省成本且不降低 Blocking Finding 命中率。"
        )
    if signal.signal_type is SignalType.ROUTING_DEVIATION:
        return (
            "提取偏差任务的正样本和容易误触发的负样本；收紧或补充 Skill 触发词、排除条件和主/支撑 Skill 组合规则；"
            "不得通过默认加载更多 Skill 掩盖路由问题。"
        )
    if signal.signal_type is SignalType.EXCESSIVE_REPAIR:
        return (
            "审查实施前任务信封、Review Packet、验收标准和依赖识别是否完整；将重复返工原因前移到 Preflight 或定向验证；"
            "保持修复轮次上限，不允许无限自我修复。"
        )
    if signal.signal_type is SignalType.LOW_REVIEWER_YIELD:
        if assessment.recommended_action is ProposalAction.DEPRECATE:
            return (
                "先将该 Reviewer 从默认组合降为按需触发并进入观察期；保留高风险场景回退入口；"
                "只有观察期内质量指标无下降且人工批准后，才可另行创建退役实施任务。"
            )
        return (
            "检查 Reviewer 职责是否与其他 Reviewer 重叠、输入 Packet 是否缺少必要证据、任务样本是否不匹配；"
            "采用默认组与按需组的对照回放，评估发现率、误报率和成本后再决定调整。"
        )
    if signal.signal_type is SignalType.NEGATIVE_OUTCOME:
        return (
            "按失败类别、Skill、项目阶段、模型档位和 Reviewer 组合分层复盘；补齐可区分根因的结构化字段；"
            "在没有单一高置信根因前，只形成调查任务，不直接修改全局规则。"
        )
    return "收集更多独立任务证据，明确价值、复杂度、风险、回滚和验证边界后再决定是否修改。"


def _expected_value(signal: PatternSignal) -> str:
    if signal.signal_type is SignalType.MODEL_ESCALATION:
        return "降低不必要的模型升级和 Token/credits 消耗，同时保持任务质量与 Blocking Finding 覆盖率。"
    if signal.signal_type is SignalType.LOW_REVIEWER_YIELD:
        return "减少低收益 Reviewer 调用和重复上下文加载，并保留高风险任务的兜底覆盖。"
    if signal.signal_type is SignalType.ROUTING_DEVIATION:
        return "降低 Skill 误触发、漏触发和无关 Reference 加载，提高任务范围识别准确率。"
    if signal.signal_type is SignalType.EXCESSIVE_REPAIR:
        return "将问题发现前移，减少集中修复轮次、上下文漂移和重复验证。"
    if signal.signal_type is SignalType.REPEATED_FAILURE:
        return "降低同类故障复发率和人工返工成本，使失败能够在更早阶段被阻断。"
    return "提高结果稳定性和可解释性，为后续受控优化提供可比较基线。"


def _rollback_plan(signal: PatternSignal) -> Tuple[str, ...]:
    return (
        "实施前记录目标文件、规则、模型配置或 Reviewer Profile 的完整哈希和 Git 基线",
        "所有变更以独立任务和最小提交实施，不覆盖历史提案、Evidence 和观察快照",
        "验证失败、质量下降或成本异常时恢复原配置并重新执行原回归基线",
        "回滚后记录失败原因和实际结果，不自动再次应用同一提案",
    )


def _validation_plan(signal: PatternSignal) -> Tuple[str, ...]:
    base = [
        "使用提案 Evidence 中的历史任务构造回放集，并补充至少一个负向对照样本",
        "比较修改前后的成功率、Blocking Finding、修复轮次、模型升级率和 Reviewer 成本",
        "执行现有 Skill 路由回归、运行时合同测试、安装/恢复测试和最终读回校验",
        "至少经过一个新的独立任务窗口后再判断优化是否有效，不以单次成功作为结论",
    ]
    if signal.signal_type is SignalType.LOW_REVIEWER_YIELD:
        base.append("确认 Reviewer 调整后高风险任务覆盖率没有下降，并保留人工强制启用入口")
    if signal.signal_type is SignalType.ROUTING_DEVIATION:
        base.append("同时验证正向触发、相邻语义误触发和不应触发三类路由用例")
    return tuple(base)


def generate_proposals(
    project_id: str,
    snapshot: SelfObservationSnapshot,
    assessments: Sequence[ValueComplexityAssessment],
) -> List[OptimizationProposal]:
    snapshot.verify_integrity()
    signals: Dict[str, PatternSignal] = {signal.signal_id: signal for signal in snapshot.signals}
    proposals: List[OptimizationProposal] = []
    for assessment in assessments:
        assessment.verify_integrity()
        signal = signals.get(assessment.signal_id)
        if signal is None:
            raise ProposalGenerationError("评估引用了不存在的 signal_id: %s" % assessment.signal_id)
        if not assessment.evidence:
            continue
        if assessment.recommended_action is not ProposalAction.INVESTIGATE:
            if assessment.confidence not in {ConfidenceLevel.L3, ConfidenceLevel.L4}:
                continue
        if assessment.value_score < 35:
            continue
        constraints = list(assessment.constraints)
        constraints.extend([
            "该提案只能进入人工评审队列，不得由 Self Evolution 服务自动实施",
            "接受提案不等于授权修改；实施仍需新的 Task Envelope 与 Approval",
            "禁止将单一项目结论直接晋升为跨项目全局规则",
        ])
        proposals.append(OptimizationProposal.create(
            project_id=project_id,
            assessment=assessment,
            action_type=assessment.recommended_action,
            target_resource=signal.target,
            problem_statement=signal.summary,
            recommendation=_recommendation(signal, assessment),
            expected_value=_expected_value(signal),
            rollback_plan=_rollback_plan(signal),
            validation_plan=_validation_plan(signal),
            constraints=constraints,
        ))
    return proposals
