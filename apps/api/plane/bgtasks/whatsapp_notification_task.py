# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import os
import re
import uuid
from typing import Optional, Tuple, Union

import requests
from celery import shared_task

# Module imports
from plane.db.models import Issue, User
from plane.license.utils.instance_value import get_configuration_value
from plane.settings.redis import redis_instance
from plane.utils.exception_logger import log_exception

logger = logging.getLogger("plane.worker")


def get_waha_config() -> Tuple[str | None, str | None, str | None]:
    """
    Helper to get WAHA configuration values, returns:
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
    """Celery task to send a WhatsApp notification to a mentioned user.

    Skips notification if mobile number is empty or not set.
    """
    try:
        target_user_id = receiver_id or user_id
        notification_text = text or message

        if not notification_text:
            logger.warning("No message or text provided for WhatsApp notification. Skipping.")
            return None
        
        try:
            ri = redis_instance()
            base_api = ri.get(str(issue_id)).decode() if ri.get(str(issue_id)) else None

            issue = Issue.objects.get(pk=issue_id)
            workspace_slug = str(issue.project.workspace.slug)
            project_id = str(issue.project.id)

            if base_api and workspace_slug and project_id and issue_id:
                notification_text = f"{notification_text}\n\n{base_api}/{workspace_slug}/projects/{str(project_id)}/issues/{issue_id}"
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
