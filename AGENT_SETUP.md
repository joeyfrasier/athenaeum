# 🏛️ Athenaeum Agent Setup Guide

Complete guide for setting up and running Athenaeum, your production-ready AI agent powered by Claude.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Configuration](#configuration)
5. [Running the Agent](#running-the-agent)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)

---

## Prerequisites

Before you begin, ensure you have:

- ✅ **Database running** (see [DOCKER_SETUP.md](DOCKER_SETUP.md) or [TIGERDATA_SETUP.md](TIGERDATA_SETUP.md))
- ✅ **Slack app configured** (see [SLACK_SETUP.md](SLACK_SETUP.md))
- ✅ **Python 3.11+** installed
- ✅ **Anthropic API key** (get it from https://console.anthropic.com/)

---

## Quick Start

### 1. Get Your Anthropic API Key

1. Go to https://console.anthropic.com/
2. Sign up or log in to your account
3. Navigate to **API Keys** section
4. Click **Create Key**
5. Copy your API key (starts with `sk-ant-...`)

> **Important**: Your API key is sensitive! Never commit it to git.

### 2. Configure Environment

Copy the sample environment file and add your API key:

```bash
cp .env.sample .env
```

Edit `.env` and set your API key:

```bash
# AI/LLM Configuration
ANTHROPIC_API_KEY=sk-ant-your-actual-api-key-here

# Claude Configuration (defaults are fine for most use cases)
CLAUDE_MODEL=claude-3-5-sonnet-20241022
CLAUDE_MAX_TOKENS=4096
CLAUDE_TEMPERATURE=0.7
MAX_CONVERSATION_HISTORY=50
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Agent

```bash
python athenaeum.py
```

You should see:

```
🏛️ Athenaeum is ready! Listening for Slack messages...
```

---

## Detailed Setup

### Architecture Overview

Athenaeum integrates three main components:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Athenaeum Agent                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────┐      ┌─────────────┐      ┌─────────────────┐  │
│  │   Slack   │─────▶│   Worker    │─────▶│     Claude      │  │
│  │  Events   │      │    Pool     │      │  (Anthropic)    │  │
│  └───────────┘      └─────────────┘      └─────────────────┘  │
│       │                    │                       │            │
│       │                    │                       │            │
│       └────────────────────┼───────────────────────┘            │
│                            ▼                                    │
│                  ┌──────────────────┐                          │
│                  │   TimescaleDB    │                          │
│                  │  (Conversation   │                          │
│                  │     Memory)      │                          │
│                  └──────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Flow

1. **Slack Events** → Messages arrive via Socket Mode
2. **Event Queue** → Events stored in database with exactly-once semantics
3. **Worker Pool** → Bounded concurrency processing (configurable)
4. **Conversation Context** → Retrieves thread history from TimescaleDB
5. **Claude API** → Generates intelligent responses
6. **Response Posting** → Replies posted back to Slack

---

## Configuration

### Environment Variables

All configuration is managed via environment variables. Here's what each setting does:

#### Database Configuration

```bash
# PostgreSQL/TimescaleDB connection
DATABASE_URL=postgresql://tsdbadmin:password@localhost:5432/tsdb
```

#### Slack Configuration

```bash
# Socket Mode app token (starts with xapp-)
SLACK_APP_TOKEN=xapp-your-app-token-here

# Bot OAuth token (starts with xoxb-)
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
```

#### Claude Configuration

```bash
# Your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Claude model to use (recommended: claude-3-5-sonnet-20241022)
# Available models:
# - claude-3-5-sonnet-20241022 (recommended - best balance)
# - claude-3-opus-20240229 (most capable, slower, more expensive)
# - claude-3-haiku-20240307 (fastest, cheapest, less capable)
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Maximum tokens in response (1024-8192)
# Higher = longer responses, more cost
CLAUDE_MAX_TOKENS=4096

# Temperature for responses (0.0-1.0)
# Lower = more focused and deterministic
# Higher = more creative and varied
CLAUDE_TEMPERATURE=0.7

# Maximum conversation history messages to include
# Higher = more context, more tokens used
MAX_CONVERSATION_HISTORY=50
```

#### Worker Pool Configuration

```bash
# Number of concurrent workers
# Recommendation: 5-10 for most workloads
WORKER_POOL_SIZE=5

# Event visibility timeout (seconds)
# How long a worker can process an event before it's reclaimed
EVENT_VISIBILITY_TIMEOUT=300

# Maximum retry attempts for failed events
MAX_RETRY_COUNT=3
```

#### Agent Configuration

```bash
# Your company/organization name (used in prompts)
COMPANY_NAME=Your Company

# Domain areas your agent specializes in
DOMAIN_AREAS=Python,Databases,APIs

# Environment (development, staging, production)
ENVIRONMENT=development

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

---

## Running the Agent

### Development Mode

For development with auto-reload:

```bash
# Using watchdog
pip install watchdog
watchmedo auto-restart -d . -p '*.py' -- python athenaeum.py
```

### Production Mode

For production, use a process manager like **systemd** or **supervisord**.

#### Systemd Service

Create `/etc/systemd/system/athenaeum.service`:

```ini
[Unit]
Description=Athenaeum AI Agent
After=network.target postgresql.service

[Service]
Type=simple
User=athenaeum
WorkingDirectory=/opt/athenaeum
Environment=PATH=/opt/athenaeum/venv/bin
ExecStart=/opt/athenaeum/venv/bin/python athenaeum.py
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/athenaeum/logs

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable athenaeum
sudo systemctl start athenaeum
sudo systemctl status athenaeum
```

#### Supervisord

Create `/etc/supervisor/conf.d/athenaeum.conf`:

```ini
[program:athenaeum]
command=/opt/athenaeum/venv/bin/python athenaeum.py
directory=/opt/athenaeum
user=athenaeum
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/athenaeum/agent.log
environment=PATH="/opt/athenaeum/venv/bin"
```

Start:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start athenaeum
```

### Docker Deployment

If using Docker for the entire stack:

```bash
# Start database
docker-compose up -d timescaledb

# Run agent (in separate terminal or background)
python athenaeum.py
```

Or create a Dockerfile for the agent:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "athenaeum.py"]
```

---

## Testing

### Manual Testing

1. **Start the agent**:
   ```bash
   python athenaeum.py
   ```

2. **Send a test message** in Slack:
   - In a channel where the bot is a member: `@Athenaeum hello!`
   - In a DM: `hello!`

3. **Check logs** for processing:
   ```
   event_queued event_id=1 event_type=slack_app_mention
   processing_event event_id=1 event_type=slack_app_mention
   generating_response user_id=U123456
   response_generated input_tokens=150 output_tokens=75
   slack_response_posted event_id=1
   ```

### Automated Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio

# Run all tests
pytest

# Run with coverage
pytest --cov=agent --cov=slack --cov-report=html

# Run specific test
pytest tests/test_agent_core.py -v
```

### Integration Testing

Test the full flow with a real Slack message:

```python
# scripts/test_integration.py
import os
from agent.config import get_config
from agent.llm_client import ClaudeClient
from agent.core import AthenaeumAgent
from database.connection import DatabaseConnection
from slack.client import SlackClient

config = get_config()
db = DatabaseConnection(config.database_url)
slack = SlackClient(config.slack_bot_token)
claude = ClaudeClient(config.anthropic_api_key)

with db.session() as session:
    agent = AthenaeumAgent(
        claude_client=claude,
        slack_client=slack,
        db_session=session,
        bot_user_id="U123456",  # Your bot's user ID
    )

    # Simulate an event
    from database.models import Event
    event = Event(
        event_type="slack_message",
        payload={
            "channel": "C123456",
            "user": "U789012",
            "text": "What is TimescaleDB?",
            "ts": "1234567890.123456",
        },
    )

    result = agent.process_event(event)
    print(f"Result: {result}")
```

---

## Troubleshooting

### Common Issues

#### 1. **"ANTHROPIC_API_KEY is required"**

**Problem**: API key not set in environment

**Solution**:
```bash
# Check if .env file exists
ls -la .env

# Verify API key is set
grep ANTHROPIC_API_KEY .env

# If missing, add it
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env
```

#### 2. **"Rate limited" errors**

**Problem**: Too many API requests

**Solution**:
- Reduce `WORKER_POOL_SIZE` to limit concurrency
- Increase retry delays in `agent/llm_client.py`
- Consider upgrading your Anthropic plan

#### 3. **"Database connection failed"**

**Problem**: TimescaleDB not accessible

**Solution**:
```bash
# Check database is running
docker ps | grep timescale

# Test connection
psql $DATABASE_URL -c "SELECT version();"

# Check logs
docker logs athenaeum-timescaledb-1
```

#### 4. **"Slack socket disconnected"**

**Problem**: Socket Mode connection lost

**Solution**:
- Check your `SLACK_APP_TOKEN` is correct
- Verify Socket Mode is enabled in Slack app settings
- Check firewall/proxy settings
- The handler will auto-reconnect after brief outage

#### 5. **"No response from bot"**

**Problem**: Event not being processed

**Solution**:
```bash
# Check worker pool is running
# Look for: "starting_worker_pool workers=5"

# Check event queue
psql $DATABASE_URL -c "SELECT * FROM events WHERE status='pending' LIMIT 10;"

# Check bot has correct scopes
# Must have: app_mentions:read, chat:write, channels:history
```

### Debug Mode

Enable debug logging for more details:

```bash
# In .env
LOG_LEVEL=DEBUG

# Run agent
python athenaeum.py
```

This will show:
- Detailed event processing
- Full API requests/responses
- Database queries
- Token usage

### Health Checks

Check system health:

```bash
# Database health
psql $DATABASE_URL -c "SELECT COUNT(*) FROM events;"

# API connectivity
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","messages":[{"role":"user","content":"test"}],"max_tokens":10}'

# Slack connectivity
curl https://slack.com/api/auth.test \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN"
```

---

## Advanced Configuration

### Custom Prompts

Athenaeum uses Jinja2 templates for prompts. Customize them in `prompts/`:

**`prompts/system.jinja2`** - System prompt with agent personality:
```jinja2
You are Athenaeum, an AI assistant inspired by Minerva's temple of wisdom.

**Current Context:**
- User: {{ user_name }} ({{ user_email }})
- Channel: #{{ channel_name }}
- Date: {{ current_date }}

{% if is_thread %}
**Thread Context:**
{{ thread_context }}
{% endif %}

**Your Role:**
Provide helpful, accurate, and thoughtful responses about {{ domain_areas }}.
```

**`prompts/conversation.jinja2`** - Conversation history formatting:
```jinja2
{% for message in conversation_history %}
**{{ message.user_name }}**: {{ message.text }}
{% endfor %}
```

### Multiple Models

Use different models for different event types:

```python
# In athenaeum.py, modify process_event_with_agent:

def process_event_with_agent(event):
    # Use faster model for simple queries
    model = "claude-3-haiku-20240307" if len(event.payload.get("text", "")) < 50 else config.claude_model

    claude_client = ClaudeClient(
        api_key=config.anthropic_api_key,
        model=model,
    )

    with db_connection.session() as session:
        agent = AthenaeumAgent(
            claude_client=claude_client,
            slack_client=slack_client,
            db_session=session,
        )
        return agent.process_event(event)
```

### Streaming Responses

For real-time streaming to Slack (updates message as it generates):

```python
# In agent/core.py, use process_with_streaming:

def handle_streaming_event(event):
    agent = AthenaeumAgent(...)

    chunks = []
    def collect_chunk(chunk):
        chunks.append(chunk)
        # Update Slack message in real-time
        # (requires initial message post + updates)

    agent.process_with_streaming(event, callback=collect_chunk)
```

### Cost Tracking

Track API costs:

```python
# In athenaeum.py, add cost tracking:

COSTS = {
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},  # per 1K tokens
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
}

def calculate_cost(model, usage):
    costs = COSTS.get(model, {"input": 0, "output": 0})
    input_cost = (usage["input_tokens"] / 1000) * costs["input"]
    output_cost = (usage["output_tokens"] / 1000) * costs["output"]
    return input_cost + output_cost

# After processing:
cost = calculate_cost(config.claude_model, response.get("usage", {}))
logger.info("api_cost", cost_usd=cost, **response.get("usage", {}))
```

---

## Performance Tuning

### Optimize Worker Pool

```bash
# For high throughput (many messages):
WORKER_POOL_SIZE=10
CLAUDE_MAX_TOKENS=2048  # Shorter responses = faster

# For long conversations:
WORKER_POOL_SIZE=3
MAX_CONVERSATION_HISTORY=100  # More context
```

### Database Performance

```sql
-- Add indexes for faster queries
CREATE INDEX idx_slack_messages_channel_ts
  ON slack_messages(channel_id, created_at DESC);

CREATE INDEX idx_events_status_created
  ON events(status, created_at)
  WHERE status = 'pending';

-- Enable compression on older messages
SELECT add_compression_policy('slack_messages', INTERVAL '7 days');
```

### Connection Pooling

```python
# In athenaeum.py, tune pool sizes:

db_connection = DatabaseConnection(
    database_url=config.database_url,
    pool_size=20,        # Max connections
    max_overflow=10,     # Additional overflow
)
```

---

## Monitoring

### Metrics to Track

1. **Event Processing Rate**
   - Events/second
   - Queue depth
   - Processing latency

2. **API Usage**
   - Requests/minute
   - Token usage
   - Cost per message

3. **Error Rates**
   - Failed events
   - API errors
   - Retry count

### Structured Logging

All logs are JSON-formatted for easy parsing:

```json
{
  "event": "response_generated",
  "timestamp": "2024-01-15T10:30:00Z",
  "user_id": "U123456",
  "input_tokens": 250,
  "output_tokens": 150,
  "level": "info"
}
```

Parse with tools like:
- **jq**: `tail -f logs/athenaeum.log | jq .`
- **Grafana Loki**: For log aggregation
- **Datadog**: For full observability

---

## Security Best Practices

1. **Never commit secrets** to version control
   ```bash
   # Ensure .env is in .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment-specific configs**
   - `.env.development` (local dev)
   - `.env.production` (production)

3. **Rotate API keys regularly**
   - Set reminders every 90 days
   - Use Anthropic Console to rotate

4. **Limit bot permissions**
   - Only grant required Slack scopes
   - Use least-privilege principle

5. **Monitor API usage**
   - Set up Anthropic usage alerts
   - Track daily/weekly costs

---

## Next Steps

Now that your agent is running:

1. ✅ Test with various Slack messages
2. 📊 Set up monitoring and alerts
3. 🔧 Customize prompts for your use case
4. 🚀 Move to **Phase 4: MCP Servers** (see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md))

---

## Support

- **Documentation**: All markdown files in this repository
- **Issues**: Check [TESTING_STRATEGY.md](TESTING_STRATEGY.md) for debugging
- **Architecture**: See [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md)

---

**🏛️ Welcome to Athenaeum - Where Knowledge Meets Intelligence!**
