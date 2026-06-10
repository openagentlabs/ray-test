"""DDL aligned with ``aspire.svc/lib/database/service-registry-schema.ts``."""

from __future__ import annotations

SERVICE_REGISTRY_DDL: str = """
CREATE TABLE IF NOT EXISTS registered_services (
  id TEXT PRIMARY KEY NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('application', 'service')),
  kind TEXT NOT NULL CHECK (kind IN ('node', 'shell', 'python')),
  workdir_relative TEXT NOT NULL,
  command TEXT NOT NULL,
  args_json TEXT NOT NULL DEFAULT '[]',
  port INTEGER,
  health_kind TEXT NOT NULL DEFAULT 'none' CHECK (health_kind IN ('none', 'http', 'tcp')),
  health_target TEXT,
  description TEXT,
  start_order INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  auto_start_with_home INTEGER NOT NULL DEFAULT 0,
  env_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_registered_services_order
  ON registered_services (enabled, start_order);
"""
