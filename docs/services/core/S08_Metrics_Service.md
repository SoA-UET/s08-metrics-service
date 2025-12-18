# Telcenter Core - **S08. Metrics Service**

Introducing the series of Telcenter Engineering.

Telcenter, on the surface, is a semi-automated telecom services call center -
it is a web app that offers telecommunication services consultation. People
are serviced by the AI Agent, and they will be forwarded to in-person
consultants if the AI detected down mood, rage, or that it could not answer
the question itself given a pre-fed ground truth database. Now, we are
designing this as microservices. Telcenter Core would act as the main backend
for the end-user interface, and it consists of multiple microservices.
Telcenter Partner is another system that is deployed separately on each of
the telecom partner's servers, and it is responsible for taking up forwarded
conversations and continuing them with the real persons in-charge. Together,
one Core and several Partner systems cooperate to deliver the best customer
experience, while lowering cost dramatically, with the help of automated AI
responses.

The general deployment and communication topology is like this:

    Core <---(Internet)---> (Partner_1, Partner_2..., Partner_N)

The users' inquiries and answers to those are primarily in Vietnamese.

Now, you are designing the **S08. Metrics Service** service, in Python.
This service is inside the **Telcenter Core** system.

Here are the peer services that the **S08. Metrics Service** service may interact with. We will come up
with the flow of this service itself later.

- **S01. Consultation Service**: The center of the Telcenter system, responsible for receiving and responding to customer messages. It manages the entire conversation lifecycle, orchestrates the flow between AI agents and consultant, and stores all interaction data including conversation history, content of messages, and customer reviews.
- **S04. Customer Identity Service**: This service is responsible for managing customer identities. It handles user registration, authentication, and profile management. 
- **S07. Partner Management Service**: This service if responsible for managing partner connection. It handles partner addition, update, deletion.
- **S14. Partner Metrics Service**: This service is responsible for tracking conversation volume, satisfaction rates, and partner offload rates.
## A Note on API Transport Layers

The APIs of the services (including this one
and the peers) might be based on HTTP and/or
RabbitMQ transport protocols. One service might
also exposes multiple APIs of different kinds.

HTTP is mostly used in APIs that are exposed
to the frontend web apps, though it occasionally
is used for internal communication between
microservices, too. HTTP APIs are somewhat
RESTful (it is CRUD, stateless, versioned,
and HATEOAS, but it need not follow
Code-on-Demand requirements.)

For APIs that are based on RabbitMQ transport,
each API usually demands two queues, the
requests queue and the responses queue. The
caller would send requests into the former queue
and expect the responses to come out from the
latter. Exceptions will be explicitly noted.
The default queue names will be specified for
each such API. The queue names should be configurable
via `.env`, too.

## Peer Service APIs

Note that the base URL to call the services
must be specified via `.env`. Construct
a `.env.example` file for that.

### **S01. Consultation Service**
[A03](../../api_groups/A03a.md) (Event)
[A03](../../api_groups/A03b.md) (Method)

### **S04. Customer Identity Service**

[A04](../../api_groups/A04.md)


### **S07. Partner Management Service**

[A07](../../api_groups/A07.md) (Method)

### **S14. Partner Metrics Service**

## The Flow

S08 Metrics Service aggregates and provides 5 main types of metrics for the Core Portal. The service operates in two modes: real-time metrics collection via events (background processing) and responding to HTTP requests (on-demand queries).

---

### Flow 1: Total Customers

**Background Processing (A04a Event Consumer):**

1. **Service Startup - Initial Data Load**:
   - Call A04b Method API to get current customer count.
   - Send RabbitMQ request via queue `s08_s04_requests_queue`
   - Method: `get_customer` (without date filters to get all-time total)
   - Wait for response from queue `s08_s04_responses_queue`
   - Initialize `total_customers` counter
   - If API call fails, retry up to 3 times before marking service as unhealthy

2. **Initialize Event Listener**: 
   - Spawn worker thread to consume events from S04 Customer Identity Service
   - RabbitMQ queue: `s04_events_queue` (A04a)

3. **Process `customer_registered` Event**:
   - Validate event payload: `customer_id`, `partner_id`
   - Increment `total_customers` counter in metrics database
   - Update partner-specific customer count if `partner_id` is present
   - If validation fails: log error, continue processing other events

