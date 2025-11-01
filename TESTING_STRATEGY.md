# Production Agent System - Comprehensive Testing Strategy

## Overview

This document defines the comprehensive testing strategy for the production agent system, ensuring reliability, correctness, and performance across all components.

## Testing Philosophy

**Core Principles**:
1. **Test Early, Test Often**: Tests written alongside implementation
2. **Production-Like Testing**: Integration tests use real dependencies (Dockerized)
3. **Fast Feedback**: Unit tests complete in seconds
4. **Comprehensive Coverage**: 80%+ code coverage target
5. **Automated Everything**: No manual testing for regression prevention

## Test Pyramid

```
           /\
          /  \      E2E Tests (10%)
         / 5% \     - 20-30 tests
        /______\    - User scenarios
       /        \
      /   20%    \  Integration Tests (30%)
     /            \ - 50-100 tests
    /______________\ - Component interactions
   /                \
  /       70%        \ Unit Tests (60%)
 /                    \ - 500-1000 tests
/______________________\ - Individual functions
```

## Test Categories

### 1. Unit Tests (60% of tests)

**Purpose**: Test individual functions/classes in isolation with mocked dependencies

**Scope**:
- Database models and queries
- Event processing logic
- Prompt template rendering
- Slack message parsing
- Configuration loading
- Utility functions

**Tools**:
- `pytest` - Test framework
- `pytest-mock` - Mocking
- `pytest-cov` - Coverage reporting
- `hypothesis` - Property-based testing
- `freezegun` - Time mocking

**Example Tests**:

```python
# tests/unit/test_event_processor.py

import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from agent.event_processor import EventProcessor

class TestEventClaiming:
    def test_claim_pending_event(self, db_session, mock_worker):
        """Test claiming a pending event succeeds."""
        event = create_event(status='pending')
        db_session.add(event)
        db_session.commit()

        processor = EventProcessor(db_session, worker_id='worker-1')
        claimed = processor.claim_event()

        assert claimed is not None
        assert claimed.id == event.id
        assert claimed.status == 'processing'
        assert claimed.claimed_by == 'worker-1'

    def test_claim_with_no_pending_events(self, db_session, mock_worker):
        """Test claiming when no events are pending returns None."""
        processor = EventProcessor(db_session, worker_id='worker-1')
        claimed = processor.claim_event()

        assert claimed is None

    def test_concurrent_claims_no_duplicates(self, db_session):
        """Test that concurrent workers don't claim the same event."""
        event = create_event(status='pending')
        db_session.add(event)
        db_session.commit()

        # Simulate two concurrent claims
        processor1 = EventProcessor(db_session, worker_id='worker-1')
        processor2 = EventProcessor(db_session, worker_id='worker-2')

        claimed1 = processor1.claim_event()
        claimed2 = processor2.claim_event()

        # Only one should succeed
        assert (claimed1 is not None and claimed2 is None) or \
               (claimed1 is None and claimed2 is not None)

    @freeze_time("2025-01-01 12:00:00")
    def test_claim_respects_visibility_timeout(self, db_session):
        """Test that events with future visibility timeout are not claimed."""
        # Event with visibility timeout in the future
        event = create_event(
            status='pending',
            visibility_timeout=datetime.now() + timedelta(minutes=5)
        )
        db_session.add(event)
        db_session.commit()

        processor = EventProcessor(db_session, worker_id='worker-1')
        claimed = processor.claim_event()

        assert claimed is None

    @freeze_time("2025-01-01 12:00:00")
    def test_claim_expired_visibility_timeout(self, db_session):
        """Test that events with expired visibility timeout can be claimed."""
        # Event with visibility timeout in the past
        event = create_event(
            status='processing',
            visibility_timeout=datetime.now() - timedelta(minutes=5),
            retry_count=1
        )
        db_session.add(event)
        db_session.commit()

        processor = EventProcessor(db_session, worker_id='worker-2')
        claimed = processor.claim_event()

        assert claimed is not None
        assert claimed.retry_count == 2

# tests/unit/test_prompt_templates.py

from agent.prompts import PromptRenderer

class TestPromptTemplates:
    def test_render_system_prompt(self):
        """Test system prompt rendering with variables."""
        renderer = PromptRenderer()
        prompt = renderer.render('system.jinja2', {
            'company_name': 'Acme Corp',
            'domain_areas': ['Python', 'Databases', 'APIs']
        })

        assert 'Acme Corp' in prompt
        assert 'Python' in prompt
        assert 'Databases' in prompt

    def test_render_with_missing_variable_raises_error(self):
        """Test that missing required variables raise an error."""
        renderer = PromptRenderer()

        with pytest.raises(TemplateError):
            renderer.render('system.jinja2', {})

# tests/unit/test_slack_message_parser.py

from slack.parser import SlackMessageParser

class TestSlackMessageParser:
    def test_parse_mention_event(self):
        """Test parsing an app_mention event."""
        event = {
            'type': 'app_mention',
            'user': 'U123456',
            'text': '<@U999999> what is TimescaleDB?',
            'ts': '1234567890.123456',
            'channel': 'C123456',
            'thread_ts': '1234567890.123456'
        }

        parser = SlackMessageParser()
        parsed = parser.parse(event)

        assert parsed.user_id == 'U123456'
        assert parsed.text == 'what is TimescaleDB?'
        assert parsed.channel_id == 'C123456'
        assert parsed.thread_ts == '1234567890.123456'

    def test_parse_message_with_attachments(self):
        """Test parsing messages with attachments."""
        event = {
            'type': 'message',
            'user': 'U123456',
            'text': 'Check this out',
            'files': [{'id': 'F123', 'name': 'test.pdf'}],
            'ts': '1234567890.123456',
            'channel': 'C123456'
        }

        parser = SlackMessageParser()
        parsed = parser.parse(event)

        assert len(parsed.attachments) == 1
        assert parsed.attachments[0].name == 'test.pdf'
```

