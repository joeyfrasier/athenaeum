# Athenaeum - Slack Integration Setup

> Connect Athenaeum to your Slack workspace for real-time AI assistance

## Overview

This guide shows how to integrate Athenaeum with Slack, enabling:

✅ **Real-time message ingestion** - Socket Mode WebSocket connection
✅ **App mentions** - Respond to @mentions automatically
✅ **Conversation memory** - Store all messages in TimescaleDB
✅ **Historical import** - Import past conversations
✅ **User/channel sync** - Keep metadata up-to-date
✅ **Thread support** - Maintain conversation context

## Quick Start (5 Minutes)

### Prerequisites

- Slack workspace with admin access
- Athenaeum database running (see [DOCKER_SETUP.md](DOCKER_SETUP.md))
- Python environment with dependencies installed

### Step 1: Create Slack App

1. **Go to** [api.slack.com/apps](https://api.slack.com/apps)

2. **Click "Create New App"** → **"From a manifest"**

3. **Select your workspace**

4. **Paste the manifest** from `slack-app-manifest.json`:

```bash
cat slack-app-manifest.json
```

5. **Review permissions** and click **"Create"**

### Step 2: Enable Socket Mode

1. Go to **Settings → Socket Mode**
2. Click **"Enable Socket Mode"**
3. Generate an app-level token:
   - Token Name: `athenaeum-socket`
   - Scope: `connections:write`
4. **Copy the token** (starts with `xapp-`)

### Step 3: Install to Workspace

1. Go to **Settings → Install App**
2. Click **"Install to Workspace"**
3. **Review permissions** and click **"Allow"**
4. **Copy the Bot User OAuth Token** (starts with `xoxb-`)

### Step 4: Configure Environment

```bash
# Edit .env file
nano .env
```

Add your tokens:

```bash
# Slack Configuration
SLACK_APP_TOKEN=xapp-1-A123...  # From Step 2
SLACK_BOT_TOKEN=xoxb-123...      # From Step 3
```

### Step 5: Sync Metadata

```bash
# Sync users and channels
python scripts/sync_slack_metadata.py
```

**Output**:
```
INFO syncing_users_started
INFO users_fetched_from_slack count=42
INFO users_sync_completed total=42 ingested=42
INFO syncing_channels_started
INFO channels_fetched_from_slack count=15
INFO channels_sync_completed total=15 ingested=15
✅ Slack metadata sync completed
```

### Step 6: Start Slack Service

```python
# test_slack.py
import os
from dotenv import load_dotenv
from database import init_db
from slack.service import SlackService

load_dotenv()

# Initialize database
db = init_db()

# Initialize Slack service
service = SlackService(
    app_token=os.getenv("SLACK_APP_TOKEN"),
    bot_token=os.getenv("SLACK_BOT_TOKEN"),
    db_connection=db,
)

# Start service
service.start()

print("✅ Slack service started!")
print("💬 Try mentioning @Athenaeum in Slack")

# Run until interrupted
service.run_forever()
```

Run it:

```bash
python test_slack.py
```

### Step 7: Test in Slack

1. **Open Slack** and go to any channel where the bot is present
2. **Send a message**: `@Athenaeum hello!`
3. **Check logs** - you should see the event being processed

**Expected output**:
```
INFO slack_event_received event_type=app_mention
INFO handling_app_mention channel=C123456 ts=1234567890.123456
INFO slack_message_ingested channel=C123456 ts=1234567890.123456
✅ Event queued for agent processing
```

That's it! Athenaeum is now connected to Slack! 🎉

---

## Detailed Setup Guide

### Slack App Manifest Explanation

The `slack-app-manifest.json` configures:

**Display Information**:
- Name: "Athenaeum"
- Description and branding
- Background color

**Features**:
- **Bot User**: Always-online presence
- **App Home**: Home tab and DM support
- **Socket Mode**: Real-time WebSocket connection

**Permissions (OAuth Scopes)**:
```
app_mentions:read      - Receive @mentions
channels:history       - Read public channel messages
channels:read          - List public channels
chat:write            - Post messages
groups:history        - Read private channel messages
groups:read           - List private channels
im:history            - Read DMs
im:read, im:write     - Access DMs
mpim:history, mpim:read - Read group DMs
reactions:read        - Read reactions
users:read            - Read user info
users:read.email      - Read user emails
```

**Event Subscriptions**:
- `app_mention` - Bot is mentioned
- `message.*` - Messages in channels/DMs
- `reaction_added/removed` - Reactions to messages
- `user_change` - User profile updates
- `channel_*` - Channel lifecycle events

### Socket Mode vs Request URL

Athenaeum uses **Socket Mode** instead of Request URLs:

| Feature | Socket Mode | Request URL |
|---------|-------------|-------------|
| **Setup** | No public endpoint needed | Requires HTTPS endpoint |
| **Firewall** | Works behind firewall | Must be publicly accessible |
| **Development** | Perfect for local dev | Harder to test locally |
| **Latency** | Real-time WebSocket | HTTP requests |
| **Reliability** | Auto-reconnect | Manual retry logic |

Socket Mode is ideal for Athenaeum because:
- No need to expose a public endpoint
- Works in Docker/localhost
- Real-time event delivery
- Automatic reconnection

### Architecture

```
┌─────────────────────────────────────────┐
│         Slack Workspace                 │
│  - Users send messages                  │
│  - Bot receives @mentions               │
└──────────────┬──────────────────────────┘
               │ WebSocket (Socket Mode)
               ▼
┌─────────────────────────────────────────┐
│    Slack Service (Python)               │
│  ┌───────────────────────────────────┐  │
│  │  Socket Mode Handler              │  │
│  │  - Receives events                │  │
│  │  - Acknowledges immediately       │  │
│  └───────────────┬───────────────────┘  │
│                  ▼                       │
│  ┌───────────────────────────────────┐  │
│  │  Event Handler                    │  │
│  │  - Routes by event type           │  │
│  └───────────────┬───────────────────┘  │
│                  ▼                       │
│  ┌───────────────────────────────────┐  │
│  │  Slack Ingestor                   │  │
│  │  - Stores messages                │  │
│  │  - Queues for agent processing    │  │
│  └───────────────┬───────────────────┘  │
└──────────────────┼──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│    TimescaleDB                          │
│  - slack_messages (hypertable)          │
│  - slack_users                          │
│  - slack_channels                       │
│  - events (agent queue)                 │
└─────────────────────────────────────────┘
```

## Components

### 1. Slack Client (`slack/client.py`)

Wrapper around Slack WebClient with:
- **Rate limiting**: Respects Slack API rate limits
- **Retry logic**: Exponential backoff on errors
- **Pagination**: Automatically handles cursor-based pagination

**Usage**:

```python
from slack.client import SlackClient

client = SlackClient(bot_token="xoxb-...")

# Post a message
client.post_message(
    channel="C123456",
    text="Hello from Athenaeum!",
    thread_ts="1234567890.123456"  # Reply in thread
)

# Get user info
user = client.get_user_info("U123456")
print(user["real_name"])

# List all channels
channels = client.list_channels()
for channel in channels:
    print(f"{channel['name']}: {channel['id']}")

# Get conversation history
messages = client.get_conversation_history(
    channel_id="C123456",
    limit=100
)
```

### 2. Socket Mode Handler (`slack/socket_handler.py`)

Handles real-time Slack events:
- **WebSocket connection**: Persistent connection to Slack
- **Event routing**: Routes events to handlers
- **Auto-reconnect**: Automatic reconnection on disconnect
- **Async support**: Both sync and async versions

**Usage**:

```python
from slack.socket_handler import SocketModeHandler

def handle_event(event):
    event_type = event.get("type")
    print(f"Received event: {event_type}")

handler = SocketModeHandler(
    app_token="xapp-...",
    event_handler=handle_event,
    auto_reconnect=True
)

handler.start()
print(f"Connected: {handler.is_connected()}")

# Runs until stopped
handler.stop()
```

### 3. Slack Ingestor (`slack/ingest.py`)

Stores Slack data in TimescaleDB:
- **Messages**: Conversation history with threading
- **Users**: User metadata and profiles
- **Channels**: Channel information
- **Reactions**: Message reactions

**Usage**:

```python
from database import get_session
from slack.ingest import SlackIngestor

with get_session() as session:
    ingestor = SlackIngestor(session)

    # Ingest a user
    user_data = {"id": "U123", "name": "alice", ...}
    user = ingestor.ingest_user(user_data)

    # Ingest a message
    message_data = {
        "ts": "1234567890.123456",
        "user": "U123",
        "text": "Hello!",
        ...
    }
    message = ingestor.ingest_message(message_data, "C123456")

    # Bulk ingest
    messages = [...list of message_data...]
    count = ingestor.bulk_ingest_messages(messages, "C123456")
```

### 4. Slack Service (`slack/service.py`)

Main service that runs continuously:
- **Event processing**: Handles all Slack events
- **Graceful shutdown**: SIGINT/SIGTERM handling
- **Status monitoring**: Health checks and logging

**Usage**:

```python
from database import init_db
from slack.service import SlackService

db = init_db()

service = SlackService(
    app_token="xapp-...",
    bot_token="xoxb-...",
    db_connection=db
)

service.start()
service.run_forever()  # Blocks until shutdown
```

## Scripts

### Sync Metadata (`scripts/sync_slack_metadata.py`)

Syncs users and channels from Slack to database:

```bash
# Sync all users and channels
python scripts/sync_slack_metadata.py
```

**What it does**:
1. Fetches all workspace users via Slack API
2. Stores/updates in `slack_users` table
3. Fetches all accessible channels
4. Stores/updates in `slack_channels` table

**When to run**:
- Initial setup (once)
- When new users/channels are added
- Periodically (e.g., daily cron job)

### Import History (`scripts/import_slack_history.py`)

Imports historical messages from Slack:

```bash
# Import all channels
python scripts/import_slack_history.py

# Import specific channel
python scripts/import_slack_history.py --channel C123456

# Import with time range
python scripts/import_slack_history.py \
  --oldest 1672531200 \  # Unix timestamp
  --latest 1704067200

# Include archived channels
python scripts/import_slack_history.py --include-archived

# Adjust rate limiting
python scripts/import_slack_history.py --rate-limit-delay 2.0
```

**What it does**:
1. Fetches message history for channel(s)
2. Paginates through all messages
3. Stores in `slack_messages` table
4. Handles rate limiting

**When to run**:
- After initial setup (to get historical context)
- When joining new channels
- To backfill missing data

**Rate Limits**:
- Tier 3: 50+ requests/minute
- Script defaults to 1 request/second (safe)
- Adjust `--rate-limit-delay` if needed

## Database Schema

### slack_users

```sql
CREATE TABLE slack_users (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    real_name VARCHAR(100),
    email VARCHAR(255),
    is_bot BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    timezone VARCHAR(50),
    avatar_url TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
```

### slack_channels

```sql
CREATE TABLE slack_channels (
    channel_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_private BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    topic TEXT,
    purpose TEXT,
    member_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
```

### slack_messages (Hypertable)

```sql
CREATE TABLE slack_messages (
    channel_id VARCHAR(50) NOT NULL,
    ts VARCHAR(50) NOT NULL,
    user_id VARCHAR(50),
    text TEXT,
    thread_ts VARCHAR(50),  -- NULL if not a thread reply
    subtype VARCHAR(50),
    is_bot_message BOOLEAN,
    attachments JSONB,
    files JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL,  -- Partitioned by this
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (channel_id, ts)
);

-- Convert to hypertable (7-day chunks)
SELECT create_hypertable('slack_messages', 'created_at',
    chunk_time_interval => INTERVAL '7 days');
```

### slack_reactions

```sql
CREATE TABLE slack_reactions (
    id BIGSERIAL PRIMARY KEY,
    channel_id VARCHAR(50) NOT NULL,
    message_ts VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    reaction VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (channel_id, message_ts, user_id, reaction)
);
```

## Querying Conversation History

### Get recent messages

```sql
-- Messages from last 7 days
SELECT
    m.ts,
    u.name as user_name,
    c.name as channel_name,
    m.text,
    m.created_at
FROM slack_messages m
LEFT JOIN slack_users u ON m.user_id = u.user_id
LEFT JOIN slack_channels c ON m.channel_id = c.channel_id
WHERE m.created_at > NOW() - INTERVAL '7 days'
ORDER BY m.created_at DESC
LIMIT 100;
```

### Get thread messages

```sql
-- All messages in a thread
SELECT
    m.ts,
    u.name as user_name,
    m.text,
    m.created_at,
    CASE WHEN m.thread_ts = m.ts THEN 'parent' ELSE 'reply' END as message_type
FROM slack_messages m
LEFT JOIN slack_users u ON m.user_id = u.user_id
WHERE m.thread_ts = '1234567890.123456'
ORDER BY m.created_at ASC;
```

### Full-text search

```sql
-- Search messages by text
SELECT
    m.channel_id,
    m.ts,
    u.name as user_name,
    m.text,
    m.created_at
FROM slack_messages m
LEFT JOIN slack_users u ON m.user_id = u.user_id
WHERE m.text ILIKE '%timescaledb%'
ORDER BY m.created_at DESC
LIMIT 50;
```

### Message statistics

```sql
-- Messages per day
SELECT
    date_trunc('day', created_at) as day,
    COUNT(*) as message_count
FROM slack_messages
GROUP BY day
ORDER BY day DESC
LIMIT 30;

-- Messages by channel
SELECT
    c.name as channel_name,
    COUNT(*) as message_count
FROM slack_messages m
JOIN slack_channels c ON m.channel_id = c.channel_id
GROUP BY c.name
ORDER BY message_count DESC;
```

## Monitoring

### Check connection status

```python
from slack.service import SlackService

# Check if running
print(f"Running: {service.is_running()}")

# Check if connected
print(f"Connected: {service.socket_handler.is_connected()}")
```

### View ingestion stats

```sql
-- Total messages ingested
SELECT COUNT(*) FROM slack_messages;

-- Messages by day
SELECT
    date_trunc('day', created_at)::date as day,
    COUNT(*) as messages
FROM slack_messages
GROUP BY day
ORDER BY day DESC
LIMIT 7;

-- Latest messages
SELECT
    channel_id,
    MAX(created_at) as latest_message
FROM slack_messages
GROUP BY channel_id
ORDER BY latest_message DESC;
```

### Logs

The service uses `structlog` for structured logging:

```
INFO slack_service_started
INFO slack_event_received event_type=app_mention
INFO handling_app_mention channel=C123456 ts=1234567890.123456
INFO slack_message_ingested channel=C123456 ts=1234567890.123456
INFO event_queued event_id=42
```

## Troubleshooting

### Socket Mode won't connect

**Error**: `slack.errors.SlackApiError: invalid_auth`

**Solution**:
1. Verify `SLACK_APP_TOKEN` starts with `xapp-`
2. Ensure Socket Mode is enabled in Slack app settings
3. Check token has `connections:write` scope

### Bot not receiving messages

**Problem**: Messages in channels but bot doesn't see them

**Solution**:
1. Verify bot is invited to channels: `/invite @Athenaeum`
2. Check event subscriptions in Slack app
3. Ensure `channels:history` permission

### Historical import failing

**Error**: `rate_limited`

**Solution**:
```bash
# Increase delay between requests
python scripts/import_slack_history.py --rate-limit-delay 2.0
```

### Duplicate messages

**Problem**: Same message appears multiple times in database

**Check**:
```sql
-- Find duplicates
SELECT channel_id, ts, COUNT(*)
FROM slack_messages
GROUP BY channel_id, ts
HAVING COUNT(*) > 1;
```

**Solution**: The `(channel_id, ts)` primary key should prevent this. If duplicates exist:

```sql
-- Remove duplicates (keep first)
DELETE FROM slack_messages
WHERE ctid NOT IN (
    SELECT MIN(ctid)
    FROM slack_messages
    GROUP BY channel_id, ts
);
```

## Best Practices

### 1. Run metadata sync daily

```bash
# Add to crontab
0 2 * * * cd /path/to/athenaeum && python scripts/sync_slack_metadata.py
```

### 2. Monitor database size

```sql
-- Check message table size
SELECT pg_size_pretty(pg_total_relation_size('slack_messages'));

-- Enable compression (automatic after 45 days)
SELECT show_chunks('slack_messages');
```

### 3. Graceful shutdown

```python
import signal

def shutdown_handler(signum, frame):
    print("Shutting down gracefully...")
    service.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

service.run_forever()
```

### 4. Error handling

Always wrap in try/except:

```python
try:
    service.start()
    service.run_forever()
except Exception as e:
    logger.error("service_failed", error=str(e))
    service.stop()
    raise
```

## Next Steps

With Slack integration complete, you can:

1. **Phase 3**: Add LLM integration (Anthropic Claude) for intelligent responses
2. **Phase 4**: Integrate MCP servers for documentation search, code search, etc.
3. **Deploy**: Run in production with Docker or TigerData Cloud

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full roadmap.

## Resources

- **Slack API Docs**: https://api.slack.com/
- **Socket Mode**: https://api.slack.com/apis/connections/socket
- **Slack SDK**: https://slack.dev/python-slack-sdk/
- **TimescaleDB**: https://docs.timescale.com
- **Athenaeum Docs**: See other `*.md` files in this repository

## Summary

Athenaeum's Slack integration provides:

✅ **Real-time event processing** via Socket Mode
✅ **Durable message storage** in TimescaleDB hypertables
✅ **Automatic compression** for long-term storage
✅ **Full conversation history** with threading support
✅ **User/channel metadata** sync
✅ **Historical import** for backfilling data
✅ **Production-ready** with rate limiting and retries

All messages are queued for agent processing in Phase 3! 🏛️
