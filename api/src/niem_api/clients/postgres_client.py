#!/usr/bin/env python3
"""
PostgreSQL Client

Provides database connection and query execution for PostgreSQL.
Used for application settings storage.
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)


class PostgresClient:
    """
    PostgreSQL client for application settings.

    Uses connection pooling for efficient resource management.
    """

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        min_connections: int = 1,
        max_connections: int = 10,
    ):
        """
        Initialize Postgres client with connection pool.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            min_connections: Minimum connections in pool
            max_connections: Maximum connections in pool
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

        # Create connection pool
        try:
            self.pool = SimpleConnectionPool(
                min_connections,
                max_connections,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=10,
            )
            logger.info(
                f"PostgreSQL connection pool created: {user}@{host}:{port}/{database}"
            )
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool.

        Yields:
            Database connection
        """
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a query and return results as list of dictionaries.

        Args:
            query: SQL query with named placeholders (%(name)s)
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params or {})

                # Check if this is a SELECT query
                if cursor.description:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:
                    # INSERT/UPDATE/DELETE - commit and return empty list
                    conn.commit()
                    return []

    def execute_one(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return a single result.

        Args:
            query: SQL query with named placeholders (%(name)s)
            params: Query parameters

        Returns:
            Single result dictionary or None
        """
        results = self.execute(query, params)
        return results[0] if results else None

    def execute_update(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query and return affected rows.

        Args:
            query: SQL query with named placeholders (%(name)s)
            params: Query parameters

        Returns:
            Number of affected rows
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params or {})
                conn.commit()
                return cursor.rowcount

    def close(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")
