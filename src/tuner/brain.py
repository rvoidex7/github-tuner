import os
import json
import logging
import numpy as np
from typing import List, Optional, Tuple, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalBrain:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = None
        self.model_name = model_name
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
        except ImportError:
            logger.warning("sentence-transformers not installed. LocalBrain will operate in mock mode.")
        except Exception as e:
            logger.warning(f"Failed to load model {self.model_name}: {e}. LocalBrain will operate in mock mode.")

    def vectorize(self, text: str) -> np.ndarray:
        """Convert text to vector embedding."""
        if not text:
            return np.zeros(384) # Default dimension for all-MiniLM-L6-v2

        if self.model:
            return self.model.encode(text)
        else:
            # Mock embedding (random vector)
            return np.random.rand(384)

    def calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        if vec1 is None or vec2 is None:
            return 0.0

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def calculate_user_vector(self, starred_descriptions: List[str]) -> np.ndarray:
        """Deprecated: Use generate_interest_clusters instead."""
        clusters = self.generate_interest_clusters(starred_descriptions, k=1)
        return clusters[0] if len(clusters) > 0 else np.zeros(384)

    def generate_interest_clusters(self, descriptions: List[str], k: int = 5) -> List[np.ndarray]:
        """
        Generate K clusters from the descriptions using KMeans.
        Returns a list of cluster center vectors.
        """
        if not descriptions:
            return []

        vectors = []
        for desc in descriptions:
            vectors.append(self.vectorize(desc))

        if not vectors:
            return []

        vectors_np = np.array(vectors)

        # If fewer data points than k, use all points as centers
        if len(vectors) <= k:
            return [v for v in vectors_np]

        try:
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(vectors_np)
            return list(kmeans.cluster_centers_)
        except ImportError:
            logger.warning("scikit-learn not installed. Falling back to simple mean.")
            return [np.mean(vectors_np, axis=0)]
        except Exception as e:
             logger.error(f"Clustering failed: {e}. Falling back to simple mean.")
             return [np.mean(vectors_np, axis=0)]

