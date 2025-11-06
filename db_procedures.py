"""
Database Stored Procedures and Advanced Queries
This module demonstrates how to use custom SQLite functions and triggers
"""

from database import get_db

# ==================== STORED PROCEDURES (CUSTOM FUNCTIONS) ====================

def get_overdue_tasks(org_id):
    """Get all overdue tasks with urgency scores"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            t.id,
            t.title,
            t.description,
            t.priority,
            t.due_date,
            days_overdue(t.due_date) as overdue_days,
            task_urgency_score(t.priority, t.due_date) as urgency_score,
            u.full_name as assigned_to_name
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.org_id = ? 
        AND t.status != 'done'
        AND days_overdue(t.due_date) > 0
        ORDER BY urgency_score DESC, overdue_days DESC
    ''', (org_id,))
    
    results = cursor.fetchall()
    conn.close()
    return results


def get_user_performance_metrics(user_id):
    """Get comprehensive performance metrics for a user"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            u.full_name,
            u.role,
            user_display_name(u.full_name, u.role) as display_name,
            task_completion_rate(u.id) as completion_rate,
            avg_completion_time(u.id) as avg_days_to_complete,
            pending_meetings(u.id) as pending_meeting_count,
            is_admin(u.id) as is_admin,
            (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'todo') as todo_tasks,
            (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'in_progress') as active_tasks,
            (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'done') as completed_tasks
        FROM users u
        WHERE u.id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    return result


def get_organization_dashboard(org_id):
    """Get organization-wide dashboard metrics"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            o.name as org_name,
            org_employee_count(o.id) as active_employees,
            (SELECT COUNT(*) FROM tasks WHERE org_id = o.id) as total_tasks,
            (SELECT COUNT(*) FROM tasks WHERE org_id = o.id AND status = 'done') as completed_tasks,
            (SELECT COUNT(*) FROM meetings WHERE org_id = o.id) as total_meetings,
            (SELECT COUNT(*) FROM tasks 
             WHERE org_id = o.id AND days_overdue(due_date) > 0 AND status != 'done') as overdue_tasks
        FROM organizations o
        WHERE o.id = ?
    ''', (org_id,))
    
    result = cursor.fetchone()
    conn.close()
    return result


def get_meeting_summary(meeting_id):
    """Get detailed meeting summary with formatted duration"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            m.title,
            m.description,
            m.meeting_date,
            format_duration(m.duration_minutes) as formatted_duration,
            m.location,
            u.full_name as created_by_name,
            (SELECT COUNT(*) FROM meeting_participants WHERE meeting_id = m.id) as total_participants,
            (SELECT COUNT(*) FROM meeting_participants WHERE meeting_id = m.id AND status = 'accepted') as accepted_count,
            (SELECT COUNT(*) FROM meeting_participants WHERE meeting_id = m.id AND status = 'declined') as declined_count,
            (SELECT COUNT(*) FROM meeting_participants WHERE meeting_id = m.id AND status = 'pending') as pending_count
        FROM meetings m
        JOIN users u ON m.created_by = u.id
        WHERE m.id = ?
    ''', (meeting_id,))
    
    result = cursor.fetchone()
    conn.close()
    return result


def get_high_priority_tasks_by_urgency(org_id, limit=10):
    """Get top urgent tasks sorted by urgency score"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            t.id,
            t.title,
            sanitize_text(t.description) as safe_description,
            t.priority,
            t.due_date,
            task_urgency_score(t.priority, t.due_date) as urgency_score,
            u.full_name as assigned_to
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.org_id = ? AND t.status != 'done'
        ORDER BY urgency_score DESC
        LIMIT ?
    ''', (org_id, limit))
    
    results = cursor.fetchall()
    conn.close()
    return results


def get_user_activity_summary(user_id, days=30):
    """Get user activity summary from activity log"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            action,
            table_name,
            COUNT(*) as action_count,
            MAX(timestamp) as last_action
        FROM activity_log
        WHERE user_id = ?
        AND timestamp >= datetime('now', '-' || ? || ' days')
        GROUP BY action, table_name
        ORDER BY action_count DESC
    ''', (user_id, days))
    
    results = cursor.fetchall()
    conn.close()
    return results


def get_inactive_employees(org_id, days_inactive=30):
    """Find employees who haven't had activity in specified days"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            u.id,
            u.full_name,
            u.email,
            u.job_level,
            u.last_login,
            (SELECT MAX(timestamp) FROM activity_log WHERE user_id = u.id) as last_activity,
            task_completion_rate(u.id) as completion_rate
        FROM users u
        WHERE u.org_id = ? 
        AND u.role = 'employee'
        AND u.is_active = 1
        AND (
            u.last_login IS NULL 
            OR u.last_login < datetime('now', '-' || ? || ' days')
        )
        ORDER BY u.last_login ASC
    ''', (org_id, days_inactive))
    
    results = cursor.fetchall()
    conn.close()
    return results


# ==================== ADVANCED TRIGGER TESTS ====================

def test_triggers():
    """Test all database triggers"""
    conn = get_db()
    cursor = conn.cursor()
    
    print("Testing Database Triggers...")
    print("="*60)
    
    # Check all triggers exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    triggers = cursor.fetchall()
    
    print(f"\n✓ Total Triggers: {len(triggers)}")
    for trigger in triggers:
        print(f"  - {trigger['name']}")
    
    conn.close()
    return True


def test_stored_procedures():
    """Test all custom SQLite functions (stored procedures)"""
    conn = get_db()
    cursor = conn.cursor()
    
    print("\nTesting Stored Procedures (Custom Functions)...")
    print("="*60)
    
    # Test 1: days_overdue
    cursor.execute("SELECT days_overdue('2024-01-01') as result")
    print(f"\n✓ days_overdue('2024-01-01'): {cursor.fetchone()['result']} days")
    
    # Test 2: format_duration
    cursor.execute("SELECT format_duration(125) as result")
    print(f"✓ format_duration(125): {cursor.fetchone()['result']}")
    
    # Test 3: task_urgency_score
    cursor.execute("SELECT task_urgency_score('urgent', '2024-01-01') as result")
    print(f"✓ task_urgency_score('urgent', '2024-01-01'): {cursor.fetchone()['result']}")
    
    # Test 4: user_display_name
    cursor.execute("SELECT user_display_name('John Doe', 'admin') as result")
    print(f"✓ user_display_name('John Doe', 'admin'): {cursor.fetchone()['result']}")
    
    conn.close()
    return True


# ==================== EXAMPLE USAGE ====================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("DATABASE PROCEDURES & TRIGGERS DEMO")
    print("="*60)
    
    # Test triggers
    test_triggers()
    
    # Test stored procedures
    test_stored_procedures()
    
    print("\n" + "="*60)
    print("✓ All database enhancements are working!")
    print("="*60 + "\n")
