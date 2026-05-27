"""
Dashboard Management Service for analytics dashboards
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_async_session
from src.models.analytics.dashboard_models import (
    Dashboard,
    DashboardCreate,
    DashboardLayout,
    DashboardPermission,
    DashboardResponse,
    DashboardTheme,
    DashboardUpdate,
    DashboardWidget,
    DashboardWidgetType,
    DashboardWithWidgets,
    WidgetConfiguration,
    WidgetCreate,
    WidgetResponse,
    WidgetUpdate,
)
from src.models.base import GUID

logger = logging.getLogger(__name__)


class DashboardService:
    """Service for managing analytics dashboards"""

    def __init__(self):
        self.default_widget_configs = self._load_default_widget_configs()
        self.max_widgets_per_dashboard = 50
        self.max_dashboard_size_mb = 10

    def _load_default_widget_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load default widget configurations"""
        return {
            "line_chart": {
                "chart_type": "line",
                "x_axis": "timestamp",
                "y_axis": "value",
                "colors": ["#3b82f6", "#10b981", "#f59e0b"],
                "show_legend": True,
                "show_grid": True,
            },
            "bar_chart": {
                "chart_type": "bar",
                "orientation": "vertical",
                "colors": ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"],
                "show_values": True,
            },
            "pie_chart": {
                "chart_type": "pie",
                "show_labels": True,
                "show_percentages": True,
                "colors": ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"],
            },
            "metric_card": {
                "show_trend": True,
                "show_change": True,
                "format": "number",
                "precision": 2,
            },
            "table": {
                "sortable": True,
                "filterable": True,
                "pagination": True,
                "page_size": 10,
            },
        }

    async def create_dashboard(
        self,
        request: DashboardCreate,
        owner_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> DashboardResponse:
        """Create a new analytics dashboard"""
        try:
            async with get_async_session() as db:
                # Create dashboard
                dashboard = Dashboard(
                    name=request.name,
                    description=request.description,
                    owner_id=owner_id,
                    organization_id=organization_id,
                    layout=request.layout,
                    theme=request.theme,
                    is_public=request.is_public,
                    is_template=request.is_template,
                    auto_refresh=request.auto_refresh,
                    refresh_interval=request.refresh_interval,
                    timezone=request.timezone,
                    tags=request.tags,
                    category=request.category,
                )
                db.add(dashboard)
                await db.commit()
                await db.refresh(dashboard)

                # Create widgets if provided
                if request.widgets:
                    await self._create_widgets_for_dashboard(
                        db, dashboard.id, request.widgets
                    )

                # Give owner full permissions
                permission = DashboardPermission(
                    dashboard_id=dashboard.id,
                    user_id=owner_id,
                    can_view=True,
                    can_edit=True,
                    can_delete=True,
                    can_share=True,
                    can_export=True,
                )
                db.add(permission)
                await db.commit()

                # Get dashboard with widget count
                dashboard_response = await self._get_dashboard_with_count(
                    db, dashboard.id
                )
                return dashboard_response

        except Exception as e:
            logger.error(f"Error creating dashboard: {e}")
            raise

    async def get_dashboard(
        self, dashboard_id: uuid.UUID, user_id: uuid.UUID, include_widgets: bool = False
    ) -> Union[DashboardResponse, DashboardWithWidgets]:
        """Get dashboard by ID with permission check"""
        try:
            async with get_async_session() as db:
                # Check permissions
                if not await self._has_dashboard_permission(
                    db, dashboard_id, user_id, "can_view"
                ):
                    raise PermissionError(
                        "User does not have permission to view this dashboard"
                    )

                if include_widgets:
                    return await self._get_dashboard_with_widgets(db, dashboard_id)
                else:
                    return await self._get_dashboard_with_count(db, dashboard_id)

        except Exception as e:
            logger.error(f"Error getting dashboard {dashboard_id}: {e}")
            raise

    async def update_dashboard(
        self, dashboard_id: uuid.UUID, request: DashboardUpdate, user_id: uuid.UUID
    ) -> DashboardResponse:
        """Update dashboard with permission check"""
        try:
            async with get_async_session() as db:
                # Check permissions
                if not await self._has_dashboard_permission(
                    db, dashboard_id, user_id, "can_edit"
                ):
                    raise PermissionError(
                        "User does not have permission to edit this dashboard"
                    )

                # Get dashboard
                query = select(Dashboard).where(Dashboard.id == dashboard_id)
                result = await db.execute(query)
                dashboard = result.scalar_one_or_none()

                if not dashboard:
                    raise ValueError(f"Dashboard not found: {dashboard_id}")

                # Update fields
                update_data = request.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(dashboard, field, value)

                await db.commit()
                await db.refresh(dashboard)

                return await self._get_dashboard_with_count(db, dashboard_id)

        except Exception as e:
            logger.error(f"Error updating dashboard {dashboard_id}: {e}")
            raise

    async def delete_dashboard(
        self, dashboard_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Delete dashboard with permission check"""
        try:
            async with get_async_session() as db:
                # Check permissions
                if not await self._has_dashboard_permission(
                    db, dashboard_id, user_id, "can_delete"
                ):
                    raise PermissionError(
                        "User does not have permission to delete this dashboard"
                    )

                # Soft delete dashboard
                query = (
                    update(Dashboard)
                    .where(Dashboard.id == dashboard_id)
                    .values(is_deleted=True, deleted_at=datetime.utcnow())
                )
                await db.execute(query)
                await db.commit()

                return True

        except Exception as e:
            logger.error(f"Error deleting dashboard {dashboard_id}: {e}")
            raise

    async def list_dashboards(
        self,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
        include_public: bool = True,
        include_templates: bool = False,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DashboardResponse]:
        """List dashboards with filtering"""
        try:
            async with get_async_session() as db:
                # Build base query
                query = select(Dashboard).where(Dashboard.is_deleted == False)

                # Apply filters
                conditions = []

                # User's own dashboards
                conditions.append(Dashboard.owner_id == user_id)

                # Public dashboards
                if include_public:
                    conditions.append(Dashboard.is_public == True)

                # Organization dashboards
                if organization_id:
                    conditions.append(Dashboard.organization_id == organization_id)

                # Templates
                if include_templates:
                    conditions.append(Dashboard.is_template == True)

                if len(conditions) > 1:
                    query = query.where(or_(*conditions))
                else:
                    query = query.where(conditions[0])

                # Category filter
                if category:
                    query = query.where(Dashboard.category == category)

                # Tags filter
                if tags:
                    # This is a simplified version - in production you'd use proper JSON querying
                    for tag in tags:
                        query = query.where(Dashboard.tags.contains([tag]))

                # Order and pagination
                query = (
                    query.order_by(desc(Dashboard.updated_at))
                    .offset(offset)
                    .limit(limit)
                )

                # Subquery for widget counts (single query instead of N+1)
                widget_count_subq = (
                    select(
                        DashboardWidget.dashboard_id,
                        func.count(DashboardWidget.id).label("widget_count"),
                    )
                    .where(DashboardWidget.is_active == True)
                    .group_by(DashboardWidget.dashboard_id)
                    .subquery()
                )

                # Join widget counts into the main query
                query = query.add_columns(
                    func.coalesce(widget_count_subq.c.widget_count, 0).label(
                        "widget_count"
                    )
                ).outerjoin(
                    widget_count_subq,
                    Dashboard.id == widget_count_subq.c.dashboard_id,
                )

                result = await db.execute(query)
                rows = result.all()

                dashboard_responses = []
                for dashboard, widget_count in rows:
                    dashboard_response = DashboardResponse(
                        id=dashboard.id,
                        name=dashboard.name,
                        description=dashboard.description,
                        owner_id=dashboard.owner_id,
                        organization_id=dashboard.organization_id,
                        layout=dashboard.layout,
                        theme=dashboard.theme,
                        is_public=dashboard.is_public,
                        is_template=dashboard.is_template,
                        auto_refresh=dashboard.auto_refresh,
                        refresh_interval=dashboard.refresh_interval,
                        timezone=dashboard.timezone,
                        tags=dashboard.tags,
                        category=dashboard.category,
                        version=dashboard.version,
                        created_at=dashboard.created_at,
                        updated_at=dashboard.updated_at,
                        widget_count=widget_count,
                    )
                    dashboard_responses.append(dashboard_response)

                return dashboard_responses

        except Exception as e:
            logger.error(f"Error listing dashboards: {e}")
            raise

    async def create_widget(
        self, dashboard_id: uuid.UUID, request: WidgetCreate, user_id: uuid.UUID
    ) -> WidgetResponse:
        """Create widget for dashboard"""
        try:
            async with get_async_session() as db:
                # Check permissions
                if not await self._has_dashboard_permission(
                    db, dashboard_id, user_id, "can_edit"
                ):
                    raise PermissionError(
                        "User does not have permission to edit this dashboard"
                    )

                # Check widget count limit
                widget_count_query = select(func.count(DashboardWidget.id)).where(
                    and_(
                        DashboardWidget.dashboard_id == dashboard_id,
                        DashboardWidget.is_active == True,
                    )
                )
                result = await db.execute(widget_count_query)
                widget_count = result.scalar()

                if widget_count >= self.max_widgets_per_dashboard:
                    raise ValueError(
                        f"Dashboard cannot have more than {self.max_widgets_per_dashboard} widgets"
                    )

                # Validate widget configuration
                await self._validate_widget_config(
                    request.widget_type, request.visualization_config
                )

                # Create widget
                widget = DashboardWidget(
                    dashboard_id=dashboard_id,
                    widget_type=request.widget_type,
                    title=request.title,
                    description=request.description,
                    x=request.x,
                    y=request.y,
                    width=request.width,
                    height=request.height,
                    data_source=request.data_source,
                    query_config=request.query_config,
                    visualization_config=request.visualization_config,
                    is_realtime=request.is_realtime,
                    real_time_config=request.real_time_config,
                    filters=request.filters,
                    drilldown_config=request.drilldown_config,
                    cache_ttl=request.cache_ttl,
                    cache_key=f"widget_{dashboard_id}_{uuid.uuid4()}",
                    is_active=request.is_active,
                    is_visible=request.is_visible,
                )
                db.add(widget)
                await db.commit()
                await db.refresh(widget)

                return await self._widget_to_response(db, widget)

        except Exception as e:
            logger.error(f"Error creating widget: {e}")
            raise

    async def update_widget(
        self, widget_id: uuid.UUID, request: WidgetUpdate, user_id: uuid.UUID
    ) -> WidgetResponse:
        """Update widget with permission check"""
        try:
            async with get_async_session() as db:
                # Get widget with dashboard
                query = (
                    select(DashboardWidget)
                    .options(selectinload(DashboardWidget.dashboard))
                    .where(DashboardWidget.id == widget_id)
                )
                result = await db.execute(query)
                widget = result.scalar_one_or_none()

                if not widget:
                    raise ValueError(f"Widget not found: {widget_id}")

                # Check permissions
                if not await self._has_dashboard_permission(
                    db, widget.dashboard_id, user_id, "can_edit"
                ):
                    raise PermissionError(
                        "User does not have permission to edit this widget"
                    )

                # Validate widget configuration if provided
                if request.visualization_config:
                    await self._validate_widget_config(
                        widget.widget_type, request.visualization_config
                    )

                # Update fields
                update_data = request.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(widget, field, value)

                # Update cache key if data source changed
                if "data_source" in update_data:
                    widget.cache_key = f"widget_{widget.dashboard_id}_{uuid.uuid4()}"

                await db.commit()
                await db.refresh(widget)

                return await self._widget_to_response(db, widget)

        except Exception as e:
            logger.error(f"Error updating widget {widget_id}: {e}")
            raise

    async def delete_widget(self, widget_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete widget with permission check"""
        try:
            async with get_async_session() as db:
                # Get widget
                query = select(DashboardWidget).where(DashboardWidget.id == widget_id)
                result = await db.execute(query)
                widget = result.scalar_one_or_none()

                if not widget:
                    raise ValueError(f"Widget not found: {widget_id}")

                # Check permissions
                if not await self._has_dashboard_permission(
                    db, widget.dashboard_id, user_id, "can_edit"
                ):
                    raise PermissionError(
                        "User does not have permission to delete this widget"
                    )

                # Soft delete widget
                query = (
                    update(DashboardWidget)
                    .where(DashboardWidget.id == widget_id)
                    .values(is_active=False, is_visible=False)
                )
                await db.execute(query)
                await db.commit()

                return True

        except Exception as e:
            logger.error(f"Error deleting widget {widget_id}: {e}")
            raise

    async def duplicate_dashboard(
        self, dashboard_id: uuid.UUID, new_name: str, user_id: uuid.UUID
    ) -> DashboardResponse:
        """Duplicate a dashboard"""
        try:
            async with get_async_session() as db:
                # Get original dashboard with widgets
                query = (
                    select(Dashboard)
                    .options(selectinload(Dashboard.widgets))
                    .where(Dashboard.id == dashboard_id)
                )
                result = await db.execute(query)
                original_dashboard = result.scalar_one_or_none()

                if not original_dashboard:
                    raise ValueError(f"Dashboard not found: {dashboard_id}")

                # Check permissions
                if not await self._has_dashboard_permission(
                    db, dashboard_id, user_id, "can_view"
                ):
                    raise PermissionError(
                        "User does not have permission to view this dashboard"
                    )

                # Create new dashboard
                new_dashboard = Dashboard(
                    name=new_name,
                    description=f"Copy of {original_dashboard.description}"
                    if original_dashboard.description
                    else None,
                    owner_id=user_id,
                    organization_id=original_dashboard.organization_id,
                    layout=original_dashboard.layout,
                    theme=original_dashboard.theme,
                    is_public=False,  # Duplicated dashboards are private by default
                    is_template=False,
                    auto_refresh=original_dashboard.auto_refresh,
                    refresh_interval=original_dashboard.refresh_interval,
                    timezone=original_dashboard.timezone,
                    tags=original_dashboard.tags,
                    category=original_dashboard.category,
                )
                db.add(new_dashboard)
                await db.commit()
                await db.refresh(new_dashboard)

                # Copy widgets
                for widget in original_dashboard.widgets:
                    if widget.is_active:
                        new_widget = DashboardWidget(
                            dashboard_id=new_dashboard.id,
                            widget_type=widget.widget_type,
                            title=widget.title,
                            description=widget.description,
                            x=widget.x,
                            y=widget.y,
                            width=widget.width,
                            height=widget.height,
                            data_source=widget.data_source,
                            query_config=widget.query_config,
                            visualization_config=widget.visualization_config,
                            is_realtime=widget.is_realtime,
                            real_time_config=widget.real_time_config,
                            filters=widget.filters,
                            drilldown_config=widget.drilldown_config,
                            cache_ttl=widget.cache_ttl,
                            cache_key=f"widget_{new_dashboard.id}_{uuid.uuid4()}",
                            is_active=widget.is_active,
                            is_visible=widget.is_visible,
                        )
                        db.add(new_widget)

                # Give owner full permissions
                permission = DashboardPermission(
                    dashboard_id=new_dashboard.id,
                    user_id=user_id,
                    can_view=True,
                    can_edit=True,
                    can_delete=True,
                    can_share=True,
                    can_export=True,
                )
                db.add(permission)
                await db.commit()

                return await self._get_dashboard_with_count(db, new_dashboard.id)

        except Exception as e:
            logger.error(f"Error duplicating dashboard {dashboard_id}: {e}")
            raise

    async def share_dashboard(
        self,
        dashboard_id: uuid.UUID,
        user_id: uuid.UUID,
        share_with_user_id: uuid.UUID,
        permissions: Dict[str, bool],
    ) -> bool:
        """Share dashboard with another user"""
        try:
            async with get_async_session() as db:
                # Check permissions
                if not await self._has_dashboard_permission(
                    db, dashboard_id, user_id, "can_share"
                ):
                    raise PermissionError(
                        "User does not have permission to share this dashboard"
                    )

                # Remove existing permissions for this user
                delete_query = delete(DashboardPermission).where(
                    and_(
                        DashboardPermission.dashboard_id == dashboard_id,
                        DashboardPermission.user_id == share_with_user_id,
                    )
                )
                await db.execute(delete_query)

                # Create new permissions
                permission = DashboardPermission(
                    dashboard_id=dashboard_id,
                    user_id=share_with_user_id,
                    can_view=permissions.get("can_view", True),
                    can_edit=permissions.get("can_edit", False),
                    can_delete=permissions.get("can_delete", False),
                    can_share=permissions.get("can_share", False),
                    can_export=permissions.get("can_export", True),
                )
                db.add(permission)
                await db.commit()

                return True

        except Exception as e:
            logger.error(f"Error sharing dashboard {dashboard_id}: {e}")
            raise

    async def get_dashboard_categories(self, user_id: uuid.UUID) -> List[str]:
        """Get available dashboard categories for user"""
        try:
            async with get_async_session() as db:
                query = (
                    select(Dashboard.category)
                    .where(
                        and_(
                            Dashboard.is_deleted == False,
                            or_(
                                Dashboard.owner_id == user_id,
                                Dashboard.is_public == True,
                            ),
                        )
                    )
                    .distinct()
                )

                result = await db.execute(query)
                categories = [row[0] for row in result.fetchall() if row[0]]
                return categories

        except Exception as e:
            logger.error(f"Error getting dashboard categories: {e}")
            return []

    async def get_dashboard_tags(self, user_id: uuid.UUID) -> List[str]:
        """Get available dashboard tags for user"""
        try:
            async with get_async_session() as db:
                query = (
                    select(Dashboard.tags)
                    .where(
                        and_(
                            Dashboard.is_deleted == False,
                            or_(
                                Dashboard.owner_id == user_id,
                                Dashboard.is_public == True,
                            ),
                        )
                    )
                    .distinct()
                )

                result = await db.execute(query)
                all_tags = []
                for row in result.fetchall():
                    if row[0]:  # tags list
                        all_tags.extend(row[0])

                return list(set(all_tags))  # Remove duplicates

        except Exception as e:
            logger.error(f"Error getting dashboard tags: {e}")
            return []

    async def _create_widgets_for_dashboard(
        self,
        db: AsyncSession,
        dashboard_id: uuid.UUID,
        widgets: List[WidgetConfiguration],
    ):
        """Create widgets for a dashboard"""
        for widget_config in widgets:
            await self._validate_widget_config(
                widget_config.widget_type, widget_config.visualization_config
            )

            widget = DashboardWidget(
                dashboard_id=dashboard_id,
                widget_type=widget_config.widget_type,
                title=widget_config.title,
                description=widget_config.description,
                x=widget_config.x,
                y=widget_config.y,
                width=widget_config.width,
                height=widget_config.height,
                data_source=widget_config.data_source,
                query_config=widget_config.query_config,
                visualization_config=widget_config.visualization_config,
                is_realtime=widget_config.is_realtime,
                real_time_config=widget_config.real_time_config,
                filters=widget_config.filters,
                drilldown_config=widget_config.drilldown_config,
                cache_ttl=widget_config.cache_ttl,
                cache_key=f"widget_{dashboard_id}_{uuid.uuid4()}",
                is_active=widget_config.is_active,
                is_visible=widget_config.is_visible,
            )
            db.add(widget)

        await db.commit()

    async def _get_dashboard_with_count(
        self, db: AsyncSession, dashboard_id: uuid.UUID
    ) -> DashboardResponse:
        """Get dashboard with widget count"""
        # Get dashboard
        query = select(Dashboard).where(Dashboard.id == dashboard_id)
        result = await db.execute(query)
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        # Get widget count
        widget_count_query = select(func.count(DashboardWidget.id)).where(
            and_(
                DashboardWidget.dashboard_id == dashboard.id,
                DashboardWidget.is_active == True,
            )
        )
        widget_count_result = await db.execute(widget_count_query)
        widget_count = widget_count_result.scalar()

        return DashboardResponse(
            id=dashboard.id,
            name=dashboard.name,
            description=dashboard.description,
            owner_id=dashboard.owner_id,
            organization_id=dashboard.organization_id,
            layout=dashboard.layout,
            theme=dashboard.theme,
            is_public=dashboard.is_public,
            is_template=dashboard.is_template,
            auto_refresh=dashboard.auto_refresh,
            refresh_interval=dashboard.refresh_interval,
            timezone=dashboard.timezone,
            tags=dashboard.tags,
            category=dashboard.category,
            version=dashboard.version,
            created_at=dashboard.created_at,
            updated_at=dashboard.updated_at,
            widget_count=widget_count,
        )

    async def _get_dashboard_with_widgets(
        self, db: AsyncSession, dashboard_id: uuid.UUID
    ) -> DashboardWithWidgets:
        """Get dashboard with widgets included"""
        # Get dashboard with widgets
        query = (
            select(Dashboard)
            .options(selectinload(Dashboard.widgets))
            .where(Dashboard.id == dashboard_id)
        )
        result = await db.execute(query)
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        # Convert widgets
        widgets = []
        for widget in dashboard.widgets:
            if widget.is_active:
                widget_response = WidgetResponse(
                    id=widget.id,
                    dashboard_id=widget.dashboard_id,
                    widget_type=widget.widget_type,
                    title=widget.title,
                    description=widget.description,
                    x=widget.x,
                    y=widget.y,
                    width=widget.width,
                    height=widget.height,
                    data_source=widget.data_source,
                    query_config=widget.query_config,
                    visualization_config=widget.visualization_config,
                    is_realtime=widget.is_realtime,
                    real_time_config=widget.real_time_config,
                    filters=widget.filters,
                    drilldown_config=widget.drilldown_config,
                    cache_ttl=widget.cache_ttl,
                    is_active=widget.is_active,
                    is_visible=widget.is_visible,
                    created_at=widget.created_at,
                    updated_at=widget.updated_at,
                )
                widgets.append(widget_response)

        return DashboardWithWidgets(
            id=dashboard.id,
            name=dashboard.name,
            description=dashboard.description,
            owner_id=dashboard.owner_id,
            organization_id=dashboard.organization_id,
            layout=dashboard.layout,
            theme=dashboard.theme,
            is_public=dashboard.is_public,
            is_template=dashboard.is_template,
            auto_refresh=dashboard.auto_refresh,
            refresh_interval=dashboard.refresh_interval,
            timezone=dashboard.timezone,
            tags=dashboard.tags,
            category=dashboard.category,
            version=dashboard.version,
            created_at=dashboard.created_at,
            updated_at=dashboard.updated_at,
            widget_count=len(widgets),
            widgets=widgets,
        )

    async def _widget_to_response(
        self, db: AsyncSession, widget: DashboardWidget
    ) -> WidgetResponse:
        """Convert widget model to response"""
        return WidgetResponse(
            id=widget.id,
            dashboard_id=widget.dashboard_id,
            widget_type=widget.widget_type,
            title=widget.title,
            description=widget.description,
            x=widget.x,
            y=widget.y,
            width=widget.width,
            height=widget.height,
            data_source=widget.data_source,
            query_config=widget.query_config,
            visualization_config=widget.visualization_config,
            is_realtime=widget.is_realtime,
            real_time_config=widget.real_time_config,
            filters=widget.filters,
            drilldown_config=widget.drilldown_config,
            cache_ttl=widget.cache_ttl,
            is_active=widget.is_active,
            is_visible=widget.is_visible,
            created_at=widget.created_at,
            updated_at=widget.updated_at,
        )

    async def _has_dashboard_permission(
        self,
        db: AsyncSession,
        dashboard_id: uuid.UUID,
        user_id: uuid.UUID,
        permission: str,
    ) -> bool:
        """Check if user has permission for dashboard"""
        try:
            # Check if user is owner
            dashboard_query = select(Dashboard.owner_id).where(
                Dashboard.id == dashboard_id
            )
            result = await db.execute(dashboard_query)
            owner_id = result.scalar()

            if owner_id == user_id:
                return True

            # Check permissions table
            permission_query = select(getattr(DashboardPermission, permission)).where(
                and_(
                    DashboardPermission.dashboard_id == dashboard_id,
                    DashboardPermission.user_id == user_id,
                )
            )
            result = await db.execute(permission_query)
            has_permission = result.scalar()

            return bool(has_permission)

        except Exception as e:
            logger.error(f"Error checking dashboard permission: {e}")
            return False

    async def _validate_widget_config(
        self, widget_type: DashboardWidgetType, config: Optional[Dict[str, Any]]
    ) -> None:
        """Validate widget configuration"""
        if not config:
            # Apply default configuration
            widget_type_str = widget_type.value
            if widget_type_str in self.default_widget_configs:
                return  # Default will be applied
            else:
                raise ValueError(
                    f"No default configuration available for widget type: {widget_type}"
                )

        # Validate based on widget type
        if widget_type in [
            DashboardWidgetType.CHART,
            DashboardWidgetType.LINE,
            DashboardWidgetType.BAR,
            DashboardWidgetType.PIE,
        ]:
            required_fields = (
                ["x_axis", "y_axis"]
                if widget_type != DashboardWidgetType.PIE
                else ["value_field", "label_field"]
            )
            for field in required_fields:
                if field not in config:
                    raise ValueError(
                        f"Missing required field '{field}' for chart widget"
                    )

        elif widget_type == DashboardWidgetType.METRIC:
            if "metric_id" not in config:
                raise ValueError("Missing required field 'metric_id' for metric widget")

        elif widget_type == DashboardWidgetType.GRAPH:
            if "graph_type" not in config:
                raise ValueError("Missing required field 'graph_type' for graph widget")

        # Check size constraints
        if "size" in config:
            total_size = config.get("width", 1) * config.get("height", 1)
            if total_size > 50:  # Arbitrary limit for grid units
                raise ValueError("Widget size too large")

    def get_widget_type_config(
        self, widget_type: DashboardWidgetType
    ) -> Dict[str, Any]:
        """Get default configuration for widget type"""
        widget_type_str = widget_type.value
        if widget_type_str in self.default_widget_configs:
            return self.default_widget_configs[widget_type_str].copy()
        return {}


# Global instance
dashboard_service = DashboardService()