**On-Demand Query (H21.1: `GET /api/v1/metrics/users/total`):**

1. **Authenticate Request**: Validate JWT token → return HTTP 401 if invalid
2. **Validate Query Parameters**: Parse `from_date`, `to_date` (optional) → ensure valid date range
3. **Query S04 via A04b Method API**:
   - Send RabbitMQ request via queue `s08_s04_requests_queue`
   - Method: `get_customer` with optional partner_id filter
   - Wait for response from queue `s08_s04_responses_queue`
4. **Handle Response**:
   - Success: Extract `total_customers` from response
   - Error "DB_TIMEOUT": return HTTP 500 with message "Database timeout while counting customers"
5. **Return Response**: HTTP 200 with `{"status": "success", "total_customers": N, "from_date": "...", "to_date": "..."}`

**Error Handling:**
- S04 unavailable: HTTP 500 "Customer Identity Service unavailable"
- DB_TIMEOUT: HTTP 500 "Database timeout while counting customers"

---

### Flow 2: Number of active conversations

**Background Processing (A03a Event Consumer):**

1. **Service Startup - Initial Data Load**:
   - Call A03b Method API to get current conversation statistics
   - Send RabbitMQ request via queue `s08_s01_requests_queue`
   - Method: `get_conversation_statistics`
   - Wait for response from queue `s08_s01_responses_queue`
   - Initialize counters:
     - `total_conversations`
     - `texting_conversations`
     - `calling_conversations`
     - `forwarding_conversations`
     - `ai_failed_conversations`
     - `offloaded_conversations`
   - If API call fails, retry up to 3 times before marking service as unhealthy

2. **Initialize Event Listener**:
   - Spawn worker thread to consume events from S01 Consultation Service
   - RabbitMQ queue: `s01_events_queue` (A03a)

3. **Process `conversation_start` Event**:
   - Validate payload: `conversation_id`, `customer_id`, `partner_id`, `created_at`
   - Increment `total_conversations` counter
   - Initialize conversation with default status "AI_AGENT_TEXTING"
   - Increment `texting_conversations` counter

3. **Process `conversation_status_update` Event**:
   - Validate payload: `conversation_id`, `old_status`, `new_status`, `partner_id`, `updated_at`
   - **Map status to category:**
     - `AI_AGENT_TEXTING` → texting_conversations
     - `AI_AGENT_CALLING` → calling_conversations
     - `FORWARDING` → forwarding_conversations
     - `HUMAN_AGENT_TEXTING` → texting_conversations
     - `HUMAN_AGENT_CALLING` → calling_conversations
   - **Update counters:**
     - Decrement (-1) counter for category of `old_status`
     - Increment (+1) counter for category of `new_status`
   - **Examples:**
     - `old_status=FORWARDING, new_status=HUMAN_AGENT_TEXTING`: `texting_conversations++, forwarding_conversations--`
     - `old_status=AI_AGENT_CALLING, new_status=FORWARDING`: `calling_conversations--, forwarding_conversations++`
     - `old_status=AI_AGENT_TEXTING, new_status=FORWARDING`: `texting_conversations--, forwarding_conversations++`
   - Update partner-specific conversation counts

**On-Demand Query (H21.2: `GET /api/v1/core/metrics/conversations/summary`):**

1. **Authenticate Request**: Validate JWT token
2. **Validate Query Parameters**: Parse `from_date`, `to_date` (optional)
3. **Query S01 via A03b Method API**:
   - Send RabbitMQ request via queue `s08_s01_requests_queue`
   - Method: `get_conversation_statistics`
   - Wait for response from queue `s08_s01_responses_queue`
4. **Handle Response**:
   - Success: Extract `total_conversations`, `texting_conversations`, `calling_conversations`
   - Error "DB_CONNECTION_ERROR": return HTTP 500 "Database connection error"
5. **Return Response**: HTTP 200 with conversation summary

**Error Handling:**
- S01 unavailable: HTTP 500 "Consultation Service unavailable"
- DB_CONNECTION_ERROR: HTTP 500 "Database connection error"

---

