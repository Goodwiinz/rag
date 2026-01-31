"""
Security Monitoring and Alerting System
Real-time security monitoring, threat detection, and automated response
"""

import asyncio
import json
import logging
import smtplib
import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MimeMultipart
from email.mime.text import MimeText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import psycopg2
import redis
import requests
import yaml
from jinja2 import Template
from psycopg2 import sql

from src.core.config import settings

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatLevel(Enum):
    SAFE = "safe"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    id: str
    type: str
    severity: AlertSeverity
    timestamp: datetime
    source_ip: str
    user_id: Optional[str]
    details: Dict[str, Any]
    threat_indicators: List[str]
    resolved: bool = False
    response_actions: List[str] = None

    def __post_init__(self):
        if self.response_actions is None:
            self.response_actions = []


@dataclass
class SecurityAlert:
    id: str
    title: str
    description: str
    severity: AlertSeverity
    events: List[SecurityEvent]
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class ThreatDetectionRule:
    """Base class for threat detection rules"""

    def __init__(self, name: str, severity: AlertSeverity):
        self.name = name
        self.severity = severity
        self.enabled = True

    def evaluate(self, events: List[SecurityEvent]) -> List[SecurityAlert]:
        """Evaluate events and generate alerts"""
        raise NotImplementedError


class BruteForceRule(ThreatDetectionRule):
    """Detect brute force attacks"""

    def __init__(self):
        super().__init__("brute_force_detection", AlertSeverity.HIGH)
        self.failed_attempts_threshold = 5
        self.time_window_minutes = 15

    def evaluate(self, events: List[SecurityEvent]) -> List[SecurityAlert]:
        alerts = []

        # Group events by IP and user
        ip_events = defaultdict(list)
        user_events = defaultdict(list)

        for event in events:
            if event.type == "auth_failure":
                ip_events[event.source_ip].append(event)
                if event.user_id:
                    user_events[event.user_id].append(event)

        # Check IP-based brute force
        for ip, ip_event_list in ip_events.items():
            if len(ip_event_list) >= self.failed_attempts_threshold:
                # Check if attempts are within time window
                recent_events = [
                    e
                    for e in ip_event_list
                    if e.timestamp
                    > datetime.utcnow() - timedelta(minutes=self.time_window_minutes)
                ]

                if len(recent_events) >= self.failed_attempts_threshold:
                    alert = SecurityAlert(
                        id=f"brute_force_ip_{int(time.time())}",
                        title=f"Brute Force Attack Detected from {ip}",
                        description=f"Multiple failed authentication attempts from IP {ip}",
                        severity=self.severity,
                        events=recent_events,
                        created_at=datetime.utcnow(),
                    )
                    alerts.append(alert)

        # Check user-based brute force
        for user_id, user_event_list in user_events.items():
            if len(user_event_list) >= self.failed_attempts_threshold:
                recent_events = [
                    e
                    for e in user_event_list
                    if e.timestamp
                    > datetime.utcnow() - timedelta(minutes=self.time_window_minutes)
                ]

                if len(recent_events) >= self.failed_attempts_threshold:
                    alert = SecurityAlert(
                        id=f"brute_force_user_{int(time.time())}",
                        title=f"Brute Force Attack on User {user_id}",
                        description=f"Multiple failed authentication attempts for user {user_id}",
                        severity=self.severity,
                        events=recent_events,
                        created_at=datetime.utcnow(),
                    )
                    alerts.append(alert)

        return alerts


