"""
ProjectFlow - Complete Project Management App
Single file version - guaranteed to work
Run: python app.py
Open: http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from datetime import datetime, date, timedelta
import bcrypt, os, uuid
from werkzeug.utils import secure_filename

# ─── APP SETUP ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'projectflow-secret-key-super-long-string-abc123'
app.config['JWT_SECRET_KEY'] = 'projectflow-jwt-key-super-long-string-xyz789'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///projectflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
jwt = JWTManager(app)
CORS(app)

# ─── MODELS ───────────────────────────────────────────────────────────────────
project_members = db.Table('project_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
)

task_assignees = db.Table('task_assignees',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'), primary_key=True),
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='member')
    job_title = db.Column(db.String(100), default='')
    is_active = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'email': self.email,
                'role': self.role, 'job_title': self.job_title,
                'is_active': self.is_active,
                'last_seen': self.last_seen.isoformat() if self.last_seen else None,
                'created_at': self.created_at.isoformat()}

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='active')
    priority = db.Column(db.String(10), default='medium')
    color = db.Column(db.String(10), default='#6366f1')
    start_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner = db.relationship('User', foreign_keys=[owner_id])
    members = db.relationship('User', secondary=project_members, backref='projects')
    tasks = db.relationship('Task', backref='project', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='project', cascade='all, delete-orphan')
    files = db.relationship('File', backref='project', cascade='all, delete-orphan')
    milestones = db.relationship('Milestone', backref='project', cascade='all, delete-orphan')

    def to_dict(self):
        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t.status == 'done')
        return {
            'id': self.id, 'name': self.name, 'description': self.description,
            'status': self.status, 'priority': self.priority, 'color': self.color,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'progress': int((done/total)*100) if total > 0 else 0,
            'owner_id': self.owner_id,
            'owner': self.owner.to_dict() if self.owner else None,
            'members': [m.to_dict() for m in self.members],
            'task_count': total, 'done_tasks': done,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='todo')
    priority = db.Column(db.String(10), default='medium')
    due_date = db.Column(db.DateTime)
    estimated_hours = db.Column(db.Float, default=0)
    position = db.Column(db.Integer, default=0)
    tags = db.Column(db.String(200), default='')
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestone.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    assignees = db.relationship('User', secondary=task_assignees)
    time_logs = db.relationship('TimeLog', backref='task', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='task', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])

    def logged_hours(self):
        return sum(t.hours for t in self.time_logs)

    def to_dict(self):
        return {
            'id': self.id, 'title': self.title, 'description': self.description,
            'status': self.status, 'priority': self.priority,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'estimated_hours': self.estimated_hours,
            'logged_hours': self.logged_hours(),
            'position': self.position,
            'tags': self.tags.split(',') if self.tags else [],
            'project_id': self.project_id,
            'milestone_id': self.milestone_id,
            'assignees': [a.to_dict() for a in self.assignees],
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class Milestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default='')
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending')
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tasks = db.relationship('Task', backref='milestone')

    def to_dict(self):
        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t.status == 'done')
        return {'id': self.id, 'name': self.name, 'description': self.description,
                'due_date': self.due_date.isoformat() if self.due_date else None,
                'status': self.status, 'project_id': self.project_id,
                'task_count': total, 'done_tasks': done,
                'progress': int((done/total)*100) if total > 0 else 0,
                'created_at': self.created_at.isoformat()}

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User')

    def to_dict(self):
        return {'id': self.id, 'content': self.content, 'task_id': self.task_id,
                'user_id': self.user_id, 'author': self.author.to_dict(),
                'created_at': self.created_at.isoformat()}

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User')

    def to_dict(self):
        return {'id': self.id, 'content': self.content, 'project_id': self.project_id,
                'sender_id': self.sender_id, 'sender': self.sender.to_dict(),
                'created_at': self.created_at.isoformat()}

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    file_type = db.Column(db.String(100), default='')
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader = db.relationship('User')

    def to_dict(self):
        return {'id': self.id, 'filename': self.filename, 'original_name': self.original_name,
                'file_size': self.file_size, 'file_type': self.file_type,
                'project_id': self.project_id, 'uploaded_by': self.uploaded_by,
                'uploader': self.uploader.to_dict(), 'created_at': self.created_at.isoformat()}

class TimeLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hours = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), default='')
    date = db.Column(db.Date, default=date.today)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')

    def to_dict(self):
        return {'id': self.id, 'hours': self.hours, 'description': self.description,
                'date': self.date.isoformat() if self.date else None,
                'task_id': self.task_id, 'user_id': self.user_id,
                'user': self.user.to_dict(),
                'task': {'id': self.task.id, 'title': self.task.title, 'project_id': self.task.project_id},
                'created_at': self.created_at.isoformat()}

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), default='info')
    is_read = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'title': self.title, 'message': self.message,
                'type': self.type, 'is_read': self.is_read, 'user_id': self.user_id,
                'created_at': self.created_at.isoformat()}

class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    all_day = db.Column(db.Boolean, default=False)
    color = db.Column(db.String(10), default='#6366f1')
    event_type = db.Column(db.String(30), default='meeting')
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'title': self.title, 'description': self.description,
                'start_time': self.start_time.isoformat(),
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'all_day': self.all_day, 'color': self.color,
                'event_type': self.event_type, 'project_id': self.project_id,
                'created_by': self.created_by, 'created_at': self.created_at.isoformat()}

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def current_user():
    return User.query.get(int(get_jwt_identity()))

def notif(user_id, title, msg, t='info'):
    n = Notification(title=title, message=msg, type=t, user_id=user_id)
    db.session.add(n)

# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def register():
    d = request.get_json()
    if not d or not all(k in d for k in ['name','email','password']):
        return jsonify({'error': 'Name, email, password required'}), 400
    if User.query.filter_by(email=d['email']).first():
        return jsonify({'error': 'Email already registered'}), 409
    u = User(name=d['name'], email=d['email'], role=d.get('role','member'), job_title=d.get('job_title',''))
    u.set_password(d['password'])
    db.session.add(u)
    db.session.commit()
    token = create_access_token(identity=str(u.id))
    return jsonify({'token': token, 'user': u.to_dict()}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.get_json()
    u = User.query.filter_by(email=d.get('email','')).first()
    if not u or not u.check_password(d.get('password','')):
        return jsonify({'error': 'Invalid email or password'}), 401
    u.last_seen = datetime.utcnow()
    db.session.commit()
    token = create_access_token(identity=str(u.id))
    return jsonify({'token': token, 'user': u.to_dict()}), 200

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_me():
    return jsonify(current_user().to_dict())

@app.route('/api/auth/me', methods=['PUT'])
@jwt_required()
def update_me():
    u = current_user()
    d = request.get_json()
    if 'name' in d: u.name = d['name']
    if 'job_title' in d: u.job_title = d['job_title']
    if d.get('password'): u.set_password(d['password'])
    db.session.commit()
    return jsonify(u.to_dict())

# ─── USER ROUTES ──────────────────────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
@jwt_required()
def get_users():
    return jsonify([u.to_dict() for u in User.query.filter_by(is_active=True).all()])

@app.route('/api/users/<int:uid>', methods=['PUT'])
@jwt_required()
def update_user(uid):
    u = User.query.get_or_404(uid)
    d = request.get_json()
    for f in ['name','job_title','role','is_active']:
        if f in d: setattr(u, f, d[f])
    db.session.commit()
    return jsonify(u.to_dict())

# ─── PROJECT ROUTES ───────────────────────────────────────────────────────────
@app.route('/api/projects', methods=['GET'])
@jwt_required()
def get_projects():
    u = current_user()
    if u.role == 'admin':
        projects = Project.query.all()
    else:
        owned = Project.query.filter_by(owner_id=u.id).all()
        member_of = u.projects
        seen = set()
        projects = []
        for p in owned + member_of:
            if p.id not in seen:
                seen.add(p.id)
                projects.append(p)
    return jsonify([p.to_dict() for p in projects])

@app.route('/api/projects', methods=['POST'])
@jwt_required()
def create_project():
    u = current_user()
    d = request.get_json()
    if not d or 'name' not in d:
        return jsonify({'error': 'Project name required'}), 400
    p = Project(
        name=d['name'], description=d.get('description',''),
        status=d.get('status','active'), priority=d.get('priority','medium'),
        color=d.get('color','#6366f1'), owner_id=u.id,
        start_date=datetime.strptime(d['start_date'],'%Y-%m-%d').date() if d.get('start_date') else None,
        due_date=datetime.strptime(d['due_date'],'%Y-%m-%d').date() if d.get('due_date') else None,
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201

@app.route('/api/projects/<int:pid>', methods=['GET'])
@jwt_required()
def get_project(pid):
    return jsonify(Project.query.get_or_404(pid).to_dict())

@app.route('/api/projects/<int:pid>', methods=['PUT'])
@jwt_required()
def update_project(pid):
    p = Project.query.get_or_404(pid)
    d = request.get_json()
    for f in ['name','description','status','priority','color']:
        if f in d: setattr(p, f, d[f])
    if d.get('start_date'): p.start_date = datetime.strptime(d['start_date'],'%Y-%m-%d').date()
    if d.get('due_date'): p.due_date = datetime.strptime(d['due_date'],'%Y-%m-%d').date()
    p.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(p.to_dict())

@app.route('/api/projects/<int:pid>', methods=['DELETE'])
@jwt_required()
def delete_project(pid):
    p = Project.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'Deleted'})

@app.route('/api/projects/<int:pid>/members', methods=['POST'])
@jwt_required()
def add_member(pid):
    p = Project.query.get_or_404(pid)
    d = request.get_json()
    m = User.query.filter_by(email=d.get('email','')).first()
    if not m: return jsonify({'error': 'User not found'}), 404
    if m not in p.members: p.members.append(m)
    db.session.commit()
    return jsonify({'message': 'Member added', 'user': m.to_dict()})

@app.route('/api/projects/<int:pid>/members/<int:uid>', methods=['DELETE'])
@jwt_required()
def remove_member(pid, uid):
    p = Project.query.get_or_404(pid)
    m = User.query.get_or_404(uid)
    if m in p.members: p.members.remove(m)
    db.session.commit()
    return jsonify({'message': 'Removed'})

@app.route('/api/projects/<int:pid>/milestones', methods=['GET'])
@jwt_required()
def get_milestones(pid):
    return jsonify([m.to_dict() for m in Milestone.query.filter_by(project_id=pid).all()])

@app.route('/api/projects/<int:pid>/milestones', methods=['POST'])
@jwt_required()
def create_milestone(pid):
    d = request.get_json()
    m = Milestone(name=d['name'], description=d.get('description',''),
                  due_date=datetime.strptime(d['due_date'],'%Y-%m-%d').date() if d.get('due_date') else None,
                  project_id=pid)
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201

# ─── TASK ROUTES ──────────────────────────────────────────────────────────────
@app.route('/api/tasks/project/<int:pid>', methods=['GET'])
@jwt_required()
def get_tasks(pid):
    tasks = Task.query.filter_by(project_id=pid).order_by(Task.position, Task.created_at).all()
    return jsonify([t.to_dict() for t in tasks])

@app.route('/api/tasks/board/<int:pid>', methods=['GET'])
@jwt_required()
def get_board(pid):
    board = {}
    for s in ['todo','in_progress','review','done']:
        board[s] = [t.to_dict() for t in Task.query.filter_by(project_id=pid, status=s).order_by(Task.position).all()]
    return jsonify(board)

@app.route('/api/tasks', methods=['POST'])
@jwt_required()
def create_task():
    u = current_user()
    d = request.get_json()
    if not d or 'title' not in d or 'project_id' not in d:
        return jsonify({'error': 'Title and project_id required'}), 400
    t = Task(title=d['title'], description=d.get('description',''),
             status=d.get('status','todo'), priority=d.get('priority','medium'),
             due_date=datetime.fromisoformat(d['due_date']) if d.get('due_date') else None,
             estimated_hours=d.get('estimated_hours',0),
             tags=','.join(d.get('tags',[])),
             project_id=d['project_id'], milestone_id=d.get('milestone_id'),
             created_by=u.id)
    db.session.add(t)
    db.session.flush()
    for uid in d.get('assignee_ids',[]):
        au = User.query.get(uid)
        if au: t.assignees.append(au)
    db.session.commit()
    return jsonify(t.to_dict()), 201

@app.route('/api/tasks/<int:tid>', methods=['GET'])
@jwt_required()
def get_task(tid):
    return jsonify(Task.query.get_or_404(tid).to_dict())

@app.route('/api/tasks/<int:tid>', methods=['PUT'])
@jwt_required()
def update_task(tid):
    t = Task.query.get_or_404(tid)
    d = request.get_json()
    old_status = t.status
    for f in ['title','description','status','priority','estimated_hours','position','milestone_id']:
        if f in d: setattr(t, f, d[f])
    if 'due_date' in d:
        t.due_date = datetime.fromisoformat(d['due_date']) if d['due_date'] else None
    if 'tags' in d: t.tags = ','.join(d['tags'])
    if 'assignee_ids' in d:
        t.assignees = []
        for uid in d['assignee_ids']:
            au = User.query.get(uid)
            if au: t.assignees.append(au)
    if d.get('status') == 'done' and old_status != 'done':
        t.completed_at = datetime.utcnow()
    t.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(t.to_dict())

@app.route('/api/tasks/<int:tid>', methods=['DELETE'])
@jwt_required()
def delete_task(tid):
    t = Task.query.get_or_404(tid)
    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': 'Deleted'})

@app.route('/api/tasks/<int:tid>/comments', methods=['GET'])
@jwt_required()
def get_comments(tid):
    return jsonify([c.to_dict() for c in Comment.query.filter_by(task_id=tid).order_by(Comment.created_at).all()])

@app.route('/api/tasks/<int:tid>/comments', methods=['POST'])
@jwt_required()
def add_comment(tid):
    u = current_user()
    d = request.get_json()
    c = Comment(content=d['content'], task_id=tid, user_id=u.id)
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201

# ─── MESSAGES ─────────────────────────────────────────────────────────────────
@app.route('/api/messages/project/<int:pid>', methods=['GET'])
@jwt_required()
def get_messages(pid):
    msgs = Message.query.filter_by(project_id=pid).order_by(Message.created_at).limit(100).all()
    return jsonify({'messages': [m.to_dict() for m in msgs], 'total': len(msgs), 'pages': 1, 'current_page': 1})

@app.route('/api/messages', methods=['POST'])
@jwt_required()
def send_message():
    u = current_user()
    d = request.get_json()
    m = Message(content=d['content'], project_id=d['project_id'], sender_id=u.id)
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201

# ─── FILES ────────────────────────────────────────────────────────────────────
ALLOWED = {'pdf','doc','docx','xls','xlsx','png','jpg','jpeg','gif','zip','txt','csv'}

@app.route('/api/files/project/<int:pid>', methods=['GET'])
@jwt_required()
def get_files(pid):
    return jsonify([f.to_dict() for f in File.query.filter_by(project_id=pid).all()])

@app.route('/api/files/upload', methods=['POST'])
@jwt_required()
def upload_file():
    u = current_user()
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    pid = request.form.get('project_id')
    if not pid: return jsonify({'error': 'project_id required'}), 400
    ext = f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED: return jsonify({'error': 'File type not allowed'}), 400
    fname = f'{uuid.uuid4().hex}.{ext}'
    fpath = os.path.join(UPLOAD_FOLDER, fname)
    f.save(fpath)
    dbf = File(filename=fname, original_name=secure_filename(f.filename),
               file_size=os.path.getsize(fpath), file_type=f.content_type,
               project_id=int(pid), uploaded_by=u.id)
    db.session.add(dbf)
    db.session.commit()
    return jsonify(dbf.to_dict()), 201

@app.route('/api/files/download/<int:fid>', methods=['GET'])
@jwt_required()
def download_file(fid):
    f = File.query.get_or_404(fid)
    return send_from_directory(UPLOAD_FOLDER, f.filename, as_attachment=True, download_name=f.original_name)

@app.route('/api/files/<int:fid>', methods=['DELETE'])
@jwt_required()
def delete_file(fid):
    f = File.query.get_or_404(fid)
    try: os.remove(os.path.join(UPLOAD_FOLDER, f.filename))
    except: pass
    db.session.delete(f)
    db.session.commit()
    return jsonify({'message': 'Deleted'})

# ─── TIMELOG ──────────────────────────────────────────────────────────────────
@app.route('/api/timelog', methods=['POST'])
@jwt_required()
def log_time():
    u = current_user()
    d = request.get_json()
    l = TimeLog(hours=d['hours'], description=d.get('description',''),
                date=datetime.strptime(d['date'],'%Y-%m-%d').date() if d.get('date') else date.today(),
                task_id=d['task_id'], user_id=u.id)
    db.session.add(l)
    db.session.commit()
    return jsonify(l.to_dict()), 201

@app.route('/api/timelog/task/<int:tid>', methods=['GET'])
@jwt_required()
def get_task_logs(tid):
    return jsonify([l.to_dict() for l in TimeLog.query.filter_by(task_id=tid).all()])

@app.route('/api/timelog/user', methods=['GET'])
@jwt_required()
def get_my_logs():
    u = current_user()
    return jsonify([l.to_dict() for l in TimeLog.query.filter_by(user_id=u.id).order_by(TimeLog.date.desc()).limit(100).all()])

@app.route('/api/timelog/<int:lid>', methods=['DELETE'])
@jwt_required()
def delete_log(lid):
    l = TimeLog.query.get_or_404(lid)
    db.session.delete(l)
    db.session.commit()
    return jsonify({'message': 'Deleted'})

# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────
@app.route('/api/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    u = current_user()
    notifs = Notification.query.filter_by(user_id=u.id).order_by(Notification.created_at.desc()).limit(50).all()
    unread = Notification.query.filter_by(user_id=u.id, is_read=False).count()
    return jsonify({'notifications': [n.to_dict() for n in notifs], 'unread': unread})

@app.route('/api/notifications/read-all', methods=['PUT'])
@jwt_required()
def mark_all_read():
    u = current_user()
    Notification.query.filter_by(user_id=u.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'message': 'Done'})

@app.route('/api/notifications/<int:nid>/read', methods=['PUT'])
@jwt_required()
def mark_read(nid):
    n = Notification.query.get_or_404(nid)
    n.is_read = True
    db.session.commit()
    return jsonify(n.to_dict())

# ─── REPORTS ──────────────────────────────────────────────────────────────────
@app.route('/api/reports/summary', methods=['GET'])
@jwt_required()
def summary():
    u = current_user()
    if u.role == 'admin':
        projects = Project.query.all()
    else:
        owned = Project.query.filter_by(owner_id=u.id).all()
        projects = list({p.id: p for p in owned + u.projects}.values())
    return jsonify({
        'total_projects': len(projects),
        'active_projects': sum(1 for p in projects if p.status == 'active'),
        'total_tasks': sum(len(p.tasks) for p in projects),
        'completed_tasks': sum(sum(1 for t in p.tasks if t.status == 'done') for p in projects),
    })

@app.route('/api/reports/project/<int:pid>', methods=['GET'])
@jwt_required()
def project_report(pid):
    p = Project.query.get_or_404(pid)
    tasks = p.tasks
    total = len(tasks)
    by_status = {'todo': 0, 'in_progress': 0, 'review': 0, 'done': 0}
    by_priority = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
    total_logged = 0
    total_estimated = 0
    for t in tasks:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        total_logged += t.logged_hours()
        total_estimated += t.estimated_hours or 0
    member_hours = {}
    all_members = list({u.id: u for u in p.members + [p.owner]}.values())
    for m in all_members:
        logs = TimeLog.query.join(Task).filter(Task.project_id == pid, TimeLog.user_id == m.id).all()
        member_hours[m.name] = sum(l.hours for l in logs)
    return jsonify({'project': p.to_dict(), 'total_tasks': total,
                    'by_status': by_status, 'by_priority': by_priority,
                    'total_logged_hours': total_logged,
                    'total_estimated_hours': total_estimated,
                    'member_hours': member_hours})

# ─── CALENDAR ─────────────────────────────────────────────────────────────────
@app.route('/api/calendar', methods=['GET'])
@jwt_required()
def get_events():
    u = current_user()
    if u.role == 'admin':
        events = CalendarEvent.query.all()
    else:
        pids = [p.id for p in u.projects + Project.query.filter_by(owner_id=u.id).all()]
        events = CalendarEvent.query.filter(
            db.or_(CalendarEvent.project_id.in_(pids), CalendarEvent.created_by == u.id)
        ).all()
    return jsonify([e.to_dict() for e in events])

@app.route('/api/calendar', methods=['POST'])
@jwt_required()
def create_event():
    u = current_user()
    d = request.get_json()
    e = CalendarEvent(title=d['title'], description=d.get('description',''),
                      start_time=datetime.fromisoformat(d['start_time']),
                      end_time=datetime.fromisoformat(d['end_time']) if d.get('end_time') else None,
                      all_day=d.get('all_day', False), color=d.get('color','#6366f1'),
                      event_type=d.get('event_type','meeting'),
                      project_id=d.get('project_id'), created_by=u.id)
    db.session.add(e)
    db.session.commit()
    return jsonify(e.to_dict()), 201

@app.route('/api/calendar/<int:eid>', methods=['DELETE'])
@jwt_required()
def delete_event(eid):
    e = CalendarEvent.query.get_or_404(eid)
    db.session.delete(e)
    db.session.commit()
    return jsonify({'message': 'Deleted'})

# ─── PAGE ROUTES ──────────────────────────────────────────────────────────────
@app.route('/')
def index(): return redirect('/login')

@app.route('/login')
def login_page(): return send_from_directory('templates', 'login.html')

@app.route('/register')
def register_page(): return send_from_directory('templates', 'register.html')

@app.route('/dashboard')
def dashboard(): return send_from_directory('templates', 'dashboard.html')

@app.route('/projects')
def projects_page(): return send_from_directory('templates', 'projects.html')

@app.route('/projects/<int:pid>')
def project_detail(pid): return send_from_directory('templates', 'project_detail.html')

@app.route('/calendar')
def calendar_page(): return send_from_directory('templates', 'calendar.html')

@app.route('/reports')
def reports_page(): return send_from_directory('templates', 'reports.html')

@app.route('/team')
def team_page(): return send_from_directory('templates', 'team.html')

@app.route('/profile')
def profile_page(): return send_from_directory('templates', 'profile.html')

@app.route('/static/<path:filename>')
def static_files(filename): return send_from_directory('static', filename)

# ─── SEED DATA ────────────────────────────────────────────────────────────────
def seed():
    if User.query.first(): return  # already seeded
    print("Seeding database...")

    admin = User(name='Admin User', email='admin@projectflow.com', role='admin', job_title='Administrator')
    admin.set_password('admin123')
    manager = User(name='Sarah Chen', email='sarah@projectflow.com', role='manager', job_title='Project Manager')
    manager.set_password('password123')
    dev1 = User(name='James Wilson', email='james@projectflow.com', role='member', job_title='Developer')
    dev1.set_password('password123')
    dev2 = User(name='Priya Patel', email='priya@projectflow.com', role='member', job_title='Designer')
    dev2.set_password('password123')
    db.session.add_all([admin, manager, dev1, dev2])
    db.session.flush()

    p1 = Project(name='E-Commerce Platform', description='Build a full-featured online store.',
                 status='active', priority='high', color='#6366f1', owner_id=manager.id,
                 start_date=date.today()-timedelta(days=30), due_date=date.today()+timedelta(days=60))
    p1.members.extend([dev1, dev2])
    p2 = Project(name='Mobile App Redesign', description='Redesign the mobile app for better UX.',
                 status='active', priority='medium', color='#10b981', owner_id=manager.id,
                 start_date=date.today()-timedelta(days=10), due_date=date.today()+timedelta(days=45))
    p2.members.append(dev2)
    db.session.add_all([p1, p2])
    db.session.flush()

    tasks_data = [
        ('Setup project structure', 'done', 'high', dev1, p1.id),
        ('Design database schema', 'done', 'high', dev1, p1.id),
        ('Build auth API', 'in_progress', 'critical', dev1, p1.id),
        ('Product catalog UI', 'in_progress', 'high', dev2, p1.id),
        ('Payment integration', 'todo', 'critical', dev1, p1.id),
        ('Shopping cart feature', 'todo', 'high', dev2, p1.id),
        ('Admin dashboard', 'review', 'medium', dev2, p1.id),
        ('User research', 'done', 'high', dev2, p2.id),
        ('Wireframes', 'in_progress', 'high', dev2, p2.id),
        ('Prototype testing', 'todo', 'medium', dev2, p2.id),
    ]
    for title, status, priority, assignee, pid in tasks_data:
        t = Task(title=title, status=status, priority=priority,
                 estimated_hours=8, project_id=pid, created_by=manager.id,
                 due_date=datetime.now()+timedelta(days=14))
        t.assignees.append(assignee)
        if status == 'done': t.completed_at = datetime.utcnow()
        db.session.add(t)

    e = CalendarEvent(title='Sprint Planning', start_time=datetime.now()+timedelta(days=2, hours=9),
                      end_time=datetime.now()+timedelta(days=2, hours=11),
                      color='#6366f1', event_type='meeting', project_id=p1.id, created_by=manager.id)
    db.session.add(e)

    n = Notification(title='Welcome!', message='Welcome to ProjectFlow!', type='success', user_id=admin.id)
    db.session.add(n)
    db.session.commit()
    print("✅ Database seeded! Login: admin@projectflow.com / admin123")

# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed()
    print("\n🚀 ProjectFlow running at http://localhost:5000\n")
    app.run(debug=False, host='0.0.0.0', port=5000)
