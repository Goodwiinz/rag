"""
User behavior analytics service for tracking and analyzing user interactions
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func, desc, asc

from src.core.database import get_db
from src.models.quality_metrics import SearchSession, SearchEvent
from src.models.user import User
from src.models.organization import Organization
from src.core.config import settings

logger = logging.getLogger(__name__)


class BehaviorPattern(Enum):
    """User behavior patterns"""
    POWER_USER = "power_user"           # High frequency, advanced features
    CASUAL_USER = "casual_user"         # Low frequency, basic features
    RESEARCHER = "researcher"           # Deep queries, long sessions
    EFFICIENT_USER = "efficient_user"   # Quick searches, high success
    EXPLORER = "explorer"              # Diverse queries, browsing
    FRUSTRATED_USER = "frustrated_user" # Many failed searches


@dataclass
class UserBehaviorMetrics:
    """User behavior metrics"""
    user_id: str
    session_count: int
    total_searches: int
    avg_session_duration: float
    avg_response_time: float
    success_rate: float
    click_through_rate: float
    avg_results_per_search: float
    query_diversity: float
    preferred_search_types: List[str]
    top_queries: List[str]
    behavior_pattern: BehaviorPattern
    last_active: datetime
    engagement_score: float
    satisfaction_score: Optional[float]


@dataclass
class SessionAnalysis:
    """Search session analysis"""
    session_id: str
    user_id: str
    duration: float
    search_count: int
    avg_response_time: float
    clicked_results: int
    total_results_viewed: int
    queries: List[str]
    search_types: List[str]
    bounce_rate: bool
    task_completion_rate: float
    satisfaction_indicators: List[str]


class UserBehaviorService:
    """
    Service for tracking and analyzing user behavior patterns
    """

    def __init__(self):
        self.behavior_cache = {}  # Cache user behavior analysis
        self.session_cache = {}   # Cache session analysis

    async def track_search_event(
        self,
        session_id: str,
        query: str,
        search_type: str,
        results_count: int,
        response_time: float,
        user_id: Optional[str] = None,
        search_query_id: Optional[str] = None,
        page_number: int = 1,
        filters_applied: Optional[Dict[str, Any]] = None,
        sort_order: Optional[str] = None
    ) -> SearchEvent:
        """Track a search event for behavior analysis"""

        db = next(get_db())

        try:
            # Create search event
            search_event = SearchEvent(
                session_id=uuid.UUID(session_id) if isinstance(session_id, str) else session_id,
                query=query,
                search_type=search_type,
                results_count=results_count,
                response_time=response_time,
                user_id=uuid.UUID(user_id) if user_id else None,
                search_query_id=uuid.UUID(search_query_id) if search_query_id else None,
                page_number=page_number,
                filters_applied=filters_applied,
                sort_order=sort_order
            )

            db.add(search_event)
            db.commit()
            db.refresh(search_event)

            # Update session metrics
            await self._update_session_metrics(session_id, search_event, db)

            logger.info(f"Tracked search event: {query} for user {user_id}")
            return search_event

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to track search event: {e}")
            raise
        finally:
            db.close()

    async def track_user_interaction(
        self,
        session_id: str,
        event_id: str,
        interaction_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """Track user interaction with search results"""

        db = next(get_db())

        try:
            # Get the search event
            search_event = db.query(SearchEvent).filter(
                SearchEvent.id == uuid.UUID(event_id)
            ).first()

            if not search_event:
                logger.warning(f"Search event not found: {event_id}")
                return False

            # Update interaction data based on type
            if interaction_type == "click":
                if search_event.clicked_results is None:
                    search_event.clicked_results = 0
                search_event.clicked_results += 1

                if search_event.clicked_result_ids is None:
                    search_event.clicked_result_ids = []
                if "result_id" in data:
                    search_event.clicked_result_ids.append(data["result_id"])

                # Track time to first click
                if search_event.time_to_first_click is None and "click_time" in data:
                    search_event.time_to_first_click = data["click_time"]

            elif interaction_type == "dwell":
                if "dwell_time" in data:
                    search_event.dwell_time = data["dwell_time"]

            elif interaction_type == "rating":
                if "rating" in data:
                    search_event.user_rating = data["rating"]
                if "feedback" in data:
                    search_event.feedback_text = data["feedback"]

            elif interaction_type == "bookmark":
                search_event.is_bookmarked = data.get("bookmarked", False)

            db.commit()

            logger.info(f"Tracked user interaction: {interaction_type} for event {event_id}")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to track user interaction: {e}")
            return False
        finally:
            db.close()

    async def analyze_user_behavior(
        self,
        user_id: str,
        days_back: int = 30,
        use_cache: bool = True
    ) -> UserBehaviorMetrics:
        """Analyze user behavior patterns"""

        cache_key = f"{user_id}_{days_back}"
        if use_cache and cache_key in self.behavior_cache:
            return self.behavior_cache[cache_key]

        db = next(get_db())

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            # Get user's search sessions
            sessions = db.query(SearchSession).filter(
                SearchSession.user_id == uuid.UUID(user_id),
                SearchSession.start_time >= cutoff_date
            ).all()

            if not sessions:
                return self._create_empty_behavior_metrics(user_id)

            # Get user's search events
            session_ids = [s.id for s in sessions]
            events = db.query(SearchEvent).filter(
                SearchEvent.session_id.in_(session_ids)
            ).all()

            # Calculate metrics
            metrics = self._calculate_behavior_metrics(
                user_id, sessions, events, days_back
            )

            # Cache the results
            if use_cache:
                self.behavior_cache[cache_key] = metrics

            return metrics

        except Exception as e:
            logger.error(f"Failed to analyze user behavior: {e}")
            return self._create_empty_behavior_metrics(user_id)
        finally:
            db.close()

    async def analyze_session(self, session_id: str) -> SessionAnalysis:
        """Analyze a specific search session"""

        if session_id in self.session_cache:
            return self.session_cache[session_id]

        db = next(get_db())

        try:
            # Get session
            session = db.query(SearchSession).filter(
                SearchSession.session_id == session_id
            ).first()

            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Get events
            events = db.query(SearchEvent).filter(
                SearchEvent.session_id == session.id
            ).order_by(SearchEvent.created_at).all()

            # Analyze session
            analysis = self._analyze_session_details(session, events)

            # Cache the result
            self.session_cache[session_id] = analysis

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze session: {e}")
            raise
        finally:
            db.close()

    async def get_behavior_trends(
        self,
        organization_id: str,
        days_back: int = 30,
        group_by: str = "day"
    ) -> Dict[str, Any]:
        """Get behavior trends for organization"""

        db = next(get_db())

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            # Get daily/weekly/monthly aggregates
            if group_by == "day":
                date_format = "YYYY-MM-DD"
            elif group_by == "week":
                date_format = "YYYY-\"WW\""
            else:  # month
                date_format = "YYYY-MM"

            # Query session trends
            session_trends = db.execute(text(f"""
                SELECT
                    DATE_TRUNC('{group_by}', start_time) as period,
                    COUNT(*) as session_count,
                    AVG(search_count) as avg_searches_per_session,
                    AVG(EXTRACT(EPOCH FROM (end_time - start_time))) as avg_duration_seconds
                FROM search_sessions
                WHERE organization_id = :org_id
                    AND start_time >= :cutoff_date
                GROUP BY period
                ORDER BY period
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchall()

            # Query search event trends
            event_trends = db.execute(text(f"""
                SELECT
                    DATE_TRUNC('{group_by}', created_at) as period,
                    COUNT(*) as search_count,
                    AVG(response_time) as avg_response_time,
                    AVG(results_count) as avg_results,
                    SUM(clicked_results) as total_clicks
                FROM search_events
                WHERE organization_id = :org_id
                    AND created_at >= :cutoff_date
                GROUP BY period
                ORDER BY period
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchall()

            # Query user engagement trends
            engagement_trends = db.execute(text(f"""
                SELECT
                    DATE_TRUNC('{group_by}', s.start_time) as period,
                    COUNT(DISTINCT s.user_id) as active_users,
                    COUNT(DISTINCT CASE WHEN s.search_count > 5 THEN s.user_id END) as power_users,
                    AVG(CASE WHEN e.user_rating IS NOT NULL THEN e.user_rating END) as avg_satisfaction
                FROM search_sessions s
                LEFT JOIN search_events e ON s.id = e.session_id
                WHERE s.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
                GROUP BY period
                ORDER BY period
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchall()

            return {
                "session_trends": [
                    {
                        "period": str(row.period),
                        "session_count": row.session_count,
                        "avg_searches_per_session": float(row.avg_searches_per_session or 0),
                        "avg_duration_seconds": float(row.avg_duration_seconds or 0)
                    }
                    for row in session_trends
                ],
                "search_trends": [
                    {
                        "period": str(row.period),
                        "search_count": row.search_count,
                        "avg_response_time": float(row.avg_response_time or 0),
                        "avg_results": float(row.avg_results or 0),
                        "total_clicks": row.total_clicks
                    }
                    for row in event_trends
                ],
                "engagement_trends": [
                    {
                        "period": str(row.period),
                        "active_users": row.active_users,
                        "power_users": row.power_users,
                        "avg_satisfaction": float(row.avg_satisfaction or 0)
                    }
                    for row in engagement_trends
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get behavior trends: {e}")
            raise
        finally:
            db.close()

    async def identify_behavior_patterns(
        self,
        organization_id: str,
        min_sessions: int = 5
    ) -> Dict[str, Any]:
        """Identify user behavior patterns in the organization"""

        db = next(get_db())

        try:
            # Get users with sufficient activity
            active_users = db.execute(text("""
                SELECT
                    u.id,
                    u.first_name,
                    u.last_name,
                    COUNT(s.id) as session_count,
                    COUNT(e.id) as search_count,
                    AVG(e.response_time) as avg_response_time,
                    AVG(CASE WHEN e.clicked_results > 0 THEN 1 ELSE 0 END) as click_rate,
                    AVG(e.user_rating) as avg_rating
                FROM users u
                JOIN search_sessions s ON u.id = s.user_id
                JOIN search_events e ON s.id = e.session_id
                WHERE u.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
                GROUP BY u.id, u.first_name, u.last_name
                HAVING COUNT(s.id) >= :min_sessions
                ORDER BY search_count DESC
            """), {
                "org_id": organization_id,
                "cutoff_date": datetime.utcnow() - timedelta(days=30),
                "min_sessions": min_sessions
            }).fetchall()

            patterns = {
                "power_users": [],
                "casual_users": [],
                "researchers": [],
                "efficient_users": [],
                "explorers": [],
                "frustrated_users": []
            }

            for user in active_users:
                pattern = self._classify_user_behavior(
                    session_count=user.session_count,
                    search_count=user.search_count,
                    avg_response_time=user.avg_response_time,
                    click_rate=user.click_rate,
                    avg_rating=user.avg_rating
                )

                patterns[pattern.value].append({
                    "user_id": str(user.id),
                    "name": f"{user.first_name} {user.last_name}",
                    "session_count": user.session_count,
                    "search_count": user.search_count,
                    "avg_response_time": float(user.avg_response_time or 0),
                    "click_rate": float(user.click_rate or 0),
                    "avg_rating": float(user.avg_rating or 0)
                })

            return patterns

        except Exception as e:
            logger.error(f"Failed to identify behavior patterns: {e}")
            raise
        finally:
            db.close()

    async def generate_behavior_report(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Generate comprehensive behavior analytics report"""

        report = {
            "report_period": {
                "start_date": (datetime.utcnow() - timedelta(days=days_back)).isoformat(),
                "end_date": datetime.utcnow().isoformat(),
                "days": days_back
            },
            "generated_at": datetime.utcnow().isoformat()
        }

        if user_id:
            # Individual user report
            user_metrics = await self.analyze_user_behavior(user_id, days_back)
            report["user_metrics"] = {
                "user_id": user_metrics.user_id,
                "behavior_pattern": user_metrics.behavior_pattern.value,
                "session_count": user_metrics.session_count,
                "total_searches": user_metrics.total_searches,
                "avg_session_duration": user_metrics.avg_session_duration,
                "success_rate": user_metrics.success_rate,
                "engagement_score": user_metrics.engagement_score,
                "satisfaction_score": user_metrics.satisfaction_score,
                "preferred_search_types": user_metrics.preferred_search_types,
                "top_queries": user_metrics.top_queries
            }

        if organization_id:
            # Organization-level report
            report["organization_metrics"] = await self.get_behavior_trends(
                organization_id, days_back
            )
            report["behavior_patterns"] = await self.identify_behavior_patterns(
                organization_id
            )

        return report

    async def _update_session_metrics(self, session_id: str, event: SearchEvent, db: Session):
        """Update session metrics when a new event is added"""

        session = db.query(SearchSession).filter(
            SearchSession.session_id == session_id
        ).first()

        if session:
            session.search_count += 1
            session.total_response_time += event.response_time
            session.avg_response_time = session.total_response_time / session.search_count

            db.commit()

    def _calculate_behavior_metrics(
        self,
        user_id: str,
        sessions: List[SearchSession],
        events: List[SearchEvent],
        days_back: int
    ) -> UserBehaviorMetrics:
        """Calculate behavior metrics from sessions and events"""

        if not sessions:
            return self._create_empty_behavior_metrics(user_id)

        # Basic metrics
        session_count = len(sessions)
        total_searches = len(events)

        # Session duration
        durations = []
        for session in sessions:
            if session.end_time:
                duration = (session.end_time - session.start_time).total_seconds()
                durations.append(duration)

        avg_session_duration = statistics.mean(durations) if durations else 0

        # Response times
        response_times = [e.response_time for e in events]
        avg_response_time = statistics.mean(response_times) if response_times else 0

        # Success metrics
        successful_events = [e for e in events if e.clicked_results > 0]
        success_rate = len(successful_events) / total_searches if total_searches > 0 else 0

        # Click through rate
        total_clicks = sum(e.clicked_results or 0 for e in events)
        total_results = sum(e.results_count for e in events)
        click_through_rate = total_clicks / total_results if total_results > 0 else 0

        # Average results per search
        avg_results_per_search = statistics.mean([e.results_count for e in events]) if events else 0

        # Query diversity
        unique_queries = len(set(e.query for e in events))
        query_diversity = unique_queries / total_searches if total_searches > 0 else 0

        # Preferred search types
        search_types = [e.search_type for e in events]
        type_counts = {}
        for st in search_types:
            type_counts[st] = type_counts.get(st, 0) + 1
        preferred_search_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        preferred_search_types = [t[0] for t in preferred_search_types]

        # Top queries
        query_counts = {}
        for e in events:
            query_counts[e.query] = query_counts.get(e.query, 0) + 1
        top_queries = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_queries = [q[0] for q in top_queries]

        # Behavior pattern
        behavior_pattern = self._classify_user_behavior(
            session_count=session_count,
            search_count=total_searches,
            avg_response_time=avg_response_time,
            click_rate=success_rate,
            avg_rating=statistics.mean([e.user_rating for e in events if e.user_rating]) if any(e.user_rating for e in events) else None
        )

        # Engagement score (0-100)
        engagement_score = self._calculate_engagement_score(
            session_count, total_searches, avg_session_duration, query_diversity
        )

        # Satisfaction score
        satisfaction_scores = [e.user_rating for e in events if e.user_rating]
        satisfaction_score = statistics.mean(satisfaction_scores) if satisfaction_scores else None

        # Last active
        last_active = max(s.start_time for s in sessions)

        return UserBehaviorMetrics(
            user_id=user_id,
            session_count=session_count,
            total_searches=total_searches,
            avg_session_duration=avg_session_duration,
            avg_response_time=avg_response_time,
            success_rate=success_rate,
            click_through_rate=click_through_rate,
            avg_results_per_search=avg_results_per_search,
            query_diversity=query_diversity,
            preferred_search_types=preferred_search_types,
            top_queries=top_queries,
            behavior_pattern=behavior_pattern,
            last_active=last_active,
            engagement_score=engagement_score,
            satisfaction_score=satisfaction_score
        )

    def _analyze_session_details(
        self,
        session: SearchSession,
        events: List[SearchEvent]
    ) -> SessionAnalysis:
        """Analyze individual session details"""

        duration = 0
        if session.end_time:
            duration = (session.end_time - session.start_time).total_seconds()

        queries = [e.query for e in events]
        search_types = [e.search_type for e in events]

        clicked_results = sum(e.clicked_results or 0 for e in events)
        total_results_viewed = sum(e.results_count for e in events)

        avg_response_time = statistics.mean([e.response_time for e in events]) if events else 0

        # Bounce rate (single search and no interaction)
        bounce_rate = len(events) == 1 and clicked_results == 0

        # Task completion indicators
        satisfaction_indicators = []
        if any(e.user_rating and e.user_rating >= 4 for e in events):
            satisfaction_indicators.append("high_ratings")
        if any(e.is_bookmarked for e in events):
            satisfaction_indicators.append("bookmarks")
        if clicked_results > 0:
            satisfaction_indicators.append("clicks")

        task_completion_rate = len(satisfaction_indicators) / 3.0  # Max 3 indicators

        return SessionAnalysis(
            session_id=session.session_id,
            user_id=str(session.user_id) if session.user_id else None,
            duration=duration,
            search_count=len(events),
            avg_response_time=avg_response_time,
            clicked_results=clicked_results,
            total_results_viewed=total_results_viewed,
            queries=queries,
            search_types=search_types,
            bounce_rate=bounce_rate,
            task_completion_rate=task_completion_rate,
            satisfaction_indicators=satisfaction_indicators
        )

    def _classify_user_behavior(
        self,
        session_count: int,
        search_count: int,
        avg_response_time: float,
        click_rate: float,
        avg_rating: Optional[float]
    ) -> BehaviorPattern:
        """Classify user into behavior pattern"""

        # Power user: High activity, good engagement
        if session_count > 10 and search_count > 50:
            return BehaviorPattern.POWER_USER

        # Frustrated user: Low success rate, low ratings
        if click_rate < 0.3 and avg_rating and avg_rating < 2.5:
            return BehaviorPattern.FRUSTRATED_USER

        # Researcher: Long sessions, diverse queries
        if search_count > 20 and avg_response_time > 3000:  # > 3 seconds avg
            return BehaviorPattern.RESEARCHER

        # Efficient user: Fast searches, high success rate
        if avg_response_time < 2000 and click_rate > 0.7:
            return BehaviorPattern.EFFICIENT_USER

        # Explorer: Moderate activity, diverse patterns
        if 5 <= session_count <= 15:
            return BehaviorPattern.EXPLORER

        # Casual user: Low activity
        if session_count < 5:
            return BehaviorPattern.CASUAL_USER

        # Default to explorer
        return BehaviorPattern.EXPLORER

    def _calculate_engagement_score(
        self,
        session_count: int,
        search_count: int,
        avg_session_duration: float,
        query_diversity: float
    ) -> float:
        """Calculate engagement score (0-100)"""

        # Normalize factors
        session_score = min(session_count / 20, 1.0) * 25  # Max 25 points
        search_score = min(search_count / 100, 1.0) * 25   # Max 25 points
        duration_score = min(avg_session_duration / 300, 1.0) * 25  # Max 25 points (5 min)
        diversity_score = query_diversity * 25  # Max 25 points

        return session_score + search_score + duration_score + diversity_score

    def _create_empty_behavior_metrics(self, user_id: str) -> UserBehaviorMetrics:
        """Create empty behavior metrics for inactive users"""

        return UserBehaviorMetrics(
            user_id=user_id,
            session_count=0,
            total_searches=0,
            avg_session_duration=0,
            avg_response_time=0,
            success_rate=0,
            click_through_rate=0,
            avg_results_per_search=0,
            query_diversity=0,
            preferred_search_types=[],
            top_queries=[],
            behavior_pattern=BehaviorPattern.CASUAL_USER,
            last_active=datetime.utcnow(),
            engagement_score=0,
            satisfaction_score=None
        )


# Global service instance
user_behavior_service = UserBehaviorService()