"""
A17a Event Publisher and A17b Method Responder.
S08 publishes events to S14 and responds to method calls from S14.
"""
from ..services.MessageQueueService import MessageQueueService
from ..services.MetricsService import MetricsService
import threading
import time
from typing import Dict


class S14IntegrationService:
    """
    Service to integrate with S14 Partner Metrics Service.
    - Publishes events to S14 (A17a)
    - Responds to method calls from S14 (A17b)
    """
    
    def __init__(self, mq_service: MessageQueueService, metrics_service: MetricsService):
        self.mq_service = mq_service
        self.metrics_service = metrics_service
        self.mq_lock = threading.Lock()
        
        # A17a: Event publishing
        self.s08_events_queue = "s08_events_queue"
        self.event_buffer = []
        self.buffer_lock = threading.Lock()
        
        # A17b: Method responder
        self.s14_s08_requests_queue = "s14_s08_requests_queue"
        self.s14_s08_responses_queue = "s14_s08_responses_queue"
        
        # Method map for A17b
        self.method_map = {
            "get_partner_conversation_statistics": self._handle_get_partner_conversation_statistics,
            "get_partner_satisfaction_distribution": self._handle_get_partner_satisfaction_distribution
        }
        
        # Start services
        self._start_event_publisher()
        self._start_method_responder()
    
    # A17a: Event Publisher
    
    def _start_event_publisher(self):
        """Start background thread to publish buffered events."""
        publisher_thread = threading.Thread(
            target=self._event_publisher_worker,
            daemon=True,
            name="S14-EventPublisher"
        )
        publisher_thread.start()
        print("[S14IntegrationService] Started event publisher")
    
    def _event_publisher_worker(self):
        """Background worker to batch publish events every 1 second."""
        with self.mq_lock:
            mq = self.mq_service.clone()
        mq.declare_queue(self.s08_events_queue)
        
        while True:
            time.sleep(1)  # Batch window: 1 second
            
            with self.buffer_lock:
                if not self.event_buffer:
                    continue
                
                events_to_publish = self.event_buffer[:50]  # Max 50 events per batch
                self.event_buffer = self.event_buffer[50:]
            
            # Publish events
            for event in events_to_publish:
                try:
                    mq.publish_message(self.s08_events_queue, event)
                    print(f"[A17a] Published event: {event['event_type']}")
                except Exception as e:
                    print(f"[A17a] Failed to publish event: {e}")
    
    def publish_event(self, event_type: str, params: Dict):
        """
        Buffer an event for publishing to S14.
        Event types: conversation_start_by_partner, conversation_changed_status_by_partner,
                    conversation_satisfaction_change_by_partner
        """
        import uuid
        event = {
            "event_type": event_type,
            "params": params,
            "id": str(uuid.uuid4())
        }
        
        with self.buffer_lock:
            self.event_buffer.append(event)
    
    def publish_conversation_start(self, conversation_id: str, partner_id: str, started_at: str):
        """Publish conversation_start_by_partner event."""
        self.publish_event("conversation_start_by_partner", {
            "conversation_id": conversation_id,
            "partner_id": partner_id,
            "started_at": started_at
        })
    
    def publish_conversation_status_changed(self, conversation_id: str, partner_id: str, 
                                           old_status: str, new_status: str, updated_at: str):
        """Publish conversation_changed_status_by_partner event."""
        self.publish_event("conversation_changed_status_by_partner", {
            "conversation_id": conversation_id,
            "partner_id": partner_id,
            "old_status": old_status,
            "new_status": new_status,
            "updated_at": updated_at
        })
    
    def publish_satisfaction_changed(self, conversation_id: str, partner_id: str,
                                    old_satisfaction: int, new_satisfaction: int, updated_at: str):
        """Publish conversation_satisfaction_change_by_partner event."""
        self.publish_event("conversation_satisfaction_change_by_partner", {
            "conversation_id": conversation_id,
            "partner_id": partner_id,
            "old_satisfaction": old_satisfaction,
            "new_satisfaction": new_satisfaction,
            "updated_at": updated_at
        })
    
    # A17b: Method Responder
    
    def _start_method_responder(self):
        """Start background threads to respond to method calls from S14."""
        # Start multiple worker threads for parallel processing
        for i in range(5):
            thread = threading.Thread(
                target=self._method_responder_worker,
                daemon=True,
                name=f"S14-MethodResponder-{i}"
            )
            thread.start()
        
        print("[S14IntegrationService] Started method responder with 5 worker threads")
    
    def _method_responder_worker(self):
        """Worker thread to consume and respond to method calls."""
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        mq.declare_queue(self.s14_s08_requests_queue)
        mq.declare_queue(self.s14_s08_responses_queue)
        
        # Create controller to handle requests
        controller = MethodResponderController(
            mq,
            self.s14_s08_responses_queue,
            self.method_map
        )
        
        mq.register_callback(self.s14_s08_requests_queue, controller.handle_request)
        mq.start_consuming()
    
    # A17b Method Handlers
    
    def _handle_get_partner_conversation_statistics(self, params: Dict) -> Dict:
        """
        Handle get_partner_conversation_statistics method.
        Returns conversation statistics for a specific partner.
        """
        partner_id = params.get("partner_id")
        if not partner_id:
            raise ValueError("Missing required parameter: partner_id")
        
        try:
            stats = self.metrics_service.get_partner_conversation_statistics(partner_id)
            return stats
        except ValueError as e:
            error_msg = str(e)
            if error_msg == "PARTNER_NOT_FOUND":
                raise ValueError("PARTNER_NOT_FOUND")
            else:
                raise Exception("DB_CONNECTION_ERROR")
    
    def _handle_get_partner_satisfaction_distribution(self, params: Dict) -> Dict:
        """
        Handle get_partner_satisfaction_distribution method.
        Returns satisfaction distribution for a specific partner.
        """
        partner_id = params.get("partner_id")
        if not partner_id:
            raise ValueError("Missing required parameter: partner_id")
        
        try:
            distribution = self.metrics_service.get_partner_satisfaction_distribution(partner_id)
            return distribution
        except ValueError as e:
            error_msg = str(e)
            if error_msg == "PARTNER_NOT_FOUND":
                raise ValueError("PARTNER_NOT_FOUND")
            elif error_msg == "NO_DATA_FOUND":
                raise ValueError("NO_DATA_FOUND")
            else:
                raise Exception("DB_CONNECTION_ERROR")


