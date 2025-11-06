from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime
import sqlite3
from database import get_db, init_db, create_user, log_activity
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, org_id, login_id, full_name, email, role, job_level):
        self.id = id
        self.org_id = org_id
        self.login_id = login_id
        self.full_name = full_name
        self.email = email
        self.role = role
        self.job_level = job_level
    
    def is_admin(self):
        return self.role == 'admin'

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(
            id=user_data['id'],
            org_id=user_data['org_id'],
            login_id=user_data['login_id'],
            full_name=user_data['full_name'],
            email=user_data['email'],
            role=user_data['role'],
            job_level=user_data['job_level']
        )
    return None

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        login_id = request.form.get('login_id')
        password = request.form.get('password')
        login_type = request.form.get('login_type', 'employee')  # Get login type
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE login_id = ? AND is_active = 1', (login_id,))
        user_data = cursor.fetchone()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            # Verify user role matches login type
            if login_type == 'admin' and user_data['role'] != 'admin':
                conn.close()
                flash('Invalid admin credentials. Please use employee login.', 'danger')
                return render_template('login.html')
            elif login_type == 'employee' and user_data['role'] == 'admin':
                conn.close()
                flash('Please use admin login for admin accounts.', 'warning')
                return render_template('login.html')
            
            # Update last login
            cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_data['id'],))
            conn.commit()
            
            # Log activity
            log_activity(user_data['id'], 'LOGIN', 'users', user_data['id'], 'User logged in', request.remote_addr)
            
            user = User(
                id=user_data['id'],
                org_id=user_data['org_id'],
                login_id=user_data['login_id'],
                full_name=user_data['full_name'],
                email=user_data['email'],
                role=user_data['role'],
                job_level=user_data['job_level']
            )
            login_user(user)
            conn.close()
            
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            conn.close()
            flash('Invalid login credentials. Please try again.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity(current_user.id, 'LOGOUT', 'users', current_user.id, 'User logged out', request.remote_addr)
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/create-organization', methods=['GET', 'POST'])
def create_organization():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        org_name = request.form.get('org_name')
        admin_name = request.form.get('admin_name')
        admin_email = request.form.get('admin_email')
        admin_login_id = request.form.get('admin_login_id')
        admin_password = request.form.get('admin_password')
        admin_password_confirm = request.form.get('admin_password_confirm')
        
        # Validate passwords match
        if admin_password != admin_password_confirm:
            flash('Passwords do not match!', 'danger')
            return render_template('create_organization.html')
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Check if organization name already exists
            cursor.execute('SELECT id FROM organizations WHERE name = ?', (org_name,))
            if cursor.fetchone():
                flash('Organization name already exists. Please choose a different name.', 'danger')
                return render_template('create_organization.html')
            
            # Check if admin login_id already exists
            cursor.execute('SELECT id FROM users WHERE login_id = ?', (admin_login_id,))
            if cursor.fetchone():
                flash('Login ID already exists. Please choose a different login ID.', 'danger')
                return render_template('create_organization.html')
            
            # Create organization
            cursor.execute('INSERT INTO organizations (name) VALUES (?)', (org_name,))
            org_id = cursor.lastrowid
            
            # Create admin user
            password_hash = generate_password_hash(admin_password)
            cursor.execute('''
                INSERT INTO users (org_id, login_id, password_hash, full_name, email, role, job_level)
                VALUES (?, ?, ?, ?, ?, 'admin', 'admin')
            ''', (org_id, admin_login_id, password_hash, admin_name, admin_email))
            
            admin_id = cursor.lastrowid
            conn.commit()
            
            # Log activity
            log_activity(admin_id, 'CREATE', 'organizations', org_id, 
                        f'Created organization: {org_name}', request.remote_addr)
            
            conn.close()
            
            flash(f'Organization "{org_name}" created successfully! You can now login with your admin credentials.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f'Error creating organization: {str(e)}', 'danger')
            return render_template('create_organization.html')
    
    return render_template('create_organization.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE org_id = ? AND assigned_to = ?', 
                   (current_user.org_id, current_user.id))
    my_tasks = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM meetings WHERE org_id = ? AND meeting_date >= datetime("now")', 
                   (current_user.org_id,))
    upcoming_meetings = cursor.fetchone()['count']
    
    if current_user.is_admin():
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE org_id = ? AND is_active = 1', 
                       (current_user.org_id,))
        total_employees = cursor.fetchone()['count']
    else:
        total_employees = 0
    
    # Get tasks for mini Kanban - admins see all, employees see only their tasks
    if current_user.is_admin():
        cursor.execute('''
            SELECT t.*, 
                   u1.full_name as assigned_to_name,
                   u2.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            JOIN users u2 ON t.created_by = u2.id
            WHERE t.org_id = ?
            ORDER BY t.position ASC, t.created_at DESC
        ''', (current_user.org_id,))
    else:
        cursor.execute('''
            SELECT t.*, 
                   u1.full_name as assigned_to_name,
                   u2.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            JOIN users u2 ON t.created_by = u2.id
            WHERE t.org_id = ? AND (t.assigned_to = ? OR t.created_by = ?)
            ORDER BY t.position ASC, t.created_at DESC
        ''', (current_user.org_id, current_user.id, current_user.id))
    all_tasks = cursor.fetchall()
    
    # Group tasks by status for Kanban
    tasks_by_status = {
        'todo': [t for t in all_tasks if t['status'] == 'todo'],
        'in_progress': [t for t in all_tasks if t['status'] == 'in_progress'],
        'review': [t for t in all_tasks if t['status'] == 'review'],
        'done': [t for t in all_tasks if t['status'] == 'done']
    }
    
    # Get upcoming meetings - only where user is participant or creator
    if current_user.is_admin():
        cursor.execute('''
            SELECT m.*, u.full_name as created_by_name
            FROM meetings m
            JOIN users u ON m.created_by = u.id
            WHERE m.org_id = ? AND m.meeting_date >= datetime("now")
            ORDER BY m.meeting_date ASC LIMIT 5
        ''', (current_user.org_id,))
    else:
        cursor.execute('''
            SELECT DISTINCT m.*, u.full_name as created_by_name
            FROM meetings m
            JOIN users u ON m.created_by = u.id
            LEFT JOIN meeting_participants mp ON m.id = mp.meeting_id
            WHERE m.org_id = ? AND m.meeting_date >= datetime("now") 
                  AND (m.created_by = ? OR mp.user_id = ?)
            ORDER BY m.meeting_date ASC LIMIT 5
        ''', (current_user.org_id, current_user.id, current_user.id))
    
    upcoming_meetings_list = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html',
                         my_tasks=my_tasks,
                         upcoming_meetings=upcoming_meetings,
                         total_employees=total_employees,
                         tasks_by_status=tasks_by_status,
                         upcoming_meetings_list=upcoming_meetings_list)

