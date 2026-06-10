"""
User Factory for Test Data Generation
Creates realistic test users, roles, and related entities
"""

import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from faker import Faker

# Import models
from src.models.user import User, UserRole
from src.models.organization import Organization, StorageTier


# Initialize Faker for realistic data generation
fake = Faker()


@dataclass
class UserConfig:
    """Configuration for user generation"""
    id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_email_verified: bool = True
    organization_id: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    password_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrganizationConfig:
    """Configuration for organization generation"""
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    storage_tier: StorageTier = StorageTier.FREE
    is_active: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)
    billing_email: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserFactory:
    """Factory for creating test users and related entities"""

    # Role configurations with realistic permissions
    ROLE_CONFIGS = {
        UserRole.SUPER_ADMIN: {
            'permissions': ['*'],
            'description': 'Full system access',
        },
        UserRole.ADMIN: {
            'permissions': [
                'organization_read', 'organization_update', 'user_manage',
                'document_manage', 'analytics_read', 'analytics_export',
                'billing_manage', 'settings_manage', 'api_manage'
            ],
            'description': 'Organization administrator',
        },
        UserRole.CONTENT_MANAGER: {
            'permissions': [
                'organization_read', 'document_create', 'document_update',
                'document_delete', 'document_share', 'quality_manage'
            ],
            'description': 'Manages content and documents',
        },
        UserRole.ANALYST: {
            'permissions': [
                'organization_read', 'document_read', 'analytics_read',
                'analytics_export', 'search_advanced', 'report_create'
            ],
            'description': 'Data analyst with read access',
        },
        UserRole.USER: {
            'permissions': [
                'organization_read', 'document_read', 'document_create',
                'search_basic', 'profile_manage'
            ],
            'description': 'Standard user',
        },
        UserRole.VIEWER: {
            'permissions': [
                'organization_read', 'document_read', 'search_basic'
            ],
            'description': 'Read-only access',
        },
    }

    @classmethod
    def create_user(cls, config: Optional[UserConfig] = None) -> User:
        """
        Create a single test user with realistic data
        
        Args:
            config: User configuration overrides
            
        Returns:
            User instance with test data
        """
        if config is None:
            config = UserConfig()

        # Generate basic info
        first_name = config.first_name or fake.first_name()
        last_name = config.last_name or fake.last_name()
        name = config.name or f"{first_name} {last_name}"
        email = config.email or fake.email()
        
        # Generate timestamps
        now = datetime.now(timezone.utc)
        created_at = config.created_at or now - timedelta(days=random.randint(1, 365))
        updated_at = config.updated_at or created_at + timedelta(days=random.randint(1, 30))
        last_login_at = config.last_login_at or now - timedelta(days=random.randint(0, 30))
        
        # Generate metadata
        if not config.metadata:
            config.metadata = cls._generate_user_metadata(config.role)
        
        # Create user instance
        user = User(
            id=config.id or str(uuid.uuid4()),
            email=email,
            name=name,
            first_name=first_name,
            last_name=last_name,
            role=config.role,
            is_active=config.is_active,
            is_email_verified=config.is_email_verified,
            organization_id=config.organization_id or str(uuid.uuid4()),
            phone=config.phone or fake.phone_number(),
            avatar_url=config.avatar_url or f"https://api.dicebear.com/7.x/avataaars/svg?seed={email}",
            bio=config.bio or fake.sentence(),
            timezone=config.timezone,
            language=config.language,
            created_at=created_at,
            updated_at=updated_at,
            last_login_at=last_login_at,
            password_hash=config.password_hash or "hashed_password_placeholder",
            metadata=config.metadata
        )
        
        return user
    
    @classmethod
    def create_batch_users(cls, count: int, config: Optional[UserConfig] = None) -> List[User]:
        """
        Create multiple test users
        
        Args:
            count: Number of users to create
            config: Base configuration for all users
            
        Returns:
            List of User instances
        """
        users = []
        
        for i in range(count):
            user_config = UserConfig() if config is None else UserConfig(**config.__dict__)
            
            # Add variation
            if config is None:
                user_config.role = random.choice(list(UserRole))
                user_config.is_active = random.choice([True, True, True, False])  # 75% active
            
            user = cls.create_user(user_config)
            users.append(user)
        
        return users
    
    @classmethod
    def create_users_for_organization(cls, org_id: str, count: int = 5) -> List[User]:
        """
        Create a realistic set of users for an organization
        
        Args:
            org_id: Organization ID
            count: Number of users (default creates 1 admin, 1 content_manager, 1 analyst, 2 users, 1 viewer)
            
        Returns:
            List of User instances
        """
        default_roles = [
            UserRole.ADMIN,
            UserRole.CONTENT_MANAGER,
            UserRole.ANALYST,
            UserRole.USER,
            UserRole.USER,
            UserRole.VIEWER,
        ]
        
        users = []
        for i in range(min(count, len(default_roles))):
            config = UserConfig(
                organization_id=org_id,
                role=default_roles[i]
            )
            user = cls.create_user(config)
            users.append(user)
        
        # Add remaining users with random roles
        for i in range(len(default_roles), count):
            config = UserConfig(
                organization_id=org_id,
                role=random.choice([UserRole.USER, UserRole.VIEWER, UserRole.ANALYST])
            )
            user = cls.create_user(config)
            users.append(user)
        
        return users
    
    @classmethod
    def _generate_user_metadata(cls, role: UserRole) -> Dict[str, Any]:
        """Generate realistic user metadata based on role"""
        base_metadata = {
            'login_count': random.randint(1, 500),
            'total_documents_uploaded': random.randint(0, 100),
            'total_searches': random.randint(0, 1000),
            'total_api_calls': random.randint(0, 5000),
            'preferred_theme': random.choice(['light', 'dark', 'system']),
            'notification_settings': {
                'email': random.choice([True, False]),
                'push': random.choice([True, False]),
                'slack': random.choice([True, False]),
            },
            'onboarding_completed': True,
            'last_used_features': random.sample(
                ['search', 'upload', 'analytics', 'settings', 'api', 'sharing'],
                k=random.randint(1, 3)
            ),
        }
        
        role_specific_metadata = {
            UserRole.ADMIN: {
                'managed_users_count': random.randint(1, 50),
                'last_audit_log_review': fake.date_time_between(start_date='-30d', end_date='now').isoformat(),
                'security_alerts_enabled': True,
            },
            UserRole.ANALYST: {
                'saved_reports_count': random.randint(0, 20),
                'favorite_dashboards': random.sample(['overview', 'search', 'users', 'documents'], k=random.randint(1, 3)),
                'export_format_preference': random.choice(['pdf', 'csv', 'json', 'xlsx']),
            },
            UserRole.CONTENT_MANAGER: {
                'managed_collections_count': random.randint(1, 10),
                'quality_checks_enabled': random.choice([True, False]),
                'auto_tagging_enabled': random.choice([True, False]),
            },
        }
        
        metadata = {**base_metadata, **role_specific_metadata.get(role, {})}
        return metadata


