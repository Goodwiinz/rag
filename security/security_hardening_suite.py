#!/usr/bin/env python3
"""
Enterprise Security Hardening Suite for Knowledge Graph Analytics Dashboard
Comprehensive system security configuration and hardening automation
"""

import os
import sys
import json
import yaml
import subprocess
import shutil
import hashlib
import secrets
import string
import time
import logging
import ssl
import socket
import requests
import sqlite3
import psycopg2
import redis
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.fernet import Fernet
import bcrypt
import passlib.hash
from passlib.hash import argon2

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/goodwiinz/development/RAG_system/rag/security/logs/hardening.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HardeningStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class SystemComponent(Enum):
    OPERATING_SYSTEM = "operating_system"
    DOCKER = "docker"
    DATABASE = "database"
    WEB_SERVER = "web_server"
    APPLICATION = "application"
    NETWORK = "network"
    ENCRYPTION = "encryption"
    MONITORING = "monitoring"

@dataclass
class HardeningTask:
    """Hardening task data structure"""
    id: str
    title: str
    description: str
    component: SystemComponent
    severity: str  # critical, high, medium, low
    status: HardeningStatus
    command: Optional[str]
    config_file: Optional[str]
    backup_file: Optional[str]
    validation_command: Optional[str]
    rollback_command: Optional[str]
    dependencies: List[str]
    execution_time: Optional[float]
    error_message: Optional[str]
    completed_at: Optional[datetime]

