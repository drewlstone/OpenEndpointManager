from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api import ops
from app.api.deps import Principal, get_principal
from app.main import app


class FakeRedis:
    def __init__(self, value=None, fail=False):
        self.value = value
        self.fail = fail

    async def ping(self):
        if self.fail:
            raise RuntimeError("redis down")
        return True

    async def get(self, key):
        if self.fail:
            raise RuntimeError("redis down")
        return self.value

    async def llen(self, key):
        if self.fail:
            raise RuntimeError("redis down")
        if key.endswith("discovery:buffer"):
            return 2
        return 7


def _client():
    app.dependency_overrides[get_principal] = lambda: Principal(
        "user", "1", None, {"report:read"}
    )
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_health_engine_runtime_reports_worker_config(monkeypatch):
    last_run = datetime.now(timezone.utc)
    monkeypatch.setattr(ops, "redis_client", FakeRedis(last_run.isoformat().encode()))
    monkeypatch.setattr(
        ops,
        "_celery_worker_status",
        lambda: (True, ["celery@worker-1"], "5.4.0"),
    )
    monkeypatch.setattr(
        ops,
        "_worker_runtime_config",
        lambda: {
            "health_probe_scheduler_enabled": True,
            "health_probe_icmp_enabled": True,
            "health_probe_interval_seconds": 123,
            "health_probe_timeout_seconds": 4.5,
            "health_probe_batch_size": 9,
            "health_probe_concurrency": 3,
            "health_probe_jitter_seconds": 17,
            "health_probe_schedule_seconds": 60,
            "hostname": "worker-1",
        },
    )

    res = _client().get("/api/v1/ops/health-engine")

    assert res.status_code == 200
    body = res.json()
    assert body["health_probe_icmp_enabled"] is True
    assert body["health_probe_interval_seconds"] == 123
    assert body["health_probe_timeout_seconds"] == 4.5
    assert body["health_probe_batch_size"] == 9
    assert body["health_probe_concurrency"] == 3
    assert body["health_probe_jitter_seconds"] == 17
    assert body["worker_connected"] is True
    assert body["beat_connected"] is True
    assert body["redis_connected"] is True
    assert body["worker_hostnames"] == ["celery@worker-1"]
    assert body["celery_worker_version"] == "5.4.0"
    expected_last = last_run.isoformat().replace("+00:00", "Z")
    expected_next = (last_run + timedelta(seconds=60)).isoformat().replace("+00:00", "Z")
    assert body["scheduler_last_run"] == expected_last
    assert body["scheduler_next_run"] == expected_next
    assert "redis://" not in res.text


def test_health_engine_runtime_handles_disconnected_worker_and_redis(monkeypatch):
    monkeypatch.setattr(ops, "redis_client", FakeRedis(fail=True))
    monkeypatch.setattr(ops, "_celery_worker_status", lambda: (False, [], None))

    res = _client().get("/api/v1/ops/health-engine")

    assert res.status_code == 200
    body = res.json()
    assert body["worker_connected"] is False
    assert body["beat_connected"] is False
    assert body["redis_connected"] is False
    assert body["health_probe_icmp_enabled"] is None
    assert body["health_probe_interval_seconds"] is None

def _readiness_aggregates():
    return {
        "fleet": {
            "total_devices": 75000,
            "enrolled": 74900,
            "disabled": 75,
            "retired": 25,
            "pending_discoveries": 3,
            "recent_checkins_15m": 70000,
            "stale_24h": 5,
        },
        "provisioning": {
            "requests_15m": 1000,
            "requests_1h": 4000,
            "errors_15m": 2,
            "errors_1h": 4,
            "error_rate_15m": 0.002,
            "cache_hits_15m": 990,
            "cache_misses_15m": 10,
            "cache_hit_ratio_15m": 0.99,
        },
    }


def test_provisioning_readiness_reports_summary(monkeypatch):
    last_run = datetime.now(timezone.utc)

    async def fake_aggregates(db, principal, now):
        return True, _readiness_aggregates()

    monkeypatch.setattr(ops, "_readiness_db_aggregates", fake_aggregates)
    monkeypatch.setattr(ops, "redis_client", FakeRedis(last_run.isoformat().encode()))
    monkeypatch.setattr(ops, "_celery_worker_status", lambda: (True, ["celery@worker-1"], "5.4.0"))
    monkeypatch.setattr(
        ops,
        "_worker_runtime_config",
        lambda: {"health_probe_schedule_seconds": 60, "hostname": "worker-1"},
    )

    res = _client().get("/api/v1/ops/provisioning-readiness")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "warning"
    assert body["fleet"]["total_devices"] == 75000
    assert body["fleet"]["recent_checkins_15m"] == 70000
    assert body["provisioning"]["requests_15m"] == 1000
    assert body["provisioning"]["cache_hit_ratio_15m"] == 0.99
    assert body["buffers"]["checkin_buffer_depth"] == 7
    assert body["buffers"]["discovery_buffer_depth"] == 2
    assert body["runtime"] == {
        "db_connected": True,
        "redis_connected": True,
        "worker_connected": True,
        "beat_connected": True,
    }
    assert {item["code"] for item in body["attention"]} >= {
        "stale_devices",
        "pending_discoveries",
        "provisioning_errors",
    }
    assert "redis://" not in res.text


def test_provisioning_readiness_reports_critical_runtime(monkeypatch):
    async def fake_aggregates(db, principal, now):
        return False, _readiness_aggregates()

    monkeypatch.setattr(ops, "_readiness_db_aggregates", fake_aggregates)
    monkeypatch.setattr(ops, "redis_client", FakeRedis(fail=True))
    monkeypatch.setattr(ops, "_celery_worker_status", lambda: (False, [], None))

    res = _client().get("/api/v1/ops/provisioning-readiness")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "critical"
    assert body["buffers"]["checkin_buffer_depth"] is None
    assert body["runtime"] == {
        "db_connected": False,
        "redis_connected": False,
        "worker_connected": False,
        "beat_connected": False,
    }
    assert {item["code"] for item in body["attention"]} >= {
        "db_disconnected",
        "redis_disconnected",
        "worker_disconnected",
        "beat_disconnected",
    }
