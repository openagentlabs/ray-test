import sqlite3  # kept for sqlite3.Row / OperationalError compatibility
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import ProjectCreate, ProjectUpdate, ProjectInDB, Project
from app.models._db_backend import BACKEND, connect as _db_connect, coerce_datetime as _coerce_datetime

logger = get_logger(__name__)

class ProjectDB:
    """Project persistence: Postgres when available, SQLite fallback."""

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path if db_path else settings.DATABASE_PATH)
        self.logger = logger
        self.backend = BACKEND
        self._init_database()

    def _connect(self):
        return _db_connect(self.db_path)
    
    def _init_database(self):
        """Initialize the database and create projects table if it doesn't exist"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Create projects table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        user_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_projects_user_id 
                    ON projects(user_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_projects_name 
                    ON projects(name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_projects_created_at 
                    ON projects(created_at)
                """)
                
                conn.commit()
                self.logger.info("Project database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize project database: {str(e)}")
            raise
    
    def _generate_uuid(self) -> str:
        """Generate a unique UUID for project ID"""
        return str(uuid.uuid4())
    
    def create_project(self, project_create: ProjectCreate, user_id: int) -> Optional[ProjectInDB]:
        """Create a new project"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Generate unique project ID
                project_id = self._generate_uuid()
                current_time = datetime.now().isoformat()
                
                # Insert new project
                cursor.execute("""
                    INSERT INTO projects (id, name, description, user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    project_create.name,
                    project_create.description,
                    user_id,
                    current_time,
                    current_time
                ))
                
                conn.commit()
                
                # Fetch the created project
                return self.get_project_by_id(project_id)
                
        except Exception as e:
            self.logger.error(f"Failed to create project {project_create.name}: {str(e)}")
            return None
    
    def get_project_by_id(self, project_id: str) -> Optional[ProjectInDB]:
        """Get project by ID"""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
                row = cursor.fetchone()
                
                if row:
                    return ProjectInDB(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        user_id=row['user_id'],
                        created_at=_coerce_datetime(row['created_at']),
                        updated_at=_coerce_datetime(row['updated_at']),
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get project by ID {project_id}: {str(e)}")
            return None
    
    def get_projects_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Project]:
        """Get all projects for a specific user"""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM projects 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (user_id, limit, skip))
                
                rows = cursor.fetchall()
                return [
                    Project(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        user_id=row['user_id'],
                        created_at=_coerce_datetime(row['created_at']),
                        updated_at=_coerce_datetime(row['updated_at']),
                    )
                    for row in rows
                ]
                
        except Exception as e:
            self.logger.error(f"Failed to get projects for user {user_id}: {str(e)}")
            return []
    
    def get_project_count_by_user(self, user_id: int) -> int:
        """Get total count of projects for a specific user"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (user_id,))
                return cursor.fetchone()[0]
                
        except Exception as e:
            self.logger.error(f"Failed to get project count for user {user_id}: {str(e)}")
            return 0
    
    def update_project(self, project_id: str, project_update: ProjectUpdate, user_id: int) -> Optional[ProjectInDB]:
        """Update project information (only if user owns the project)"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Verify project exists and belongs to user
                cursor.execute("SELECT id FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
                if not cursor.fetchone():
                    self.logger.warning(f"Project {project_id} not found or not owned by user {user_id}")
                    return None
                
                # Build dynamic update query
                update_fields = []
                update_values = []
                
                if project_update.name is not None:
                    update_fields.append("name = ?")
                    update_values.append(project_update.name)
                
                if project_update.description is not None:
                    update_fields.append("description = ?")
                    update_values.append(project_update.description)
                
                if not update_fields:
                    return self.get_project_by_id(project_id)
                
                update_fields.append("updated_at = ?")
                update_values.append(datetime.now().isoformat())
                update_values.append(project_id)
                
                cursor.execute(f"""
                    UPDATE projects 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, update_values)
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    return self.get_project_by_id(project_id)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to update project {project_id}: {str(e)}")
            return None
    
    def delete_project(self, project_id: str, user_id: int) -> bool:
        """Delete a project (only if user owns the project)"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Delete project only if it belongs to the user
                cursor.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
                conn.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"Project {project_id} deleted successfully by user {user_id}")
                    return True
                else:
                    self.logger.warning(f"No project found to delete with ID {project_id} for user {user_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to delete project {project_id}: {str(e)}")
            return False
    
    def project_exists(self, project_id: str) -> bool:
        """Check if a project exists by ID"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Failed to check if project exists {project_id}: {str(e)}")
            return False
    
    def user_owns_project(self, project_id: str, user_id: int) -> bool:
        """Check if a user owns a specific project"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Failed to check project ownership {project_id} for user {user_id}: {str(e)}")
            return False

# Global project database instance
project_db = ProjectDB()
