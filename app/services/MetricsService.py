"""
Metrics Service for S08 - Telcenter Core Metrics Service.
Maintains in-memory metrics that are updated via events from other services.
"""
import threading
from typing import Dict, Optional


class MetricsService:
    """
    Service to maintain real-time metrics data.
    Thread-safe implementation using locks.
    """
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # Flow 1: Total Customers
        self.total_customers = 0
        
        # Flow 2: Conversation Metrics
        self.total_conversations = 0
        self.texting_conversations = 0
        self.calling_conversations = 0
        self.forwarding_conversations = 0
        self.ai_failed_conversations = 0
        self.offloaded_conversations = 0
        
        # Flow 3: Satisfaction Metrics
        self.satisfaction_1 = 0
        self.satisfaction_2 = 0
        self.satisfaction_3 = 0
        self.satisfaction_4 = 0
        self.satisfaction_5 = 0
        self.total_ratings = 0
        self.average_rating = 0.0
        
        # Flow 5: Per-Partner Metrics
        self.partner_metrics: Dict[str, Dict] = {}
        # Structure: {partner_id: {total_conversations, offloaded, texting, calling, forwarding, ai_failed, satisfaction_counts}}
        
        # Partner name cache from S07
        self.partner_cache: Dict[str, str] = {}  # {partner_id: partner_name}
        self.partner_cache_time = 0
    
    # Flow 1: Customer Metrics
    
    def initialize_total_customers(self, count: int):
        """Initialize total customers count from S04."""
        with self.lock:
            self.total_customers = count
    
    def increment_total_customers(self):
        """Handle customer_registered event."""
        with self.lock:
            self.total_customers += 1
    
    def get_total_customers(self) -> int:
        """Get current total customers count."""
        with self.lock:
            return self.total_customers
    
    # Flow 2: Conversation Metrics
    
    def initialize_conversation_statistics(self, stats: Dict):
        """Initialize conversation statistics from S01."""
        with self.lock:
            self.total_conversations = stats.get("total_conversations", 0)
            self.texting_conversations = stats.get("texting_conversations", 0)
            self.calling_conversations = stats.get("calling_conversations", 0)
            self.forwarding_conversations = stats.get("forwarding_conversations", 0)
            self.ai_failed_conversations = stats.get("ai_failed_conversations", 0)
            self.offloaded_conversations = stats.get("offloaded_conversations", 0)
    
    def handle_conversation_start(self, partner_id: str):
        """Handle conversation_start event."""
        with self.lock:
            self.total_conversations += 1
            self.texting_conversations += 1  # Default status: AI_AGENT_TEXTING
            
            # Update partner metrics
            if partner_id not in self.partner_metrics:
                self._init_partner_metrics(partner_id)
            self.partner_metrics[partner_id]["total_conversations"] += 1
            self.partner_metrics[partner_id]["texting_conversations"] += 1
    
    def handle_conversation_status_update(self, partner_id: str, old_status: str, new_status: str):
        """Handle conversation_status_update event."""
        with self.lock:
            # Decrement old status category
            self._decrement_status_counter(old_status)
            if partner_id in self.partner_metrics:
                self._decrement_partner_status_counter(partner_id, old_status)
            
            # Increment new status category
            self._increment_status_counter(new_status)
            if partner_id not in self.partner_metrics:
                self._init_partner_metrics(partner_id)
            self._increment_partner_status_counter(partner_id, new_status)
    
    def handle_conversation_forwarded(self, partner_id: str):
        """Handle conversation_forwarded event."""
        with self.lock:
            self.ai_failed_conversations += 1
            self.offloaded_conversations = self.total_conversations - self.ai_failed_conversations
            
            # Update partner metrics
            if partner_id not in self.partner_metrics:
                self._init_partner_metrics(partner_id)
            self.partner_metrics[partner_id]["ai_failed_conversations"] += 1
            self.partner_metrics[partner_id]["offloaded_conversations"] = (
                self.partner_metrics[partner_id]["total_conversations"] - 
                self.partner_metrics[partner_id]["ai_failed_conversations"]
            )
    
    def get_conversation_summary(self) -> Dict:
        """Get conversation summary for H21.2."""
        with self.lock:
            return {
                "total_conversations": self.total_conversations,
                "texting_conversations": self.texting_conversations,
                "calling_conversations": self.calling_conversations
            }
    
    # Flow 3: Satisfaction Metrics
    
    def initialize_satisfaction_distribution(self, distribution: Dict):
        """Initialize satisfaction distribution from S01."""
        with self.lock:
            self.satisfaction_1 = distribution.get("satisfaction_1", 0)
            self.satisfaction_2 = distribution.get("satisfaction_2", 0)
            self.satisfaction_3 = distribution.get("satisfaction_3", 0)
            self.satisfaction_4 = distribution.get("satisfaction_4", 0)
            self.satisfaction_5 = distribution.get("satisfaction_5", 0)
            self.total_ratings = (
                self.satisfaction_1 + self.satisfaction_2 + self.satisfaction_3 +
                self.satisfaction_4 + self.satisfaction_5
            )
            self._recalculate_average_rating()
    
    def handle_satisfaction_changed(self, partner_id: str, old_satisfaction: Optional[int], new_satisfaction: int):
        """Handle conversation_customer_satisfaction_changed event."""
        with self.lock:
            # Decrement old satisfaction if exists
            if old_satisfaction is not None:
                self._decrement_satisfaction_counter(old_satisfaction)
                if partner_id in self.partner_metrics:
                    self._decrement_partner_satisfaction_counter(partner_id, old_satisfaction)
            
            # Increment new satisfaction
            self._increment_satisfaction_counter(new_satisfaction)
            if partner_id not in self.partner_metrics:
                self._init_partner_metrics(partner_id)
            self._increment_partner_satisfaction_counter(partner_id, new_satisfaction)
            
            # Recalculate totals and average
            self.total_ratings = (
                self.satisfaction_1 + self.satisfaction_2 + self.satisfaction_3 +
                self.satisfaction_4 + self.satisfaction_5
            )
            self._recalculate_average_rating()
            
            # Recalculate partner average
            self._recalculate_partner_average_rating(partner_id)
    
    def get_satisfaction_metrics(self) -> Dict:
        """Get satisfaction metrics for H21.3."""
        with self.lock:
            return {
                "total_conversations": self.total_ratings,
                "satisfaction_distribution": {
                    "satisfaction_1": self.satisfaction_1,
                    "satisfaction_2": self.satisfaction_2,
                    "satisfaction_3": self.satisfaction_3,
                    "satisfaction_4": self.satisfaction_4,
                    "satisfaction_5": self.satisfaction_5
                },
                "average_rating": round(self.average_rating, 2)
            }
    
    # Flow 4: Offload Rate
    
    def get_offload_rate(self) -> Dict:
        """Get offload rate metrics for H21.4."""
        with self.lock:
            offload_rate = 0.0
            if self.total_conversations > 0:
                offload_rate = (self.offloaded_conversations / self.total_conversations) * 100
            
            return {
                "total_conversations": self.total_conversations,
                "ai_failed_conversation": self.ai_failed_conversations,
                "offloaded_conversations": self.offloaded_conversations,
                "offload_rate_percentage": round(offload_rate, 2)
            }
    
    # Flow 5: Per-Partner Offload Rate
    
    def initialize_partner_offload_data(self, partner_data: Dict[str, int]):
        """Initialize per-partner offload data from S01."""
        with self.lock:
            for partner_id, offloaded_count in partner_data.items():
                if partner_id not in self.partner_metrics:
                    self._init_partner_metrics(partner_id)
                self.partner_metrics[partner_id]["offloaded_conversations"] = offloaded_count
    
    def update_partner_cache(self, partners: list):
        """Update partner name cache from S07."""
        with self.lock:
            self.partner_cache = {p["partner_id"]: p["name"] for p in partners}
            import time
            self.partner_cache_time = time.time()
    
    def get_partner_cache_age_minutes(self) -> float:
        """Get age of partner cache in minutes."""
        import time
        with self.lock:
            return (time.time() - self.partner_cache_time) / 60
    
    def get_partner_offload_rate(self, partner_id: Optional[str] = None) -> Dict:
        """Get per-partner offload rate for H21.5."""
        with self.lock:
            partners_list = []
            total_all_conversations = 0
            total_all_offloaded = 0
            
            partners_to_process = [partner_id] if partner_id else list(self.partner_metrics.keys())
            
            for pid in partners_to_process:
                if pid not in self.partner_metrics:
                    continue
                
                pm = self.partner_metrics[pid]
                total_conv = pm["total_conversations"]
                offloaded = pm["offloaded_conversations"]
                ai_failed = pm["ai_failed_conversations"]
                
                offload_rate = 0.0
                if total_conv > 0:
                    offload_rate = (offloaded / total_conv) * 100
                
                partner_name = self.partner_cache.get(pid, pid)
                
                partners_list.append({
                    "partner_id": pid,
                    "partner_name": partner_name,
                    "total_conversations": total_conv,
                    "offloaded_conversations": offloaded,
                    "ai_failed_conversations": ai_failed,
                    "offload_rate_percentage": round(offload_rate, 2)
                })
                
                total_all_conversations += total_conv
                total_all_offloaded += offloaded
            
            overall_rate = 0.0
            if total_all_conversations > 0:
                overall_rate = (total_all_offloaded / total_all_conversations) * 100
            
            return {
                "total_consultations": total_all_conversations,
                "partners": partners_list,
                "overall_offload_rate_percentage": round(overall_rate, 2)
            }
    
    # A17b: Methods for S14
    
    def get_partner_conversation_statistics(self, partner_id: str) -> Dict:
        """Get conversation statistics for a specific partner (A17b)."""
        with self.lock:
            if partner_id not in self.partner_metrics:
                raise ValueError("PARTNER_NOT_FOUND")
            
            pm = self.partner_metrics[partner_id]
            return {
                "partner_id": partner_id,
                "total_conversations": pm["total_conversations"],
                "forwarding_conversations": pm["forwarding_conversations"],
                "texting_conversations": pm["texting_conversations"],
                "calling_conversations": pm["calling_conversations"],
                "ai_failed_conversations": pm["ai_failed_conversations"],
                "offloaded_conversations": pm["offloaded_conversations"]
            }
    
    def get_partner_satisfaction_distribution(self, partner_id: str) -> Dict:
        """Get satisfaction distribution for a specific partner (A17b)."""
        with self.lock:
            if partner_id not in self.partner_metrics:
                raise ValueError("PARTNER_NOT_FOUND")
            
            pm = self.partner_metrics[partner_id]
            satisfaction = pm["satisfaction"]
            
            # Check if any satisfaction data exists
            total = sum(satisfaction.values())
            if total == 0:
                raise ValueError("NO_DATA_FOUND")
            
            return {
                "partner_id": partner_id,
                "satisfaction_1": satisfaction.get("satisfaction_1", 0),
                "satisfaction_2": satisfaction.get("satisfaction_2", 0),
                "satisfaction_3": satisfaction.get("satisfaction_3", 0),
                "satisfaction_4": satisfaction.get("satisfaction_4", 0),
                "satisfaction_5": satisfaction.get("satisfaction_5", 0)
            }
    
    # Helper methods
    
    def _init_partner_metrics(self, partner_id: str):
        """Initialize metrics for a new partner."""
        self.partner_metrics[partner_id] = {
            "total_conversations": 0,
            "texting_conversations": 0,
            "calling_conversations": 0,
            "forwarding_conversations": 0,
            "ai_failed_conversations": 0,
            "offloaded_conversations": 0,
            "satisfaction": {
                "satisfaction_1": 0,
                "satisfaction_2": 0,
                "satisfaction_3": 0,
                "satisfaction_4": 0,
                "satisfaction_5": 0
            },
            "average_rating": 0.0
        }
    
    def _increment_status_counter(self, status: str):
        """Increment counter for given status."""
        if status in ["AI_AGENT_TEXTING", "HUMAN_AGENT_TEXTING"]:
            self.texting_conversations += 1
        elif status in ["AI_AGENT_CALLING", "HUMAN_AGENT_CALLING"]:
            self.calling_conversations += 1
        elif status == "FORWARDING":
            self.forwarding_conversations += 1
    
    def _decrement_status_counter(self, status: str):
        """Decrement counter for given status."""
        if status in ["AI_AGENT_TEXTING", "HUMAN_AGENT_TEXTING"]:
            self.texting_conversations = max(0, self.texting_conversations - 1)
        elif status in ["AI_AGENT_CALLING", "HUMAN_AGENT_CALLING"]:
            self.calling_conversations = max(0, self.calling_conversations - 1)
        elif status == "FORWARDING":
            self.forwarding_conversations = max(0, self.forwarding_conversations - 1)
    
    def _increment_partner_status_counter(self, partner_id: str, status: str):
        """Increment partner status counter."""
        pm = self.partner_metrics[partner_id]
        if status in ["AI_AGENT_TEXTING", "HUMAN_AGENT_TEXTING"]:
            pm["texting_conversations"] += 1
        elif status in ["AI_AGENT_CALLING", "HUMAN_AGENT_CALLING"]:
            pm["calling_conversations"] += 1
        elif status == "FORWARDING":
            pm["forwarding_conversations"] += 1
    
    def _decrement_partner_status_counter(self, partner_id: str, status: str):
        """Decrement partner status counter."""
        pm = self.partner_metrics[partner_id]
        if status in ["AI_AGENT_TEXTING", "HUMAN_AGENT_TEXTING"]:
            pm["texting_conversations"] = max(0, pm["texting_conversations"] - 1)
        elif status in ["AI_AGENT_CALLING", "HUMAN_AGENT_CALLING"]:
            pm["calling_conversations"] = max(0, pm["calling_conversations"] - 1)
        elif status == "FORWARDING":
            pm["forwarding_conversations"] = max(0, pm["forwarding_conversations"] - 1)
    
    def _increment_satisfaction_counter(self, rating: int):
        """Increment satisfaction counter."""
        if rating == 1:
            self.satisfaction_1 += 1
        elif rating == 2:
            self.satisfaction_2 += 1
        elif rating == 3:
            self.satisfaction_3 += 1
        elif rating == 4:
            self.satisfaction_4 += 1
        elif rating == 5:
            self.satisfaction_5 += 1
    
    def _decrement_satisfaction_counter(self, rating: int):
        """Decrement satisfaction counter."""
        if rating == 1:
            self.satisfaction_1 = max(0, self.satisfaction_1 - 1)
        elif rating == 2:
            self.satisfaction_2 = max(0, self.satisfaction_2 - 1)
        elif rating == 3:
            self.satisfaction_3 = max(0, self.satisfaction_3 - 1)
        elif rating == 4:
            self.satisfaction_4 = max(0, self.satisfaction_4 - 1)
        elif rating == 5:
            self.satisfaction_5 = max(0, self.satisfaction_5 - 1)
    
    def _increment_partner_satisfaction_counter(self, partner_id: str, rating: int):
        """Increment partner satisfaction counter."""
        pm = self.partner_metrics[partner_id]
        key = f"satisfaction_{rating}"
        pm["satisfaction"][key] = pm["satisfaction"].get(key, 0) + 1
    
    def _decrement_partner_satisfaction_counter(self, partner_id: str, rating: int):
        """Decrement partner satisfaction counter."""
        pm = self.partner_metrics[partner_id]
        key = f"satisfaction_{rating}"
        pm["satisfaction"][key] = max(0, pm["satisfaction"].get(key, 0) - 1)
    
    def _recalculate_average_rating(self):
        """Recalculate average rating."""
        if self.total_ratings > 0:
            self.average_rating = (
                1 * self.satisfaction_1 +
                2 * self.satisfaction_2 +
                3 * self.satisfaction_3 +
                4 * self.satisfaction_4 +
                5 * self.satisfaction_5
            ) / self.total_ratings
        else:
            self.average_rating = 0.0
    
    def _recalculate_partner_average_rating(self, partner_id: str):
        """Recalculate partner average rating."""
        pm = self.partner_metrics[partner_id]
        sat = pm["satisfaction"]
        total = sum(sat.values())
        
        if total > 0:
            pm["average_rating"] = (
                1 * sat.get("satisfaction_1", 0) +
                2 * sat.get("satisfaction_2", 0) +
                3 * sat.get("satisfaction_3", 0) +
                4 * sat.get("satisfaction_4", 0) +
                5 * sat.get("satisfaction_5", 0)
            ) / total
        else:
            pm["average_rating"] = 0.0
