# S08 Metrics Service - Telcenter Core

This service is the **S08. Metrics Service** for Telcenter Core system. It aggregates and provides real-time metrics for the Core Portal.

## Overview

S08 Metrics Service collects metrics from other services via RabbitMQ events and provides aggregated data through HTTP APIs. The service operates in two modes:
1. **Real-time metrics collection** via events (background processing)
2. **On-demand queries** via HTTP REST API

## Features

### Metrics Tracked
1. **Total Customers** - Count of registered customers
2. **Active Conversations** - Conversation statistics by status (texting, calling, forwarding)
3. **Customer Satisfaction** - Distribution of satisfaction ratings (1-5 stars)
4. **Overall Offload Rate** - Percentage of conversations handled by AI without human intervention
5. **Per-Partner Offload Rate** - Offload rates broken down by partner

### API Endpoints (H21)

#### Authentication
All endpoints require JWT authentication via `Authorization: Bearer <token>` header.

#### Endpoints
- `GET /api/v1/metrics/users/total` - Total registered customers
- `GET /api/v1/core/metrics/conversations/summary` - Conversation statistics
- `GET /api/v1/core/metrics/consultations/satisfaction` - Satisfaction distribution
- `GET /api/v1/core/metrics/consultations/offload-rate` - Overall offload rate
- `GET /api/v1/core/metrics/consultations/offload-rate-by-partner` - Per-partner offload rates

### Event Consumers (RabbitMQ)

**A03a - S01 Events** (`s01_events_queue`)
- `conversation_start` - New conversation started
- `conversation_status_update` - Conversation status changed
- `conversation_customer_satisfaction_changed` - Customer rated conversation
- `conversation_forwarded` - Conversation forwarded to human agent

**A04a - S04 Events** (`s04_events_queue`)
- `customer_registered` - New customer registered

### Method Callers (RabbitMQ)

**A03b - S01 Methods**
- `get_conversation_statistics` - Fetch conversation statistics
- `get_customer_satisfaction_distribution` - Fetch satisfaction distribution
- `get_offloaded_conversations_by_partner` - Fetch per-partner offload data

**A04b - S04 Methods**
- `get_customers_count` - Fetch total customer count

**A07 - S07 Methods**
- `get_partners` - Fetch partner list (for enriching responses with partner names)

### S14 Integration (RabbitMQ)

**A17a - Event Publisher** (`s08_events_queue`)
- Publishes metrics events to S14 Partner Metrics Service

**A17b - Method Responder** (`s14_s08_requests_queue`)
- `get_partner_conversation_statistics` - Return statistics for specific partner
- `get_partner_satisfaction_distribution` - Return satisfaction distribution for specific partner

## Installation

### Prerequisites
- Python 3.12+
- RabbitMQ server
- uv (Python package manager)

### Setup

1. Clone the repository
2. Install dependencies:
```bash
uv sync
```

3. Create `.env` file:
```bash
cp .env.example .env
```

4. Configure environment variables in `.env`:
```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5008
FLASK_DEBUG=false
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
IDENTITY_SERVICE_URL=http://localhost:5004
JWKS_TTL_IN_MINUTES=10
```

## Running the Service

```bash
uv run python -m app
```

The service will:
1. Initialize by fetching current metrics from S01, S04, S07
2. Start consuming events from S01 and S04
3. Start HTTP API server on configured port (default: 5008)
4. Start responding to S14 method calls
5. Periodically refresh partner cache (every 1 hour)

## Architecture

### Components

1. **MetricsService** - In-memory metrics storage with thread-safe operations
2. **EventConsumerService** - Consumes events from S01 and S04
3. **MethodCallerService** - Calls methods on S01, S04, S07 via RabbitMQ
4. **S14IntegrationService** - Publishes events to S14 and responds to S14 method calls
5. **HTTP Controllers** - Flask REST API endpoints (H21)
6. **JWTVerifier** - JWT authentication middleware using JWKS

## Documentation

For detailed specifications, see:
- [S08 Service Specification](docs/services/core/S08_Metrics_Service.md)
- [H21 HTTP API](docs/api_groups/H21.md)
- [A03a Events](docs/api_groups/A03a.md), [A03b Methods](docs/api_groups/A03b.md)
- [A04 API](docs/api_groups/A04.md)
- [A07 Methods](docs/api_groups/A07.md)
- [A17a Events](docs/api_groups/A17a.md), [A17b Methods](docs/api_groups/A17b.md)
- [JWT Verification](docs/auth/VERIFY.md)
