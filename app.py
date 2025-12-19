import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit, join_room
from functools import wraps
from datetime import datetime
import sqlite3, os

# -----------------------------
# APP SETUP
# -----------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "123"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

UPLOAD_FOLDER = "static/files"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# -----------------------------
# DATABASE CONNECT
# -----------------------------
def get_db():
    conn = sqlite3.connect("chat.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# LOGIN REQUIRED
# -----------------------------
def login_required(f):
    @wraps(f)
    def secure(*a, **k):
        if "name" not in session:
            return redirect("/login")
        return f(*a, **k)
    return secure


# -----------------------------
# REGISTER
# -----------------------------
@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":
        phone = request.form["phone"]
        name = request.form["name"]
        password = request.form["password"]

        image = request.files["image"]
        filename = f"{phone}.png"
        image.save(f"static/profile/{filename}")

        db = get_db()
        c = db.cursor()

        c.execute("INSERT INTO users(phone,name,password,image) VALUES(?,?,?,?)",
                  (phone,name,password,filename))

        db.commit()
        db.close()

        return redirect("/login")

    return render_template("register.html")


# -----------------------------
# LOGIN
# -----------------------------
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":
        phone = request.form["phone"]
        password = request.form["password"]

        db = get_db()
        c = db.cursor()

        c.execute("SELECT name,image FROM users WHERE phone=? AND password=?",
                  (phone,password))

        user = c.fetchone()
        db.close()

        if user:
            session["phone"] = phone
            session["name"] = user["name"]
            session["image"] = user["image"]
            return redirect("/")

        return render_template("login.html", error="Invalid Login")

    return render_template("login.html")


# -----------------------------
# LOGOUT
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -----------------------------
# PUBLIC CHAT
# -----------------------------
@app.route("/")
@login_required
def index():

    db = get_db()
    c = db.cursor()

    c.execute("SELECT username,message,time FROM messages ORDER BY id ASC")
    history = c.fetchall()
    db.close()

    return render_template("index.html", history=history)


@socketio.on("message_send")
def send_msg(data):

    data["time"] = datetime.now().strftime("%H:%M")

    db = get_db()
    c = db.cursor()

    c.execute("INSERT INTO messages(username,message,time) VALUES(?,?,?)",
              (data["user"],data["message"],data["time"]))

    db.commit()
    db.close()

    emit("message_receive", data, broadcast=True)


# -----------------------------
# USERS PAGE
# -----------------------------
@app.route("/users")
@login_required
def users():

    db = get_db()
    c = db.cursor()

    c.execute("SELECT name,image FROM users WHERE name!=?",(session["name"],))
    persons = c.fetchall()

    c.execute("SELECT username,last_seen FROM online_users")
    online_data = {i["username"]:i["last_seen"] for i in c.fetchall()}

    output = []

    for u in persons:

        c.execute("""
        SELECT sender,receiver,status FROM friend_requests
        WHERE (sender=? AND receiver=?)
        OR (sender=? AND receiver=?)
        """,(session["name"],u["name"],u["name"],session["name"]))

        req = c.fetchone()

        if not req:
            status = "none"
        elif req["status"] == "pending" and req["sender"] == session["name"]:
            status = "sent"
        elif req["status"] == "pending" and req["receiver"] == session["name"]:
            status = "incoming"
        else:
            status = "friends"

        output.append({
            "name":u["name"],
            "image":u["image"],
            "status":status,
            "online":online_data.get(u["name"],"offline")
        })

    db.close()

    return render_template("users.html", friends=output)


@app.route("/send/<user>")
@login_required
def send(user):

    db = get_db()
    c = db.cursor()

    c.execute("INSERT INTO friend_requests(sender,receiver,status) VALUES(?,?,?)",
              (session["name"],user,"pending"))

    db.commit()
    db.close()

    return redirect("/users")


@app.route("/accept/<user>")
@login_required
def accept(user):

    db = get_db()
    c = db.cursor()

    c.execute("UPDATE friend_requests SET status='friends' WHERE sender=? AND receiver=?",
              (user,session["name"]))

    db.commit()
    db.close()

    return redirect("/users")


# -----------------------------
# PRIVATE CHAT
# -----------------------------
@app.route("/chat/<friend>")
@login_required
def chat(friend):

    db = get_db()
    c = db.cursor()

    c.execute("""
    UPDATE private_messages SET read=1
    WHERE sender=? AND receiver=?""",
    (friend,session["name"]))

    db.commit()

    c.execute("""
    SELECT sender,receiver,message,file,time,read FROM private_messages
    WHERE (sender=? AND receiver=?)
    OR (sender=? AND receiver=?)
    ORDER BY id ASC
    """,(session["name"],friend,friend,session["name"]))

    history = c.fetchall()
    db.close()

    return render_template("private_chat.html",friend=friend,history=history)


@socketio.on("join_private")
def join_private(data):
    room = "_".join(sorted([data["sender"],data["receiver"]]))
    join_room(room)


@socketio.on("private_send")
def private_send(data):

    data["time"] = datetime.now().strftime("%H:%M")

    db = get_db()
    c = db.cursor()

    c.execute("""
    INSERT INTO private_messages(sender,receiver,message,file,time)
    VALUES(?,?,?,?,?)
    """,(data["sender"],data["receiver"],data["message"],"",data["time"]))

    db.commit()
    db.close()

    room = "_".join(sorted([data["sender"],data["receiver"]]))

    emit("private_receive", data, room=room)


# -----------------------------
# FILE SEND
# -----------------------------
@app.route("/upload/<friend>", methods=["POST"])
@login_required
def upload(friend):

    file = request.files["file"]
    name = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + file.filename
    file.save(os.path.join(UPLOAD_FOLDER,name))

    db = get_db()
    c = db.cursor()

    c.execute("""
    INSERT INTO private_messages(sender,receiver,message,file,time)
    VALUES(?,?,?,?,?)
    """,(session["name"],friend,"",name,datetime.now().strftime("%H:%M")))

    db.commit()
    db.close()

    return redirect(f"/chat/{friend}")


# -----------------------------
# ONLINE / OFFLINE
# -----------------------------
@socketio.on("connect")
def online():

    if "name" in session:
        db = get_db()
        c = db.cursor()

        c.execute("INSERT OR REPLACE INTO online_users VALUES(?,?)",
        (session["name"],"online"))

        db.commit()
        db.close()


@socketio.on("disconnect")
def offline():

    if "name" in session:
        db = get_db()
        c = db.cursor()

        c.execute("UPDATE online_users SET last_seen='offline' WHERE username=?",
        (session["name"],))

        db.commit()
        db.close()


# -----------------------------
# comment out socketio.run for production
pass
if __name__ == "__main__":
    socketio.run(app, debug=True)
