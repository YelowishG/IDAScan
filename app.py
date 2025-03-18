from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import psycopg2
from psycopg2 import Error
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages

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
                if category == 'teacher' or category == 'class_monitor':
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

@app.route('/teacher_classmonitor')
def teacher_classmonitor():
    return render_template('classmonitor.html')

@app.route('/student_dashboard/<id_number>')
def student_dashboard(id_number):
    db = get_db_connection()
    if db:
        cursor = db.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT COUNT(*) AS total_attendances FROM dtr WHERE id_number = %s", (id_number,))
        total_attendances = cursor.fetchone()['total_attendances']
        cursor.execute("SELECT COUNT(*) AS total_absences FROM dtr WHERE id_number = %s AND time_in IS NULL", (id_number,))
        total_absences = cursor.fetchone()['total_absences']
        cursor.execute("SELECT COUNT(DISTINCT date) AS total_school_days FROM dtr WHERE id_number = %s", (id_number,))
        total_school_days = cursor.fetchone()['total_school_days']
        cursor.close()
        db.close()
        attendance = {
            'total_attendances': total_attendances,
            'total_absences': total_absences,
            'total_school_days': total_school_days
        }
        return render_template('student_red.html', user_id=id_number, attendance=attendance)
    else:
        flash('Database connection failed. Please try again later.', 'danger')
        return redirect(url_for('homepage'))

@app.route('/fetch_student_records/<user_id>')
def fetch_student_records(user_id):
    db = get_db_connection()
    if db:
        cursor = db.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT id_number, date, time_in, time_out FROM dtr WHERE id_number = %s", (user_id,))
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
            
        cursor.close()
        db.close()
        return jsonify(result)
    else:
        return jsonify({'error': 'Database connection failed.'})

@app.route('/fetch_records')
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