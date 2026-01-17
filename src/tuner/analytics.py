import logging
from typing import Dict, Any, List
from tuner.storage import TunerStorage

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    def __init__(self, db_path: str = "data/tuner.db"):
        self.storage = TunerStorage(db_path)

    async def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        await self.storage.initialize()
        
        report = {
            "yield_rates": await self._calculate_yield_rates(),
            "rejection_analysis": await self._analyze_rejections(),
            "top_performers": await self._get_top_performers()
        }
        return report

    async def _calculate_yield_rates(self) -> Dict[str, float]:
        """Calculate efficiency metrics."""
        async with self.storage._get_conn_ctx() as db:
            # Total Findings
            async with db.execute("SELECT COUNT(*) FROM findings") as cursor:
                total_findings = (await cursor.fetchone())[0]

            # AI Approved (High score or interesting)
            # Assuming 'interested' is not explicitly a status, we use match_score > threshold
            # or we check if it was presented to user (status != 'filtered')
            async with db.execute("SELECT COUNT(*) FROM findings WHERE match_score > 0.6") as cursor:
                ai_approved = (await cursor.fetchone())[0]

            # User Reviewed
            async with db.execute("SELECT COUNT(*) FROM feedback_logs") as cursor:
                total_reviewed = (await cursor.fetchone())[0]

            # User Liked
            async with db.execute("SELECT COUNT(*) FROM feedback_logs WHERE action = 'like'") as cursor:
                user_liked = (await cursor.fetchone())[0]

            return {
                "total_findings": total_findings,
                "ai_approved": ai_approved,
                "ai_yield": (ai_approved / total_findings) if total_findings > 0 else 0.0,
                "user_acceptance_rate": (user_liked / total_reviewed) if total_reviewed > 0 else 0.0,
            }

    async def _analyze_rejections(self) -> List[Dict[str, Any]]:
        """Identify why items are being rejected."""
        async with self.storage._get_conn_ctx() as db:
            db.row_factory = None
            # Group by Category
            async with db.execute("""
                SELECT category, COUNT(*) as count 
                FROM feedback_logs 
                WHERE action = 'dislike' 
                GROUP BY category 
                ORDER BY count DESC
            """) as cursor:
                by_category = [{"category": row[0], "count": row[1]} for row in await cursor.fetchall()]

            # Reasons text analysis (simplified: just list frequent reasons if repeated, or last few)
            # Ideally we'd cluster these with AI, but for now just raw dump of granular reasons
            async with db.execute("""
                SELECT reason, COUNT(*) as count 
                FROM feedback_logs 
                WHERE action = 'dislike' AND reason IS NOT NULL 
                GROUP BY reason 
                ORDER BY count DESC 
                LIMIT 5
            """) as cursor:
                common_reasons = [{"reason": row[0], "count": row[1]} for row in await cursor.fetchall()]

            return {
                "by_category": by_category,
                "common_reasons": common_reasons
            }

    async def _get_top_performers(self) -> List[Dict[str, Any]]:
        """Identify which languages/topics are performing best."""
        async with self.storage._get_conn_ctx() as db:
            # Yield by Language
            async with db.execute("""
                SELECT f.language, 
                       COUNT(CASE WHEN fl.action = 'like' THEN 1 END) as likes,
                       COUNT(*) as total
                FROM feedback_logs fl
                JOIN findings f ON fl.finding_id = f.id
                GROUP BY f.language
                HAVING total > 2
                ORDER BY likes DESC
            """) as cursor:
                return [{"language": row[0], "likes": row[1], "total": row[2]} for row in await cursor.fetchall()]
