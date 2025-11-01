"""Database connection management with connection pooling."""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, event, pool, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
import structlog

from database.models import Base

logger = structlog.get_logger(__name__)


class DatabaseConnection:
    """Manages database connections with pooling and health checks."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False,
    ):
        """Initialize database connection.

        Args:
            database_url: PostgreSQL connection URL
            pool_size: Number of connections to maintain
            max_overflow: Max connections beyond pool_size
            pool_timeout: Seconds to wait for connection
            pool_recycle: Recycle connections after N seconds
            echo: Echo SQL statements (for debugging)
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://tsdbadmin:password@localhost:5432/tsdb"
        )

        # Create engine with connection pooling
        self.engine = create_engine(
            self.database_url,
            poolclass=pool.QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Verify connections before using
            echo=echo,
        )

        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Register connection event listeners
        self._register_event_listeners()

        logger.info(
            "database_connection_initialized",
            pool_size=pool_size,
            max_overflow=max_overflow,
        )

    def _register_event_listeners(self):
        """Register event listeners for connection lifecycle."""

        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Called when a new DB connection is created."""
            logger.debug("database_connection_created")

        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Called when a connection is retrieved from the pool."""
            logger.debug("database_connection_checkout")

        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            """Called when a connection is returned to the pool."""
            logger.debug("database_connection_checkin")

    def create_tables(self):
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("database_tables_created")
            self._setup_timescale_hypertables()
        except Exception as e:
            logger.error("database_tables_creation_failed", error=str(e))
            raise

    def _setup_timescale_hypertables(self):
        """Set up TimescaleDB hypertables for time-series data."""
        try:
            with self.engine.connect() as conn:
                # Check if TimescaleDB extension is available
                result = conn.execute(
                    text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
                )
                has_timescale = result.scalar()

                if has_timescale:
                    # Convert slack_messages to hypertable if not already
                    conn.execute(
                        text(
                            """
                        SELECT create_hypertable(
                            'slack_messages',
                            'created_at',
                            chunk_time_interval => INTERVAL '7 days',
                            if_not_exists => TRUE
                        )
                        """
                        )
                    )
                    conn.commit()
                    logger.info("timescaledb_hypertables_created")
                else:
                    logger.warning("timescaledb_extension_not_found")
        except Exception as e:
            logger.warning("timescaledb_setup_failed", error=str(e))

    def drop_tables(self):
        """Drop all database tables (use with caution!)."""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("database_tables_dropped")
        except Exception as e:
            logger.error("database_tables_drop_failed", error=str(e))
            raise

    def truncate_all(self):
        """Truncate all tables (for testing)."""
        try:
            with self.engine.connect() as conn:
                # Get all table names
                tables = [table.name for table in Base.metadata.sorted_tables]

                # Truncate each table
                for table in tables:
                    conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                conn.commit()

            logger.info("database_tables_truncated")
        except Exception as e:
            logger.error("database_tables_truncate_failed", error=str(e))
            raise

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional session scope.

        Usage:
            with db.session() as session:
                session.add(obj)
                session.commit()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        """Get a new database session.

        Note: Caller is responsible for closing the session.
        """
        return self.SessionLocal()

    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError as e:
            logger.error("database_health_check_failed", error=str(e))
            return False

    def get_pool_status(self) -> dict:
        """Get connection pool status."""
        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }

    def close(self):
        """Close all database connections."""
        self.engine.dispose()
        logger.info("database_connection_closed")


# Global database connection instance
_db_connection: Optional[DatabaseConnection] = None


def init_db(database_url: Optional[str] = None, **kwargs) -> DatabaseConnection:
    """Initialize global database connection."""
    global _db_connection
    _db_connection = DatabaseConnection(database_url=database_url, **kwargs)
    return _db_connection


def get_db() -> DatabaseConnection:
    """Get global database connection instance."""
    if _db_connection is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db_connection


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session from global connection.

    Usage:
        with get_session() as session:
            session.add(obj)
            session.commit()
    """
    db = get_db()
    with db.session() as session:
        yield session
