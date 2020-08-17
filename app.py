import os

import sqlite3
import urllib
import requests
import json
import glob
import http.client
import shutil
import random
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
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect("app.db")
    c = db.cursor()
    latest = c.execute('''
    SELECT * FROM pets p
    LEFT JOIN (SELECT pet_id, filename FROM photos GROUP BY pet_id) ph
    ON ph.pet_id = p.id
    ORDER BY entry_date DESC
    LIMIT 4
    ''').fetchall()

    random_cat = get_random_cat()
    random_dog = get_random_dog()

    db.close()

    return render_template('index.html', user=user, latest=latest, unread_messages=unread_messages, random_cat=random_cat, random_dog=random_dog)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    user = session.get("user")
    unread_messages = session.get("unread_messages")

    if request.method == "GET":
        return render_template("register.html", user=user, unread_messages=unread_messages)
    else:
        db = sqlite3.connect("app.db")
        c = db.cursor()
        is_shelter = request.form.get("shelter")
        firstname = request.form.get("firstname")
        lastname = request.form.get("lastname")
        sheltername = request.form.get("sheltername")
        email = request.form.get("email")
        location = request.form.get("location")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        if not email:
            db.close()
            return render_template("register.html", message="Email not valid", email=email, user=user, unread_messages=unread_messages)
        existing_emails = c.execute("SELECT email FROM users").fetchall()
        if len(existing_emails) != 0:
            if (email, ) in existing_emails:
                db.close()
                return render_template("register.html", message="Email address already registered", user=user, unread_messages=unread_messages)
        if not password:
            db.close()
            return render_template("register.html", message="Password invalid", email=email, user=user, unread_messages=unread_messages)
        if not password_confirm:
            db.close()
            return render_template("register.html", message="Passwords did not match", email=email, user=user, unread_messages=unread_messages)
        if password != password_confirm:
            db.close()
            return render_template("register.html", message="Passwords did not match", email=email, user=user, unread_messages=unread_messages)
        
        if is_shelter == 'No':
            data = (is_shelter, firstname, lastname, email, location, generate_password_hash(password))
            sql = "INSERT INTO users (shelter, firstname, lastname, email, location, hash) VALUES (?, ?, ?, ?, ?, ?)"
        elif is_shelter == 'Yes':
            data = (is_shelter, sheltername, email, location, generate_password_hash(password))
            sql = "INSERT INTO users (shelter, sheltername, email, location, hash) VALUES (?, ?, ?, ?, ?)"
        c.execute(sql, data)
        db.commit()
        db.close()
        return redirect("/login")
    return render_template("index.html", user=user, unread_messages=unread_messages)



@app.route('/login', methods=['GET', 'POST'])
def login():
    '''Log user in'''
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Ensure email was submitted
        if not email:
            return render_template('login.html', message='Email not valid')

        # Ensure password was submitted
        elif not password:
            return render_template('login.html', message='Password is required')

        # Query database for email
        db = sqlite3.connect('app.db')
        c = db.cursor()
        rows = c.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchall()

        # Ensure email exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][7], password):
            db.close()
            return render_template('login.html', message='Invalid email and/or password')

        # Remember which user has logged in
        session['user_id'] = rows[0][0]
        if rows[0][1] == 'Yes':
            session['user'] = rows[0][4]
        elif rows[0][1] == 'No':
            session['user'] = rows[0][2] + ' ' + rows[0][3]

        # Check if user has unread messages
        session['unread_messages'] = c.execute("SELECT COUNT(thread_id) FROM messages WHERE read IS NULL AND sender <> ?", (rows[0][0],)).fetchall()[0][0]

        # Redirect user to home page
        db.close()
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



