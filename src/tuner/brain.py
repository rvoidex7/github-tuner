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
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except ImportError:
                logger.warning("google-generativeai not installed. CloudBrain will operate in mock mode.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}. CloudBrain will operate in mock mode.")
        else:
            logger.warning("No API key provided for CloudBrain. Operating in mock mode.")

    async def analyze_repo(self, readme_content: str) -> Tuple[str, float]:
        """Analyze a repo's README and return a summary and relevance score."""
        if self.model:
            try:
                prompt = f"""
                Analyze the following GitHub repository README.
                Provide a short summary (max 2 sentences) and a relevance score (0.0 to 1.0) based on how well it fits a developer interested in modern, efficient, and innovative tools.

                Format the output as JSON: {{"summary": "...", "score": 0.X}}

                README Content (truncated):
                {readme_content[:5000]}
                """
                response = self.model.generate_content(prompt)
                text = response.text
                # Simple parsing (robustness could be improved)
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end != -1:
                    data = json.loads(text[start:end])
                    return data.get("summary", "No summary"), float(data.get("score", 0.0))
            except Exception as e:
                logger.error(f"CloudBrain analysis failed: {e}")

        # Mock response
        return "A interesting repository found by the mock brain.", 0.85

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
