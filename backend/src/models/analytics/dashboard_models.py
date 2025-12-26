"""
Dashboard models for analytics dashboards
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, ConfigDict
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, JSON, Integer, ForeignKey,
    Float, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..base import BaseModel as SQLBaseModel, GUID


class DashboardWidgetType(str, Enum):
    """Widget types for dashboards"""
    CHART = "chart"
    METRIC = "metric"
    TABLE = "table"
    GRAPH = "graph"
    MAP = "map"
    TEXT = "text"
    FILTER = "filter"
    GAUGE = "gauge"
    HEATMAP = "heatmap"
    TIMELINE = "timeline"
    HISTOGRAM = "histogram"
    SCATTER = "scatter"
    PIE = "pie"
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    FUNNEL = "funnel"
    SANKEY = "sankey"
    TREEMAP = "treemap"


class DashboardTheme(str, Enum):
    """Dashboard themes"""
    LIGHT = "light"
    DARK = "dark"
    BLUE = "blue"
    GREEN = "green"
    PURPLE = "purple"
    ORANGE = "orange"
    RED = "red"
    CUSTOM = "custom"


class Dashboard(SQLBaseModel):
    """Dashboard model for analytics dashboards"""

    __tablename__ = "analytics_dashboards"

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True, index=True)

    # Layout and configuration
    layout = Column(JSON, nullable=True)  # Grid layout configuration
    theme = Column(SQLEnum(DashboardTheme), default=DashboardTheme.LIGHT, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)

    # Settings
    auto_refresh = Column(Boolean, default=True, nullable=False)
    refresh_interval = Column(Integer, default=30, nullable=False)  # seconds
    timezone = Column(String(50), default="UTC", nullable=False)

    # Metadata
    tags = Column(JSON, nullable=True)  # List of tags
    category = Column(String(100), nullable=True)
    version = Column(String(50), default="1.0.0", nullable=False)

    # Relationships
    widgets = relationship("DashboardWidget", back_populates="dashboard", cascade="all, delete-orphan")
    permissions = relationship("DashboardPermission", back_populates="dashboard", cascade="all, delete-orphan")


class DashboardWidget(SQLBaseModel):
    """Widget model for dashboard widgets"""

    __tablename__ = "analytics_dashboard_widgets"

    dashboard_id = Column(GUID(), ForeignKey("analytics_dashboards.id"), nullable=False, index=True)
    widget_type = Column(SQLEnum(DashboardWidgetType), nullable=False)

    # Widget properties
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Layout and positioning
    x = Column(Integer, default=0, nullable=False)
    y = Column(Integer, default=0, nullable=False)
    width = Column(Integer, default=4, nullable=False)  # Grid units
    height = Column(Integer, default=3, nullable=False)  # Grid units

    # Data configuration
    data_source = Column(String(255), nullable=True)  # Data source identifier
    query_config = Column(JSON, nullable=True)  # Query configuration
    visualization_config = Column(JSON, nullable=True)  # Chart/visualization settings

    # Real-time settings
    is_realtime = Column(Boolean, default=False, nullable=False)
    real_time_config = Column(JSON, nullable=True)  # WebSocket subscription config

    # Filters and interactions
    filters = Column(JSON, nullable=True)  # Widget-specific filters
    drilldown_config = Column(JSON, nullable=True)  # Drill-down configuration

    # Caching
    cache_ttl = Column(Integer, default=300, nullable=False)  # seconds
    cache_key = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_visible = Column(Boolean, default=True, nullable=False)

    # Relationships
    dashboard = relationship("Dashboard", back_populates="widgets")


class DashboardLayout(SQLBaseModel):
    """Dashboard layout configurations"""

    __tablename__ = "analytics_dashboard_layouts"

    dashboard_id = Column(GUID(), ForeignKey("analytics_dashboards.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    layout_type = Column(String(50), default="grid", nullable=False)  # grid, flex, absolute

    # Layout configuration
    config = Column(JSON, nullable=False)  # Layout configuration
    breakpoints = Column(JSON, nullable=True)  # Responsive breakpoints
    constraints = Column(JSON, nullable=True)  # Layout constraints

    # Metadata
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class DashboardPermission(SQLBaseModel):
    """Dashboard permissions for users and roles"""

    __tablename__ = "analytics_dashboard_permissions"

    dashboard_id = Column(GUID(), ForeignKey("analytics_dashboards.id"), nullable=False, index=True)

    # Permission target
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    role_id = Column(GUID(), ForeignKey("permissions.id"), nullable=True, index=True)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True, index=True)

    # Permissions
    can_view = Column(Boolean, default=True, nullable=False)
    can_edit = Column(Boolean, default=False, nullable=False)
    can_delete = Column(Boolean, default=False, nullable=False)
    can_share = Column(Boolean, default=False, nullable=False)
    can_export = Column(Boolean, default=True, nullable=False)

    # Relationships
    dashboard = relationship("Dashboard", back_populates="permissions")


# Pydantic models for API serialization

class WidgetConfiguration(BaseModel):
    """Widget configuration model"""
    widget_type: DashboardWidgetType
    title: str
    description: Optional[str] = None
    x: int = 0
    y: int = 0
    width: int = 4
    height: int = 3
    data_source: Optional[str] = None
    query_config: Optional[Dict[str, Any]] = None
    visualization_config: Optional[Dict[str, Any]] = None
    is_realtime: bool = False
    real_time_config: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    drilldown_config: Optional[Dict[str, Any]] = None
    cache_ttl: int = 300
    is_active: bool = True
    is_visible: bool = True

    model_config = ConfigDict(from_attributes=True)


class DashboardCreate(BaseModel):
    """Create dashboard request model"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    theme: DashboardTheme = DashboardTheme.LIGHT
    is_public: bool = False
    is_template: bool = False
    auto_refresh: bool = True
    refresh_interval: int = Field(default=30, ge=1, le=3600)
    timezone: str = "UTC"
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    widgets: Optional[List[WidgetConfiguration]] = None

    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate timezone"""
        import pytz
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")

    model_config = ConfigDict(from_attributes=True)


class DashboardUpdate(BaseModel):
    """Update dashboard request model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    theme: Optional[DashboardTheme] = None
    is_public: Optional[bool] = None
    auto_refresh: Optional[bool] = None
    refresh_interval: Optional[int] = Field(None, ge=1, le=3600)
    timezone: Optional[str] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None

    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate timezone"""
        if v is None:
            return v
        import pytz
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")

    model_config = ConfigDict(from_attributes=True)


class DashboardResponse(BaseModel):
    """Dashboard response model"""
    id: uuid.UUID
    name: str
    description: Optional[str]
    owner_id: uuid.UUID
    organization_id: Optional[uuid.UUID]
    layout: Optional[Dict[str, Any]]
    theme: DashboardTheme
    is_public: bool
    is_template: bool
    auto_refresh: bool
    refresh_interval: int
    timezone: str
    tags: Optional[List[str]]
    category: Optional[str]
    version: str
    created_at: datetime
    updated_at: datetime
    widget_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class WidgetResponse(BaseModel):
    """Widget response model"""
    id: uuid.UUID
    dashboard_id: uuid.UUID
    widget_type: DashboardWidgetType
    title: str
    description: Optional[str]
    x: int
    y: int
    width: int
    height: int
    data_source: Optional[str]
    query_config: Optional[Dict[str, Any]]
    visualization_config: Optional[Dict[str, Any]]
    is_realtime: bool
    real_time_config: Optional[Dict[str, Any]]
    filters: Optional[Dict[str, Any]]
    drilldown_config: Optional[Dict[str, Any]]
    cache_ttl: int
    is_active: bool
    is_visible: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardWithWidgets(DashboardResponse):
    """Dashboard with widgets included"""
    widgets: List[WidgetResponse]

    model_config = ConfigDict(from_attributes=True)