@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    '''Manage user's account'''
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchall()

    if request.method == 'GET':
        db.close()
        return render_template("account.html", user=user, unread_messages=unread_messages, rows=rows[0])
    
    else:
        firstname = request.form.get("firstname")
        lastname = request.form.get("lastname")
        sheltername = request.form.get("sheltername")
        location = request.form.get("location")
        phone = request.form.get("phone")
        website = request.form.get("website")
        facebook = request.form.get("facebook")
        instagram = request.form.get("instagram")
        twitter = request.form.get("twitter")

        if rows[0][1] == 'No':
            data = (firstname, lastname, location, phone, website, facebook, instagram, twitter, user_id)
            sql = "UPDATE users SET firstname = ?, lastname = ?, location = ?, phone = ?, website = ?, facebook = ?, instagram = ?, twitter = ? WHERE id = ?"
        elif rows[0][1] == 'Yes':
            data = (sheltername, location, phone, website, facebook, instagram, twitter, user_id)
            sql = "UPDATE users SET sheltername = ?, location = ?, phone = ?, website = ?, facebook = ?, instagram = ?, twitter = ? WHERE id = ?"
        c.execute(sql, data)
        db.commit()

        if rows[0][1] == 'Yes':
            session['user'] = sheltername
        elif rows[0][1] == 'No':
            session['user'] = firstname + ' ' + lastname
        user = session.get("user")
        rows = c.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchall()
        db.close()
        message = "Account details updated successfully"
        return render_template("account.html", user=user, unread_messages=unread_messages, rows=rows[0], message=message)


@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    '''Manage user's account'''
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchall()
    
    if request.method == 'GET':
        db.close()
        return render_template("change_password.html", user=user, unread_messages=unread_messages, rows=rows[0])
    
    else:
        email = request.form.get("email")
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        password_confirm = request.form.get("password_confirm")

        if not check_password_hash(rows[0][7], current_password):
            db.close()
            message = "Current password is incorrect"
            return render_template("change_password.html", user=user, unread_messages=unread_messages, rows=rows[0], message=message)

        if new_password:
            data = (email, generate_password_hash(new_password), user_id)
            sql = "UPDATE users SET email = ?, hash = ? WHERE id = ?"
        else:
            data = (email, user_id)
            sql = "UPDATE users SET email = ? WHERE id = ?"
        c.execute(sql, data)
        db.commit()
        
        rows = c.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchall()
        db.close()
        message = "Email and password updated successfully"
        return render_template("change_password.html", user=user, unread_messages=unread_messages, rows=rows[0], message=message)


@app.route('/account/pets')
@login_required
def mypets():
    '''Manage user's account'''
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('SELECT * FROM pets WHERE owner = ?', (user_id,)).fetchall()
    
    db.close()
    return render_template("mypets.html", user=user, unread_messages=unread_messages, rows=rows)


@app.route('/about')
def learn():
    user = session.get("user")
    unread_messages = session.get("unread_messages")

    return render_template("learn.html", user=user, unread_messages=unread_messages)


@app.route('/members/<member_id>')
def members(member_id):
    ''' Member profile page '''
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    # Query database for member_id
    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('SELECT * FROM users WHERE id = ?', (member_id,)).fetchall()
    if len(rows) > 0:
        member = rows[0]
        pets = c.execute('''
        SELECT p.id, p.owner, p.name, p.age, p.gender, p.animal, p.breed, p.entry_date as "[timestamp]", p.description, ph.filename FROM pets p
        LEFT JOIN (SELECT pet_id, filename FROM photos GROUP BY pet_id) ph
        ON ph.pet_id = p.id WHERE p.owner = ?
        ''', (member_id, )).fetchall()
        return render_template("members.html", user=user, user_id=user_id, unread_messages=unread_messages, member=member, pets=pets)
    else:
        db.close()
        return redirect("/")



@app.route('/contact/<member_id>', methods=["GET", "POST"])
@login_required
def contact(member_id):
    ''' Send message to user '''
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    if request.method == "GET":
        # Query database for member_id
        db = sqlite3.connect('app.db')
        c = db.cursor()
        rows = c.execute('SELECT * FROM users WHERE id = ?', (member_id,)).fetchall()
        if len(rows) > 0:
            if rows[0][1] == 'Yes':
                member = rows[0][4]
            elif rows[0][1] == 'No':
                member = rows[0][2] + ' ' + rows[0][3]
                db.close()
            return render_template("contact.html", user=user, unread_messages=unread_messages, user_id=user_id, member=member, member_id=rows[0][0])
        else:
            db.close()
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
        return redirect("/messages/" + str(thread_id))



