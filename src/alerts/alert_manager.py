"""
Alert management system for pipeline failures and issues.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert data structure"""
    level: AlertLevel
    message: str
    context: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "level": self.level.value,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class LogChannel:
    """Sends alerts to Python logging"""
    
    def send(self, alert: Alert) -> None:
        """Send alert via logging"""
        logger = logging.getLogger('pipeline.alerts')
        msg = f"[{alert.level.value.upper()}] {alert.message}"
        
        if alert.level == AlertLevel.CRITICAL:
            logger.critical(msg)
        elif alert.level == AlertLevel.ERROR:
            logger.error(msg)
        elif alert.level == AlertLevel.WARNING:
            logger.warning(msg)
        else:
            logger.info(msg)


class FileChannel:
    """Sends alerts to JSON file"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.output_file = os.path.join(output_dir, 'alerts.json')
    
    def send(self, alert: Alert) -> None:
        """Append alert to JSON file"""
        alerts: List[Dict[str, Any]] = []
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    alerts = json.load(f)
            except (json.JSONDecodeError, IOError):
                alerts = []
        
        alerts.append(alert.to_dict())
        
        with open(self.output_file, 'w') as f:
            json.dump(alerts, f, indent=2)


class AlertManager:
    """
    Manages alerts for the pipeline.
    
    Supports multiple alert channels:
    - Logging (always enabled)
    - File (alerts.json)
    """
    
    def __init__(self, config: Dict[str, Any]):
        alerting_config = config.get('alerting', {}) if isinstance(config, dict) else {}
        self.config = alerting_config
        self.enabled = self.config.get('enabled', True)
        self.alert_log: List[Alert] = []
        
        # Initialize channels
        self.channels: List[Any] = []
        
        # Always add log channel
        self.channels.append(LogChannel())
        
        # Add file channel if output dir specified in config
        output_config = config.get('output', {}) if isinstance(config, dict) else {}
        if output_config and 'output_dir' in output_config:
            self.channels.append(FileChannel(output_config['output_dir']))
    
    def alert(self, level: AlertLevel, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Send an alert through all channels"""
        if not self.enabled:
            return
        
        alert = Alert(
            level=level,
            message=message,
            context=context or {},
            timestamp=datetime.utcnow()
        )
        
        self.alert_log.append(alert)
        
        # Send to all channels
        for channel in self.channels:
            try:
                channel.send(alert)
            except Exception as e:
                logging.error(f"Failed to send alert via {channel.__class__.__name__}: {e}")
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Send info level alert"""
        self.alert(AlertLevel.INFO, message, context)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Send warning level alert"""
        self.alert(AlertLevel.WARNING, message, context)
    
    def error(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Send error level alert"""
        self.alert(AlertLevel.ERROR, message, context)
    
    def critical(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Send critical level alert"""
        self.alert(AlertLevel.CRITICAL, message, context)
    
    def save_alert_log(self, output_path: str) -> None:
        """Save all alerts to file"""
        alerts_data = [a.to_dict() for a in self.alert_log]
        with open(output_path, 'w') as f:
            json.dump(alerts_data, f, indent=2)
    
    def get_alert_count(self, level: Optional[AlertLevel] = None) -> int:
        """Get count of alerts, optionally filtered by level"""
        if level is None:
            return len(self.alert_log)
        return sum(1 for a in self.alert_log if a.level == level)
    
    def has_critical_alerts(self) -> bool:
        """Check if any critical alerts exist"""
        return any(a.level == AlertLevel.CRITICAL for a in self.alert_log)