class SuspiciousActivityRule(ThreatDetectionRule):
    """Detect suspicious user behavior"""

    def __init__(self):
        super().__init__("suspicious_activity_detection", AlertSeverity.MEDIUM)
        self.unusual_patterns = {
            "multiple_failed_logins": 3,
            "rapid_api_calls": 100,
            "unusual_access_times": True,
            "multiple_device_access": True,
        }

    def evaluate(self, events: List[SecurityEvent]) -> List[SecurityAlert]:
        alerts = []

        # Group events by user
        user_events = defaultdict(list)
        for event in events:
            if event.user_id:
                user_events[event.user_id].append(event)

        # Analyze each user's activity
        for user_id, user_event_list in user_events.items():
            # Check for rapid API calls
            api_events = [e for e in user_event_list if e.type == "api_call"]
            if len(api_events) > self.unusual_patterns["rapid_api_calls"]:
                time_span = max(e.timestamp for e in api_events) - min(
                    e.timestamp for e in api_events
                )
                if time_span < timedelta(minutes=1):
                    alert = SecurityAlert(
                        id=f"rapid_api_{user_id}_{int(time.time())}",
                        title=f"Suspicious API Activity - User {user_id}",
                        description=f"Unusual number of API calls from user {user_id}",
                        severity=self.severity,
                        events=api_events,
                        created_at=datetime.utcnow(),
                    )
                    alerts.append(alert)

            # Check for unusual access times (2 AM - 4 AM)
            night_events = [e for e in user_event_list if 2 <= e.timestamp.hour <= 4]
            if len(night_events) > 5:  # Threshold for unusual night activity
                alert = SecurityAlert(
                    id=f"night_activity_{user_id}_{int(time.time())}",
                    title=f"Unusual Access Time - User {user_id}",
                    description=f"Unusual access pattern detected during night hours for user {user_id}",
                    severity=AlertSeverity.LOW,
                    events=night_events,
                    created_at=datetime.utcnow(),
                )
                alerts.append(alert)

        return alerts


class DataExfiltrationRule(ThreatDetectionRule):
    """Detect potential data exfiltration"""

    def __init__(self):
        super().__init__("data_exfiltration_detection", AlertSeverity.CRITICAL)
        self.download_threshold = 1000  # MB
        self.api_export_threshold = 100
        self.time_window_hours = 1

    def evaluate(self, events: List[SecurityEvent]) -> List[SecurityAlert]:
        alerts = []

        # Group events by user
        user_events = defaultdict(list)
        for event in events:
            if event.user_id and event.type in [
                "file_download",
                "data_export",
                "bulk_api_call",
            ]:
                user_events[event.user_id].append(event)

        for user_id, user_event_list in user_events.items():
            # Calculate total data downloaded
            total_size = sum(
                e.details.get("file_size", 0) + e.details.get("record_count", 0) * 0.001
                for e in user_event_list
            )

            if total_size > self.download_threshold:
                alert = SecurityAlert(
                    id=f"data_exfil_{user_id}_{int(time.time())}",
                    title=f"Potential Data Exfiltration - User {user_id}",
                    description=f"Large data download detected from user {user_id}: {total_size:.2f} MB",
                    severity=self.severity,
                    events=user_event_list,
                    created_at=datetime.utcnow(),
                )
                alerts.append(alert)

        return alerts


