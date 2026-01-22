"""
TacticEngine - Farklı arama taktikleri havuzu.

Bu modül, GitHub aramalarında çeşitlilik sağlamak için farklı
taktikler sunar. Program kendi kendine taktik değiştirir.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SearchTactic:
    """Arama taktiği tanımı."""
    name: str
    description: str
    stars_min: int = 10
    stars_max: Optional[int] = None
    date_filter: Optional[str] = None  # "pushed:>2024-01-01"
    sort_by: str = "updated"  # updated, stars, forks
    page_range: tuple = (1, 5)
    per_page: int = 10
    keyword_strategy: str = "all"  # all, rotate, single
    weight: float = 1.0  # Seçilme ağırlığı (performansa göre değişir)


# Varsayılan taktikler havuzu
DEFAULT_TACTICS: List[SearchTactic] = [
    SearchTactic(
        name="trending",
        description="Son 30 günde güncellenen, aktif projeler",
        stars_min=20,
        date_filter="pushed:>{30_days_ago}",
        sort_by="updated",
        page_range=(1, 3),
        weight=1.5
    ),
    SearchTactic(
        name="rising_stars",
        description="Düşük yıldız ama aktif - henüz keşfedilmemiş",
        stars_min=10,
        stars_max=100,
        date_filter="pushed:>{14_days_ago}",
        sort_by="updated",
        page_range=(1, 5),
        weight=1.2
    ),
    SearchTactic(
        name="established",
        description="Yüksek yıldızlı, kanıtlanmış projeler",
        stars_min=500,
        sort_by="stars",
        page_range=(1, 10),
        weight=1.0
    ),
    SearchTactic(
        name="deep_dive",
        description="Derin sayfalarda arama - az görülen sonuçlar",
        stars_min=50,
        sort_by="updated",
        page_range=(5, 20),
        per_page=30,
        weight=0.8
    ),
    SearchTactic(
        name="keyword_rotation",
        description="Farklı keyword kombinasyonları dene",
        stars_min=30,
        keyword_strategy="rotate",
        page_range=(1, 5),
        weight=1.0
    ),
    SearchTactic(
        name="fresh_projects",
        description="Son 7 günde oluşturulan yeni projeler",
        stars_min=5,
        date_filter="created:>{7_days_ago}",
        sort_by="stars",
        page_range=(1, 3),
        weight=0.7
    ),
]


class TacticEngine:
    """
    Arama taktiklerini yöneten motor.
    
    Performansa göre taktik ağırlıklarını ayarlar ve
    en uygun taktiği seçer.
    """
    
    def __init__(self, storage=None):
        self.storage = storage
        self.tactics = {t.name: t for t in DEFAULT_TACTICS}
        self._mission_tactic_history: Dict[str, List[str]] = {}
    
    def _resolve_date_placeholder(self, date_filter: Optional[str]) -> Optional[str]:
        """Tarih placeholder'larını çöz."""
        if not date_filter:
            return None
        
        now = datetime.now()
        
        if "{30_days_ago}" in date_filter:
            date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            return date_filter.replace("{30_days_ago}", date)
        elif "{14_days_ago}" in date_filter:
            date = (now - timedelta(days=14)).strftime("%Y-%m-%d")
            return date_filter.replace("{14_days_ago}", date)
        elif "{7_days_ago}" in date_filter:
            date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            return date_filter.replace("{7_days_ago}", date)
        
        return date_filter
    
    def select_tactic(self, mission_name: str, performance_data: Dict[str, float] = None) -> SearchTactic:
        """
        Mission için en uygun taktiği seç.
        
        Weighted random selection kullanır - daha yüksek performanslı
        taktikler daha sık seçilir.
        """
        # Performans verisine göre ağırlıkları güncelle
        tactics_list = list(self.tactics.values())
        weights = []
        
        for tactic in tactics_list:
            base_weight = tactic.weight
            
            # Performans verisi varsa, ağırlığı ayarla
            if performance_data and tactic.name in performance_data:
                success_rate = performance_data[tactic.name]
                # Başarı oranı düşükse ağırlığı azalt (ama sıfırlama)
                adjusted_weight = base_weight * (0.3 + 0.7 * success_rate)
            else:
                adjusted_weight = base_weight
            
            # Son kullanılan taktiği biraz cezalandır (çeşitlilik için)
            history = self._mission_tactic_history.get(mission_name, [])
            if history and history[-1] == tactic.name:
                adjusted_weight *= 0.5
            
            weights.append(max(0.1, adjusted_weight))  # Minimum 0.1 ağırlık
        
        # Weighted random selection
        selected = random.choices(tactics_list, weights=weights, k=1)[0]
        
        # History güncelle
        if mission_name not in self._mission_tactic_history:
            self._mission_tactic_history[mission_name] = []
        self._mission_tactic_history[mission_name].append(selected.name)
        
        # Son 10 taktiği tut sadece
        self._mission_tactic_history[mission_name] = self._mission_tactic_history[mission_name][-10:]
        
        logger.info(f"🎯 Selected tactic: {selected.name} for mission: {mission_name}")
        return selected
    
    def rotate_tactic(self, mission_name: str) -> SearchTactic:
        """
        Mevcut taktik çalışmıyorsa zorla farklı bir taktik seç.
        """
        history = self._mission_tactic_history.get(mission_name, [])
        recent_tactics = set(history[-3:]) if history else set()
        
        # Son 3 taktikten farklı olanları tercih et
        available = [t for t in self.tactics.values() if t.name not in recent_tactics]
        
        if not available:
            available = list(self.tactics.values())
        
        selected = random.choice(available)
        
        if mission_name not in self._mission_tactic_history:
            self._mission_tactic_history[mission_name] = []
        self._mission_tactic_history[mission_name].append(selected.name)
        
        logger.info(f"🔄 Force-rotated to tactic: {selected.name} for mission: {mission_name}")
        return selected
    
    def build_query(self, tactic: SearchTactic, mission_goal: str, languages: List[str]) -> str:
        """
        Build GitHub search query from tactic and mission info.
        """
        import re
        
        # Stop words
        stop_words = {
            "and", "the", "for", "with", "this", "that", "from", "like", "look", 
            "find", "research", "focus", "on", "to", "a", "an", "of", "in", "or",
            "using", "similar", "tools", "best", "modern", "involving", "analyze",
            "existing", "such", "as", "alternatives", "those", "user's", "list",
            "identify", "directory", "project", "implementations", "libraries",
            "patterns", "improve", "features", "practices", "enhancements",
            "component", "templates", "architecture", "app", "web"
        }
        
        # Priority keywords
        priority_keywords = {
            "whatsapp", "crm", "dashboard", "admin", "api", "tui", "cli",
            "python", "rust", "react", "nextjs", "next.js", "daisyui",
            "tailwind", "wrapper", "bot", "agent", "automation", "workflow",
            "sdk", "client", "library"
        }
        
        # Keywords çıkar
        goal_words = [w.lower().strip(",.()\"'") for w in mission_goal.split()]
        
        found_priority = []
        other_keywords = []
        
        for w in goal_words:
            if len(w) < 3:
                continue
            if re.match(r'^https?://', w) or '/' in w or '\\' in w:
                continue
            if w.startswith("d:") or w.startswith("c:"):
                continue
            if w in stop_words:
                continue
            
            if w in priority_keywords:
                found_priority.append(w)
            else:
                other_keywords.append(w)
        
        # Keyword strategy'ye göre keywords seç
        if tactic.keyword_strategy == "rotate":
            # Her seferinde farklı subset
            all_kw = found_priority + other_keywords
            if len(all_kw) > 2:
                keywords = random.sample(all_kw, min(2, len(all_kw)))
            else:
                keywords = all_kw[:2]
        elif tactic.keyword_strategy == "single":
            # Sadece en önemli keyword
            keywords = (found_priority[:1] or other_keywords[:1])
        else:
            # Tümü (max 3)
            keywords = found_priority[:2] + other_keywords[:max(0, 3 - len(found_priority[:2]))]
        
        if not keywords:
            keywords = ["developer", "tools"]
        
        # Query parçaları
        query_parts = keywords[:3]
        
        # Dil filtresi (sadece ilk non-Any dil)
        for lang in languages:
            if lang.lower() != "any":
                query_parts.append(f"language:{lang}")
                break
        
        # Yıldız filtresi
        if tactic.stars_max:
            query_parts.append(f"stars:{tactic.stars_min}..{tactic.stars_max}")
        else:
            query_parts.append(f"stars:>={tactic.stars_min}")
        
        # Tarih filtresi
        date_filter = self._resolve_date_placeholder(tactic.date_filter)
        if date_filter:
            query_parts.append(date_filter)
        
        query = " ".join(query_parts)
        logger.debug(f"Built query: {query}")
        return query
    
    def get_search_params(self, tactic: SearchTactic) -> Dict[str, Any]:
        """Return search parameters for the tactic."""
        page = random.randint(tactic.page_range[0], tactic.page_range[1])
        
        return {
            "page": page,
            "per_page": tactic.per_page,
            "sort": tactic.sort_by,
        }
    
    def update_tactic_weight(self, tactic_name: str, success_rate: float):
        """Update tactic weight based on performance."""
        if tactic_name in self.tactics:
            # Ağırlığı başarı oranına göre ayarla (0.5 - 2.0 arası)
            new_weight = 0.5 + (1.5 * success_rate)
            self.tactics[tactic_name].weight = max(0.3, min(2.0, new_weight))
            logger.debug(f"Updated {tactic_name} weight to {new_weight:.2f}")
    
    def get_tactic_stats(self) -> Dict[str, Dict[str, Any]]:
        """Tüm taktiklerin durumunu döndür."""
        return {
            name: {
                "description": t.description,
                "weight": t.weight,
                "stars_range": f"{t.stars_min}-{t.stars_max or '∞'}",
            }
            for name, t in self.tactics.items()
        }
