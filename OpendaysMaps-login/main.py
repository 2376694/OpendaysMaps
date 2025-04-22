# OpendaysMaps application with authentication and form submission
import os
import sqlite3
import re
import logging
import secrets
import time
import pyodbc
import html
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'abcd')  # Use env variable if available

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
SQLITE_DATABASE = 'users.db'
SQL_SERVER = os.getenv("DB_SERVER", "ALI\\SQLEXPRESS")
SQL_DATABASE = os.getenv("DB_NAME", "Wlv")
SQL_USERNAME = os.getenv("DB_USERNAME", "")
SQL_PASSWORD = os.getenv("DB_PASSWORD", "")
TRUSTED_CONNECTION = os.getenv("TRUSTED_CONNECTION", "yes")

# Rate limiting dictionary - basic implementation
request_counts = {}  # IP -> (count, timestamp)

def is_rate_limited(ip_address, max_requests=5, window_seconds=60):
    """Simple rate limiting implementation"""
    current_time = time.time()
    
    # Remove old entries
    for ip in list(request_counts.keys()):
        if current_time - request_counts[ip][1] > window_seconds:
            del request_counts[ip]
    
    if ip_address not in request_counts:
        request_counts[ip_address] = (1, current_time)
        return False
    
    count, timestamp = request_counts[ip_address]
    if current_time - timestamp > window_seconds:
        # Reset if window has passed
        request_counts[ip_address] = (1, current_time)
        return False
    
    if count >= max_requests:
        logger.warning(f"Rate limit exceeded for IP {ip_address}")
        return True
    
    # Increment count
    request_counts[ip_address] = (count + 1, timestamp)
    return False

