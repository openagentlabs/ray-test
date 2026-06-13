/**
 * Project management service for API calls
 */

import { apiInterceptor } from './apiInterceptor';

export interface Project {
  id: string;
  name: string;
  description?: string;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectRequest {
  name: string;
  description?: string;
}

export interface UpdateProjectRequest {
  name: string;
  description?: string;
}

export interface ProjectResponse {
  success: boolean;
  message: string;
  project?: Project;
}

export interface ProjectListResponse {
  success: boolean;
  message: string;
  projects: Project[];
  total_count: number;
}

export interface ProjectError {
  detail: string;
}

class ProjectService {
  /**
   * Create a new project
   */
  async createProject(projectData: CreateProjectRequest): Promise<Project> {
    try {
      const { data } = await apiInterceptor.post<ProjectResponse>('/projects', projectData);
      if (!data.project) {
        throw new Error('Invalid response format');
      }
      return data.project;
    } catch (error) {
      console.error('Create project error:', error);
      throw error;
    }
  }

  /**
   * Get all projects for the current user
   */
  async getProjects(skip: number = 0, limit: number = 100): Promise<ProjectListResponse> {
    try {
      const { data } = await apiInterceptor.get<ProjectListResponse>('/projects', {
        params: { skip, limit },
      });
      return data;
    } catch (error) {
      console.error('Get projects error:', error);
      throw error;
    }
  }

  /**
   * Get a specific project by ID
   */
  async getProject(projectId: string): Promise<Project> {
    try {
      const { data } = await apiInterceptor.get<ProjectResponse>(`/projects/${projectId}`);
      if (!data.project) {
        throw new Error('Invalid response format');
      }
      return data.project;
    } catch (error) {
      console.error('Get project error:', error);
      throw error;
    }
  }

  /**
   * Update a project
   */
  async updateProject(projectId: string, projectData: UpdateProjectRequest): Promise<Project> {
    try {
      const { data } = await apiInterceptor.put<ProjectResponse>(`/projects/${projectId}`, projectData);
      if (!data.project) {
        throw new Error('Invalid response format');
      }
      return data.project;
    } catch (error) {
      console.error('Update project error:', error);
      throw error;
    }
  }

  /**
   * Delete a project
   */
  async deleteProject(projectId: string): Promise<void> {
    try {
      await apiInterceptor.delete(`/projects/${projectId}`);
    } catch (error) {
      console.error('Delete project error:', error);
      throw error;
    }
  }
}

export const projectService = new ProjectService();
export default projectService;
