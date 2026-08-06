"""
Alert Management and Escalation System for Knowledge Graph Analytics Dashboard
Comprehensive alerting with multi-channel notification and escalation policies
"""

import asyncio
import json
import logging
import os
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MimeMultipart
from email.mime.text import MimeText
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import aiohttp
import jinja2

from .metrics import business_metrics
from .opentelemetry import otel_manager

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert status states"""

    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


class NotificationChannel(Enum):
    """Available notification channels"""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"


@dataclass
class Alert:
    """Alert data structure"""

    id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    summary: str
    description: str
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    starts_at: datetime = field(default_factory=datetime.utcnow)
    ends_at: Optional[datetime] = None
    generator_url: Optional[str] = None
    fingerprint: str = ""
    runbook_url: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None


@dataclass
class EscalationPolicy:
    """Escalation policy configuration"""

    id: str
    name: str
    severity_threshold: AlertSeverity
    steps: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True


@dataclass
class NotificationConfig:
    """Notification channel configuration"""

    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    rate_limit_minutes: int = 5
    max_per_hour: int = 20


class AlertManager:
    """Centralized alert management system"""

    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.escalation_policies: Dict[str, EscalationPolicy] = {}
        self.notification_configs: Dict[NotificationChannel, NotificationConfig] = {}
        self.notification_history: List[Dict[str, Any]] = []
        self._last_notifications: Dict[str, datetime] = {}
        self._notification_counts: Dict[str, int] = {}

        # Initialize notification configs
        self._initialize_notification_configs()
        self._initialize_escalation_policies()

    def _initialize_notification_configs(self):
        """Initialize notification channel configurations"""
        # Email configuration
        self.notification_configs[NotificationChannel.EMAIL] = NotificationConfig(
            channel=NotificationChannel.EMAIL,
            enabled=os.environ.get("ALERT_EMAIL_ENABLED", "true").lower() == "true",
            config={
                "smtp_server": os.environ.get("SMTP_SERVER", "localhost"),
                "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
                "smtp_username": os.environ.get("SMTP_USERNAME", ""),
                "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
                "from_address": os.environ.get(
                    "ALERT_FROM_EMAIL", "alerts@knowledge-graph.dev"
                ),
                "to_addresses": os.environ.get("ALERT_TO_EMAILS", "").split(","),
                "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() == "true",
            },
            rate_limit_minutes=5,
            max_per_hour=20,
        )

        # Slack configuration
        self.notification_configs[NotificationChannel.SLACK] = NotificationConfig(
            channel=NotificationChannel.SLACK,
            enabled=os.environ.get("ALERT_SLACK_ENABLED", "true").lower() == "true",
            config={
                "webhook_url": os.environ.get("SLACK_WEBHOOK_URL", ""),
                "channel": os.environ.get("SLACK_CHANNEL", "#alerts"),
                "username": "Knowledge Graph Alerts",
            },
            rate_limit_minutes=2,
            max_per_hour=30,
        )

        # Webhook configuration
        self.notification_configs[NotificationChannel.WEBHOOK] = NotificationConfig(
            channel=NotificationChannel.WEBHOOK,
            enabled=os.environ.get("ALERT_WEBHOOK_ENABLED", "false").lower() == "true",
            config={
                "url": os.environ.get("ALERT_WEBHOOK_URL", ""),
                "headers": json.loads(os.environ.get("ALERT_WEBHOOK_HEADERS", "{}")),
                "timeout": int(os.environ.get("ALERT_WEBHOOK_TIMEOUT", "30")),
            },
            rate_limit_minutes=1,
            max_per_hour=100,
        )

        # PagerDuty configuration
        self.notification_configs[NotificationChannel.PAGERDUTY] = NotificationConfig(
            channel=NotificationChannel.PAGERDUTY,
            enabled=os.environ.get("ALERT_PAGERDUTY_ENABLED", "false").lower()
            == "true",
            config={
                "integration_key": os.environ.get("PAGERDUTY_INTEGRATION_KEY", ""),
                "service_key": os.environ.get("PAGERDUTY_SERVICE_KEY", ""),
                "api_url": "https://events.pagerduty.com/v2/enqueue",
            },
            rate_limit_minutes=1,
            max_per_hour=50,
        )

    def _initialize_escalation_policies(self):
        """Initialize escalation policies"""
        # Critical escalation policy
        self.escalation_policies["critical"] = EscalationPolicy(
            id="critical",
            name="Critical Alert Escalation",
            severity_threshold=AlertSeverity.CRITICAL,
            steps=[
                {
                    "delay_minutes": 0,
                    "channels": [NotificationChannel.SLACK, NotificationChannel.EMAIL],
                    "message": "Immediate notification required",
                },
                {
                    "delay_minutes": 5,
                    "channels": [NotificationChannel.PAGERDUTY],
                    "message": "Critical alert not acknowledged in 5 minutes",
                },
                {
                    "delay_minutes": 15,
                    "channels": [NotificationChannel.EMAIL],
                    "message": "Critical alert escalation - management notification",
                    "additional_recipients": ["management@company.com"],
                },
            ],
            enabled=True,
        )

        # Warning escalation policy
        self.escalation_policies["warning"] = EscalationPolicy(
            id="warning",
            name="Warning Alert Escalation",
            severity_threshold=AlertSeverity.WARNING,
            steps=[
                {
                    "delay_minutes": 0,
                    "channels": [NotificationChannel.SLACK],
                    "message": "Warning notification",
                },
                {
                    "delay_minutes": 10,
                    "channels": [NotificationChannel.EMAIL],
                    "message": "Warning alert persists for 10 minutes",
                },
            ],
            enabled=True,
        )

        # Info escalation policy
        self.escalation_policies["info"] = EscalationPolicy(
            id="info",
            name="Info Alert Escalation",
            severity_threshold=AlertSeverity.INFO,
            steps=[
                {
                    "delay_minutes": 0,
                    "channels": [NotificationChannel.SLACK],
                    "message": "Informational alert",
                }
            ],
            enabled=True,
        )

    async def process_alert(self, alert_data: Dict[str, Any]) -> Alert:
        """Process an incoming alert"""
        try:
            # Create Alert object
            alert = Alert(
                id=alert_data.get("id", f"alert_{datetime.utcnow().timestamp()}"),
                name=alert_data.get("name", ""),
                severity=AlertSeverity(alert_data.get("severity", "info")),
                status=AlertStatus(alert_data.get("status", "firing")),
                summary=alert_data.get("summary", ""),
                description=alert_data.get("description", ""),
                labels=alert_data.get("labels", {}),
                annotations=alert_data.get("annotations", {}),
                starts_at=datetime.fromisoformat(
                    alert_data.get("startsAt", datetime.utcnow().isoformat())
                ),
                ends_at=datetime.fromisoformat(alert_data["endsAt"])
                if "endsAt" in alert_data
                else None,
                generator_url=alert_data.get("generatorURL"),
                fingerprint=alert_data.get("fingerprint", ""),
                runbook_url=alert_data.get("annotations", {}).get("runbook_url"),
                service=alert_data.get("labels", {}).get("service"),
                environment=alert_data.get("labels", {}).get("environment"),
            )

            # Handle alert state
            fingerprint = (
                alert.fingerprint
                or f"{alert.name}_{alert.severity.value}_{alert.service}"
            )

            if alert.status == AlertStatus.FIRING:
                if fingerprint not in self.active_alerts:
                    # New alert
                    self.active_alerts[fingerprint] = alert
                    self.alert_history.append(alert)
                    await self._handle_new_alert(alert)
                else:
                    # Alert update
                    existing_alert = self.active_alerts[fingerprint]
                    existing_alert.description = alert.description
                    existing_alert.annotations.update(alert.annotations)
                    existing_alert.labels.update(alert.labels)

            elif alert.status == AlertStatus.RESOLVED:
                if fingerprint in self.active_alerts:
                    resolved_alert = self.active_alerts[fingerprint]
                    resolved_alert.status = AlertStatus.RESOLVED
                    resolved_alert.ends_at = alert.ends_at or datetime.utcnow()
                    await self._handle_resolved_alert(resolved_alert)
                    del self.active_alerts[fingerprint]

            # Record metrics
            self._record_alert_metrics(alert)

            return alert

        except Exception as e:
            logger.error(f"Error processing alert: {e}")
            raise

    async def _handle_new_alert(self, alert: Alert):
        """Handle a new alert"""
        logger.info(f"New alert: {alert.name} ({alert.severity.value})")

        # Get escalation policy
        policy = self._get_escalation_policy(alert.severity)
        if not policy or not policy.enabled:
            return

        # Process immediate notifications
        await self._execute_escalation_step(alert, policy, 0)

        # Schedule delayed escalations
        asyncio.create_task(self._schedule_escalations(alert, policy))

    async def _handle_resolved_alert(self, alert: Alert):
        """Handle a resolved alert"""
        logger.info(f"Alert resolved: {alert.name}")

        # Send resolution notifications
        await self._send_resolution_notifications(alert)

    def _get_escalation_policy(
        self, severity: AlertSeverity
    ) -> Optional[EscalationPolicy]:
        """Get escalation policy for severity level"""
        for policy in self.escalation_policies.values():
            if severity.value >= policy.severity_threshold.value:
                return policy
        return None

    async def _schedule_escalations(self, alert: Alert, policy: EscalationPolicy):
        """Schedule delayed escalations for an alert"""
        fingerprint = (
            alert.fingerprint or f"{alert.name}_{alert.severity.value}_{alert.service}"
        )

        for i, step in enumerate(
            policy.steps[1:], 1
        ):  # Skip first step (handled immediately)
            delay_seconds = step["delay_minutes"] * 60

            # Wait for the delay
            await asyncio.sleep(delay_seconds)

            # Check if alert is still active
            if fingerprint not in self.active_alerts:
                return  # Alert was resolved

            current_alert = self.active_alerts[fingerprint]
            if current_alert.status == AlertStatus.ACKNOWLEDGED:
                continue  # Skip escalation if acknowledged

            # Execute escalation step
            await self._execute_escalation_step(current_alert, policy, i)

    async def _execute_escalation_step(
        self, alert: Alert, policy: EscalationPolicy, step_index: int
    ):
        """Execute an escalation step"""
        if step_index >= len(policy.steps):
            return

        step = policy.steps[step_index]

        for channel in step["channels"]:
            try:
                await self._send_notification(alert, channel, step)
            except Exception as e:
                logger.error(
                    f"Failed to send {channel.value} notification for alert {alert.id}: {e}"
                )

    async def _send_notification(
        self, alert: Alert, channel: NotificationChannel, step: Dict[str, Any]
    ):
        """Send notification through specified channel"""
        config = self.notification_configs.get(channel)
        if not config or not config.enabled:
            return

        # Check rate limits
        if not self._check_rate_limits(alert.id, config):
            logger.warning(f"Rate limit exceeded for {channel.value} notifications")
            return

        try:
            if channel == NotificationChannel.EMAIL:
                await self._send_email_notification(alert, step)
            elif channel == NotificationChannel.SLACK:
                await self._send_slack_notification(alert, step)
            elif channel == NotificationChannel.WEBHOOK:
                await self._send_webhook_notification(alert, step)
            elif channel == NotificationChannel.PAGERDUTY:
                await self._send_pagerduty_notification(alert, step)

            # Record notification
            self._record_notification(alert, channel, step)

        except Exception as e:
            logger.error(f"Failed to send {channel.value} notification: {e}")
            # Record failed notification
            self._record_notification(alert, channel, step, success=False)

    def _check_rate_limits(self, alert_id: str, config: NotificationConfig) -> bool:
        """Check if notification is within rate limits"""
        now = datetime.utcnow()
        notification_key = f"{alert_id}_{config.channel.value}"

        # Check minimum interval between notifications
        if notification_key in self._last_notifications:
            time_diff = now - self._last_notifications[notification_key]
            if time_diff.total_seconds() < config.rate_limit_minutes * 60:
                return False

        # Check hourly limit
        hourly_key = f"{config.channel.value}_{now.strftime('%Y%m%d%H')}"
        if hourly_key not in self._notification_counts:
            self._notification_counts[hourly_key] = 0

        if self._notification_counts[hourly_key] >= config.max_per_hour:
            return False

        # Update tracking
        self._last_notifications[notification_key] = now
        self._notification_counts[hourly_key] += 1

        return True

    async def _send_email_notification(self, alert: Alert, step: Dict[str, Any]):
        """Send email notification"""
        config = self.notification_configs[NotificationChannel.EMAIL]
        email_config = config.config

        if not email_config["to_addresses"] or not email_config["to_addresses"][0]:
            return

        # Create email content
        subject = f"[{alert.severity.value.upper()}] {alert.summary}"

        # Render email template
        template = self._get_email_template(alert)
        body = template.render(
            alert=alert,
            step=step,
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        # Send email
        msg = MimeMultipart()
        msg["From"] = email_config["from_address"]
        msg["To"] = ", ".join(email_config["to_addresses"])
        msg["Subject"] = subject
        msg.attach(MimeText(body, "html"))

        # Add additional recipients if specified
        if "additional_recipients" in step:
            additional_to = step["additional_recipients"]
            if isinstance(additional_to, str):
                additional_to = [additional_to]
            msg["To"] += ", " + ", ".join(additional_to)

        # Send via SMTP
        with smtplib.SMTP(
            email_config["smtp_server"], email_config["smtp_port"]
        ) as server:
            if email_config["use_tls"]:
                server.starttls()
            if email_config["smtp_username"]:
                server.login(
                    email_config["smtp_username"], email_config["smtp_password"]
                )
            server.send_message(msg)

    async def _send_slack_notification(self, alert: Alert, step: Dict[str, Any]):
        """Send Slack notification"""
        config = self.notification_configs[NotificationChannel.SLACK]
        slack_config = config.config

        webhook_url = slack_config["webhook_url"]
        if not webhook_url:
            return

        # Prepare Slack message
        color = self._get_slack_color(alert.severity)

        payload = {
            "channel": slack_config["channel"],
            "username": slack_config["username"],
            "attachments": [
                {
                    "color": color,
                    "title": f"{alert.severity.value.upper()}: {alert.summary}",
                    "text": alert.description,
                    "fields": [
                        {
                            "title": "Service",
                            "value": alert.service or "Unknown",
                            "short": True,
                        },
                        {
                            "title": "Severity",
                            "value": alert.severity.value.upper(),
                            "short": True,
                        },
                        {
                            "title": "Started",
                            "value": alert.starts_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "short": True,
                        },
                    ],
                    "footer": step.get("message", ""),
                    "ts": int(alert.starts_at.timestamp()),
                }
            ],
        }

        # Add runbook link if available
        if alert.runbook_url:
            payload["attachments"][0]["actions"] = [
                {"type": "button", "text": "View Runbook", "url": alert.runbook_url}
            ]

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                response.raise_for_status()

    async def _send_webhook_notification(self, alert: Alert, step: Dict[str, Any]):
        """Send webhook notification"""
        config = self.notification_configs[NotificationChannel.WEBHOOK]
        webhook_config = config.config

        webhook_url = webhook_config["url"]
        if not webhook_url:
            return

        payload = {
            "alert_id": alert.id,
            "name": alert.name,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "summary": alert.summary,
            "description": alert.description,
            "labels": alert.labels,
            "annotations": alert.annotations,
            "starts_at": alert.starts_at.isoformat(),
            "ends_at": alert.ends_at.isoformat() if alert.ends_at else None,
            "service": alert.service,
            "environment": alert.environment,
            "escalation_step": step,
        }

        headers = webhook_config.get("headers", {})
        timeout = webhook_config.get("timeout", 30)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url, json=payload, headers=headers, timeout=timeout
            ) as response:
                response.raise_for_status()

    async def _send_pagerduty_notification(self, alert: Alert, step: Dict[str, Any]):
        """Send PagerDuty notification"""
        config = self.notification_configs[NotificationChannel.PAGERDUTY]
        pd_config = config.config

        integration_key = pd_config.get("integration_key")
        if not integration_key:
            return

        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": alert.summary,
                "source": alert.service or "knowledge-graph-analytics",
                "severity": self._get_pagerduty_severity(alert.severity),
                "timestamp": alert.starts_at.isoformat(),
                "component": alert.service,
                "group": alert.labels.get("service", "application"),
                "class": alert.labels.get("alertname", "system"),
                "custom_details": {
                    "description": alert.description,
                    "labels": alert.labels,
                    "annotations": alert.annotations,
                    "runbook_url": alert.runbook_url,
                    "escalation_message": step.get("message", ""),
                },
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(pd_config["api_url"], json=payload) as response:
                response.raise_for_status()

    async def _send_resolution_notifications(self, alert: Alert):
        """Send notifications when alert is resolved"""
        # Send to all channels that were used for this alert
        fingerprint = (
            alert.fingerprint or f"{alert.name}_{alert.severity.value}_{alert.service}"
        )

        # Send resolution to Slack
        if self.notification_configs[NotificationChannel.SLACK].enabled:
            await self._send_slack_resolution(alert)

        # Send resolution email if severity was critical or warning
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.WARNING]:
            if self.notification_configs[NotificationChannel.EMAIL].enabled:
                await self._send_email_resolution(alert)

    async def _send_slack_resolution(self, alert: Alert):
        """Send Slack resolution notification"""
        config = self.notification_configs[NotificationChannel.SLACK]
        slack_config = config.config

        webhook_url = slack_config["webhook_url"]
        if not webhook_url:
            return

        payload = {
            "channel": slack_config["channel"],
            "username": slack_config["username"],
            "attachments": [
                {
                    "color": "good",
                    "title": f"RESOLVED: {alert.summary}",
                    "text": f"The alert has been resolved.",
                    "fields": [
                        {
                            "title": "Service",
                            "value": alert.service or "Unknown",
                            "short": True,
                        },
                        {
                            "title": "Duration",
                            "value": self._format_duration(
                                alert.starts_at, alert.ends_at
                            ),
                            "short": True,
                        },
                    ],
                    "ts": int(datetime.utcnow().timestamp()),
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                response.raise_for_status()

    async def _send_email_resolution(self, alert: Alert):
        """Send email resolution notification"""
        config = self.notification_configs[NotificationChannel.EMAIL]
        email_config = config.config

        if not email_config["to_addresses"] or not email_config["to_addresses"][0]:
            return

        subject = f"[RESOLVED] {alert.summary}"

        body = f"""
        <html>
        <body>
            <h2>Alert Resolved</h2>
            <p><strong>Alert:</strong> {alert.summary}</p>
            <p><strong>Service:</strong> {alert.service or 'Unknown'}</p>
            <p><strong>Severity:</strong> {alert.severity.value.upper()}</p>
            <p><strong>Started:</strong> {alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p><strong>Resolved:</strong> {alert.ends_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p><strong>Duration:</strong> {self._format_duration(alert.starts_at, alert.ends_at)}</p>
            <p><strong>Description:</strong> {alert.description}</p>
            <hr>
            <p><em>This alert has been automatically resolved.</em></p>
        </body>
        </html>
        """

        msg = MimeMultipart()
        msg["From"] = email_config["from_address"]
        msg["To"] = ", ".join(email_config["to_addresses"])
        msg["Subject"] = subject
        msg.attach(MimeText(body, "html"))

        with smtplib.SMTP(
            email_config["smtp_server"], email_config["smtp_port"]
        ) as server:
            if email_config["use_tls"]:
                server.starttls()
            if email_config["smtp_username"]:
                server.login(
                    email_config["smtp_username"], email_config["smtp_password"]
                )
            server.send_message(msg)

    def _get_email_template(self, alert: Alert) -> jinja2.Template:
        """Get email template for alert"""
        template_str = """
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #eee;">
                    <h1 style="margin: 0; color: #333;">Knowledge Graph Analytics Alert</h1>
                </div>

                <div style="padding: 20px 0;">
                    <div style="background-color: {{ severity_color }}; color: white; padding: 10px; border-radius: 4px; margin-bottom: 20px;">
                        <h2 style="margin: 0;">{{ alert.severity.value.upper() }} - {{ alert.summary }}</h2>
                    </div>

                    <div style="margin-bottom: 20px;">
                        <p><strong>Service:</strong> {{ alert.service or 'Unknown' }}</p>
                        <p><strong>Started:</strong> {{ alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC') }}</p>
                        {% if alert.environment %}
                        <p><strong>Environment:</strong> {{ alert.environment }}</p>
                        {% endif %}
                    </div>

                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
                        <h3 style="margin-top: 0;">Description</h3>
                        <p>{{ alert.description }}</p>
                        {% if step.message %}
                        <p><strong>Escalation:</strong> {{ step.message }}</p>
                        {% endif %}
                    </div>

                    {% if alert.labels %}
                    <div style="margin-bottom: 20px;">
                        <h3>Labels</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            {% for key, value in alert.labels.items() %}
                            <tr>
                                <td style="padding: 5px; border: 1px solid #ddd; font-weight: bold;">{{ key }}</td>
                                <td style="padding: 5px; border: 1px solid #ddd;">{{ value }}</td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                    {% endif %}

                    {% if alert.runbook_url %}
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="{{ alert.runbook_url }}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block;">View Runbook</a>
                    </div>
                    {% endif %}
                </div>

                <div style="text-align: center; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px;">
                    <p>This alert was generated at {{ timestamp }}</p>
                </div>
            </div>
        </body>
        </html>
        """

        severity_colors = {
            "info": "#17a2b8",
            "warning": "#ffc107",
            "critical": "#dc3545",
            "emergency": "#721c24",
        }

        return jinja2.Template(template_str).render(
            alert=alert,
            severity_color=severity_colors.get(alert.severity.value, "#6c757d"),
        )

    def _get_slack_color(self, severity: AlertSeverity) -> str:
        """Get Slack color for severity"""
        colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9500",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#8b0000",
        }
        return colors.get(severity, "#808080")

    def _get_pagerduty_severity(self, severity: AlertSeverity) -> str:
        """Get PagerDuty severity for alert"""
        mapping = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.EMERGENCY: "critical",
        }
        return mapping.get(severity, "error")

    def _format_duration(self, start: datetime, end: Optional[datetime]) -> str:
        """Format duration between timestamps"""
        end = end or datetime.utcnow()
        duration = end - start

        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def _record_notification(
        self,
        alert: Alert,
        channel: NotificationChannel,
        step: Dict[str, Any],
        success: bool = True,
    ):
        """Record notification in history"""
        notification = {
            "alert_id": alert.id,
            "alert_name": alert.name,
            "channel": channel.value,
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "step": step,
            "severity": alert.severity.value,
        }

        self.notification_history.append(notification)

        # Keep only last 1000 notifications
        if len(self.notification_history) > 1000:
            self.notification_history = self.notification_history[-1000:]

    def _record_alert_metrics(self, alert: Alert):
        """Record alert metrics"""
        # Record to business metrics
        business_metrics.increment_counter(
            "alerts_total",
            {
                "severity": alert.severity.value,
                "status": alert.status.value,
                "service": alert.service or "unknown",
            },
        )

        if alert.status == AlertStatus.FIRING:
            business_metrics.increment_counter(
                "alerts_active",
                {
                    "severity": alert.severity.value,
                    "service": alert.service or "unknown",
                },
            )

    def get_active_alerts(
        self, severity: Optional[AlertSeverity] = None, service: Optional[str] = None
    ) -> List[Alert]:
        """Get active alerts with optional filtering"""
        alerts = list(self.active_alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if service:
            alerts = [a for a in alerts if a.service == service]

        return alerts

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics"""
        total_active = len(self.active_alerts)

        severity_counts = {}
        for alert in self.active_alerts.values():
            severity = alert.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        recent_notifications = [
            n
            for n in self.notification_history
            if datetime.fromisoformat(n["timestamp"])
            > datetime.utcnow() - timedelta(hours=24)
        ]

        return {
            "total_active_alerts": total_active,
            "severity_breakdown": severity_counts,
            "notifications_last_24h": len(recent_notifications),
            "last_updated": datetime.utcnow().isoformat(),
        }


# Global alert manager instance
alert_manager = AlertManager()


# Convenience functions
async def handle_prometheus_alert(alert_data: Dict[str, Any]) -> Alert:
    """Handle Prometheus alert"""
    return await alert_manager.process_alert(alert_data)


def get_active_alerts_count() -> int:
    """Get count of active alerts"""
    return len(alert_manager.active_alerts)


def get_critical_alerts_count() -> int:
    """Get count of critical alerts"""
    return len(
        [
            a
            for a in alert_manager.active_alerts.values()
            if a.severity == AlertSeverity.CRITICAL
        ]
    )
