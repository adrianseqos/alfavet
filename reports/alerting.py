"""Alerting module: dispatches reports and gap alerts to configured channels.

Supports Slack webhooks and e-mail (SMTP).  All channels degrade gracefully
when their configuration is missing — a warning is logged but the process
never crashes due to missing credentials.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Sequence

from config.settings import (
    ALERT_EMAIL_FROM,
    ALERT_EMAIL_TO,
    SLACK_WEBHOOK_URL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract channel
# ---------------------------------------------------------------------------
class AlertChannel(ABC):
    """Base class for alert delivery channels."""

    @abstractmethod
    def send(self, subject: str, body: str, priority: str = "normal") -> bool:
        """Send a message through this channel.

        Parameters
        ----------
        subject:
            Short summary / title.
        body:
            Full message text.
        priority:
            One of ``"low"``, ``"normal"``, ``"high"``.

        Returns
        -------
        bool
            ``True`` when the message was sent successfully.
        """

    @abstractmethod
    def is_configured(self) -> bool:
        """Return ``True`` if all required env vars / settings are present."""


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------
class SlackAlertChannel(AlertChannel):
    """Send alerts to a Slack channel via an incoming webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or SLACK_WEBHOOK_URL

    def is_configured(self) -> bool:  # noqa: D102
        return bool(self.webhook_url)

    def send(self, subject: str, body: str, priority: str = "normal") -> bool:  # noqa: D102
        if not self.is_configured():
            logger.warning("Slack webhook URL not configured — skipping alert.")
            return False

        import urllib.request

        emoji = ":warning:" if priority == "high" else ":memo:"
        payload = {
            "text": f"{emoji} *{subject}*\n```\n{body[:3000]}\n```",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    logger.info("Slack alert sent: %s", subject)
                    return True
                logger.warning("Slack webhook returned status %d", resp.status)
                return False
        except Exception as exc:
            logger.error("Failed to send Slack alert: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
class EmailAlertChannel(AlertChannel):
    """Send alerts via SMTP e-mail."""

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        email_to: str | None = None,
        email_from: str | None = None,
    ) -> None:
        self.smtp_host = smtp_host or SMTP_HOST
        self.smtp_port = smtp_port or SMTP_PORT
        self.smtp_user = smtp_user or SMTP_USER
        self.smtp_password = smtp_password or SMTP_PASSWORD
        self.email_to = email_to or ALERT_EMAIL_TO
        self.email_from = email_from or ALERT_EMAIL_FROM

    def is_configured(self) -> bool:  # noqa: D102
        return bool(self.smtp_host and self.email_to)

    def send(self, subject: str, body: str, priority: str = "normal") -> bool:  # noqa: D102
        if not self.is_configured():
            logger.warning(
                "Email alerting not configured (SMTP_HOST or ALERT_EMAIL_TO missing) "
                "— skipping alert."
            )
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[PetNutraIntel] {subject}"
        msg["From"] = self.email_from
        msg["To"] = self.email_to
        if priority == "high":
            msg["X-Priority"] = "1"

        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.ehlo()
                if self.smtp_port != 25:
                    server.starttls()
                    server.ehlo()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.email_from, self.email_to.split(","), msg.as_string())
            logger.info("Email alert sent to %s: %s", self.email_to, subject)
            return True
        except Exception as exc:
            logger.error("Failed to send email alert: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Alert manager
# ---------------------------------------------------------------------------
class AlertManager:
    """Dispatches alerts to all configured channels."""

    def __init__(self, channels: Sequence[AlertChannel] | None = None) -> None:
        if channels is not None:
            self.channels = list(channels)
        else:
            # Auto-discover available channels from settings
            self.channels: list[AlertChannel] = []
            slack = SlackAlertChannel()
            if slack.is_configured():
                self.channels.append(slack)
            email = EmailAlertChannel()
            if email.is_configured():
                self.channels.append(email)

        if not self.channels:
            logger.warning(
                "No alert channels are configured.  Set SLACK_WEBHOOK_URL or "
                "SMTP_HOST + ALERT_EMAIL_TO to enable alerting."
            )

    def send(self, subject: str, body: str, priority: str = "normal") -> int:
        """Send *subject* / *body* to every configured channel.

        Returns the number of channels that accepted the message.
        """
        success = 0
        for channel in self.channels:
            try:
                if channel.send(subject, body, priority=priority):
                    success += 1
            except Exception as exc:
                logger.error("Alert channel %s failed: %s", type(channel).__name__, exc)
        return success


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------
def send_weekly_report(summary: str) -> int:
    """Send the weekly intelligence summary to all configured channels.

    Returns the number of channels that accepted the message.
    """
    manager = AlertManager()
    return manager.send(
        subject="Weekly Pet Nutraceutical Intelligence Report",
        body=summary,
        priority="normal",
    )


def send_gap_alert(gaps: list[dict]) -> int:
    """Send a high-priority alert for newly identified portfolio gaps.

    Parameters
    ----------
    gaps:
        List of gap dicts as returned by ``run_gap_analysis``.

    Returns
    -------
    int
        Number of channels that accepted the message.
    """
    if not gaps:
        logger.info("No gaps to alert on.")
        return 0

    lines = ["HIGH-PRIORITY GAP ALERT", "=" * 40, ""]
    for i, gap in enumerate(gaps, 1):
        lines.append(
            f"{i}. [{gap.get('priority', '?').upper()}] "
            f"{gap.get('type', '?')}: {gap.get('dimension', '?')}"
        )
        if gap.get("rationale"):
            lines.append(f"   {gap['rationale']}")
        lines.append("")

    body = "\n".join(lines)
    manager = AlertManager()
    return manager.send(
        subject=f"Gap Alert: {len(gaps)} portfolio gaps identified",
        body=body,
        priority="high",
    )
