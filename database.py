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
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

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