@app.route('/messages')
@login_required
def message_threads():
    ''' View user's messages '''
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    # Query database for threads
    db = sqlite3.connect('app.db')
    c = db.cursor()
    threads = c.execute('''
        SELECT t.*, CASE u.shelter
		WHEN 'No' then u.firstname || ' ' || u.lastname
		WHEN 'Yes' then u.sheltername
		END as counterpart_name
		FROM (
        SELECT id, user2 as counterpart, latest, subject from threads where user1 = ?
        union all
        SELECT id, user1 as counterpart, latest, subject from threads where user2 = ?
        ) t
        LEFT JOIN users u on u.id = t.counterpart
        ORDER BY latest DESC
    ''', (user_id, user_id)).fetchall()

    unread_threads = []
    rows = c.execute("SELECT DISTINCT thread_id FROM messages WHERE read IS NULL AND sender <> ?", (user_id, )).fetchall()
    for row in rows:
        unread_threads.append(row[0])

    db.close()
    return render_template("threads.html", user=user, unread_messages=unread_messages, threads=threads, unread_threads=unread_threads)



@app.route('/messages/<thread_id>')
@login_required
def messages(thread_id):
    ''' View user's messages '''
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    # Check if user is in thread
    db = sqlite3.connect('app.db')
    c = db.cursor()
    rows = c.execute('''
        SELECT * FROM threads WHERE (id = ? AND user1 = ?) OR (id = ? AND user2 = ?)
    ''', (thread_id, user_id, thread_id, user_id)).fetchall()
    if len(rows) == 0:
        db.close()
        return redirect("/")

    # Query database for messages
    messages = c.execute('''
        SELECT m.*, u.shelter, u.firstname, u.lastname, u.sheltername, t.user1, t.user2, t.subject FROM messages m 
        LEFT JOIN users u ON u.id = m.sender
		LEFT JOIN threads t on m.thread_id = t.id
        LEFT JOIN users u1 on t.user1 = u1.id
		LEFT JOIN users u2 on t.user2 = u2.id
        WHERE thread_id = ?
    ''', (thread_id)).fetchall()

    # Set read status
    c.execute("UPDATE messages SET read = 1 WHERE thread_id = ? AND sender <> ?", (thread_id, user_id))

    # Check for more unread messages
    session['unread_messages'] = c.execute("SELECT COUNT(thread_id) FROM messages WHERE read IS NULL AND sender <> ?", (user_id,)).fetchall()[0][0]
    unread_messages = session.get("unread_messages")

    db.commit()
    db.close()

    return render_template("messages.html", user=user, unread_messages=unread_messages, user_id=user_id, messages=messages)



