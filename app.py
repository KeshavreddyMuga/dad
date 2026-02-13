import os
import requests
from datetime import datetime
from flask import Flask, request, redirect, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///team_workspace.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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
    body {{
        margin:0;
        font-family:Arial;
        background:linear-gradient(135deg,#667eea,#764ba2);
        color:white;
    }}
    .container {{
        width:90%;
        max-width:1000px;
        margin:40px auto;
        padding:30px;
        background:rgba(255,255,255,0.15);
        border-radius:15px;
        backdrop-filter:blur(10px);
        position:relative;
    }}
    .logout {{
        position:absolute;
        top:20px;
        right:20px;
        color:white;
    }}
    input {{
        width:100%;
        padding:10px;
        margin:8px 0;
        border:none;
        border-radius:8px;
    }}
    button {{
        padding:8px 15px;
        border:none;
        border-radius:8px;
        background:black;
        color:white;
        cursor:pointer;
        margin:5px 0;
    }}
    .card {{
        background:rgba(0,0,0,0.3);
        padding:15px;
        border-radius:10px;
        margin:10px 0;
    }}
    a {{
        text-decoration:none;
        color:white;
    }}
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
        <a href='/login'><button>Back to Login</button></a>
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

# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    content = f"<h2>Welcome {session['user_name']} ({session['role']})</h2>"

    # Admin Create Project Form
    if session["role"] == "admin":
        content += """
        <h3>Create Project</h3>
        <form method='POST' action='/create_project'>
        <input name='name' required placeholder='Project Name'>
        <input type='number' name='weeks' required placeholder='Total Weeks'>
        <button>Create Project</button>
        </form>
        """

    # Project List
    content += "<h3>Projects</h3>"
    for p in Project.query.all():
        status = " (Finished)" if p.is_finished else ""
        content += f"<div class='card'><a href='/project/{p.id}'>{p.name}{status}</a></div>"

    return render(content)

# ================= CREATE PROJECT =================

@app.route("/create_project", methods=["POST"])
def create_project():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/dashboard")

    project = Project(
        name=request.form["name"],
        weeks=int(request.form["weeks"])
    )

    db.session.add(project)
    db.session.commit()

    return redirect("/dashboard")

# ================= PROJECT PAGE =================

@app.route("/project/<int:pid>")
def project_page(pid):
    if "user_id" not in session:
        return redirect("/login")

    project = Project.query.get_or_404(pid)

    content = f"<h2>{project.name}</h2>"
    content += f"<p>Total Weeks: {project.weeks}</p>"
    content += f"<p>Current Week: {project.current_week}</p>"
    content += "<br><a href='/dashboard'><button>Back</button></a>"

    return render(content)

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
