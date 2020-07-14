import os

import sqlite3
import urllib
import requests
import json
from datetime import datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Expires'] = 0
    response.headers['Pragma'] = 'no-cache'
    return response

# Custom filter


# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_FILE_DIR'] = mkdtemp()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Configure CS50 Library to use SQLite database


# Make sure API key is set
#if not os.environ.get('API_KEY'):
    #raise RuntimeError('API_KEY not set')



@app.route('/')
def index():
    '''Homepage'''
    user = session.get("user")

    return render_template('index.html', user=user)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    user = session.get("user")
    if request.method == "GET":
        return render_template("register.html", user=user)
    else:
        db = sqlite3.connect("app.db")
        c = db.cursor()
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")
        if not username:
            return render_template("register.html", message="Username not valid", email=email, user=user)
        existing_users = c.execute("SELECT username FROM users").fetchall()
        if len(existing_users) != 0:
            if (username, ) in existing_users:
                db.close()
                return render_template("register.html", message="Username already exists", email=email, user=user)
        existing_emails = c.execute("SELECT email FROM users").fetchall()
        if len(existing_emails) != 0:
            if (email, ) in existing_emails:
                db.close()
                return render_template("register.html", message="Email address already registered", username=username, user=user)
        if not password:
            return render_template("register.html", message="Password invalid", username=username, email=email, user=user)
        if not password_confirm:
            return render_template("register.html", message="Passwords did not match", username=username, email=email, user=user)
        if password != password_confirm:
            return render_template("register.html", message="Passwords did not match", username=username, email=email, user=user)
        data = (username, email, generate_password_hash(password))
        sql = "INSERT INTO users (username, email, hash) VALUES (?, ?, ?)"
        c.execute(sql, data)
        db.commit()
        db.close()
        return redirect("/login")
    return render_template("index.html", user=user)



@app.route('/login', methods=['GET', 'POST'])
def login():
    '''Log user in'''
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Ensure username was submitted
        if not username:
            return render_template('login.html', message='Username not valid', user=user)

        # Ensure password was submitted
        elif not password:
            return render_template('login.html', message='Password is required', user=user)

        # Query database for username
        db = sqlite3.connect('app.db')
        c = db.cursor()
        rows = c.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][3], password):
            return render_template('login.html', message='Invalid username and/or password', user=user)

        # Remember which user has logged in
        session['user'] = username

        # Redirect user to home page
        return redirect('/')

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('login.html', user=user)


@app.route('/logout')
def logout():
    '''Log user out'''
    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect('/')




@app.route('/members/<username>')
def members(username):
    ''' Member profile page '''
    user = session.get("user")

    # Query database for username
    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('SELECT * FROM cards WHERE owner = ? ORDER BY card_name', (username,)).fetchall()
    return render_template("members.html", user=user, member=username, rows=rows)

@app.route('/contact/<username>', methods=["GET", "POST"])
@login_required
def contact(username):
    ''' Send email to user '''
    user = session.get("user")

    if request.method == "GET":
        db = sqlite3.connect('app.db')
        c = db.cursor()
        rows = c.execute('SELECT * FROM cards WHERE owner = ? ORDER BY card_name', (username,)).fetchall()
        return render_template("contact.html", user=user, member=username, rows=rows)
    else:
        # card_list = request.form.getlist("card_list")
        sender = request.form.get("sender")
        receiver = request.form.get("receiver")
        message = request.form.get("message")
        timestamp = datetime.now()
        db = sqlite3.connect('app.db')
        c = db.cursor()
        data = (sender, receiver, message, timestamp)
        sql = "INSERT INTO messages (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)"
        c.execute(sql, data)
        db.commit()
        db.close()
        return redirect("/")


def errorhandler(e):
    '''Handle error'''
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
    


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
