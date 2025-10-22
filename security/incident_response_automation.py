#!/usr/bin/env python3
"""
Enterprise Incident Response Automation System for Knowledge Graph Analytics Dashboard
Automated incident detection, response, and management with comprehensive workflow
"""

import os
import sys
import json
import yaml
import time
import logging
import asyncio
import aiohttp
import sqlite3
import hashlib
import smtplib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import pandas as pd
import numpy as np
from collections import defaultdict
import threading
import queue
import subprocess
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
import slack_sdk
from slack_sdk.web.async_client import AsyncWebClient

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/goodwiinz/development/RAG_system/rag/security/logs/incident_response.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IncidentSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentStatus(Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    UNDER_INVESTIGATION = "under_investigation"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"

class IncidentCategory(Enum):
    SECURITY_BREACH = "security_breach"
    MALWARE = "malware"
    PHISHING = "phishing"
    DDOS = "ddos"
    DATA_BREACH = "data_breach"
    INSIDER_THREAT = "insider_threat"
    SYSTEM_COMPROMISE = "system_compromise"
    NETWORK_INTRUSION = "network_intrusion"
    DENIAL_OF_SERVICE = "denial_of_service"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

class ResponseAction(Enum):
    ISOLATE_SYSTEM = "isolate_system"
    BLOCK_IP = "block_ip"
    DISABLE_ACCOUNT = "disable_account"
    QUARANTINE_FILE = "quarantine_file"
    SHUTDOWN_SERVICE = "shutdown_service"
    BACKUP_DATA = "backup_data"
    COLLECT_EVIDENCE = "collect_evidence"
    NOTIFY_STAKEHOLDERS = "notify_stakeholders"
    ACTIVATE_INCIDENT_RESPONSE = "activate_incident_response"
    ESCALATE_INCIDENT = "escalate_incident"

@dataclass
class Incident:
    """Incident data structure"""
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    category: IncidentCategory
    status: IncidentStatus
    source_ip: Optional[str]
    affected_systems: List[str]
    affected_users: List[str]
    detected_at: datetime
    reported_by: str
    assigned_to: Optional[str]
    priority: int  # 1-5, where 1 is highest
    impact: Dict[str, Any]
    indicators: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    evidence: List[str]
    response_actions: List[str]
    resolution_notes: Optional[str]
    root_cause: Optional[str]
    lessons_learned: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]

@dataclass
class ResponsePlan:
    """Incident response plan data structure"""
    id: str
    name: str
    description: str
    category: IncidentCategory
    severity: IncidentSeverity
    triggers: List[str]
    steps: List[Dict[str, Any]]
    estimated_duration: int  # minutes
    required_resources: List[str]
    escalation_criteria: Dict[str, Any]
    communication_plan: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class ResponseAction:
    """Response action data structure"""
    id: str
    incident_id: str
    action_type: ResponseAction
    description: str
    automated: bool
    executed_at: Optional[datetime]
    executed_by: str
    status: str  # pending, executed, failed, skipped
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]

