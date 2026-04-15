from typing import Optional

from database.manager import BaseModel


class Notification(BaseModel):
    table_name: Optional[str] = "notifications"


class NotificationPreferences(BaseModel):
    table_name: Optional[str] = "notification_preferences"


class NotificationTemplate(BaseModel):
    table_name: Optional[str] = "notification_templates"
