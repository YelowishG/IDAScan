from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import psycopg2
from psycopg2 import Error
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time, timedelta
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages and sessions

# Database connection function
def get_db_connection():
    try:
        # Get database connection details from environment variables
        DATABASE_URL = os.environ.get('DATABASE_URL')
        
        # If DATABASE_URL is provided, use it directly
        if DATABASE_URL:
            connection = psycopg2.connect(DATABASE_URL)
        else:
            # Otherwise, use individual parameters
            connection = psycopg2.connect(
                host=os.environ.get('DB_HOST'),
                port=os.environ.get('DB_PORT', 5432),  # Default PostgreSQL port
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD'),
                database=os.environ.get('DB_NAME')
            )
        
        return connection
    except Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
    return None

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('homepage'))
        return f(*args, **kwargs)
    return decorated_function

# Role-based access control decorator
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] not in allowed_roles:
                flash('Access denied: You do not have permission to access this page.', 'danger')
                return redirect(url_for('homepage'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def homepage():
    return render_template('homepage.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname'].upper()
        lastname = request.form['lastname'].upper()
        middlename = request.form['middlename'].upper()
        name = f"{firstname} {middlename[0]}. {lastname}"  # Combine name fields in the required format
        birthday = request.form['birthday']
        section = request.form['section']
        category = request.form['category']
        id_number = request.form['id_number']
        password = generate_password_hash(request.form['password'], method='sha256')  # Specify algorithm

        db = get_db_connection()
        if db:
            try:
                # Create cursor with dictionary support
                cursor = db.cursor()
                cursor.execute(
                    "INSERT INTO website_users (firstname, lastname, middlename, section, category, id_number, password) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (firstname, lastname, middlename, section, category, id_number, password)
                )
                cursor.execute(
                    "INSERT INTO users (id_number, name, role) VALUES (%s, %s, %s)",
                    (id_number, name, category)
                )
                db.commit()
                cursor.close()
                flash('Registration successful!', 'success')
            except psycopg2.Error as err:
                db.rollback()  # Rollback on error
                flash(f"Error: {err}", 'danger')
                cursor.close()
                return redirect(url_for('register'))
            finally:
                db.close()
        else:
            flash('Database connection failed. Please try again later.', 'danger')
            return redirect(url_for('register'))

        return redirect(url_for('homepage'))
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    id_number = request.form['id_number']
    password = request.form['password']
    category = request.form['category']

    db = get_db_connection()
    if db:
        try:
            cursor = db.cursor(cursor_factory=DictCursor)  # Use DictCursor for dictionary-like results
            cursor.execute("SELECT * FROM website_users WHERE id_number = %s AND category = %s", (id_number, category))
            user = cursor.fetchone()
            
            cursor.close()
            if user and check_password_hash(user['password'], password):  # Verify hashed password
                # Store user information in session
                session['user_id'] = user['id']
                session['user_role'] = category
                session['user_name'] = user['firstname']
                
                # Redirect based on user role
                if category == 'teacher' or category == 'class_monitor' or category == 'monitor':
                    return redirect(url_for('teacher_classmonitor'))
                elif category == 'student':
                    return redirect(url_for('student_dashboard', id_number=user['id']))
                else:
                    return f"Welcome {user['firstname']}! You are logged in as a {category.capitalize()}."
            else:
                flash('Invalid credentials. Please try again.', 'danger')
                return redirect(url_for('homepage'))
        finally:
            db.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        return redirect(url_for('homepage'))

@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('homepage'))

@app.route('/teacher_classmonitor')
@login_required
@role_required(['teacher', 'class_monitor', 'monitor'])
def teacher_classmonitor():
    return render_template('classmonitor.html')

@app.route('/student_dashboard/<id_number>')
@login_required
def student_dashboard(id_number):
    # Ensure users can only access their own dashboard
    if str(session['user_id']) != str(id_number) and session['user_role'] != 'teacher' and session['user_role'] != 'monitor':
        flash('Access denied: You can only view your own dashboard.', 'danger')
        return redirect(url_for('homepage'))
        
    db = get_db_connection()
    if db:
        try:
            cursor = db.cursor(cursor_factory=DictCursor)
            
            # Get the student's name
            cursor.execute("SELECT name FROM users WHERE id_number = %s", (id_number,))
            user_data = cursor.fetchone()
            user_name = user_data['name'] if user_data else "Student"
            
            # Count attendances (days where time_in is not null)
            cursor.execute("""
                SELECT COUNT(*) AS total_attendances 
                FROM dtr 
                WHERE id_number = %s AND time_in IS NOT NULL
            """, (id_number,))
            total_attendances = cursor.fetchone()['total_attendances']
            
            # If there are no records yet, set a default value of 1 for attendance
            if total_attendances == 0:
                total_attendances = 1
            
            # Count absences (days where time_in is null)
            cursor.execute("""
                SELECT COUNT(*) AS total_absences 
                FROM dtr 
                WHERE id_number = %s AND time_in IS NULL
            """, (id_number,))
            total_absences = cursor.fetchone()['total_absences']
            
            # Count total school days - we'll set this to a fixed value of 180
            total_school_days = 180
            
            # Count late days (time_in after 07:40:00)
            cursor.execute("""
                SELECT COUNT(*) AS total_late 
                FROM dtr 
                WHERE id_number = %s AND time_in > '07:40:00'
            """, (id_number,))
            total_late = cursor.fetchone()['total_late']
            
            attendance = {
                'total_attendances': total_attendances,
                'total_absences': total_absences,
                'total_school_days': total_school_days,
                'total_late': total_late,
                'user_name': user_name
            }
            
            return render_template('student_red.html', user_id=id_number, attendance=attendance)
            
        except Exception as e:
            print(f"Error in student dashboard: {e}")
            flash(f'Error retrieving attendance data: {str(e)}', 'danger')
            return redirect(url_for('homepage'))
        finally:
            db.close()
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        return redirect(url_for('homepage'))

@app.route('/fetch_student_records/<user_id>')
@login_required
def fetch_student_records(user_id):
    # Ensure users can only access their own records
    if str(session['user_id']) != str(user_id) and session['user_role'] != 'teacher' and session['user_role'] != 'monitor':
        return jsonify({'error': 'Access denied'})
        
    db = get_db_connection()
    if db:
        try:
            cursor = db.cursor(cursor_factory=DictCursor)
            
            # Get all attendance records for this student
            cursor.execute("""
                SELECT id_number, date, time_in, time_out 
                FROM dtr 
                WHERE id_number = %s
                ORDER BY date DESC
            """, (user_id,))
            
            records = cursor.fetchall()
            
            # Convert records to a list of dictionaries
            result = []
            for record in records:
                # Convert date and time objects to strings
                record_dict = dict(record)
                record_dict['date'] = record_dict['date'].strftime("%Y-%m-%d")
                if record_dict['time_in']:
                    record_dict['time_in'] = record_dict['time_in'].strftime('%H:%M:%S')
                if record_dict['time_out']:
                    record_dict['time_out'] = record_dict['time_out'].strftime('%H:%M:%S')
                result.append(record_dict)
                
            return jsonify(result)
            
        except Exception as e:
            print(f"Error fetching student records: {e}")
            return jsonify({'error': f'Database error: {str(e)}'})
        finally:
            db.close()
    else:
        return jsonify({'error': 'Database connection failed.'})

@app.route('/fetch_records')
@login_required
@role_required(['teacher', 'class_monitor', 'monitor'])
def fetch_records():
    db = get_db_connection()
    if db:
        cursor = db.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT date, id_number, name, time_in, time_out FROM dtr")
        records = cursor.fetchall()
        
        # Convert records to a list of dictionaries
        result = []
        for record in records:
            record_dict = dict(record)
            
            # Convert date and time objects to strings
            record_dict['date'] = record_dict['date'].strftime('%Y-%m-%d')
            
            if record_dict['time_in']:
                record_dict['time_in'] = record_dict['time_in'].strftime('%H:%M:%S')
            if record_dict['time_out']:
                record_dict['time_out'] = record_dict['time_out'].strftime('%H:%M:%S')
                
            # Combine time_in and time_out into a single time column
            record_dict['time'] = f"{record_dict['time_in']} - {record_dict['time_out']}" if record_dict['time_out'] else f"{record_dict['time_in']}"
            
            # Add "late" to remarks if time_in is after 07:40:00
            if record_dict['time_in'] and datetime.strptime(record_dict['time_in'], '%H:%M:%S') > datetime.strptime('07:40:00', '%H:%M:%S'):
                record_dict['remarks'] = 'late'
            else:
                record_dict['remarks'] = ''
                
            result.append(record_dict)

        cursor.close()
        db.close()
        return jsonify(result)
    else:
        return jsonify({'error': 'Database connection failed.'})

if __name__ == '__main__':
    app.run(debug=True)