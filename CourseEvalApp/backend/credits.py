"""Who may run an analysis, with which key, and how much of the lab's credit they have used.

Credit modes (set per professor by the admin):
- our_key_capped:    lab OpenAI key, up to yearly_cap_usd per credit year
- our_key_unlimited: lab OpenAI key, no personal limit
- own_key:           the professor's own key for OpenAI, Anthropic or Google Gemini, with a model they choose;
                     their usage never counts against lab credit
The local Mac Studio model is free but admin-only.

Phase 3's analysis endpoint calls `plan_run()` before a run and `record_usage()` after it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import config
import model_options
from keyvault import KeyVaultError, decrypt_key
from models import CreditMode, Role, UsageLog, User

MODEL_OPENAI = "openai"
MODEL_LOCAL = "local"


def credit_year_start(now: datetime | None = None) -> datetime:
    """Start of the current credit year, from CREDIT_YEAR_START (MM-DD)."""
    now = now or datetime.now(timezone.utc)
    month, day = (int(part) for part in config.CREDIT_YEAR_START.split("-"))
    start = datetime(now.year, month, day, tzinfo=timezone.utc)
    return start if start <= now else start.replace(year=now.year - 1)


def lab_spend_this_year(db: Session, user: User | None = None) -> float:
    query = select(func.coalesce(func.sum(UsageLog.cost_usd), 0.0)).where(
        UsageLog.used_own_key.is_(False), UsageLog.created_at >= credit_year_start()
    )
    if user is not None:
        query = query.where(UsageLog.user_id == user.id)
    return round(float(db.scalar(query) or 0.0), 4)


def allowed_models(user: User) -> list[str]:
    return [MODEL_OPENAI, MODEL_LOCAL] if user.role == Role.ADMIN else [MODEL_OPENAI]


def credit_status(db: Session, user: User) -> dict:
    spent = lab_spend_this_year(db, user)
    capped = user.credit_mode == CreditMode.OUR_KEY_CAPPED
    cap = user.yearly_cap_usd if capped else None
    return {
        "credit_mode": user.credit_mode,
        "yearly_cap_usd": cap,
        "spent_this_year_usd": spent,
        "remaining_usd": round(max(0.0, (cap or 0.0) - spent), 4) if capped and cap is not None else None,
        "credit_year_start": credit_year_start().date().isoformat(),
        "has_own_key": bool(user.encrypted_api_key),
        "api_key_last4": user.api_key_last4,
        **own_key_choice(user),
        "allowed_models": allowed_models(user),
    }


def own_key_choice(user: User) -> dict:
    """The provider and model of the user's own key, for the account page (None when no key is saved)."""
    if not user.encrypted_api_key:
        return {"api_provider": None, "api_provider_name": None, "api_model": None, "api_model_label": None}
    provider, model = model_options.resolve(user.api_provider, user.api_model)
    return {"api_provider": provider, "api_provider_name": model_options.providers().get(provider, provider),
            "api_model": model["model_id"], "api_model_label": model["label"].split(" (")[0]}  # drop "(recommended)"


@dataclass
class RunPlan:
    model_choice: str        # provider: openai, anthropic, gemini or local
    api_key: str | None      # professor's own key, or None to use the lab key / local model
    uses_own_key: bool
    model_id: str | None = None  # None: the provider's default (the lab model for OpenAI)


def _refuse(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def plan_run(db: Session, user: User, model_choice: str) -> RunPlan:
    """Check the user may start a run now, and pick the key. Raises HTTPException with a clear reason."""
    if model_choice not in (MODEL_OPENAI, MODEL_LOCAL):
        raise _refuse(status.HTTP_400_BAD_REQUEST, "Unknown model")
    if model_choice == MODEL_LOCAL:
        if user.role != Role.ADMIN:
            raise _refuse(status.HTTP_403_FORBIDDEN, "The local model is only available to administrators")
        return RunPlan(MODEL_LOCAL, None, False)

    if user.credit_mode == CreditMode.OWN_KEY:
        if not user.encrypted_api_key:
            raise _refuse(status.HTTP_400_BAD_REQUEST, "Add your AI provider and API key in your account settings first")
        provider, model = model_options.resolve(user.api_provider, user.api_model)
        try:
            return RunPlan(provider, decrypt_key(user.encrypted_api_key), True, model["model_id"])
        except KeyVaultError as exc:
            raise _refuse(status.HTTP_400_BAD_REQUEST, str(exc))

    if config.TOTAL_CREDIT_BUDGET_USD > 0 and lab_spend_this_year(db) >= config.TOTAL_CREDIT_BUDGET_USD:
        raise _refuse(status.HTTP_402_PAYMENT_REQUIRED, "The shared AI credit for this year is used up. Please contact the administrator.")

    if user.credit_mode == CreditMode.OUR_KEY_CAPPED:
        cap = user.yearly_cap_usd if user.yearly_cap_usd is not None else config.DEFAULT_YEARLY_CAP_USD
        if lab_spend_this_year(db, user) >= cap:
            raise _refuse(status.HTTP_402_PAYMENT_REQUIRED,
                          f"You have used your ${cap:.2f} AI credit for this year. Please contact the administrator.")
    return RunPlan(MODEL_OPENAI, None, False)


def record_usage(db: Session, user: User, usage: dict, plan: RunPlan, report_id: int | None = None) -> UsageLog:
    """Store a finished run's token use (from report["metadata"]["usage"]). Own-key and local runs cost the lab $0."""
    lab_cost = 0.0 if plan.uses_own_key or plan.model_choice == MODEL_LOCAL else float(usage.get("estimated_cost_usd") or 0.0)
    entry = UsageLog(
        user_id=user.id,
        report_id=report_id,
        used_own_key=plan.uses_own_key,
        input_tokens=int(usage.get("input_tokens") or 0),
        cached_input_tokens=int(usage.get("cached_input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cost_usd=lab_cost,
    )
    db.add(entry)
    db.commit()
    return entry
