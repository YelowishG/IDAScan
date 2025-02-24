from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash, safe_str_cmp
from datetime import datetime, time, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages

# Database connection function
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="sql12.freesqldatabase.com",
            user="sql12762297",
            password="52gVNadWvI",
            database="sql12762297",
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
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
            except mysql.connector.Error as err:
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
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM website_users WHERE id_number = %s AND category = %s", (id_number, category))
            user = cursor.fetchone()
            cursor.fetchall()  # Fetch all remaining results to avoid "Unread result found" error
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
        cursor = db.cursor(dictionary=True)
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
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_number, date, time_in, time_out FROM dtr WHERE id_number = %s", (user_id,))
        records = cursor.fetchall()
        for record in records:
            record['date'] = record['date'].strftime("%Y-%m-%d")
            if record['time_in']:
                record['time_in'] = record['time_in'].strftime('%H:%M:%S')
            if record['time_out']:
                record['time_out'] = record['time_out'].strftime('%H:%M:%S')
        cursor.close()
        db.close()
        return jsonify(records)
    else:
        return jsonify({'error': 'Database connection failed.'})

@app.route('/fetch_records')
def fetch_records():
    db = get_db_connection()
    if db:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT date, id_number, name, time_in, time_out FROM dtr")
        records = cursor.fetchall()

        for record in records:
            # Convert timedelta fields to time and then to string if they are not None
            if isinstance(record['time_in'], timedelta):
                total_seconds = record['time_in'].total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                record['time_in'] = time(hours, minutes, seconds).strftime('%H:%M:%S')
            if isinstance(record['time_out'], timedelta):
                total_seconds = record['time_out'].total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                record['time_out'] = time(hours, minutes, seconds).strftime('%H:%M:%S')
                
            # Combine time_in and time_out into a single time column
            record['time'] = f"{record['time_in']} - {record['time_out']}" if record['time_out'] else f"{record['time_in']}"
            
            # Format the date to exclude GMT
            record['date'] = record['date'].strftime('%Y-%m-%d')
            
            # Add "late" to remarks if time_in is after 08:00:00
            if datetime.strptime(record['time_in'], '%H:%M:%S') > datetime.strptime('07:40:00', '%H:%M:%S'):
                record['remarks'] = 'late'
            else:
                record['remarks'] = ''

        cursor.close()
        db.close()

        # Log the fetched records
        print('Fetched records:', records)

        return jsonify(records)
    else:
        return jsonify({'error': 'Database connection failed.'})

if __name__ == '__main__':
    app.run(debug=True)
