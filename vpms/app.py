from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import MySQLdb.cursors
from datetime import datetime
import random,string

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'xxxxxxxx'
app.config['MYSQL_DB'] = 'vehicle_parking'

mysql = MySQL(app)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Home/Login
@app.route('/')
def home():
    return render_template('index.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the user is admin
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['loggedin'] = True
            session['username'] = ADMIN_USERNAME
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        else:
            # Check if it's a staff member (fetching details from DB)
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM staff WHERE username = %s AND password = %s', (username, password))
            account = cursor.fetchone()

            if account:
                session['loggedin'] = True
                session['username'] = account['username']
                session['role'] = 'staff'
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect username or password!')

    return render_template('index.html')

# Registration Route for Staff
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        phone_number = request.form['phone_number']
        e_mail = request.form['e_mail']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('INSERT INTO staff (username, password, phone_number, e_mail, role) VALUES (%s, %s, %s, %s, %s)', (username, password, phone_number, e_mail, 'staff'))
        mysql.connection.commit()
        flash('Registration successful! You can now log in.')
        return redirect(url_for('login'))
    return render_template('register.html')
# Forgotten Password
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        
        # Check if email exists in the staff table
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM staff WHERE e_mail = %s', (email,))
        account = cursor.fetchone()

        if account:
            # Generate a temporary reset token (or skip this if not using tokens)
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

            # Store token in session or database (for simplicity, using session here)
            session['reset_token'] = token
            session['reset_email'] = email

            flash('Password reset link sent! Please check your email.')
            return redirect(url_for('reset_password', token=token))
        else:
            flash('No account found with that email!')
    
    return render_template('forgot_password.html')
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if 'reset_token' not in session or session['reset_token'] != token:
        flash('Invalid or expired token!')
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['password']
        email = session['reset_email']

        # Update the user's password in the database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE staff SET password = %s WHERE e_mail = %s', (new_password, email))
        mysql.connection.commit()

        # Clear the reset session data
        session.pop('reset_token', None)
        session.pop('reset_email', None)

        flash('Password reset successfully! You can now log in.')
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)


# Dashboard (For Staff)
@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session and session['role']=='staff':
        return render_template('dashboard.html')
    else:
        flash('Please login to access the dashboard.')
        return redirect(url_for('login'))

