import os
import requests
from datetime import datetime
from uuid import uuid4
from flask import Flask, request, redirect, session, send_from_directory, url_for
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

# ================= EMAIL =================

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
        logout = "<a href='/logout' style='float:right;color:white;'>Logout</a>"

    return f"""
    <html>
    <head>
    <style>
    body {{ font-family:Arial; background:#667eea; color:white; padding:30px; }}
    input,textarea,select {{ padding:8px;margin:5px 0;width:100%; }}
    button {{ padding:8px 15px;margin:5px 0; }}
    .card {{ background:#444;padding:15px;margin:10px 0; }}
    </style>
    </head>
    <body>
    {logout}
    {content}
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
            return render("<h3>Email already exists</h3>")
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
        <h2>Register</h2>
        <form method='POST'>
        <input name='name' placeholder='Name' required>
        <input name='email' placeholder='Email' required>
        <input type='password' name='password' placeholder='Password' required>
        <button>Create Account</button>
        </form>
        <a href='/login'>Login</a>
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
        <input name='email' required>
        <input type='password' name='password' required>
        <button>Login</button>
        </form>
        <a href='/register'>Create Account</a>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    content = f"<h2>Welcome {session['user_name']}</h2>"

    if session["role"] == "admin":
        content += """
        <h3>Create Project</h3>
        <form method='POST' action='/create_project'>
        <input name='name' placeholder='Project Name' required>
        <input type='number' name='weeks' placeholder='Weeks' required>
        <button>Create</button>
        </form>
        """

    content += "<h3>Projects</h3>"
    for p in Project.query.all():
        content += f"<div class='card'><a href='/project/{p.id}'>{p.name}</a></div>"

    return render(content)

# ================= PROJECT =================

@app.route("/create_project", methods=["POST"])
def create_project():
    project = Project(name=request.form["name"], weeks=int(request.form["weeks"]))
    db.session.add(project)
    db.session.commit()
    return redirect("/dashboard")

@app.route("/project/<int:pid>")
def project_page(pid):
    project = Project.query.get_or_404(pid)
    content = f"<h2>{project.name}</h2>"
    content += f"<p>Current Week: {project.current_week}</p>"
    content += "<a href='/dashboard'>Back</a>"
    return render(content)

# ================= REMINDER =================

@app.route("/check_due_tasks")
def check_due_tasks():
    today = datetime.today().date()
    tasks = Task.query.filter_by(end_date=today, is_completed=False).all()
    for task in tasks:
        member = User.query.get(task.assigned_to)
        send_email(member.email, "Reminder", f"Task '{task.title}' due today.")
    return "Done"

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
