import os
import json
import time
import platform
from datetime import datetime
from typing import Dict, Any, List
import requests

from app.core.config import settings


class MetricsCollectorService:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.total_requests = 0
        self.status_counts: Dict[str, int] = {"2xx": 0, "4xx": 0, "5xx": 0, "other": 0}
        self.endpoint_stats: Dict[str, Dict[str, Any]] = {}
        self.reports_dir = os.path.abspath(settings.METRICS_REPORTS_DIRECTORY or "metrics-reports")
        if settings.METRICS_STORAGE_LOCAL_ENABLED:
            os.makedirs(self.reports_dir, exist_ok=True)

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        self.total_requests += 1
        if 200 <= status_code < 300:
            self.status_counts["2xx"] += 1
        elif 400 <= status_code < 500:
            self.status_counts["4xx"] += 1
        elif 500 <= status_code < 600:
            self.status_counts["5xx"] += 1
        else:
            self.status_counts["other"] += 1

        key = f"{method} {path}"
        if key not in self.endpoint_stats:
            self.endpoint_stats[key] = {
                "count": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
                "min_ms": duration_ms,
                "errors": 0,
            }
        st = self.endpoint_stats[key]
        st["count"] += 1
        st["total_ms"] += duration_ms
        st["max_ms"] = max(st["max_ms"], duration_ms)
        st["min_ms"] = min(st["min_ms"], duration_ms)
        if status_code >= 400:
            st["errors"] += 1

    def build_report(self, report_type: str = "MANUAL") -> Dict[str, Any]:
        uptime_seconds = int(time.time() - self.start_time)
        endpoints_summary = {}
        for k, v in self.endpoint_stats.items():
            avg_ms = round(v["total_ms"] / v["count"], 2) if v["count"] > 0 else 0.0
            endpoints_summary[k] = {
                "requests": v["count"],
                "avgResponseTimeMs": avg_ms,
                "maxResponseTimeMs": round(v["max_ms"], 2),
                "minResponseTimeMs": round(v["min_ms"], 2),
                "errors": v["errors"],
            }

        return {
            "reportType": report_type,
            "timestamp": datetime.now().isoformat(),
            "application": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "runtime": {
                "language": "Python",
                "version": platform.python_version(),
                "platform": platform.platform(),
                "uptimeSeconds": uptime_seconds,
            },
            "httpMetrics": {
                "totalRequests": self.total_requests,
                "statusBreakdown": self.status_counts,
                "endpoints": endpoints_summary,
            },
        }

    def save_report(self, report_type: str = "MANUAL") -> Dict[str, Any]:
        report = self.build_report(report_type)
        os.makedirs(self.reports_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"metrics_{report_type.lower()}_{stamp}.json"
        filepath = os.path.join(self.reports_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        report["savedFile"] = filename
        return report

    def list_saved_reports(self) -> List[str]:
        if not os.path.exists(self.reports_dir):
            return []
        files = [f for f in os.listdir(self.reports_dir) if f.endswith(".json")]
        return sorted(files, reverse=True)

    def load_report(self, filename: str) -> Dict[str, Any]:
        safe_name = os.path.basename(filename)
        filepath = os.path.join(self.reports_dir, safe_name)
        if not os.path.exists(filepath):
            return {"error": f"Archivo {safe_name} no encontrado"}
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def cleanup_old_reports(self, days_to_keep: int = 30) -> int:
        if not os.path.exists(self.reports_dir):
            return 0
        cutoff = time.time() - (days_to_keep * 86400)
        deleted = 0
        for fname in os.listdir(self.reports_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.reports_dir, fname)
            if os.path.getmtime(fpath) < cutoff:
                try:
                    os.remove(fpath)
                    deleted += 1
                except OSError:
                    pass
        return deleted

    def test_gitlab_connection(self) -> Dict[str, Any]:
        if not settings.GITLAB_ENABLED or not settings.GITLAB_TOKEN or not settings.GITLAB_PROJECT_ID:
            return {
                "enabled": settings.GITLAB_ENABLED,
                "connected": False,
                "message": "GitLab storage no está habilitado o faltan credenciales",
            }
        try:
            url = f"{settings.GITLAB_API_URL.rstrip('/')}/projects/{settings.GITLAB_PROJECT_ID}"
            resp = requests.get(url, headers={"PRIVATE-TOKEN": settings.GITLAB_TOKEN}, timeout=10)
            return {
                "enabled": True,
                "connected": resp.status_code == 200,
                "statusCode": resp.status_code,
            }
        except Exception as exc:
            return {"enabled": True, "connected": False, "error": str(exc)}


metrics_collector = MetricsCollectorService()

