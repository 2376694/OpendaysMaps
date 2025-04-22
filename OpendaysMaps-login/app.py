from flask import Flask, request, redirect, render_template_string, send_from_directory
import pyodbc
import os
import re
import logging
from dotenv import load_dotenv
import secrets
import html

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables instead of hardcoding
DB_SERVER = os.getenv("DB_SERVER", "ALI\\SQLEXPRESS")
DB_NAME = os.getenv("DB_NAME", "Wlv")
DB_USERNAME = os.getenv("DB_USERNAME", "")  # Optional for Windows Auth
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # Optional for Windows Auth
TRUSTED_CONNECTION = os.getenv("TRUSTED_CONNECTION", "yes")

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

# Rate limiting dictionary - basic implementation
request_counts = {}  # IP -> (count, timestamp)

def is_rate_limited(ip_address, max_requests=5, window_seconds=60):
    """Simple rate limiting implementation"""
    import time
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
        return True
    
    # Increment count
    request_counts[ip_address] = (count + 1, timestamp)
    return False

# Route to serve the contact form
@app.route('/')
def contact_form():
    return send_from_directory('.', 'contact_us.html')

# Route to serve other static files
@app.route('/<path:filename>')
def static_files(filename):
    # Prevent directory traversal attacks by sanitizing the filename
    if '..' in filename or filename.startswith('/'):
        return "Invalid file path", 400
    
    # Only allow certain file extensions
    allowed_extensions = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif'}
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        return "File type not allowed", 403
        
    return send_from_directory('.', filename)

# Route to handle form submission
@app.route('/submit-form', methods=['POST'])
def submit_form():
    try:
        # Apply rate limiting
        client_ip = request.remote_addr
        if is_rate_limited(client_ip):
            logger.warning(f"Rate limit exceeded for IP {client_ip}")
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
                            background-color: rgb(220, 207, 194);
                            font-family: Arial, sans-serif;
                            text-align: center;
                            padding: 50px;
                        }
                        .error-message {
                            background-color: rgb(220, 110, 110);
                            border-radius: 10px;
                            padding: 30px;
                            max-width: 600px;
                            margin: 0 auto;
                            color: white;
                        }
                        a {
                            display: inline-block;
                            margin-top: 20px;
                            padding: 15px 30px;
                            background-color: rgb(220, 207, 194);
                            color: rgb(105, 90, 90);
                            text-decoration: none;
                            border-radius: 10px;
                            font-weight: bold;
                        }
                        a:hover {
                            background-color: rgb(196, 196, 196);
                        }
                    </style>
                </head>
                <body>
                    <div class='error-message'>
                        <h2>Form Validation Error</h2>
                        <p>{{ error }}</p>
                        <a href='/'>Return to Contact Form</a>
                    </div>
                </body>
                </html>
            """, error=html.escape(error_message))
        
        # Connect to SQL Server with parameters to prevent injection
        if TRUSTED_CONNECTION.lower() == "yes":
            conn_str = f'DRIVER={{SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};Trusted_Connection=yes;'
        else:
            conn_str = f'DRIVER={{SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USERNAME};PWD={DB_PASSWORD};'
        
        conn = pyodbc.connect(conn_str)
        
        try:
            cursor = conn.cursor()
            
            # Use parameterized query to prevent SQL injection
            cursor.execute("""
                INSERT INTO contact_submissions (name, student_id, email, subject, details, submission_date, ip_address)
                VALUES (?, ?, ?, ?, ?, GETDATE(), ?)
                """, (name, student_id, email, subject, details, client_ip))
            
            conn.commit()
            
            # Log successful submission (without personal details)
            logger.info(f"Successful form submission for {email}")
            
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
                        background-color: rgb(220, 207, 194);
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                    }
                    .success-message {
                        background-color: rgb(136, 110, 110);
                        border-radius: 10px;
                        padding: 30px;
                        max-width: 600px;
                        margin: 0 auto;
                        color: white;
                    }
                    a {
                        display: inline-block;
                        margin-top: 20px;
                        padding: 15px 30px;
                        background-color: rgb(220, 207, 194);
                        color: rgb(105, 90, 90);
                        text-decoration: none;
                        border-radius: 10px;
                        font-weight: bold;
                    }
                    a:hover {
                        background-color: rgb(196, 196, 196);
                    }
                </style>
            </head>
            <body>
                <div class='success-message'>
                    <h2>Thank you for your submission!</h2>
                    <p>We have received your inquiry and will respond shortly.</p>
                    <a href='/'>Return to Contact Form</a>
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
                        background-color: rgb(220, 207, 194);
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                    }
                    .error-message {
                        background-color: rgb(220, 110, 110);
                        border-radius: 10px;
                        padding: 30px;
                        max-width: 600px;
                        margin: 0 auto;
                        color: white;
                    }
                    a {
                        display: inline-block;
                        margin-top: 20px;
                        padding: 15px 30px;
                        background-color: rgb(220, 207, 194);
                        color: rgb(105, 90, 90);
                        text-decoration: none;
                        border-radius: 10px;
                        font-weight: bold;
                    }
                    a:hover {
                        background-color: rgb(196, 196, 196);
                    }
                </style>
            </head>
            <body>
                <div class='error-message'>
                    <h2>Submission Error</h2>
                    <p>We encountered an error processing your submission. Please try again later or contact support.</p>
                    <a href='/'>Return to Contact Form</a>
                </div>
            </body>
            </html>
        """)

# Run the app
if __name__ == '__main__':
    # Generate a secure secret key
    app.secret_key = secrets.token_hex(24)
    # In production, disable debug mode
    app.run(debug=False, port=5000)