class SecurityAlertManager:
    """Manages security alerts and notifications"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.db_connection = self._get_db_connection()
        self.detection_rules = [
            BruteForceRule(),
            SuspiciousActivityRule(),
            DataExfiltrationRule(),
        ]
        self.notification_channels = []
        self.auto_response_enabled = True

        # Load configuration
        self.config = self._load_config()

        # Setup notification channels
        self._setup_notification_channels()

    def _get_db_connection(self):
        """Get database connection for logging"""
        try:
            return psycopg2.connect(settings.DATABASE_URL)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None

    def _load_config(self) -> Dict[str, Any]:
        """Load security monitoring configuration"""
        default_config = {
            "alert_retention_days": 30,
            "event_retention_days": 7,
            "auto_response_enabled": True,
            "notification_channels": {
                "email": {
                    "enabled": True,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "recipients": ["security@company.com"],
                },
                "slack": {"enabled": False, "webhook_url": ""},
                "pagerduty": {"enabled": False, "integration_key": ""},
            },
            "response_actions": {
                "block_ip": True,
                "lock_account": True,
                "require_mfa": True,
            },
        }

        try:
            # Try to load from file
            with open("/etc/rag/security_monitoring.yml", "r") as f:
                file_config = yaml.safe_load(f)
                default_config.update(file_config)
        except FileNotFoundError:
            logger.warning("Security monitoring config file not found, using defaults")

        return default_config

    def _setup_notification_channels(self):
        """Setup notification channels based on configuration"""
        if self.config["notification_channels"]["email"]["enabled"]:
            self.notification_channels.append(EmailNotifier(self.config))

        if self.config["notification_channels"]["slack"]["enabled"]:
            self.notification_channels.append(SlackNotifier(self.config))

        if self.config["notification_channels"]["pagerduty"]["enabled"]:
            self.notification_channels.append(PagerDutyNotifier(self.config))

    async def process_security_event(self, event: SecurityEvent) -> None:
        """Process a single security event"""
        # Store event
        await self._store_security_event(event)

        # Get recent events for analysis
        recent_events = await self._get_recent_events(minutes=60)

        # Run detection rules
        for rule in self.detection_rules:
            if rule.enabled:
                try:
                    alerts = rule.evaluate(recent_events)
                    for alert in alerts:
                        await self._handle_alert(alert)
                except Exception as e:
                    logger.error(f"Error in detection rule {rule.name}: {e}")

    async def _store_security_event(self, event: SecurityEvent) -> None:
        """Store security event in database and Redis"""
        # Store in Redis for quick access
        event_key = f"security_event:{event.id}"
        event_data = {
            "id": event.id,
            "type": event.type,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "source_ip": event.source_ip,
            "user_id": event.user_id,
            "details": json.dumps(event.details),
            "threat_indicators": json.dumps(event.threat_indicators),
        }

        self.redis.hmset(event_key, event_data)
        self.redis.expire(event_key, 7 * 24 * 3600)  # 7 days

        # Store in database for long-term storage
        if self.db_connection:
            try:
                with self.db_connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO security_events
                        (id, type, severity, timestamp, source_ip, user_id, details, threat_indicators)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            event.id,
                            event.type,
                            event.severity.value,
                            event.timestamp,
                            event.source_ip,
                            event.user_id,
                            json.dumps(event.details),
                            json.dumps(event.threat_indicators),
                        ),
                    )
                self.db_connection.commit()
            except Exception as e:
                logger.error(f"Failed to store security event in database: {e}")

    async def _get_recent_events(self, minutes: int = 60) -> List[SecurityEvent]:
        """Get recent security events"""
        events = []

        # Get events from Redis
        pattern = "security_event:*"
        keys = self.redis.keys(pattern)

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        for key in keys:
            try:
                event_data = self.redis.hgetall(key)
                if event_data:
                    timestamp = datetime.fromisoformat(event_data["timestamp"])
                    if timestamp > cutoff_time:
                        event = SecurityEvent(
                            id=event_data["id"],
                            type=event_data["type"],
                            severity=AlertSeverity(event_data["severity"]),
                            timestamp=timestamp,
                            source_ip=event_data["source_ip"],
                            user_id=event_data.get("user_id"),
                            details=json.loads(event_data["details"]),
                            threat_indicators=json.loads(
                                event_data["threat_indicators"]
                            ),
                        )
                        events.append(event)
            except Exception as e:
                logger.error(f"Error parsing security event from Redis: {e}")

        return sorted(events, key=lambda x: x.timestamp)

    async def _handle_alert(self, alert: SecurityAlert) -> None:
        """Handle security alert"""
        # Store alert
        await self._store_alert(alert)

        # Send notifications
        await self._send_notifications(alert)

        # Execute auto-response actions
        if self.auto_response_enabled:
            await self._execute_response_actions(alert)

    async def _store_alert(self, alert: SecurityAlert) -> None:
        """Store security alert"""
        alert_key = f"security_alert:{alert.id}"
        alert_data = {
            "id": alert.id,
            "title": alert.title,
            "description": alert.description,
            "severity": alert.severity.value,
            "created_at": alert.created_at.isoformat(),
            "acknowledged": str(alert.acknowledged),
            "event_ids": json.dumps([e.id for e in alert.events]),
        }

        self.redis.hmset(alert_key, alert_data)
        self.redis.expire(alert_key, 30 * 24 * 3600)  # 30 days

        # Add to active alerts list
        self.redis.lpush("active_alerts", alert.id)
        self.redis.expire("active_alerts", 30 * 24 * 3600)

    async def _send_notifications(self, alert: SecurityAlert) -> None:
        """Send alert notifications"""
        for notifier in self.notification_channels:
            try:
                await notifier.send_alert(alert)
            except Exception as e:
                logger.error(
                    f"Failed to send alert via {notifier.__class__.__name__}: {e}"
                )

    async def _execute_response_actions(self, alert: SecurityAlert) -> None:
        """Execute automatic response actions"""
        if alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
            # Block malicious IPs
            source_ips = list(set(event.source_ip for event in alert.events))
            for ip in source_ips:
                await self._block_ip(
                    ip, f"Auto-block due to security alert: {alert.id}"
                )

            # Lock user accounts if suspicious
            user_ids = list(
                set(event.user_id for event in alert.events if event.user_id)
            )
            for user_id in user_ids:
                await self._lock_user_account(
                    user_id, f"Auto-lock due to security alert: {alert.id}"
                )

    async def _block_ip(self, ip: str, reason: str) -> None:
        """Block IP address"""
        block_key = f"blocked_ip:{ip}"
        self.redis.setex(block_key, 24 * 3600, reason)  # Block for 24 hours

        logger.warning(f"IP {ip} blocked: {reason}")

    async def _lock_user_account(self, user_id: str, reason: str) -> None:
        """Lock user account"""
        lock_key = f"locked_user:{user_id}"
        self.redis.setex(lock_key, 24 * 3600, reason)  # Lock for 24 hours

        logger.warning(f"User {user_id} account locked: {reason}")

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge security alert"""
        alert_key = f"security_alert:{alert_id}"

        if self.redis.exists(alert_key):
            self.redis.hset(alert_key, "acknowledged", "true")
            self.redis.hset(alert_key, "acknowledged_by", acknowledged_by)
            self.redis.hset(alert_key, "acknowledged_at", datetime.utcnow().isoformat())
            return True

        return False

    async def resolve_alert(self, alert_id: str, resolved_by: str) -> bool:
        """Resolve security alert"""
        alert_key = f"security_alert:{alert_id}"

        if self.redis.exists(alert_key):
            self.redis.hset(alert_key, "resolved", "true")
            self.redis.hset(alert_key, "resolved_by", resolved_by)
            self.redis.hset(alert_key, "resolved_at", datetime.utcnow().isoformat())

            # Remove from active alerts
            self.redis.lrem("active_alerts", 1, alert_id)
            return True

        return False

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active security alerts"""
        alert_ids = self.redis.lrange("active_alerts", 0, -1)
        alerts = []

        for alert_id in alert_ids:
            alert_key = f"security_alert:{alert_id.decode()}"
            alert_data = self.redis.hgetall(alert_key)
            if alert_data:
                alerts.append(
                    {
                        k.decode()
                        if isinstance(k, bytes)
                        else k: v.decode()
                        if isinstance(v, bytes)
                        else v
                        for k, v in alert_data.items()
                    }
                )

        return alerts

    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics"""
        # Count events by type and severity
        event_metrics = defaultdict(lambda: defaultdict(int))

        pattern = "security_event:*"
        keys = self.redis.keys(pattern)

        for key in keys:
            try:
                event_data = self.redis.hgetall(key)
                if event_data:
                    event_type = event_data.get("type", "unknown").decode()
                    severity = event_data.get("severity", "unknown").decode()
                    event_metrics[event_type][severity] += 1
            except Exception as e:
                logger.error(f"Error parsing event metrics: {e}")

        # Count active alerts
        active_alerts_count = len(self.redis.lrange("active_alerts", 0, -1))

        # Get threat level
        critical_alerts = sum(
            1
            for alert in self.get_active_alerts()
            if alert.get("severity") == "critical"
        )

        if critical_alerts > 0:
            threat_level = ThreatLevel.CRITICAL
        elif active_alerts_count > 10:
            threat_level = ThreatLevel.HIGH
        elif active_alerts_count > 5:
            threat_level = ThreatLevel.ELEVATED
        else:
            threat_level = ThreatLevel.SAFE

        return {
            "threat_level": threat_level.value,
            "active_alerts": active_alerts_count,
            "event_metrics": dict(event_metrics),
            "blocked_ips": len(self.redis.keys("blocked_ip:*")),
            "locked_users": len(self.redis.keys("locked_user:*")),
        }