**Property-Based Testing**:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=1000))
def test_message_sanitization(text):
    """Test that message sanitization handles all text inputs."""
    from slack.sanitize import sanitize_message

    sanitized = sanitize_message(text)

    # Properties that should always hold
    assert isinstance(sanitized, str)
    assert len(sanitized) <= len(text)
    # No SQL injection characters
    assert "'" not in sanitized or "\\'" in sanitized
    assert '"' not in sanitized or '\\"' in sanitized
```

**Running Unit Tests**:
```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=agent --cov=slack --cov=database --cov-report=html

# Run specific test file
pytest tests/unit/test_event_processor.py -v

# Run with parallel execution
pytest tests/unit/ -n auto
```

**Success Criteria**:
- All tests pass
- Code coverage > 80%
- Test execution time < 30 seconds
- Zero flaky tests

### 2. Integration Tests (30% of tests)

**Purpose**: Test interactions between components with real dependencies

**Scope**:
- Database operations (real PostgreSQL)
- Event processing pipeline (claim → process → complete)
- Slack API interactions (test workspace)
- MCP server communication
- Worker pool concurrency

**Tools**:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `docker-py` - Docker container management
- `testcontainers` - Containerized dependencies
- `pytest-xdist` - Parallel execution

**Setup**:
```python
# tests/integration/conftest.py

import pytest
import docker
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    """Provide a PostgreSQL container for integration tests."""
    with PostgresContainer("timescale/timescaledb-ha:pg17") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def db_connection(postgres_container):
    """Provide a database connection for tests."""
    from database.connection import DatabaseConnection

    conn = DatabaseConnection(
        host=postgres_container.get_container_host_ip(),
        port=postgres_container.get_exposed_port(5432),
        database=postgres_container.POSTGRES_DB,
        user=postgres_container.POSTGRES_USER,
        password=postgres_container.POSTGRES_PASSWORD
    )

    # Run migrations
    conn.run_migrations()

    yield conn

    conn.close()

@pytest.fixture
def clean_db(db_connection):
    """Provide a clean database for each test."""
    # Truncate all tables before test
    db_connection.truncate_all()
    yield db_connection
    # Cleanup after test
    db_connection.truncate_all()
```

**Example Tests**:

```python
# tests/integration/test_event_pipeline.py

import pytest
import asyncio
from datetime import datetime
from agent.event_processor import EventProcessor
from agent.worker_pool import WorkerPool

