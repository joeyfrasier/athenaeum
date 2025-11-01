# Production Agent System - Architecture Analysis

## Executive Summary

TigerData's production agent system (Eon) is a Slack-native AI assistant built on PostgreSQL/TimescaleDB as the foundation ("Agentic Postgres"). The system achieved 50% daily active usage within 6 weeks through enterprise-grade reliability, durable event processing, and contextual conversation memory.

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Slack Workspace                         │
└────────────────────────┬────────────────────────────────────────┘
                         │ Socket Mode / Events API
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Tiger Agents for Work                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Event Processor (Python)                                │  │
│  │  - Socket Mode Listener                                  │  │
│  │  - PostgreSQL Event Claiming                             │  │
│  │  - Fixed Worker Pool (Bounded Concurrency)               │  │
│  │  - Automatic Retry Logic                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL/TimescaleDB (Core Data Layer)           │
│  ┌──────────────────────┐  ┌──────────────────────────────┐    │
│  │  Event Queue         │  │  Conversational Memory       │    │
│  │  - Atomic claiming   │  │  - Hypertables (7-day chunks)│    │
│  │  - Exactly-once      │  │  - pgvector embeddings       │    │
│  │  - Retry visibility  │  │  - Full-text search          │    │
│  └──────────────────────┘  └──────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Documentation Search (Semantic)                         │  │
│  │  - PostgreSQL 14-18 docs                                 │  │
│  │  - TimescaleDB/Tiger Cloud docs                          │  │
│  │  - OpenAI embeddings + cosine similarity                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server Layer                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  Tiger Slack MCP │  │  Tiger Docs MCP  │  │ Tiger GH MCP │  │
│  │  (TypeScript)    │  │  (TypeScript)    │  │(TypeScript)  │  │
│  │  - Conversation  │  │  - Semantic      │  │- PR/Issue    │  │
│  │    retrieval     │  │    search        │  │  retrieval   │  │
│  │  - Channel/user  │  │  - Prompt        │  │- Code search │  │
│  │    metadata      │  │    templates     │  │              │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Agent (Pydantic-AI)                       │
│  - Claude (Anthropic) as primary LLM                            │
│  - Jinja2 prompt templates                                      │
│  - Multi-model support                                          │
│  - Tool orchestration                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components Deep Dive

### 1. Tiger Agents for Work (Agent Framework)

**Purpose**: Production-ready event processing framework with reliability guarantees

**Key Features**:
- **Exactly-Once Processing**: PostgreSQL-backed event claiming with atomic operations
- **Bounded Concurrency**: Fixed worker pools prevent resource exhaustion
- **Sub-Millisecond Latency**: Immediate event triggering (not polling-based)
- **Automatic Retry**: Configurable visibility thresholds for failed events
- **Horizontal Scalability**: Multiple instances coordinate through PostgreSQL

**Technology Stack**:
- Language: Python (99.3%)
- Agent Framework: Pydantic-AI
- Database: PostgreSQL connection pooling
- Observability: Logfire instrumentation

**Event Processing Flow**:
```
1. Slack Socket Mode → Event received
2. PostgreSQL atomic claim → Lock event for worker
3. Worker pool processing → Execute agent logic
4. Completion/Failure → Update event status
5. Auto-retry on failure → Visibility timeout mechanism
```

**Customization Levels**:
1. **Zero-Code**: Default prompts + environment variables
2. **Light**: Jinja2 template customization + MCP configuration
3. **Heavy**: Python subclassing of TigerAgent or EventProcessor

### 2. Tiger Slack (Conversational Memory)

**Purpose**: Real-time Slack data ingestion and contextual conversation storage

**Architecture**: Three-tier design

#### Tier 1: Data Ingestion (Python)
- WebSocket connection via Socket Mode
- Real-time event capture: messages, reactions, user changes, channel updates
- Scheduled synchronization jobs for users/channels
- Historical export processing capability

#### Tier 2: Storage (TimescaleDB)
- **Time-series optimizations**:
  - 7-day chunk partitioning
  - Automatic compression after 45 days (5-10x space savings)
  - Hypertable-based message storage
