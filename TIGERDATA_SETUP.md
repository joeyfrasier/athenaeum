# Athenaeum - TigerData Integration Guide

> Integrate Athenaeum with TigerData's production-ready cloud database and AI tools

## Overview

This guide shows how to set up **Athenaeum** with TigerData's cloud infrastructure, which provides:

- **Managed TimescaleDB**: Production-ready time-series database optimized for AI agents
- **Tiger CLI & MCP Server**: AI-powered database assistance with expert guidance
- **Hosted Documentation MCP**: Semantic search over PostgreSQL/TimescaleDB docs
- **pgvector Support**: Built-in vector embeddings for semantic search
- **Automatic Compression**: 5-10x storage savings on historical data

## Why TigerData for Athenaeum?

TigerData (formerly Timescale) is the company that built the production agent system we're based on. Their infrastructure is specifically designed for:

1. **Conversational Memory**: Time-series optimized storage with hypertables
2. **Semantic Search**: Native pgvector support for embeddings
3. **Production Reliability**: 99.99% uptime SLA
4. **AI-Optimized**: Built for agentic workflows

## Part 1: TigerData Cloud Setup

### Step 1: Sign Up for TigerData

1. **Visit**: [tigerdata.com/mst-signup](https://www.tigerdata.com/mst-signup)

2. **Free Trial**: 30-day free trial (no credit card required)
   - Includes Performance plan features
   - Perfect for development and testing
   - Upgrade to production when ready

3. **Create Account**:
   - Sign up with email or GitHub
   - Choose your cloud provider (AWS, Azure, or GCP)
   - Select a region (choose closest to your users)

### Step 2: Create a Database Service

1. **Log into Tiger Console**: [console.cloud.timescale.com](https://console.cloud.timescale.com)

2. **Create Service**:
   - Click "Create Service"
   - Service name: `athenaeum-prod` (or `athenaeum-dev`)
   - Plan: Start with **Performance** (free trial)
   - Region: Choose closest to your Slack workspace/users
   - Compute: Start with smallest size (can scale later)

3. **Wait for Provisioning** (~2 minutes):
   - TimescaleDB will be automatically configured
   - pgvector extension will be available
   - Automatic backups enabled

4. **Get Connection Details**:
   - Click on your service
   - Go to "Connection Info" tab
   - Copy the connection string (format: `postgres://tsdbadmin:password@host:port/tsdb`)

### Step 3: Configure Athenaeum

Update your `.env` file with TigerData connection:

```bash
# TigerData Cloud Connection
DATABASE_URL=postgres://tsdbadmin:YOUR_PASSWORD@YOUR_HOST.tsdb.cloud.timescale.com:PORT/tsdb

# PostgreSQL Connection Details (for reference)
PGHOST=YOUR_HOST.tsdb.cloud.timescale.com
PGPORT=PORT
PGDATABASE=tsdb
PGUSER=tsdbadmin
PGPASSWORD=YOUR_PASSWORD
DB_SCHEMA=public
```

**Security Note**: Never commit `.env` to git. Always use environment variables in production.

### Step 4: Run Database Migrations

```bash
# Option 1: Using psql directly
psql $DATABASE_URL -f migrations/001_initial_schema.sql

# Option 2: Using Python
python -c "
from database import init_db
db = init_db()
db.create_tables()
print('✅ Database tables created successfully!')
"
```

Verify the setup:

```bash
psql $DATABASE_URL -c "
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
"
```

You should see:
- `events`
- `slack_users`
- `slack_channels`
- `slack_messages` (as a hypertable!)
- `slack_reactions`
- `documentation_embeddings`

### Step 5: Verify TimescaleDB Features

Check that hypertables are working:

```sql
-- Connect to your database
psql $DATABASE_URL

-- Check hypertables
SELECT * FROM timescaledb_information.hypertables;

-- Should show slack_messages with 7-day chunks

-- Check compression policy
SELECT * FROM timescaledb_information.compression_settings;

-- Check extensions
SELECT * FROM pg_extension WHERE extname IN ('timescaledb', 'vector');
```

## Part 2: TigerData CLI & MCP Server Setup

The Tiger CLI provides AI-powered database assistance directly in your development environment.

### Step 1: Install Tiger CLI

**macOS (Homebrew)**:
```bash
brew install --cask timescale/tap/tiger-cli
```

**Linux/macOS (Quick Install)**:
```bash
curl -fsSL https://cli.tigerdata.com | sh
```

**Windows**:
Download from [Tiger CLI releases](https://github.com/timescale/tiger-cli/releases)

### Step 2: Authenticate

```bash
# Login to your TigerData account
tiger auth login

# Follow the browser authentication flow
# This will store credentials securely
```

### Step 3: Install MCP Server

The Tiger MCP server provides:
- 35 years of PostgreSQL expertise via prompt templates
- Semantic search over PostgreSQL docs (versions 14-18)
- TimescaleDB and Tiger Cloud documentation
- Auto-discovered best practices

**For Claude Code**:
```bash
tiger mcp install claude-code
```

**For Cursor IDE**:
```bash
tiger mcp install cursor
```

**For other clients**:
```bash
# Interactive mode - prompts for client selection
tiger mcp install
```

Supported clients:
- `claude-code` - Claude Code
- `cursor` - Cursor IDE
- `windsurf` - Windsurf
- `codex` - Codex
- `gemini` - Gemini CLI
- `vscode` - VS Code

### Step 4: Verify MCP Server

**In Claude Code**:
```bash
# Check available MCP tools
claude mcp list

# Should show:
# - tiger-cli (with various database tools)
# - tiger-docs (documentation search)
```

**Test the MCP server**:
```bash
# Ask Claude Code a database question
# "How do I create a hypertable in TimescaleDB?"
# Claude will use the Tiger MCP server to provide expert guidance
```

## Part 3: Use Hosted Documentation MCP

TigerData provides a public MCP server for documentation search at:
**https://mcp.tigerdata.com/docs**

### Option 1: Add to Claude Code

```bash
claude mcp add --transport http tiger-docs https://mcp.tigerdata.com/docs
```

### Option 2: Add to Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "tiger-docs": {
      "transport": "http",
      "url": "https://mcp.tigerdata.com/docs"
    }
  }
}
```

### Available Tools

The docs MCP server provides:

1. **semantic_search_postgres_docs**
   ```python
   # Search PostgreSQL documentation
   search_postgres_docs(
       prompt="How do I create an index?",
       version="17",  # 14-18 supported
       limit=10
   )
   ```

2. **semantic_search_tiger_docs**
   ```python
   # Search TimescaleDB/Tiger Cloud docs
   search_tiger_docs(
       prompt="How do I set up compression?",
       limit=10
   )
   ```

3. **get_prompt_template**
   ```python
   # Get curated prompt templates
   get_prompt_template(name="create_hypertable")
   ```

### Update Athenaeum Configuration

Update `.env` to use hosted MCP server:

```bash
# MCP Server Configuration
DOCS_MCP_URL=https://mcp.tigerdata.com/docs
DOCS_MCP_TRANSPORT=http