class OrganizationFactory:
    """Factory for creating test organizations"""
    
    @classmethod
    def create_organization(cls, config: Optional[OrganizationConfig] = None) -> Organization:
        """
        Create a single test organization
        
        Args:
            config: Organization configuration overrides
            
        Returns:
            Organization instance
        """
        if config is None:
            config = OrganizationConfig()
        
        # Generate basic info
        name = config.name or fake.company()
        slug = config.slug or name.lower().replace(' ', '-').replace(',', '').replace('.', '')
        domain = config.domain or f"{slug}.example.com"
        description = config.description or fake.catch_phrase()
        
        # Generate timestamps
        now = datetime.now(timezone.utc)
        created_at = config.created_at or now - timedelta(days=random.randint(1, 730))
        updated_at = config.updated_at or created_at + timedelta(days=random.randint(1, 60))
        
        # Generate settings
        if not config.settings:
            config.settings = cls._generate_organization_settings(config.storage_tier)
        
        # Create organization instance
        organization = Organization(
            id=config.id or str(uuid.uuid4()),
            name=name,
            slug=slug,
            domain=domain,
            description=description,
            storage_tier=config.storage_tier,
            is_active=config.is_active,
            settings=config.settings,
            billing_email=config.billing_email or fake.company_email(),
            created_at=created_at,
            updated_at=updated_at,
        )
        
        return organization
    
    @classmethod
    def create_batch_organizations(cls, count: int, config: Optional[OrganizationConfig] = None) -> List[Organization]:
        """
        Create multiple test organizations
        
        Args:
            count: Number of organizations to create
            config: Base configuration
            
        Returns:
            List of Organization instances
        """
        organizations = []
        
        for i in range(count):
            org_config = OrganizationConfig() if config is None else OrganizationConfig(**config.__dict__)
            
            if config is None:
                org_config.storage_tier = random.choice(list(StorageTier))
                org_config.is_active = random.choice([True, True, True, False])  # 75% active
            
            org = cls.create_organization(org_config)
            organizations.append(org)
        
        return organizations
    
    @classmethod
    def _generate_organization_settings(cls, tier: StorageTier) -> Dict[str, Any]:
        """Generate realistic organization settings based on tier"""
        base_settings = {
            'theme': random.choice(['light', 'dark', 'system']),
            'default_language': random.choice(['en', 'es', 'fr', 'de', 'ja']),
            'date_format': random.choice(['MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD']),
            'time_format': random.choice(['12h', '24h']),
            'timezone': fake.timezone(),
            'notifications': {
                'email_digest': random.choice(['daily', 'weekly', 'never']),
                'security_alerts': True,
                'billing_alerts': True,
            },
            'security': {
                'mfa_required': tier != StorageTier.FREE,
                'password_policy': random.choice(['basic', 'standard', 'strict']),
                'session_timeout_minutes': 30 if tier == StorageTier.FREE else 60,
            },
            'features': {
                'advanced_search': tier != StorageTier.FREE,
                'api_access': tier == StorageTier.ENTERPRISE,
                'custom_integrations': tier == StorageTier.ENTERPRISE,
                'white_label': tier == StorageTier.ENTERPRISE,
                'audit_logs': tier != StorageTier.FREE,
                'sso': tier == StorageTier.ENTERPRISE,
            },
        }
        
        tier_specific_settings = {
            StorageTier.FREE: {
                'max_users': 3,
                'max_documents': 100,
                'max_storage_gb': 5,
                'api_rate_limit': 100,
            },
            StorageTier.PROFESSIONAL: {
                'max_users': 25,
                'max_documents': 5000,
                'max_storage_gb': 100,
                'api_rate_limit': 1000,
                'support_priority': 'standard',
            },
            StorageTier.ENTERPRISE: {
                'max_users': None,
                'max_documents': None,
                'max_storage_gb': None,
                'api_rate_limit': None,
                'support_priority': 'priority',
                'dedicated_support': True,
                'custom_contract': True,
            },
        }
        
        return {**base_settings, **tier_specific_settings.get(tier, {})}


