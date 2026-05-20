import psycopg2
import psycopg2.pool
from login import config

_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=config.PG_POOL_MIN,
    maxconn=config.PG_POOL_MAX,
    host=config.PG_HOST,
    port=config.PG_PORT,
    user=config.PG_USER,
    password=config.PG_PASSWORD,
    dbname=config.PG_DBNAME,
)

_tables_initialized = False


def init_db():
    global _tables_initialized
    if _tables_initialized:
        return
    conn = _pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(20) UNIQUE NOT NULL,
                username VARCHAR(50) UNIQUE NOT NULL,
                miyao_key VARCHAR(100) NOT NULL DEFAULT '',
                password VARCHAR(255) NOT NULL,
                password_changed_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                data JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
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
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
    finally:
        _pool.putconn(conn)
    _tables_initialized = True


def get_db():
    init_db()
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)