- **Search capabilities**:
  - Full-text search across message content
  - Bloom filter and minmax sparse indexes
  - Channel-based table segmentation

#### Tier 3: API Layer (TypeScript MCP)
- **Tools exposed**:
  - `list_channels`: Channel browsing with intelligent filtering
  - `list_users`: User metadata retrieval
  - `get_conversation`: Thread-aware conversation retrieval
  - `search_messages`: Full-text search with context
- **Protocol**: Model Context Protocol (HTTP + stdio)
- **Integration**: Claude, other LLM clients

**Deployment Strategy**:
1. Initialize schema and sync users/channels
2. Deploy ingest service for real-time accumulation
3. Import historical exports to eliminate gaps

### 3. Tiger Docs MCP Server (Knowledge Base)

**Purpose**: Semantic search over PostgreSQL, TimescaleDB, and Tiger Cloud documentation

**Core Technologies**:
- Language: TypeScript/Node.js + Python ingestion scripts
- Database: TimescaleDB with pgvector extension
- Embedding Model: OpenAI embeddings
- Search: Vector similarity with cosine distance

**API Tools**:

1. **semantic_search_postgres_docs**
   - Input: `prompt`, `version` (14-18), `limit`
   - Output: Ranked results with content + metadata + distance scores
   - Use case: PostgreSQL documentation queries

2. **semantic_search_tiger_docs**
   - Input: `prompt`, `limit`
   - Output: TimescaleDB/Tiger Cloud documentation results
   - Use case: Time-series and cloud-specific queries

3. **get_prompt_template**
   - Input: Template `name`
   - Output: Curated prompt for common tasks
   - Use case: Setup guidance, best practices

**Implementation Details**:
- Vector embeddings pre-computed and stored in database
- Lower distance score = higher relevance
- Public endpoint available: `https://mcp.tigerdata.com/docs`

### 4. Tiger GitHub MCP Server (Code Context)

**Purpose**: Focused GitHub API wrapper for LLM tool use

**Key Features**:
- TypeScript wrapper around GitHub REST API
- MCP-compliant tool interface
- Scoped to specific operations: PR retrieval, issue management, code search

**Authentication**:
- GitHub token with scopes: `repo`, `read:org`, `read:user`, `user:email`
- Token-based authentication for API calls

**Tools Provided** (inferred from typical GitHub MCP servers):
- PR retrieval and diffing
- Issue search and retrieval
- Code search across repositories
- Comment posting capabilities

**Integration**:
- STDIO transport for local execution
- Environment-based token configuration
- VS Code debugging support with source maps

## Key Design Decisions

### 1. PostgreSQL as Foundation ("Agentic Postgres")

**Rationale**:
- Single source of truth for all data
- ACID guarantees for event processing
- Native time-series optimizations (TimescaleDB)
- Vector similarity search (pgvector)
- Full-text search capabilities

**Benefits**:
- Reduced infrastructure complexity
- Consistent data model
- Transactional event handling
- Built-in scalability features

### 2. Model Context Protocol (MCP) for Tool Integration

**Rationale**:
- Standardized protocol for LLM-tool communication
- Modular, composable architecture
- Language-agnostic interface
- Growing ecosystem

**Benefits**:
- Easy to add/remove tools
- Reusable across different agents
- Community-contributed servers
- Protocol-level observability

### 3. Exactly-Once Event Processing

**Challenge**: Slack events can duplicate under network conditions

**Solution**: PostgreSQL-backed event claiming
```sql
-- Pseudocode for event claiming
BEGIN;
SELECT * FROM events
WHERE status = 'pending'
  AND (visibility_timeout IS NULL OR visibility_timeout < NOW())
LIMIT 1
FOR UPDATE SKIP LOCKED;

UPDATE events SET status = 'processing', claimed_by = worker_id;
COMMIT;
```

**Result**: Zero duplicate responses, reliable under high load

### 4. Bounded Concurrency with Fixed Worker Pools

