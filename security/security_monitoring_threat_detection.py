#!/usr/bin/env python3
"""
Enterprise Security Monitoring and Threat Detection System for Knowledge Graph Analytics Dashboard
Real-time threat detection, security monitoring, and incident response automation
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
import re
import ipaddress
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import threading
import queue
import subprocess
import psutil
import socket
import ssl
import requests
from scapy.all import sniff, IP, TCP, UDP, ICMP
import paramiko
from jinja2 import Template

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/goodwiinz/development/RAG_system/rag/security/logs/monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertStatus(Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"

class EventType(Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    PROCESS = "process"
    DATABASE = "database"
    API = "api"
    SYSTEM = "system"
    APPLICATION = "application"

class DetectionMethod(Enum):
    SIGNATURE_BASED = "signature_based"
    ANOMALY_DETECTION = "anomaly_detection"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    THREAT_INTEL = "threat_intel"
    MACHINE_LEARNING = "machine_learning"
    RULE_BASED = "rule_based"

@dataclass
class SecurityEvent:
    """Security event data structure"""
    id: str
    timestamp: datetime
    event_type: EventType
    source_ip: str
    target: str
    user: Optional[str]
    action: str
    details: Dict[str, Any]
    severity: str
    raw_log: str
    normalized: bool = False

@dataclass
class ThreatAlert:
    """Threat alert data structure"""
    id: str
    title: str
    description: str
    threat_level: ThreatLevel
    confidence: float  # 0-100
    events: List[str]  # Event IDs
    detection_method: DetectionMethod
    rule_id: str
    mitre_tactics: List[str]
    mitre_techniques: List[str]
    indicators: Dict[str, Any]
    status: AlertStatus
    assigned_to: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    false_positive: bool = False

@dataclass
class DetectionRule:
    """Detection rule data structure"""
    id: str
    name: str
    description: str
    event_types: List[EventType]
    conditions: Dict[str, Any]
    severity: str
    threat_level: ThreatLevel
    detection_method: DetectionMethod
    enabled: bool
    tags: List[str]
    mitre_tactics: List[str]
    mitre_techniques: List[str]
    created_at: datetime
    updated_at: datetime

class SecurityMonitoringSystem:
    """Enterprise Security Monitoring and Threat Detection System"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.db_path = self.config['database']['path']
        self.rules_dir = Path(self.config['detection']['rules_directory'])
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = f"monitoring_{int(time.time())}"

        # Initialize components
        self.event_queue = asyncio.Queue()
        self.alert_queue = asyncio.Queue()
        self.rules: Dict[str, DetectionRule] = {}
        self.event_buffer = deque(maxlen=self.config['monitoring']['event_buffer_size'])
        self.alert_history = deque(maxlen=1000)
        self.baseline_stats = defaultdict(list)
        self.whitelist_ips = set(self.config['monitoring']['whitelist_ips'])
        self.blocked_ips = set()
        self.threat_intel_cache = {}

        # Initialize database
        self._init_database()

        # Load detection rules
        self._load_detection_rules()

        # Start monitoring threads
        self.monitoring_active = True
        self.monitor_threads = []

    def _load_config(self, config_path: str = None) -> Dict:
        """Load monitoring configuration"""
        default_config = {
            "environment": "production",
            "database": {
                "path": "/Users/goodwiinz/development/RAG_system/rag/security/monitoring.db"
            },
            "monitoring": {
                "event_buffer_size": 10000,
                "alert_retention_days": 90,
                "baseline_window_hours": 24,
                "anomaly_threshold": 2.5,
                "whitelist_ips": ["127.0.0.1", "::1"],
                "log_sources": [
                    "/var/log/auth.log",
                    "/var/log/nginx/access.log",
                    "/var/log/application.log"
                ]
            },
            "detection": {
                "rules_directory": "/Users/goodwiinz/development/RAG_system/rag/security/rules",
                "signature_rules": True,
                "anomaly_detection": True,
                "behavioral_analysis": True,
                "threat_intel_enabled": True,
                "ml_enabled": False
            },
            "network_monitoring": {
                "enabled": True,
                "interface": "eth0",
                "packet_capture": True,
                "port_monitoring": [22, 80, 443, 8000, 5432],
                "connection_tracking": True
            },
            "system_monitoring": {
                "enabled": True,
                "process_monitoring": True,
                "file_monitoring": True,
                "performance_monitoring": True,
                "log_monitoring": True
            },
            "application_monitoring": {
                "enabled": True,
                "api_monitoring": True,
                "authentication_monitoring": True,
                "database_monitoring": True,
                "error_tracking": True
            },
            "alerting": {
                "enabled": True,
                "thresholds": {
                    "failed_login_threshold": 5,
                    "failed_login_window": 300,  # 5 minutes
                    "suspicious_activity_threshold": 10,
                    "performance_degradation_threshold": 80
                },
                "notification_channels": ["email", "slack", "webhook"],
                "escalation_policy": {
                    "low": {"time_minutes": 60, "channel": "email"},
                    "medium": {"time_minutes": 30, "channel": "slack"},
                    "high": {"time_minutes": 15, "channel": ["slack", "email"]},
                    "critical": {"time_minutes": 5, "channel": ["slack", "email", "webhook"]}
                }
            },
            "threat_intel": {
                "enabled": True,
                "feeds": [
                    "https://reputation.alienvault.com/reputation.data",
                    "https://lists.blocklist.de/lists/all.txt",
                    "https://www.projecthoneypot.org/list_of_ips.php?t=d&rss=1"
                ],
                "cache_duration_hours": 24,
                "auto_block": True
            },
            "response": {
                "automated_response": True,
                "auto_block_duration_hours": 24,
                "quarantine_suspicious_files": True,
                "notify_security_team": True
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
        """Initialize monitoring database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Events table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_ip TEXT,
                    target TEXT,
                    user TEXT,
                    action TEXT,
                    details TEXT,
                    severity TEXT,
                    raw_log TEXT,
                    normalized BOOLEAN
                )
            ''')

            # Alerts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    threat_level TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    events TEXT,
                    detection_method TEXT,
                    rule_id TEXT,
                    mitre_tactics TEXT,
                    mitre_techniques TEXT,
                    indicators TEXT,
                    status TEXT NOT NULL,
                    assigned_to TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolution_notes TEXT,
                    false_positive BOOLEAN DEFAULT FALSE
                )
            ''')

            # Rules table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS detection_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    event_types TEXT,
                    conditions TEXT,
                    severity TEXT,
                    threat_level TEXT,
                    detection_method TEXT,
                    enabled BOOLEAN DEFAULT TRUE,
                    tags TEXT,
                    mitre_tactics TEXT,
                    mitre_techniques TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            # Baseline statistics table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS baseline_stats (
                    metric_name TEXT PRIMARY KEY,
                    baseline_value REAL,
                    std_deviation REAL,
                    last_updated TEXT,
                    sample_count INTEGER
                )
            ''')

            conn.commit()

    def _load_detection_rules(self):
        """Load detection rules from files"""
        logger.info("Loading detection rules")

        # Load built-in rules
        self._load_builtin_rules()

        # Load custom rules from directory
        if self.rules_dir.exists():
            for rule_file in self.rules_dir.glob("*.yaml"):
                try:
                    with open(rule_file, 'r') as f:
                        rule_data = yaml.safe_load(f)
                        rule = self._create_rule_from_data(rule_data)
                        self.rules[rule.id] = rule
                        logger.info(f"Loaded custom rule: {rule.name}")
                except Exception as e:
                    logger.error(f"Failed to load rule {rule_file}: {e}")

        # Save rules to database
        self._save_rules_to_database()

        logger.info(f"Loaded {len(self.rules)} detection rules")

    def _load_builtin_rules(self):
        """Load built-in detection rules"""
        builtin_rules = [
            {
                "id": "brute_force_login",
                "name": "Brute Force Login Attack",
                "description": "Detect multiple failed login attempts from same IP",
                "event_types": [EventType.AUTHENTICATION],
                "conditions": {
                    "action": "login_failed",
                    "time_window": 300,  # 5 minutes
                    "threshold": 5,
                    "same_source_ip": True
                },
                "severity": "high",
                "threat_level": ThreatLevel.HIGH,
                "detection_method": DetectionMethod.RULE_BASED,
                "enabled": True,
                "tags": ["authentication", "brute_force"],
                "mitre_tactics": ["Credential Access"],
                "mitre_techniques": ["T1110", "T1110.001"]
            },
            {
                "id": "suspicious_file_access",
                "name": "Suspicious File Access",
                "description": "Detect access to sensitive system files",
                "event_types": [EventType.FILE_SYSTEM],
                "conditions": {
                    "file_patterns": [
                        "/etc/passwd",
                        "/etc/shadow",
                        "/etc/sudoers",
                        "/root/.ssh/*"
                    ],
                    "whitelisted_users": ["root", "nobody"]
                },
                "severity": "medium",
                "threat_level": ThreatLevel.MEDIUM,
                "detection_method": DetectionMethod.RULE_BASED,
                "enabled": True,
                "tags": ["file_system", "privilege_escalation"],
                "mitre_tactics": ["Privilege Escalation"],
                "mitre_techniques": ["T1003", "T1083"]
            },
            {
                "id": "anomalous_network_traffic",
                "name": "Anomalous Network Traffic",
                "description": "Detect unusual network traffic patterns",
                "event_types": [EventType.NETWORK],
                "conditions": {
                    "baseline_deviation": 3.0,
                    "metrics": ["connection_count", "bytes_transferred", "unique_ports"]
                },
                "severity": "medium",
                "threat_level": ThreatLevel.MEDIUM,
                "detection_method": DetectionMethod.ANOMALY_DETECTION,
                "enabled": True,
                "tags": ["network", "anomaly"],
                "mitre_tactics": ["Command and Control"],
                "mitre_techniques": ["T1071", "T1095"]
            },
            {
                "id": "malicious_ip_connection",
                "name": "Connection to Malicious IP",
                "description": "Detect connections to known malicious IP addresses",
                "event_types": [EventType.NETWORK],
                "conditions": {
                    "threat_intel_match": True,
                    "confidence_threshold": 0.7
                },
                "severity": "high",
                "threat_level": ThreatLevel.HIGH,
                "detection_method": DetectionMethod.THREAT_INTEL,
                "enabled": True,
                "tags": ["network", "threat_intel"],
                "mitre_tactics": ["Command and Control"],
                "mitre_techniques": ["T1071"]
            },
            {
                "id": "unauthorized_api_access",
                "name": "Unauthorized API Access",
                "description": "Detect unauthorized access to API endpoints",
                "event_types": [EventType.API],
                "conditions": {
                    "response_codes": [401, 403],
                    "sensitive_endpoints": [
                        "/api/v1/admin",
                        "/api/v1/users",
                        "/api/v1/system"
                    ],
                    "threshold": 3
                },
                "severity": "medium",
                "threat_level": ThreatLevel.MEDIUM,
                "detection_method": DetectionMethod.RULE_BASED,
                "enabled": True,
                "tags": ["api", "authorization"],
                "mitre_tactics": ["Initial Access"],
                "mitre_techniques": ["T1190", "T1078"]
            },
            {
                "id": "process_anomaly",
                "name": "Suspicious Process Activity",
                "description": "Detect unusual process execution patterns",
                "event_types": [EventType.PROCESS],
                "conditions": {
                    "suspicious_commands": [
                        "nc -l",
                        "python -c",
                        "perl -e",
                        "bash -i",
                        "powershell"
                    ],
                    "network_connections": True,
                    "unusual_user": True
                },
                "severity": "high",
                "threat_level": ThreatLevel.HIGH,
                "detection_method": DetectionMethod.BEHAVIORAL_ANALYSIS,
                "enabled": True,
                "tags": ["process", "malware"],
                "mitre_tactics": ["Execution", "Persistence"],
                "mitre_techniques": ["T1059", "T1053"]
            },
            {
                "id": "database_anomaly",
                "name": "Database Anomaly Detection",
                "description": "Detect unusual database access patterns",
                "event_types": [EventType.DATABASE],
                "conditions": {
                    "unusual_queries": True,
                    "large_data_export": True,
                    "off_hours_access": True,
                    "privilege_escalation": True
                },
                "severity": "medium",
                "threat_level": ThreatLevel.MEDIUM,
                "detection_method": DetectionMethod.ANOMALY_DETECTION,
                "enabled": True,
                "tags": ["database", "data_exfiltration"],
                "mitre_tactics": ["Collection"],
                "mitre_techniques": ["T1079", "T1005"]
            }
        ]

        for rule_data in builtin_rules:
            rule = self._create_rule_from_data(rule_data)
            self.rules[rule.id] = rule

    def _create_rule_from_data(self, rule_data: Dict) -> DetectionRule:
        """Create DetectionRule from dictionary"""
        return DetectionRule(
            id=rule_data['id'],
            name=rule_data['name'],
            description=rule_data['description'],
            event_types=[EventType(t) for t in rule_data['event_types']],
            conditions=rule_data['conditions'],
            severity=rule_data['severity'],
            threat_level=ThreatLevel(rule_data['threat_level']) if isinstance(rule_data['threat_level'], str) else rule_data['threat_level'],
            detection_method=DetectionMethod(rule_data['detection_method']),
            enabled=rule_data.get('enabled', True),
            tags=rule_data.get('tags', []),
            mitre_tactics=rule_data.get('mitre_tactics', []),
            mitre_techniques=rule_data.get('mitre_techniques', []),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    def _save_rules_to_database(self):
        """Save detection rules to database"""
        with sqlite3.connect(self.db_path) as conn:
            for rule in self.rules.values():
                conn.execute('''
                    INSERT OR REPLACE INTO detection_rules
                    (id, name, description, event_types, conditions, severity, threat_level,
                     detection_method, enabled, tags, mitre_tactics, mitre_techniques, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    rule.id,
                    rule.name,
                    rule.description,
                    json.dumps([t.value for t in rule.event_types]),
                    json.dumps(rule.conditions),
                    rule.severity,
                    rule.threat_level.value,
                    rule.detection_method.value,
                    rule.enabled,
                    json.dumps(rule.tags),
                    json.dumps(rule.mitre_tactics),
                    json.dumps(rule.mitre_techniques),
                    rule.created_at.isoformat(),
                    rule.updated_at.isoformat()
                ))
            conn.commit()

    async def start_monitoring(self):
        """Start security monitoring system"""
        logger.info(f"Starting security monitoring: {self.session_id}")

        try:
            # Start monitoring threads
            if self.config['system_monitoring']['enabled']:
                self._start_system_monitoring()

            if self.config['network_monitoring']['enabled']:
                self._start_network_monitoring()

            if self.config['application_monitoring']['enabled']:
                self._start_application_monitoring()

            # Start event processing
            await self._start_event_processing()

            # Start alert processing
            await self._start_alert_processing()

            # Start threat intelligence updates
            if self.config['threat_intel']['enabled']:
                await self._start_threat_intel_updates()

            # Start baseline calculation
            await self._start_baseline_calculation()

            logger.info("Security monitoring system started successfully")

        except Exception as e:
            logger.error(f"Failed to start security monitoring: {e}")
            raise

    def _start_system_monitoring(self):
        """Start system monitoring thread"""
        def system_monitor():
            while self.monitoring_active:
                try:
                    # Monitor processes
                    if self.config['system_monitoring']['process_monitoring']:
                        self._monitor_processes()

                    # Monitor file system
                    if self.config['system_monitoring']['file_monitoring']:
                        self._monitor_file_system()

                    # Monitor system performance
                    if self.config['system_monitoring']['performance_monitoring']:
                        self._monitor_performance()

                    # Monitor log files
                    if self.config['system_monitoring']['log_monitoring']:
                        self._monitor_log_files()

                    time.sleep(10)  # Monitor every 10 seconds

                except Exception as e:
                    logger.error(f"System monitoring error: {e}")
                    time.sleep(5)

        thread = threading.Thread(target=system_monitor, daemon=True)
        thread.start()
        self.monitor_threads.append(thread)

    def _start_network_monitoring(self):
        """Start network monitoring thread"""
        def network_monitor():
            while self.monitoring_active:
                try:
                    self._monitor_network_connections()
                    time.sleep(30)  # Monitor every 30 seconds
                except Exception as e:
                    logger.error(f"Network monitoring error: {e}")
                    time.sleep(10)

        thread = threading.Thread(target=network_monitor, daemon=True)
        thread.start()
        self.monitor_threads.append(thread)

        # Start packet capture if enabled
        if self.config['network_monitoring']['packet_capture']:
            self._start_packet_capture()

    def _start_application_monitoring(self):
        """Start application monitoring thread"""
        def application_monitor():
            while self.monitoring_active:
                try:
                    # Monitor API endpoints
                    if self.config['application_monitoring']['api_monitoring']:
                        self._monitor_api_endpoints()

                    # Monitor authentication events
                    if self.config['application_monitoring']['authentication_monitoring']:
                        self._monitor_authentication()

                    # Monitor database activity
                    if self.config['application_monitoring']['database_monitoring']:
                        self._monitor_database_activity()

                    # Monitor application errors
                    if self.config['application_monitoring']['error_tracking']:
                        self._monitor_application_errors()

                    time.sleep(15)  # Monitor every 15 seconds

                except Exception as e:
                    logger.error(f"Application monitoring error: {e}")
                    time.sleep(10)

        thread = threading.Thread(target=application_monitor, daemon=True)
        thread.start()
        self.monitor_threads.append(thread)

    def _monitor_processes(self):
        """Monitor system processes for suspicious activity"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'connections']):
                try:
                    proc_info = proc.info
                    cmdline = ' '.join(proc_info['cmdline'] or [])

                    # Check for suspicious commands
                    suspicious_patterns = [
                        r'nc\s+-l',  # netcat listener
                        r'python\s+-c',
                        r'perl\s+-e',
                        r'bash\s+-i',
                        r'powershell.*-enc',
                        r'wget.*\|.*sh',
                        r'curl.*\|.*bash'
                    ]

                    for pattern in suspicious_patterns:
                        if re.search(pattern, cmdline, re.IGNORECASE):
                            self._create_event(
                                event_type=EventType.PROCESS,
                                source_ip="localhost",
                                target=f"PID:{proc_info['pid']}",
                                user=proc_info['username'],
                                action="suspicious_process",
                                details={
                                    "process_name": proc_info['name'],
                                    "command_line": cmdline,
                                    "pattern": pattern,
                                    "pid": proc_info['pid']
                                },
                                severity="high",
                                raw_log=f"Suspicious process detected: {cmdline}"
                            )

                    # Check for network connections
                    if self.config['network_monitoring']['connection_tracking']:
                        connections = proc.connections()
                        if connections:
                            for conn in connections:
                                if conn.status == 'ESTABLISHED':
                                    self._create_event(
                                        event_type=EventType.NETWORK,
                                        source_ip=conn.laddr.ip,
                                        target=f"{conn.raddr.ip}:{conn.raddr.port}",
                                        user=proc_info['username'],
                                        action="process_network_connection",
                                        details={
                                            "process_name": proc_info['name'],
                                            "pid": proc_info['pid'],
                                            "local_addr": f"{conn.laddr.ip}:{conn.laddr.port}",
                                            "remote_addr": f"{conn.raddr.ip}:{conn.raddr.port}",
                                            "status": conn.status
                                        },
                                        severity="low",
                                        raw_log=f"Process network connection: {proc_info['name']} -> {conn.raddr.ip}:{conn.raddr.port}"
                                    )

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            logger.error(f"Process monitoring error: {e}")

    def _monitor_file_system(self):
        """Monitor file system for suspicious activity"""
        try:
            # Monitor critical system files
            critical_files = [
                "/etc/passwd",
                "/etc/shadow",
                "/etc/sudoers",
                "/etc/hosts",
                "/root/.ssh/authorized_keys"
            ]

            for file_path in critical_files:
                if os.path.exists(file_path):
                    stat = os.stat(file_path)
                    current_mtime = stat.st_mtime

                    # Check if file was recently modified (within last minute)
                    if time.time() - current_mtime < 60:
                        self._create_event(
                            event_type=EventType.FILE_SYSTEM,
                            source_ip="localhost",
                            target=file_path,
                            user=None,  # Would need to track file owner
                            action="critical_file_modified",
                            details={
                                "file_path": file_path,
                                "modified_time": current_mtime,
                                "size": stat.st_size
                            },
                            severity="high",
                            raw_log=f"Critical file modified: {file_path}"
                        )

        except Exception as e:
            logger.error(f"File system monitoring error: {e}")

    def _monitor_performance(self):
        """Monitor system performance for anomalies"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self._update_baseline("cpu_usage", cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self._update_baseline("memory_usage", memory.percent)

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = (disk.used / disk.total) * 100
            self._update_baseline("disk_usage", disk_usage)

            # Network I/O
            net_io = psutil.net_io_counters()
            self._update_baseline("network_bytes_sent", net_io.bytes_sent)
            self._update_baseline("network_bytes_recv", net_io.bytes_recv)

            # Check for anomalies
            if self._is_anomaly("cpu_usage", cpu_percent, threshold=80):
                self._create_event(
                    event_type=EventType.SYSTEM,
                    source_ip="localhost",
                    target="system",
                    user=None,
                    action="high_cpu_usage",
                    details={"cpu_percent": cpu_percent},
                    severity="medium",
                    raw_log=f"High CPU usage detected: {cpu_percent}%"
                )

            if self._is_anomaly("memory_usage", memory.percent, threshold=90):
                self._create_event(
                    event_type=EventType.SYSTEM,
                    source_ip="localhost",
                    target="system",
                    user=None,
                    action="high_memory_usage",
                    details={"memory_percent": memory.percent},
                    severity="medium",
                    raw_log=f"High memory usage detected: {memory.percent}%"
                )

        except Exception as e:
            logger.error(f"Performance monitoring error: {e}")

    def _monitor_log_files(self):
        """Monitor log files for security events"""
        try:
            log_sources = self.config['monitoring']['log_sources']

            for log_file in log_sources:
                if os.path.exists(log_file):
                    # Read new lines from log file
                    with open(log_file, 'r') as f:
                        f.seek(0, 2)  # Go to end of file
                        new_lines = f.readlines()

                    for line in new_lines:
                        self._parse_log_line(line.strip(), log_file)

        except Exception as e:
            logger.error(f"Log monitoring error: {e}")

    def _parse_log_line(self, line: str, log_file: str):
        """Parse log line and create security event"""
        try:
            # SSH authentication logs
            if "sshd" in log_file:
                self._parse_ssh_log(line)

            # Nginx access logs
            elif "nginx" in log_file:
                self._parse_nginx_log(line)

            # Application logs
            elif "application" in log_file:
                self._parse_application_log(line)

        except Exception as e:
            logger.debug(f"Failed to parse log line: {e}")

    def _parse_ssh_log(self, line: str):
        """Parse SSH authentication logs"""
        if "Failed password" in line:
            # Extract IP address and user
            match = re.search(r'from (\d+\.\d+\.\d+\.\d+)', line)
            user_match = re.search(r'for (\w+)', line)

            if match:
                ip = match.group(1)
                user = user_match.group(1) if user_match else "unknown"

                self._create_event(
                    event_type=EventType.AUTHENTICATION,
                    source_ip=ip,
                    target="ssh_server",
                    user=user,
                    action="login_failed",
                    details={
                        "service": "ssh",
                        "log_line": line
                    },
                    severity="medium",
                    raw_log=line
                )

        elif "Accepted password" in line:
            match = re.search(r'from (\d+\.\d+\.\d+\.\d+)', line)
            user_match = re.search(r'for (\w+)', line)

            if match:
                ip = match.group(1)
                user = user_match.group(1) if user_match else "unknown"

                self._create_event(
                    event_type=EventType.AUTHENTICATION,
                    source_ip=ip,
                    target="ssh_server",
                    user=user,
                    action="login_success",
                    details={
                        "service": "ssh",
                        "log_line": line
                    },
                    severity="low",
                    raw_log=line
                )

    def _parse_nginx_log(self, line: str):
        """Parse Nginx access logs"""
        try:
            # Extract IP, status code, URL
            parts = line.split()
            if len(parts) >= 7:
                ip = parts[0]
                status_code = parts[8]
                url = parts[6]

                # Check for suspicious status codes
                if status_code in ['401', '403', '404']:
                    severity = "low"
                    if status_code in ['401', '403']:
                        severity = "medium"

                    self._create_event(
                        event_type=EventType.API,
                        source_ip=ip,
                        target="web_server",
                        user=None,
                        action="http_request",
                        details={
                            "status_code": status_code,
                            "url": url,
                            "user_agent": ' '.join(parts[11:]) if len(parts) > 11 else ""
                        },
                        severity=severity,
                        raw_log=line
                    )

                # Check for suspicious URLs
                suspicious_patterns = [
                    r'/admin',
                    r'/wp-admin',
                    r'/phpmyadmin',
                    r'\.php\?',
                    r'\.asp\?',
                    r'union.*select',
                    r'script.*alert'
                ]

                for pattern in suspicious_patterns:
                    if re.search(pattern, url, re.IGNORECASE):
                        self._create_event(
                            event_type=EventType.API,
                            source_ip=ip,
                            target="web_server",
                            user=None,
                            action="suspicious_request",
                            details={
                                "url": url,
                                "pattern": pattern,
                                "status_code": status_code
                            },
                            severity="high",
                            raw_log=line
                        )
                        break

        except Exception as e:
            logger.debug(f"Failed to parse nginx log: {e}")

    def _parse_application_log(self, line: str):
        """Parse application logs"""
        # Check for authentication events
        if "login" in line.lower() or "auth" in line.lower():
            if "failed" in line.lower() or "invalid" in line.lower():
                self._create_event(
                    event_type=EventType.AUTHENTICATION,
                    source_ip="application",
                    target="auth_service",
                    user=None,
                    action="login_failed",
                    details={"log_line": line},
                    severity="medium",
                    raw_log=line
                )

        # Check for error messages
        elif "error" in line.lower() or "exception" in line.lower():
            self._create_event(
                event_type=EventType.APPLICATION,
                source_ip="application",
                target="application",
                user=None,
                action="error",
                details={"log_line": line},
                severity="low",
                raw_log=line
            )

    def _monitor_network_connections(self):
        """Monitor network connections"""
        try:
            connections = psutil.net_connections()

            # Track connections by IP
            connection_counts = defaultdict(int)
            for conn in connections:
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    ip = conn.raddr.ip
                    connection_counts[ip] += 1

                    # Check if IP is in threat intelligence
                    if self._is_malicious_ip(ip):
                        self._create_event(
                            event_type=EventType.NETWORK,
                            source_ip=ip,
                            target=f"localhost:{conn.laddr.port}" if conn.laddr else "localhost",
                            user=None,
                            action="malicious_ip_connection",
                            details={
                                "remote_ip": ip,
                                "local_port": conn.laddr.port if conn.laddr else None,
                                "status": conn.status
                            },
                            severity="high",
                            raw_log=f"Connection to malicious IP: {ip}"
                        )

            # Check for unusual connection patterns
            for ip, count in connection_counts.items():
                if count > 50:  # More than 50 connections from single IP
                    self._create_event(
                        event_type=EventType.NETWORK,
                        source_ip=ip,
                        target="localhost",
                        user=None,
                        action="unusual_connection_pattern",
                        details={"connection_count": count},
                        severity="medium",
                        raw_log=f"Unusual connection pattern from {ip}: {count} connections"
                    )

        except Exception as e:
            logger.error(f"Network connection monitoring error: {e}")

    def _start_packet_capture(self):
        """Start packet capture thread"""
        def packet_capture():
            try:
                sniff(
                    prn=self._process_packet,
                    store=False,
                    stop_filter=lambda x: not self.monitoring_active
                )
            except Exception as e:
                logger.error(f"Packet capture error: {e}")

        thread = threading.Thread(target=packet_capture, daemon=True)
        thread.start()
        self.monitor_threads.append(thread)

    def _process_packet(self, packet):
        """Process captured packet"""
        try:
            if IP in packet:
                ip_layer = packet[IP]
                src_ip = ip_layer.src
                dst_ip = ip_layer.dst

                # Check for suspicious traffic
                if self._is_malicious_ip(src_ip) or self._is_malicious_ip(dst_ip):
                    self._create_event(
                        event_type=EventType.NETWORK,
                        source_ip=src_ip,
                        target=dst_ip,
                        user=None,
                        action="malicious_packet",
                        details={
                            "protocol": ip_layer.proto,
                            "packet_size": len(packet),
                            "ttl": ip_layer.ttl
                        },
                        severity="high",
                        raw_log=packet.summary()
                    )

        except Exception as e:
            logger.debug(f"Packet processing error: {e}")

    def _monitor_api_endpoints(self):
        """Monitor API endpoints for suspicious activity"""
        try:
            # Check application logs for API activity
            # This would integrate with actual application monitoring
            pass

        except Exception as e:
            logger.error(f"API monitoring error: {e}")

    def _monitor_authentication(self):
        """Monitor authentication events"""
        try:
            # This would integrate with actual authentication monitoring
            # Simulate failed login threshold check
            pass

        except Exception as e:
            logger.error(f"Authentication monitoring error: {e}")

    def _monitor_database_activity(self):
        """Monitor database activity"""
        try:
            # This would integrate with actual database monitoring
            pass

        except Exception as e:
            logger.error(f"Database monitoring error: {e}")

    def _monitor_application_errors(self):
        """Monitor application errors"""
        try:
            # This would integrate with actual error monitoring
            pass

        except Exception as e:
            logger.error(f"Application error monitoring error: {e}")

    def _create_event(self, event_type: EventType, source_ip: str, target: str, user: Optional[str],
                     action: str, details: Dict, severity: str, raw_log: str):
        """Create a security event"""
        event = SecurityEvent(
            id=f"evt_{int(time.time() * 1000)}_{hashlib.md5(raw_log.encode()).hexdigest()[:8]}",
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            source_ip=source_ip,
            target=target,
            user=user,
            action=action,
            details=details,
            severity=severity,
            raw_log=raw_log
        )

        # Add to event buffer
        self.event_buffer.append(event)

        # Queue for processing
        asyncio.create_task(self.event_queue.put(event))

    async def _start_event_processing(self):
        """Start event processing loop"""
        logger.info("Starting event processing")

        while self.monitoring_active:
            try:
                # Get event from queue
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)

                # Normalize event
                normalized_event = self._normalize_event(event)
                if normalized_event:
                    # Save to database
                    await self._save_event(normalized_event)

                    # Run detection rules
                    await self._run_detection_rules(normalized_event)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")

    def _normalize_event(self, event: SecurityEvent) -> Optional[SecurityEvent]:
        """Normalize security event"""
        try:
            # Skip whitelisted IPs
            if event.source_ip in self.whitelist_ips:
                return None

            # Additional normalization logic
            normalized_event = event
            normalized_event.normalized = True

            return normalized_event

        except Exception as e:
            logger.error(f"Event normalization error: {e}")
            return None

    async def _save_event(self, event: SecurityEvent):
        """Save event to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO events
                    (id, timestamp, event_type, source_ip, target, user, action, details, severity, raw_log, normalized)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.id,
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.source_ip,
                    event.target,
                    event.user,
                    event.action,
                    json.dumps(event.details),
                    event.severity,
                    event.raw_log,
                    event.normalized
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save event: {e}")

    async def _run_detection_rules(self, event: SecurityEvent):
        """Run detection rules on event"""
        for rule in self.rules.values():
            if not rule.enabled:
                continue

            if event.event_type in rule.event_types:
                try:
                    if await self._evaluate_rule(rule, event):
                        await self._create_alert(rule, event)
                except Exception as e:
                    logger.error(f"Rule evaluation error for {rule.id}: {e}")

    async def _evaluate_rule(self, rule: DetectionRule, event: SecurityEvent) -> bool:
        """Evaluate detection rule against event"""
        conditions = rule.conditions

        # Rule-based detection
        if rule.detection_method == DetectionMethod.RULE_BASED:
            return self._evaluate_rule_based_conditions(conditions, event)

        # Anomaly detection
        elif rule.detection_method == DetectionMethod.ANOMALY_DETECTION:
            return self._evaluate_anomaly_conditions(conditions, event)

        # Threat intelligence
        elif rule.detection_method == DetectionMethod.THREAT_INTEL:
            return self._evaluate_threat_intel_conditions(conditions, event)

        # Behavioral analysis
        elif rule.detection_method == DetectionMethod.BEHAVIORAL_ANALYSIS:
            return self._evaluate_behavioral_conditions(conditions, event)

        return False

    def _evaluate_rule_based_conditions(self, conditions: Dict, event: SecurityEvent) -> bool:
        """Evaluate rule-based conditions"""
        # Action matching
        if "action" in conditions:
            if event.action != conditions["action"]:
                return False

        # Time window based aggregation
        if "time_window" in conditions and "threshold" in conditions:
            time_window = conditions["time_window"]
            threshold = conditions["threshold"]

            # Count similar events in time window
            cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_window)
            similar_events = [
                e for e in self.event_buffer
                if e.timestamp > cutoff_time and e.action == event.action
            ]

            # Check for same source IP if required
            if conditions.get("same_source_ip", False):
                similar_events = [
                    e for e in similar_events
                    if e.source_ip == event.source_ip
                ]

            return len(similar_events) >= threshold

        # File pattern matching
        if "file_patterns" in conditions:
            if event.event_type == EventType.FILE_SYSTEM:
                target = event.target
                for pattern in conditions["file_patterns"]:
                    if re.match(pattern.replace("*", ".*"), target):
                        # Check if user is not whitelisted
                        whitelisted_users = conditions.get("whitelisted_users", [])
                        if event.user not in whitelisted_users:
                            return True

        # Network conditions
        if "threat_intel_match" in conditions:
            return self._is_malicious_ip(event.source_ip)

        return False

    def _evaluate_anomaly_conditions(self, conditions: Dict, event: SecurityEvent) -> bool:
        """Evaluate anomaly detection conditions"""
        baseline_deviation = conditions.get("baseline_deviation", 2.5)
        metrics = conditions.get("metrics", [])

        for metric in metrics:
            if self._is_anomaly(metric, getattr(event, metric, 0), threshold=baseline_deviation):
                return True

        return False

    def _evaluate_threat_intel_conditions(self, conditions: Dict, event: SecurityEvent) -> bool:
        """Evaluate threat intelligence conditions"""
        confidence_threshold = conditions.get("confidence_threshold", 0.7)

        if event.event_type == EventType.NETWORK:
            threat_score = self._get_threat_score(event.source_ip)
            return threat_score >= confidence_threshold

        return False

    def _evaluate_behavioral_conditions(self, conditions: Dict, event: SecurityEvent) -> bool:
        """Evaluate behavioral analysis conditions"""
        if event.event_type == EventType.PROCESS:
            cmdline = event.details.get("command_line", "")
            suspicious_commands = conditions.get("suspicious_commands", [])

            for pattern in suspicious_commands:
                if re.search(pattern, cmdline, re.IGNORECASE):
                    # Additional checks
                    if conditions.get("network_connections", False):
                        # Would check if process has network connections
                        pass

                    if conditions.get("unusual_user", False):
                        # Would check if user is unusual for this process
                        pass

                    return True

        return False

    async def _create_alert(self, rule: DetectionRule, event: SecurityEvent):
        """Create security alert"""
        alert_id = f"alert_{int(time.time() * 1000)}_{rule.id}"

        # Gather related events
        related_events = []
        for e in self.event_buffer:
            if (e.event_type == event.event_type and
                e.source_ip == event.source_ip and
                (datetime.now(timezone.utc) - e.timestamp).seconds < 300):
                related_events.append(e.id)

        alert = ThreatAlert(
            id=alert_id,
            title=rule.name,
            description=rule.description,
            threat_level=rule.threat_level,
            confidence=min(100, len(related_events) * 20),  # Confidence based on event count
            events=related_events,
            detection_method=rule.detection_method,
            rule_id=rule.id,
            mitre_tactics=rule.mitre_tactics,
            mitre_techniques=rule.mitre_techniques,
            indicators={
                "source_ip": event.source_ip,
                "target": event.target,
                "user": event.user,
                "action": event.action
            },
            status=AlertStatus.NEW,
            assigned_to=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            resolved_at=None,
            resolution_notes=None
        )

        # Queue alert for processing
        await self.alert_queue.put(alert)

        # Add to alert history
        self.alert_history.append(alert)

        logger.warning(f"Security alert created: {alert.title} (Level: {alert.threat_level.value})")

    async def _start_alert_processing(self):
        """Start alert processing loop"""
        logger.info("Starting alert processing")

        while self.monitoring_active:
            try:
                # Get alert from queue
                alert = await asyncio.wait_for(self.alert_queue.get(), timeout=1.0)

                # Save alert to database
                await self._save_alert(alert)

                # Send notifications
                if self.config['alerting']['enabled']:
                    await self._send_alert_notification(alert)

                # Automated response
                if self.config['response']['automated_response']:
                    await self._execute_automated_response(alert)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Alert processing error: {e}")

    async def _save_alert(self, alert: ThreatAlert):
        """Save alert to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO alerts
                    (id, title, description, threat_level, confidence, events, detection_method,
                     rule_id, mitre_tactics, mitre_techniques, indicators, status, assigned_to,
                     created_at, updated_at, resolved_at, resolution_notes, false_positive)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.id,
                    alert.title,
                    alert.description,
                    alert.threat_level.value,
                    alert.confidence,
                    json.dumps(alert.events),
                    alert.detection_method.value,
                    alert.rule_id,
                    json.dumps(alert.mitre_tactics),
                    json.dumps(alert.mitre_techniques),
                    json.dumps(alert.indicators),
                    alert.status.value,
                    alert.assigned_to,
                    alert.created_at.isoformat(),
                    alert.updated_at.isoformat(),
                    alert.resolved_at.isoformat() if alert.resolved_at else None,
                    alert.resolution_notes,
                    alert.false_positive
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")

    async def _send_alert_notification(self, alert: ThreatAlert):
        """Send alert notification"""
        try:
            # Determine notification channels based on threat level
            escalation = self.config['alerting']['escalation_policy'][alert.threat_level.value]
            channels = escalation['channel']
            if isinstance(channels, str):
                channels = [channels]

            for channel in channels:
                if channel == "email":
                    await self._send_email_notification(alert)
                elif channel == "slack":
                    await self._send_slack_notification(alert)
                elif channel == "webhook":
                    await self._send_webhook_notification(alert)

        except Exception as e:
            logger.error(f"Alert notification error: {e}")

    async def _send_email_notification(self, alert: ThreatAlert):
        """Send email notification"""
        # Implementation would depend on email service
        logger.info(f"Email notification sent for alert: {alert.title}")

    async def _send_slack_notification(self, alert: ThreatAlert):
        """Send Slack notification"""
        # Implementation would depend on Slack integration
        logger.info(f"Slack notification sent for alert: {alert.title}")

    async def _send_webhook_notification(self, alert: ThreatAlert):
        """Send webhook notification"""
        # Implementation would depend on webhook endpoint
        logger.info(f"Webhook notification sent for alert: {alert.title}")

    async def _execute_automated_response(self, alert: ThreatAlert):
        """Execute automated response to alert"""
        try:
            # Block malicious IP if enabled
            if (self.config['threat_intel']['auto_block'] and
                alert.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]):

                source_ip = alert.indicators.get('source_ip')
                if source_ip and source_ip not in self.whitelist_ips:
                    await self._block_ip(source_ip)

            # Additional automated response actions
            if alert.threat_level == ThreatLevel.CRITICAL:
                # Trigger incident response
                await self._trigger_incident_response(alert)

        except Exception as e:
            logger.error(f"Automated response error: {e}")

    async def _block_ip(self, ip: str):
        """Block IP address"""
        try:
            # Add to blocked IPs set
            self.blocked_ips.add(ip)

            # Add firewall rule (implementation depends on firewall system)
            # For example: iptables -A INPUT -s {ip} -j DROP
            logger.info(f"Blocked IP address: {ip}")

        except Exception as e:
            logger.error(f"Failed to block IP {ip}: {e}")

    async def _trigger_incident_response(self, alert: ThreatAlert):
        """Trigger incident response procedure"""
        logger.critical(f"CRITICAL ALERT - Incident response triggered: {alert.title}")
        # Implementation would notify security team and initiate incident response procedures

    async def _start_threat_intel_updates(self):
        """Start threat intelligence updates"""
        logger.info("Starting threat intelligence updates")

        while self.monitoring_active:
            try:
                await self._update_threat_intelligence()
                # Update every 24 hours
                await asyncio.sleep(24 * 3600)
            except Exception as e:
                logger.error(f"Threat intelligence update error: {e}")
                await asyncio.sleep(3600)  # Retry after 1 hour

    async def _update_threat_intelligence(self):
        """Update threat intelligence data"""
        try:
            feeds = self.config['threat_intel']['feeds']

            for feed_url in feeds:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                            if response.status == 200:
                                content = await response.text()
                                self._parse_threat_feed(feed_url, content)

                except Exception as e:
                    logger.error(f"Failed to update threat feed {feed_url}: {e}")

            # Clean old entries
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                hours=self.config['threat_intel']['cache_duration_hours']
            )
            self._cleanup_threat_intel(cutoff_time)

            logger.info("Threat intelligence updated successfully")

        except Exception as e:
            logger.error(f"Threat intelligence update failed: {e}")

    def _parse_threat_feed(self, feed_url: str, content: str):
        """Parse threat intelligence feed"""
        try:
            # Parse different feed formats
            lines = content.strip().split('\n')

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Check if line is an IP address
                if self._is_valid_ip(line):
                    self.threat_intel_cache[line] = {
                        'source': feed_url,
                        'added_at': datetime.now(timezone.utc),
                        'confidence': 0.8
                    }

        except Exception as e:
            logger.error(f"Failed to parse threat feed {feed_url}: {e}")

    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string is a valid IP address"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _is_malicious_ip(self, ip: str) -> bool:
        """Check if IP is in threat intelligence"""
        return ip in self.threat_intel_cache

    def _get_threat_score(self, ip: str) -> float:
        """Get threat score for IP"""
        if ip in self.threat_intel_cache:
            return self.threat_intel_cache[ip]['confidence']
        return 0.0

    def _cleanup_threat_intel(self, cutoff_time: datetime):
        """Clean up old threat intelligence entries"""
        keys_to_remove = [
            ip for ip, data in self.threat_intel_cache.items()
            if data['added_at'] < cutoff_time
        ]

        for ip in keys_to_remove:
            del self.threat_intel_cache[ip]

        logger.info(f"Cleaned up {len(keys_to_remove)} old threat intelligence entries")

    async def _start_baseline_calculation(self):
        """Start baseline calculation loop"""
        logger.info("Starting baseline calculation")

        while self.monitoring_active:
            try:
                await self._calculate_baselines()
                # Update baselines every hour
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Baseline calculation error: {e}")
                await asyncio.sleep(300)  # Retry after 5 minutes

    async def _calculate_baselines(self):
        """Calculate baseline statistics"""
        try:
            for metric_name, values in self.baseline_stats.items():
                if len(values) >= 10:  # Need minimum samples
                    mean_value = np.mean(values)
                    std_dev = np.std(values)

                    # Update baseline in database
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute('''
                            INSERT OR REPLACE INTO baseline_stats
                            (metric_name, baseline_value, std_deviation, last_updated, sample_count)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            metric_name,
                            mean_value,
                            std_dev,
                            datetime.now(timezone.utc).isoformat(),
                            len(values)
                        ))
                        conn.commit()

        except Exception as e:
            logger.error(f"Baseline calculation error: {e}")

    def _update_baseline(self, metric_name: str, value: float):
        """Update baseline metric"""
        self.baseline_stats[metric_name].append(value)

        # Keep only recent values (last 1000)
        if len(self.baseline_stats[metric_name]) > 1000:
            self.baseline_stats[metric_name] = self.baseline_stats[metric_name][-1000:]

    def _is_anomaly(self, metric_name: str, value: float, threshold: float = 2.5) -> bool:
        """Check if value is anomalous"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT baseline_value, std_deviation FROM baseline_stats WHERE metric_name = ?',
                    (metric_name,)
                )
                result = cursor.fetchone()

                if result:
                    baseline_value, std_deviation = result
                    if std_deviation > 0:
                        z_score = abs(value - baseline_value) / std_deviation
                        return z_score > threshold

        except Exception as e:
            logger.error(f"Anomaly detection error for {metric_name}: {e}")

        return False

    def stop_monitoring(self):
        """Stop security monitoring"""
        logger.info("Stopping security monitoring")
        self.monitoring_active = False

        # Wait for threads to finish
        for thread in self.monitor_threads:
            if thread.is_alive():
                thread.join(timeout=5)

        logger.info("Security monitoring stopped")

    def get_monitoring_status(self) -> Dict:
        """Get monitoring system status"""
        return {
            "session_id": self.session_id,
            "monitoring_active": self.monitoring_active,
            "active_threads": len([t for t in self.monitor_threads if t.is_alive()]),
            "event_queue_size": self.event_queue.qsize(),
            "alert_queue_size": self.alert_queue.qsize(),
            "rules_loaded": len(self.rules),
            "events_buffered": len(self.event_buffer),
            "alerts_history": len(self.alert_history),
            "blocked_ips": len(self.blocked_ips),
            "threat_intel_entries": len(self.threat_intel_cache)
        }


async def main():
    """Main function to run security monitoring"""
    # Create output directories
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/logs", exist_ok=True)
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/rules", exist_ok=True)

    # Initialize monitoring system
    monitoring_system = SecurityMonitoringSystem()

    try:
        # Start monitoring
        await monitoring_system.start_monitoring()

        # Keep monitoring running
        while True:
            status = monitoring_system.get_monitoring_status()
            print(f"\n🛡️ Security Monitoring Status")
            print(f"Session: {status['session_id']}")
            print(f"Active: {status['monitoring_active']}")
            print(f"Events Processed: {status['events_buffered']}")
            print(f"Alerts Generated: {status['alerts_history']}")
            print(f"Threat Intel Entries: {status['threat_intel_entries']}")
            print(f"Blocked IPs: {status['blocked_ips']}")

            await asyncio.sleep(60)  # Status update every minute

    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
    finally:
        monitoring_system.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())