class TestEventPipeline:
    @pytest.mark.asyncio
    async def test_end_to_end_event_processing(self, clean_db):
        """Test complete event processing from claim to completion."""
        # Create a test event
        event = {
            'type': 'app_mention',
            'user': 'U123456',
            'text': '<@UBOT> test message',
            'channel': 'C123456',
            'ts': '1234567890.123456'
        }

        # Insert event into queue
        event_id = clean_db.insert_event(event)

        # Create processor and worker pool
        processor = EventProcessor(clean_db)
        pool = WorkerPool(size=2, processor=processor)

        # Start processing
        pool.start()

        # Wait for processing to complete
        await asyncio.sleep(2)

        # Verify event was processed
        processed_event = clean_db.get_event(event_id)
        assert processed_event.status == 'completed'
        assert processed_event.processed_at is not None

        # Verify response was sent (check mock Slack API)
        # ... assertions ...

        # Cleanup
        pool.stop()

    def test_concurrent_event_processing(self, clean_db):
        """Test that multiple workers process events concurrently without duplicates."""
        # Create 100 test events
        event_ids = []
        for i in range(100):
            event = {
                'type': 'app_mention',
                'user': f'U{i}',
                'text': f'test message {i}',
                'channel': 'C123456',
                'ts': f'123456789.{i}'
            }
            event_ids.append(clean_db.insert_event(event))

        # Start 10 workers
        processor = EventProcessor(clean_db)
        pool = WorkerPool(size=10, processor=processor)
        pool.start()

        # Wait for all events to be processed
        import time
        max_wait = 30  # seconds
        start = time.time()
        while time.time() - start < max_wait:
            pending = clean_db.count_events(status='pending')
            if pending == 0:
                break
            time.sleep(0.5)

        pool.stop()

        # Verify all events were processed exactly once
        for event_id in event_ids:
            event = clean_db.get_event(event_id)
            assert event.status in ['completed', 'failed']
            assert event.processed_at is not None

        # Verify no duplicates (check Slack API calls)
        # ... assertions ...

    def test_retry_on_failure(self, clean_db, mock_failing_llm):
        """Test that failed events are automatically retried."""
        # Create event
        event = {'type': 'app_mention', 'text': 'test'}
        event_id = clean_db.insert_event(event)

        # Mock LLM to fail first 2 times, succeed on 3rd
        mock_failing_llm.fail_count = 2

        processor = EventProcessor(clean_db, llm=mock_failing_llm)
        pool = WorkerPool(size=1, processor=processor)
        pool.start()

        # Wait for retries
        import time
        time.sleep(10)

        pool.stop()

        # Verify event eventually succeeded
        event = clean_db.get_event(event_id)
        assert event.status == 'completed'
        assert event.retry_count == 2

# tests/integration/test_slack_integration.py

class TestSlackIntegration:
    @pytest.mark.asyncio
    async def test_socket_mode_connection(self, slack_test_workspace):
        """Test establishing Socket Mode connection to Slack."""
        from slack.socket_handler import SocketHandler

        handler = SocketHandler(
            app_token=slack_test_workspace.app_token,
            bot_token=slack_test_workspace.bot_token
        )

        # Connect
        await handler.connect()
        assert handler.is_connected()

        # Disconnect
        await handler.disconnect()
        assert not handler.is_connected()

    @pytest.mark.asyncio
    async def test_receive_app_mention(self, slack_test_workspace, clean_db):
        """Test receiving and processing an app_mention event."""
        from slack.socket_handler import SocketHandler

        handler = SocketHandler(
            app_token=slack_test_workspace.app_token,
            bot_token=slack_test_workspace.bot_token,
            db=clean_db
        )

        await handler.connect()

        # Send a mention to the bot in the test workspace
        slack_test_workspace.post_message(
            channel='test-channel',
            text='<@UBOT> what is TimescaleDB?'
        )

        # Wait for event to be received and stored
        await asyncio.sleep(2)

        # Verify event was stored in database
        events = clean_db.get_events(type='app_mention')
        assert len(events) == 1
        assert 'TimescaleDB' in events[0].payload['text']

        await handler.disconnect()

# tests/integration/test_mcp_servers.py

class TestMCPServers:
    def test_slack_mcp_get_conversation(self, clean_db, mcp_slack_server):
        """Test retrieving conversation via Slack MCP server."""
        # Insert test messages
        messages = [
            {'channel': 'C123', 'ts': '1.0', 'text': 'Hello', 'user': 'U1'},
            {'channel': 'C123', 'ts': '2.0', 'text': 'Hi there', 'user': 'U2', 'thread_ts': '1.0'},
            {'channel': 'C123', 'ts': '3.0', 'text': 'How are you?', 'user': 'U1', 'thread_ts': '1.0'}
        ]
        for msg in messages:
            clean_db.insert_message(msg)

        # Call MCP tool
        result = mcp_slack_server.call_tool('get_conversation', {
            'channel_id': 'C123',
            'thread_ts': '1.0'
        })

        assert len(result.messages) == 3
        assert result.messages[0].text == 'Hello'
        assert result.messages[1].text == 'Hi there'

    def test_docs_mcp_semantic_search(self, mcp_docs_server):
        """Test semantic search via Docs MCP server."""
        result = mcp_docs_server.call_tool('semantic_search_postgres_docs', {
            'prompt': 'How do I create a hypertable?',
            'limit': 5
        })

        assert len(result) <= 5
        assert any('hypertable' in r.content.lower() for r in result)
        # Verify results are ranked by relevance
        assert result[0].distance <= result[-1].distance

    def test_github_mcp_get_pr(self, mcp_github_server):
        """Test retrieving PR via GitHub MCP server."""
        result = mcp_github_server.call_tool('get_pull_request', {
            'owner': 'timescale',
            'repo': 'tiger-agents-for-work',
            'pr_number': 1
        })

        assert result.number == 1
        assert result.title is not None
        assert result.diff is not None