# If using Tiger CLI MCP (installed locally)
TIGER_CLI_MCP=true
```

## Part 4: Integrate with Athenaeum

### Update Database Connection

The existing `database/connection.py` already supports TigerData - just update your environment variables!

```python
from database import init_db

# Initialize with TigerData connection
db = init_db(database_url=os.getenv("DATABASE_URL"))

# Verify connection
if db.health_check():
    print("✅ Connected to TigerData successfully!")

    # Check pool status
    status = db.get_pool_status()
    print(f"Pool size: {status['size']}")
    print(f"Available: {status['checked_in']}")
```

### Use TimescaleDB Features

```python
from database import get_session
from database.models import SlackMessage
from datetime import datetime, timedelta

# Query recent messages (fast due to hypertable partitioning)
with get_session() as session:
    recent = session.query(SlackMessage).filter(
        SlackMessage.created_at > datetime.utcnow() - timedelta(days=7)
    ).all()

    print(f"Retrieved {len(recent)} messages from last 7 days")
```

### Enable Automatic Compression

```sql
-- Connect to TigerData
psql $DATABASE_URL

-- Check current compression settings
SELECT * FROM timescaledb_information.compression_settings
WHERE hypertable_name = 'slack_messages';

-- Manually compress old chunks (optional - happens automatically)
SELECT compress_chunk(i) FROM show_chunks('slack_messages') i
WHERE range_end < NOW() - INTERVAL '45 days';

-- Verify compression ratio
SELECT
    pg_size_pretty(before_compression_total_bytes) as before,
    pg_size_pretty(after_compression_total_bytes) as after,
    100 - (after_compression_total_bytes::numeric / before_compression_total_bytes::numeric * 100) as savings_pct
FROM timescaledb_information.compressed_chunk_stats
WHERE hypertable_name = 'slack_messages';
```

## Part 5: Production Best Practices

### Connection Pooling

TigerData recommends:
- **Connection pool size**: 10-20 for most applications
- **Max overflow**: 20
- **Pool timeout**: 30 seconds

Already configured in `database/connection.py`:

```python
db = DatabaseConnection(
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,  # Recycle connections every hour
)
```

### Monitoring

**Enable Query Stats**:
```sql
-- See slow queries
SELECT * FROM timescaledb_information.job_stats;

-- See compression stats
SELECT * FROM timescaledb_information.compressed_chunk_stats;

-- See chunk usage
SELECT show_chunks('slack_messages');
```

**Tiger Console**:
- Dashboard: [console.cloud.timescale.com](https://console.cloud.timescale.com)
- Metrics: CPU, Memory, Storage, Connections
- Alerts: Set up email alerts for high load

### Backup and Recovery

TigerData provides:
- **Automatic daily backups** (retained for 7 days on free tier)
- **Point-in-time recovery** (PITR)
- **Manual backups** via console

To create a manual backup:
```bash
# Via CLI
tiger backup create --service athenaeum-prod