### Flow 3: Customer Satisfaction Rate

**Background Processing (A03a Event Consumer):**

1. **Service Startup - Initial Data Load**:
   - Call A03b Method API to get current satisfaction distribution
   - Send RabbitMQ request via queue `s08_s01_requests_queue`
   - Method: `get_customer_satisfaction_distribution`
   - Wait for response from queue `s08_s01_responses_queue`
   - Initialize satisfaction counters:
     - `satisfaction_1`, `satisfaction_2`, `satisfaction_3`, `satisfaction_4`, `satisfaction_5`
     - `total_ratings`
   - Calculate and store initial `average_rating`
   - If API call fails or returns "NO_DATA_FOUND", initialize all counters to 0

2. **Process `conversation_customer_satisfaction_changed` Event**:
   - Validate payload: `conversation_id`, `old_satisfaction`, `new_satisfaction`, `partner_id`, `updated_at`
   - **Update satisfaction distribution:**
     - If `old_satisfaction` exists (rating changed): Decrement `satisfaction_[old_value]` counter
     - Increment `satisfaction_[new_value]` counter (1-5 stars)
   - Update `total_ratings` count
   - **Recalculate average rating:**
     ```
     average_rating = (1×satisfaction_1 + 2×satisfaction_2 + 3×satisfaction_3 + 4×satisfaction_4 + 5×satisfaction_5) / total_ratings
     ```

**On-Demand Query (H21.3: `GET /api/v1/core/metrics/consultations/satisfaction`):**

1. **Authenticate Request**: Validate JWT token
2. **Validate Query Parameters**: Parse `from_date`, `to_date` (optional)
3. **Query S01 via A03b Method API**:
   - Method: `get_customer_satisfaction_distribution`
   - Handle "NO_DATA_FOUND": return HTTP 200 with empty distribution
4. **Calculate Satisfaction Rate**:
   ```
   satisfied_customers = satisfaction_3 + satisfaction_4 + satisfaction_5
   satisfaction_rate_percentage = (satisfied_customers / total_ratings) × 100
   ```
5. **Return Response**: HTTP 200 with:
   ```json
   {
     "status": "success",
     "total_conversations": N,
     "satisfaction_distribution": {...},
     "average_rating": X.XX,
     "from_date": "...",
     "to_date": "..."
   }
   ```

**Error Handling:**
- NO_DATA_FOUND: HTTP 200 with empty distribution, average_rating = 0
- S01 unavailable: HTTP 500 "Consultation Service unavailable"

---

### Flow 4: Overall Offload Rate

**Background Processing (A03a Event Consumer):**

1. **Service Startup - Initial Data Load**:
   - Call A03b Method API to get current conversation statistics
   - Method: `get_conversation_statistics` (same as Flow 2)
   - Extract: `total_conversations`, `ai_failed_conversations`, `offloaded_conversations`
   - Initialize offload metrics
   - Calculate initial `offload_rate_percentage`
   - Note: This uses the same initial data load as Flow 2, can be done in parallel

2. **Process `conversation_forwarded` Event**:
   - Validate payload: `conversation_id`, `partner_id`
   - Increment `ai_failed_conversations` counter (conversation forwarded to human)
   - Update global and partner-specific failure counts

3. **Calculate Offload Metrics**:
   ```
   offloaded_conversations = total_conversations - ai_failed_conversations
   offload_rate_percentage = (offloaded_conversations / total_conversations) × 100
   ```
   - Batch persist to database (every 10 seconds OR 100 events)

**On-Demand Query (H21.4: `GET /api/v1/core/metrics/consultations/offload-rate`):**

1. **Authenticate Request**: Validate JWT token
2. **Validate Query Parameters**: Parse `from_date`, `to_date` (optional)
3. **Query S01 via A03b Method API**:
   - Method: `get_conversation_statistics`
   - Extract: `total_conversations`, `ai_failed_conversations`, `offloaded_conversations`
4. **Calculate Offload Rate**:
   ```
   offload_rate_percentage = (offloaded_conversations / total_conversations) × 100
   ```
   - Handle edge case: if `total_conversations` = 0, return `offload_rate_percentage` = 0
5. **Return Response**: HTTP 200 with offload metrics