```

**Running Integration Tests**:
```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with Docker containers
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/ -v
docker-compose -f docker-compose.test.yml down

# Run specific test
pytest tests/integration/test_event_pipeline.py::TestEventPipeline::test_concurrent_event_processing -v

# Run with parallel execution (careful with shared resources)
pytest tests/integration/ -n 4
```

**Success Criteria**:
- All tests pass with real dependencies
- No race conditions or deadlocks
- Concurrent tests are deterministic
- Test execution time < 5 minutes

### 3. End-to-End Tests (10% of tests)

**Purpose**: Test complete user scenarios from Slack to response

**Scope**:
- User mentions bot → Bot responds
- Multi-turn conversations
- Tool usage workflows
- Error scenarios

**Tools**:
- `pytest` - Test framework
- Slack test workspace with real API
- Real LLM API (with test quotas)
- Full deployment (Docker Compose or staging environment)

**Example Tests**:

```python
# tests/e2e/test_user_scenarios.py

import pytest
import time
from slack_sdk import WebClient

class TestUserScenarios:
    @pytest.mark.e2e
    def test_simple_question_answer(self, slack_client, bot_user_id):
        """Test user asks simple question and receives answer."""
        # Post message mentioning bot
        response = slack_client.chat_postMessage(
            channel='test-channel',
            text=f'<@{bot_user_id}> What is PostgreSQL?'
        )
        thread_ts = response['ts']

        # Wait for bot response
        time.sleep(5)

        # Check for bot reply in thread
        replies = slack_client.conversations_replies(
            channel='test-channel',
            ts=thread_ts
        )

        bot_messages = [m for m in replies['messages'] if m['user'] == bot_user_id]
        assert len(bot_messages) == 1
        assert 'PostgreSQL' in bot_messages[0]['text']

    @pytest.mark.e2e
    def test_multi_turn_conversation(self, slack_client, bot_user_id):
        """Test multi-turn conversation with context."""
        # First message
        response = slack_client.chat_postMessage(
            channel='test-channel',
            text=f'<@{bot_user_id}> Tell me about TimescaleDB'
        )
        thread_ts = response['ts']
        time.sleep(5)

        # Follow-up question
        slack_client.chat_postMessage(
            channel='test-channel',
            thread_ts=thread_ts,
            text=f'<@{bot_user_id}> How do I install it?'
        )
        time.sleep(5)

        # Check bot maintained context
        replies = slack_client.conversations_replies(
            channel='test-channel',
            ts=thread_ts
        )

        bot_messages = [m for m in replies['messages'] if m['user'] == bot_user_id]
        assert len(bot_messages) == 2
        # Second response should reference TimescaleDB without re-asking
        assert 'install' in bot_messages[1]['text'].lower()

    @pytest.mark.e2e
    def test_search_documentation(self, slack_client, bot_user_id):
        """Test bot searches documentation to answer question."""
        response = slack_client.chat_postMessage(
            channel='test-channel',
            text=f'<@{bot_user_id}> How do I create a continuous aggregate?'
        )
        thread_ts = response['ts']
        time.sleep(5)

        replies = slack_client.conversations_replies(
            channel='test-channel',
            ts=thread_ts
        )

        bot_messages = [m for m in replies['messages'] if m['user'] == bot_user_id]
        assert len(bot_messages) == 1
        # Should contain SQL example from docs
        assert 'CREATE MATERIALIZED VIEW' in bot_messages[0]['text']

    @pytest.mark.e2e
    def test_search_github_code(self, slack_client, bot_user_id):
        """Test bot searches GitHub for code examples."""
        response = slack_client.chat_postMessage(
            channel='test-channel',
            text=f'<@{bot_user_id}> Show me an example of event claiming in our codebase'
        )
        thread_ts = response['ts']
        time.sleep(5)

        replies = slack_client.conversations_replies(
            channel='test-channel',
            ts=thread_ts
        )

        bot_messages = [m for m in replies['messages'] if m['user'] == bot_user_id]
        assert len(bot_messages) == 1
        # Should reference code from GitHub
        assert 'github.com' in bot_messages[0]['text'] or 'event_processor.py' in bot_messages[0]['text']

    @pytest.mark.e2e
    def test_error_handling(self, slack_client, bot_user_id):
        """Test bot handles errors gracefully."""
        # Ask something that will fail
        response = slack_client.chat_postMessage(
            channel='test-channel',
            text=f'<@{bot_user_id}> [TRIGGER_ERROR]'
        )
        thread_ts = response['ts']
        time.sleep(5)

        replies = slack_client.conversations_replies(
            channel='test-channel',
            ts=thread_ts
        )

        bot_messages = [m for m in replies['messages'] if m['user'] == bot_user_id]
        assert len(bot_messages) == 1
        # Should provide helpful error message
        assert 'sorry' in bot_messages[0]['text'].lower() or 'error' in bot_messages[0]['text'].lower()

    @pytest.mark.e2e
    def test_no_duplicate_responses(self, slack_client, bot_user_id):
        """Test bot never sends duplicate responses."""
        response = slack_client.chat_postMessage(
            channel='test-channel',
            text=f'<@{bot_user_id}> Test message'
        )
        thread_ts = response['ts']

        # Wait longer than usual
        time.sleep(10)

        replies = slack_client.conversations_replies(
            channel='test-channel',
            ts=thread_ts
        )

        bot_messages = [m for m in replies['messages'] if m['user'] == bot_user_id]
        # Should be exactly one response
        assert len(bot_messages) == 1
