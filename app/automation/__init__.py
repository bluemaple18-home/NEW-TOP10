"""Automation 的純政策與執行協調元件。"""

from app.automation.status_contract import AutomationStatus, STATUS_SCHEMA_VERSION, StepResult

__all__ = ["AutomationStatus", "STATUS_SCHEMA_VERSION", "StepResult"]
