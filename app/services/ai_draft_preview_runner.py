"""Background execution for async AI draft preview (LLM + transcript + bundle)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import app.config as app_config
from app.api.schemas import AiTaskDraftValidationErrorBody
from app.models.ai_draft_communication_event import AiDraftCommunicationKind
from app.services import ai_draft_session_repo
from app.services.ai_task_draft_service import (
    AiTaskDraftItemValidationError,
    AiTaskDraftService,
    AiTaskDraftValidationError,
)
from app.services.integrations.llm_text_adapter import (
    OpenAITextDraftAdapter,
    TextDraftRefusalError,
    TextDraftUpstreamError,
)
from app.services import tenant_repo

logger = logging.getLogger(__name__)


def _validation_error_body(exc: AiTaskDraftValidationError) -> dict[str, Any]:
    if isinstance(exc, AiTaskDraftItemValidationError):
        return AiTaskDraftValidationErrorBody(
            message=str(exc),
            item_index=exc.item_index,
            field=exc.field,
        ).model_dump()
    return AiTaskDraftValidationErrorBody(message=str(exc)).model_dump()


def run_ai_draft_preview_job(
    *,
    draft_session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    brief: str,
) -> None:
    """Run LLM preview: transcript rows, then bundle + terminal preview_status."""

    tenant = tenant_repo.get_tenant_by_id(tenant_id)
    if tenant is None:
        logger.warning("ai_draft_preview: tenant %s not found", tenant_id)
        ai_draft_session_repo.finalize_preview_failure(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            last_error={"error": "tenant_missing", "message": "Tenant not found"},
        )
        return

    adapter = OpenAITextDraftAdapter(api_key=app_config.OPENAI_API_KEY)
    service = AiTaskDraftService(adapter)

    try:
        ai_draft_session_repo.append_communication_event(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            kind=AiDraftCommunicationKind.USER_INPUT,
            payload={"brief": brief},
        )
        messages = adapter.build_preview_messages(
            brief=brief,
            tenant_context=AiTaskDraftService.build_tenant_context(tenant),
        )
        ai_draft_session_repo.append_communication_event(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            kind=AiDraftCommunicationKind.PROMPT_TO_AI,
            payload={
                "model": adapter.model,
                "messages": messages,
            },
        )
        raw_text = adapter.complete_preview_chat(messages)
        ai_draft_session_repo.append_communication_event(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            kind=AiDraftCommunicationKind.RESPONSE_FROM_AI,
            payload={"content": raw_text},
        )
        raw_dict = adapter.parse_campaign_json_from_assistant(raw_text)
        preview = service.validate_raw_llm_dict(raw_dict)
        ai_draft_session_repo.finalize_preview_success(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            items=[it.model_dump(mode="json") for it in preview.items],
        )
    except TextDraftRefusalError as exc:
        _record_failure(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            message=str(exc),
            error_type="refusal",
        )
    except TextDraftUpstreamError as exc:
        _record_failure(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            message=str(exc),
            error_type="upstream",
        )
    except AiTaskDraftValidationError as exc:
        body = _validation_error_body(exc)
        ai_draft_session_repo.append_communication_event(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            kind=AiDraftCommunicationKind.ERROR,
            payload={"error": "validation", "detail": body},
        )
        ai_draft_session_repo.finalize_preview_failure(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            last_error=body,
        )
    except Exception as exc:
        logger.exception("ai_draft_preview unexpected failure")
        _record_failure(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            message=str(exc),
            error_type="internal",
        )


def _record_failure(
    *,
    draft_session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    message: str,
    error_type: str,
) -> None:
    payload = {"error": error_type, "message": message}
    try:
        ai_draft_session_repo.append_communication_event(
            draft_session_id=draft_session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            kind=AiDraftCommunicationKind.ERROR,
            payload=payload,
        )
    except Exception:
        logger.exception("ai_draft_preview failed to append error event")
    ai_draft_session_repo.finalize_preview_failure(
        draft_session_id=draft_session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        last_error=payload,
    )
