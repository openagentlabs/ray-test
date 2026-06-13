"""Pydantic models for Jira tool inputs and outputs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JiraConfig(BaseModel):
    """Connection configuration loaded from env vars or CLI flags."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(..., description="Jira base URL, e.g. https://yourorg.atlassian.net")
    email: str = Field(..., description="Atlassian account email (used with API key)")
    api_token: str = Field(..., description="Jira API token generated from id.atlassian.com")


class TicketSummary(BaseModel):
    """Minimal ticket representation returned by list/find operations."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    key: str
    summary: str
    status: str
    issue_type: str
    priority: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    sprint: Optional[str] = None
    epic_key: Optional[str] = None
    epic_name: Optional[str] = None
    story_points: Optional[float] = None
    url: Optional[str] = None


class TicketDetail(TicketSummary):
    """Full ticket detail including description and comments."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    description: Optional[str] = None
    comments: list[CommentSummary] = Field(default_factory=list)
    subtasks: list[str] = Field(default_factory=list)
    linked_issues: list[str] = Field(default_factory=list)


class CommentSummary(BaseModel):
    """A single Jira comment."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    author: str
    created: str
    body: str


class BoardSummary(BaseModel):
    """Minimal board representation."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    name: str
    board_type: str
    project_key: Optional[str] = None


class SprintSummary(BaseModel):
    """Minimal sprint representation."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    name: str
    state: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goal: Optional[str] = None


class EpicSummary(BaseModel):
    """Minimal epic representation."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    key: str
    summary: str
    status: str
    assignee: Optional[str] = None
    done: bool = False
    url: Optional[str] = None


class UserSummary(BaseModel):
    """A Jira user account."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_id: str
    display_name: str
    email: Optional[str] = None
    active: bool = True


# Rebuild to resolve forward refs
TicketDetail.model_rebuild()
