# FlowDeck - Employee Management System

A comprehensive Flask-based web application for managing employees, tasks, meetings, and workflows in an organization.

## 🚀 Features

### Two-Level Authentication
- **Admin Level**: Full control over the organization
  - Create and manage employees
  - Assign job levels (Intern, Developer, Senior Developer, Team Lead, Manager)
  - View activity logs and statistics
  - Auto-generated login credentials with popup display

- **Employee Level**: Access to assigned tasks and meetings
  - View and update personal tasks
  - Participate in meetings
  - Track work progress on Kanban board

### Core Features

#### 📅 Meetings Management
- Schedule meetings with title, description, date/time, and location
- Assign multiple participants
- View meeting details and participant lists
- Track meeting status

#### 📋 Tasks Management
- Create tasks with priority levels (Low, Medium, High, Urgent)
- Assign tasks to specific employees
- Set due dates and track progress
- Update task status (To Do, In Progress, Review, Done)

#### 📊 Kanban Board
- Visual task management with drag-and-drop functionality
- Four columns: To Do, In Progress, Review, Done
- Real-time task status updates
- Color-coded priority indicators

#### 👑 Admin Console
- Employee management dashboard
- Create employees with auto-generated credentials
- Deactivate employees
- View organization statistics

## 🗄️ Database Design

The application uses **SQLite3** with **6 tables** and includes **6 triggers** for data integrity:

### Tables
1. **organizations** - Organization information
2. **users** - Employees and admins with authentication
3. **meetings** - Meeting schedules and details
4. **meeting_participants** - Meeting attendee tracking
5. **tasks** - Task management with assignments
6. **activity_log** - Audit trail for all actions

### SQLite Triggers
1. **update_last_login** - Tracks user login timestamps
2. **log_user_creation** - Logs new user creation
3. **log_user_deletion** - Logs user deletion
4. **update_task_timestamp** - Updates task modification time
5. **log_task_status_change** - Logs task status changes
6. **prevent_last_admin_deletion** - Prevents deleting the last admin

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone or navigate to the project directory**
   ```bash
   cd flowdeck-webapp
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment**
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your secret key (or use the default for development)

6. **Initialize the database**
   ```bash
   python database.py
   ```

7. **Run the application**
   ```bash
   python app.py
   ```

8. **Access the application**
   
   You'll see output like this:
   ```
   ============================================================
   🚀 FlowDeck Server Started!
   ============================================================
   📍 Local Access:    http://127.0.0.1:5010
   🌐 Network Access:  http://192.168.1.100:5010
   ============================================================
   💡 Other devices on your network can access using the Network URL
   🛑 Press CTRL+C to quit
   ============================================================
   ```
   
   **Access Options:**
   - **On the same computer**: Use `http://localhost:5010` or `http://127.0.0.1:5010`
   - **From other devices on the same network**: Use the Network URL (e.g., `http://192.168.1.100:5010`)
   
   **Important Network Notes:**
   - All devices must be connected to the **same Wi-Fi network**
   - Make sure your **firewall** allows connections on port 5010 (or whichever port is shown)
   - On macOS, you may need to allow Python in System Preferences → Security & Privacy → Firewall
   - The IP address shown is your computer's local network IP
   
   **Port Notes:**
   - The app automatically uses port **5010** by default
   - If 5010 is busy, it will try 5011, 5012, etc. up to 5019
   - The actual port will be displayed in the startup message

## 🔐 Default Login Credentials

After initialization, use these credentials to login:

- **Login ID**: `admin`
- **Password**: `admin123`

**⚠️ Important**: Change the default admin password in production!

## 📱 Usage Guide

### For Admins

1. **Login** with admin credentials
2. Navigate to **Admin Console**
3. Click **"+ Create Employee"**
4. Fill in employee details:
   - Full Name
   - Email
   - Job Level
5. A popup will display the auto-generated credentials
6. **Save the credentials securely** - they won't be shown again!

### For Employees

1. **Login** with provided credentials
2. View your **Dashboard** for overview
3. Access **Tasks** to see assigned work
4. Use **Kanban Board** for visual task management (drag & drop)
5. Check **Meetings** for scheduled events

### Creating Tasks

1. Navigate to **Tasks** or **Kanban**
2. Click **"+ Create Task"**
3. Fill in:
   - Title and Description
   - Priority (Low/Medium/High/Urgent)
   - Assign to employee
   - Set due date
4. Click **Create Task**

### Scheduling Meetings

1. Navigate to **Meetings**
2. Click **"+ Schedule Meeting"**
3. Fill in:
   - Title and Description
   - Date & Time
   - Duration
   - Location
   - Select Participants
4. Click **Schedule Meeting**

### Using Kanban Board

1. Navigate to **Kanban**
2. **Drag and drop** task cards between columns
3. Tasks automatically update status
4. View tasks by priority (colored borders):
   - 🟢 Green = Low
   - 🟡 Yellow = Medium
   - 🟠 Orange = High
   - 🔴 Red = Urgent

## 🔒 Security Features

- Password hashing using Werkzeug
- Flask-Login for session management
- Role-based access control (Admin vs Employee)
- CSRF protection
- SQL injection prevention
- Activity logging for audit trails
- Prevents deletion of last admin

## 🛠️ Technology Stack

- **Backend**: Flask 3.0
- **Database**: SQLite3 with triggers
- **Authentication**: Flask-Login
- **Security**: Werkzeug password hashing
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Design**: Custom responsive CSS with gradient themes

## 📊 Database Triggers & Integrity

The application maintains data integrity through:

1. **Foreign Key Constraints** - Cascade deletions and proper relationships
2. **Check Constraints** - Valid role, status, and priority values
3. **Unique Constraints** - Prevent duplicate login IDs and emails
4. **Triggers** - Automatic logging and timestamp updates
5. **Activity Logging** - Complete audit trail of all actions

## 🎨 Design Features

- Modern gradient theme (Purple/Blue)
- Responsive design for mobile and desktop
- Intuitive card-based UI
- Modal dialogs for forms
- Toast notifications for actions
- Smooth animations and transitions

## 📝 Project Structure

```
flowdeck-webapp/
├── app.py                 # Main Flask application
├── database.py            # Database schema and initialization
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── .gitignore            # Git ignore rules
├── templates/            # HTML templates
│   ├── base.html         # Base template with navbar
│   ├── login.html        # Login page
│   ├── dashboard.html    # Dashboard page
│   ├── admin_console.html # Admin management
│   ├── meetings.html     # Meetings list
│   ├── meeting_detail.html # Meeting details
│   ├── tasks.html        # Tasks list
│   └── kanban.html       # Kanban board
└── flowdeck.db           # SQLite database (created after init)
```

## 🚀 Future Enhancements

- Email notifications for task assignments
- Calendar integration
- File attachments for tasks
- Team chat functionality
- Advanced reporting and analytics
- Multi-organization support
- API endpoints for mobile apps

## 📄 License

This project is open source and available for educational purposes.

## 👥 Support

For issues or questions, please contact your system administrator.

---

**Built with ❤️ using Flask and SQLite**
