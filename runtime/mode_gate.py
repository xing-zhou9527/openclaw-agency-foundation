from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping

from .guardrails import FoundationRuleError


class SessionMode(str, Enum):
    ASSISTANT = "assistant"
    COMPANY = "company"


class RequestKind(str, Enum):
    GENERAL_CHAT = "general_chat"
    KNOWLEDGE_HELP = "knowledge_help"
    META_FOUNDATION = "meta_foundation"
    COMPANY_OPERATION = "company_operation"


class ActivationScope(str, Enum):
    REQUEST = "request"
    STICKY_TASK = "sticky_task"


NON_COMPANY_REQUEST_KINDS = {
    RequestKind.GENERAL_CHAT,
    RequestKind.KNOWLEDGE_HELP,
    RequestKind.META_FOUNDATION,
}


@dataclass(frozen=True)
class ModeIntent:
    request_id: str
    request_kind: RequestKind
    reason: str
    requires_business_execution: bool = False
    requires_line_ownership: bool = False
    continue_existing_company_task: bool = False
    target_line_id: str | None = None
    scope: ActivationScope = ActivationScope.REQUEST


@dataclass(frozen=True)
class ModeDecision:
    request_id: str
    request_kind: RequestKind
    session_mode: SessionMode
    reason: str
    allow_control_tower: bool
    requires_business_execution: bool
    requires_line_ownership: bool
    continue_existing_company_task: bool
    scope: ActivationScope
    target_line_id: str | None = None
    needs_confirmation: bool = False


def decide_session_mode(intent: ModeIntent) -> ModeDecision:
    reason = intent.reason.strip()
    if not reason:
        raise FoundationRuleError("mode intent requires a non-empty reason")

    if intent.scope == ActivationScope.STICKY_TASK and not intent.continue_existing_company_task:
        raise FoundationRuleError(
            "sticky company mode is only allowed when continuing an existing company task"
        )

    if intent.request_kind in NON_COMPANY_REQUEST_KINDS:
        return ModeDecision(
            request_id=intent.request_id,
            request_kind=intent.request_kind,
            session_mode=SessionMode.ASSISTANT,
            reason=reason,
            allow_control_tower=False,
            requires_business_execution=False,
            requires_line_ownership=False,
            continue_existing_company_task=False,
            scope=ActivationScope.REQUEST,
            target_line_id=None,
            needs_confirmation=False,
        )

    if intent.request_kind == RequestKind.COMPANY_OPERATION:
        if intent.continue_existing_company_task or (
            intent.requires_business_execution and intent.requires_line_ownership
        ):
            return ModeDecision(
                request_id=intent.request_id,
                request_kind=intent.request_kind,
                session_mode=SessionMode.COMPANY,
                reason=reason,
                allow_control_tower=True,
                requires_business_execution=True,
                requires_line_ownership=True,
                continue_existing_company_task=intent.continue_existing_company_task,
                scope=intent.scope,
                target_line_id=intent.target_line_id,
                needs_confirmation=False,
            )

        return ModeDecision(
            request_id=intent.request_id,
            request_kind=intent.request_kind,
            session_mode=SessionMode.ASSISTANT,
            reason=(
                "request sounds operational, but company mode was denied because "
                "line-owned execution / durable task ownership was not established"
            ),
            allow_control_tower=False,
            requires_business_execution=intent.requires_business_execution,
            requires_line_ownership=intent.requires_line_ownership,
            continue_existing_company_task=False,
            scope=ActivationScope.REQUEST,
            target_line_id=intent.target_line_id,
            needs_confirmation=True,
        )

    raise FoundationRuleError(f"unsupported request kind for mode gate: {intent.request_kind}")


def validate_mode_decision(decision: ModeDecision) -> None:
    if not decision.request_id.strip():
        raise FoundationRuleError("mode decision requires request_id")
    if not decision.reason.strip():
        raise FoundationRuleError("mode decision requires a non-empty reason")
    if decision.scope == ActivationScope.STICKY_TASK and not decision.continue_existing_company_task:
        raise FoundationRuleError(
            "sticky_task scope requires continue_existing_company_task=true"
        )
    if decision.allow_control_tower and decision.session_mode != SessionMode.COMPANY:
        raise FoundationRuleError(
            "allow_control_tower=true requires session_mode=company"
        )
    if decision.session_mode == SessionMode.COMPANY:
        if decision.request_kind != RequestKind.COMPANY_OPERATION:
            raise FoundationRuleError(
                "company mode requires request_kind=company_operation"
            )
        if not decision.allow_control_tower:
            raise FoundationRuleError(
                "company mode requires allow_control_tower=true"
            )
        if not (
            decision.continue_existing_company_task
            or (decision.requires_business_execution and decision.requires_line_ownership)
        ):
            raise FoundationRuleError(
                "company mode requires either company-task continuation or both execution + line ownership"
            )
    if decision.request_kind in NON_COMPANY_REQUEST_KINDS and decision.session_mode != SessionMode.ASSISTANT:
        raise FoundationRuleError(
            f"non-company request kind must stay in assistant mode: {decision.request_kind.value}"
        )


def coerce_mode_decision(payload: Mapping[str, object] | ModeDecision) -> ModeDecision:
    if isinstance(payload, ModeDecision):
        validate_mode_decision(payload)
        return payload

    decision = ModeDecision(
        request_id=str(payload["request_id"]),
        request_kind=RequestKind(str(payload["request_kind"])),
        session_mode=SessionMode(str(payload["session_mode"])),
        reason=str(payload["reason"]),
        allow_control_tower=bool(payload["allow_control_tower"]),
        requires_business_execution=bool(payload["requires_business_execution"]),
        requires_line_ownership=bool(payload["requires_line_ownership"]),
        continue_existing_company_task=bool(payload["continue_existing_company_task"]),
        scope=ActivationScope(str(payload["scope"])),
        target_line_id=(
            str(payload["target_line_id"])
            if payload.get("target_line_id") is not None
            else None
        ),
        needs_confirmation=bool(payload["needs_confirmation"]),
    )
    validate_mode_decision(decision)
    return decision


def mode_decision_to_payload(decision: ModeDecision) -> dict:
    validate_mode_decision(decision)
    payload = asdict(decision)
    payload["request_kind"] = decision.request_kind.value
    payload["session_mode"] = decision.session_mode.value
    payload["scope"] = decision.scope.value
    return payload


def ensure_company_mode_active(
    decision: ModeDecision,
    *,
    expected_line_id: str | None = None,
) -> None:
    validate_mode_decision(decision)
    if decision.session_mode != SessionMode.COMPANY or not decision.allow_control_tower:
        raise FoundationRuleError(
            "company-mode control-tower actions require an active company-mode decision"
        )
    if decision.request_kind != RequestKind.COMPANY_OPERATION:
        raise FoundationRuleError(
            "company-mode control-tower actions require request_kind=company_operation"
        )
    if expected_line_id and decision.target_line_id and decision.target_line_id != expected_line_id:
        raise FoundationRuleError(
            f"mode decision line mismatch: {decision.target_line_id} != {expected_line_id}"
        )
