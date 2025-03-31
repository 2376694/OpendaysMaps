Version 0.2 Authentication and autherization implemented

# OpendaysMaps Application

This is a Flask-based web application that allows users to register, log in, and manage their accounts for the OpendaysMaps website. It includes features like user authentication, password recovery, and session management.

---

## Features

- User registration with email and password.
- Login and logout functionality.
- Password recovery with email validation.
- Secure password storage using hashing.
- Error handling and user-friendly feedback.
- DRY principle applied for reusable templates and components.

---

## Prerequisites

Before running the application, ensure you have the following installed:

- Python 3.7 or higher
- pip (Python package manager)

---

## Setup Instructions

1. Clone the Repository
   git clone https://github.com/2376694/OpendaysMaps
   cd OpendaysMaps

2. Set Up a Virtual Environment (optional but recommended)
    python -m venv .venv
    .venv\Scripts\activate 

3. Install Dependencies: Install the required Python packages using the requirements.txt file
    pip install -r requirements.txt

4. Run the aplication
    python main.py

5. Access the Application: Open your browser and navigate to
    http://127.0.0.1:5000