```

**Running E2E Tests**:
```bash
# Run all E2E tests
pytest tests/e2e/ -v -m e2e

# Run against staging environment
ENV=staging pytest tests/e2e/ -v -m e2e

# Run single scenario
pytest tests/e2e/test_user_scenarios.py::TestUserScenarios::test_simple_question_answer -v -m e2e
```

**Success Criteria**:
- All user scenarios complete successfully
- Response time < 5 seconds per interaction
- Zero duplicate responses
- Graceful error handling

### 4. Performance Tests

**Purpose**: Measure system performance under load

**Tools**:
- `Locust` - Load testing framework
- `pytest-benchmark` - Microbenchmarks
- Grafana - Metrics visualization

**Load Test Scenarios**:

```python
# tests/performance/locustfile.py

from locust import User, task, between, events
import random

class SlackUser(User):
    wait_time = between(5, 15)  # Wait 5-15 seconds between tasks

    def on_start(self):
        """Initialize Slack client."""
        self.slack_client = WebClient(token=self.environment.slack_token)
        self.bot_user_id = self.environment.bot_user_id
        self.channel = 'load-test-channel'

    @task(3)
    def ask_simple_question(self):
        """Ask a simple question (most common)."""
        questions = [
            'What is PostgreSQL?',
            'What is TimescaleDB?',
            'How do I create a table?',
            'What is a hypertable?'
        ]
        question = random.choice(questions)

        start_time = time.time()
        try:
            response = self.slack_client.chat_postMessage(
                channel=self.channel,
                text=f'<@{self.bot_user_id}> {question}'
            )
            thread_ts = response['ts']

            # Wait for bot response (with timeout)
            bot_replied = self.wait_for_bot_reply(thread_ts, timeout=10)

            if bot_replied:
                response_time = (time.time() - start_time) * 1000  # milliseconds
                events.request.fire(
                    request_type="slack_question",
                    name="simple_question",
                    response_time=response_time,
                    response_length=0,
                    exception=None,
                    context={}
                )
            else:
                events.request.fire(
                    request_type="slack_question",
                    name="simple_question",
                    response_time=(time.time() - start_time) * 1000,
                    response_length=0,
                    exception=Exception("Bot did not reply"),
                    context={}
                )
        except Exception as e:
            events.request.fire(
                request_type="slack_question",
                name="simple_question",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=e,
                context={}
            )

    @task(1)
    def ask_complex_question(self):
        """Ask a complex question requiring tool use."""
        questions = [
            'How do I create a continuous aggregate?',
            'Show me an example of event claiming',
            'What are the best practices for indexing?'
        ]
        question = random.choice(questions)

        start_time = time.time()
        try:
            response = self.slack_client.chat_postMessage(
                channel=self.channel,
                text=f'<@{self.bot_user_id}> {question}'
            )
            thread_ts = response['ts']

            bot_replied = self.wait_for_bot_reply(thread_ts, timeout=15)

            response_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="slack_question",
                name="complex_question",
                response_time=response_time,
                response_length=0,
                exception=None if bot_replied else Exception("No reply"),
                context={}
            )
        except Exception as e:
            events.request.fire(
                request_type="slack_question",
                name="complex_question",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=e,
                context={}
            )

    def wait_for_bot_reply(self, thread_ts, timeout=10):
        """Wait for bot to reply in thread."""
        start = time.time()
        while time.time() - start < timeout:
            replies = self.slack_client.conversations_replies(
                channel=self.channel,
                ts=thread_ts
            )
            bot_messages = [m for m in replies['messages'] if m['user'] == self.bot_user_id]
            if len(bot_messages) > 0:
                return True
            time.sleep(0.5)
        return False
