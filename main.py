# This is a simple Flask web application that allows users to register, log in, and manage their accounts for OpendaysMaps website.
# It uses SQLite for user data storage and includes routes for home, login, registration, password recovery, and contact us.
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'abcd'

# Database setup
DATABASE = 'users.db'


def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

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

        # Check user in the database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, password FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error=True)

    return render_template('login.html', error=False)

# Route: Register


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        # Insert user into the database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', email_exists=True)
        finally:
            conn.close()

    return render_template('register.html', email_exists=False)

# Route: Forgot Password


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Check if the email exists in the database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return render_template('forgotpassword.html', email_exists=True, redirect_to_login=True)
        else:
            return render_template('forgotpassword.html', email_exists=False, email_not_found=True)

    return render_template('forgotpassword.html', email_exists=None)

# Route: Logout


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Route: Contact Us


@app.route('/contact-us')
def contact_form():
    return send_file('Contact Us.html')


# Initialize the database and run the app
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