class MethodResponderController:
    """
    Controller to handle method requests from S14.
    Similar pattern to MessageQueueService-usage-example.py
    """
    
    def __init__(self, mq: MessageQueueService, response_queue: str, method_map: Dict):
        self.mq = mq
        self.response_queue = response_queue
        self.method_map = method_map
    
    def handle_request(self, message: dict):
        """Handle incoming method request."""
        request_id = message.get("id")
        if not request_id:
            print(f"[A17b] Request missing id: {message}")
            return
        
        result_status = "success"
        try:
            result_content = self._handle_request_with_id(request_id, message)
        except ValueError as e:
            # Special error codes
            result_status = "error"
            result_content = str(e)
        except Exception as e:
            result_status = "error"
            result_content = str(e)
        
        response = {
            "id": request_id,
            "result": {
                "status": result_status,
                "content": result_content
            }
        }
        
        self.mq.publish_message(self.response_queue, response)
        print(f"[A17b] Sent response for request_id={request_id}, status={result_status}")
    
    def _handle_request_with_id(self, request_id: str, message: dict):
        """Handle request and return result content."""
        method_name = message.get("method")
        if not method_name:
            raise ValueError("Missing 'method' field")
        
        method = self.method_map.get(method_name)
        if not method:
            raise ValueError(f"Unknown method: {method_name}")
        
        params = message.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("'params' must be a dict")
        
        return method(params)
