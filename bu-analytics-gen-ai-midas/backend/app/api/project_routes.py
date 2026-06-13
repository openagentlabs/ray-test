"""
Project Management API routes for creating, reading, updating, and deleting projects
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List

from app.models.schemas import (
    ProjectCreate, ProjectUpdate, Project, ProjectResponse, ProjectListResponse
)
from app.models.project_database import project_db
from app.api.auth_routes import get_current_user_dependency
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Initialize router
project_router = APIRouter()

# Security scheme
security = HTTPBearer()

@project_router.post("/projects", response_model=ProjectResponse)
async def create_project(
    project_create: ProjectCreate,
    current_user = Depends(get_current_user_dependency)
):
    """
    Create a new project (requires authentication)
    """
    logger.info(f"Project creation request from user: {current_user.username}")
    
    try:
        # Create project
        created_project = project_db.create_project(project_create, current_user.id)
        
        if not created_project:
            logger.error(f"Failed to create project: {project_create.name}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create project"
            )
        
        # Convert to response model
        project_response = Project(
            id=created_project.id,
            name=created_project.name,
            description=created_project.description,
            user_id=created_project.user_id,
            created_at=created_project.created_at,
            updated_at=created_project.updated_at
        )
        
        logger.info(f"Project created successfully: {created_project.name} (ID: {created_project.id}) by user {current_user.username}")
        
        return ProjectResponse(
            success=True,
            message="Project created successfully",
            project=project_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@project_router.get("/projects", response_model=ProjectListResponse)
async def get_user_projects(
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(get_current_user_dependency)
):
    """
    Get all projects for the current user (requires authentication)
    """
    logger.info(f"Get projects request from user: {current_user.username}")
    
    try:
        # Get projects for the user
        projects = project_db.get_projects_by_user(current_user.id, skip=skip, limit=limit)
        total_count = project_db.get_project_count_by_user(current_user.id)
        
        logger.info(f"Retrieved {len(projects)} projects for user {current_user.username}")
        
        return ProjectListResponse(
            success=True,
            message=f"Retrieved {len(projects)} projects",
            projects=projects,
            total_count=total_count
        )
        
    except Exception as e:
        logger.error(f"Failed to get projects for user {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@project_router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user = Depends(get_current_user_dependency)
):
    """
    Get a specific project by ID (requires authentication and ownership)
    """
    logger.info(f"Get project request for ID {project_id} from user: {current_user.username}")
    
    try:
        # Get project
        project = project_db.get_project_by_id(project_id)
        
        if not project:
            logger.warning(f"Project {project_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check if user owns the project
        if project.user_id != current_user.id:
            logger.warning(f"User {current_user.username} attempted to access project {project_id} owned by user {project.user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this project"
            )
        
        # Convert to response model
        project_response = Project(
            id=project.id,
            name=project.name,
            description=project.description,
            user_id=project.user_id,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        
        logger.info(f"Project retrieved successfully: {project.name} (ID: {project.id})")
        
        return ProjectResponse(
            success=True,
            message="Project retrieved successfully",
            project=project_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@project_router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    current_user = Depends(get_current_user_dependency)
):
    """
    Update a project (requires authentication and ownership)
    """
    logger.info(f"Update project request for ID {project_id} from user: {current_user.username}")
    
    try:
        # Check if project exists and user owns it
        if not project_db.user_owns_project(project_id, current_user.id):
            logger.warning(f"User {current_user.username} attempted to update project {project_id} they don't own")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
        
        # Update project
        updated_project = project_db.update_project(project_id, project_update, current_user.id)
        
        if not updated_project:
            logger.error(f"Failed to update project {project_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update project"
            )
        
        # Convert to response model
        project_response = Project(
            id=updated_project.id,
            name=updated_project.name,
            description=updated_project.description,
            user_id=updated_project.user_id,
            created_at=updated_project.created_at,
            updated_at=updated_project.updated_at
        )
        
        logger.info(f"Project updated successfully: {updated_project.name} (ID: {updated_project.id})")
        
        return ProjectResponse(
            success=True,
            message="Project updated successfully",
            project=project_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@project_router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user = Depends(get_current_user_dependency)
):
    """
    Delete a project (requires authentication and ownership)
    """
    logger.info(f"Delete project request for ID {project_id} from user: {current_user.username}")
    
    try:
        # Get project first to check if it exists and get details for response
        project = project_db.get_project_by_id(project_id)
        
        if not project:
            logger.warning(f"Project {project_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check if user owns the project
        if project.user_id != current_user.id:
            logger.warning(f"User {current_user.username} attempted to delete project {project_id} owned by user {project.user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this project"
            )
        
        # Delete project
        success = project_db.delete_project(project_id, current_user.id)
        
        if not success:
            logger.error(f"Failed to delete project {project_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete project"
            )
        
        logger.info(f"Project deleted successfully: {project.name} (ID: {project_id})")
        
        return {
            "success": True,
            "message": f"Project '{project.name}' deleted successfully",
            "deleted_project_id": project_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project deletion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
