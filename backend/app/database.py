"""
数据库配置与初始化
"""
import aiosqlite
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent / "ai_code_reviewer.db"


async def get_db():
    """获取数据库连接"""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """初始化数据库表结构"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 用户表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                github_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 评审记录表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pr_url TEXT NOT NULL,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                pr_title TEXT,
                pr_author TEXT,
                summary TEXT,
                risk_level TEXT,
                analysis_result TEXT,
                diff_content TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 添加 diff_content 列（如果不存在）
        try:
            await db.execute("ALTER TABLE reviews ADD COLUMN diff_content TEXT")
        except Exception:
            pass  # 列已存在

        # 问题详情表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                suggestion TEXT,
                confidence REAL,
                is_false_positive BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES reviews(id)
            )
        """)

        await db.commit()
