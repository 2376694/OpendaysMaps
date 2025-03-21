from flask import Flask, request, redirect, render_template_string, send_from_directory
import pyodbc
import os

app = Flask(__name__)

# Configuration
DB_SERVER = "ALI\\SQLEXPRESS"
DB_NAME = "Wlv"

# Route to serve the contact form
@app.route('/')
def contact_form():
    return send_from_directory('.', 'contact_us.html')

# Route to serve other static files
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# Route to handle form submission
@app.route('/submit-form', methods=['POST'])
def submit_form():
    try:
        # Get form data
        name = request.form.get('Name', '')
        student_id = request.form.get('ID', '')
        email = request.form.get('Email', '')
        subject = request.form.get('Subject', '')
        details = request.form.get('Details', '')
        
        # Connect to SQL Server
        conn_str = f'DRIVER={{SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};Trusted_Connection=yes;'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Insert data into database
        cursor.execute("""
            INSERT INTO contact_submissions (name, student_id, email, subject, details)
            VALUES (?, ?, ?, ?, ?)
            """, (name, student_id, email, subject, details))
        
        conn.commit()
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
        # Return error message
        return f"""
            <h1>Error</h1>
            <p>An error occurred: {str(e)}</p>
            <a href='/'>Return to form</a>
        """

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=5000)