def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(SQLITE_DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("SQLite database initialized")

# Input validation functions
def validate_name(name):
    """Validate name is alphanumeric with spaces, max 100 chars"""
    if not name or len(name) > 100:
        return False
    return bool(re.match(r'^[A-Za-z0-9\s\-\'\.]{1,100}$', name))

def validate_student_id(student_id):
    """Validate student ID is in correct format"""
    if not student_id:
        return True  # Student ID can be optional
    return bool(re.match(r'^[0-9]{7,8}$', student_id))

def validate_email(email):
    """Validate email address format"""
    if not email or len(email) > 120:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def validate_subject(subject):
    """Validate subject is reasonable text, max 200 chars"""
    if not subject or len(subject) > 200:
        return False
    return bool(re.match(r'^[A-Za-z0-9\s\-\'\.,:;!?()]{1,200}$', subject))

def validate_details(details):
    """Validate details field, max 2000 chars"""
    return details is not None and len(details) <= 2000

# Route: Home (requires login)
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    home_file_path = os.path.join(os.getcwd(), 'Home.html')
    return send_file(home_file_path)

# Route: Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Apply rate limiting
        client_ip = request.remote_addr
        if is_rate_limited(client_ip, max_requests=3):
            flash('Too many login attempts. Please try again later.', 'danger')
            return render_template('login.html', error=True)

        # Check user in the database
        conn = sqlite3.connect(SQLITE_DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, password FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            logger.info(f"Successful login for {email}")
            return redirect(url_for('home'))
        else:
            logger.warning(f"Failed login attempt for {email}")
            return render_template('login.html', error=True)

    return render_template('login.html', error=False)

# Route: Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        # Apply rate limiting
        client_ip = request.remote_addr
        if is_rate_limited(client_ip, max_requests=2):
            flash('Too many registration attempts. Please try again later.', 'danger')
            return render_template('register.html', email_exists=False)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        # Insert user into the database
        conn = sqlite3.connect(SQLITE_DATABASE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_password))
            conn.commit()
            logger.info(f"New user registered: {email}")
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            logger.warning(f"Registration attempt with existing email: {email}")
            return render_template('register.html', email_exists=True)
        finally:
            conn.close()

    return render_template('register.html', email_exists=False)

# Route: Forgot Password
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Apply rate limiting
        client_ip = request.remote_addr
        if is_rate_limited(client_ip, max_requests=3):
            flash('Too many password reset attempts. Please try again later.', 'danger')
            return render_template('forgotpassword.html', email_exists=None)

        # Check if the email exists in the database
        conn = sqlite3.connect(SQLITE_DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            logger.info(f"Password reset requested for {email}")
            return render_template('forgotpassword.html', email_exists=True, redirect_to_login=True)
        else:
            logger.warning(f"Password reset attempted for non-existent email: {email}")
            return render_template('forgotpassword.html', email_exists=False, email_not_found=True)

    return render_template('forgotpassword.html', email_exists=None)

# Route: Logout
@app.route('/logout')
def logout():
    if 'user_id' in session:
        logger.info(f"User {session['user_id']} logged out")
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Route: Contact Us
@app.route('/contact-us')
def contact_form():
    file_path = os.path.join(os.getcwd(), 'Contact Us.html')
    return send_file(file_path)

# Route to serve static files
@app.route('/<path:filename>')
def serve_files(filename):
    # Prevent directory traversal attacks
    if '..' in filename or filename.startswith('/'):
        logger.warning(f"Attempted directory traversal: {filename}")
        return "Invalid file path", 400
    
    try:
        return send_file(filename)
    except Exception as e:
        logger.error(f"Error serving {filename}: {e}")
        return f"File not found: {filename}", 404

# Route to handle form submission
@app.route('/submit-form', methods=['POST'])
def submit_form():
    try:
        # Apply rate limiting
        client_ip = request.remote_addr
        if is_rate_limited(client_ip):
            logger.warning(f"Rate limit exceeded for form submission from IP {client_ip}")
            return "Too many submissions, please try again later", 429
        
        # Get and validate form data
        name = request.form.get('Name', '').strip()
        student_id = request.form.get('ID', '').strip()
        email = request.form.get('Email', '').strip()
        subject = request.form.get('Subject', '').strip()
        details = request.form.get('Details', '').strip()
        
        # Validate all inputs
        validation_errors = []
        if not validate_name(name):
            validation_errors.append("Invalid name format")
        if not validate_student_id(student_id):
            validation_errors.append("Invalid student ID format")
        if not validate_email(email):
            validation_errors.append("Invalid email format")
        if not validate_subject(subject):
            validation_errors.append("Invalid subject format")
        if not validate_details(details):
            validation_errors.append("Details too long or invalid")
            
        if validation_errors:
            error_message = "Validation errors: " + ", ".join(validation_errors)
            logger.warning(error_message)
            return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Validation Error</title>
                    <style>
                        body {
                            background-color: #F5F5F5;
                            font-family: Arial, sans-serif;
                            text-align: center;
                            padding: 50px;
                        }
                        .error-message {
                            background-color: #003A70;
                            border-radius: 10px;
                            padding: 30px;
                            max-width: 600px;
                            margin: 0 auto;
                            color: #FFD100;
                        }
                        a {
                            display: inline-block;
                            margin-top: 20px;
                            padding: 15px 30px;
                            background-color: #FFD100;
                            color: #003A70;
                            text-decoration: none;
                            border-radius: 10px;
                            font-weight: bold;
                        }
                        a:hover {
                            background-color: #e6be00;
                        }
                    </style>
                </head>
                <body>
                    <div class='error-message'>
                        <h2>Form Validation Error</h2>
                        <p>{{ error }}</p>
                        <a href='/contact-us'>Return to Contact Form</a>
                    </div>
                </body>
                </html>
            """, error=html.escape(error_message))
        
        # Connect to SQL Server with parameters to prevent injection
        if TRUSTED_CONNECTION.lower() == "yes":
            conn_str = f'DRIVER={{SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};Trusted_Connection=yes;'
        else:
            conn_str = f'DRIVER={{SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USERNAME};PWD={SQL_PASSWORD};'
        
        conn = pyodbc.connect(conn_str)
        
        try:
            cursor = conn.cursor()
            
            # Use parameterized query to prevent SQL injection
            print(f"Inserting form data into database: {name}, {student_id}, {email}")
            cursor.execute("""
                INSERT INTO contact_submissions (name, student_id, email, subject, details, submission_date, ip_address)
                VALUES (?, ?, ?, ?, ?, GETDATE(), ?)
                """, (name, student_id, email, subject, details, client_ip))
            
            conn.commit()
            
            # Log successful submission (without personal details)
            logger.info(f"Successfully saved form submission from {email}")
            
        finally:
            conn.close()
        
        # Return success message
        return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Submission Successful</title>
                <style>
                    body {
                        background-color: #F5F5F5;
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                    }
                    .success-message {
                        background-color: #003A70;
                        border-radius: 10px;
                        padding: 30px;
                        max-width: 600px;
                        margin: 0 auto;
                        color: #FFD100;
                    }
                    a {
                        display: inline-block;
                        margin-top: 20px;
                        padding: 15px 30px;
                        background-color: #FFD100;
                        color: #003A70;
                        text-decoration: none;
                        border-radius: 10px;
                        font-weight: bold;
                    }
                    a:hover {
                        background-color: #e6be00;
                    }
                </style>
            </head>
            <body>
                <div class='success-message'>
                    <h2>Thank you for your submission!</h2>
                    <p>We have received your inquiry and will respond shortly.</p>
                    <a href='/'>Return to Home</a>
                </div>
            </body>
            </html>
        """)
        
    except Exception as e:
        # Log the error (without exposing details to user)
        logger.error(f"Error in form submission: {str(e)}")
        
        # Return generic error message (without exposing exception details)
        return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Submission Error</title>
                <style>
                    body {
                        background-color: #F5F5F5;
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                    }
                    .error-message {
                        background-color: #003A70;
                        border-radius: 10px;
                        padding: 30px;
                        max-width: 600px;
                        margin: 0 auto;
                        color: #FFD100;
                    }
                    a {
                        display: inline-block;
                        margin-top: 20px;
                        padding: 15px 30px;
                        background-color: #FFD100;
                        color: #003A70;
                        text-decoration: none;
                        border-radius: 10px;
                        font-weight: bold;
                    }
                    a:hover {
                        background-color: #e6be00;
                    }
                </style>
            </head>
            <body>
                <div class='error-message'>
                    <h2>Submission Error</h2>
                    <p>We encountered an error processing your submission. Please try again later or contact support.</p>
                    <a href='/contact-us'>Return to Contact Form</a>
                </div>
            </body>
            </html>
        """)

# Initialize the database and run the app
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)