@app.route("/pets")
def pets0():
    user = session.get("user")
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect('app.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = db.cursor()
    query = '''
    SELECT p.id, p.owner, p.name, p.age, p.gender, p.animal, p.breed, p.entry_date as "[timestamp]", p.description, ph.filename FROM pets p
    LEFT JOIN (SELECT pet_id, filename FROM photos GROUP BY pet_id) ph
    ON ph.pet_id = p.id
    '''

    breed_filters = []
    age_filters = []
    gender_filters = []

    for key, value in request.args.items():
        if key[:5] == 'breed' and value == 'on':
            breed_filters.append(key[5:])
        elif key[:3] == 'age' and value == 'on':
            age_filters.append(key[3:])
        elif key[:6] == 'gender' and value == 'on':
            gender_filters.append(key[6:])

    filters = breed_filters + age_filters + gender_filters
            

    if len(breed_filters) + len(age_filters) + len(gender_filters) > 0:
        query += ' WHERE '
    
    if len(breed_filters) > 0:
        query += 'p.breed IN ('
        for i in range(len(breed_filters)):
            query += '"' + breed_filters[i] + '"'
            if i < len(breed_filters) - 1:
                query += ', '
        query += ')'
        if len(age_filters) + len(gender_filters) > 0:
            query += ' AND '

    if len(age_filters) > 0:
        query += 'p.age IN ('
        for i in range(len(age_filters)):
            query += '"' + age_filters[i] + '"'
            if i < len(age_filters) - 1:
                query += ', '
        query += ')'
        if len(gender_filters) > 0:
            query += ' AND '

    if len(gender_filters) > 0:
        query += 'p.gender IN ('
        for i in range(len(gender_filters)):
            query += '"' + gender_filters[i] + '"'
            if i < len(gender_filters) - 1:
                query += ', '
        query += ')'


    query += ' ORDER BY entry_date DESC'
    pets = c.execute(query).fetchall()
    breeds = c.execute('SELECT DISTINCT breed FROM pets').fetchall()
    ages = c.execute('SELECT DISTINCT age FROM pets').fetchall()
    genders = c.execute('SELECT DISTINCT gender FROM pets').fetchall()

    current = datetime.now()

    db.close()
    return render_template("pets.html", user=user, unread_messages=unread_messages, pets=pets, breeds=breeds, ages=ages, genders=genders, current=current, filters=filters)


@app.route("/pets/<animal>")
def pets(animal):
    user = session.get("user")
    unread_messages = session.get("unread_messages")

    if animal not in ['cats', 'dogs']:
        return redirect("/pets")

    animal = animal.capitalize()[:-1]

    db = sqlite3.connect('app.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = db.cursor()
    query = '''
    SELECT p.id, p.owner, p.name, p.age, p.gender, p.animal, p.breed, p.entry_date as "[timestamp]", p.description, ph.filename FROM pets p
    LEFT JOIN (SELECT pet_id, filename FROM photos GROUP BY pet_id) ph
    ON ph.pet_id = p.id WHERE p.animal = 
    '''
    query += '"' + animal + '" '

    breed_filters = []
    age_filters = []
    gender_filters = []

    for key, value in request.args.items():
        if key[:5] == 'breed' and value == 'on':
            breed_filters.append(key[5:])
        elif key[:3] == 'age' and value == 'on':
            age_filters.append(key[3:])
        elif key[:6] == 'gender' and value == 'on':
            gender_filters.append(key[6:])
            
    filters = breed_filters + age_filters + gender_filters


    if len(breed_filters) + len(age_filters) + len(gender_filters) > 0:
        query += ' AND '
    
    if len(breed_filters) > 0:
        query += 'p.breed IN ('
        for i in range(len(breed_filters)):
            query += '"' + breed_filters[i] + '"'
            if i < len(breed_filters) - 1:
                query += ', '
        query += ')'
        if len(age_filters) + len(gender_filters) > 0:
            query += ' AND '

    if len(age_filters) > 0:
        query += 'p.age IN ('
        for i in range(len(age_filters)):
            query += '"' + age_filters[i] + '"'
            if i < len(age_filters) - 1:
                query += ', '
        query += ')'
        if len(gender_filters) > 0:
            query += ' AND '

    if len(gender_filters) > 0:
        query += 'p.gender IN ('
        for i in range(len(gender_filters)):
            query += '"' + gender_filters[i] + '"'
            if i < len(gender_filters) - 1:
                query += ', '
        query += ')'
    

    query += ' ORDER BY entry_date DESC'
    pets = c.execute(query).fetchall()
    breeds = c.execute('SELECT DISTINCT breed FROM pets WHERE animal = ?', (animal, )).fetchall()
    ages = c.execute('SELECT DISTINCT age FROM pets WHERE animal = ?', (animal, )).fetchall()
    genders = c.execute('SELECT DISTINCT gender FROM pets WHERE animal = ?', (animal, )).fetchall()

    current = datetime.now()

    db.close()
    return render_template("pets.html", user=user, unread_messages=unread_messages, pets=pets, breeds=breeds, ages=ages, genders=genders, current=current, filters=filters)



@app.route("/pets/<animal>/<pet_id>")
def pets_detail(animal, pet_id):
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect('app.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = db.cursor()
    details = c.execute('SELECT id, owner, name, age, gender, animal, breed, entry_date as "[timestamp]", description FROM pets WHERE id = ?', (pet_id, )).fetchall()[0]
    if len(details) < 1:
        db.close()
        return redirect("/pets")
    owner = c.execute('SELECT * FROM users WHERE id = (SELECT owner FROM pets WHERE id = ?)', (pet_id, )).fetchall()[0]
    photos = c.execute('SELECT * FROM photos WHERE pet_id = ?',(pet_id, )).fetchall()

    animal = details[5]
    breed = details[6]

    if animal == 'Dog':
        breed_details = get_dog_details(breed)
    elif animal == 'Cat':
        breed_details = get_cat_details(breed)
    else:
        breed_details = None

    db.close()
    return render_template("pet_detail.html", user=user, unread_messages=unread_messages, user_id=user_id, details=details, owner=owner, photos=photos, breed_details=breed_details)



@app.route("/add_pet", methods=["GET", "POST"])
@login_required
def add_pet():
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    if request.method == "GET":
        cats = get_cat_breeds()
        dogs = get_dog_breeds()
        return render_template("add_pet.html", user=user, unread_messages=unread_messages, user_id = user_id, dogs=dogs, cats=cats)
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
                        filename = pet_id + photo + '.' + secure_filename(file.filename).rsplit('.', 1)[1]
                        file.save(os.path.join(basedir, path + "/", filename))
                        c.execute("INSERT INTO photos (pet_id, filename) VALUES (?, ?)", (pet_id, filename))
                        db.commit()
        
        db.close()

        #add_photo(pet_id, )

        return redirect("/pets")



@app.route("/pets/<animal>/<pet_id>/edit", methods=["GET", "POST"])
@login_required
def edit_pet(animal, pet_id):
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect('app.db', detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = db.cursor()
    details = c.execute('SELECT id, owner, name, age, gender, animal, breed, entry_date as "[timestamp]", description FROM pets WHERE id = ?', (pet_id, )).fetchall()[0]
    
    if len(details) < 1:
        db.close()
        return redirect("/pets")
    if details[1] != user_id:
        db.close()
        return redirect("/")

    if request.method == "GET":
        cats = get_cat_breeds()
        dogs = get_dog_breeds()
        photos = c.execute('SELECT * FROM photos WHERE pet_id = ?', (pet_id, )).fetchall()
        db.close()
        return render_template("edit_pet.html", user=user, user_id=user_id, unread_messages=unread_messages, details=details, photos=photos, dogs=dogs, cats=cats)
    
    else:
        name = request.form.get("name")
        animal = request.form.get("animal")
        age = request.form.get("age")
        gender = request.form.get("gender")
        breed = request.form.get("breed")
        description = request.form.get("description")

        data = (name, age, gender, animal, breed, description, pet_id)
        sql = "UPDATE pets SET name = ?, age = ?, gender = ?, animal = ?, breed = ?, description = ? WHERE id = ?"
        c.execute(sql, data)
        db.commit()

        path = "static/uploads/" + pet_id
        
        if not os.path.exists(path):
            os.mkdir(path)
            print("path does not exist")
        else:
            print("path exists")

        images = []
        for file in glob.glob(path + "/*"):
            images.append(file)

        for photo in ['photo1', 'photo2', 'photo3', 'photo4']:
            if photo in request.files:
                file = request.files[photo]
                if file.filename != '':
                    if file and allowed_file(file.filename):
                        filename = pet_id + photo + '.' + secure_filename(file.filename).rsplit('.', 1)[1]
                        file.save(os.path.join(basedir, path + "/", filename))
                        exists = c.execute("SELECT filename FROM photos WHERE filename = ?", (filename, )).fetchall()
                        if len(exists) == 0:
                            c.execute("INSERT INTO photos (pet_id, filename) VALUES (?, ?)", (pet_id, filename))
                            db.commit()

        for delete_photo in ['delete1', 'delete2', 'delete3', 'delete4']:
            if request.form.get(delete_photo) != "0":
                filename = request.form.get(delete_photo)
                os.remove(os.path.join(basedir, path + "/", filename))
                c.execute("DELETE FROM photos WHERE filename = ?", (filename, ))
                db.commit()

        db.commit()
        db.close()
        return redirect("/pets/" + animal.lower() + "s/" + pet_id)



@app.route("/remove/<pet_id>", methods=["GET", "POST"])
@login_required
def remove(pet_id):
    user = session.get("user")
    user_id = session.get("user_id")
    unread_messages = session.get("unread_messages")

    db = sqlite3.connect("app.db")
    c = db.cursor()
    q = c.execute("SELECT * FROM pets WHERE id = ?", (pet_id, )).fetchall()

    if len(q) < 1:
        return redirect("/")
    
    pet = q[0]
    if pet[1] != user_id:
        return redirect("/")

    if request.method == "GET":
        return render_template("confirmation.html", user=user, unread_messages=unread_messages, user_id=user_id, pet=pet)
    else:
        c.execute("DELETE FROM pets WHERE id = ?", (pet_id, ))
        c.execute("DELETE FROM photos WHERE pet_id = ?", (pet_id, ))
        db.commit()
        db.close()
        shutil.rmtree("static/uploads/" + pet_id)
        return redirect("/account")



@app.route("/catapi", methods=["GET", "POST"])
def catapi():
    
    random_cat = get_random_cat()

    return render_template("cats.html", random_cat=random_cat)



@app.route("/dogapi", methods=["GET", "POST"])
def dogapi():
    
    conn = http.client.HTTPSConnection("api.thedogapi.com")

    headers = { 'x-api-key': "3a2b00e5-a4b0-4618-8181-43a3192048fd" }

    conn.request("GET", "/v1/breeds?attach_breed=0", headers=headers)

    res = conn.getresponse()
    data = res.read()
    breeds = json.loads(data.decode("utf-8"))

    random_dog = breeds[random.randint(0, len(breeds) - 1)]
    
    conn.request("GET", "/v1/images/search?breed_id=" + str(random_dog["id"]), headers=headers)
    res = conn.getresponse()
    data = res.read()
    random_dog = json.loads(data.decode("utf-8"))[0]

    return render_template("cats.html", random_cat=random_dog, breeds=breeds)



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
        cats.append(line.replace("\n",""))
    return cats

def get_cat_ids():
    cats = []
    f = open("static/txt/cats_id.txt", "r")
    for line in f:
        cats.append(line.replace("\n",""))
    return cats

def get_random_cat():

    ids = get_cat_ids()
    random_id = ids[random.randint(0, len(ids) - 1)].replace("\n","")
    
    conn = http.client.HTTPSConnection("api.thecatapi.com")

    headers = { 'x-api-key': "7737b5f1-f53b-4225-b781-d0b80604ebab" }
   
    conn.request("GET", "/v1/images/search?breed_id=" + str(random_id), headers=headers)
    res = conn.getresponse()
    data = res.read()
    random_cat = json.loads(data.decode("utf-8"))[0]

    return random_cat


def get_cat_details(breed):

    ids = get_cat_ids()
    breeds = get_cat_breeds()

    try:
        cat_id = ids[breeds.index(breed)]
    except:
        return {}

    conn = http.client.HTTPSConnection("api.thecatapi.com")

    headers = { 'x-api-key': "7737b5f1-f53b-4225-b781-d0b80604ebab" }

    conn.request("GET", "/v1/images/search?breed_id=" + str(cat_id), headers=headers)
    res = conn.getresponse()
    data = res.read()
    cat_details = json.loads(data.decode("utf-8"))[0]

    return cat_details


def get_dog_breeds():
    dogs = []
    f = open("static/txt/dogs.txt", "r")
    for line in f:
        dogs.append(line.replace("\n",""))
    return dogs

def get_dog_ids():
    dogs = []
    f = open("static/txt/dogs_id.txt", "r")
    for line in f:
        dogs.append(line.replace("\n",""))
    return dogs

def get_random_dog():

    ids = get_dog_ids()
    random_id = ids[random.randint(0, len(ids) - 1)].replace("\n","")
    
    conn = http.client.HTTPSConnection("api.thedogapi.com")

    headers = { 'x-api-key': "3a2b00e5-a4b0-4618-8181-43a3192048fd" }

    conn.request("GET", "/v1/images/search?breed_id=" + str(random_id), headers=headers)
    res = conn.getresponse()
    data = res.read()
    random_dog = json.loads(data.decode("utf-8"))[0]

    return random_dog


def get_dog_details(breed):

    ids = get_dog_ids()
    breeds = get_dog_breeds()

    try:
        dog_id = ids[breeds.index(breed)]
    except:
        return {}

    conn = http.client.HTTPSConnection("api.thedogapi.com")

    headers = { 'x-api-key': "3a2b00e5-a4b0-4618-8181-43a3192048fd" }

    conn.request("GET", "/v1/images/search?breed_id=" + str(dog_id), headers=headers)
    res = conn.getresponse()
    data = res.read()
    dog_details = json.loads(data.decode("utf-8"))[0]

    return dog_details

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
