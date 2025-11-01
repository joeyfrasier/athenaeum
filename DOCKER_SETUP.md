# Athenaeum - Self-Hosted Docker Setup

> Run Athenaeum with **TimescaleDB in Docker** - the same open-source database that powers TigerData Cloud

## Overview

This guide shows how to run **Athenaeum** with a self-hosted TimescaleDB setup using Docker Compose. You get all the same features as TigerData Cloud, but running on your own infrastructure:

✅ **TimescaleDB** - Production-ready time-series database
✅ **pgvector** - Semantic search with vector embeddings
✅ **Automatic Compression** - Configurable retention and compression policies
✅ **Hypertables** - 7-day chunk partitioning for fast queries
✅ **pgAdmin** - Web-based database management UI (optional)
✅ **Redis** - Caching and rate limiting (optional)

## Architecture

```
┌─────────────────────────────────────────┐
│         Athenaeum Application           │
│    (Python Worker Pool + Agent)         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       TimescaleDB Container             │
│  - PostgreSQL 17 + TimescaleDB          │
│  - pgvector extension                   │
│  - pg_trgm (full-text search)           │
│  - Automatic compression                │
└─────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- **Docker** 20.10+ and **Docker Compose** 2.0+
- **4GB RAM** minimum (8GB recommended)
- **20GB disk space** minimum

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/athenaeum.git
cd athenaeum
```

### Step 2: Configure Environment

```bash
# Copy Docker environment template
cp .env.docker .env

# Edit .env with your settings
nano .env
```

**Required settings**:
```bash
# Change the default password!
POSTGRES_PASSWORD=your-secure-password-here

# Add your Slack tokens
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_BOT_TOKEN=xoxb-your-bot-token

# Add your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Step 3: Start TimescaleDB

```bash
# Start just the database
docker-compose up -d timescaledb

# Check logs
docker-compose logs -f timescaledb
```

Wait for the database to be ready:
```
timescaledb_1  | PostgreSQL init process complete; ready for start up.
timescaledb_1  | LOG:  database system is ready to accept connections
```

### Step 4: Verify Database

```bash
# Check if TimescaleDB is running
docker-compose ps

# Should show:
# NAME                 IMAGE                              STATUS
# athenaeum-db        timescale/timescaledb-ha:pg17      Up (healthy)
```

**Test connection**:
```bash
# Using psql (if installed locally)
psql postgresql://tsdbadmin:password@localhost:5432/tsdb -c "SELECT version();"

# Using Docker exec
docker exec -it athenaeum-db psql -U tsdbadmin -d tsdb -c "SELECT version();"
```

### Step 5: Run Migrations

```bash
# Option 1: Using psql
psql postgresql://tsdbadmin:password@localhost:5432/tsdb -f migrations/001_initial_schema.sql

# Option 2: Using Docker exec
docker exec -i athenaeum-db psql -U tsdbadmin -d tsdb < migrations/001_initial_schema.sql

# Option 3: Using Python
python -c "
from database import init_db
db = init_db()
db.create_tables()
print('✅ Database initialized!')
"
```

**Verify schema**:
```bash
docker exec -it athenaeum-db psql -U tsdbadmin -d tsdb -c "
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
"
```

You should see:
- `documentation_embeddings`
- `events`
- `slack_channels`
- `slack_messages`
- `slack_reactions`
- `slack_users`

### Step 6: Verify TimescaleDB Features

```bash
docker exec -it athenaeum-db psql -U tsdbadmin -d tsdb
```

**Check extensions**:
```sql
SELECT * FROM pg_extension WHERE extname IN ('timescaledb', 'vector', 'pg_trgm');
```

**Check hypertables**:
```sql
SELECT * FROM timescaledb_information.hypertables;
-- Should show slack_messages as a hypertable
```

**Check compression settings**:
```sql
SELECT * FROM timescaledb_information.compression_settings;
```

### Step 7: Start Athenaeum

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the agent
python main.py  # (to be created in Phase 2)
```

## Optional: Web-Based Database Management

### Start pgAdmin

```bash
# Start with pgAdmin included
docker-compose --profile tools up -d
```