# Convenience functions

def create_test_user_with_org(role: UserRole = UserRole.USER, org_tier: StorageTier = StorageTier.FREE) -> Dict[str, Any]:
    """
    Create a test user with their organization
    
    Args:
        role: User role
        org_tier: Organization storage tier
        
    Returns:
        Dictionary with 'user' and 'organization' keys
    """
    org = OrganizationFactory.create_organization(
        OrganizationConfig(storage_tier=org_tier)
    )
    
    user = UserFactory.create_user(
        UserConfig(organization_id=org.id, role=role)
    )
    
    return {
        'user': user,
        'organization': org,
        'users': UserFactory.create_users_for_organization(org.id, count=5)
    }


def create_test_scenario_full_organization() -> Dict[str, Any]:
    """
    Create a complete test scenario with organization, users, and documents
    
    Returns:
        Dictionary with complete test scenario
    """
    from tests.factories.document_factory import DocumentFactory, DocumentConfig
    
    org = OrganizationFactory.create_organization()
    users = UserFactory.create_users_for_organization(org.id, count=6)
    admin = next(u for u in users if u.role == UserRole.ADMIN)
    
    # Create documents uploaded by different users
    documents = []
    for user in users:
        docs = DocumentFactory.create_batch_documents(
            count=random.randint(1, 5),
            config=DocumentConfig(
                organization_id=org.id,
                uploaded_by_user_id=user.id
            )
        )
        documents.extend(docs)
    
    return {
        'organization': org,
        'users': users,
        'admin': admin,
        'documents': documents,
    }