# Via console: Services → Your Service → Backups → Create Backup
```

### Scaling

**Vertical Scaling** (more CPU/RAM):
```bash
# Via console: Services → Your Service → Settings → Resize
# Choose larger compute size
# No downtime required
```

**Horizontal Scaling** (read replicas):
```bash
# Via console: Services → Your Service → Replicas → Add Replica
# Offload read queries to replicas
```

## Part 6: Cost Optimization

### Pricing Model

TigerData charges based on:
1. **Compute**: Hourly rate (varies by size)
2. **Storage**: $0.001212 per GB-hour (post-compression)

**Cost Savings**:
- **Compression**: 5-10x storage reduction (auto-enabled after 45 days)
- **Right-sizing**: Start small, scale as needed
- **Storage-only**: Can pause compute when not in use

### Free Tier Limits

30-day free trial includes:
- Up to 25GB compressed storage
- 2 vCPU, 8GB RAM compute
- All features (compression, backups, etc.)

### Estimate Costs

For Athenaeum with moderate usage:
- **Storage**: 10GB compressed (~$0.12/day = ~$3.60/month)
- **Compute**: Smallest instance (~$0.50/hour = ~$360/month for 24/7)
- **Total**: ~$363/month (or less if you pause compute)

**Optimization tip**: Use compute-only when agent is running. Pause during off-hours if possible.

## Part 7: Migration from Local Setup

If you've been using local PostgreSQL/Docker:

### Step 1: Export Data

```bash
# Export from local database
pg_dump $LOCAL_DATABASE_URL > athenaeum_export.sql
```

### Step 2: Import to TigerData

```bash
# Import to TigerData
psql $DATABASE_URL < athenaeum_export.sql

# Or use pg_restore for custom format
pg_restore -d $DATABASE_URL athenaeum_export.dump
```

### Step 3: Verify Data

```bash
psql $DATABASE_URL -c "
SELECT 'events' as table_name, COUNT(*) FROM events
UNION ALL
SELECT 'slack_messages', COUNT(*) FROM slack_messages
UNION ALL
SELECT 'slack_users', COUNT(*) FROM slack_users;
"
```

### Step 4: Update Environment

```bash
# Update .env to point to TigerData
# Restart Athenaeum services
# Verify everything works
```

## Troubleshooting

### Connection Issues

**Error: "connection refused"**
```bash
# Check connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT version();"

# Check firewall: TigerData allows all IPs by default
# If restricted, add your IP in console
```

**Error: "SSL required"**
```bash
# TigerData requires SSL
# Add to connection string:
DATABASE_URL=postgres://user:pass@host:port/db?sslmode=require
```

### Performance Issues

**Slow queries**:
```sql
-- Check missing indexes
SELECT * FROM pg_stat_user_tables
WHERE schemaname = 'public' AND seq_scan > 1000;

-- Add indexes as needed
CREATE INDEX idx_custom ON table_name(column);
```

**High storage usage**:
```sql
-- Check chunk sizes
SELECT show_chunks('slack_messages');

-- Manually compress
SELECT compress_chunk('_timescaledb_internal._hyper_1_1_chunk');
```

### MCP Server Issues

**MCP server not working**:
```bash
# Reinstall
tiger mcp uninstall
tiger mcp install claude-code

# Check logs
tiger mcp logs

# Verify authentication
tiger auth status
```

## Next Steps

1. ✅ Sign up for TigerData
2. ✅ Create database service
3. ✅ Update `.env` with connection string
4. ✅ Run migrations
5. ✅ Install Tiger CLI & MCP server
6. ✅ Test connection and features
7. ✅ Deploy Athenaeum with TigerData backend

## Resources

- **TigerData Signup**: [tigerdata.com/mst-signup](https://www.tigerdata.com/mst-signup)
- **Console**: [console.cloud.timescale.com](https://console.cloud.timescale.com)
- **Documentation**: [docs.tigerdata.com](https://docs.tigerdata.com)
- **Tiger CLI Docs**: [docs.tigerdata.com/ai/latest/mcp-server](https://docs.tigerdata.com/ai/latest/mcp-server)
- **Pricing**: [tigerdata.com/pricing](https://www.tigerdata.com/pricing)
- **Support**: [tigerdata.com/support](https://www.tigerdata.com/support)

## Summary

By integrating Athenaeum with TigerData, you get:

✅ **Production-ready database** optimized for AI agents
✅ **Automatic compression** (5-10x storage savings)
✅ **pgvector support** for semantic search
✅ **AI-powered tools** via Tiger CLI MCP
✅ **Expert documentation** via hosted MCP server
✅ **99.99% uptime SLA**
✅ **Automatic backups** and point-in-time recovery
✅ **Easy scaling** (vertical and horizontal)

This is the same infrastructure TigerData uses for their own production agent (Eon) that achieved 50% daily active usage! 🏛️
