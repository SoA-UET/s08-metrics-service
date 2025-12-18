"""
Event consumers for A03a and A04a - consume events from S01 and S04.
"""
from ..services.MessageQueueService import MessageQueueService
from ..services.MetricsService import MetricsService
import threading


class EventConsumerService:
    """
    Service to consume events from S01 and S04 via RabbitMQ.
    Updates metrics in real-time as events are received.
    """
    
    def __init__(self, mq_service: MessageQueueService, metrics_service: MetricsService):
        self.mq_service = mq_service
        self.metrics_service = metrics_service
        self.mq_lock = threading.Lock()
        self.threads = []
        
        # Queue names
        self.s01_events_queue = "s01_events_queue"
        self.s04_events_queue = "s04_events_queue"
        
        # Event counters
        self.invalid_events_counter = 0
    
    def start(self, num_threads: int = 2):
        """
        Start consuming events in background threads.
        Uses 1 thread for S01 events and 1 thread for S04 events.
        """
        # Start S01 event consumer
        s01_thread = threading.Thread(
            target=self._consume_s01_events,
            daemon=True,
            name="S01-EventConsumer"
        )
        s01_thread.start()
        self.threads.append(s01_thread)
        
        # Start S04 event consumer
        s04_thread = threading.Thread(
            target=self._consume_s04_events,
            daemon=True,
            name="S04-EventConsumer"
        )
        s04_thread.start()
        self.threads.append(s04_thread)
        
        print("[EventConsumerService] Started consuming events from S01 and S04")
    
    def _consume_s01_events(self):
        """Consume events from S01 Consultation Service (A03a)."""
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        mq.declare_queue(self.s01_events_queue)
        mq.register_callback(self.s01_events_queue, self._handle_s01_event)
        mq.start_consuming()
    
    def _consume_s04_events(self):
        """Consume events from S04 Customer Identity Service (A04a)."""
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        mq.declare_queue(self.s04_events_queue)
        mq.register_callback(self.s04_events_queue, self._handle_s04_event)
        mq.start_consuming()
    
    def _handle_s01_event(self, message: dict):
        """
        Handle events from S01 (A03a).
        Events: conversation_start, conversation_status_update, 
                conversation_customer_satisfaction_changed, conversation_forwarded
        """
        try:
            event_type = message.get("event_type")
            params = message.get("params", {})
            
            if not event_type:
                print(f"[S01 Event] Missing event_type: {message}")
                self._increment_invalid_counter()
                return
            
            if event_type == "conversation_start":
                self._handle_conversation_start(params)
            elif event_type == "conversation_status_update":
                self._handle_conversation_status_update(params)
            elif event_type == "conversation_customer_satisfaction_changed":
                self._handle_satisfaction_changed(params)
            elif event_type == "conversation_forwarded":
                self._handle_conversation_forwarded(params)
            else:
                print(f"[S01 Event] Unknown event type: {event_type}")
                self._increment_invalid_counter()
                
        except Exception as e:
            print(f"[S01 Event] Error processing event: {e}, message: {message}")
            self._increment_invalid_counter()
    
    def _handle_s04_event(self, message: dict):
        """
        Handle events from S04 (A04a).
        Events: customer_registered
        """
        try:
            event_type = message.get("event_type")
            params = message.get("params", {})
            
            if not event_type:
                print(f"[S04 Event] Missing event_type: {message}")
                self._increment_invalid_counter()
                return
            
            if event_type == "customer_registered":
                self._handle_customer_registered(params)
            else:
                print(f"[S04 Event] Unknown event type: {event_type}")
                self._increment_invalid_counter()
                
        except Exception as e:
            print(f"[S04 Event] Error processing event: {e}, message: {message}")
            self._increment_invalid_counter()
    
    # A03a Event Handlers
    
    def _handle_conversation_start(self, params: dict):
        """Handle conversation_start event."""
        conversation_id = params.get("conversation_id")
        partner_id = params.get("partner_id")
        
        if not conversation_id or not partner_id:
            print(f"[conversation_start] Missing required fields: {params}")
            self._increment_invalid_counter()
            return
        
        self.metrics_service.handle_conversation_start(partner_id)
        print(f"[conversation_start] Processed: conversation_id={conversation_id}, partner_id={partner_id}")
    
    def _handle_conversation_status_update(self, params: dict):
        """Handle conversation_status_update event."""
        conversation_id = params.get("conversation_id")
        partner_id = params.get("partner_id")
        old_status = params.get("old_status")
        new_status = params.get("new_status")
        
        if not all([conversation_id, partner_id, old_status, new_status]):
            print(f"[conversation_status_update] Missing required fields: {params}")
            self._increment_invalid_counter()
            return
        
        self.metrics_service.handle_conversation_status_update(partner_id, old_status, new_status)
        print(f"[conversation_status_update] Processed: conversation_id={conversation_id}, {old_status} -> {new_status}")
    
    def _handle_satisfaction_changed(self, params: dict):
        """Handle conversation_customer_satisfaction_changed event."""
        conversation_id = params.get("conversation_id")
        partner_id = params.get("partner_id")
        old_satisfaction = params.get("old_satisfaction")  # Can be None for new rating
        new_satisfaction = params.get("new_satisfaction")
        
        if not all([conversation_id, partner_id]) or new_satisfaction is None:
            print(f"[satisfaction_changed] Missing required fields: {params}")
            self._increment_invalid_counter()
            return
        
        self.metrics_service.handle_satisfaction_changed(partner_id, old_satisfaction, new_satisfaction)
        print(f"[satisfaction_changed] Processed: conversation_id={conversation_id}, rating: {old_satisfaction} -> {new_satisfaction}")
    
    def _handle_conversation_forwarded(self, params: dict):
        """Handle conversation_forwarded event."""
        conversation_id = params.get("conversation_id")
        partner_id = params.get("partner_id")
        
        if not conversation_id or not partner_id:
            print(f"[conversation_forwarded] Missing required fields: {params}")
            self._increment_invalid_counter()
            return
        
        self.metrics_service.handle_conversation_forwarded(partner_id)
        print(f"[conversation_forwarded] Processed: conversation_id={conversation_id}, partner_id={partner_id}")
    
    # A04a Event Handlers
    
    def _handle_customer_registered(self, params: dict):
        """Handle customer_registered event."""
        customer_id = params.get("customer_id")
        
        if not customer_id:
            print(f"[customer_registered] Missing customer_id: {params}")
            self._increment_invalid_counter()
            return
        
        self.metrics_service.increment_total_customers()
        print(f"[customer_registered] Processed: customer_id={customer_id}")
    
    def _increment_invalid_counter(self):
        """Increment invalid events counter."""
        self.invalid_events_counter += 1
        if self.invalid_events_counter > 100:
            print(f"[EventConsumerService] ALERT: Invalid events count exceeded 100: {self.invalid_events_counter}")