**Error Handling:**
- S01 unavailable: HTTP 500 "Consultation Service unavailable"

---

### Flow 5: Per-Partner Offload Rate

**Background Processing (A03a Event Consumer):**

1. **Service Startup - Initial Data Load**:
   - Call A03b Method API to get per-partner offload data
   - Send RabbitMQ request via queue `s08_s01_requests_queue`
   - Method: `get_offloaded_conversations_by_partner`
   - Wait for response from queue `s08_s01_responses_queue`
   - Initialize per-partner counters for each partner_id:
     - `partner_total_conversations[partner_id]`
     - `partner_offloaded_conversations[partner_id]`
   - Calculate `partner_ai_failed_conversations[partner_id]` = total - offloaded
   - Calculate initial `partner_offload_rate[partner_id]` for each partner
   - If API call fails or returns "NO_DATA_FOUND", initialize with empty partner list
   - **Call A07 Method API to initialize partner cache**:
     - Send RabbitMQ request via queue `s08_s07_requests_queue`
     - Method: `get_partners`
     - Wait for response from queue `s08_s07_responses_queue`
     - Cache partner_id → partner_name mapping (TTL: 1 hour)
     - If A07 fails: log warning, continue without partner names

2. **Track Partner-Specific Metrics**:
   - All events from A03a include `partner_id`
   - Maintain separate counters per partner:
     ```
     partner_total_conversations[partner_id]
     partner_ai_failed_conversations[partner_id]
     partner_offloaded_conversations[partner_id]
     ```

3. **Calculate Per-Partner Rates**:
   ```
   For each partner_id:
     partner_offload_rate[partner_id] = 
       (partner_offloaded_conversations[partner_id] / partner_total_conversations[partner_id]) × 100
   ```
   - Persist to database with partner_id indexing

**On-Demand Query (H21.5: `GET /api/v1/core/metrics/consultations/offload-rate-by-partner`):**

1. **Authenticate Request**: Validate JWT token
2. **Validate Query Parameters**:
   - Parse `from_date`, `to_date` (optional)
   - Parse `partner_id` (optional) - to filter specific partner
3. **Query S01 via A03b Method API**:
   - Method: `get_offloaded_conversations_by_partner`
   - Apply partner_id filter if specified
   - Handle "NO_DATA_FOUND": return HTTP 200 with empty partners array
3. **Query S07 Partner Management Service via A07 Method API**:
   - Send RabbitMQ request via queue `s08_s07_requests_queue`
   - Method: `get_partners`
   - Wait for response from queue `s08_s07_responses_queue`
   - Cache partner list (TTL: 1 hour) to avoid repeated calls
   - Map partner_id → partner_name from cached data
   - If S07 unavailable: log warning, use partner_id only (no partner_name)
   - If partner_id not found in cache: refresh cache and retry once
5. **Calculate Per-Partner Rates**:
   ```
   For each partner:
     offload_rate_percentage = (offloaded_conversations / total_conversations) × 100
   ```
6. **Calculate Overall Rate**:
   ```
   overall_offload_rate = SUM(all offloaded_conversations) / SUM(all total_conversations) × 100
   ```
7. **Return Response**: HTTP 200 with partners array and overall rate

**Error Handling:**
- NO_DATA_FOUND: HTTP 200 with empty partners array
- S01 unavailable: HTTP 500 "Consultation Service unavailable"
- S07 unavailable: Log warning, return response without partner_name

---

### Critical Error Handling (Applies to All Flows)

**RabbitMQ Connection Lost:**
- Log error with timestamp
- Attempt reconnection with exponential backoff (1s, 2s, 4s, 8s, max 60s)
- Buffer events in memory (max 10,000 events) during disconnection
- Process buffered events after reconnection
- Set health endpoint to unhealthy

**Database Connection Lost:**
- Attempt reconnection (3 attempts, 5s delay)
- Buffer writes in memory (max 5,000 operations)
- Return HTTP 503 if buffer full
- Set health endpoint to unhealthy


**Peer Service Unavailable (S01, S04, S07):**
- Return HTTP 500 with specific error message
- Implement circuit breaker pattern:
  - After 5 consecutive failures: open circuit for 30 seconds
  - After 30s: attempt half-open (single request)
  - Close circuit if request succeeds