```

**Running Load Tests**:
```bash
# Run load test with 10 concurrent users
locust -f tests/performance/locustfile.py --users 10 --spawn-rate 2 --run-time 10m

# Run with web UI
locust -f tests/performance/locustfile.py --host http://localhost:3000

# Run headless
locust -f tests/performance/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 30m
```

**Benchmark Tests**:

```python
# tests/performance/test_benchmarks.py

import pytest

def test_event_claiming_benchmark(benchmark, db_session):
    """Benchmark event claiming operation."""
    from agent.event_processor import EventProcessor

    # Setup: Insert 1000 events
    for i in range(1000):
        db_session.add(create_event(status='pending'))
    db_session.commit()

    processor = EventProcessor(db_session, worker_id='bench-worker')

    # Benchmark
    result = benchmark(processor.claim_event)

    assert result is not None
    # Should complete in < 10ms
    assert benchmark.stats.mean < 0.01

def test_prompt_rendering_benchmark(benchmark):
    """Benchmark prompt template rendering."""
    from agent.prompts import PromptRenderer

    renderer = PromptRenderer()
    context = {
        'company_name': 'Test Corp',
        'user_name': 'John Doe',
        'conversation': [{'role': 'user', 'content': 'test'}] * 10
    }

    result = benchmark(renderer.render, 'system.jinja2', context)

    assert len(result) > 0
    # Should complete in < 1ms
    assert benchmark.stats.mean < 0.001
```

**Performance Targets**:

| Metric | Target | Measurement |
|--------|--------|-------------|
| Event claiming latency | < 10ms (p99) | Benchmark |
| Event processing latency | < 2s (p95) | Load test |
| Database query latency | < 50ms (p95) | Integration tests |
| LLM API latency | < 1s (p95) | E2E tests |
| System throughput | > 100 events/sec | Load test |
| Concurrent users | 50+ | Load test |
| Memory usage | < 512MB per worker | Load test |
| CPU usage | < 80% | Load test |

### 5. Chaos Tests

**Purpose**: Test system resilience under failure conditions

**Scenarios**:

```python
# tests/chaos/test_resilience.py

import pytest
import time
import docker

class TestChaosEngineering:
    def test_database_connection_loss(self, agent_container, db_container):
        """Test agent handles database disconnection."""
        # Agent is running and processing events
        send_test_event()
        time.sleep(2)

        # Kill database
        db_container.stop()

        # Send more events (should be queued/retried)
        send_test_event()
        send_test_event()

        # Wait for agent to detect failure
        time.sleep(5)

        # Restart database
        db_container.start()

        # Wait for agent to reconnect
        time.sleep(10)

        # Verify all events eventually processed
        events = get_all_events()
        assert all(e.status in ['completed', 'failed'] for e in events)

    def test_slack_api_intermittent_errors(self, agent_container, mock_slack_api):
        """Test agent handles Slack API errors."""
        # Configure mock to fail 50% of requests
        mock_slack_api.set_failure_rate(0.5)

        # Send 10 events
        for i in range(10):
            send_test_event()

        time.sleep(30)

        # All events should eventually succeed via retries
        events = get_all_events()
        assert all(e.status == 'completed' for e in events)

    def test_llm_api_rate_limiting(self, agent_container, mock_llm_api):
        """Test agent handles LLM rate limiting."""
        # Configure mock to return 429 (rate limit)
        mock_llm_api.set_rate_limit(10)  # 10 requests/minute

        # Send 50 events rapidly
        for i in range(50):
            send_test_event()

        # Should process 10 immediately, queue the rest
        time.sleep(5)
        completed = count_completed_events()
        assert completed <= 15  # Some completed, but not all

        # Wait for rate limit to reset
        time.sleep(60)

        # All should eventually complete
        time.sleep(30)
        completed = count_completed_events()
        assert completed == 50

    def test_pod_restart(self, k8s_client, agent_deployment):
        """Test system recovers from pod restart."""
        # Get current pod
        pods = k8s_client.list_pods(label='app=agent')
        initial_pod = pods[0]

        # Send events
        for i in range(10):
            send_test_event()

        time.sleep(2)

        # Delete pod (triggers restart)
        k8s_client.delete_pod(initial_pod.name)

        # Wait for new pod to start
        time.sleep(10)

        # Verify new pod is running
        pods = k8s_client.list_pods(label='app=agent')
        assert len(pods) > 0
        assert pods[0].name != initial_pod.name

        # Verify events are still processed
        time.sleep(10)
        events = get_all_events()
        assert all(e.status in ['completed', 'processing'] for e in events)

    def test_network_partition(self, agent_container):
        """Test agent handles network partition."""
        # Introduce network delay
        run_command(agent_container, 'tc qdisc add dev eth0 root netem delay 2000ms')

        # Send events
        for i in range(5):
            send_test_event()

        # Events should still process (just slower)
        time.sleep(20)
        events = get_all_events()
        assert all(e.status == 'completed' for e in events)

        # Remove network delay
        run_command(agent_container, 'tc qdisc del dev eth0 root netem')
