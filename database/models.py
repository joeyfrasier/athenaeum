"""Database models for production agent system."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    Text,
    Index,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Event(Base):
    """Event queue for agent processing with exactly-once semantics."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(
        String(20), nullable=False, default="pending", index=True
    )  # pending, processing, completed, failed
    visibility_timeout = Column(DateTime, nullable=True, index=True)
    claimed_by = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_events_processing", "status", "visibility_timeout"),
        Index("idx_events_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Event(id={self.id}, type={self.event_type}, status={self.status})>"


class SlackUser(Base):
    """Slack user metadata."""

    __tablename__ = "slack_users"

    user_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    real_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    is_bot = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    timezone = Column(String(50), nullable=True)
    avatar_url = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("SlackMessage", back_populates="user", foreign_keys="SlackMessage.user_id")
    reactions = relationship("SlackReaction", back_populates="user")

    def __repr__(self):
        return f"<SlackUser(user_id={self.user_id}, name={self.name})>"


class SlackChannel(Base):
    """Slack channel metadata."""

    __tablename__ = "slack_channels"

    channel_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    is_private = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    topic = Column(Text, nullable=True)
    purpose = Column(Text, nullable=True)
    member_count = Column(Integer, default=0)
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("SlackMessage", back_populates="channel")

    def __repr__(self):
        return f"<SlackChannel(channel_id={self.channel_id}, name={self.name})>"


class SlackMessage(Base):
    """Slack messages with time-series optimization via TimescaleDB hypertable.

    Note: This table will be converted to a hypertable after creation
    using create_hypertable('slack_messages', 'created_at', chunk_time_interval => INTERVAL '7 days')
    """

    __tablename__ = "slack_messages"

    # Composite primary key (channel_id, ts)
    channel_id = Column(String(50), ForeignKey("slack_channels.channel_id"), primary_key=True)
    ts = Column(String(50), primary_key=True)  # Slack timestamp (e.g., "1234567890.123456")

    # Message content
    user_id = Column(String(50), ForeignKey("slack_users.user_id"), nullable=True)
    text = Column(Text, nullable=True)
    thread_ts = Column(String(50), nullable=True, index=True)  # Parent message timestamp for threads

    # Message metadata
    subtype = Column(String(50), nullable=True)  # message_changed, file_share, etc.
    is_bot_message = Column(Boolean, default=False)
    edited_ts = Column(String(50), nullable=True)

    # Attachments and files
    attachments = Column(JSONB, nullable=True)
    files = Column(JSONB, nullable=True)

    # Full message metadata
    metadata = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channel = relationship("SlackChannel", back_populates="messages")
    user = relationship("SlackUser", back_populates="messages", foreign_keys=[user_id])
    reactions = relationship("SlackReaction", back_populates="message")

    __table_args__ = (
        Index("idx_slack_messages_user_id", "user_id"),
        Index("idx_slack_messages_thread_ts", "thread_ts"),
        Index("idx_slack_messages_created_at", "created_at"),
        # Full-text search index on text
        Index("idx_slack_messages_text", "text", postgresql_using="gin", postgresql_ops={"text": "gin_trgm_ops"}),
    )

    def __repr__(self):
        return f"<SlackMessage(channel_id={self.channel_id}, ts={self.ts}, user_id={self.user_id})>"


class SlackReaction(Base):
    """Slack message reactions."""

    __tablename__ = "slack_reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String(50), nullable=False)
    message_ts = Column(String(50), nullable=False)
    user_id = Column(String(50), ForeignKey("slack_users.user_id"), nullable=False)
    reaction = Column(String(50), nullable=False)  # emoji name (e.g., "thumbsup")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = relationship("SlackUser", back_populates="reactions")
    message = relationship(
        "SlackMessage",
        back_populates="reactions",
        foreign_keys="[SlackReaction.channel_id, SlackReaction.message_ts]",
        primaryjoin="and_(SlackReaction.channel_id == SlackMessage.channel_id, SlackReaction.message_ts == SlackMessage.ts)",
    )

    __table_args__ = (
        Index("idx_slack_reactions_message", "channel_id", "message_ts"),
        Index("idx_slack_reactions_user", "user_id"),
        # Unique constraint to prevent duplicate reactions
        Index("idx_slack_reactions_unique", "channel_id", "message_ts", "user_id", "reaction", unique=True),
    )

    def __repr__(self):
        return f"<SlackReaction(channel={self.channel_id}, ts={self.message_ts}, reaction={self.reaction})>"


class DocumentationEmbedding(Base):
    """Vector embeddings for documentation semantic search.

    Requires pgvector extension: CREATE EXTENSION vector;
    """

    __tablename__ = "documentation_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # postgres, timescaledb, tiger_cloud
    version = Column(String(20), nullable=True, index=True)  # For PostgreSQL version-specific docs
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    url = Column(Text, nullable=True)

    # Vector embedding (stored as JSONB for now, can be converted to vector type with pgvector)
    # With pgvector: embedding = Column(Vector(1536), nullable=False)
    embedding = Column(JSONB, nullable=False)

    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_documentation_embeddings_source", "source", "version"),
        # With pgvector: Index('idx_documentation_embeddings_vector', 'embedding', postgresql_using='ivfflat')
    )

    def __repr__(self):
        return f"<DocumentationEmbedding(id={self.id}, source={self.source}, title={self.title[:50]})>"