**Challenge**: Unbounded concurrency leads to resource exhaustion

**Solution**: Fixed worker pool size
- Predictable resource consumption
- Graceful degradation under load
- Horizontal scaling through multiple instances

### 5. Conversational Memory in TimescaleDB

**Challenge**: LLMs need conversation context, but it grows unbounded

**Solution**: Time-series optimizations
- Automatic chunk compression (5-10x savings)
- Intelligent retention policies
- Fast recent-data queries
- Full-text search for semantic retrieval

## Observability and Monitoring

**Logfire Integration**:
- Distributed tracing across all components
- Event flow visibility
- Worker activity monitoring
- Database operation tracing
- AI-powered log analysis via MCP

**Key Metrics** (inferred):
- Event processing latency
- Queue depth
- Worker utilization
- LLM API latency
- Error rates by component

## Scalability Characteristics

**Horizontal Scaling**:
- Multiple agent instances coordinate via PostgreSQL
- Work distribution through event claiming
- No shared state between workers

**Database Scaling**:
- TimescaleDB native scaling features
- Chunk-based partitioning
- Compression for historical data
- Read replicas for query scaling

**Performance**:
- Sub-millisecond event processing
- Immediate event triggering (no polling)
- Connection pooling for database efficiency

## Security Considerations

**Secrets Management**:
- Environment-based configuration
- No secrets in code or version control
- Token-based authentication for all services

**Access Control**:
- Slack OAuth scopes: `connections:write`, `app_mentions:read`, `chat:write`
- GitHub token scopes: `repo`, `read:org`, `read:user`, `user:email`
- Database connection credentials

**Data Privacy**:
- All conversation data stored in company-controlled database
- No third-party conversation storage
- Audit trail through database logs

## Technology Stack Summary

| Component | Language | Database | Protocol | Deployment |
|-----------|----------|----------|----------|------------|
| Agent Framework | Python | PostgreSQL | WebSocket | Docker |
| Slack Ingestion | Python | TimescaleDB | WebSocket | Docker Compose |
| Slack MCP | TypeScript | - | HTTP/STDIO | Docker/npm |
| Docs MCP | TypeScript | TimescaleDB+pgvector | HTTP/STDIO | Docker/npm |
| GitHub MCP | TypeScript | - | STDIO | npm |

## Integration Points

1. **Slack ↔ Agent Framework**: Socket Mode (WebSocket)
2. **Agent ↔ PostgreSQL**: Connection pooling, event claiming
3. **Agent ↔ MCP Servers**: Model Context Protocol (HTTP/STDIO)
4. **Agent ↔ LLM**: Pydantic-AI (supports multiple providers)
5. **Ingestion ↔ Database**: Direct PostgreSQL writes
6. **MCP ↔ Database**: SQL queries for data retrieval

## Production Deployment Considerations

**Infrastructure Requirements**:
- PostgreSQL/TimescaleDB instance (recommended: Cloud-hosted)
- Container orchestration (Docker, Kubernetes)
- Environment variable management (secrets manager)
- Observability stack (Logfire or equivalent)

**Operational Considerations**:
- Database migration strategy
- Schema evolution handling
- Event replay capabilities
- Monitoring and alerting
- Cost management (LLM API usage)

## Lessons Learned (from Blog)

1. **Conversation memory is critical**: Context-aware responses require full conversation history
2. **Reliability matters more than features**: Users trust agents that never duplicate or lose messages
3. **PostgreSQL is sufficient**: No need for specialized message queues or vector databases
4. **MCP enables modularity**: Easy to add/remove capabilities without core changes
5. **Observability is essential**: Distributed tracing reveals bottlenecks and errors

## Conclusion

TigerData's production agent system demonstrates that enterprise-grade AI agents can be built on battle-tested open-source technologies. The key innovations are:

1. PostgreSQL as the unified data foundation
2. Exactly-once event processing semantics
3. Modular MCP-based tool architecture
4. Time-series optimized conversation storage
5. Production-grade observability

This architecture is production-proven, horizontally scalable, and fully open-sourced for adoption.
