# FollowUp Boss 🚀

**A modern dashboard for managing follow-up tasks** with automated email and WhatsApp notifications.
## ✨ Features

- **Kanban Board** - Organize tasks in Pending, Snoozed, and Done columns
- **Smart Notifications** - Automated email and WhatsApp reminders
- **Modern UI** - Glassmorphism design with responsive layout
- **Priority Management** - Color-coded task prioritization
- **Multiple Sources** - Track follow-ups from calls, emails, meetings
- **RESTful API** - Complete CRUD operations with JSON endpoints

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Git (optional)

### Installation
```bash
# Clone or download the project
cd clapgrow

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run the application
flask --app app run
```

### First Run
1. Open http://127.0.0.1:5000 in your browser
2. Add your first follow-up using the form
3. Watch it appear in the Kanban board
4. Use action buttons to change status (Mark Done, Snooze, etc.)

## � How It Works

### Task Workflow
- **Add Follow-ups** - Create tasks with source, contact, description, due date, and priority
- **Kanban Board** - View tasks in three columns: Pending (orange), Snoozed (blue), Done (green)
- **Status Changes** - Use buttons to mark done, snooze for later, or reschedule
- **Visual Indicators** - Overdue items show red warnings and "OVERDUE" chips

### Automated Notifications
- **3-Day Window** - Reminders start 3 days before due date
- **Daily Escalation** - "Due in 2 days" → "Due tomorrow" → "Due TODAY!" → "OVERDUE!"
- **Smart Timing** - Maximum one notification per day per follow-up
- **Multiple Channels** - Email (SMTP) and WhatsApp (Twilio) support

### API Endpoints
```http
GET    /api/followups              # List all follow-ups
POST   /api/followups              # Create new follow-up
GET    /api/followups/<id>         # Get specific follow-up
PATCH  /api/followups/<id>         # Update follow-up
DELETE /api/followups/<id>         # Delete follow-up
```

## ⚙️ Configuration

### Basic Setup (Works without configuration)
The app runs locally with SQLite - no additional setup required for basic usage.

# 🚀 How to Enable Real Notifications

## Step 1: Get Your Credentials

### For Email (Gmail Example):
1. Go to your Google Account settings
2. Enable 2-factor authentication
3. Generate an "App Password" for FollowUp Boss
4. Use this app password (not your regular password)

### For WhatsApp (Twilio)(optional):
1. Sign up at https://www.twilio.com
2. Get your Account SID and Auth Token from the dashboard
3. Set up a WhatsApp Business number through Twilio

## Step 2: Update Your .env File

Edit the `.env` file in your project folder with your real values:
```
# Replace these with your actual credentials:
SMTP_USERNAME=your-real-email@gmail.com
SMTP_PASSWORD=your-app-password-from-google
SMTP_FROM_EMAIL=your-email@gmail.com

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-real-auth-token
TWILIO_FROM_WHATSAPP=whatsapp:+14155238886

# Set to false for real notifications
NOTIFICATION_DRY_RUN=false
```

## Step 3: Restart Your Server

```powershell
# Stop the current server (Ctrl+C)
# Then restart:
flask --app app run
```

## ✅ That's It!

Your FollowUp Boss will now send real email and WhatsApp notifications when:
- A follow-up is due soon (within 3 days)
- A snoozed follow-up is released back to pending
```

## 🛠 Technology Stack

- **Backend**: Flask 3.0.3, SQLAlchemy 2.0.35, APScheduler 3.10.4
- **Frontend**: Modern CSS3, Vanilla JavaScript, Jinja2 templates
- **Database**: SQLite (embedded, no setup required)
- **Notifications**: SMTP (email), Twilio (WhatsApp)
- **Styling**: Glassmorphism design with Poppins/Inter fonts

## 📱 Features in Detail

### User Interface
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Glassmorphic Cards** - Modern frosted glass effect
- **Smooth Animations** - Hover effects and transitions
- **Progress Bars** - Visual column statistics
- **Modal Dialogs** - Date pickers for snooze/reschedule

### Task Management
- **Multiple Sources** - Phone, Email, Meeting, WhatsApp, SMS, Other
- **Priority Levels** - Low (green), Medium (amber), High (red)
- **Due Date Tracking** - Visual overdue indicators
- **Snooze Function** - Temporarily hide tasks until specified date
- **Quick Actions** - One-click status changes

### Background Processing
- **APScheduler** - Runs notification checks every 15 minutes
- **Automatic Snooze Release** - Moves snoozed items back to pending
- **Delivery Tracking** - Logs all notification attempts
- **Error Handling** - Graceful failure with retry logic

## 🧪 Development

### Running Tests
```bash
# Install pytest (included in requirements.txt)
pip install pytest

# Run tests
pytest
```

### Development Mode
```bash
# Enable debug mode
flask --app app run --debug

# Test notifications without sending
# Set NOTIFICATION_DRY_RUN=True in .env
```

### Database
- **Auto-created** - SQLite database created on first run
- **Tables** - `followup` (main data), `notification_log` (audit trail)
- **Migrations** - Schema updates handled automatically

## 📚 Documentation

- **README.md** - This user guide
- **TECHNICAL_GUIDE.md** - Complete technical documentation
-

## 🎯 Use Cases

- **Sales Teams** - Track customer follow-ups and proposals
- **Customer Support** - Manage pending customer issues
- **Project Management** - Follow up on action items and deadlines
- **Personal Productivity** - Organize personal tasks and reminders
- **Team Coordination** - Shared visibility of pending tasks

## 🚀 Future Enhancements

- **User Authentication** - Multi-user support with role-based access
- **Team Collaboration** - Assign tasks to team members
- **Advanced Filtering** - Search by contact, date range, tags
- **CRM Integration** - Sync with Salesforce, HubSpot, Pipedrive
- **Mobile App** - Native iOS and Android applications

---
**Built with Flask and modern web technologies. Transform your follow-up workflow with FollowUp Boss!**