# Admin Console Routes
@app.route('/admin')
@login_required
@admin_required
def admin_console():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM users 
        WHERE org_id = ? AND is_active = 1
        ORDER BY created_at DESC
    ''', (current_user.org_id,))
    employees = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE org_id = ? AND is_active = 1', 
                   (current_user.org_id,))
    total_employees = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE org_id = ?', 
                   (current_user.org_id,))
    total_tasks = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM meetings WHERE org_id = ?', 
                   (current_user.org_id,))
    total_meetings = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('admin_console.html',
                         employees=employees,
                         total_employees=total_employees,
                         total_tasks=total_tasks,
                         total_meetings=total_meetings)

@app.route('/admin/create-employee', methods=['POST'])
@login_required
@admin_required
def create_employee():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    job_level = request.form.get('job_level')
    
    result = create_user(current_user.org_id, full_name, email, 'employee', job_level, current_user.id)
    
    if result['success']:
        log_activity(current_user.id, 'CREATE', 'users', result['user_id'], 
                    f'Created employee: {full_name}', request.remote_addr)
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/admin/deactivate-employee/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def deactivate_employee(user_id):
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot deactivate yourself'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE users SET is_active = 0 WHERE id = ? AND org_id = ?', 
                      (user_id, current_user.org_id))
        conn.commit()
        log_activity(current_user.id, 'DEACTIVATE', 'users', user_id, 
                    'Deactivated employee', request.remote_addr)
        conn.close()
        flash('Employee deactivated successfully.', 'success')
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/edit-employee/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def edit_employee(user_id):
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    job_level = request.form.get('job_level')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users SET full_name = ?, email = ?, job_level = ?
            WHERE id = ? AND org_id = ?
        ''', (full_name, email, job_level, user_id, current_user.org_id))
        conn.commit()
        log_activity(current_user.id, 'UPDATE', 'users', user_id, 
                    f'Updated employee: {full_name}', request.remote_addr)
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_employee_password(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get user's first name
        cursor.execute('SELECT full_name FROM users WHERE id = ? AND org_id = ?', 
                      (user_id, current_user.org_id))
        user_data = cursor.fetchone()
        
        if not user_data:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Generate password: firstname@123
        first_name = user_data['full_name'].split()[0].lower()
        new_password = f"{first_name}@123"
        password_hash = generate_password_hash(new_password)
        
        cursor.execute('''
            UPDATE users SET password_hash = ?
            WHERE id = ? AND org_id = ?
        ''', (password_hash, user_id, current_user.org_id))
        conn.commit()
        log_activity(current_user.id, 'RESET_PASSWORD', 'users', user_id, 
                    'Reset employee password', request.remote_addr)
        conn.close()
        return jsonify({'success': True, 'password': new_password})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 400

# Meetings Routes
@app.route('/meetings')
@login_required
def meetings():
    conn = get_db()
    cursor = conn.cursor()
    
    # Only show meetings where user is creator or participant (unless admin)
    if current_user.is_admin():
        cursor.execute('''
            SELECT m.*, u.full_name as created_by_name,
                   (SELECT COUNT(*) FROM meeting_participants WHERE meeting_id = m.id) as participant_count
            FROM meetings m
            JOIN users u ON m.created_by = u.id
            WHERE m.org_id = ?
            ORDER BY m.meeting_date DESC
        ''', (current_user.org_id,))
    else:
        cursor.execute('''
            SELECT DISTINCT m.*, u.full_name as created_by_name,
                   (SELECT COUNT(*) FROM meeting_participants WHERE meeting_id = m.id) as participant_count
            FROM meetings m
            JOIN users u ON m.created_by = u.id
            LEFT JOIN meeting_participants mp ON m.id = mp.meeting_id
            WHERE m.org_id = ? AND (m.created_by = ? OR mp.user_id = ?)
            ORDER BY m.meeting_date DESC
        ''', (current_user.org_id, current_user.id, current_user.id))
    
    meetings_list = cursor.fetchall()
    
    # Get all employees for participant selection
    cursor.execute('SELECT id, full_name, job_level FROM users WHERE org_id = ? AND is_active = 1', 
                   (current_user.org_id,))
    employees = cursor.fetchall()
    
    conn.close()
    
    return render_template('meetings.html', meetings=meetings_list, employees=employees)

@app.route('/meetings/create', methods=['POST'])
@login_required
def create_meeting():
    title = request.form.get('title')
    description = request.form.get('description')
    meeting_date = request.form.get('meeting_date')
    duration = request.form.get('duration', 60)
    location = request.form.get('location')
    participants = request.form.getlist('participants[]')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO meetings (org_id, title, description, meeting_date, duration_minutes, location, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (current_user.org_id, title, description, meeting_date, duration, location, current_user.id))
        
        meeting_id = cursor.lastrowid
        
        # Add participants
        for participant_id in participants:
            cursor.execute('''
                INSERT INTO meeting_participants (meeting_id, user_id)
                VALUES (?, ?)
            ''', (meeting_id, participant_id))
        
        conn.commit()
        log_activity(current_user.id, 'CREATE', 'meetings', meeting_id, 
                    f'Created meeting: {title}', request.remote_addr)
        flash('Meeting created successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error creating meeting: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('meetings'))

@app.route('/meetings/<int:meeting_id>')
@login_required
def view_meeting(meeting_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.*, u.full_name as created_by_name
        FROM meetings m
        JOIN users u ON m.created_by = u.id
        WHERE m.id = ? AND m.org_id = ?
    ''', (meeting_id, current_user.org_id))
    meeting = cursor.fetchone()
    
    if not meeting:
        flash('Meeting not found.', 'danger')
        return redirect(url_for('meetings'))
    
    cursor.execute('''
        SELECT mp.*, u.full_name, u.email, u.job_level
        FROM meeting_participants mp
        JOIN users u ON mp.user_id = u.id
        WHERE mp.meeting_id = ?
    ''', (meeting_id,))
    participants = cursor.fetchall()
    
    # Check if current user is a participant
    cursor.execute('''
        SELECT status FROM meeting_participants
        WHERE meeting_id = ? AND user_id = ?
    ''', (meeting_id, current_user.id))
    user_participation = cursor.fetchone()
    
    conn.close()
    
    return render_template('meeting_detail.html', meeting=meeting, participants=participants, user_participation=user_participation)

@app.route('/meetings/<int:meeting_id>/update-status', methods=['POST'])
@login_required
def update_meeting_status(meeting_id):
    status = request.json.get('status')  # 'accepted' or 'declined'
    
    if status not in ['accepted', 'declined']:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Update the participant status
        cursor.execute('''
            UPDATE meeting_participants
            SET status = ?
            WHERE meeting_id = ? AND user_id = ?
        ''', (status, meeting_id, current_user.id))
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'error': 'You are not a participant of this meeting'}), 403
        
        conn.commit()
        log_activity(current_user.id, 'UPDATE', 'meeting_participants', meeting_id,
                    f'Updated meeting status to: {status}', request.remote_addr)
        conn.close()
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 400

# Tasks Routes
@app.route('/tasks')
@login_required
def tasks():
    conn = get_db()
    cursor = conn.cursor()
    
    # Only show tasks assigned to or created by the user (unless admin)
    if current_user.is_admin():
        cursor.execute('''
            SELECT t.*, 
                   u1.full_name as assigned_to_name,
                   u2.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            JOIN users u2 ON t.created_by = u2.id
            WHERE t.org_id = ?
            ORDER BY t.created_at DESC
        ''', (current_user.org_id,))
    else:
        cursor.execute('''
            SELECT t.*, 
                   u1.full_name as assigned_to_name,
                   u2.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            JOIN users u2 ON t.created_by = u2.id
            WHERE t.org_id = ? AND (t.assigned_to = ? OR t.created_by = ?)
            ORDER BY t.created_at DESC
        ''', (current_user.org_id, current_user.id, current_user.id))
    
    tasks_list = cursor.fetchall()
    
    # Get all employees for task assignment
    cursor.execute('SELECT id, full_name, job_level FROM users WHERE org_id = ? AND is_active = 1', 
                   (current_user.org_id,))
    employees = cursor.fetchall()
    
    conn.close()
    
    return render_template('tasks.html', tasks=tasks_list, employees=employees)

@app.route('/tasks/create', methods=['POST'])
@login_required
def create_task():
    title = request.form.get('title')
    description = request.form.get('description')
    priority = request.form.get('priority', 'medium')
    assigned_to = request.form.get('assigned_to')
    due_date = request.form.get('due_date')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO tasks (org_id, title, description, priority, assigned_to, created_by, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (current_user.org_id, title, description, priority, assigned_to or None, current_user.id, due_date or None))
        
        task_id = cursor.lastrowid
        conn.commit()
        log_activity(current_user.id, 'CREATE', 'tasks', task_id, 
                    f'Created task: {title}', request.remote_addr)
        flash('Task created successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error creating task: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:task_id>/update-status', methods=['POST'])
@login_required
def update_task_status(task_id):
    status = request.json.get('status')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if user has permission to update this task
        if current_user.is_admin():
            cursor.execute('''
                UPDATE tasks SET status = ?
                WHERE id = ? AND org_id = ?
            ''', (status, task_id, current_user.org_id))
        else:
            # Only allow updating tasks assigned to or created by the user
            cursor.execute('''
                UPDATE tasks SET status = ?
                WHERE id = ? AND org_id = ? AND (assigned_to = ? OR created_by = ?)
            ''', (status, task_id, current_user.org_id, current_user.id, current_user.id))
        
        conn.commit()
        log_activity(current_user.id, 'UPDATE', 'tasks', task_id, 
                    f'Updated task status to: {status}', request.remote_addr)
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 400

# Kanban Board Routes
@app.route('/kanban')
@login_required
def kanban():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get tasks grouped by status - admins see all, employees see only their tasks
    if current_user.is_admin():
        cursor.execute('''
            SELECT t.*, 
                   u1.full_name as assigned_to_name,
                   u2.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            JOIN users u2 ON t.created_by = u2.id
            WHERE t.org_id = ?
            ORDER BY t.position ASC, t.created_at DESC
        ''', (current_user.org_id,))
    else:
        cursor.execute('''
            SELECT t.*, 
                   u1.full_name as assigned_to_name,
                   u2.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            JOIN users u2 ON t.created_by = u2.id
            WHERE t.org_id = ? AND (t.assigned_to = ? OR t.created_by = ?)
            ORDER BY t.position ASC, t.created_at DESC
        ''', (current_user.org_id, current_user.id, current_user.id))
    all_tasks = cursor.fetchall()
    
    # Get all employees for task assignment
    cursor.execute('SELECT id, full_name, job_level FROM users WHERE org_id = ? AND is_active = 1', 
                   (current_user.org_id,))
    employees = cursor.fetchall()
    
    conn.close()
    
    # Group tasks by status
    tasks_by_status = {
        'todo': [t for t in all_tasks if t['status'] == 'todo'],
        'in_progress': [t for t in all_tasks if t['status'] == 'in_progress'],
        'review': [t for t in all_tasks if t['status'] == 'review'],
        'done': [t for t in all_tasks if t['status'] == 'done']
    }
    
    return render_template('kanban.html', tasks_by_status=tasks_by_status, employees=employees)

@app.route('/kanban/update-position', methods=['POST'])
@login_required
def update_task_position():
    task_id = request.json.get('task_id')
    new_status = request.json.get('status')
    new_position = request.json.get('position', 0)
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if user has permission to update this task
        if current_user.is_admin():
            cursor.execute('''
                UPDATE tasks SET status = ?, position = ?
                WHERE id = ? AND org_id = ?
            ''', (new_status, new_position, task_id, current_user.org_id))
        else:
            # Only allow updating tasks assigned to or created by the user
            cursor.execute('''
                UPDATE tasks SET status = ?, position = ?
                WHERE id = ? AND org_id = ? AND (assigned_to = ? OR created_by = ?)
            ''', (new_status, new_position, task_id, current_user.org_id, current_user.id, current_user.id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    import socket
    import os
    
    # Initialize database
    init_db()
    
    # Check if port is available
    def is_port_available(port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('0.0.0.0', port))
            s.close()
            return True
        except OSError:
            return False
    
    # Find available port starting from 5010
    port = 5010
    while not is_port_available(port) and port < 5020:
        port += 1
    
    if port >= 5020:
        print("\n❌ Error: No available ports found (5010-5019)")
        print("Please stop other services or manually specify a different port.")
        exit(1)
    
    # Only show banner on main process (not reloader process)
    # Flask's reloader sets WERKZEUG_RUN_MAIN environment variable
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # Get local IP address
        def get_local_ip():
            try:
                # Create a socket connection to get the local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                return local_ip
            except Exception:
                return "Unable to determine"
        
        local_ip = get_local_ip()
        
        print("\n" + "="*60)
        print("🚀 FlowDeck Server Started!")
        print("="*60)
        print(f"📍 Local Access:    http://127.0.0.1:{port}")
        print(f"🌐 Network Access:  http://{local_ip}:{port}")
        print("="*60)
        print("💡 Other devices on your network can access using the Network URL")
        if port != 5010:
            print(f"⚠️  Using port {port} (port 5010 was busy)")
        print("🛑 Press CTRL+C to quit")
        print("="*60 + "\n")
    
    # Run app on all network interfaces (0.0.0.0)
    app.run(debug=True, host='0.0.0.0', port=port)
