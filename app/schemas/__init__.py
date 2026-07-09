from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TenantCreate(BaseModel):
    slug: str
    name: str


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    status: str


class SiteCreate(BaseModel):
    tenant_id: int
    name: str
    region: str | None = None
    timezone: str = "UTC"


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    name: str
    region: str | None
    timezone: str


class GroupCreate(BaseModel):
    tenant_id: int
    name: str
    kind: str = "service_profile"
    site_id: int | None = None
    parent_group_id: int | None = None
    priority: int = 100


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    name: str
    kind: str
    priority: int


class DeviceCreate(BaseModel):
    tenant_id: int
    mac: str
    model: str = "CCX"
    site_id: int | None = None
    primary_group_id: int | None = None
    serial: str | None = None
    label: str | None = None


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, max_length=255)
    asset_tag: str | None = Field(default=None, max_length=128)
    site_id: int | None = None
    primary_group_id: int | None = None
    config_profile_id: int | None = None
    status: Literal["enrolled", "disabled", "retired"] | None = None


class HealthEngineRuntimeOut(BaseModel):
    health_probe_scheduler_enabled: bool | None = None
    health_probe_icmp_enabled: bool | None = None
    health_probe_interval_seconds: int | None = None
    health_probe_timeout_seconds: float | None = None
    health_probe_batch_size: int | None = None
    health_probe_concurrency: int | None = None
    health_probe_jitter_seconds: int | None = None
    worker_connected: bool
    beat_connected: bool
    redis_connected: bool
    worker_hostnames: list[str] = Field(default_factory=list)
    celery_worker_version: str | None = None
    scheduler_last_run: datetime | None = None
    scheduler_next_run: datetime | None = None


class ProbeQueued(BaseModel):
    mac: str
    status: Literal["queued"] = "queued"
    probe_source: Literal["manual"] = "manual"
    last_probe_started_at: datetime
    next_probe_at: datetime


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    tenant_name: str | None = None
    mac: str
    model: str
    model_display: str | None = None
    serial: str | None = None
    site_id: int | None
    site_name: str | None = None
    primary_group_id: int | None = None
    primary_group_name: str | None = None
    status: str
    label: str | None
    asset_tag: str | None = None
    config_profile_id: int | None = None
    config_profile_name: str | None = None
    last_seen_at: datetime | None
    last_checkin_at: datetime | None = None
    endpoint_ip: str | None = None
    proxy_ip: str | None = None
    software_version: str | None = None
    reachability_status: str = "unknown"
    reachability_checked_at: datetime | None = None
    reachability_method: str | None = None
    reachability_latency_ms: int | None = None
    reachability_error: str | None = None
    network_reachability_status: str = "unknown"
    network_reachability_method: str | None = None
    network_reachability_error: str | None = None
    network_latency_ms: int | None = None
    network_checked_at: datetime | None = None
    web_reachability_status: str = "unknown"
    web_reachability_method: str | None = None
    web_reachability_error: str | None = None
    web_latency_ms: int | None = None
    web_checked_at: datetime | None = None
    identity_confidence: str = "unknown"
    identity_checked_at: datetime | None = None
    provisioning_health: str = "unknown"
    last_probe_started_at: datetime | None = None
    last_probe_completed_at: datetime | None = None
    last_probe_duration_ms: int | None = None
    next_probe_at: datetime | None = None
    probe_attempts: int = 0
    probe_source: str | None = None


class DeviceInventoryOut(BaseModel):
    id: int
    tenant_id: int
    tenant_name: str | None = None
    site_id: int | None
    site_name: str | None = None
    primary_group_id: int | None = None
    primary_group_name: str | None = None
    mac: str
    model: str
    model_display: str | None = None
    serial: str | None = None
    label: str | None = None
    asset_tag: str | None = None
    endpoint_ip: str | None = None
    proxy_ip: str | None = None
    software_version: str | None = None
    status: str
    lifecycle_status: str
    last_seen_at: datetime | None
    last_checkin_at: datetime | None = None
    reachability_status: str = "unknown"
    reachability_checked_at: datetime | None = None
    reachability_method: str | None = None
    reachability_latency_ms: int | None = None
    reachability_error: str | None = None
    network_reachability_status: str = "unknown"
    network_reachability_method: str | None = None
    network_reachability_error: str | None = None
    network_latency_ms: int | None = None
    network_checked_at: datetime | None = None
    web_reachability_status: str = "unknown"
    web_reachability_method: str | None = None
    web_reachability_error: str | None = None
    web_latency_ms: int | None = None
    web_checked_at: datetime | None = None
    identity_confidence: str = "unknown"
    identity_checked_at: datetime | None = None
    provisioning_health: str = "unknown"
    last_probe_completed_at: datetime | None = None
    last_probe_duration_ms: int | None = None


class DeviceImportResult(BaseModel):
    total: int
    created: int
    updated: int
    errors: list[dict]


class DiscoveredEndpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mac: str
    status: str
    model: str | None
    firmware_version: str | None
    serial: str | None
    endpoint_ip: str | None
    proxy_ip: str | None
    user_agent: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    request_count: int
    last_path: str
    last_status: int
    approved_device_id: int | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None


class DiscoveryApproveRequest(BaseModel):
    tenant_id: int
    site_id: int
    primary_group_id: int | None = None
    config_profile_id: int | None = None
    model: str | None = Field(default=None, max_length=64)
    serial: str | None = Field(default=None, max_length=64)
    label: str | None = Field(default=None, max_length=255)


class DiscoveryApproveResult(BaseModel):
    discovery: DiscoveredEndpointOut
    device: DeviceOut


class TemplateCreate(BaseModel):
    name: str
    scope: str
    scope_ref: str | None = None
    tenant_id: int | None = None
    parent_id: int | None = None
    body: dict = Field(default_factory=dict)
    priority: int = 100


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    scope: str
    scope_ref: str | None
    priority: int
    body: dict


class FirmwareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model: str
    version: str
    sha256: str
    size_bytes: int


class FirmwareAssignmentCreate(BaseModel):
    scope: str = "model"
    scope_ref: str
    firmware_image_id: int
    ring: str = "test"
    window_id: int | None = None


class ApiKeyCreate(BaseModel):
    name: str
    tenant_id: int | None = None
    scopes: list[str] = Field(default_factory=list)


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    api_key: str
    prefix: str
