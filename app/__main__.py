"""
S08 Metrics Service - Main entry point.
"""
import os
from flask import Flask
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv()

# Import services
from app.services.MessageQueueService import MessageQueueService
from app.services.MetricsService import MetricsService
from app.services.EventConsumerService import EventConsumerService
from app.services.MethodCallerService import MethodCallerService
from app.services.S14IntegrationService import S14IntegrationService


def initialize_metrics_from_services(metrics_service: MetricsService, method_caller: MethodCallerService):
    """
    Initialize metrics by fetching initial data from S01, S04, S07.
    This runs at service startup as specified in the documentation.
    """
    print("[Startup] Initializing metrics from peer services...")
    
    # Flow 1: Initialize total customers from S04
    try:
        customer_count = method_caller.get_customers_count()
        metrics_service.initialize_total_customers(customer_count)
        print(f"[Startup] Initialized total_customers: {customer_count}")
    except Exception as e:
        print(f"[Startup] Failed to initialize total_customers: {e}")
    
    # Flow 2 & 4: Initialize conversation statistics from S01
    try:
        conv_stats = method_caller.get_conversation_statistics()
        metrics_service.initialize_conversation_statistics(conv_stats)
        print(f"[Startup] Initialized conversation statistics: {conv_stats}")
    except Exception as e:
        print(f"[Startup] Failed to initialize conversation statistics: {e}")
    
    # Flow 3: Initialize satisfaction distribution from S01
    try:
        satisfaction_dist = method_caller.get_customer_satisfaction_distribution()
        metrics_service.initialize_satisfaction_distribution(satisfaction_dist)
        print(f"[Startup] Initialized satisfaction distribution: {satisfaction_dist}")
    except Exception as e:
        print(f"[Startup] Failed to initialize satisfaction distribution: {e}")
    
    # Flow 5: Initialize per-partner offload data from S01
    try:
        partner_offload_data = method_caller.get_offloaded_conversations_by_partner()
        metrics_service.initialize_partner_offload_data(partner_offload_data)
        print(f"[Startup] Initialized partner offload data: {partner_offload_data}")
    except Exception as e:
        print(f"[Startup] Failed to initialize partner offload data: {e}")
    
    # Flow 5: Initialize partner cache from S07
    try:
        partners = method_caller.get_partners()
        metrics_service.update_partner_cache(partners)
        print(f"[Startup] Initialized partner cache: {len(partners)} partners")
    except Exception as e:
        print(f"[Startup] Failed to initialize partner cache: {e}")
    
    print("[Startup] Metrics initialization complete")


def start_partner_cache_refresh_worker(metrics_service: MetricsService, method_caller: MethodCallerService):
    """
    Background worker to refresh partner cache every hour.
    """
    import time
    
    def worker():
        while True:
            time.sleep(3600)  # 1 hour
            try:
                partners = method_caller.get_partners()
                metrics_service.update_partner_cache(partners)
                print(f"[PartnerCacheRefresh] Updated partner cache: {len(partners)} partners")
            except Exception as e:
                print(f"[PartnerCacheRefresh] Failed to refresh partner cache: {e}")
    
    thread = threading.Thread(target=worker, daemon=True, name="PartnerCacheRefresh")
    thread.start()
    print("[Startup] Started partner cache refresh worker")


def main():
    """Main entry point for S08 Metrics Service."""
    print("=" * 60)
    print("Starting S08 Metrics Service - Telcenter Core")
    print("=" * 60)
    
    # Initialize Flask app
    from . import app

    def initialize_services():
        # Initialize services
        print("[Startup] Initializing services...")
        
        # 1. MessageQueue Service
        mq_service = MessageQueueService()
        print("[Startup] MessageQueueService initialized")
        
        # 2. Metrics Service (in-memory metrics storage)
        metrics_service = MetricsService()
        print("[Startup] MetricsService initialized")
        
        # 3. Method Caller Service (call S01, S04, S07)
        method_caller = MethodCallerService(mq_service)
        print("[Startup] MethodCallerService initialized")
        
        # 4. Initialize metrics from peer services
        initialize_metrics_from_services(metrics_service, method_caller)
        
        # 5. Event Consumer Service (consume events from S01, S04)
        event_consumer = EventConsumerService(mq_service, metrics_service)
        event_consumer.start()
        print("[Startup] EventConsumerService started")
        
        # 6. S14 Integration Service (publish events to S14, respond to S14 method calls)
        s14_integration = S14IntegrationService(mq_service, metrics_service)
        print("[Startup] S14IntegrationService initialized")
        
        # 7. Start partner cache refresh worker
        start_partner_cache_refresh_worker(metrics_service, method_caller)
    
    threading.Thread(target=initialize_services, daemon=True, name="ServiceInitializer").start()
        
    # 8. HTTP controllers are registered via flask-restx in app/__init__.py
    print("[Startup] HTTP controllers registered")
    
    # Get Flask configuration from environment
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5008"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    print("=" * 60)
    print(f"S08 Metrics Service running on http://{host}:{port}")
    print("=" * 60)
    print("\nAvailable HTTP endpoints (H21):")
    print("  GET /api/v1/metrics/users/total")
    print("  GET /api/v1/core/metrics/conversations/summary")
    print("  GET /api/v1/core/metrics/consultations/satisfaction")
    print("  GET /api/v1/core/metrics/consultations/offload-rate")
    print("  GET /api/v1/core/metrics/consultations/offload-rate-by-partner")
    print("\nRabbitMQ consumers running:")
    print("  A03a: s01_events_queue (S01 events)")
    print("  A04a: s04_events_queue (S04 events)")
    print("  A17b: s14_s08_requests_queue (S14 method calls)")
    print("\nRabbitMQ publishers:")
    print("  A17a: s08_events_queue (events to S14)")
    print("=" * 60)
    
    # Start Flask app
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    main()