```

**Running Chaos Tests**:
```bash
# Run chaos tests (requires Docker/Kubernetes)
pytest tests/chaos/ -v

# Run specific chaos scenario
pytest tests/chaos/test_resilience.py::TestChaosEngineering::test_database_connection_loss -v
```

**Success Criteria**:
- Zero data loss under any failure scenario
- System recovers automatically within 5 minutes
- No cascading failures
- Graceful degradation (reduced throughput, not outage)

### 6. Security Tests

**Purpose**: Identify security vulnerabilities

**Tools**:
- `bandit` - Python security linter
- `safety` - Dependency vulnerability scanner
- `OWASP ZAP` - Web application security scanner
- `sqlmap` - SQL injection testing

**Security Test Categories**:

```bash
# Dependency vulnerabilities
safety check --json

# Code security issues
bandit -r agent/ slack/ database/ -f json

# SQL injection testing
python tests/security/test_sql_injection.py

# Secrets scanning
git secrets --scan

# Container security
trivy image agent:latest
```

**Example Security Tests**:

```python
# tests/security/test_sql_injection.py

import pytest

class TestSQLInjection:
    def test_message_search_sql_injection(self, db_session):
        """Test that message search is not vulnerable to SQL injection."""
        from slack.search import search_messages

        # Attempt SQL injection
        malicious_query = "test'; DROP TABLE slack_messages; --"

        try:
            results = search_messages(db_session, malicious_query)
            # Should not raise exception
            assert isinstance(results, list)

            # Verify table still exists
            count = db_session.execute("SELECT COUNT(*) FROM slack_messages").scalar()
            assert count >= 0  # Table not dropped
        except Exception as e:
            # Should not allow SQL injection
            assert 'DROP TABLE' not in str(e)

    def test_event_payload_injection(self, db_session):
        """Test that event payloads cannot inject malicious SQL."""
        from database.models import Event

        # Attempt to inject SQL in JSON payload
        event = Event(
            event_type='test',
            payload={'text': "test'; DELETE FROM events; --"},
            status='pending'
        )

        db_session.add(event)
        db_session.commit()

        # Verify no SQL injection occurred
        count = db_session.execute("SELECT COUNT(*) FROM events").scalar()
        assert count > 0  # Events table not deleted

# tests/security/test_authentication.py

class TestAuthentication:
    def test_slack_token_validation(self):
        """Test that invalid Slack tokens are rejected."""
        from slack.client import SlackClient

        with pytest.raises(AuthenticationError):
            client = SlackClient(bot_token='invalid-token')
            client.post_message('C123', 'test')

    def test_github_token_validation(self):
        """Test that invalid GitHub tokens are rejected."""
        from mcp.github_mcp.client import GitHubClient

        with pytest.raises(AuthenticationError):
            client = GitHubClient(token='invalid-token')
            client.get_pull_request('owner', 'repo', 1)

# tests/security/test_secrets_exposure.py

