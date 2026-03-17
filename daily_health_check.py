"""
Daily Health Check System for BullXAuto

Runs at 7:00 AM daily via APScheduler CronTrigger.
Analyzes previous day's log file and generates a structured health report.
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from config import config

logger = logging.getLogger(__name__)


class DailyHealthChecker:
    """Generates daily health reports by analyzing logs and system state."""

    # Log patterns to count (exact strings from enhanced_order_processing.py / database.py)
    LOG_PATTERNS = {
        # Order processing lifecycle
        "processing_started": r"STARTING ENHANCED ORDER PROCESSING FOR",
        "processing_completed": r"ENHANCED ORDER PROCESSING COMPLETED",
        "processing_failed": r"Enhanced order processing failed",

        # TP detection and renewal
        "tp_detected": r"TP DETECTED",
        "orders_renewed": r"Step 4: Processing \d+ orders marked for renewal",

        # SL hit and expired coin processing
        "sl_hit_detected": r"SL hit \+ ANY expired detected",
        "expired_coins_processed": r"EXPIRED COIN PROCESSING COMPLETED",

        # Deletion events
        "deletion_failed": r"Deletion FAILED",
        "deletion_blocked": r"DELETION BLOCKED",

        # Safety events
        "wrong_coin_block": r"THIS WOULD HAVE DELETED THE WRONG ORDER",
        "orphaned_orders": r"ORPHANED ORDERS DETECTED",
        "reconciled_orders": r"Reconciled",
        "missing_orders": r"MISSING ORDERS DETECTED",

        # Task monitoring
        "missed_task_intervals": r"Detected \d+ missed task intervals",

        # Database events
        "transaction_rolled_back": r"Transaction rolled back",
        "stale_active_orders": r"stale ACTIVE orders",
    }

    # Regex for parsing log lines (same as _read_recent_logs in routers/secure.py)
    LOG_LINE_PATTERN = re.compile(
        r"^(\d{2}/\d{2}/\d{4}-\d{2}:\d{2}:\d{2})\s+-\s+(\S+)\s+-\s+"
        r"(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+-\s+(.*)$"
    )

    def __init__(self):
        self.reports_dir = config.REPORTS_DIR

    def _ensure_reports_dir(self):
        """Create reports directory if needed."""
        os.makedirs(self.reports_dir, exist_ok=True)

    def _cleanup_old_logs(self):
        """Delete log files older than LOG_RETENTION_DAYS. Health reports are kept."""
        try:
            logs_dir = "logs"
            if not os.path.exists(logs_dir):
                return

            retention_days = config.LOG_RETENTION_DAYS
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0

            for filename in os.listdir(logs_dir):
                filepath = os.path.join(logs_dir, filename)

                # Only delete .log files (skip reports/ directory and other files)
                if not filename.endswith('.log') or not os.path.isfile(filepath):
                    continue

                # Parse date from filename (format: YYYY-MM-DD.log)
                try:
                    date_str = filename.replace('.log', '')
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    continue  # Skip files that don't match the date format

                if file_date < cutoff_date:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.info(f"🗑️  Deleted old log file: {filename}")

            if deleted_count > 0:
                logger.info(f"✅ Log cleanup complete: deleted {deleted_count} log files older than {retention_days} days")
            else:
                logger.info(f"✅ Log cleanup: no log files older than {retention_days} days to delete")

        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")

    def _get_log_file_path(self, target_date: datetime) -> str:
        """Return path to log file for a given date."""
        filename = target_date.strftime("%Y-%m-%d") + ".log"
        return os.path.join("logs", filename)

    def _parse_log_file(self, log_file_path: str) -> Dict[str, Any]:
        """
        Parse a full day's log file and return aggregated counts.
        """
        results = {
            "total_lines": 0,
            "parsed_lines": 0,
            "level_counts": {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0},
            "pattern_counts": {key: 0 for key in self.LOG_PATTERNS},
            "first_entry_time": None,
            "last_entry_time": None,
            "critical_messages": [],
        }

        if not os.path.exists(log_file_path):
            results["file_missing"] = True
            return results

        results["file_missing"] = False

        # Pre-compile all search patterns
        compiled_patterns = {
            key: re.compile(pat) for key, pat in self.LOG_PATTERNS.items()
        }

        with open(log_file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                results["total_lines"] += 1
                raw_line = raw_line.rstrip()
                if not raw_line:
                    continue

                match = self.LOG_LINE_PATTERN.match(raw_line)
                if not match:
                    continue

                results["parsed_lines"] += 1
                time_str, logger_name, log_level, message = match.groups()

                # Track first/last times
                if results["first_entry_time"] is None:
                    results["first_entry_time"] = time_str
                results["last_entry_time"] = time_str

                # Count levels
                results["level_counts"][log_level] += 1

                # Count pattern matches
                for key, compiled in compiled_patterns.items():
                    if compiled.search(message):
                        results["pattern_counts"][key] += 1

                # Collect critical/error messages (up to 50)
                if log_level in ("ERROR", "CRITICAL") and len(results["critical_messages"]) < 50:
                    results["critical_messages"].append({
                        "time": time_str,
                        "logger": logger_name,
                        "level": log_level,
                        "message": message[:200]
                    })

        return results

    def _get_current_system_state(self) -> Dict[str, Any]:
        """Query live system state from singletons (same approach as /monitoring/status)."""
        from database import db_manager
        from background_task_monitor import enhanced_order_monitor, queue_processor

        # Order monitor health
        health_status = enhanced_order_monitor.get_task_health_status()

        # Enrich with active orders per profile
        for profile_name in list(health_status.get("profiles", {}).keys()):
            active_orders = db_manager.get_active_orders_by_profile(profile_name)
            health_status["profiles"][profile_name]["active_orders"] = len(active_orders)

        # Queue status
        queue_status = queue_processor.get_queue_status()
        queued_items = db_manager.get_queue_items(status="QUEUED")
        in_progress_items = db_manager.get_queue_items(status="IN_PROGRESS")

        # Uptime
        uptime_seconds = 0
        if config.APP_START_TIME:
            uptime_seconds = (datetime.now() - config.APP_START_TIME).total_seconds()

        return {
            "uptime_seconds": round(uptime_seconds),
            "scheduler_running": health_status.get("scheduler_running", False),
            "monitored_profiles": health_status.get("monitored_profiles", []),
            "profiles": health_status.get("profiles", {}),
            "queue_running": queue_status.get("is_running", False),
            "queued_items": len(queued_items),
            "in_progress_items": len(in_progress_items),
        }

    def _determine_overall_status(self, log_analysis: Dict, system_state: Dict) -> str:
        """
        Determine overall health: HEALTHY, WARNING, or CRITICAL.
        """
        pc = log_analysis.get("pattern_counts", {})
        lc = log_analysis.get("level_counts", {})

        # CRITICAL triggers
        critical_triggers = [
            pc.get("processing_failed", 0) > 0,
            pc.get("wrong_coin_block", 0) > 0,
            pc.get("deletion_blocked", 0) > 0,
            pc.get("transaction_rolled_back", 0) > 0,
            not system_state.get("scheduler_running", False),
            (lc.get("ERROR", 0) + lc.get("CRITICAL", 0)) > 10,
        ]

        if any(critical_triggers):
            return "CRITICAL"

        # WARNING triggers
        warning_triggers = [
            pc.get("orphaned_orders", 0) > 0,
            pc.get("missing_orders", 0) > 0,
            pc.get("missed_task_intervals", 0) > 0,
            pc.get("stale_active_orders", 0) > 0,
            pc.get("deletion_failed", 0) > 0,
            lc.get("ERROR", 0) > 0,
            log_analysis.get("file_missing", False),
        ]

        if any(warning_triggers):
            return "WARNING"

        return "HEALTHY"

    async def generate_report(self, target_date: datetime = None) -> Dict[str, Any]:
        """
        Generate a full daily health report.

        Args:
            target_date: Date to analyze (defaults to yesterday).

        Returns:
            Complete report dict (also saved as JSON file).
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)

        report_date_str = target_date.strftime("%Y-%m-%d")
        log_file_path = self._get_log_file_path(target_date)

        logger.info(f"Generating daily health report for {report_date_str}...")

        # 0. Clean up old log files
        self._cleanup_old_logs()

        # 1. Parse log file
        log_analysis = self._parse_log_file(log_file_path)

        # 2. Get current system state
        system_state = self._get_current_system_state()

        # 3. Determine overall status
        overall_status = self._determine_overall_status(log_analysis, system_state)

        # 4. Build report
        report = {
            "report_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "report_date": report_date_str,
            "overall_status": overall_status,

            "summary": {
                "status": overall_status,
                "log_file": log_file_path,
                "log_file_exists": not log_analysis.get("file_missing", True),
                "total_log_lines": log_analysis.get("total_lines", 0),
                "first_log_entry": log_analysis.get("first_entry_time"),
                "last_log_entry": log_analysis.get("last_entry_time"),
            },

            "log_analysis": {
                "level_counts": log_analysis.get("level_counts", {}),
                "error_count": log_analysis.get("level_counts", {}).get("ERROR", 0),
                "warning_count": log_analysis.get("level_counts", {}).get("WARNING", 0),
                "critical_count": log_analysis.get("level_counts", {}).get("CRITICAL", 0),
            },

            "order_processing": {
                "total_checks_started": log_analysis["pattern_counts"].get("processing_started", 0),
                "successful_completions": log_analysis["pattern_counts"].get("processing_completed", 0),
                "failed_processing": log_analysis["pattern_counts"].get("processing_failed", 0),
                "tp_hits_detected": log_analysis["pattern_counts"].get("tp_detected", 0),
                "sl_hits_detected": log_analysis["pattern_counts"].get("sl_hit_detected", 0),
                "expired_coins_processed": log_analysis["pattern_counts"].get("expired_coins_processed", 0),
                "renewal_batches": log_analysis["pattern_counts"].get("orders_renewed", 0),
                "deletion_failures": log_analysis["pattern_counts"].get("deletion_failed", 0),
                "deletion_blocks": log_analysis["pattern_counts"].get("deletion_blocked", 0),
            },

            "safety_events": {
                "wrong_coin_blocks": log_analysis["pattern_counts"].get("wrong_coin_block", 0),
                "orphaned_orders_detected": log_analysis["pattern_counts"].get("orphaned_orders", 0),
                "reconciliation_actions": log_analysis["pattern_counts"].get("reconciled_orders", 0),
                "missing_orders_detected": log_analysis["pattern_counts"].get("missing_orders", 0),
                "missed_task_intervals": log_analysis["pattern_counts"].get("missed_task_intervals", 0),
            },

            "database_events": {
                "transaction_rollbacks": log_analysis["pattern_counts"].get("transaction_rolled_back", 0),
                "stale_orders_warnings": log_analysis["pattern_counts"].get("stale_active_orders", 0),
            },

            "current_system_state": system_state,

            "critical_messages": log_analysis.get("critical_messages", []),
        }

        # 5. Save report to disk
        self._save_report(report, report_date_str)

        # 6. Log summary
        self._log_summary(report)

        return report

    def _save_report(self, report: Dict, date_str: str):
        """Save report as JSON file to logs/reports/YYYY-MM-DD-report.json"""
        self._ensure_reports_dir()
        filename = f"{date_str}-report.json"
        filepath = os.path.join(self.reports_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Daily health report saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save daily health report: {e}")

    def _log_summary(self, report: Dict):
        """Log a one-line summary to today's log file."""
        status = report["overall_status"]
        date = report["report_date"]
        errors = report["log_analysis"]["error_count"]
        warnings = report["log_analysis"]["warning_count"]
        checks = report["order_processing"]["total_checks_started"]
        completed = report["order_processing"]["successful_completions"]
        failed = report["order_processing"]["failed_processing"]
        tp = report["order_processing"]["tp_hits_detected"]
        safety_total = sum(report["safety_events"].values())

        summary_line = (
            f"DAILY HEALTH REPORT [{date}]: {status} | "
            f"Errors: {errors}, Warnings: {warnings} | "
            f"Checks: {checks} (ok: {completed}, fail: {failed}) | "
            f"TP hits: {tp} | Safety events: {safety_total}"
        )

        if status == "CRITICAL":
            logger.critical(f"🚨 {summary_line}")
        elif status == "WARNING":
            logger.warning(f"⚠️  {summary_line}")
        else:
            logger.info(f"✅ {summary_line}")

    def get_report(self, date_str: str) -> Optional[Dict]:
        """Load a previously saved report from disk."""
        filepath = os.path.join(self.reports_dir, f"{date_str}-report.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read report {filepath}: {e}")
            return None

    def list_reports(self, limit: int = 30) -> List[Dict[str, str]]:
        """List available report files sorted newest first."""
        self._ensure_reports_dir()
        reports = []
        try:
            for filename in sorted(os.listdir(self.reports_dir), reverse=True):
                if filename.endswith("-report.json"):
                    date_str = filename.replace("-report.json", "")
                    filepath = os.path.join(self.reports_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        reports.append({
                            "date": date_str,
                            "status": data.get("overall_status", "UNKNOWN"),
                            "generated_at": data.get("generated_at", ""),
                        })
                    except Exception:
                        reports.append({
                            "date": date_str,
                            "status": "UNREADABLE",
                            "generated_at": "",
                        })
                if len(reports) >= limit:
                    break
        except FileNotFoundError:
            pass
        return reports


# Module-level singleton
daily_health_checker = DailyHealthChecker()


async def run_daily_health_check():
    """Entry point called by APScheduler CronTrigger."""
    try:
        await daily_health_checker.generate_report()
    except Exception as e:
        logger.error(f"Daily health check failed: {e}")