class NotificationChannel:
    """Base class for notification channels"""

    async def send_alert(self, alert: SecurityAlert) -> None:
        """Send alert notification"""
        raise NotImplementedError


class EmailNotifier(NotificationChannel):
    """Email notification channel"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.smtp_config = config["notification_channels"]["email"]

    async def send_alert(self, alert: SecurityAlert) -> None:
        """Send email alert"""
        try:
            msg = MimeMultipart()
            msg["From"] = self.smtp_config.get("sender", "security@rag-system.com")
            msg["To"] = ", ".join(self.smtp_config["recipients"])
            msg["Subject"] = f"[SECURITY ALERT] {alert.title}"

            # Create email body
            template = Template(
                """
            Security Alert: {{ alert.title }}
            Severity: {{ alert.severity.value.upper() }}
            Time: {{ alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') }}

            Description:
            {{ alert.description }}

            Events:
            {% for event in alert.events %}
            - {{ event.type }} from {{ event.source_ip }} at {{ event.timestamp.strftime('%H:%M:%S') }}
            {% endfor %}

            Immediate action required.
            """
            )

            body = template.render(alert=alert)
            msg.attach(MimeText(body, "plain"))

            # Send email
            server = smtplib.SMTP(
                self.smtp_config["smtp_server"], self.smtp_config["smtp_port"]
            )
            server.starttls()
            server.login(self.smtp_config["username"], self.smtp_config["password"])
            server.send_message(msg)
            server.quit()

            logger.info(f"Email alert sent for {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")


class SlackNotifier(NotificationChannel):
    """Slack notification channel"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.webhook_url = config["notification_channels"]["slack"]["webhook_url"]

    async def send_alert(self, alert: SecurityAlert) -> None:
        """Send Slack alert"""
        try:
            color = {
                AlertSeverity.LOW: "good",
                AlertSeverity.MEDIUM: "warning",
                AlertSeverity.HIGH: "danger",
                AlertSeverity.CRITICAL: "#FF0000",
            }.get(alert.severity, "warning")

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 Security Alert: {alert.title}",
                        "text": alert.description,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True,
                            },
                            {
                                "title": "Time",
                                "value": alert.created_at.strftime(
                                    "%Y-%m-%d %H:%M:%S UTC"
                                ),
                                "short": True,
                            },
                            {
                                "title": "Events Count",
                                "value": str(len(alert.events)),
                                "short": True,
                            },
                            {"title": "Alert ID", "value": alert.id, "short": True},
                        ],
                        "footer": "RAG Security System",
                        "ts": int(alert.created_at.timestamp()),
                    }
                ]
            }

            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()

            logger.info(f"Slack alert sent for {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")