# Manage Vehicles
@app.route('/manage_vehicles', methods=['GET', 'POST'])
def manage_vehicles():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Handle POST requests for adding or exiting vehicles
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'add':  # Add vehicle entry
                vehicle_number = request.form['vehicle_number']
                owner_name = request.form['owner_name']
                vehicle_type = request.form['vehicle_type']
                slot_number = request.form['slot_number']
                entry_time = datetime.now()
                exit_time = None
                parking_bill = 0

                 
                # Insert the vehicle entry into the database
                cursor.execute('''
                    INSERT INTO vehicles (vehicle_number, owner_name, vehicle_type, slot_number, entry_time, exit_time, parking_bill)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (vehicle_number, owner_name, vehicle_type, slot_number, entry_time, exit_time, parking_bill))

                # Update the slot status to 'occupied'
                cursor.execute('UPDATE slots SET status = %s WHERE slot_number = %s', ('occupied', slot_number))
                mysql.connection.commit()
                flash('Vehicle added successfully.')

            elif action == 'exit':  # Handle vehicle exit
                vehicle_id = request.form['vehicle_id']
                exit_time = datetime.now()

                # Retrieve the vehicle's entry time and slot number
                cursor.execute('SELECT entry_time, slot_number FROM vehicles WHERE id = %s', (vehicle_id,))
                vehicle = cursor.fetchone()
                entry_time = vehicle['entry_time']
                slot_number = vehicle['slot_number']

                # Calculate the parking duration in hours
                duration = (exit_time - entry_time).total_seconds() / 3600  # Convert seconds to hours

                # Example billing rate (you can modify this to your rate structure)
                rate_per_hour = 12  # Assume 10 currency units per hour
                parking_bill = round(duration * rate_per_hour, 2)

                # Update the vehicle record with exit time and parking bill
                cursor.execute('UPDATE vehicles SET exit_time = %s, parking_bill = %s WHERE id = %s',
                               (exit_time, parking_bill, vehicle_id))

                # Update the slot status to 'available' after the vehicle exits
                cursor.execute('UPDATE slots SET status = %s WHERE slot_number = %s', ('available', slot_number))

                mysql.connection.commit()
                flash(f'Vehicle exited. Total bill: {parking_bill}.')
                cursor.execute('UPDATE vehicles SET exit_time = %s, parking_bill = %s, status = "exited" WHERE id = %s',
               (exit_time, parking_bill, vehicle_id))
                cursor.execute('SELECT * FROM vehicles WHERE status = "active"')
                vehicles = cursor.fetchall()

        # Fetch all vehicles from the database to display
        cursor.execute('SELECT * FROM vehicles')
        vehicles = cursor.fetchall()

        return render_template('manage_vehicles.html', vehicles=vehicles)

    else:
        flash('Please login to access this page.')
        return redirect(url_for('login'))



# Vehicle Status (Available/Occupied Slots)
@app.route('/status')
def status():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        # Fetch available slots
        cursor.execute('''
            SELECT slot_number, slot_type, status
            FROM slots
            WHERE status = 'available'
        ''')
        available_slots = cursor.fetchall()
        print("Available slots:", available_slots)  # Debug print

        # Fetch occupied slots
        cursor.execute('''
            SELECT s.slot_number, s.slot_type, v.vehicle_number, v.owner_name, v.entry_time
            FROM slots s
            JOIN vehicles v ON s.slot_number = v.slot_number
            WHERE s.status = 'occupied'
        ''')
        occupied_slots = cursor.fetchall()
        print("Occupied slots:", occupied_slots)  # Debug print

    except MySQLdb.Error as e:
        print(f"Error: {e}")
        available_slots = []
        occupied_slots = []

    finally:
        cursor.close()

    return render_template('status.html', available_slots=available_slots, occupied_slots=occupied_slots)




# Admin Dashboard Route
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'loggedin' in session and session['role'] == 'admin':
        # Admin-specific functionality here
        return render_template('admin_dashboard.html')
    return redirect(url_for('login'))


# Add Slots Route
@app.route('/add_slots', methods=['GET', 'POST'])
def add_slots():
    if request.method == 'POST':
        total_slots = int(request.form['total_slots'])
        car_slots = int(request.form['car_slots'])
        bike_slots = int(request.form['bike_slots'])

        # Check if car_slots + bike_slots does not exceed total_slots
        if car_slots + bike_slots!=total_slots:
            flash('The total of car and bike slots exceeds the total parking slots!', 'danger')
            return redirect(url_for('add_slots'))

        cursor = mysql.connection.cursor()

         # Clear any existing slots
        cursor.execute('DELETE FROM slots')

        # Insert car slots
        for slot_number in range(1, car_slots + 1):
            cursor.execute('INSERT INTO slots (slot_number, slot_type, status) VALUES (%s, %s, %s)', 
                           (slot_number, 'Car', 'available'))
        
        # Insert bike slots
        for slot_number in range(car_slots + 1, total_slots + 1):
            cursor.execute('INSERT INTO slots (slot_number, slot_type, status) VALUES (%s, %s, %s)', 
                           (slot_number, 'Bike', 'available'))

        mysql.connection.commit()
        flash(f'{car_slots} car slots and {bike_slots} bike slots added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_slots.html')



# View Staff Details Route
@app.route('/staff_details')
def staff_details():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM staff')
    staff_details = cursor.fetchall()
    print(staff_details)
    return render_template('staff_details.html', staff_details=staff_details)

# Generate Parking Report Route
@app.route('/generate_report', methods=['GET','post'])
def generate_report():
    report_type = request.args.get('type', 'daily')  # Default to 'daily' if no type specified
    start_date_str=request.args.get('start_date')
    end_date_str=request.args.get('end_date')
    if not start_date_str:
        start_date = datetime.now()
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    
    if not end_date_str:
        end_date= datetime.now()
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    entries = []
    report_title = ""

    try:
        # Fetch vehicle details for the report
        if report_type == 'daily':
            query = '''
                SELECT vehicle_number, owner_name, vehicle_type, slot_number, entry_time, exit_time, parking_bill
                FROM vehicles
                WHERE DATE(entry_time) = %s
            '''
            cursor.execute(query, (start_date.strftime('%Y-%m-%d'),))
            entries = cursor.fetchall()
            report_title = f"Daily Report for {start_date.strftime('%Y-%m-%d')}"

        elif report_type == 'monthly':
            query = '''
                SELECT vehicle_number, owner_name, vehicle_type, slot_number, entry_time, exit_time, parking_bill
                FROM vehicles
                WHERE DATE(entry_time) BETWEEN %s AND %s
            '''
            cursor.execute(query, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            entries = cursor.fetchall()
            report_title = f"Monthly Report from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

        # Get total number of cars and bikes
        car_count_query = '''
            SELECT COUNT(*) as car_count FROM vehicles
            WHERE vehicle_type = 'Car' AND DATE(entry_time) BETWEEN %s AND %s
        '''
        bike_count_query = '''
            SELECT COUNT(*) as bike_count FROM vehicles
            WHERE vehicle_type = 'Bike' AND DATE(entry_time) BETWEEN %s AND %s
        '''
        cursor.execute(car_count_query, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        car_count = cursor.fetchone()['car_count']

        cursor.execute(bike_count_query, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        bike_count = cursor.fetchone()['bike_count']

        # Get total parking bill
        total_bill_query = '''
            SELECT SUM(parking_bill) as total_bill FROM vehicles
            WHERE DATE(entry_time) BETWEEN %s AND %s
        '''
        cursor.execute(total_bill_query, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        total_bill = cursor.fetchone()['total_bill']

    except Exception as e:
        flash(f"Error retrieving report: {str(e)}", 'danger')
    finally:
        cursor.close()

    # Pass the additional data (car_count, bike_count, total_bill) to the template
    return render_template('generate_report.html', 
                           entries=entries, 
                           report_title=report_title, 
                           car_count=car_count, 
                           bike_count=bike_count, 
                           total_bill=total_bill)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
if __name__ == '__main__':
    app.run(debug=True)
