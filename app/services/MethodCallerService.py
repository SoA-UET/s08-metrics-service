"""
Method callers for A03b, A04b, A07 - call methods on S01, S04, S07 via RabbitMQ.
"""
from ..services.MessageQueueService import MessageQueueService
import uuid
import threading
import time
from typing import Dict, Any, Optional


class MethodCallerService:
    """
    Service to call methods on other services via RabbitMQ.
    Implements request-response pattern.
    """
    
    def __init__(self, mq_service: MessageQueueService):
        self.mq_service = mq_service
        self.mq_lock = threading.Lock()
        
        # Queue names for S01
        self.s08_s01_requests_queue = "s08_s01_requests_queue"
        self.s08_s01_responses_queue = "s08_s01_responses_queue"
        
        # Queue names for S04
        self.s08_s04_requests_queue = "s08_s04_requests_queue"
        self.s08_s04_responses_queue = "s08_s04_responses_queue"
        
        # Queue names for S07
        self.s08_s07_requests_queue = "s08_s07_requests_queue"
        self.s08_s07_responses_queue = "s08_s07_responses_queue"
        
        # Response tracking
        self.pending_responses: Dict[str, Any] = {}
        self.response_lock = threading.Lock()
        
        # Start response consumers
        self._start_response_consumers()
    
    def _start_response_consumers(self):
        """Start background threads to consume responses."""
        # S01 response consumer
        s01_thread = threading.Thread(
            target=self._consume_responses,
            args=(self.s08_s01_responses_queue,),
            daemon=True,
            name="S01-ResponseConsumer"
        )
        s01_thread.start()
        
        # S04 response consumer
        s04_thread = threading.Thread(
            target=self._consume_responses,
            args=(self.s08_s04_responses_queue,),
            daemon=True,
            name="S04-ResponseConsumer"
        )
        s04_thread.start()
        
        # S07 response consumer
        s07_thread = threading.Thread(
            target=self._consume_responses,
            args=(self.s08_s07_responses_queue,),
            daemon=True,
            name="S07-ResponseConsumer"
        )
        s07_thread.start()
        
        print("[MethodCallerService] Started response consumers")
    
    def _consume_responses(self, queue_name: str):
        """Consume responses from a queue."""
        with self.mq_lock:
            mq = self.mq_service.clone()
        
        mq.declare_queue(queue_name)
        mq.register_callback(queue_name, self._handle_response)
        mq.start_consuming()
    
    def _handle_response(self, message: dict):
        """Handle incoming response."""
        request_id = message.get("id")
        if not request_id:
            print(f"[MethodCallerService] Response missing id: {message}")
            return
        
        with self.response_lock:
            if request_id in self.pending_responses:
                self.pending_responses[request_id] = message
                print(f"[MethodCallerService] Received response for request_id={request_id}")
    
    def _call_method(self, queue_name: str, method: str, params: dict = None, timeout: int = 30) -> Dict:
        """
        Generic method to call a remote method and wait for response.
        
        Args:
            queue_name: Request queue name
            method: Method name to call
            params: Method parameters (optional)
            timeout: Timeout in seconds
            
        Returns:
            Response dict
            
        Raises:
            TimeoutError: If response not received within timeout
            Exception: If method call fails
        """
        request_id = str(uuid.uuid4())
        
        request = {
            "method": method,
            "id": request_id
        }
        
        if params is not None:
            request["params"] = params
        
        # Register pending response
        with self.response_lock:
            self.pending_responses[request_id] = None
        
        # Publish request
        with self.mq_lock:
            mq = self.mq_service.clone()
        mq.declare_queue(queue_name)
        mq.publish_message(queue_name, request)
        
        print(f"[MethodCallerService] Sent request: method={method}, request_id={request_id}")
        
        # Wait for response
        start_time = time.time()
        while True:
            with self.response_lock:
                response = self.pending_responses.get(request_id)
                if response is not None:
                    del self.pending_responses[request_id]
                    break
            
            if time.time() - start_time > timeout:
                with self.response_lock:
                    if request_id in self.pending_responses:
                        del self.pending_responses[request_id]
                raise TimeoutError(f"Request timeout after {timeout}s: method={method}, request_id={request_id}")
            
            time.sleep(0.1)
        
        return response
    
    # A03b Methods - S01 Consultation Service
    
    def get_conversation_statistics(self, retry_count: int = 3) -> Dict:
        """
        Call A03b method: get_conversation_statistics
        Returns conversation statistics from S01.
        """
        for attempt in range(retry_count):
            try:
                response = self._call_method(
                    self.s08_s01_requests_queue,
                    "get_conversation_statistics",
                    {}
                )
                
                result = response.get("result", {})
                status = result.get("status")
                content = result.get("content")
                
                if status == "success":
                    return content
                elif status == "error":
                    if content == "DB_CONNECTION_ERROR":
                        raise Exception("S01 database connection error")
                    else:
                        raise Exception(f"S01 error: {content}")
                else:
                    raise Exception(f"Unknown response status: {status}")
                    
            except TimeoutError:
                if attempt < retry_count - 1:
                    print(f"[get_conversation_statistics] Timeout, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception("S01 unavailable: timeout after retries")
            except Exception as e:
                if attempt < retry_count - 1 and "timeout" in str(e).lower():
                    print(f"[get_conversation_statistics] Error, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)
                else:
                    raise
    
    def get_customer_satisfaction_distribution(self, retry_count: int = 3) -> Dict:
        """
        Call A03b method: get_customer_satisfaction_distribution
        Returns satisfaction distribution from S01.
        """
        for attempt in range(retry_count):
            try:
                response = self._call_method(
                    self.s08_s01_requests_queue,
                    "get_customer_satisfaction_distribution",
                    {}
                )
                
                result = response.get("result", {})
                status = result.get("status")
                content = result.get("content")
                
                if status == "success":
                    return content
                elif status == "error":
                    if content == "NO_DATA_FOUND":
                        # Return empty distribution
                        return {
                            "satisfaction_1": 0,
                            "satisfaction_2": 0,
                            "satisfaction_3": 0,
                            "satisfaction_4": 0,
                            "satisfaction_5": 0
                        }
                    else:
                        raise Exception(f"S01 error: {content}")
                else:
                    raise Exception(f"Unknown response status: {status}")
                    
            except TimeoutError:
                if attempt < retry_count - 1:
                    print(f"[get_customer_satisfaction_distribution] Timeout, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("S01 unavailable: timeout after retries")
            except Exception as e:
                if attempt < retry_count - 1 and "timeout" in str(e).lower():
                    print(f"[get_customer_satisfaction_distribution] Error, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)
                else:
                    raise
    
    def get_offloaded_conversations_by_partner(self, retry_count: int = 3) -> Dict:
        """
        Call A03b method: get_offloaded_conversations_by_partner
        Returns per-partner offload data from S01.
        """
        for attempt in range(retry_count):
            try:
                response = self._call_method(
                    self.s08_s01_requests_queue,
                    "get_offloaded_conversations_by_partner",
                    {}
                )
                
                result = response.get("result", {})
                status = result.get("status")
                content = result.get("content")
                
                if status == "success":
                    return content
                elif status == "error":
                    if content == "NO_DATA_FOUND":
                        return {}  # Empty dict for no data
                    else:
                        raise Exception(f"S01 error: {content}")
                else:
                    raise Exception(f"Unknown response status: {status}")
                    
            except TimeoutError:
                if attempt < retry_count - 1:
                    print(f"[get_offloaded_conversations_by_partner] Timeout, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("S01 unavailable: timeout after retries")
            except Exception as e:
                if attempt < retry_count - 1 and "timeout" in str(e).lower():
                    print(f"[get_offloaded_conversations_by_partner] Error, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)
                else:
                    raise
    
    # A04b Methods - S04 Customer Identity Service
    
    def get_customers_count(self, retry_count: int = 3) -> int:
        """
        Call A04b method: get_customers_count
        Returns total customer count from S04.
        """
        for attempt in range(retry_count):
            try:
                response = self._call_method(
                    self.s08_s04_requests_queue,
                    "get_customers_count",
                    {}
                )
                
                result = response.get("result", {})
                status = result.get("status")
                content = result.get("content")
                
                if status == "success":
                    return content
                elif status == "error":
                    raise Exception(f"S04 error: {content}")
                else:
                    raise Exception(f"Unknown response status: {status}")
                    
            except TimeoutError:
                if attempt < retry_count - 1:
                    print(f"[get_customers_count] Timeout, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("S04 unavailable: timeout after retries")
            except Exception as e:
                if attempt < retry_count - 1 and "timeout" in str(e).lower():
                    print(f"[get_customers_count] Error, retrying... (attempt {attempt + 1}/{retry_count})")
                    time.sleep(2 ** attempt)
                else:
                    raise
    
    # A07 Methods - S07 Partner Management Service
    
    def get_partners(self) -> list:
        """
        Call A07 method: get_partners
        Returns list of partners from S07.
        """
        try:
            response = self._call_method(
                self.s08_s07_requests_queue,
                "get_partners",
                {}
            )
            
            result = response.get("result", {})
            status = result.get("status")
            content = result.get("content")
            
            if status == "success":
                return content
            elif status == "error":
                raise Exception(f"S07 error: {content}")
            else:
                raise Exception(f"Unknown response status: {status}")
                
        except Exception as e:
            print(f"[get_partners] Failed to fetch partners from S07: {e}")
            return []  # Return empty list on failure (graceful degradation)