class TestSecretsExposure:
    def test_no_secrets_in_logs(self, caplog):
        """Test that secrets are not logged."""
        from agent.config import Config

        config = Config(
            slack_token='xoxb-secret-token',
            anthropic_key='sk-ant-secret-key'
        )

        # Trigger logging
        config.log_configuration()

        # Verify secrets are masked in logs
        assert 'xoxb-secret-token' not in caplog.text
        assert 'sk-ant-secret-key' not in caplog.text
        assert '***' in caplog.text  # Secrets should be masked

    def test_no_secrets_in_error_messages(self):
        """Test that secrets are not exposed in error messages."""
        from agent.agent import Agent

        agent = Agent(anthropic_key='sk-ant-secret-key')

        try:
            # Trigger an error
            agent.process_event({'invalid': 'event'})
        except Exception as e:
            assert 'sk-ant-secret-key' not in str(e)
```

**Success Criteria**:
- Zero critical vulnerabilities
- No secrets exposed in logs or errors
- All dependencies up-to-date with security patches
- SQL injection tests pass

## Test Data Management

### Test Fixtures

```python
# tests/fixtures/factories.py

from factory import Factory, Faker, SubFactory
from database.models import Event, SlackMessage, User, Channel

class UserFactory(Factory):
    class Meta:
        model = User

    user_id = Faker('uuid4')
    name = Faker('name')
    email = Faker('email')

class ChannelFactory(Factory):
    class Meta:
        model = Channel

    channel_id = Faker('uuid4')
    name = Faker('word')
    is_private = False

class SlackMessageFactory(Factory):
    class Meta:
        model = SlackMessage

    ts = Faker('unix_time')
    channel = SubFactory(ChannelFactory)
    user = SubFactory(UserFactory)
    text = Faker('sentence')

class EventFactory(Factory):
    class Meta:
        model = Event

    event_type = 'app_mention'
    payload = {'text': Faker('sentence')}
    status = 'pending'
```

### Test Database Seeding

```python
# tests/fixtures/seed_data.py

def seed_test_database(db_session):
    """Seed database with test data."""
    # Create users
    users = UserFactory.create_batch(10)
    db_session.add_all(users)

    # Create channels
    channels = ChannelFactory.create_batch(5)
    db_session.add_all(channels)

    # Create messages
    for channel in channels:
        messages = SlackMessageFactory.create_batch(
            20,
            channel=channel,
            user=random.choice(users)
        )
        db_session.add_all(messages)

    db_session.commit()
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb-ha:pg17
        env:
          POSTGRES_PASSWORD: password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://postgres:password@localhost:5432/postgres

  e2e-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to staging
        run: ./scripts/deploy-staging.sh
      - name: Run E2E tests
        run: pytest tests/e2e/ -v -m e2e
        env:
          STAGING_URL: ${{ secrets.STAGING_URL }}
          SLACK_TOKEN: ${{ secrets.SLACK_TEST_TOKEN }}

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Bandit
        run: bandit -r agent/ slack/ database/
      - name: Run Safety
        run: safety check
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
```

## Test Monitoring and Reporting

### Metrics to Track

1. **Test Execution Time**
   - Unit tests: < 30s
   - Integration tests: < 5m
   - E2E tests: < 15m

2. **Test Stability**
   - Flaky test rate: < 1%
   - Test pass rate: > 95%

3. **Code Coverage**
   - Line coverage: > 80%
   - Branch coverage: > 70%

4. **Test Count**
   - Total tests: 500-1000
   - Unit: 60%
   - Integration: 30%
   - E2E: 10%

### Reporting Dashboard

```python
# scripts/generate_test_report.py

import json
import pytest

# Run tests and generate report
pytest.main([
    'tests/',
    '--json-report',
    '--json-report-file=test-report.json',
    '--cov',
    '--cov-report=json'
])

# Parse results
with open('test-report.json') as f:
    test_results = json.load(f)

with open('coverage.json') as f:
    coverage_results = json.load(f)

# Generate summary
summary = {
    'total_tests': test_results['summary']['total'],
    'passed': test_results['summary']['passed'],
    'failed': test_results['summary']['failed'],
    'duration': test_results['duration'],
    'coverage': coverage_results['totals']['percent_covered']
}

print(json.dumps(summary, indent=2))
```

## Conclusion

This comprehensive testing strategy ensures the production agent system is reliable, performant, and secure. By following the test pyramid and implementing tests at all levels, we achieve:

1. **Fast Feedback**: Unit tests run in seconds
2. **Confidence**: Integration and E2E tests verify real-world scenarios
3. **Resilience**: Chaos tests ensure system recovers from failures
4. **Security**: Security tests prevent vulnerabilities
5. **Performance**: Load tests validate scalability

**Key Principles**:
- Test early and often
- Automate everything
- Use real dependencies for integration tests
- Measure and track test metrics
- Continuously improve test coverage

With this strategy, we can confidently deploy the production agent system knowing it will behave correctly under all conditions.