class CloudBrain:
    def __init__(self, api_key: Optional[str] = None, db_path: str = "data/tuner.db"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = None
        self.model_name = "gemini-flash-latest"
        self.db_path = db_path
        self.rate_limited = False
        self.rate_limit_reset_time = 0
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(f'models/{self.model_name}')
            except ImportError:
                logger.warning("google-generativeai not installed. CloudBrain will operate in mock mode.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}. CloudBrain will operate in mock mode.")
        else:
            logger.warning("No API key provided for CloudBrain. Operating in mock mode.")

    def _log_usage(self, call_type: str, context_chars: int, tokens_in: int = 0, tokens_out: int = 0, 
                   success: bool = True, error_type: str = None, duration_ms: int = 0):
        """Log AI usage to database synchronously."""
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_usage (call_type, model, context_chars, tokens_in, tokens_out, success, error_type, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (call_type, self.model_name, context_chars, tokens_in, tokens_out, 1 if success else 0, error_type, duration_ms))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Failed to log AI usage: {e}")

    def _check_rate_limit_error(self, error_msg: str) -> Tuple[bool, int]:
        """Check if error is a rate limit and extract retry delay."""
        import re
        error_str = str(error_msg).lower()
        if "quota" in error_str or "rate" in error_str or "limit" in error_str:
            # Try to extract retry delay
            match = re.search(r'retry.*?(\d+(?:\.\d+)?)\s*s', error_str)
            if match:
                return True, int(float(match.group(1)) + 1)
            return True, 60  # Default 1 minute wait
        return False, 0

    async def _call_with_tracking(self, call_type: str, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Call Gemini API with usage tracking and rate limit handling."""
        import time as time_module
        
        if not self.model:
            return None, "no_model"
        
        # Check if we're still rate limited
        if self.rate_limited and time_module.time() < self.rate_limit_reset_time:
            wait_time = int(self.rate_limit_reset_time - time_module.time())
            logger.warning(f"⏳ AI rate limited. Please wait {wait_time}s before trying again.")
            return None, "rate_limited"
        
        context_chars = len(prompt)
        start_time = time_module.time()
        
        try:
            response = self.model.generate_content(prompt)
            duration_ms = int((time_module.time() - start_time) * 1000)
            
            # Estimate tokens (roughly 4 chars per token)
            tokens_in = context_chars // 4
            tokens_out = len(response.text) // 4 if response.text else 0
            
            self._log_usage(call_type, context_chars, tokens_in, tokens_out, True, None, duration_ms)
            self.rate_limited = False
            
            return response.text, None
            
        except Exception as e:
            duration_ms = int((time_module.time() - start_time) * 1000)
            error_str = str(e)
            
            is_rate_limit, retry_delay = self._check_rate_limit_error(error_str)
            
            if is_rate_limit:
                self.rate_limited = True
                self.rate_limit_reset_time = time_module.time() + retry_delay
                error_type = "rate_limit"
                logger.error(f"🚫 AI RATE LIMIT! Quota exceeded. Retry in {retry_delay}s. Consider upgrading API plan.")
            else:
                error_type = "api_error"
                logger.error(f"AI API error: {error_str[:200]}")
            
            self._log_usage(call_type, context_chars, context_chars // 4, 0, False, error_type, duration_ms)
            return None, error_type

    async def analyze_repo(self, readme_content: str) -> Tuple[str, float]:
        """Analyze a repo's README and return a summary and relevance score."""
        prompt = f"""
        Analyze the following GitHub repository README.
        Provide a short summary (max 2 sentences) and a relevance score (0.0 to 1.0) based on how well it fits a developer interested in modern, efficient, and innovative tools.

        Format the output as JSON: {{"summary": "...", "score": 0.X}}

        README Content (truncated):
        {readme_content[:5000]}
        """
        
        text, error = await self._call_with_tracking("analyze_repo", prompt)
        
        if text:
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end != -1:
                    data = json.loads(text[start:end])
                    return data.get("summary", "No summary"), float(data.get("score", 0.0))
            except Exception as e:
                logger.error(f"Failed to parse AI response: {e}")
        
        # Mock response or error fallback
        if error == "rate_limit":
            return "⏳ Rate limited - skipped analysis", 0.3
        return "A interesting repository found by the mock brain.", 0.85

    async def generate_strategy_v2(self, mission: Dict[str, Any], session_stats: Dict[str, Any], feedback_history: List[Dict[str, Any]], analytics_report: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a new search strategy based on MISSION, Stats, and Feedback."""
        stats_str = json.dumps(session_stats, indent=2)
        feedback_str = json.dumps(feedback_history[-20:], indent=2) if feedback_history else "[]"
        mission_str = json.dumps(mission, indent=2)
        analytics_str = json.dumps(analytics_report, indent=2) if analytics_report else "{}"

        prompt = f"""
        You are an Autonomous Research Manager. Optimize the search strategy for a GitHub scraper.

        MISSION:
        {mission_str}

        LAST SESSION STATS:
        {stats_str}

        LONG_TERM ANALYTICS REPORT:
        {analytics_str}

        USER FEEDBACK (Recent):
        {feedback_str}

        TASK:
        Analyze the yield rates and rejection reasons together.
        - If 'ai_yield' is low, tighten keywords.
        - If 'user_acceptance_rate' is low, check 'rejection_analysis' for why the user hates the results (e.g. specific languages, frameworks).
        - Add 'exclude_patterns' to filter out rejected topics.
        
        Return a JSON object with this structure:
        {{
            "keywords": ["list", "of", "keywords"],
            "languages": ["list", "of", "languages"],
            "min_stars": 50,
            "exclude_patterns": ["regex", "patterns"],
            "date_range": "pushed>2024-01-01",
            "sort_by": "updated"
        }}
        """
        
        text, error = await self._call_with_tracking("generate_strategy", prompt)
        
        if text:
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end != -1:
                    return json.loads(text[start:end])
            except Exception as e:
                logger.error(f"Failed to parse strategy response: {e}")

        # Mock fallback strategy
        return {
            "keywords": mission.get("languages", ["Python"]) + ["framework"],
            "languages": mission.get("languages", ["Python"]),
            "min_stars": max(10, mission.get("min_stars", 50) - 10),
            "exclude_patterns": ["tutorial"],
            "date_range": "pushed>2023-01-01",
            "sort_by": "stars"
        }

    async def generate_strategy(self, feedback_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a new search strategy based on feedback."""
        if self.model and feedback_history:
            try:
                history_str = json.dumps(feedback_history, indent=2)
                prompt = f"""
                Based on the following user feedback history for GitHub repositories, suggest a new search strategy.

                History:
                {history_str}

                Return a JSON object with this structure:
                {{
                    "keywords": ["list", "of", "keywords"],
                    "languages": ["list", "of", "languages"],
                    "min_stars": 100
                }}
                """
                response = self.model.generate_content(prompt)
                text = response.text
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end != -1:
                    return json.loads(text[start:end])
            except Exception as e:
                logger.error(f"CloudBrain strategy generation failed: {e}")

        # Mock strategy
        return {
            "keywords": ["machine learning", "rust", "productivity"],
            "languages": ["Python", "Rust", "TypeScript"],
            "min_stars": 50
        }
