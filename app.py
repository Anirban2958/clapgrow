# =============================================================================
# IMPORTS - All required libraries for the FollowUp Boss application
# =============================================================================

# Date and time handling
from datetime import date, datetime, timedelta, timezone

# Email functionality
from email.message import EmailMessage
import smtplib
import resend

# File system operations
from pathlib import Path

# Type hints for better code clarity
from typing import Any, Dict, Mapping, Optional

# Operating system interface
import os

# Flask web framework and extensions
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

# Background task scheduler for automated reminders
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables from .env file (for sensitive credentials)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # If python-dotenv is not installed, use system environment variables

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

# Define the base directory and database path
BASE_DIR = Path(__file__).resolve().parent

# Production database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Fix for Heroku/Render PostgreSQL URL format
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    DB_URI = DATABASE_URL
else:
    # Development: Use SQLite
    DB_PATH = BASE_DIR / "followups.db"
    DB_URI = f"sqlite:///{DB_PATH.as_posix()}"

# Define allowed values for status and priority fields
ALLOWED_STATUSES = {"Pending", "Done", "Snoozed"}
ALLOWED_PRIORITIES = {"Low", "Medium", "High"}


# =============================================================================
# APPLICATION FACTORY - Creates and configures the Flask application
# =============================================================================

def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    """
    Create and configure the Flask application with all necessary settings.
    
    Args:
        test_config: Optional configuration dictionary for testing purposes
        
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Core Flask and Database Configuration
    app.config.update(
        SQLALCHEMY_DATABASE_URI=DB_URI,  # Database location (SQLite or PostgreSQL)
        SQLALCHEMY_TRACK_MODIFICATIONS=False,  # Disable modification tracking for performance
        SECRET_KEY=os.getenv("SECRET_KEY", "followup-boss-secret-change-in-production"),  # Secret key for session management
    )

    # Email Notification Settings
    app.config.setdefault("DEFAULT_NOTIFY_EMAIL", os.getenv("DEFAULT_NOTIFY_EMAIL", "ops@example.com"))
    
    # Automation Settings
    app.config.setdefault("AUTOMATION_LOOKAHEAD_DAYS", 3)  # How many days ahead to check for due items
    app.config.setdefault("AUTOMATION_INTERVAL_MINUTES", 15)  # How often to run automation (in minutes)
    
    # Email Configuration - Resend API (primary) with SMTP fallback
    app.config.setdefault("RESEND_API_KEY", os.getenv("RESEND_API_KEY", ""))
    app.config.setdefault("EMAIL_FROM", os.getenv("EMAIL_FROM", "project14281428@gmail.com"))
    
    # SMTP Configuration for Email Notifications (fallback only)
    app.config.setdefault("SMTP_HOST", os.getenv("SMTP_HOST", "smtp.gmail.com"))
    app.config.setdefault("SMTP_PORT", int(os.getenv("SMTP_PORT", "587")))
    app.config.setdefault("SMTP_USERNAME", os.getenv("SMTP_USERNAME", "your-email@gmail.com"))
    app.config.setdefault("SMTP_PASSWORD", os.getenv("SMTP_PASSWORD", "your-app-password"))
    app.config.setdefault("SMTP_FROM_EMAIL", os.getenv("SMTP_FROM_EMAIL", "followup-boss@example.com"))
    app.config.setdefault("SMTP_USE_TLS", os.getenv("SMTP_USE_TLS", "true").lower() == "true")
    app.config.setdefault("SMTP_USE_SSL", os.getenv("SMTP_USE_SSL", "false").lower() == "true")
    
    # Dry Run Mode: Set to True for testing without sending real notifications
    app.config.setdefault("NOTIFICATION_DRY_RUN", os.getenv("NOTIFICATION_DRY_RUN", "false").lower() == "true")

    # Apply test configuration if provided
    if test_config:
        app.config.update(test_config)

    # Initialize SQLAlchemy for database operations
    db = SQLAlchemy(app)

    # =========================================================================
    # DATABASE MODELS - Define the structure of our database tables
    # =========================================================================

    class FollowUp(db.Model):
        """
        Main model for storing follow-up tasks.
        Each follow-up represents a task that needs to be completed by a certain date.
        """
        __tablename__ = "followups"
        
        # Primary Key
        id = db.Column(db.Integer, primary_key=True)
        
        # Core Follow-up Information
        source = db.Column(db.String(32), nullable=False)  # Where this follow-up came from (e.g., "Meeting", "Email")
        contact = db.Column(db.String(120), nullable=False)  # Who to follow up with (person/company name)
        description = db.Column(db.Text, nullable=False)  # What needs to be done
        due_date = db.Column(db.Date, nullable=False)  # When this task is due
        priority = db.Column(db.String(16), nullable=False, default="Medium")  # Low, Medium, or High
        
        # Status Management
        status = db.Column(db.String(16), nullable=False, default="Pending")  # Pending, Done, or Snoozed
        snoozed_till = db.Column(db.Date, nullable=True)  # If snoozed, until when
        
        # Notification Settings
        notify_email = db.Column(db.String(255), nullable=True)  # Email address for notifications
        due_notification_sent = db.Column(db.Boolean, nullable=False, default=False)  # Has due notification been sent
        snooze_notification_sent = db.Column(db.Boolean, nullable=False, default=False)  # Has snooze notification been sent
        
        # Timestamps for tracking
        created_at = db.Column(
            db.DateTime,
            nullable=False,
            default=lambda: datetime.now(timezone.utc),  # When this follow-up was created
        )
        updated_at = db.Column(
            db.DateTime,
            nullable=False,
            default=lambda: datetime.now(timezone.utc),  # When this follow-up was last updated
            onupdate=lambda: datetime.now(timezone.utc),
        )
        completed_at = db.Column(db.DateTime, nullable=True)  # When this follow-up was marked as Done
        last_notification_at = db.Column(db.DateTime, nullable=True)  # When we last sent a reminder

        @property
        def is_overdue(self) -> bool:
            """Check if this follow-up is overdue (past due date and still pending)"""
            return self.status == "Pending" and self.due_date and self.due_date < date.today()

        @property
        def due_label(self) -> str:
            """Get a formatted string for the due date or snooze date"""
            reference = self.due_date
            if self.status == "Snoozed" and self.snoozed_till:
                reference = self.snoozed_till
            return reference.strftime("%b %d, %Y") if reference else "—"

        def to_dict(self) -> dict:
            """Convert this follow-up to a dictionary for API responses"""
            return {
                "id": self.id,
                "source": self.source,
                "contact": self.contact,
                "description": self.description,
                "due_date": self.due_date.isoformat() if self.due_date else None,
                "priority": self.priority,
                "status": self.status,
                "snoozed_till": self.snoozed_till.isoformat() if self.snoozed_till else None,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "notify_email": self.notify_email,
                "due_notification_sent": self.due_notification_sent,
                "snooze_notification_sent": self.snooze_notification_sent,
                "last_notification_at": self.last_notification_at.isoformat() if self.last_notification_at else None,
                "is_overdue": self.is_overdue,
            }

    class NotificationLog(db.Model):
        """
        Model for tracking all notifications sent to users.
        This helps us keep a history of what was sent and when.
        """
        __tablename__ = "notification_logs"
        
        # Primary Key
        id = db.Column(db.Integer, primary_key=True)
        
        # Foreign Key linking to the follow-up
        followup_id = db.Column(db.Integer, db.ForeignKey("followups.id"), nullable=False)
        
        # Notification Details
        channel = db.Column(db.String(32), nullable=False)  # "email" (WhatsApp removed)
        recipient = db.Column(db.String(255), nullable=False)  # Email address of recipient
        reason = db.Column(db.String(32), nullable=False)  # Why was notification sent (e.g., "due_soon")
        message = db.Column(db.Text, nullable=False)  # The actual message content that was sent
        
        # Timestamp
        created_at = db.Column(
            db.DateTime,
            nullable=False,
            default=lambda: datetime.now(timezone.utc),  # When this notification was sent
        )

        # Relationship to access the related follow-up
        followup = db.relationship("FollowUp", backref=db.backref("notification_logs", lazy=True))

    # Create all database tables if they don't exist
    # Create all database tables if they don't exist
    with app.app_context():
        db.create_all()

    # Make models accessible for testing purposes
    setattr(app, "db", db)
    setattr(app, "FollowUp", FollowUp)
    setattr(app, "NotificationLog", NotificationLog)

    # =========================================================================
    # HELPER FUNCTIONS - Utility functions used throughout the application
    # =========================================================================

    def parse_date(value: Optional[Any]) -> Optional[date]:
        """
        Convert various date formats to a Python date object.
        
        Args:
            value: Date string in YYYY-MM-DD format, or date object, or None
            
        Returns:
            date object or None
            
        Raises:
            ValueError: If the date format is invalid
        """
        if value in (None, ""):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.") from exc

    def extract_followup_fields(data: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Extract and validate follow-up fields from form data or JSON payload.
        
        Args:
            data: Dictionary containing follow-up information
            
        Returns:
            Dictionary of validated follow-up fields
            
        Raises:
            ValueError: If any required field is missing or invalid
        """
        def read_text(key: str, label: str) -> str:
            """Helper to extract and validate text fields"""
            raw = data.get(key)
            text = raw.strip() if isinstance(raw, str) else (str(raw).strip() if raw else "")
            if not text:
                raise ValueError(f"{label} is required.")
            return text

        # Extract required text fields
        source = read_text("source", "Source")
        contact = read_text("contact", "Who to follow up with")
        description = read_text("description", "Follow-up description")

        # Parse and validate due date
        try:
            due_date = parse_date(data.get("due_date"))
        except ValueError as error:
            raise ValueError(str(error))
        if due_date is None:
            raise ValueError("Due date is required.")

        # Validate priority (Low, Medium, High)
        priority_raw = data.get("priority", "Medium")
        priority = str(priority_raw).title() if priority_raw is not None else "Medium"
        if priority not in ALLOWED_PRIORITIES:
            raise ValueError("Unsupported priority.")

        # Validate status (Pending, Done, Snoozed)
        status_raw = data.get("status", "Pending")
        status = str(status_raw).title() if status_raw is not None else "Pending"
        if status not in ALLOWED_STATUSES:
            raise ValueError("Unsupported status.")

        # Parse snooze date if provided
        snoozed_raw = data.get("snoozed_till")
        try:
            snoozed_till = parse_date(snoozed_raw)
        except ValueError as error:
            raise ValueError(str(error))

        # Validate snooze logic
        if status == "Snoozed":
            if snoozed_till is None:
                raise ValueError("Snoozed follow-ups need a snooze-until date.")
            if snoozed_till < date.today():
                raise ValueError("Snoozed follow-ups need a snooze-until date that is today or later.")
            # Ensure due date is not before snooze date
            if due_date and due_date < snoozed_till:
                due_date = snoozed_till
        elif snoozed_till is not None:
            # Clear snooze date if status is not Snoozed
            snoozed_till = None

        # Get optional email notification address
        notify_email = data.get("notify_email")

        # Build the fields dictionary
        fields: Dict[str, Any] = {
            "source": source,
            "contact": contact,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "status": status,
            "snoozed_till": snoozed_till if status == "Snoozed" else None,
        }

        if isinstance(notify_email, str) and notify_email.strip():
            fields["notify_email"] = notify_email.strip()

        return fields

    def apply_status_update(followup: "FollowUp", payload: Mapping[str, Any]) -> None:
        """
        Update the status of a follow-up (Pending/Done/Snoozed) with validation.
        
        Args:
            followup: The FollowUp instance to update
            payload: Dictionary containing status and optional date updates
            
        Raises:
            ValueError: If the status or dates are invalid
        """
        # Extract and validate the new status
        raw_status = payload.get("status")
        if raw_status is None:
            raise ValueError("Status is required.")
        status = str(raw_status).title()
        if status not in ALLOWED_STATUSES:
            raise ValueError("Unsupported status.")

        # Parse optional due date update
        try:
            new_due_date = parse_date(payload.get("due_date"))
        except ValueError as error:
            raise ValueError(str(error))

        # Parse optional snooze date
        try:
            snooze_date = parse_date(payload.get("snoozed_till"))
        except ValueError as error:
            raise ValueError(str(error))

        today = date.today()

        if status == "Snoozed":
            if snooze_date is None:
                raise ValueError("Snoozing requires a target date.")
            if snooze_date < today:
                raise ValueError("Snoozing requires a target date that is today or later.")
            effective_due = new_due_date or followup.due_date
            if (
                followup.status == "Pending"
                and effective_due is not None
                and effective_due < today
            ):
                raise ValueError("Cannot snooze an overdue follow-up. Update the due date first.")

        previous_status = followup.status

        followup.status = status
        followup.snoozed_till = snooze_date if status == "Snoozed" else None

        due_changed = False
        if new_due_date:
            if followup.due_date != new_due_date:
                due_changed = True
            followup.due_date = new_due_date
        elif status == "Snoozed" and snooze_date:
            if followup.due_date != snooze_date:
                due_changed = True
            # Keep the card aligned with the snoozed target when a new due date is not specified.
            followup.due_date = snooze_date

        if due_changed:
            # Reset daily reminder tracking when due date changes
            followup.due_notification_sent = False
            followup.last_notification_at = None

        if status == "Done":
            followup.completed_at = datetime.now(timezone.utc)
            followup.due_notification_sent = True
            followup.snooze_notification_sent = True
            followup.last_notification_at = None  # Reset for potential future use
        elif status == "Pending":
            followup.completed_at = None
            if previous_status != "Pending":
                # Reset daily reminder tracking when moving back to Pending
                followup.due_notification_sent = False
                followup.last_notification_at = None
        elif status == "Snoozed":
            followup.completed_at = None
            followup.snooze_notification_sent = False
            # Keep last_notification_at to track when we last sent reminders

    def get_followup_or_404(followup_id: int) -> "FollowUp":
        """
        Get a follow-up by ID or return a 404 error if not found.
        
        Args:
            followup_id: The ID of the follow-up to retrieve
            
        Returns:
            FollowUp instance
            
        Raises:
            404 error if not found
        """
        instance = db.session.get(FollowUp, followup_id)
        if instance is None:
            abort(404)
        return instance

    def json_error(message: str, status_code: int = 400):
        """
        Return a standardized JSON error response.
        
        Args:
            message: Error message to return
            status_code: HTTP status code (default 400)
            
        Returns:
            JSON response with error
        """
        return jsonify({"success": False, "error": message}), status_code

    def resolve_recipient(value: Optional[str], default_key: str) -> Optional[str]:
        """
        Get the recipient email, using a default from config if not provided.
        
        Args:
            value: Email address provided by user
            default_key: Config key for default email
            
        Returns:
            Email address or None
        """
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                return trimmed
        default_value = app.config.get(default_key)
        if isinstance(default_value, str):
            trimmed = default_value.strip()
            return trimmed or None
        return None

    def build_notification_contents(followup: "FollowUp", reason: str) -> Dict[str, str]:
        """
        Build the notification message content based on the follow-up and reason.
        Creates escalating urgency messages based on how soon the task is due.
        
        Args:
            followup: The FollowUp instance
            reason: Why the notification is being sent (e.g., "due_soon", "snooze_released")
            
        Returns:
            Dictionary with "title" and "message" keys
        """
        due_text = followup.due_date.strftime("%b %d, %Y") if followup.due_date else "unspecified"
        base = f"Follow-up '{followup.description}' for {followup.contact}"
        
        if reason == "due_soon":
            # Calculate days until due for escalating urgency
            if followup.due_date:
                today = date.today()
                days_until_due = (followup.due_date - today).days
                
                if days_until_due > 0:
                    title = f"Follow-up due in {days_until_due} day{'s' if days_until_due > 1 else ''}"
                    urgency = "📅" if days_until_due > 1 else "⚠️"
                    message = (
                        f"{urgency} {base} is due in {days_until_due} day{'s' if days_until_due > 1 else ''} "
                        f"(on {due_text}). Source: {followup.source}. Priority: {followup.priority}."
                    )
                elif days_until_due == 0:
                    title = "Follow-up due TODAY!"
                    message = (
                        f"🔥 {base} is due TODAY ({due_text}). "
                        f"Source: {followup.source}. Priority: {followup.priority}. Take action now!"
                    )
                else:  # overdue
                    days_overdue = abs(days_until_due)
                    title = f"Follow-up OVERDUE by {days_overdue} day{'s' if days_overdue > 1 else ''}!"
                    message = (
                        f"🚨 URGENT: {base} is {days_overdue} day{'s' if days_overdue > 1 else ''} overdue! "
                        f"Was due on {due_text}. Source: {followup.source}. Priority: {followup.priority}. "
                        f"Please take immediate action!"
                    )
            else:
                title = "Follow-up due soon"
                message = f"📅 {base}. Source: {followup.source}. Priority: {followup.priority}."
                
        elif reason == "snooze_released":
            title = "Snoozed follow-up is back"
            message = (
                f"⏰ {base} is ready for action today. Original due date: {due_text}. "
                f"Source: {followup.source}. Priority: {followup.priority}."
            )
        else:
            title = reason
            message = base
            
        return {"title": title, "message": message}

    def is_dry_run() -> bool:
        """
        Check if we're in dry-run mode (notifications logged but not sent).
        Useful for testing without sending real emails.
        
        Returns:
            True if in dry-run mode, False otherwise
        """
        return bool(app.config.get("NOTIFICATION_DRY_RUN"))

    def send_email_notification(recipient: str, subject: str, body: str) -> bool:
        """
        Send an email notification using Resend API (primary) or SMTP (fallback).
        
        Args:
            recipient: Email address to send to
            subject: Email subject line
            body: Email message content (plain text)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if is_dry_run():
            app.logger.debug("Dry run: skipping email send to %s", recipient)
            return True

        # Get sender email (fixed to project14281428@gmail.com)
        sender = app.config.get("EMAIL_FROM", "project14281428@gmail.com")
        
        # Try Resend API first
        resend_api_key = app.config.get("RESEND_API_KEY")
        if resend_api_key and resend_api_key.strip():
            try:
                resend.api_key = resend_api_key
                
                # Convert plain text body to HTML for better formatting
                html_body = body.replace('\n', '<br>')
                
                # Use Resend's verified domain (onboarding@resend.dev)
                # Custom domains require verification at https://resend.com/domains
                resend_from = "FollowUp Boss <onboarding@resend.dev>"
                
                result = resend.Emails.send({
                    "from": resend_from,
                    "to": recipient,
                    "subject": subject,
                    "html": f"<div style='font-family: Arial, sans-serif;'>{html_body}</div>",
                    "reply_to": sender  # User can reply to your Gmail
                })
                
                app.logger.info("Email sent via Resend API to %s (ID: %s)", recipient, result.get('id', 'unknown'))
                return True
                
            except Exception as exc:
                app.logger.warning("Resend API failed for %s: %s. Trying SMTP fallback...", recipient, exc)
        
        # Fallback to SMTP if Resend fails or not configured
        host = app.config.get("SMTP_HOST")
        smtp_sender = app.config.get("SMTP_FROM_EMAIL", sender)
        
        if not host:
            app.logger.debug("No email service configured (Resend or SMTP); email suppressed")
            return False

        port = int(app.config.get("SMTP_PORT", 587) or 587)
        username = app.config.get("SMTP_USERNAME")
        password = app.config.get("SMTP_PASSWORD")
        use_tls = bool(app.config.get("SMTP_USE_TLS", True))
        use_ssl = bool(app.config.get("SMTP_USE_SSL", False))

        message = EmailMessage()
        message["From"] = smtp_sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        try:
            # Use SMTP_SSL for port 465, regular SMTP for port 587
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
                    if username and password:
                        smtp.login(username, password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=10) as smtp:
                    if use_tls:
                        smtp.starttls()
                    if username and password:
                        smtp.login(username, password)
                    smtp.send_message(message)
            app.logger.info("Email notification sent via SMTP to %s", recipient)
            return True
        except Exception as exc:  # pragma: no cover - network dependent
            app.logger.warning("SMTP send failed for %s: %s", recipient, exc)
            return False

    # WhatsApp functionality removed - email only

    def dispatch_notifications(followup: "FollowUp", reason: str) -> bool:
        """
        Dispatch email notifications for a follow-up and log them.
        
        Args:
            followup: The FollowUp instance to send notifications for
            reason: Why the notification is being sent
            
        Returns:
            True if notification was sent, False otherwise
        """
        # Build the notification message
        contents = build_notification_contents(followup, reason)
        email_recipient = resolve_recipient(followup.notify_email, "DEFAULT_NOTIFY_EMAIL")

        sent = False
        now_ts = datetime.now(timezone.utc)

        # Send email notification if recipient exists
        if email_recipient:
            db.session.add(
                NotificationLog(
                    followup_id=followup.id,
                    channel="email",
                    recipient=email_recipient,
                    reason=reason,
                    message=f"{contents['title']}: {contents['message']}",
                )
            )
            if send_email_notification(email_recipient, contents["title"], contents["message"]):
                sent = True

        if sent:
            followup.last_notification_at = now_ts
            app.logger.info(
                "Automated %s notification queued for follow-up %s", reason, followup.id
            )
        else:
            app.logger.debug(
                "Notification for follow-up %s reason %s logged but not dispatched (check config)",
                followup.id,
                reason,
            )

        return sent

    def send_due_notification(followup: "FollowUp") -> bool:
        """
        Send a "due soon" notification for a follow-up.
        Allows daily reminders (doesn't permanently mark as sent).
        
        Args:
            followup: The FollowUp instance
            
        Returns:
            True if sent successfully
        """
        if dispatch_notifications(followup, "due_soon"):
            return True
        return False

    def send_snooze_notification(followup: "FollowUp") -> bool:
        """
        Send a notification when a snoozed follow-up is released back to Pending.
        
        Args:
            followup: The FollowUp instance
            
        Returns:
            True if sent successfully
        """
        if dispatch_notifications(followup, "snooze_released"):
            followup.snooze_notification_sent = True
            return True
        return False

    def should_send_daily_reminder(followup: "FollowUp") -> bool:
        """
        Determine if we should send a daily reminder for this follow-up.
        Sends reminders if:
        - Status is Pending
        - Due date is within lookahead window OR up to 7 days overdue
        - No reminder sent today yet
        
        Args:
            followup: The FollowUp instance to check
            
        Returns:
            True if we should send a reminder
        """
        """Check if we should send a daily reminder for this follow-up"""
        if followup.status != "Pending" or not followup.due_date:
            return False
            
        today = date.today()
        lookahead_days = int(app.config.get("AUTOMATION_LOOKAHEAD_DAYS", 3))
        
        # Calculate days until due (negative if overdue)
        days_until_due = (followup.due_date - today).days
        
        # Send reminders if within lookahead window OR up to 7 days overdue
        in_reminder_window = days_until_due <= lookahead_days and days_until_due >= -7
        
        if not in_reminder_window:
            return False
            
        # Check if we already sent a reminder today
        if followup.last_notification_at:
            last_notification_date = followup.last_notification_at.date()
            if last_notification_date == today:
                return False  # Already sent today
                
        return True

    def evaluate_followup_for_notifications(followup: "FollowUp") -> None:
        """
        Check if a follow-up needs notifications and send them if appropriate.
        
        Args:
            followup: The FollowUp instance to evaluate
        """
        if should_send_daily_reminder(followup):
            send_due_notification(followup)

    # =========================================================================
    # AUTOMATION FUNCTIONS - Background processes for automated reminders
    # =========================================================================

    def process_automation_cycle() -> None:
        """
        Main automation cycle that runs periodically (every 15 minutes by default).
        
        This function:
        1. Sends daily reminders for pending follow-ups that are due soon or overdue
        2. Releases snoozed follow-ups back to Pending when their snooze date arrives
        3. Sends notifications for newly released follow-ups
        """
        today = date.today()
        lookahead_days = int(app.config.get("AUTOMATION_LOOKAHEAD_DAYS", 3))

        # Find all pending follow-ups that need daily reminders
        pending_for_reminders = (
            FollowUp.query.filter(
                FollowUp.status == "Pending",
                FollowUp.due_date.isnot(None),
                # Include overdue items up to 7 days
                FollowUp.due_date >= today - timedelta(days=7),
                FollowUp.due_date <= today + timedelta(days=lookahead_days)
            ).all()
        )

        # Send daily reminders for eligible follow-ups
        for followup in pending_for_reminders:
            if should_send_daily_reminder(followup):
                send_due_notification(followup)

        # Handle snoozed items that are ready to be released
        snoozed_ready = (
            FollowUp.query.filter(
                FollowUp.status == "Snoozed",
                FollowUp.snoozed_till.isnot(None),
                FollowUp.snoozed_till <= today,
            ).all()
        )

        for followup in snoozed_ready:
            followup.status = "Pending"
            followup.snoozed_till = None
            # Reset notification tracking so it can start daily reminders
            followup.due_notification_sent = False
            followup.last_notification_at = None
            send_snooze_notification(followup)
            # Check if it needs immediate daily reminder after being released
            if should_send_daily_reminder(followup):
                send_due_notification(followup)

        if pending_for_reminders or snoozed_ready:
            db.session.commit()

    def run_automation_cycle() -> None:
        """
        Wrapper function to manually trigger an automation cycle.
        Used for testing and manual execution.
        """
        process_automation_cycle()

    def start_automation_scheduler() -> None:
        """
        Start the background scheduler that runs automation cycles periodically.
        The scheduler runs every 15 minutes by default.
        """
        # Prevent multiple scheduler instances in multi-worker environments
        if hasattr(app, 'scheduler') and app.scheduler.running:
            app.logger.info("Scheduler already running, skipping initialization")
            return
            
        scheduler = BackgroundScheduler(daemon=True)

        def job_wrapper() -> None:
            """Wrapper to run automation within Flask app context"""
            with app.app_context():
                process_automation_cycle()

        # Schedule the automation job
        interval_minutes = int(app.config.get("AUTOMATION_INTERVAL_MINUTES", 15))
        scheduler.add_job(job_wrapper, "interval", minutes=interval_minutes, id="followup-automation")
        
        # Run once immediately on startup
        try:
            with app.app_context():
                app.logger.info("Running initial automation cycle on startup...")
                process_automation_cycle()
        except Exception as e:
            app.logger.error(f"Error in initial automation cycle: {e}")
        
        scheduler.start()
        app.logger.info("Automation scheduler started (interval=%s minutes)", interval_minutes)
        setattr(app, "scheduler", scheduler)

    # =========================================================================
    # WEB ROUTES - HTML pages for the user interface
    # =========================================================================

    @app.route("/")
    def index():
        """
        Main dashboard page showing all follow-ups organized in a Kanban board.
        Displays three columns: Pending, Snoozed, and Done.
        """
        today = date.today()

        # Get all pending follow-ups (sorted by due date, then priority)
        pending_items = (
            FollowUp.query.filter_by(status="Pending")
            .order_by(FollowUp.due_date.asc(), FollowUp.priority.desc())
            .all()
        )
        
        # Get all snoozed follow-ups (sorted by snooze date)
        snoozed_items = (
            FollowUp.query.filter_by(status="Snoozed")
            .order_by(FollowUp.snoozed_till.asc())
            .all()
        )
        
        # Get all completed follow-ups (sorted by completion date)
        done_items = (
            FollowUp.query.filter_by(status="Done")
            .order_by(FollowUp.completed_at.desc().nullslast(), FollowUp.updated_at.desc())
            .all()
        )

        # Count how many tasks are due today
        due_today_count = (
            FollowUp.query.filter_by(status="Pending")
            .filter(FollowUp.due_date == today)
            .count()
        )

        return render_template(
            "index.html",
            today=today,
            pending_items=pending_items,
            snoozed_items=snoozed_items,
            done_items=done_items,
            due_today_count=due_today_count,
        )

    @app.post("/add")
    def add_followup():
        """
        Create a new follow-up from the web form.
        Redirects back to the dashboard after creation.
        """
        try:
            # Extract and validate form data
            fields = extract_followup_fields(request.form)
        except ValueError as error:
            flash(str(error))
            return redirect(url_for("index"))

        # Create the new follow-up
        followup = FollowUp(**fields)
        if followup.status == "Done":
            followup.completed_at = datetime.now(timezone.utc)

        db.session.add(followup)
        db.session.flush()

        # Check if notifications should be sent
        if followup.status == "Pending":
            evaluate_followup_for_notifications(followup)

        db.session.commit()

        # Run automation cycle to process any pending notifications
        if followup.status == "Pending" or followup.status == "Snoozed":
            process_automation_cycle()

        return redirect(url_for("index"))

    @app.post("/update/<int:followup_id>")
    def update_followup(followup_id: int):
        """
        Update the status of a follow-up (move between Pending/Done/Snoozed).
        Called when dragging cards between columns or clicking status buttons.
        """
        payload = request.get_json(silent=True) or request.form
        followup = get_followup_or_404(followup_id)

        try:
            # Apply the status update with validation
            apply_status_update(followup, payload)
        except ValueError as error:
            return json_error(str(error))

        # Check if notifications should be sent
        evaluate_followup_for_notifications(followup)

        db.session.commit()
        
        # Run automation cycle if needed
        if followup.status in {"Pending", "Snoozed"}:
            process_automation_cycle()

        return jsonify({"success": True})

    # =========================================================================
    # API ROUTES - JSON endpoints for programmatic access
    # =========================================================================

    @app.get("/api/followups")
    def api_list_followups():
        """
        API endpoint to get all follow-ups, optionally filtered by status.
        
        Query parameters:
            status: Filter by status (Pending, Done, or Snoozed)
        
        Returns:
            JSON array of follow-up objects
        """
        status_filter = request.args.get("status")
        query = FollowUp.query
        
        # Apply status filter if provided
        if status_filter:
            status_normalized = status_filter.title()
            if status_normalized not in ALLOWED_STATUSES:
                return json_error("Unsupported status filter.")
            query = query.filter_by(status=status_normalized)

        items = query.order_by(FollowUp.due_date.asc()).all()
        return jsonify({"data": [item.to_dict() for item in items]})

    @app.get("/api/followups/<int:followup_id>")
    def api_get_followup(followup_id: int):
        """
        API endpoint to get a single follow-up by ID.
        
        Returns:
            JSON object with follow-up details
        """
        followup = get_followup_or_404(followup_id)
        return jsonify({"data": followup.to_dict()})

    @app.post("/api/followups")
    def api_create_followup():
        """
        API endpoint to create a new follow-up via JSON.
        
        Request body:
            JSON object with follow-up fields (source, contact, description, due_date, etc.)
        
        Returns:
            JSON object with created follow-up details and Location header
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return json_error("JSON body required.")

        try:
            fields = extract_followup_fields(payload)
        except ValueError as error:
            return json_error(str(error))

        followup = FollowUp(**fields)
        if followup.status == "Done":
            followup.completed_at = datetime.now(timezone.utc)

        db.session.add(followup)
        db.session.flush()

        if followup.status == "Pending":
            evaluate_followup_for_notifications(followup)

        db.session.commit()

        if followup.status in {"Pending", "Snoozed"}:
            process_automation_cycle()

        response = jsonify({"data": followup.to_dict()})
        response.status_code = 201
        response.headers["Location"] = url_for("api_get_followup", followup_id=followup.id)
        return response

    @app.patch("/api/followups/<int:followup_id>")
    def api_update_followup(followup_id: int):
        """
        API endpoint to update an existing follow-up via JSON.
        Used by the Edit modal in the UI.
        
        Request body:
            JSON object with fields to update (can be partial)
        
        Returns:
            JSON object with updated follow-up details
        """
        try:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"success": False, "error": "JSON body required."}), 400

            followup = get_followup_or_404(followup_id)

            # Update individual fields if provided
            if "source" in payload:
                followup.source = payload["source"]
            if "contact" in payload:
                followup.contact = payload["contact"]
            if "description" in payload:
                followup.description = payload["description"]
            if "due_date" in payload:
                try:
                    followup.due_date = parse_date(payload["due_date"])
                except ValueError as error:
                    return jsonify({"success": False, "error": str(error)}), 400
            if "priority" in payload:
                priority = str(payload["priority"]).title()
                if priority not in ALLOWED_PRIORITIES:
                    return jsonify({"success": False, "error": "Unsupported priority."}), 400
                followup.priority = priority
            if "notify_email" in payload:
                followup.notify_email = payload["notify_email"]

            # Handle status updates (with special validation)
            if "status" in payload:
                try:
                    apply_status_update(followup, payload)
                except ValueError as error:
                    return jsonify({"success": False, "error": str(error)}), 400

            # Check if notifications should be sent
            evaluate_followup_for_notifications(followup)

            db.session.commit()
            
            # Run automation cycle if needed
            if followup.status in {"Pending", "Snoozed"}:
                process_automation_cycle()

            return jsonify({"success": True, "data": followup.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)}), 500

    @app.delete("/api/followups/<int:followup_id>")
    def api_delete_followup(followup_id: int):
        """
        API endpoint to delete a follow-up.
        Used by the Delete confirmation modal in the UI.
        
        Returns:
            JSON confirmation message
        """
        try:
            followup = get_followup_or_404(followup_id)
            
            # Delete associated notification logs first (cascade delete)
            db.session.query(NotificationLog).filter_by(followup_id=followup_id).delete()
            
            # Delete the follow-up
            db.session.delete(followup)
            db.session.commit()
            
            return jsonify({"success": True, "message": "Follow-up deleted successfully"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)}), 500

    # =========================================================================
    # ADMIN/TEST ENDPOINTS - Trigger notifications manually for testing
    # =========================================================================
    
    @app.route("/api/trigger-notifications", methods=["POST"])
    def trigger_notifications():
        """
        Manually trigger the notification cycle (useful for testing).
        This endpoint runs the automation cycle immediately.
        """
        try:
            app.logger.info("Manual notification trigger requested")
            process_automation_cycle()
            return jsonify({
                "success": True, 
                "message": "Notification cycle completed successfully"
            })
        except Exception as e:
            app.logger.error(f"Error in manual notification trigger: {e}")
            return jsonify({
                "success": False, 
                "error": str(e)
            }), 500
    
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint - shows database type, config status, and follow-up count.
        Useful for debugging deployment issues.
        """
        try:
            # Get database type
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')
            if 'postgresql' in db_uri:
                db_type = "PostgreSQL ✅ (Persistent)"
            elif 'sqlite' in db_uri:
                db_type = "SQLite ⚠️ (Temporary - data will be lost!)"
            else:
                db_type = "Unknown"
            
            # Count follow-ups
            total_followups = FollowUp.query.count()
            pending_count = FollowUp.query.filter_by(status='Pending').count()
            
            # Check scheduler
            scheduler_running = hasattr(app, 'scheduler') and app.scheduler.running
            
            return jsonify({
                "status": "healthy",
                "database": {
                    "type": db_type,
                    "uri_prefix": db_uri.split('@')[0].split('://')[0] if '://' in db_uri else 'unknown'
                },
                "data": {
                    "total_followups": total_followups,
                    "pending_followups": pending_count
                },
                "scheduler": {
                    "running": scheduler_running
                },
                "config": {
                    "resend_configured": bool(app.config.get('RESEND_API_KEY')),
                    "smtp_configured": bool(app.config.get('SMTP_USERNAME')),
                    "email_from": app.config.get('EMAIL_FROM', 'Not set'),
                    "secret_key_set": app.config.get('SECRET_KEY') != 'followup-boss-secret-change-in-production'
                }
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500

    # =========================================================================
    # ERROR HANDLERS - Handle 404, 405, and 500 errors gracefully
    # =========================================================================

    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors - return JSON for API calls, simple message for web pages"""
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "Resource not found"}), 404
        # For favicon and other missing resources, just return a simple 404
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        """Handle 405 errors - return JSON"""
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "Method not allowed"}), 405
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors - return JSON with error details"""
        app.logger.error(f"Internal server error: {error}")
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "Internal server error"}), 500
        return jsonify({"error": "Internal server error"}), 500

    # Make automation cycle accessible for testing
    setattr(app, "run_automation_cycle", process_automation_cycle)

    # Start the background scheduler (unless in testing mode)
    if not app.config.get("TESTING"):
        start_automation_scheduler()

    return app


# =============================================================================
# APPLICATION INITIALIZATION
# =============================================================================

# Create the Flask application instance
app = create_app()

# Run the application (only when executed directly, not when imported)
if __name__ == "__main__":
    app.run(debug=True)
