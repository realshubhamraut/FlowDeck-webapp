import sqlite3
import secrets
import string
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

# Use instance folder for database
INSTANCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
os.makedirs(INSTANCE_PATH, exist_ok=True)
DATABASE = os.path.join(INSTANCE_PATH, 'flowdeck.db')

def get_db():
    """Get database connection with custom functions (stored procedures)"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    
    # Register custom SQLite functions (equivalent to stored procedures)
    register_custom_functions(conn)
    
    return conn

def register_custom_functions(conn):
    """Register custom SQLite functions (stored procedures equivalent)"""
    
    # Function 1: Calculate overdue days for a task
    def days_overdue(due_date_str):
        if not due_date_str:
            return None
        try:
            from datetime import datetime
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            today = datetime.now()
            if today > due_date:
                return (today - due_date).days
            return 0
        except:
            return None
    
    # Function 2: Get user's full display name with role
    def user_display_name(full_name, role):
        if not full_name:
            return "Unknown"
        role_badge = "👑" if role == 'admin' else "👤"
        return f"{role_badge} {full_name}"
    
    # Function 3: Calculate task completion percentage for a user
    def task_completion_rate(user_id):
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as completed
            FROM tasks 
            WHERE assigned_to = ?
        ''', (user_id,))
        row = cursor.fetchone()
        if row and row[0] > 0:
            return round((row[1] / row[0]) * 100, 2)
        return 0.0
    
    # Function 4: Format meeting duration
    def format_duration(minutes):
        if not minutes:
            return "N/A"
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
    
    # Function 5: Get task urgency score (priority + overdue factor)
    def task_urgency_score(priority, due_date_str):
        priority_scores = {'low': 1, 'medium': 2, 'high': 3, 'urgent': 4}
        base_score = priority_scores.get(priority, 1)
        
        overdue = days_overdue(due_date_str)
        if overdue and overdue > 0:
            return base_score * (1 + overdue * 0.1)
        return base_score
    
    # Function 6: Check if user has admin privileges
    def is_admin(user_id):
        cursor = conn.cursor()
        cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return 1 if (row and row[0] == 'admin') else 0
    
    # Function 7: Count active employees in organization
    def org_employee_count(org_id):
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM users 
            WHERE org_id = ? AND is_active = 1 AND role = 'employee'
        ''', (org_id,))
        return cursor.fetchone()[0]
    
    # Function 8: Get user's pending meeting count
    def pending_meetings(user_id):
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM meeting_participants 
            WHERE user_id = ? AND status = 'pending'
        ''', (user_id,))
        return cursor.fetchone()[0]
    
    # Function 9: Sanitize text for display (remove special chars)
    def sanitize_text(text):
        if not text:
            return ""
        import re
        return re.sub(r'[^\w\s\-.,!?@]', '', text)
    
    # Function 10: Calculate average task completion time for user
    def avg_completion_time(user_id):
        cursor = conn.cursor()
        cursor.execute('''
            SELECT AVG(JULIANDAY(updated_at) - JULIANDAY(created_at)) as avg_days
            FROM tasks 
            WHERE assigned_to = ? AND status = 'done'
        ''', (user_id,))
        row = cursor.fetchone()
        return round(row[0], 1) if (row and row[0]) else 0.0
    
    # Register all functions with SQLite
    conn.create_function("days_overdue", 1, days_overdue)
    conn.create_function("user_display_name", 2, user_display_name)
    conn.create_function("task_completion_rate", 1, task_completion_rate)
    conn.create_function("format_duration", 1, format_duration)
    conn.create_function("task_urgency_score", 2, task_urgency_score)
    conn.create_function("is_admin", 1, is_admin)
    conn.create_function("org_employee_count", 1, org_employee_count)
    conn.create_function("pending_meetings", 1, pending_meetings)
    conn.create_function("sanitize_text", 1, sanitize_text)
    conn.create_function("avg_completion_time", 1, avg_completion_time)

def init_db():
    """Initialize database with tables, triggers, and default admin"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # Table 1: Organizations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table 2: Users (Employees and Admins)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            login_id TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'employee')),
            job_level TEXT CHECK(job_level IN ('intern', 'developer', 'senior_developer', 'team_lead', 'manager', 'admin')),
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
    ''')
    
    # Table 3: Meetings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            meeting_date TIMESTAMP NOT NULL,
            duration_minutes INTEGER DEFAULT 60,
            location TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Table 4: Meeting Participants
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meeting_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'declined')),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(meeting_id, user_id)
        )
    ''')
    
    # Table 5: Tasks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'review', 'done')),
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
            assigned_to INTEGER,
            created_by INTEGER NOT NULL,
            due_date DATE,
            position INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Table 6: Activity Log (for integrity and auditing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')
    
    # TRIGGER 1: Update last_login on successful login
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_last_login
        AFTER UPDATE OF password_hash ON users
        WHEN NEW.id = OLD.id
        BEGIN
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')
    
    # TRIGGER 2: Log user creation
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_user_creation
        AFTER INSERT ON users
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.id, 'CREATE', 'users', NEW.id, 
                    'New user created: ' || NEW.full_name || ' (' || NEW.role || ')');
        END
    ''')
    
    # TRIGGER 3: Log user deletion
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_user_deletion
        BEFORE DELETE ON users
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (OLD.id, 'DELETE', 'users', OLD.id, 
                    'User deleted: ' || OLD.full_name);
        END
    ''')
    
    # TRIGGER 4: Update task updated_at timestamp
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_task_timestamp
        AFTER UPDATE ON tasks
        BEGIN
            UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')
    
    # TRIGGER 5: Log task status changes
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_task_status_change
        AFTER UPDATE OF status ON tasks
        WHEN NEW.status != OLD.status
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.assigned_to, 'UPDATE', 'tasks', NEW.id, 
                    'Task status changed from ' || OLD.status || ' to ' || NEW.status);
        END
    ''')
    
    # TRIGGER 6: Prevent deletion of last admin
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS prevent_last_admin_deletion
        BEFORE DELETE ON users
        WHEN OLD.role = 'admin'
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(*) FROM users WHERE role = 'admin' AND org_id = OLD.org_id) <= 1
                THEN RAISE(ABORT, 'Cannot delete the last admin of the organization')
            END;
        END
    ''')
    
    # TRIGGER 7: Log meeting creation
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_meeting_creation
        AFTER INSERT ON meetings
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.created_by, 'CREATE', 'meetings', NEW.id, 
                    'Meeting created: ' || NEW.title || ' on ' || NEW.meeting_date);
        END
    ''')
    
    # TRIGGER 8: Log meeting deletion
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_meeting_deletion
        BEFORE DELETE ON meetings
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (OLD.created_by, 'DELETE', 'meetings', OLD.id, 
                    'Meeting deleted: ' || OLD.title);
        END
    ''')
    
    # TRIGGER 9: Log task creation
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_task_creation
        AFTER INSERT ON tasks
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.created_by, 'CREATE', 'tasks', NEW.id, 
                    'Task created: ' || NEW.title || ' assigned to user ' || COALESCE(NEW.assigned_to, 0));
        END
    ''')
    
    # TRIGGER 10: Log task deletion
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_task_deletion
        BEFORE DELETE ON tasks
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (OLD.created_by, 'DELETE', 'tasks', OLD.id, 
                    'Task deleted: ' || OLD.title);
        END
    ''')
    
    # TRIGGER 11: Log task assignment changes
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_task_assignment
        AFTER UPDATE OF assigned_to ON tasks
        WHEN NEW.assigned_to != OLD.assigned_to OR (NEW.assigned_to IS NOT NULL AND OLD.assigned_to IS NULL)
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.assigned_to, 'UPDATE', 'tasks', NEW.id, 
                    'Task reassigned from user ' || COALESCE(OLD.assigned_to, 0) || ' to user ' || NEW.assigned_to);
        END
    ''')
    
    # TRIGGER 12: Log task priority changes
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_task_priority
        AFTER UPDATE OF priority ON tasks
        WHEN NEW.priority != OLD.priority
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.assigned_to, 'UPDATE', 'tasks', NEW.id, 
                    'Task priority changed from ' || OLD.priority || ' to ' || NEW.priority);
        END
    ''')
    
    # TRIGGER 13: Auto-update meeting participant count on changes
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_meeting_modified
        AFTER INSERT ON meeting_participants
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.user_id, 'JOIN', 'meeting_participants', NEW.meeting_id, 
                    'User joined meeting ID ' || NEW.meeting_id);
        END
    ''')
    
    # TRIGGER 14: Log meeting status changes (accept/decline)
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_meeting_status_change
        AFTER UPDATE OF status ON meeting_participants
        WHEN NEW.status != OLD.status
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.user_id, 'UPDATE', 'meeting_participants', NEW.meeting_id, 
                    'Meeting status changed from ' || OLD.status || ' to ' || NEW.status);
        END
    ''')
    
    # TRIGGER 15: Prevent task assignment to inactive users
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS prevent_inactive_task_assignment
        BEFORE INSERT ON tasks
        WHEN NEW.assigned_to IS NOT NULL
        BEGIN
            SELECT CASE
                WHEN (SELECT is_active FROM users WHERE id = NEW.assigned_to) = 0
                THEN RAISE(ABORT, 'Cannot assign task to inactive user')
            END;
        END
    ''')
    
    # TRIGGER 16: Prevent meeting invitation to inactive users
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS prevent_inactive_meeting_invite
        BEFORE INSERT ON meeting_participants
        BEGIN
            SELECT CASE
                WHEN (SELECT is_active FROM users WHERE id = NEW.user_id) = 0
                THEN RAISE(ABORT, 'Cannot invite inactive user to meeting')
            END;
        END
    ''')
    
    # TRIGGER 17: Auto-log organization changes
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS log_organization_update
        AFTER UPDATE ON organizations
        BEGIN
            INSERT INTO activity_log (action, table_name, record_id, details)
            VALUES ('UPDATE', 'organizations', NEW.id, 
                    'Organization renamed from ' || OLD.name || ' to ' || NEW.name);
        END
    ''')
    
    # TRIGGER 18: Cascade deactivate - when user is deactivated, reassign their tasks
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS handle_user_deactivation
        AFTER UPDATE OF is_active ON users
        WHEN NEW.is_active = 0 AND OLD.is_active = 1
        BEGIN
            INSERT INTO activity_log (user_id, action, table_name, record_id, details)
            VALUES (NEW.id, 'DEACTIVATE', 'users', NEW.id, 
                    'User deactivated: ' || NEW.full_name || '. Tasks may need reassignment.');
        END
    ''')
    
    # Create default organization and admin if not exists
    cursor.execute("SELECT COUNT(*) as count FROM organizations")
    if cursor.fetchone()['count'] == 0:
        cursor.execute("INSERT INTO organizations (name) VALUES ('Default Organization')")
        org_id = cursor.lastrowid
        
        # Create default admin
        admin_password = 'admin123'  # Change this in production
        password_hash = generate_password_hash(admin_password)
        cursor.execute('''
            INSERT INTO users (org_id, login_id, password_hash, full_name, email, role, job_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (org_id, 'admin', password_hash, 'System Administrator', 'admin@flowdeck.com', 'admin', 'admin'))
        
        print(f"Default admin created - Login ID: admin, Password: {admin_password}")
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def generate_credentials():
    """Generate random login credentials"""
    login_id = 'emp_' + ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    password = ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%') for _ in range(12))
    return login_id, password

def create_user(org_id, full_name, email, role, job_level, created_by=None):
    """Create a new user and return credentials"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Generate password: firstname@123
    first_name = full_name.split()[0].lower()
    password = f"{first_name}@123"
    
    # Generate login_id from concatenated full name
    # Remove spaces and convert to lowercase
    base_login_id = ''.join(full_name.lower().split())
    login_id = base_login_id
    
    # Check if login_id exists, if so add numbers
    counter = 1
    while True:
        cursor.execute('SELECT id FROM users WHERE login_id = ?', (login_id,))
        if cursor.fetchone() is None:
            break
        login_id = f"{base_login_id}{counter}"
        counter += 1
    
    password_hash = generate_password_hash(password)
    
    try:
        cursor.execute('''
            INSERT INTO users (org_id, login_id, password_hash, full_name, email, role, job_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (org_id, login_id, password_hash, full_name, email, role, job_level))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        return {
            'success': True,
            'user_id': user_id,
            'login_id': login_id,
            'password': password,
            'full_name': full_name,
            'email': email
        }
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def log_activity(user_id, action, table_name, record_id=None, details=None, ip_address=None):
    """Log user activity"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO activity_log (user_id, action, table_name, record_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, action, table_name, record_id, details, ip_address))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
