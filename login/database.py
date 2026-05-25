import psycopg2
import psycopg2.pool
from psycopg2 import sql
from login import config

_pool = None


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=config.PG_POOL_MIN,
        maxconn=config.PG_POOL_MAX,
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.PG_DBNAME,
    )
    return _pool

_tables_initialized = False
TIMESTAMPTZ_COLUMNS = {
    "users": ("password_changed_at", "created_at", "updated_at"),
    "settings": ("created_at", "updated_at"),
    "ssh_configs": ("created_at", "updated_at"),
}


def _ensure_timestamptz_columns(cur):
    for table_name, column_names in TIMESTAMPTZ_COLUMNS.items():
        for column_name in column_names:
            cur.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name = %s
                """,
                (table_name, column_name),
            )
            row = cur.fetchone()
            if row and row[0] == "timestamp without time zone":
                cur.execute(
                    sql.SQL(
                        """
                        ALTER TABLE {table_name}
                        ALTER COLUMN {column_name}
                        TYPE TIMESTAMPTZ
                        USING {column_name} AT TIME ZONE 'UTC'
                        """
                    ).format(
                        table_name=sql.Identifier(table_name),
                        column_name=sql.Identifier(column_name),
                    )
                )


def init_db():
    global _tables_initialized
    if _tables_initialized:
        return
    conn = _get_pool().getconn()
    try:
        cur = conn.cursor()
        cur.execute("SET TIME ZONE 'UTC'")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(20) UNIQUE NOT NULL,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                password_changed_at TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'miyao_key'
                ) THEN
                    ALTER TABLE users DROP COLUMN miyao_key;
                END IF;
            END
            $$;
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                data JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ssh_configs (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                host VARCHAR(255) DEFAULT '',
                port INTEGER DEFAULT 22,
                username VARCHAR(100) DEFAULT '',
                password VARCHAR(255) DEFAULT '',
                remote_path VARCHAR(500) DEFAULT '/home/quant',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        _ensure_timestamptz_columns(cur)
        conn.commit()
        cur.close()
    finally:
        _get_pool().putconn(conn)
    _tables_initialized = True


def get_db():
    init_db()
    conn = _get_pool().getconn()
    try:
        yield conn
    finally:
        _get_pool().putconn(conn)