class PagerDutyNotifier(NotificationChannel):
    """PagerDuty notification channel"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.integration_key = config["notification_channels"]["pagerduty"][
            "integration_key"
        ]

    async def send_alert(self, alert: SecurityAlert) -> None:
        """Send PagerDuty alert"""
        if alert.severity not in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
            return  # Only send high/critical alerts

        try:
            payload = {
                "routing_key": self.integration_key,
                "event_action": "trigger",
                "payload": {
                    "summary": alert.title,
                    "source": "RAG Security System",
                    "severity": "critical"
                    if alert.severity == AlertSeverity.CRITICAL
                    else "error",
                    "timestamp": alert.created_at.isoformat(),
                    "component": "Security Monitoring",
                    "group": "Security Alerts",
                    "class": alert.type,
                    "custom_details": {
                        "description": alert.description,
                        "events_count": len(alert.events),
                        "alert_id": alert.id,
                    },
                },
            }

            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            logger.info(f"PagerDuty alert sent for {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")


class SecurityMonitoringService:
    """Main security monitoring service"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.alert_manager = SecurityAlertManager(self.redis_client)
        self.running = False
        self.monitor_thread = None

    async def start_monitoring(self):
        """Start security monitoring service"""
        self.running = True

        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitor_thread.start()

        logger.info("Security monitoring service started")

    def stop_monitoring(self):
        """Stop security monitoring service"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Security monitoring service stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Process any pending security events from Redis
                self._process_pending_events()

                # Check for expired blocks and locks
                self._cleanup_expired_blocks()

                # Generate security metrics
                self._update_security_metrics()

                time.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait longer on error

    def _process_pending_events(self):
        """Process pending security events"""
        try:
            # Get events from processing queue
            events = self.redis.lrange("security_event_queue", 0, 10)

            for event_data in events:
                try:
                    event_dict = json.loads(event_data)
                    event = SecurityEvent(**event_dict)

                    # Process event
                    asyncio.run(self.alert_manager.process_security_event(event))

                    # Remove from queue
                    self.redis.lrem("security_event_queue", 1, event_data)

                except Exception as e:
                    logger.error(f"Error processing security event: {e}")

        except Exception as e:
            logger.error(f"Error processing pending events: {e}")

    def _cleanup_expired_blocks(self):
        """Clean up expired IP blocks and user locks"""
        try:
            # Check for expired IP blocks
            blocked_ips = self.redis.keys("blocked_ip:*")
            for ip_key in blocked_ips:
                if self.redis.ttl(ip_key) == -1:  # No expiry set
                    self.redis.expire(ip_key, 24 * 3600)  # Set 24 hour expiry

            # Check for expired user locks
            locked_users = self.redis.keys("locked_user:*")
            for user_key in locked_users:
                if self.redis.ttl(user_key) == -1:  # No expiry set
                    self.redis.expire(user_key, 24 * 3600)  # Set 24 hour expiry

        except Exception as e:
            logger.error(f"Error cleaning up expired blocks: {e}")

    def _update_security_metrics(self):
        """Update security metrics"""
        try:
            metrics = self.alert_manager.get_security_metrics()

            # Store metrics in Redis
            metrics_key = "security_metrics"
            self.redis.hmset(metrics_key, metrics)
            self.redis.expire(metrics_key, 3600)  # 1 hour expiry

        except Exception as e:
            logger.error(f"Error updating security metrics: {e}")

    async def log_security_event(
        self,
        event_type: str,
        source_ip: str,
        user_id: Optional[str] = None,
        details: Dict[str, Any] = None,
        threat_indicators: List[str] = None,
    ) -> str:
        """Log a security event"""
        event = SecurityEvent(
            id=f"event_{int(time.time())}_{source_ip}_{event_type}",
            type=event_type,
            severity=AlertSeverity.MEDIUM,  # Default severity
            timestamp=datetime.utcnow(),
            source_ip=source_ip,
            user_id=user_id,
            details=details or {},
            threat_indicators=threat_indicators or [],
        )

        # Add to processing queue
        self.redis.lpush("security_event_queue", json.dumps(asdict(event)))

        return event.id


# Global security monitoring service instance
security_monitoring_service = SecurityMonitoringService()
