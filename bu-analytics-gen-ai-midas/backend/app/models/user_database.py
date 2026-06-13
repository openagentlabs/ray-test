import sqlite3  # kept for sqlite3.Row / OperationalError compatibility
import hashlib
import secrets
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
from datetime import timedelta
from passlib.context import CryptContext
from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import UserCreate, UserUpdate, UserInDB, User
from app.models._db_backend import BACKEND, connect as _db_connect, coerce_datetime as _coerce_datetime

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserDB:
    """User + refresh token persistence: Postgres when available, SQLite fallback."""

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path if db_path else settings.DATABASE_PATH)
        self.logger = logger
        self.backend = BACKEND
        self._init_database()

    def _connect(self, timeout: float = None):
        return _db_connect(self.db_path, timeout=timeout)
    
    def _init_database(self):
        """Initialize the database and create users table if it doesn't exist"""
        try:
            # Multiple Gunicorn workers can import this module at once. CREATE IF NOT EXISTS
            # avoids duplicate CREATE TABLE errors; BEGIN IMMEDIATE serializes migrations.
            with self._connect(timeout=30.0) as conn:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        full_name TEXT NOT NULL,
                        email TEXT,
                        hashed_password TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                cursor.execute("PRAGMA table_info(users)")
                columns = [column[1] for column in cursor.fetchall()]

                # Handle migration from old schema to new schema
                if "password_hash" in columns and "hashed_password" not in columns:
                    cursor.execute(
                        "ALTER TABLE users RENAME COLUMN password_hash TO hashed_password"
                    )
                    self.logger.info("Renamed password_hash column to hashed_password")
                    cursor.execute("PRAGMA table_info(users)")
                    columns = [column[1] for column in cursor.fetchall()]

                # Remove salt column if it exists (we're using bcrypt now)
                if "salt" in columns:
                    cursor.execute(
                        """
                        CREATE TABLE users_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            full_name TEXT NOT NULL,
                            email TEXT,
                            hashed_password TEXT NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )

                    cursor.execute(
                        """
                        INSERT INTO users_new (id, username, full_name, email, hashed_password, is_active, created_at, updated_at)
                        SELECT id, username, full_name, email, hashed_password, is_active, created_at, updated_at
                        FROM users
                        """
                    )

                    cursor.execute("DROP TABLE users")
                    cursor.execute("ALTER TABLE users_new RENAME TO users")
                    self.logger.info("Migrated users table to new schema")
                    cursor.execute("PRAGMA table_info(users)")
                    columns = [column[1] for column in cursor.fetchall()]

                if "email" not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
                    self.logger.info("Added email column to existing users table")

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_username
                    ON users(username)
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_email
                    ON users(email)
                    """
                )

                conn.commit()
                self.logger.info("User database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize user database: {str(e)}")
            raise

        # Initialize refresh_tokens table separately to ensure it's created even if users table exists
        try:
            with self._connect(timeout=30.0) as conn:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS refresh_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        token_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        revoked BOOLEAN DEFAULT FALSE
                    )
                    """
                )

                # Indexes for fast lookup
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_refresh_token_hash
                    ON refresh_tokens(token_hash)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_refresh_user_id
                    ON refresh_tokens(user_id)
                    """
                )

                conn.commit()
                self.logger.info("Refresh token table initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize refresh token table: {str(e)}")
            raise
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_user(self, user_create: UserCreate) -> Optional[UserInDB]:
        """Create a new user"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Check if username already exists
                cursor.execute("SELECT id FROM users WHERE username = ?", (user_create.username,))
                if cursor.fetchone():
                    self.logger.warning(f"Username {user_create.username} already exists")
                    return None
                
                # Hash the password
                hashed_password = self._hash_password(user_create.password)
                
                # Insert new user
                cursor.execute("""
                    INSERT INTO users (username, full_name, email, hashed_password, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_create.username,
                    user_create.full_name,
                    user_create.email,
                    hashed_password,
                    user_create.is_active
                ))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                # Fetch the created user
                return self.get_user_by_id(user_id)
                
        except Exception as e:
            self.logger.error(f"Failed to create user {user_create.username}: {str(e)}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[UserInDB]:
        """Get user by ID"""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return UserInDB(
                        id=row['id'],
                        username=row['username'],
                        full_name=row['full_name'],
                        email=row['email'],
                        hashed_password=row['hashed_password'],
                        is_active=bool(row['is_active']),
                        created_at=_coerce_datetime(row['created_at']),
                        updated_at=_coerce_datetime(row['updated_at']),
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get user by ID {user_id}: {str(e)}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        """Get user by username"""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                
                if row:
                    return UserInDB(
                        id=row['id'],
                        username=row['username'],
                        full_name=row['full_name'],
                        email=row['email'],
                        hashed_password=row['hashed_password'],
                        is_active=bool(row['is_active']),
                        created_at=_coerce_datetime(row['created_at']),
                        updated_at=_coerce_datetime(row['updated_at']),
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get user by username {username}: {str(e)}")
            return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """Authenticate a user by username and password"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not self._verify_password(password, user.hashed_password):
            return None
        return user
    
    def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[UserInDB]:
        """Update user information"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Build dynamic update query
                update_fields = []
                update_values = []
                
                if user_update.full_name is not None:
                    update_fields.append("full_name = ?")
                    update_values.append(user_update.full_name)
                
                if user_update.email is not None:
                    update_fields.append("email = ?")
                    update_values.append(user_update.email)
                
                if user_update.is_active is not None:
                    update_fields.append("is_active = ?")
                    update_values.append(user_update.is_active)
                
                if not update_fields:
                    return self.get_user_by_id(user_id)
                
                update_fields.append("updated_at = ?")
                update_values.append(datetime.now().isoformat())
                update_values.append(user_id)
                
                cursor.execute(f"""
                    UPDATE users 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, update_values)
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    return self.get_user_by_id(user_id)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to update user {user_id}: {str(e)}")
            return None
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"User {user_id} deleted successfully")
                    return True
                else:
                    self.logger.warning(f"No user found to delete with ID {user_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to delete user {user_id}: {str(e)}")
            return False
    
    def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """List all users (without password hashes)"""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, username, full_name, email, is_active, created_at, updated_at
                    FROM users
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, skip))
                
                rows = cursor.fetchall()
                return [
                    User(
                        id=row['id'],
                        username=row['username'],
                        full_name=row['full_name'],
                        email=row['email'],
                        is_active=bool(row['is_active']),
                        created_at=_coerce_datetime(row['created_at']),
                        updated_at=_coerce_datetime(row['updated_at']),
                    )
                    for row in rows
                ]
                
        except Exception as e:
            self.logger.error(f"Failed to list users: {str(e)}")
            return []
    
    def user_exists(self, username: str) -> bool:
        """Check if a user exists by username"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Failed to check if user exists {username}: {str(e)}")
            return False

    # =====================
    # Refresh Token Methods
    # =====================

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        """Hash a refresh token using SHA-256 for storage."""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def create_refresh_token(self, user_id: int, token: str, expires_at: datetime) -> bool:
        """Persist a hashed refresh token for the user."""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO refresh_tokens (user_id, token_hash, expires_at, revoked)
                    VALUES (?, ?, ?, FALSE)
                    """,
                    (user_id, self._hash_refresh_token(token), expires_at.isoformat()),
                )
                conn.commit()
                return cursor.rowcount == 1
        except Exception as e:
            self.logger.error(f"Failed to create refresh token for user {user_id}: {str(e)}")
            return False

    def verify_refresh_token(self, token: str) -> Optional[Tuple[int, int]]:
        """
        Verify a refresh token. Returns tuple (token_id, user_id) if valid, else None.
        """
        try:
            token_hash = self._hash_refresh_token(token)
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, user_id, expires_at, revoked
                    FROM refresh_tokens
                    WHERE token_hash = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (token_hash,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                if row['revoked']:
                    return None
                # Check expiry
                expires_at = _coerce_datetime(row['expires_at'])
                if expires_at is None or datetime.utcnow() > expires_at:
                    return None
                return (row['id'], row['user_id'])
        except Exception as e:
            self.logger.error(f"Failed to verify refresh token: {str(e)}")
            return None

    def revoke_refresh_token(self, token: str) -> bool:
        """Mark a specific refresh token as revoked."""
        try:
            token_hash = self._hash_refresh_token(token)
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked = TRUE
                    WHERE token_hash = ? AND revoked = FALSE
                    """,
                    (token_hash,),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Failed to revoke refresh token: {str(e)}")
            return False

    def revoke_all_refresh_tokens_for_user(self, user_id: int) -> int:
        """Revoke all active refresh tokens for a user. Returns number of tokens revoked."""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked = TRUE
                    WHERE user_id = ? AND revoked = FALSE
                    """,
                    (user_id,),
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"Failed to revoke all refresh tokens for user {user_id}: {str(e)}")
            return 0

    def rotate_refresh_token(self, old_token: str, user_id: int, new_token: str, expires_at: datetime) -> bool:
        """
        Revoke the old token and store the new one for the same user.
        Returns True if both operations succeeded.
        """
        try:
            success_revoke = self.revoke_refresh_token(old_token)
            success_create = self.create_refresh_token(user_id, new_token, expires_at)
            return success_revoke and success_create
        except Exception as e:
            self.logger.error(f"Failed to rotate refresh token for user {user_id}: {str(e)}")
            return False

# Global user database instance
user_db = UserDB()
