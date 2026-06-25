from prometheus_client import Counter, Histogram, Gauge

provisioning_requests = Counter(
    "polyprov_provisioning_requests_total",
    "Total provisioning requests",
    ["path_type", "status", "cache"],
)

provisioning_latency = Histogram(
    "polyprov_provisioning_latency_seconds",
    "Provisioning request latency",
    ["path_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

config_render_duration = Histogram(
    "polyprov_config_render_seconds",
    "Time to resolve + render a config on cache miss",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)

cache_hits = Counter("polyprov_cache_hits_total", "Config cache hits")
cache_misses = Counter("polyprov_cache_misses_total", "Config cache misses")

checkins = Counter("polyprov_checkins_total", "Device check-ins recorded")

firmware_bytes = Counter(
    "polyprov_firmware_bytes_total", "Firmware bytes served (logged)"
)

checkin_buffer_depth = Gauge(
    "polyprov_checkin_buffer_depth", "Pending check-in writes in Redis buffer"
)

admin_requests = Counter(
    "polyprov_admin_requests_total", "Admin API requests", ["method", "status"]
)
