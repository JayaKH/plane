# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import os
import re
import uuid
from datetime import timedelta
from typing import Optional, Tuple, Union

import requests
from celery import shared_task
from django.db.models import Prefetch, Q
from django.utils import timezone

# Module imports
from plane.db.models import Issue, IssueAssignee, User
from plane.license.utils.instance_value import get_configuration_value
from plane.settings.redis import redis_instance
from plane.utils.exception_logger import log_exception

logger = logging.getLogger("plane.worker")


def get_waha_config() -> Tuple[str | None, str | None, str | None]:
    """Helper to get WAHA configuration values, returns:

    - base_url, api_key, session
    """
    base_url, api_key, session = get_configuration_value(
        [
            {
                "key": "WAHA_BASE_URL",
                "default": os.environ.get("WAHA_BASE_URL", None),
            },
            {
                "key": "WAHA_API_KEY",
                "default": os.environ.get("WAHA_API_KEY", None),
            },
            {
                "key": "WAHA_SESSION",
                "default": os.environ.get("WAHA_SESSION", None),
            },
        ]
    )

    if not base_url:
        log_exception(ValueError("Missing WAHA base URL from environment variables"))
        return None, None, None

    if not api_key:
        log_exception(ValueError(f"Missing API key for URL: {base_url}"))
        return None, None, None

    if not session:
        log_exception(ValueError(f"Missing session for URL: {base_url}"))
        return None, None, None

    return base_url.strip(), api_key.strip(), session.strip()


def format_chat_id(mobile_number: Optional[str]) -> Optional[str]:
    """Format user mobile number into WAHA chatId (e.g., 12132132130@c.us).

    Returns None if mobile_number is empty, not set, or contains no digits.
    """
    if not mobile_number:
        return None
    cleaned = str(mobile_number).strip()
    if not cleaned:
        return None
    if "@c.us" in cleaned or "@g.us" in cleaned:
        return cleaned
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None
    return f"{digits}@c.us"


def send_waha_message(chat_id: str, text: str) -> Optional[dict]:
    """Send text message to WAHA /api/sendText."""
    base_url, api_key, session = get_waha_config()
    if not base_url or not api_key or not session:
        return None

    url = f"{base_url.rstrip('/')}/api/sendText"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "session": session,
        "chatId": chat_id,
        "text": text,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"WhatsApp notification sent successfully to {chat_id}")
        return response.json() if response.content else {}
    except requests.RequestException as e:
        logger.error(f"Failed to send WhatsApp message via WAHA to {chat_id}: {e}")
        return None
    except Exception as e:
        log_exception(e)
        return None


@shared_task
def send_whatsapp_notification(
    receiver_id: Optional[Union[str, uuid.UUID]] = None,
    message: Optional[str] = None,
    issue_id: Optional[Union[str, uuid.UUID]] = None,
    user_id: Optional[Union[str, uuid.UUID]] = None,
    chat_id: Optional[str] = None,
    text: Optional[str] = None,
    **kwargs,
):
    """Celery task to send a WhatsApp notification to a user.

    Skips notification if mobile number is empty or not set.
    """
    try:
        target_user_id = receiver_id or user_id
        notification_text = text or message

        if not notification_text:
            logger.warning("No message or text provided for WhatsApp notification. Skipping.")
            return None

        if issue_id:
            try:
                ri = redis_instance()
                base_api = ri.get(str(issue_id)).decode() if ri.get(str(issue_id)) else None
                base_url = (base_api or os.environ.get("WEB_URL")).strip().rstrip("/")

                issue = Issue.objects.get(pk=issue_id)
                workspace_slug = str(issue.project.workspace.slug)
                project_id = str(issue.project.id)

                if base_url and workspace_slug and project_id:
                    issue_link = f"{base_url}/{workspace_slug}/projects/{project_id}/issues/{issue_id}"
                    if issue_link not in notification_text:
                        notification_text = f"{notification_text}\n\n{issue_link}"
            except Exception as e:
                log_exception(e)

        if not chat_id:
            if not target_user_id:
                logger.warning("No receiver_id or user_id provided for WhatsApp notification. Skipping.")
                return None

            try:
                user = User.objects.get(pk=target_user_id)
            except (User.DoesNotExist, Exception) as e:
                logger.warning(f"User {target_user_id} not found: {e}. Skipping WhatsApp notification.")
                return None

            if not user.mobile_number or not str(user.mobile_number).strip():
                logger.info(f"User {target_user_id} has no mobile number configured. Skipping WhatsApp notification.")
                return None

            chat_id = format_chat_id(user.mobile_number)
            if not chat_id:
                logger.info(
                    f"User {target_user_id} mobile number could not be formatted into chatId. Skipping WhatsApp notification."
                )
                return None
        else:
            chat_id = format_chat_id(chat_id)
            if not chat_id:
                logger.info("Invalid chatId provided. Skipping WhatsApp notification.")
                return None

        return send_waha_message(chat_id=chat_id, text=notification_text)
    except Exception as e:
        log_exception(e)
        return None


@shared_task
def send_due_date_reminder():
    """Daily background task to send WhatsApp notifications via WAHA for any issue

    in any project that is in the "Todo" or "In Progress" state and has a due
    date of tomorrow, today, or a past date.
    Issues with no due date are skipped.
    """
    try:
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        issues = (
            Issue.objects.filter(
                is_draft=False,
                target_date__isnull=False,
                target_date__lte=tomorrow,
                archived_at__isnull=True,
                project__archived_at__isnull=True,
            )
            .filter(
                Q(state__name__iexact="Todo")
                | Q(state__name__iexact="In Progress")
            )
            .select_related("project", "state", "created_by")
            .prefetch_related(
                Prefetch(
                    "issue_assignee",
                    queryset=IssueAssignee.objects.select_related("assignee"),
                )
            )
        )

        sent_count = 0
        for issue in issues:
            if issue.target_date < today:
                days_overdue = (today - issue.target_date).days
                days_text = f"{days_overdue} day{'s' if days_overdue > 1 else ''} overdue"
                due_status = f"is {days_text} (due {issue.target_date})"
            elif issue.target_date == today:
                due_status = f"is due today ({issue.target_date})"
            else:
                due_status = f"is due tomorrow ({issue.target_date})"

            project_identifier = issue.project.identifier if issue.project and issue.project.identifier else ""
            issue_identifier = f"{project_identifier}-{issue.sequence_id}" if project_identifier else f"#{issue.sequence_id}"
            state_status = f"State: *{issue.state.name}*" if issue.state and issue.state.name else ""

            message = (
                f"Reminder: Issue *{issue_identifier}* ({issue.name}) assigned to you {due_status}. {state_status}"
                if assignees else f"Reminder: Your issue *{issue_identifier}* ({issue.name}) {due_status}. {state_status}"
            ).strip()

            assignees = [ia.assignee for ia in issue.issue_assignee.all() if ia.assignee]
            recipients = assignees if assignees else ([issue.created_by] if issue.created_by else [])

            for recipient in recipients:
                if not recipient or not recipient.mobile_number or not str(recipient.mobile_number).strip():
                    continue

                send_whatsapp_notification.delay(
                    issue_id=str(issue.id),
                    receiver_id=str(recipient.id),
                    message=message,
                )
                sent_count += 1

        logger.info(f"send_due_date_reminder finished. Dispatched {sent_count} notifications.")
        return sent_count
    except Exception as e:
        log_exception(e)
        logger.error(f"Error executing send_due_date_reminder: {e}")
        return 0