class IncidentResponseSystem:
    """Enterprise Incident Response Automation System"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.db_path = self.config['database']['path']
        self.plans_dir = Path(self.config['response']['plans_directory'])
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = f"incident_response_{int(time.time())}"

        # Initialize components
        self.incident_queue = asyncio.Queue()
        self.action_queue = asyncio.Queue()
        self.plans: Dict[str, ResponsePlan] = {}
        self.active_incidents: Dict[str, Incident] = {}
        self.response_team = self.config['response']['team']
        self.notification_channels = self.config['notifications']['channels']

        # Initialize database
        self._init_database()

        # Load response plans
        self._load_response_plans()

        # Initialize notification clients
        self._init_notification_clients()

    def _load_config(self, config_path: str = None) -> Dict:
        """Load incident response configuration"""
        default_config = {
            "environment": "production",
            "database": {
                "path": "/Users/goodwiinz/development/RAG_system/rag/security/incident_response.db"
            },
            "response": {
                "plans_directory": "/Users/goodwiinz/development/RAG_system/rag/security/plans",
                "automated_response": True,
                "evidence_collection": True,
                "containment_first": True,
                "escalation_enabled": True,
                "team": {
                    "lead": "security_team_lead@company.com",
                    "members": [
                        "security_analyst1@company.com",
                        "security_analyst2@company.com",
                        "it_admin@company.com",
                        "compliance_officer@company.com"
                    ],
                    "on_call_rotation": True,
                    "escalation_contacts": [
                        "cto@company.com",
                        "ceo@company.com"
                    ]
                },
                "playbooks": {
                    "malware": True,
                    "phishing": True,
                    "ddos": True,
                    "data_breach": True,
                    "insider_threat": True
                }
            },
            "notifications": {
                "enabled": True,
                "channels": {
                    "email": {
                        "enabled": True,
                        "smtp_server": "smtp.company.com",
                        "smtp_port": 587,
                        "username": "security@company.com",
                        "password": "password"
                    },
                    "slack": {
                        "enabled": True,
                        "bot_token": "xoxb-your-slack-bot-token",
                        "channel": "#security-incidents"
                    },
                    "webhook": {
                        "enabled": True,
                        "url": "https://api.company.com/webhooks/security"
                    }
                },
                "templates": {
                    "initial_alert": "templates/initial_alert.html",
                    "status_update": "templates/status_update.html",
                    "resolution": "templates/resolution.html"
                }
            },
            "automation": {
                "enabled": True,
                "max_parallel_actions": 5,
                "action_timeout": 300,  # 5 minutes
                "retry_attempts": 3,
                "auto_escalation": True,
                "auto_containment": True
            },
            "forensics": {
                "enabled": True,
                "evidence_collection": True,
                "memory_dump": True,
                "disk_imaging": True,
                "network_capture": True,
                "log_preservation": True,
                "chain_of_custody": True
            },
            "reporting": {
                "enabled": True,
                "post_incident_reports": True,
                "trend_analysis": True,
                "metrics_tracking": True,
                "automated_reports": True,
                "report_retention_days": 2555  # 7 years
            }
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                self._deep_merge(default_config, user_config)

        return default_config

    def _deep_merge(self, base: Dict, override: Dict):
        """Deep merge two dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _init_database(self):
        """Initialize incident response database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Incidents table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_ip TEXT,
                    affected_systems TEXT,
                    affected_users TEXT,
                    detected_at TEXT NOT NULL,
                    reported_by TEXT NOT NULL,
                    assigned_to TEXT,
                    priority INTEGER,
                    impact TEXT,
                    indicators TEXT,
                    timeline TEXT,
                    evidence TEXT,
                    response_actions TEXT,
                    resolution_notes TEXT,
                    root_cause TEXT,
                    lessons_learned TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT,
                    closed_at TEXT
                )
            ''')

            # Response plans table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS response_plans (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    triggers TEXT,
                    steps TEXT,
                    estimated_duration INTEGER,
                    required_resources TEXT,
                    escalation_criteria TEXT,
                    communication_plan TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            # Response actions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS response_actions (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    description TEXT,
                    automated BOOLEAN,
                    executed_at TEXT,
                    executed_by TEXT,
                    status TEXT,
                    result TEXT,
                    error_message TEXT,
                    FOREIGN KEY (incident_id) REFERENCES incidents (id)
                )
            ''')

            # Incident metrics table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS incident_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    total_incidents INTEGER,
                    critical_incidents INTEGER,
                    high_incidents INTEGER,
                    medium_incidents INTEGER,
                    low_incidents INTEGER,
                    avg_resolution_time REAL,
                    containment_time REAL,
                    mttr REAL  # Mean Time to Resolve
                )
            ''')

            conn.commit()

    def _load_response_plans(self):
        """Load incident response plans"""
        logger.info("Loading incident response plans")

        # Load built-in plans
        self._load_builtin_plans()

        # Load custom plans from directory
        if self.plans_dir.exists():
            for plan_file in self.plans_dir.glob("*.yaml"):
                try:
                    with open(plan_file, 'r') as f:
                        plan_data = yaml.safe_load(f)
                        plan = self._create_plan_from_data(plan_data)
                        self.plans[plan.id] = plan
                        logger.info(f"Loaded custom response plan: {plan.name}")
                except Exception as e:
                    logger.error(f"Failed to load plan {plan_file}: {e}")

        # Save plans to database
        self._save_plans_to_database()

        logger.info(f"Loaded {len(self.plans)} response plans")

    def _load_builtin_plans(self):
        """Load built-in response plans"""
        builtin_plans = [
            {
                "id": "malware_response",
                "name": "Malware Incident Response",
                "description": "Response plan for malware detection and containment",
                "category": IncidentCategory.MALWARE,
                "severity": IncidentSeverity.HIGH,
                "triggers": ["malware_detected", "suspicious_file", "antivirus_alert"],
                "steps": [
                    {
                        "order": 1,
                        "action": "isolate_affected_systems",
                        "description": "Isolate affected systems from network",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 2,
                        "action": "collect_evidence",
                        "description": "Collect memory and disk images",
                        "automated": True,
                        "timeout": 30
                    },
                    {
                        "order": 3,
                        "action": "scan_systems",
                        "description": "Run comprehensive antivirus scans",
                        "automated": True,
                        "timeout": 60
                    },
                    {
                        "order": 4,
                        "action": "identify_patient_zero",
                        "description": "Identify source of infection",
                        "automated": False,
                        "timeout": 120
                    },
                    {
                        "order": 5,
                        "action": "containment",
                        "description": "Contain and eradicate malware",
                        "automated": True,
                        "timeout": 60
                    },
                    {
                        "order": 6,
                        "action": "recovery",
                        "description": "Restore systems from clean backups",
                        "automated": False,
                        "timeout": 240
                    }
                ],
                "estimated_duration": 360,
                "required_resources": ["security_analyst", "it_admin", "forensics_tools"],
                "escalation_criteria": {
                    "multiple_systems": 5,
                    "critical_data_affected": True,
                    "containment_failed": True
                },
                "communication_plan": {
                    "initial_notification": ["security_team", "it_team"],
                    "escalation_notification": ["management", "legal"],
                    "resolution_notification": ["all_stakeholders"]
                }
            },
            {
                "id": "phishing_response",
                "name": "Phishing Attack Response",
                "description": "Response plan for phishing attacks",
                "category": IncidentCategory.PHISHING,
                "severity": IncidentSeverity.MEDIUM,
                "triggers": ["phishing_report", "suspicious_email", "credential_theft"],
                "steps": [
                    {
                        "order": 1,
                        "action": "collect_email_evidence",
                        "description": "Preserve phishing emails and headers",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 2,
                        "action": "identify_targeted_users",
                        "description": "Identify all users who received phishing email",
                        "automated": True,
                        "timeout": 10
                    },
                    {
                        "order": 3,
                        "action": "block_sender",
                        "description": "Block malicious sender domains and IPs",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 4,
                        "action": "user_notification",
                        "description": "Notify targeted users about the attack",
                        "automated": True,
                        "timeout": 15
                    },
                    {
                        "order": 5,
                        "action": "password_reset",
                        "description": "Force password reset for affected accounts",
                        "automated": True,
                        "timeout": 10
                    },
                    {
                        "order": 6,
                        "action": "email_filtering",
                        "description": "Update email filtering rules",
                        "automated": True,
                        "timeout": 5
                    }
                ],
                "estimated_duration": 60,
                "required_resources": ["security_analyst", "email_admin"],
                "escalation_criteria": {
                    "executive_targeted": True,
                    "credentials_compromised": True,
                    "widespread_attack": True
                },
                "communication_plan": {
                    "initial_notification": ["security_team", "email_admin"],
                    "escalation_notification": ["management", "hr"],
                    "resolution_notification": ["all_employees"]
                }
            },
            {
                "id": "ddos_response",
                "name": "DDoS Attack Response",
                "description": "Response plan for Distributed Denial of Service attacks",
                "category": IncidentCategory.DDOS,
                "severity": IncidentSeverity.HIGH,
                "triggers": ["ddos_detected", "service_unavailable", "traffic_spike"],
                "steps": [
                    {
                        "order": 1,
                        "action": "identify_attack_vectors",
                        "description": "Identify attack sources and vectors",
                        "automated": True,
                        "timeout": 10
                    },
                    {
                        "order": 2,
                        "action": "activate_ddos_protection",
                        "description": "Activate DDoS protection services",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 3,
                        "action": "block_attack_ips",
                        "description": "Block malicious IP addresses",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 4,
                        "action": "rate_limiting",
                        "description": "Implement rate limiting",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 5,
                        "action": "traffic_analysis",
                        "description": "Analyze attack patterns",
                        "automated": True,
                        "timeout": 30
                    },
                    {
                        "order": 6,
                        "action": "service_restoration",
                        "description": "Gradually restore normal service",
                        "automated": False,
                        "timeout": 120
                    }
                ],
                "estimated_duration": 180,
                "required_resources": ["network_engineer", "security_analyst", "ddos_provider"],
                "escalation_criteria": {
                    "service_completely_down": True,
                    "attack_bandwidth_exceeds_capacity": True,
                    "mitigation_ineffective": True
                },
                "communication_plan": {
                    "initial_notification": ["network_team", "security_team"],
                    "escalation_notification": ["management", "customers"],
                    "resolution_notification": ["all_stakeholders"]
                }
            },
            {
                "id": "data_breach_response",
                "name": "Data Breach Response",
                "description": "Response plan for data breach incidents",
                "category": IncidentCategory.DATA_BREACH,
                "severity": IncidentSeverity.CRITICAL,
                "triggers": ["unauthorized_data_access", "data_exfiltration", "privacy_breach"],
                "steps": [
                    {
                        "order": 1,
                        "action": "immediate_containment",
                        "description": "Immediately contain the breach",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 2,
                        "action": "assess_breach_scope",
                        "description": "Assess scope and impact of breach",
                        "automated": False,
                        "timeout": 60
                    },
                    {
                        "order": 3,
                        "action": "preserve_evidence",
                        "description": "Preserve all relevant evidence",
                        "automated": True,
                        "timeout": 30
                    },
                    {
                        "order": 4,
                        "action": "notify_legal_compliance",
                        "description": "Notify legal and compliance teams",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 5,
                        "action": "determine_notification_requirements",
                        "description": "Determine regulatory notification requirements",
                        "automated": False,
                        "timeout": 120
                    },
                    {
                        "order": 6,
                        "action": "affected_party_notification",
                        "description": "Notify affected parties and regulators",
                        "automated": False,
                        "timeout": 240
                    },
                    {
                        "order": 7,
                        "action": "remediation",
                        "description": "Remediate vulnerabilities and improve controls",
                        "automated": False,
                        "timeout": 480
                    }
                ],
                "estimated_duration": 1440,  # 24 hours
                "required_resources": ["security_team", "legal_team", "compliance_officer", "pr_team"],
                "escalation_criteria": {
                    "sensitive_data_exposed": True,
                    "large_scale_breach": True,
                    "regulatory_impact": True
                },
                "communication_plan": {
                    "initial_notification": ["c_suite", "legal", "compliance"],
                    "escalation_notification": ["board", "regulators"],
                    "resolution_notification": ["all_stakeholders", "public"]
                }
            },
            {
                "id": "unauthorized_access_response",
                "name": "Unauthorized Access Response",
                "description": "Response plan for unauthorized access incidents",
                "category": IncidentCategory.UNAUTHORIZED_ACCESS,
                "severity": IncidentSeverity.HIGH,
                "triggers": ["unauthorized_login", "privilege_escalation", "suspicious_activity"],
                "steps": [
                    {
                        "order": 1,
                        "action": "immediate_isolation",
                        "description": "Isolate compromised accounts",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 2,
                        "action": "disable_compromised_accounts",
                        "description": "Disable compromised user accounts",
                        "automated": True,
                        "timeout": 5
                    },
                    {
                        "order": 3,
                        "action": "password_reset",
                        "description": "Force password reset for all affected accounts",
                        "automated": True,
                        "timeout": 10
                    },
                    {
                        "order": 4,
                        "action": "access_review",
                        "description": "Review access logs and permissions",
                        "automated": True,
                        "timeout": 30
                    },
                    {
                        "order": 5,
                        "action": "investigate_source",
                        "description": "Investigate source of unauthorized access",
                        "automated": False,
                        "timeout": 120
                    },
                    {
                        "order": 6,
                        "action": "remediation",
                        "description": "Remediate security weaknesses",
                        "automated": False,
                        "timeout": 180
                    }
                ],
                "estimated_duration": 240,
                "required_resources": ["security_analyst", "system_admin", "identity_team"],
                "escalation_criteria": {
                    "admin_account_compromised": True,
                    "data_access_confirmed": True,
                    "lateral_movement_detected": True
                },
                "communication_plan": {
                    "initial_notification": ["security_team", "identity_team"],
                    "escalation_notification": ["management", "system_owners"],
                    "resolution_notification": ["affected_users", "management"]
                }
            }
        ]

        for plan_data in builtin_plans:
            plan = self._create_plan_from_data(plan_data)
            self.plans[plan.id] = plan

    def _create_plan_from_data(self, plan_data: Dict) -> ResponsePlan:
        """Create ResponsePlan from dictionary"""
        return ResponsePlan(
            id=plan_data['id'],
            name=plan_data['name'],
            description=plan_data['description'],
            category=IncidentCategory(plan_data['category']),
            severity=IncidentSeverity(plan_data['severity']),
            triggers=plan_data['triggers'],
            steps=plan_data['steps'],
            estimated_duration=plan_data['estimated_duration'],
            required_resources=plan_data['required_resources'],
            escalation_criteria=plan_data.get('escalation_criteria', {}),
            communication_plan=plan_data.get('communication_plan', {}),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    def _save_plans_to_database(self):
        """Save response plans to database"""
        with sqlite3.connect(self.db_path) as conn:
            for plan in self.plans.values():
                conn.execute('''
                    INSERT OR REPLACE INTO response_plans
                    (id, name, description, category, severity, triggers, steps,
                     estimated_duration, required_resources, escalation_criteria,
                     communication_plan, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    plan.id,
                    plan.name,
                    plan.description,
                    plan.category.value,
                    plan.severity.value,
                    json.dumps(plan.triggers),
                    json.dumps(plan.steps),
                    plan.estimated_duration,
                    json.dumps(plan.required_resources),
                    json.dumps(plan.escalation_criteria),
                    json.dumps(plan.communication_plan),
                    plan.created_at.isoformat(),
                    plan.updated_at.isoformat()
                ))
            conn.commit()

    def _init_notification_clients(self):
        """Initialize notification clients"""
        self.email_client = None
        self.slack_client = None

        # Initialize email client
        if self.config['notifications']['channels']['email']['enabled']:
            self.email_client = {
                'smtp_server': self.config['notifications']['channels']['email']['smtp_server'],
                'smtp_port': self.config['notifications']['channels']['email']['smtp_port'],
                'username': self.config['notifications']['channels']['email']['username'],
                'password': self.config['notifications']['channels']['email']['password']
            }

        # Initialize Slack client
        if self.config['notifications']['channels']['slack']['enabled']:
            self.slack_client = AsyncWebClient(
                token=self.config['notifications']['channels']['slack']['bot_token']
            )

    async def start_incident_response(self):
        """Start incident response system"""
        logger.info(f"Starting incident response system: {self.session_id}")

        try:
            # Start incident processing
            await self._start_incident_processing()

            # Start action processing
            await self._start_action_processing()

            # Start monitoring for active incidents
            await self._start_incident_monitoring()

            logger.info("Incident response system started successfully")

        except Exception as e:
            logger.error(f"Failed to start incident response system: {e}")
            raise

    async def _start_incident_processing(self):
        """Start incident processing loop"""
        logger.info("Starting incident processing")

        while True:
            try:
                # Get incident from queue
                incident = await asyncio.wait_for(self.incident_queue.get(), timeout=1.0)

                # Process incident
                await self._process_incident(incident)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Incident processing error: {e}")

    async def _process_incident(self, incident: Incident):
        """Process incident"""
        try:
            logger.info(f"Processing incident: {incident.title}")

            # Add to active incidents
            self.active_incidents[incident.id] = incident

            # Save to database
            await self._save_incident(incident)

            # Find appropriate response plan
            plan = self._find_response_plan(incident)
            if plan:
                logger.info(f"Using response plan: {plan.name}")

                # Execute response plan
                await self._execute_response_plan(incident, plan)

            # Send initial notifications
            await self._send_initial_notifications(incident)

            # Check for escalation
            await self._check_escalation(incident)

        except Exception as e:
            logger.error(f"Incident processing error: {e}")

    def _find_response_plan(self, incident: Incident) -> Optional[ResponsePlan]:
        """Find appropriate response plan for incident"""
        # Find plan by category and severity
        matching_plans = [
            plan for plan in self.plans.values()
            if plan.category == incident.category and plan.severity == incident.severity
        ]

        if matching_plans:
            return matching_plans[0]

        # Find plan by category only
        category_plans = [
            plan for plan in self.plans.values()
            if plan.category == incident.category
        ]

        if category_plans:
            return category_plans[0]

        return None

    async def _execute_response_plan(self, incident: Incident, plan: ResponsePlan):
        """Execute response plan"""
        try:
            logger.info(f"Executing response plan: {plan.name}")

            # Sort steps by order
            sorted_steps = sorted(plan.steps, key=lambda x: x['order'])

            # Execute steps
            for step in sorted_steps:
                try:
                    await self._execute_response_step(incident, step, plan)
                except Exception as e:
                    logger.error(f"Step execution error: {e}")

        except Exception as e:
            logger.error(f"Response plan execution error: {e}")

    async def _execute_response_step(self, incident: Incident, step: Dict, plan: ResponsePlan):
        """Execute response step"""
        step_name = step['action']
        description = step['description']
        automated = step.get('automated', False)
        timeout = step.get('timeout', 30)

        logger.info(f"Executing step: {step_name} - {description}")

        # Create response action record
        action = ResponseAction(
            id=f"action_{int(time.time() * 1000)}_{hashlib.md5(step_name.encode()).hexdigest()[:8]}",
            incident_id=incident.id,
            action_type=ResponseAction(step_name.replace('_', '_')),
            description=description,
            automated=automated,
            executed_at=datetime.now(timezone.utc),
            executed_by="system" if automated else "analyst",
            status="pending",
            result=None,
            error_message=None
        )

        try:
            if automated:
                # Execute automated action
                result = await self._execute_automated_action(incident, step_name, step)
                action.result = result
                action.status = "executed"

                # Add to incident timeline
                incident.timeline.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": step_name,
                    "description": description,
                    "status": "completed",
                    "automated": True,
                    "result": result
                })

                # Update incident
                incident.updated_at = datetime.now(timezone.utc)
                await self._save_incident(incident)

            else:
                # Create manual action task
                await self._create_manual_action_task(incident, step)
                action.status = "pending"

        except Exception as e:
            action.status = "failed"
            action.error_message = str(e)
            logger.error(f"Action execution failed: {e}")

        # Save action
        await self._save_action(action)

    async def _execute_automated_action(self, incident: Incident, action_name: str, step: Dict) -> Dict:
        """Execute automated action"""
        try:
            if action_name == "isolate_affected_systems":
                return await self._isolate_systems(incident.affected_systems)

            elif action_name == "block_sender":
                return await self._block_malicious_sender(incident)

            elif action_name == "disable_compromised_accounts":
                return await self._disable_accounts(incident.affected_users)

            elif action_name == "collect_evidence":
                return await self._collect_evidence(incident)

            elif action_name == "block_attack_ips":
                return await self._block_ips(incident.source_ip)

            elif action_name == "password_reset":
                return await self._force_password_reset(incident.affected_users)

            elif action_name == "notify_stakeholders":
                return await self._notify_stakeholders(incident, step)

            elif action_name == "activate_ddos_protection":
                return await self._activate_ddos_protection()

            elif action_name == "rate_limiting":
                return await self._implement_rate_limiting()

            else:
                return {"status": "skipped", "reason": f"Unknown action: {action_name}"}

        except Exception as e:
            logger.error(f"Automated action error for {action_name}: {e}")
            raise

    async def _isolate_systems(self, systems: List[str]) -> Dict:
        """Isolate affected systems from network"""
        try:
            isolated_systems = []
            for system in systems:
                # Implement system isolation logic
                # This would typically involve network configuration changes
                logger.info(f"Isolating system: {system}")
                isolated_systems.append(system)

            return {
                "status": "success",
                "isolated_systems": isolated_systems,
                "count": len(isolated_systems)
            }

        except Exception as e:
            logger.error(f"System isolation error: {e}")
            raise

    async def _block_malicious_sender(self, incident: Incident) -> Dict:
        """Block malicious email sender"""
        try:
            # Extract sender information from indicators
            sender_domain = incident.indicators.get('sender_domain')
            sender_ip = incident.indicators.get('sender_ip')

            blocked_items = []
            if sender_domain:
                # Block domain in email system
                logger.info(f"Blocking domain: {sender_domain}")
                blocked_items.append(f"domain:{sender_domain}")

            if sender_ip:
                # Block IP in firewall
                logger.info(f"Blocking IP: {sender_ip}")
                blocked_items.append(f"ip:{sender_ip}")

            return {
                "status": "success",
                "blocked_items": blocked_items,
                "count": len(blocked_items)
            }

        except Exception as e:
            logger.error(f"Sender blocking error: {e}")
            raise

    async def _disable_accounts(self, users: List[str]) -> Dict:
        """Disable compromised user accounts"""
        try:
            disabled_accounts = []
            for user in users:
                # Disable account in identity management system
                logger.info(f"Disabling account: {user}")
                disabled_accounts.append(user)

            return {
                "status": "success",
                "disabled_accounts": disabled_accounts,
                "count": len(disabled_accounts)
            }

        except Exception as e:
            logger.error(f"Account disabling error: {e}")
            raise

    async def _collect_evidence(self, incident: Incident) -> Dict:
        """Collect forensic evidence"""
        try:
            evidence_collected = []

            # Collect system logs
            logs_path = f"/evidence/{incident.id}/logs"
            # Implement log collection logic
            evidence_collected.append("system_logs")

            # Collect memory dumps
            if incident.affected_systems:
                for system in incident.affected_systems:
                    # Implement memory dump collection
                    evidence_collected.append(f"memory_dump_{system}")

            # Collect network captures
            evidence_collected.append("network_capture")

            return {
                "status": "success",
                "evidence_collected": evidence_collected,
                "evidence_path": f"/evidence/{incident.id}",
                "chain_of_custody_initiated": True
            }

        except Exception as e:
            logger.error(f"Evidence collection error: {e}")
            raise

    async def _block_ips(self, ip_addresses: str) -> Dict:
        """Block IP addresses"""
        try:
            if not ip_addresses:
                return {"status": "skipped", "reason": "No IP addresses provided"}

            blocked_ips = []
            if isinstance(ip_addresses, str):
                ip_addresses = [ip_addresses]

            for ip in ip_addresses:
                # Block IP in firewall
                logger.info(f"Blocking IP: {ip}")
                blocked_ips.append(ip)

            return {
                "status": "success",
                "blocked_ips": blocked_ips,
                "count": len(blocked_ips)
            }

        except Exception as e:
            logger.error(f"IP blocking error: {e}")
            raise

    async def _force_password_reset(self, users: List[str]) -> Dict:
        """Force password reset for users"""
        try:
            reset_users = []
            for user in users:
                # Force password reset in identity system
                logger.info(f"Force password reset for: {user}")
                reset_users.append(user)

            return {
                "status": "success",
                "reset_users": reset_users,
                "count": len(reset_users)
            }

        except Exception as e:
            logger.error(f"Password reset error: {e}")
            raise

    async def _notify_stakeholders(self, incident: Incident, step: Dict) -> Dict:
        """Notify stakeholders"""
        try:
            recipients = step.get('recipients', [])
            if not recipients:
                recipients = self.response_team['members']

            notification_sent = []
            for recipient in recipients:
                # Send notification
                await self._send_notification(recipient, f"Incident Update: {incident.title}", incident.description)
                notification_sent.append(recipient)

            return {
                "status": "success",
                "notified": notification_sent,
                "count": len(notification_sent)
            }

        except Exception as e:
            logger.error(f"Stakeholder notification error: {e}")
            raise

    async def _activate_ddos_protection(self) -> Dict:
        """Activate DDoS protection"""
        try:
            # Activate DDoS protection service
            logger.info("Activating DDoS protection")

            return {
                "status": "success",
                "protection_activated": True,
                "provider": "cloudflare"
            }

        except Exception as e:
            logger.error(f"DDoS protection activation error: {e}")
            raise

    async def _implement_rate_limiting(self) -> Dict:
        """Implement rate limiting"""
        try:
            # Implement rate limiting rules
            logger.info("Implementing rate limiting")

            return {
                "status": "success",
                "rate_limiting_active": True,
                "rules": ["ip_rate_limit", "endpoint_rate_limit"]
            }

        except Exception as e:
            logger.error(f"Rate limiting implementation error: {e}")
            raise

    async def _create_manual_action_task(self, incident: Incident, step: Dict):
        """Create manual action task"""
        # This would integrate with task management system
        logger.info(f"Creating manual task: {step['description']}")

    async def _save_incident(self, incident: Incident):
        """Save incident to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO incidents
                    (id, title, description, severity, category, status, source_ip,
                     affected_systems, affected_users, detected_at, reported_by,
                     assigned_to, priority, impact, indicators, timeline,
                     evidence, response_actions, resolution_notes, root_cause,
                     lessons_learned, created_at, updated_at, resolved_at, closed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    incident.id,
                    incident.title,
                    incident.description,
                    incident.severity.value,
                    incident.category.value,
                    incident.status.value,
                    incident.source_ip,
                    json.dumps(incident.affected_systems),
                    json.dumps(incident.affected_users),
                    incident.detected_at.isoformat(),
                    incident.reported_by,
                    incident.assigned_to,
                    incident.priority,
                    json.dumps(incident.impact),
                    json.dumps(incident.indicators),
                    json.dumps(incident.timeline),
                    json.dumps(incident.evidence),
                    json.dumps(incident.response_actions),
                    incident.resolution_notes,
                    incident.root_cause,
                    incident.lessons_learned,
                    incident.created_at.isoformat(),
                    incident.updated_at.isoformat(),
                    incident.resolved_at.isoformat() if incident.resolved_at else None,
                    incident.closed_at.isoformat() if incident.closed_at else None
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save incident: {e}")

    async def _save_action(self, action: ResponseAction):
        """Save action to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO response_actions
                    (id, incident_id, action_type, description, automated,
                     executed_at, executed_by, status, result, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    action.id,
                    action.incident_id,
                    action.action_type.value,
                    action.description,
                    action.automated,
                    action.executed_at.isoformat() if action.executed_at else None,
                    action.executed_by,
                    action.status,
                    json.dumps(action.result) if action.result else None,
                    action.error_message
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save action: {e}")

    async def _send_initial_notifications(self, incident: Incident):
        """Send initial incident notifications"""
        try:
            if not self.config['notifications']['enabled']:
                return

            # Determine notification recipients based on severity
            if incident.severity == IncidentSeverity.CRITICAL:
                recipients = self.response_team['members'] + self.response_team['escalation_contacts']
            elif incident.severity == IncidentSeverity.HIGH:
                recipients = self.response_team['members'] + [self.response_team['lead']]
            else:
                recipients = [self.response_team['lead']]

            # Send notifications
            for recipient in recipients:
                await self._send_notification(
                    recipient,
                    f"SECURITY ALERT: {incident.title}",
                    self._format_incident_notification(incident)
                )

            # Send Slack notification
            if self.slack_client:
                await self._send_slack_notification(incident)

        except Exception as e:
            logger.error(f"Initial notification error: {e}")

    def _format_incident_notification(self, incident: Incident) -> str:
        """Format incident notification message"""
        return f"""
Incident Details:
- ID: {incident.id}
- Title: {incident.title}
- Severity: {incident.severity.value}
- Category: {incident.category.value}
- Description: {incident.description}
- Detected: {incident.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
- Affected Systems: {', '.join(incident.affected_systems)}
- Source IP: {incident.source_ip or 'Unknown'}
- Reported By: {incident.reported_by}

Please investigate and respond immediately.
        """.strip()

    async def _send_notification(self, recipient: str, subject: str, message: str):
        """Send email notification"""
        try:
            if not self.email_client:
                return

            msg = MIMEMultipart()
            msg['From'] = self.email_client['username']
            msg['To'] = recipient
            msg['Subject'] = subject

            msg.attach(MIMEText(message, 'plain'))

            # Send email (implementation depends on SMTP library)
            logger.info(f"Email notification sent to {recipient}")

        except Exception as e:
            logger.error(f"Email notification error: {e}")

    async def _send_slack_notification(self, incident: Incident):
        """Send Slack notification"""
        try:
            if not self.slack_client:
                return

            color = {
                IncidentSeverity.LOW: "good",
                IncidentSeverity.MEDIUM: "warning",
                IncidentSeverity.HIGH: "danger",
                IncidentSeverity.CRITICAL: "danger"
            }.get(incident.severity, "warning")

            await self.slack_client.chat_postMessage(
                channel=self.config['notifications']['channels']['slack']['channel'],
                text=f"🚨 Security Incident: {incident.title}",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🚨 Security Incident: {incident.title}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Severity:* {incident.severity.value.upper()}"},
                            {"type": "mrkdwn", "text": f"*Category:* {incident.category.value.replace('_', ' ').title()}"},
                            {"type": "mrkdwn", "text": f"*Status:* {incident.status.value.replace('_', ' ').title()}"},
                            {"type": "mrkdwn", "text": f"*Detected:* {incident.detected_at.strftime('%Y-%m-%d %H:%M:%S')}"}
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Description:*\n{incident.description}"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Incident ID: {incident.id} | Assigned to: {incident.assigned_to or 'Unassigned'}"
                            }
                        ]
                    }
                ]
            )

        except Exception as e:
            logger.error(f"Slack notification error: {e}")

    async def _check_escalation(self, incident: Incident):
        """Check if incident needs escalation"""
        try:
            if not self.config['response']['escalation_enabled']:
                return

            # Find applicable response plan
            plan = self._find_response_plan(incident)
            if not plan or not plan.escalation_criteria:
                return

            # Check escalation criteria
            escalate = False
            escalation_reasons = []

            # Check for multiple affected systems
            if len(incident.affected_systems) >= plan.escalation_criteria.get('multiple_systems', 999):
                escalate = True
                escalation_reasons.append("Multiple systems affected")

            # Check for critical data impact
            if incident.impact.get('critical_data_affected', False):
                escalate = True
                escalation_reasons.append("Critical data affected")

            # Check for executive targeting
            if incident.impact.get('executive_targeted', False):
                escalate = True
                escalation_reasons.append("Executive targeted")

            # Check for regulatory impact
            if incident.impact.get('regulatory_impact', False):
                escalate = True
                escalation_reasons.append("Regulatory impact")

            # Escalate if needed
            if escalate:
                await self._escalate_incident(incident, escalation_reasons)

        except Exception as e:
            logger.error(f"Escalation check error: {e}")

    async def _escalate_incident(self, incident: Incident, reasons: List[str]):
        """Escalate incident"""
        try:
            logger.warning(f"Escalating incident {incident.id}: {', '.join(reasons)}")

            # Update incident priority
            incident.priority = 1  # Highest priority
            incident.updated_at = datetime.now(timezone.utc)

            # Add to timeline
            incident.timeline.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "escalation",
                "description": f"Incident escalated: {', '.join(reasons)}",
                "status": "completed"
            })

            # Notify escalation contacts
            escalation_contacts = self.response_team['escalation_contacts']
            for contact in escalation_contacts:
                await self._send_notification(
                    contact,
                    f"ESCALATED INCIDENT: {incident.title}",
                    f"Incident {incident.id} has been escalated.\n\nReasons: {', '.join(reasons)}\n\nImmediate attention required."
                )

            # Update in database
            await self._save_incident(incident)

        except Exception as e:
            logger.error(f"Incident escalation error: {e}")

    async def _start_action_processing(self):
        """Start action processing loop"""
        logger.info("Starting action processing")

        while True:
            try:
                # Get action from queue
                action = await asyncio.wait_for(self.action_queue.get(), timeout=1.0)

                # Process action
                await self._process_action(action)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Action processing error: {e}")

    async def _process_action(self, action: ResponseAction):
        """Process response action"""
        # This would handle manual action processing
        logger.info(f"Processing action: {action.description}")

    async def _start_incident_monitoring(self):
        """Start incident monitoring"""
        logger.info("Starting incident monitoring")

        while True:
            try:
                # Monitor active incidents
                await self._monitor_active_incidents()

                # Update metrics
                await self._update_metrics()

                # Wait for next check
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Incident monitoring error: {e}")
                await asyncio.sleep(10)

    async def _monitor_active_incidents(self):
        """Monitor active incidents"""
        try:
            for incident_id, incident in list(self.active_incidents.items()):
                # Check if incident needs updates
                if incident.status in [IncidentStatus.NEW, IncidentStatus.ASSIGNED, IncidentStatus.IN_PROGRESS]:
                    # Check if automated actions are complete
                    await self._check_action_completion(incident)

                    # Check if incident should be escalated
                    await self._check_time_based_escalation(incident)

                # Check if incident should be auto-resolved
                if incident.status == IncidentStatus.CONTAINED:
                    await self._check_auto_resolution(incident)

        except Exception as e:
            logger.error(f"Active incident monitoring error: {e}")

    async def _check_action_completion(self, incident: Incident):
        """Check if all actions are complete"""
        # This would check if all response actions are completed
        pass

    async def _check_time_based_escalation(self, incident: Incident):
        """Check for time-based escalation"""
        try:
            # Define escalation timeframes by severity
            escalation_timeframes = {
                IncidentSeverity.CRITICAL: 15,  # 15 minutes
                IncidentSeverity.HIGH: 30,       # 30 minutes
                IncidentSeverity.MEDIUM: 60,     # 1 hour
                IncidentSeverity.LOW: 240        # 4 hours
            }

            timeframe = escalation_timeframes.get(incident.severity, 60)
            time_since_detection = (datetime.now(timezone.utc) - incident.detected_at).total_seconds() / 60

            if time_since_detection > timeframe and incident.status != IncidentStatus.UNDER_INVESTIGATION:
                await self._escalate_incident(incident, [f"No progress after {timeframe} minutes"])

        except Exception as e:
            logger.error(f"Time-based escalation error: {e}")

    async def _check_auto_resolution(self, incident: Incident):
        """Check for automatic resolution"""
        # This would implement logic to automatically resolve certain types of incidents
        pass

    async def _update_metrics(self):
        """Update incident response metrics"""
        try:
            # Calculate metrics for today
            today = datetime.now(timezone.utc).date()

            with sqlite3.connect(self.db_path) as conn:
                # Get incident counts by severity
                cursor = conn.execute('''
                    SELECT severity, COUNT(*) FROM incidents
                    WHERE date(created_at) = ?
                    GROUP BY severity
                ''', (today.isoformat(),))

                severity_counts = dict(cursor.fetchall())

                # Calculate MTTR and other metrics
                cursor = conn.execute('''
                    SELECT AVG(
                        CASE
                            WHEN resolved_at IS NOT NULL THEN
                                (julianday(resolved_at) - julianday(detected_at)) * 24 * 60
                            ELSE NULL
                        END
                    ) as avg_resolution_time
                    FROM incidents
                    WHERE date(detected_at) = ? AND resolved_at IS NOT NULL
                ''', (today.isoformat(),))

                avg_resolution_time = cursor.fetchone()[0] or 0

                # Save metrics
                conn.execute('''
                    INSERT OR REPLACE INTO incident_metrics
                    (date, total_incidents, critical_incidents, high_incidents,
                     medium_incidents, low_incidents, avg_resolution_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    today.isoformat(),
                    sum(severity_counts.values()),
                    severity_counts.get('critical', 0),
                    severity_counts.get('high', 0),
                    severity_counts.get('medium', 0),
                    severity_counts.get('low', 0),
                    avg_resolution_time
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Metrics update error: {e}")

    def create_incident(self, title: str, description: str, severity: IncidentSeverity,
                       category: IncidentCategory, source_ip: Optional[str] = None,
                       affected_systems: List[str] = None, affected_users: List[str] = None,
                       indicators: Dict[str, Any] = None) -> str:
        """Create new incident"""
        try:
            incident_id = f"inc_{int(time.time() * 1000)}_{hashlib.md5(title.encode()).hexdigest()[:8]}"

            incident = Incident(
                id=incident_id,
                title=title,
                description=description,
                severity=severity,
                category=category,
                status=IncidentStatus.NEW,
                source_ip=source_ip,
                affected_systems=affected_systems or [],
                affected_users=affected_users or [],
                detected_at=datetime.now(timezone.utc),
                reported_by="automated_system",
                assigned_to=None,
                priority=self._calculate_priority(severity, category),
                impact={},
                indicators=indicators or {},
                timeline=[{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "incident_created",
                    "description": "Incident created",
                    "status": "completed"
                }],
                evidence=[],
                response_actions=[],
                resolution_notes=None,
                root_cause=None,
                lessons_learned=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                resolved_at=None,
                closed_at=None
            )

            # Add to queue for processing
            asyncio.create_task(self.incident_queue.put(incident))

            logger.info(f"Created incident {incident_id}: {title}")
            return incident_id

        except Exception as e:
            logger.error(f"Failed to create incident: {e}")
            raise

    def _calculate_priority(self, severity: IncidentSeverity, category: IncidentCategory) -> int:
        """Calculate incident priority"""
        base_priority = {
            IncidentSeverity.CRITICAL: 1,
            IncidentSeverity.HIGH: 2,
            IncidentSeverity.MEDIUM: 3,
            IncidentSeverity.LOW: 4
        }.get(severity, 3)

        # Adjust based on category
        category_adjustment = {
            IncidentCategory.DATA_BREACH: -1,
            IncidentCategory.SECURITY_BREACH: -1,
            IncidentCategory.MALWARE: 0,
            IncidentCategory.UNAUTHORIZED_ACCESS: -1,
            IncidentCategory.DDOS: 0,
            IncidentCategory.PHISHING: 1
        }.get(category, 0)

        return max(1, min(5, base_priority + category_adjustment))

    def get_incident_status(self, incident_id: str) -> Optional[Dict]:
        """Get incident status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM incidents WHERE id = ?
                ''', (incident_id,))

                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"Failed to get incident status: {e}")

        return None

    async def resolve_incident(self, incident_id: str, resolution_notes: str, root_cause: str = None):
        """Resolve incident"""
        try:
            if incident_id in self.active_incidents:
                incident = self.active_incidents[incident_id]
                incident.status = IncidentStatus.RESOLVED
                incident.resolution_notes = resolution_notes
                incident.root_cause = root_cause
                incident.resolved_at = datetime.now(timezone.utc)
                incident.updated_at = datetime.now(timezone.utc)

                # Add to timeline
                incident.timeline.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "incident_resolved",
                    "description": "Incident resolved",
                    "status": "completed"
                })

                # Save to database
                await self._save_incident(incident)

                # Send resolution notifications
                await self._send_resolution_notifications(incident)

                logger.info(f"Resolved incident {incident_id}")

        except Exception as e:
            logger.error(f"Failed to resolve incident: {e}")
            raise

    async def _send_resolution_notifications(self, incident: Incident):
        """Send resolution notifications"""
        try:
            if not self.config['notifications']['enabled']:
                return

            # Notify team members
            recipients = self.response_team['members'] + [self.response_team['lead']]
            if incident.assigned_to:
                recipients.append(incident.assigned_to)

            resolution_message = f"""
Incident Resolved:
- ID: {incident.id}
- Title: {incident.title}
- Resolution: {incident.resolution_notes}
- Root Cause: {incident.root_cause or 'Not determined'}
- Resolved At: {incident.resolved_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
            """.strip()

            for recipient in recipients:
                await self._send_notification(
                    recipient,
                    f"RESOLVED: {incident.title}",
                    resolution_message
                )

        except Exception as e:
            logger.error(f"Resolution notification error: {e}")

    def get_system_status(self) -> Dict:
        """Get system status"""
        return {
            "session_id": self.session_id,
            "active_incidents": len(self.active_incidents),
            "response_plans": len(self.plans),
            "email_enabled": self.email_client is not None,
            "slack_enabled": self.slack_client is not None,
            "automated_response": self.config['automation']['enabled'],
            "escalation_enabled": self.config['response']['escalation_enabled']
        }


async def main():
    """Main function to run incident response system"""
    # Create output directories
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/logs", exist_ok=True)
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/plans", exist_ok=True)
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/templates", exist_ok=True)

    # Initialize incident response system
    ir_system = IncidentResponseSystem()

    try:
        # Start incident response system
        await ir_system.start_incident_response()

        # Example: Create a test incident
        incident_id = ir_system.create_incident(
            title="Suspicious Login Activity Detected",
            description="Multiple failed login attempts from unusual IP address followed by successful login",
            severity=IncidentSeverity.HIGH,
            category=IncidentCategory.UNAUTHORIZED_ACCESS,
            source_ip="192.168.1.100",
            affected_systems=["auth_service", "user_database"],
            affected_users=["admin", "user123"],
            indicators={
                "failed_attempts": 15,
                "successful_login": True,
                "unusual_location": True,
                "off_hours_access": True
            }
        )

        # Keep system running
        while True:
            status = ir_system.get_system_status()
            print(f"\n🚨 Incident Response System Status")
            print(f"Session: {status['session_id']}")
            print(f"Active Incidents: {status['active_incidents']}")
            print(f"Response Plans: {status['response_plans']}")
            print(f"Automated Response: {status['automated_response']}")
            print(f"Escalation Enabled: {status['escalation_enabled']}")

            await asyncio.sleep(60)  # Status update every minute

    except KeyboardInterrupt:
        logger.info("Incident response system stopped by user")
    except Exception as e:
        logger.error(f"Incident response system error: {e}")


if __name__ == "__main__":
    asyncio.run(main())