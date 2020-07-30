import os

import sqlite3
import urllib
import requests
import json
import glob
import http.client
from datetime import datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import apology, login_required

# Configure application
app = Flask(__name__)

ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'bmp']
basedir = os.path.abspath(os.path.dirname(__file__))

# Ensure templates are auto-reloaded
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Expires'] = 0
    response.headers['Pragma'] = 'no-cache'
    return response



# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_FILE_DIR'] = mkdtemp()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)



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
            return render_template('login.html', message='Username not valid')

        # Ensure password was submitted
        elif not password:
            return render_template('login.html', message='Password is required')

        # Query database for username
        db = sqlite3.connect('app.db')
        c = db.cursor()
        rows = c.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][3], password):
            return render_template('login.html', message='Invalid username and/or password')

        # Remember which user has logged in
        session['user_id'] = rows[0][0]
        session['user'] = rows[0][1]

        # Redirect user to home page
        return redirect('/')

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('login.html')


@app.route('/logout')
def logout():
    '''Log user out'''
    # Forget any user_id
    session.clear()

    return redirect('/')



@app.route('/account')
@login_required
def account():
    '''Manage user's account'''
    user = session.get("user")
    user_id = session.get("user_id")

    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('SELECT * FROM pets WHERE owner = ?', (user_id,)).fetchall()
    
    return render_template("account.html", user=user, rows=rows)




@app.route('/members/<username>')
def members(username):
    ''' Member profile page '''
    user = session.get("user")

    # Query database for username
    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchall()
    if len(rows) > 0:
        return render_template("members.html", user=user, member=username)
    else:
        return redirect("/")



@app.route('/contact/<username>', methods=["GET", "POST"])
@login_required
def contact(username):
    ''' Send message to user '''
    user = session.get("user")
    user_id = session.get("user_id")

    if request.method == "GET":
        # Query database for username
        db = sqlite3.connect('app.db')
        c = db.cursor()
        rows = c.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchall()
        if len(rows) > 0:
            return render_template("contact.html", user=user, user_id=user_id, member=username, member_id=rows[0][0])
        else:
            return redirect("/")

    else:
        sender = request.form.get("sender")
        receiver = request.form.get("receiver")
        message = request.form.get("message")
        subject = request.form.get("subject")
        timestamp = datetime.now()

        # Query database for thread
        db = sqlite3.connect('app.db')
        c = db.cursor()
        data = (sender, receiver, subject, sender, receiver, subject)
        sql = "SELECT id FROM threads WHERE (user1 = ? AND user2 = ? AND subject = ?) OR (user2 = ? AND user1 = ? AND subject = ?)"
        rows = c.execute(sql, data).fetchall()
        if len(rows) > 0:
            thread_id = rows[0][0]
            c.execute("UPDATE threads SET latest = ? WHERE id = ?", (timestamp, thread_id))
        else:
            c.execute("INSERT INTO threads (user1, user2, latest, subject) VALUES (?, ?, ?, ?)", (sender, receiver, timestamp, subject))
            thread_id = c.execute("SELECT id FROM threads WHERE (user1 = ? AND user2 = ? AND subject = ?)", (sender, receiver, subject)).fetchall()[0][0]
        
        message_data = (sender, thread_id, message, timestamp)
        message_sql = "INSERT INTO messages (sender, thread_id, message, timestamp) VALUES (?, ?, ?, ?)"
        c.execute(message_sql, message_data)
        db.commit()
        db.close()
        return redirect("/")



@app.route('/messages')
@login_required
def message_threads():
    ''' View user's messages '''
    user = session.get("user")
    user_id = session.get("user_id")

    # Query database for threads
    db = sqlite3.connect('app.db')
    c = db.cursor()
    threads = c.execute('''
        SELECT t.*, u.username as counterpart_username FROM (
        SELECT id, user2 as counterpart, latest, subject from threads where user1 = ?
        union all
        SELECT id, user1 as counterpart, latest, subject from threads where user2 = ?
        ) t
        LEFT JOIN users u on u.id = t.counterpart
        ORDER BY latest DESC
    ''', (user_id, user_id)).fetchall()

    return render_template("threads.html", user=user, threads=threads)