class SecurityHardeningSuite:
    """Enterprise Security Hardening Suite"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.tasks: List[HardeningTask] = []
        self.execution_log: List[Dict] = []
        self.backup_dir = Path(self.config['backup']['directory'])
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = f"hardening_{int(time.time())}"

    def _load_config(self, config_path: str = None) -> Dict:
        """Load hardening configuration"""
        default_config = {
            "environment": "production",
            "backup": {
                "enabled": True,
                "directory": "/Users/goodwiinz/development/RAG_system/rag/security/backups",
                "retention_days": 30
            },
            "components": {
                "operating_system": {
                    "enabled": True,
                    "tasks": [
                        "system_updates",
                        "firewall_config",
                        "user_permissions",
                        "ssh_hardening",
                        "file_permissions",
                        "audit_logging"
                    ]
                },
                "docker": {
                    "enabled": True,
                    "tasks": [
                        "docker_security",
                        "container_hardening",
                        "image_scanning",
                        "network_isolation",
                        "resource_limits"
                    ]
                },
                "database": {
                    "enabled": True,
                    "tasks": [
                        "postgres_security",
                        "connection_encryption",
                        "access_controls",
                        "audit_logging",
                        "backup_encryption"
                    ]
                },
                "web_server": {
                    "enabled": True,
                    "tasks": [
                        "tls_configuration",
                        "security_headers",
                        "rate_limiting",
                        "access_controls",
                        "error_handling"
                    ]
                },
                "application": {
                    "enabled": True,
                    "tasks": [
                        "env_hardening",
                        "dependency_updates",
                        "session_security",
                        "input_validation",
                        "error_logging"
                    ]
                },
                "network": {
                    "enabled": True,
                    "tasks": [
                        "port_security",
                        "network_isolation",
                        "dns_security",
                        "proxy_config"
                    ]
                },
                "encryption": {
                    "enabled": True,
                    "tasks": [
                        "ssl_certificates",
                        "data_encryption",
                        "key_management",
                        "backup_encryption"
                    ]
                },
                "monitoring": {
                    "enabled": True,
                    "tasks": [
                        "security_monitoring",
                        "log_aggregation",
                        "alert_systems",
                        "audit_trails"
                    ]
                }
            },
            "security_settings": {
                "password_policy": {
                    "min_length": 12,
                    "require_uppercase": True,
                    "require_lowercase": True,
                    "require_numbers": True,
                    "require_special": True,
                    "max_age_days": 90,
                    "history_count": 12
                },
                "ssl_settings": {
                    "min_version": "TLSv1.2",
                    "cipher_suites": [
                        "TLS_AES_256_GCM_SHA384",
                        "TLS_CHACHA20_POLY1305_SHA256",
                        "TLS_AES_128_GCM_SHA256"
                    ],
                    "certificate_validity_days": 365
                },
                "firewall_rules": {
                    "allowed_ports": [22, 80, 443, 8000],
                    "blocked_ports": [23, 135, 139, 445],
                    "rate_limits": {
                        "ssh": 5,
                        "web": 100
                    }
                }
            },
            "validation": {
                "enabled": True,
                "retry_attempts": 3,
                "timeout_seconds": 30
            },
            "reporting": {
                "output_dir": "/Users/goodwiinz/development/RAG_system/rag/security/reports",
                "formats": ["json", "html", "csv"]
            }
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                # Deep merge configurations
                self._deep_merge(default_config, user_config)

        return default_config

    def _deep_merge(self, base: Dict, override: Dict):
        """Deep merge two dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def create_hardening_tasks(self):
        """Create hardening tasks based on configuration"""
        logger.info("Creating hardening tasks")

        # Operating System Hardening
        if self.config['components']['operating_system']['enabled']:
            self._create_os_tasks()

        # Docker Hardening
        if self.config['components']['docker']['enabled']:
            self._create_docker_tasks()

        # Database Hardening
        if self.config['components']['database']['enabled']:
            self._create_database_tasks()

        # Web Server Hardening
        if self.config['components']['web_server']['enabled']:
            self._create_web_server_tasks()

        # Application Hardening
        if self.config['components']['application']['enabled']:
            self._create_application_tasks()

        # Network Hardening
        if self.config['components']['network']['enabled']:
            self._create_network_tasks()

        # Encryption Hardening
        if self.config['components']['encryption']['enabled']:
            self._create_encryption_tasks()

        # Monitoring Hardening
        if self.config['components']['monitoring']['enabled']:
            self._create_monitoring_tasks()

        logger.info(f"Created {len(self.tasks)} hardening tasks")

    def _create_os_tasks(self):
        """Create operating system hardening tasks"""
        tasks = [
            HardeningTask(
                id="os_system_updates",
                title="Update System Packages",
                description="Update all system packages to latest secure versions",
                component=SystemComponent.OPERATING_SYSTEM,
                severity="critical",
                status=HardeningStatus.PENDING,
                command="sudo apt update && sudo apt upgrade -y",
                config_file=None,
                backup_file=None,
                validation_command="apt list --upgradable",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="os_firewall_config",
                title="Configure Firewall",
                description="Configure UFW firewall with security rules",
                component=SystemComponent.OPERATING_SYSTEM,
                severity="critical",
                status=HardeningStatus.PENDING,
                command="sudo ufw --force enable && sudo ufw default deny incoming && sudo ufw default allow outgoing",
                config_file="/etc/ufw/user.rules",
                backup_file="/etc/ufw/user.rules.backup",
                validation_command="sudo ufw status verbose",
                rollback_command="sudo ufw --force disable",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="os_ssh_hardening",
                title="Harden SSH Configuration",
                description="Secure SSH server configuration",
                component=SystemComponent.OPERATING_SYSTEM,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file="/etc/ssh/sshd_config",
                backup_file="/etc/ssh/sshd_config.backup",
                validation_command="sshd -t",
                rollback_command="sudo cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="os_file_permissions",
                title="Secure File Permissions",
                description="Set secure file permissions on critical system files",
                component=SystemComponent.OPERATING_SYSTEM,
                severity="medium",
                status=HardeningStatus.PENDING,
                command="sudo chmod 600 /etc/shadow && sudo chmod 644 /etc/passwd && sudo chmod 600 /etc/ssh/sshd_config",
                config_file=None,
                backup_file=None,
                validation_command="ls -la /etc/shadow /etc/passwd /etc/ssh/sshd_config",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="os_audit_logging",
                title="Enable Audit Logging",
                description="Configure comprehensive audit logging",
                component=SystemComponent.OPERATING_SYSTEM,
                severity="medium",
                status=HardeningStatus.PENDING,
                command="sudo systemctl enable auditd && sudo systemctl start auditd",
                config_file="/etc/audit/rules.d/audit.rules",
                backup_file="/etc/audit/rules.d/audit.rules.backup",
                validation_command="sudo systemctl status auditd",
                rollback_command="sudo systemctl stop auditd",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    def _create_docker_tasks(self):
        """Create Docker hardening tasks"""
        tasks = [
            HardeningTask(
                id="docker_daemon_config",
                title="Secure Docker Daemon",
                description="Configure Docker daemon security settings",
                component=SystemComponent.DOCKER,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file="/etc/docker/daemon.json",
                backup_file="/etc/docker/daemon.json.backup",
                validation_command="docker info",
                rollback_command="sudo systemctl restart docker",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="docker_user_removal",
                title="Remove Docker from sudo Group",
                description="Remove Docker from sudo group for security",
                component=SystemComponent.DOCKER,
                severity="high",
                status=HardeningStatus.PENDING,
                command="sudo deluser $USER docker",
                config_file=None,
                backup_file=None,
                validation_command="groups $USER",
                rollback_command="sudo usermod -aG docker $USER",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="docker_network_isolation",
                title="Configure Docker Network Isolation",
                description="Configure Docker networks for isolation",
                component=SystemComponent.DOCKER,
                severity="medium",
                status=HardeningStatus.PENDING,
                command="docker network create --driver bridge secure_network",
                config_file=None,
                backup_file=None,
                validation_command="docker network ls",
                rollback_command="docker network rm secure_network",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    def _create_database_tasks(self):
        """Create database hardening tasks"""
        tasks = [
            HardeningTask(
                id="db_password_policy",
                title="Enforce Database Password Policy",
                description="Configure strong password policy for PostgreSQL",
                component=SystemComponent.DATABASE,
                severity="critical",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file="/etc/postgresql/13/main/pg_hba.conf",
                backup_file="/etc/postgresql/13/main/pg_hba.conf.backup",
                validation_command="sudo -u postgres psql -c '\\l'",
                rollback_command="sudo cp /etc/postgresql/13/main/pg_hba.conf.backup /etc/postgresql/13/main/pg_hba.conf",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="db_ssl_configuration",
                title="Configure Database SSL",
                description="Enable SSL encryption for database connections",
                component=SystemComponent.DATABASE,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file="/etc/postgresql/13/main/postgresql.conf",
                backup_file="/etc/postgresql/13/main/postgresql.conf.backup",
                validation_command="sudo -u postgres psql -c 'SHOW ssl;'",
                rollback_command="sudo systemctl restart postgresql",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="db_access_controls",
                title="Configure Database Access Controls",
                description="Implement role-based access control in PostgreSQL",
                component=SystemComponent.DATABASE,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command="sudo -u postgres psql -c '\\du'",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    def _create_web_server_tasks(self):
        """Create web server hardening tasks"""
        tasks = [
            HardeningTask(
                id="web_tls_config",
                title="Configure TLS Encryption",
                description="Configure strong TLS encryption for web services",
                component=SystemComponent.WEB_SERVER,
                severity="critical",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command="openssl s_client -connect localhost:443 -showcerts",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="web_security_headers",
                title="Implement Security Headers",
                description="Add security headers to web application",
                component=SystemComponent.WEB_SERVER,
                severity="medium",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command="curl -I http://localhost:8000",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="web_rate_limiting",
                title="Configure Rate Limiting",
                description="Implement rate limiting for API endpoints",
                component=SystemComponent.WEB_SERVER,
                severity="medium",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command="ab -n 100 -c 10 http://localhost:8000/",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    def _create_application_tasks(self):
        """Create application hardening tasks"""
        tasks = [
            HardeningTask(
                id="app_env_hardening",
                title="Harden Environment Configuration",
                description="Secure environment variables and configuration",
                component=SystemComponent.APPLICATION,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file="/Users/goodwiinz/development/RAG_system/rag/.env",
                backup_file="/Users/goodwiinz/development/RAG_system/rag/.env.backup",
                validation_command="grep -E 'SECRET_KEY|DATABASE_URL' .env",
                rollback_command="cp /Users/goodwiinz/development/RAG_system/rag/.env.backup /Users/goodwiinz/development/RAG_system/rag/.env",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="app_session_security",
                title="Secure Session Management",
                description="Configure secure session settings",
                component=SystemComponent.APPLICATION,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command=None,
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="app_dependency_updates",
                title="Update Dependencies",
                description="Update all application dependencies to secure versions",
                component=SystemComponent.APPLICATION,
                severity="high",
                status=HardeningStatus.PENDING,
                command="pip install --upgrade -r requirements.txt && npm audit fix",
                config_file=None,
                backup_file=None,
                validation_command="pip list && npm audit",
                rollback_command="git checkout requirements.txt package-lock.json",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    def _create_network_tasks(self):
        """Create network hardening tasks"""
        tasks = [
            HardeningTask(
                id="net_port_security",
                title="Secure Network Ports",
                description="Close unnecessary network ports and services",
                component=SystemComponent.NETWORK,
                severity="high",
                status=HardeningStatus.PENDING,
                command="sudo netstat -tulpn | grep LISTEN",
                config_file=None,
                backup_file=None,
                validation_command="sudo netstat -tulpn | grep LISTEN",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="net_dns_security",
                title="Configure DNS Security",
                description="Configure secure DNS settings",
                component=SystemComponent.NETWORK,
                severity="medium",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file="/etc/resolv.conf",
                backup_file="/etc/resolv.conf.backup",
                validation_command="nslookup google.com",
                rollback_command="sudo cp /etc/resolv.conf.backup /etc/resolv.conf",
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    def _create_encryption_tasks(self):
        """Create encryption hardening tasks"""
        tasks = [
            HardeningTask(
                id="enc_ssl_certificates",
                title="Generate SSL Certificates",
                description="Generate and configure SSL certificates",
                component=SystemComponent.ENCRYPTION,
                severity="critical",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command="openssl x509 -in /etc/ssl/certs/rag.crt -text -noout",
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="enc_data_encryption",
                title="Configure Data Encryption",
                description="Configure data-at-rest encryption",
                component=SystemComponent.ENCRYPTION,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command=None,
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="enc_key_management",
                title="Setup Key Management",
                description="Configure secure key management system",
                component=SystemComponent.ENCRYPTION,
                severity="high",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command=None,
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    def _create_monitoring_tasks(self):
        """Create monitoring hardening tasks"""
        tasks = [
            HardeningTask(
                id="mon_security_monitoring",
                title="Configure Security Monitoring",
                description="Setup security monitoring and alerting",
                component=SystemComponent.MONITORING,
                severity="medium",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command=None,
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            ),
            HardeningTask(
                id="mon_log_aggregation",
                title="Configure Log Aggregation",
                description="Setup centralized log aggregation",
                component=SystemComponent.MONITORING,
                severity="medium",
                status=HardeningStatus.PENDING,
                command=None,  # Will be generated dynamically
                config_file=None,
                backup_file=None,
                validation_command=None,
                rollback_command=None,
                dependencies=[],
                execution_time=None,
                error_message=None,
                completed_at=None
            )
        ]

        self.tasks.extend(tasks)

    async def execute_hardening_plan(self):
        """Execute the complete hardening plan"""
        logger.info(f"Starting security hardening execution: {self.session_id}")

        try:
            # Sort tasks by severity and dependencies
            sorted_tasks = self._sort_tasks_by_priority()

            for task in sorted_tasks:
                await self._execute_task(task)

            # Generate reports
            await self._generate_hardening_report()

            logger.info("Security hardening completed successfully")
            return True

        except Exception as e:
            logger.error(f"Security hardening failed: {e}")
            return False

    def _sort_tasks_by_priority(self) -> List[HardeningTask]:
        """Sort tasks by severity and dependencies"""
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

        # Sort by severity first
        tasks_by_severity = sorted(
            self.tasks,
            key=lambda t: (severity_order.get(t.severity, 4), len(t.dependencies))
        )

        # Topological sort for dependencies
        sorted_tasks = []
        visited = set()

        def visit(task):
            if task.id in visited:
                return
            visited.add(task.id)

            # Visit dependencies first
            for dep_id in task.dependencies:
                dep_task = next((t for t in self.tasks if t.id == dep_id), None)
                if dep_task:
                    visit(dep_task)

            sorted_tasks.append(task)

        for task in tasks_by_severity:
            visit(task)

        return sorted_tasks

    async def _execute_task(self, task: HardeningTask):
        """Execute a single hardening task"""
        logger.info(f"Executing task: {task.title}")
        task.status = HardeningStatus.IN_PROGRESS

        try:
            # Create backup if needed
            if task.config_file and task.backup_file:
                await self._create_backup(task.config_file, task.backup_file)

            # Generate command if needed
            if not task.command:
                task.command = await self._generate_command(task)

            # Execute the hardening command
            if task.command:
                start_time = time.time()
                result = await self._run_command(task.command)
                task.execution_time = time.time() - start_time

                if result['returncode'] == 0:
                    # Validate the task
                    if await self._validate_task(task):
                        task.status = HardeningStatus.COMPLETED
                        task.completed_at = datetime.now(timezone.utc)
                        logger.info(f"Task completed successfully: {task.title}")
                    else:
                        task.status = HardeningStatus.FAILED
                        task.error_message = "Validation failed"
                        await self._rollback_task(task)
                        logger.error(f"Task validation failed: {task.title}")
                else:
                    task.status = HardeningStatus.FAILED
                    task.error_message = result['stderr']
                    await self._rollback_task(task)
                    logger.error(f"Task execution failed: {task.title} - {result['stderr']}")
            else:
                # Handle tasks without commands (e.g., certificate generation)
                if await self._execute_special_task(task):
                    task.status = HardeningStatus.COMPLETED
                    task.completed_at = datetime.now(timezone.utc)
                    logger.info(f"Special task completed: {task.title}")
                else:
                    task.status = HardeningStatus.FAILED
                    task.error_message = "Special task execution failed"
                    logger.error(f"Special task failed: {task.title}")

        except Exception as e:
            task.status = HardeningStatus.FAILED
            task.error_message = str(e)
            await self._rollback_task(task)
            logger.error(f"Task execution failed: {task.title} - {e}")

        # Log execution
        self.execution_log.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'task_id': task.id,
            'task_title': task.title,
            'status': task.status.value,
            'execution_time': task.execution_time,
            'error_message': task.error_message
        })

    async def _create_backup(self, source_file: str, backup_file: str):
        """Create backup of configuration file"""
        try:
            if os.path.exists(source_file):
                backup_path = self.backup_dir / os.path.basename(backup_file)
                shutil.copy2(source_file, backup_path)
                logger.info(f"Backup created: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to create backup for {source_file}: {e}")

    async def _generate_command(self, task: HardeningTask) -> Optional[str]:
        """Generate command for specific tasks"""
        if task.id == "os_ssh_hardening":
            return self._generate_ssh_hardening_command()
        elif task.id == "docker_daemon_config":
            return self._generate_docker_daemon_command()
        elif task.id == "db_password_policy":
            return self._generate_db_password_command()
        elif task.id == "db_ssl_configuration":
            return self._generate_db_ssl_command()
        elif task.id == "db_access_controls":
            return self._generate_db_access_command()
        elif task.id == "app_env_hardening":
            return self._generate_app_env_command()
        elif task.id == "app_session_security":
            return self._generate_app_session_command()
        elif task.id == "net_dns_security":
            return self._generate_dns_security_command()
        elif task.id == "enc_ssl_certificates":
            return None  # Special task
        elif task.id == "enc_data_encryption":
            return self._generate_data_encryption_command()
        elif task.id == "enc_key_management":
            return self._generate_key_management_command()
        elif task.id == "mon_security_monitoring":
            return self._generate_monitoring_command()
        elif task.id == "mon_log_aggregation":
            return self._generate_log_aggregation_command()
        else:
            return task.command

    def _generate_ssh_hardening_command(self) -> str:
        """Generate SSH hardening commands"""
        ssh_config = """
# Disable root login
PermitRootLogin no

# Disable password authentication
PasswordAuthentication no

# Enable key-based authentication
PubkeyAuthentication yes

# Disable empty passwords
PermitEmptyPasswords no

# Set protocol to 2 only
Protocol 2

# Disable X11 forwarding
X11Forwarding no

# Set maximum authentication attempts
MaxAuthTries 3

# Set login grace time
LoginGraceTime 60

# Disable forwarding
AllowTcpForwarding no

# Set banner
Banner /etc/ssh/banner.txt
"""
        return f"echo '{ssh_config}' > /tmp/sshd_config && sudo cp /tmp/sshd_config /etc/ssh/sshd_config && sudo systemctl restart sshd"

    def _generate_docker_daemon_command(self) -> str:
        """Generate Docker daemon configuration command"""
        docker_config = {
            "live-restore": True,
            "userland-proxy": False,
            "no-new-privileges": True,
            "seccomp-profile": "/etc/docker/seccomp.json",
            "log-driver": "json-file",
            "log-opts": {
                "max-size": "10m",
                "max-file": "3"
            },
            "storage-driver": "overlay2",
            "default-ulimits": {
                "nofile": {
                    "Name": "nofile",
                    "Hard": 64000,
                    "Soft": 64000
                }
            }
        }

        config_json = json.dumps(docker_config, indent=2)
        return f"echo '{config_json}' > /tmp/daemon.json && sudo cp /tmp/daemon.json /etc/docker/daemon.json && sudo systemctl restart docker"

    def _generate_db_password_command(self) -> str:
        """Generate database password configuration command"""
        hba_config = """
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             postgres                                md5
local   all             all                                     md5

# IPv4 local connections:
host    all             all             127.0.0.1/32            md5

# IPv6 local connections:
host    all             all             ::1/128                 md5

# Require SSL for remote connections
hostssl all             all             0.0.0.0/0               md5
"""
        return f"echo '{hba_config}' > /tmp/pg_hba.conf && sudo cp /tmp/pg_hba.conf /etc/postgresql/13/main/pg_hba.conf && sudo systemctl restart postgresql"

    def _generate_db_ssl_command(self) -> str:
        """Generate database SSL configuration command"""
        ssl_config = """
# SSL Configuration
ssl = on
ssl_cert_file = '/etc/ssl/certs/rag.crt'
ssl_key_file = '/etc/ssl/private/rag.key'
ssl_ca_file = '/etc/ssl/certs/ca.crt'
ssl_ciphers = 'HIGH:MEDIUM:+3DES:!aNULL:!SSLv2:!SSLv3'
ssl_prefer_server_ciphers = on
ssl_ecdh_curve = 'prime256v1'
"""
        return f"echo '{ssl_config}' >> /etc/postgresql/13/main/postgresql.conf && sudo systemctl restart postgresql"

    def _generate_db_access_command(self) -> str:
        """Generate database access control command"""
        commands = [
            "sudo -u postgres createuser --no-createrole --no-superuser --no-createdb rag_user",
            "sudo -u postgres createdb --owner rag_user rag_db",
            "sudo -u postgres psql -c \"ALTER USER rag_user WITH PASSWORD '$(openssl rand -base64 32)';\""
        ]
        return " && ".join(commands)

    def _generate_app_env_command(self) -> str:
        """Generate application environment hardening command"""
        secure_env = {
            "DEBUG": "False",
            "SECRET_KEY": f"$(openssl rand -hex 64)",
            "ALLOWED_HOSTS": "localhost,127.0.0.1",
            "CORS_ALLOWED_ORIGINS": "http://localhost:3000",
            "SESSION_COOKIE_SECURE": "True",
            "SESSION_COOKIE_HTTPONLY": "True",
            "CSRF_COOKIE_SECURE": "True",
            "SECURE_SSL_REDIRECT": "True",
            "SECURE_HSTS_SECONDS": "31536000",
            "SECURE_HSTS_INCLUDE_SUBDOMAINS": "True",
            "SECURE_HSTS_PRELOAD": "True"
        }

        env_commands = []
        for key, value in secure_env.items():
            env_commands.append(f"sed -i 's/^{key}=.*/{key}={value}/' .env")

        return " && ".join(env_commands)

    def _generate_app_session_command(self) -> str:
        """Generate application session security command"""
        return "echo 'SESSION_ENGINE=django.contrib.sessions.backends.cache' >> .env && echo 'SESSION_CACHE_ALIAS=default' >> .env"

    def _generate_dns_security_command(self) -> str:
        """Generate DNS security configuration command"""
        dns_config = """
# Google DNS with DNSSEC validation
nameserver 8.8.8.8
nameserver 8.8.4.4
options timeout:2
options attempts:3
options rotate
"""
        return f"echo '{dns_config}' > /tmp/resolv.conf && sudo cp /tmp/resolv.conf /etc/resolv.conf"

    def _generate_data_encryption_command(self) -> str:
        """Generate data encryption command"""
        return "mkdir -p /etc/rag/keys && openssl rand -base64 32 > /etc/rag/keys/data_key.txt && chmod 600 /etc/rag/keys/data_key.txt"

    def _generate_key_management_command(self) -> str:
        """Generate key management command"""
        return "chmod 700 /etc/rag/keys && chown rag:rag /etc/rag/keys"

    def _generate_monitoring_command(self) -> str:
        """Generate monitoring setup command"""
        return "docker run -d --name security-monitor -p 9090:9090 prom/prometheus --config.file=/etc/prometheus/prometheus.yml"

    def _generate_log_aggregation_command(self) -> str:
        """Generate log aggregation command"""
        return "docker run -d --name log-aggregator -p 514:514/udp -p 5044:5044 docker.elastic.co/logstash/logstash:7.15.0"

    async def _execute_special_task(self, task: HardeningTask) -> bool:
        """Execute special tasks like certificate generation"""
        if task.id == "enc_ssl_certificates":
            return await self._generate_ssl_certificates()
        else:
            return False

    async def _generate_ssl_certificates(self) -> bool:
        """Generate SSL certificates"""
        try:
            # Create certificate directory
            cert_dir = Path("/etc/ssl/certs")
            key_dir = Path("/etc/ssl/private")
            cert_dir.mkdir(exist_ok=True)
            key_dir.mkdir(exist_ok=True)

            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )

            # Generate certificate
            subject = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "RAG System"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])

            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                subject
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.now(timezone.utc)
            ).not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=self.config['security_settings']['ssl_settings']['certificate_validity_days'])
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())

            # Save certificate and key
            cert_path = cert_dir / "rag.crt"
            key_path = key_dir / "rag.key"

            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # Set proper permissions
            os.chmod(key_path, 0o600)
            os.chmod(cert_path, 0o644)

            logger.info("SSL certificates generated successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to generate SSL certificates: {e}")
            return False

    async def _run_command(self, command: str) -> Dict:
        """Run a shell command"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config['validation']['timeout_seconds']
            )

            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out'
            }

    async def _validate_task(self, task: HardeningTask) -> bool:
        """Validate task execution"""
        if not task.validation_command:
            return True

        try:
            result = await self._run_command(task.validation_command)
            return result['returncode'] == 0
        except Exception as e:
            logger.warning(f"Task validation failed: {e}")
            return False

    async def _rollback_task(self, task: HardeningTask):
        """Rollback failed task"""
        logger.info(f"Rolling back task: {task.title}")

        try:
            if task.rollback_command:
                await self._run_command(task.rollback_command)

            if task.backup_file and os.path.exists(task.backup_file):
                backup_path = self.backup_dir / os.path.basename(task.backup_file)
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, task.config_file)
                    logger.info(f"Restored backup: {task.config_file}")

        except Exception as e:
            logger.error(f"Rollback failed for task {task.title}: {e}")

    async def _generate_hardening_report(self):
        """Generate hardening execution report"""
        report_dir = Path(self.config['reporting']['output_dir'])
        report_dir.mkdir(parents=True, exist_ok=True)

        # Calculate statistics
        completed_tasks = len([t for t in self.tasks if t.status == HardeningStatus.COMPLETED])
        failed_tasks = len([t for t in self.tasks if t.status == HardeningStatus.FAILED])
        total_execution_time = sum(t.execution_time or 0 for t in self.tasks)

        # Generate JSON report
        report_data = {
            'session_id': self.session_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': self.config['environment'],
            'summary': {
                'total_tasks': len(self.tasks),
                'completed_tasks': completed_tasks,
                'failed_tasks': failed_tasks,
                'success_rate': (completed_tasks / len(self.tasks) * 100) if self.tasks else 0,
                'total_execution_time': total_execution_time
            },
            'tasks': [asdict(task) for task in self.tasks],
            'execution_log': self.execution_log,
            'configuration': self.config
        }

        # Convert datetime objects
        for task in report_data['tasks']:
            if task.get('completed_at'):
                task['completed_at'] = task['completed_at'].isoformat()
            task['status'] = task['status'].value
            task['component'] = task['component'].value

        # Save JSON report
        json_path = report_dir / f"hardening_report_{self.session_id}.json"
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        # Generate HTML report
        await self._generate_html_report(report_dir, report_data)

        logger.info(f"Hardening report generated: {json_path}")

    async def _generate_html_report(self, report_dir: Path, report_data: Dict):
        """Generate HTML hardening report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Security Hardening Report - {self.session_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; padding: 20px; background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; border-radius: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
        .metric {{ background-color: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #28a745; }}
        .metric.failed {{ border-left-color: #dc3545; }}
        .task {{ border: 1px solid #dee2e6; margin: 20px 0; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .task-header {{ padding: 15px 20px; color: white; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }}
        .task-header.completed {{ background-color: #28a745; }}
        .task-header.failed {{ background-color: #dc3545; }}
        .task-header.pending {{ background-color: #6c757d; }}
        .task-body {{ padding: 20px; }}
        .execution-log {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ Security Hardening Report</h1>
            <p>Session ID: {self.session_id}</p>
            <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>

        <div class="summary">
            <div class="metric">
                <h3>Total Tasks</h3>
                <h2>{len(self.tasks)}</h2>
            </div>
            <div class="metric">
                <h3>Completed</h3>
                <h2>{len([t for t in self.tasks if t.status == HardeningStatus.COMPLETED])}</h2>
            </div>
            <div class="metric failed">
                <h3>Failed</h3>
                <h2>{len([t for t in self.tasks if t.status == HardeningStatus.FAILED])}</h2>
            </div>
            <div class="metric">
                <h3>Success Rate</h3>
                <h2>{(len([t for t in self.tasks if t.status == HardeningStatus.COMPLETED]) / len(self.tasks) * 100) if self.tasks else 0:.1f}%</h2>
            </div>
            <div class="metric">
                <h3>Total Time</h3>
                <h2>{sum(t.execution_time or 0 for t in self.tasks):.1f}s</h2>
            </div>
        </div>

        <h2>Task Details</h2>
"""

        for task in self.tasks:
            status_class = task.status.value
            html_content += f"""
        <div class="task">
            <div class="task-header {status_class}">
                <div>
                    <div>{task.title}</div>
                    <div>{task.component.value} - {task.severity}</div>
                </div>
                <div>{task.status.value.upper()}</div>
            </div>
            <div class="task-body">
                <p><strong>Description:</strong> {task.description}</p>
                <p><strong>Component:</strong> {task.component.value}</p>
                <p><strong>Severity:</strong> {task.severity}</p>
                {f'<p><strong>Execution Time:</strong> {task.execution_time:.2f}s</p>' if task.execution_time else ''}
                {f'<p><strong>Completed:</strong> {task.completed_at.strftime("%Y-%m-%d %H:%M:%S") if task.completed_at else "N/A"}</p>' if task.completed_at else ''}
                {f'<div class="execution-log"><strong>Command:</strong><br>{task.command}</div>' if task.command else ''}
                {f'<div class="execution-log"><strong>Error:</strong><br>{task.error_message}</div>' if task.error_message else ''}
            </div>
        </div>
"""

        html_content += """
    </div>
</body>
</html>
"""

        html_path = report_dir / f"hardening_report_{self.session_id}.html"
        with open(html_path, 'w') as f:
            f.write(html_content)

        logger.info(f"HTML hardening report generated: {html_path}")


async def main():
    """Main function to run security hardening"""
    # Create output directories
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/logs", exist_ok=True)
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/backups", exist_ok=True)
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/reports", exist_ok=True)

    # Initialize hardening suite
    suite = SecurityHardeningSuite()

    # Create hardening tasks
    suite.create_hardening_tasks()

    # Execute hardening plan
    success = await suite.execute_hardening_plan()

    # Print summary
    completed = len([t for t in suite.tasks if t.status == HardeningStatus.COMPLETED])
    failed = len([t for t in suite.tasks if t.status == HardeningStatus.FAILED])

    print(f"\n🛡️ Security Hardening Complete")
    print(f"📊 Total Tasks: {len(suite.tasks)}")
    print(f"✅ Completed: {completed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(completed / len(suite.tasks) * 100) if suite.tasks else 0:.1f}%")

    if success:
        print("\n✅ Security hardening completed successfully")
        exit(0)
    else:
        print("\n❌ Security hardening encountered errors")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())