**Invalid Event Payload:**
- Log validation error with full event details
- Continue processing other events (do not crash)
- Increment `invalid_events_counter` metric
- Alert if invalid_events_counter > 100/hour

---

## This Service's APIs

This service exposes the following APIs:

### Event Consumer APIs (Background Processing)

**A03a - Consultation Events**
[A03](../../api_groups/A03a.md) - Consumes real-time events from S01 Consultation Service (RabbitMQ)
  - Event Queue: `s01_events_queue`
  - Events consumed:
    - `conversation_start`
    - `conversation_status_update`
    - `conversation_customer_satisfaction_changed` 
    - `conversation_forwarded`

**A04a - Customer Identity Events**
[A04](../../api_groups/A04.md) - Consumes real-time events from S04 Customer Identity Service (RabbitMQ)
  - Event Queue: `s04_events_queue`
  - Events consumed:
    - `customer_registered`

### Method Call APIs (Request/Response via RabbitMQ)

**A03b - Consultation Methods**
[A03](../../api_groups/A03b.md) - Calls S01 to retrieve aggregated conversation statistics (RabbitMQ)
  - Request Queue: `s08_s01_requests_queue`
  - Response Queue: `s08_s01_responses_queue`
  - Methods used:
    - `get_conversation_statistics`
    - `get_customer_satisfaction_distribution`
    - `get_offloaded_conversations_by_partner`

**A04b - Customer Identity Methods**
[A04](../../api_groups/A04b.md) - Calls S04 to retrieve customer statistics (RabbitMQ)
  - Request Queue: `s08_s04_requests_queue`
  - Response Queue: `s08_s04_responses_queue`
  - Methods used:
    - `get_customer`

**A07 - Partner Management Methods**
[A07](../../api_groups/A07.md) - Calls S07 to retrieve partner information (RabbitMQ)
  - Request Queue: `s08_s07_requests_queue`
  - Response Queue: `s08_s07_responses_queue`
  - Methods used:
    - `get_partners`
  - Usage: Cache partner list for enriching metrics responses with partner names

### Event Publisher APIs (S08 → S14)

**A17a - Metrics Events Publisher**
[A17](../../api_groups/A17a.md) - Publishes real-time metrics events to S14 Partner Metrics Service (RabbitMQ)
  - Event Queue: `s08_events_queue`

### Method Responder APIs (S08 ← S14)

**A17b - Metrics Query Methods**
[A17](../../api_groups/A17b.md) - Responds to method calls from S14 Partner Metrics Service (RabbitMQ)
  - Request Queue: `s08_s14_requests_queue`
  - Response Queue: `s08_s14_responses_queue`

### HTTP API for Core Portal (H21)

[H21](../../api_groups/H21.md) - Exposes metrics data to Core Portal (HTTP/REST)
  - **H21.1**: `GET /api/v1/metrics/users/total`
  - **H21.2**: `GET /api/v1/core/metrics/conversations/summary`
  - **H21.3**: `GET /api/v1/core/metrics/consultations/satisfaction`
  - **H21.4**: `GET /api/v1/core/metrics/consultations/offload-rate`
  - **H21.5**: `GET /api/v1/core/metrics/consultations/offload-rate-by-partner`



## Technology

- Python
- Use `uv` as the virtual environment and package manager.
- Multithreaded logic should be used for performance, since this
    component relies a lot on other services, which means the API calls
    to those services take up very much time. So this service is I/O bound.
    Note that, using multithreading to emulate async operations is very
    important - but do NOT use `async` and `await` in Python - that would
    be a mess!

- The class `MessageQueueService` must be used for RabbitMQ communication (which internally
    use `pika`).

    The class is [located in this file](../../app/services/MessageQueueService.py).

    An example of using this class [is given here](../MessageQueueService-usage-example.py).

    Also, for multithreading, only use the scheme in that file.
    Any other use of multithreading, if necessary, must strictly
    look for hazards - use locks and other synchronization primitives
    where appropriate.

- If this service needs to expose HTTP API(s), use Flask.

- The program entry point is [in this file](../../app/__main__.py).