@app.route('/messages/<thread_id>')
@login_required
def messages(thread_id):
    ''' View user's messages '''
    user = session.get("user")
    user_id = session.get("user_id")

    # Check if user is in thread
    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('''
        SELECT * FROM threads WHERE (id = ? AND user1 = ?) OR (id = ? AND user2 = ?)
    ''', (thread_id, user_id, thread_id, user_id)).fetchall()
    if len(rows) == 0:
        return redirect("/")

    # Query database for messages
    messages = c.execute('''
        SELECT m.*, u.username AS from_user, t.user1, t.user2, t.subject FROM messages m 
        LEFT JOIN users u ON u.id = m.sender
		LEFT JOIN threads t on m.thread_id = t.id
        WHERE thread_id = ?
    ''', (thread_id)).fetchall()

    return render_template("messages.html", user=user, user_id=user_id, messages=messages)



@app.route("/pets")
def pets0():
    user = session.get("user")

    db = sqlite3.connect('app.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = db.cursor()
    pets = c.execute('''SELECT p.id, p.owner, p.name, p.age, p.gender, p.animal, p.breed, p.entry_date as "[timestamp]", p.description, ph.filename FROM pets p
                        LEFT JOIN (SELECT pet_id, filename FROM photos GROUP BY pet_id) ph
                        ON ph.pet_id = p.id''').fetchall()
    breeds = c.execute('SELECT DISTINCT breed FROM pets').fetchall()
    ages = c.execute('SELECT DISTINCT age FROM pets').fetchall()
    genders = c.execute('SELECT DISTINCT gender FROM pets').fetchall()

    current = datetime.now()

    return render_template("pets.html", user=user, pets=pets, breeds=breeds, ages=ages, genders=genders, current=current)


@app.route("/pets/<animal>")
def pets(animal):
    user = session.get("user")

    if animal not in ['cats', 'dogs']:
        return redirect("/pets")

    animal = animal.capitalize()[:-1]
    print(animal)

    db = sqlite3.connect('app.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = db.cursor()
    pets = c.execute('''SELECT p.id, p.owner, p.name, p.age, p.gender, p.animal, p.breed, p.entry_date as "[timestamp]", p.description, ph.filename FROM pets p
                        LEFT JOIN (SELECT pet_id, filename FROM photos GROUP BY pet_id) ph
                        ON ph.pet_id = p.id WHERE p.animal = ?''', (animal, )).fetchall()
    breeds = c.execute('SELECT DISTINCT breed FROM pets WHERE animal = ?', (animal, )).fetchall()
    ages = c.execute('SELECT DISTINCT age FROM pets WHERE animal = ?', (animal, )).fetchall()
    genders = c.execute('SELECT DISTINCT gender FROM pets WHERE animal = ?', (animal, )).fetchall()

    current = datetime.now()

    return render_template("pets.html", user=user, pets=pets, breeds=breeds, ages=ages, genders=genders, current=current)



@app.route("/pets/<animal>/<pet_id>")
def pets_detail(animal, pet_id):
    user = session.get("user")
    user_id = session.get("user_id")

    db = sqlite3.connect('app.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = db.cursor()
    details = c.execute('SELECT id, owner, name, age, gender, animal, breed, entry_date as "[timestamp]", description FROM pets WHERE id = ?', (pet_id, )).fetchall()[0]
    if len(details) < 1:
        return redirect("/pets")
    owner = c.execute('SELECT * FROM users WHERE id = (SELECT owner FROM pets WHERE id = ?)', (pet_id, )).fetchall()[0]
    photos = c.execute('SELECT * FROM photos WHERE pet_id = ?',(pet_id, )).fetchall()

    return render_template("pet_detail.html", user=user, user_id=user_id, details=details, owner=owner, photos=photos)



@app.route("/add_pet", methods=["GET", "POST"])
@login_required
def add_pet():
    user = session.get("user")
    user_id = session.get("user_id")

    if request.method == "GET":
        cats = get_cat_breeds()
        dogs = get_dog_breeds()
        return render_template("add_pet.html", user=user, user_id = user_id, dogs=dogs, cats=cats)
    else: 
        owner = request.form.get("owner")
        name = request.form.get("name")
        age = request.form.get("age")
        gender = request.form.get("gender")
        animal = request.form.get("animal")
        breed = request.form.get("breed")
        description = request.form.get("description")

        entry_date = datetime.now()

        db = sqlite3.connect("app.db")
        c = db.cursor()
        data = (owner, name, age, gender, animal, breed, entry_date, description)
        sql = "INSERT INTO pets (owner, name, age, gender, animal, breed, entry_date, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        c.execute(sql, data)
        db.commit()

        pet_id = str(c.execute("SELECT id FROM pets WHERE entry_date = ?", (entry_date,)).fetchall()[0][0])

        path = "static/uploads/" + pet_id
        os.mkdir(path)

        images = []
        for file in glob.glob(path + "/*"):
            images.append(file)

        for photo in ['photo1', 'photo2', 'photo3', 'photo4']:
            if photo in request.files:
                file = request.files[photo]
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        i = 1
                        while path + "/" + filename in images:
                            filename = secure_filename(file.filename).rsplit('.', 1)[0] + str(i) + secure_filename(file.filename).rsplit('.', 1)[1]
                            i += 1
                        file.save(os.path.join(basedir, path + "/", filename))
                        c.execute("INSERT INTO photos (pet_id, filename) VALUES (?, ?)", (pet_id, filename))
                        db.commit()
        
        db.close()

        #add_photo(pet_id, )

        return redirect("/pets")



@app.route("/catapi", methods=["GET", "POST"])
def catapi():
    
    conn = http.client.HTTPSConnection("api.thecatapi.com")

    headers = { 'x-api-key': "7737b5f1-f53b-4225-b781-d0b80604ebab" }

    conn.request("GET", "/v1/breeds?attach_breed=0", headers=headers)

    res = conn.getresponse()
    data = res.read()
    j = json.loads(data.decode("utf-8"))

    return render_template("cats.html", cats=j)



@app.route("/dogapi", methods=["GET", "POST"])
def dogapi():
    

    conn = http.client.HTTPSConnection("api.thedogapi.com")

    headers = { 'x-api-key': "3a2b00e5-a4b0-4618-8181-43a3192048fd" }

    conn.request("GET", "/v1/breeds?attach_breed=0", headers=headers)

    res = conn.getresponse()
    data = res.read()
    j = json.loads(data.decode("utf-8"))

    return render_template("cats.html", cats=j)



@app.route("/test", methods=["GET", "POST"])
#@login_required
def test():
    '''test to upload photos'''
    images = []
    for file in glob.glob("static/uploads/*"):
        images.append(file)
        print(file)
    if request.method == "GET":
        print("GET")
        return render_template("test.html", images=images)
    else:
        print("POST")
        # check if the post request has the file part
        if 'file' not in request.files:
            print("No file part")
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            print("No selected file")
            return redirect(request.url)
        # file = request.form.get("file")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            print(filename)
            i = 1
            while "static/uploads/" + filename in images:
                filename = secure_filename(file.filename).rsplit('.', 1)[0] + str(i) + secure_filename(file.filename).rsplit('.', 1)[1]
                i += 1
            file.save(os.path.join(basedir, "static/uploads", filename))
        return redirect(request.url)


def errorhandler(e):
    '''Handle error'''
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
    

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_cat_breeds():
    cats = []
    f = open("static/txt/cats.txt", "r")
    for line in f:
        cats.append(line)
    return cats

def get_dog_breeds():
    dogs = []
    f = open("static/txt/dogs.txt", "r")
    for line in f:
        dogs.append(line)
    return dogs


def add_photo(pet_id, file):
    images = []
    for file in glob.glob("static/uploads/" + pet_id + "/*"):
        images.append(file)
    file = request.files['file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        print("No selected file")
        return redirect(request.url)
    # file = request.form.get("file")
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        print(filename)
        i = 1
        while "static/uploads/" + filename in images:
            filename = secure_filename(file.filename).rsplit('.', 1)[0] + str(i) + secure_filename(file.filename).rsplit('.', 1)[1]
            i += 1
        file.save(os.path.join(basedir, "static/uploads", filename))


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
