import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "mac", "tenant", "latency_ms", "cache_hit", "path"):
            val = getattr(record, key, None)
            if val is not None:
                base[key] = val
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


logger = logging.getLogger("polyprov")