**Access pgAdmin**:
1. Open browser to [http://localhost:5050](http://localhost:5050)
2. Login with credentials from `.env`:
   - Email: `admin@athenaeum.local` (default)
   - Password: `admin` (default - change this!)

3. Server connection is pre-configured as "Athenaeum TimescaleDB"
4. Password: Your `POSTGRES_PASSWORD` from `.env`

### Using pgAdmin

**Run queries**:
- Tools → Query Tool
- Write SQL and execute

**View data**:
- Navigate to Servers → Athenaeum TimescaleDB → Databases → tsdb → Schemas → public → Tables
- Right-click any table → View/Edit Data

**Monitor performance**:
- Dashboard → Server Activity
- View active connections, transactions, queries

## Docker Compose Commands

### Start Services

```bash
# Start only database
docker-compose up -d timescaledb

# Start database + pgAdmin + Redis
docker-compose --profile tools up -d

# Start and view logs
docker-compose up
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ DELETES DATA)
docker-compose down -v
```

### View Logs

```bash
# All services
docker-compose logs -f

# Just TimescaleDB
docker-compose logs -f timescaledb

# Last 100 lines
docker-compose logs --tail=100
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart just database
docker-compose restart timescaledb
```

## Database Management

### Backup Database

```bash
# Backup to file
docker exec athenaeum-db pg_dump -U tsdbadmin tsdb > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup with compression
docker exec athenaeum-db pg_dump -U tsdbadmin tsdb | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore Database

```bash
# Restore from backup
docker exec -i athenaeum-db psql -U tsdbadmin tsdb < backup.sql

# Restore from compressed backup
gunzip -c backup.sql.gz | docker exec -i athenaeum-db psql -U tsdbadmin tsdb
```

### Access Database Shell

```bash
# Interactive psql session
docker exec -it athenaeum-db psql -U tsdbadmin -d tsdb

# Run single command
docker exec athenaeum-db psql -U tsdbadmin -d tsdb -c "SELECT COUNT(*) FROM events;"
```

### View Database Size

```sql
-- Total database size
SELECT pg_size_pretty(pg_database_size('tsdb'));

-- Size by table
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Compression stats
SELECT
    hypertable_name,
    pg_size_pretty(before_compression_total_bytes) as before,
    pg_size_pretty(after_compression_total_bytes) as after,
    ROUND(100 - (after_compression_total_bytes::numeric / before_compression_total_bytes::numeric * 100), 2) as savings_pct
FROM timescaledb_information.compressed_chunk_stats;
```

## TimescaleDB Features

### Hypertables

Slack messages are stored in a **hypertable** with automatic partitioning:

```sql
-- View chunks (partitions)
SELECT show_chunks('slack_messages');

-- View chunk details
SELECT
    chunk_name,
    range_start,
    range_end,
    pg_size_pretty(total_bytes)
FROM timescaledb_information.chunks
WHERE hypertable_name = 'slack_messages'
ORDER BY range_start DESC;
```

### Compression

Automatic compression after 45 days (configured in migration):

```sql
-- Check compression policy
SELECT * FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

-- Manually compress old chunks
SELECT compress_chunk(i) FROM show_chunks('slack_messages') i
WHERE range_end < NOW() - INTERVAL '45 days';

-- Decompress a chunk (if needed)
SELECT decompress_chunk('_timescaledb_internal._hyper_1_1_chunk');
```

### Retention Policy

Add automatic data retention (optional):

```sql
-- Delete data older than 1 year
SELECT add_retention_policy('slack_messages', INTERVAL '1 year');

-- View retention policies
SELECT * FROM timescaledb_information.jobs
WHERE proc_name = 'policy_retention';

-- Remove retention policy
SELECT remove_retention_policy('slack_messages');
```

### Continuous Aggregates

Create pre-computed aggregations for fast queries:

```sql
-- Example: Messages per day by channel
CREATE MATERIALIZED VIEW messages_per_day
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', created_at) AS day,
    channel_id,
    COUNT(*) as message_count
FROM slack_messages
GROUP BY day, channel_id;

-- Refresh policy (automatic updates)
SELECT add_continuous_aggregate_policy('messages_per_day',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour');
```

## Performance Tuning

### Connection Pooling

Docker Compose is configured with:
- `TS_TUNE_MAX_CONNS: 100` - Maximum connections
- `TS_TUNE_MEMORY: 2GB` - Memory allocation

**For production**, adjust based on your hardware:

```yaml
# docker-compose.yml
environment:
  TS_TUNE_MEMORY: 8GB          # 25% of total RAM
  TS_TUNE_MAX_CONNS: 200       # Based on expected load
  TS_TUNE_MAX_BG_WORKERS: 16   # Number of CPU cores
```

### Indexes

Add custom indexes for your queries:

```sql
-- Example: Index on user_id for fast user lookups
CREATE INDEX idx_slack_messages_user_created
ON slack_messages(user_id, created_at DESC);

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### Query Performance

```sql
-- Enable query timing
\timing

-- Analyze query plan
EXPLAIN ANALYZE
SELECT * FROM slack_messages
WHERE created_at > NOW() - INTERVAL '7 days';

-- Update table statistics
ANALYZE slack_messages;
```

## Monitoring

### Health Checks

```bash
# Check container health
docker-compose ps

# Database connection
docker exec athenaeum-db pg_isready -U tsdbadmin

# Extension status
docker exec athenaeum-db psql -U tsdbadmin -d tsdb -c "
SELECT extname, extversion FROM pg_extension;
"
```

### Resource Usage

```bash
# Container stats
docker stats athenaeum-db

# Disk usage
docker exec athenaeum-db df -h /home/postgres/pgdata
```

### Database Stats

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity;

-- Current queries
SELECT pid, usename, query, state
FROM pg_stat_activity
WHERE state != 'idle';

-- Cache hit ratio (should be > 99%)
SELECT
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit) as heap_hit,
    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100 as cache_hit_ratio
FROM pg_statio_user_tables;

-- Slow queries (queries taking > 1 second)
SELECT
    calls,
    mean_exec_time,
    query
FROM pg_stat_statements
WHERE mean_exec_time > 1000
ORDER BY mean_exec_time DESC
LIMIT 10;
```

## Production Deployment

### Security Hardening

**1. Change default passwords**:
```bash
# Update .env with strong passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32)
PGADMIN_PASSWORD=$(openssl rand -base64 32)
```

**2. Restrict network access**:
```yaml
# docker-compose.yml
services:
  timescaledb:
    ports:
      # Bind to localhost only
      - "127.0.0.1:5432:5432"
```

**3. Enable SSL** (optional):
```yaml
# docker-compose.yml
services:
  timescaledb:
    environment:
      POSTGRES_HOST_AUTH_METHOD: scram-sha-256
    volumes:
      - ./certs/server.crt:/var/lib/postgresql/server.crt
      - ./certs/server.key:/var/lib/postgresql/server.key
```

### Persistent Volumes

Volumes are automatically created and persisted:

```bash
# List volumes
docker volume ls | grep athenaeum

# Inspect volume
docker volume inspect athenaeum_timescaledb_data

# Backup volume
docker run --rm \
  -v athenaeum_timescaledb_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/timescaledb_backup.tar.gz /data
```

### Resource Limits

Add resource limits for production:

```yaml
# docker-compose.yml
services:
  timescaledb:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
```

### Logging

Configure log rotation:

```yaml
# docker-compose.yml
services:
  timescaledb:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs timescaledb

# Common issues:
# - Port 5432 already in use
# - Insufficient disk space
# - Corrupted data volume

# Reset (⚠️ DELETES DATA)
docker-compose down -v
docker-compose up -d
```

### Connection refused

```bash
# Verify container is running
docker-compose ps

# Check if port is accessible
nc -zv localhost 5432

# Check firewall
sudo ufw status
```

### Out of disk space

```bash
# Check Docker disk usage
docker system df

# Clean up old containers/images
docker system prune -a

# Check database size
docker exec athenaeum-db psql -U tsdbadmin -d tsdb -c "
SELECT pg_size_pretty(pg_database_size('tsdb'));
"
```

### Slow queries

```sql
-- Enable slow query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
SELECT pg_reload_conf();

-- Check logs
docker-compose logs -f timescaledb | grep "duration:"
```

## Scaling

### Vertical Scaling

Increase resources in `docker-compose.yml`:

```yaml
environment:
  TS_TUNE_MEMORY: 16GB
  TS_TUNE_MAX_CONNS: 500
deploy:
  resources:
    limits:
      cpus: '8.0'
      memory: 32G
```

### Horizontal Scaling

For read scaling, add replica:

```yaml
# docker-compose.yml
services:
  timescaledb-replica:
    image: timescale/timescaledb-ha:pg17-latest
    environment:
      POSTGRES_USER: tsdbadmin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: tsdb
      # Replication settings
      REPMGR_PARTNER_NODES: timescaledb
      REPMGR_PRIMARY_HOST: timescaledb
    depends_on:
      - timescaledb
```

## Comparison: Self-Hosted vs TigerData Cloud

| Feature | Self-Hosted Docker | TigerData Cloud |
|---------|-------------------|-----------------|
| **Cost** | Infrastructure only | ~$360/month |
| **Setup Time** | 10 minutes | 5 minutes |
| **Maintenance** | You manage | Fully managed |
| **Backups** | Manual | Automatic daily |
| **Scaling** | Manual | One-click |
| **Monitoring** | Self-setup | Built-in dashboard |
| **HA/Failover** | Manual setup | Automatic |
| **Support** | Community | Enterprise support |
| **Updates** | Manual | Automatic |
| **Best For** | Development, small teams | Production, large teams |

## Migration to TigerData Cloud

When ready to migrate to TigerData Cloud:

```bash
# 1. Export data
docker exec athenaeum-db pg_dump -U tsdbadmin tsdb > export.sql

# 2. Sign up for TigerData
# https://www.tigerdata.com/mst-signup

# 3. Import to TigerData
psql $TIGERDATA_URL < export.sql

# 4. Update .env
DATABASE_URL=$TIGERDATA_URL

# 5. Test connection
python -c "from database import init_db; db = init_db(); print(db.health_check())"
```

See [TIGERDATA_SETUP.md](TIGERDATA_SETUP.md) for full migration guide.

## Resources

- **TimescaleDB Docs**: https://docs.timescale.com
- **Docker Image**: https://hub.docker.com/r/timescale/timescaledb-ha
- **GitHub**: https://github.com/timescale/timescaledb-docker-ha
- **pgAdmin Docs**: https://www.pgadmin.org/docs/
- **Athenaeum Docs**: See `README.md` and other guides

## Summary

With Docker, you get:

✅ **100% open-source** - No vendor lock-in
✅ **Full control** - Run anywhere Docker runs
✅ **Same features** - All TimescaleDB capabilities
✅ **Cost-effective** - Only infrastructure costs
✅ **Development-ready** - Perfect for local dev and small deployments

For production at scale, consider [TigerData Cloud](TIGERDATA_SETUP.md) for managed service benefits! 🏛️
