import os
import requests
from datetime import datetime
from uuid import uuid4
from flask import Flask, request, redirect, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///team_workspace.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
db = SQLAlchemy(app)

# ================= EMAIL FUNCTION =================

def send_email(to_email, subject, html_content):
    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {os.environ.get('RESEND_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "from": "onboarding@resend.dev",
                "to": to_email,
                "subject": subject,
                "html": html_content,
            },
        )
    except:
        pass

# ================= MODELS =================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    weeks = db.Column(db.Integer)
    current_week = db.Column(db.Integer, default=1)
    is_finished = db.Column(db.Boolean, default=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    week_number = db.Column(db.Integer)
    title = db.Column(db.String(200))
    assigned_to = db.Column(db.Integer)
    end_date = db.Column(db.Date)
    is_completed = db.Column(db.Boolean, default=False)

class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer)
    week_number = db.Column(db.Integer)
    file_name = db.Column(db.String(300))
    original_name = db.Column(db.String(300))
    uploaded_by = db.Column(db.String(100))
    description = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# ================= UI =================

def render(content):
    logout = ""
    if "user_id" in session:
        logout = "<a href='/logout' class='logout'>Logout</a>"

    return f"""
    <html>
    <head>
    <style>
    body {{ margin:0; font-family:Arial; background:linear-gradient(135deg,#667eea,#764ba2); color:white; }}
    .container {{ width:90%; max-width:1000px; margin:40px auto; padding:30px;
        background:rgba(255,255,255,0.15); border-radius:15px; backdrop-filter:blur(10px); position:relative; }}
    .logout {{ position:absolute; top:20px; right:20px; color:white; }}
    input, textarea, select {{ width:100%; padding:10px; margin:8px 0; border:none; border-radius:8px; }}
    button {{ padding:8px 15px; border:none; border-radius:8px; background:black; color:white; cursor:pointer; margin:5px 0; }}
    .card {{ background:rgba(0,0,0,0.3); padding:15px; border-radius:10px; margin:10px 0; }}
    .locked {{ background:gray; cursor:not-allowed; }}
    a {{ text-decoration:none; color:white; }}
    </style>
    </head>
    <body>
    <div class='container'>
    {logout}
    {content}
    </div>
    </body>
    </html>
    """

# ================= AUTH =================

@app.route("/")
def home():
    return redirect("/dashboard") if "user_id" in session else redirect("/login")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        if User.query.filter_by(email=request.form["email"]).first():
            return render("<h3>Email already registered!</h3>")

        role = "admin" if User.query.count() == 0 else "member"
        user = User(
            name=request.form["name"],
            email=request.form["email"],
            password=generate_password_hash(request.form["password"]),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        return redirect("/login")

    return render("""
        <h2>Create Account</h2>
        <form method='POST'>
        <input name='name' required placeholder='Name'>
        <input name='email' required placeholder='Email'>
        <input type='password' name='password' required placeholder='Password'>
        <button>Create Account</button>
        </form>
        <a href='/login'><button>Back</button></a>
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            session["user_id"] = user.id
            session["user_name"] = user.name
            session["role"] = user.role
            return redirect("/dashboard")
        return render("<h3>Invalid login</h3>")

    return render("""
        <h2>Login</h2>
        <form method='POST'>
        <input name='email' required placeholder='Email'>
        <input type='password' name='password' required placeholder='Password'>
        <button>Login</button>
        </form>
        <a href='/register'><button>Create Account</button></a>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= PROJECT / TASK LOGIC =================

@app.route("/create_project", methods=["POST"])
def create_project():
    if session.get("role") != "admin":
        return redirect("/dashboard")

    project = Project(name=request.form["name"], weeks=int(request.form["weeks"]))
    db.session.add(project)
    db.session.commit()
    return redirect("/dashboard")

@app.route("/next_week/<int:pid>")
def next_week(pid):
    project = Project.query.get_or_404(pid)
    if project.current_week < project.weeks:
        project.current_week += 1
        db.session.commit()

        users = User.query.filter(User.role != "admin").all()
        for u in users:
            send_email(
                u.email,
                f"Project Moved to Next Week - {project.name}",
                f"The project '{project.name}' has moved to Week {project.current_week}."
            )

    return redirect(f"/project/{pid}")

@app.route("/finish_project/<int:pid>")
def finish_project(pid):
    project = Project.query.get_or_404(pid)
    project.is_finished = True
    db.session.commit()

    users = User.query.filter(User.role != "admin").all()
    for u in users:
        send_email(
            u.email,
            f"Project Completed - {project.name}",
            f"The project '{project.name}' has been completed."
        )

    return redirect(f"/project/{pid}")

# ================= DUE REMINDER ROUTE =================

@app.route("/check_due_tasks")
def check_due_tasks():
    today = datetime.today().date()
    tasks = Task.query.filter_by(end_date=today, is_completed=False).all()

    for task in tasks:
        member = User.query.get(task.assigned_to)
        send_email(
            member.email,
            f"Reminder: Task Due Today",
            f"Hello {member.name}, today is the last day to submit '{task.title}'."
        )

    return "Reminder check completed"

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
