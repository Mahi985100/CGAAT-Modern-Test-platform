from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from pathlib import Path
from math import ceil
from datetime import datetime
from functools import wraps
from io import BytesIO
import json
from fpdf import FPDF

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'cgaat.db'

app = Flask(__name__)
app.secret_key = 'change-this-secret-key'


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS test_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            test_slug TEXT NOT NULL,
            test_name TEXT NOT NULL,
            package_name TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            score INTEGER NOT NULL,
            category TEXT NOT NULL,
            strengths TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            test_slug TEXT NOT NULL,
            package_name TEXT NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    db.commit()

    admin_email = 'admin@cgaat.in'
    admin_exists = cur.execute('SELECT id FROM users WHERE email = ?', (admin_email,)).fetchone()
    if not admin_exists:
        cur.execute(
            'INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
            ('Admin', admin_email, generate_password_hash('admin123'), 'admin', datetime.now().isoformat(timespec='seconds'))
        )
    db.commit()
    db.close()


BLOG_POSTS = [
    {
        'slug': 'why-career-guidance-is-essential-for-students-today',
        'category': 'Career',
        'title': 'Why Career Guidance Is Essential for Students Today?',
        'excerpt': 'Students face many choices. Career guidance helps them understand strengths, interests, and future paths with more confidence.',
        'content': 'Career guidance helps students understand themselves better. It connects interests, strengths, academic choices, and future careers so decisions are made with more clarity and less confusion. When students get timely guidance, they avoid random choices and move toward a path that fits them.',
        'date': '2026-04-01'
    },
    {
        'slug': 'what-is-the-right-age-to-take-a-career-assessment-test',
        'category': 'Student',
        'title': 'What Is the Right Age to Take a Career Assessment Test?',
        'excerpt': 'A career assessment can be useful when students start making subject or stream decisions and want structured insight.',
        'content': 'There is no single perfect age, but assessment becomes especially useful when students start asking serious questions about streams, careers, and future planning. Early awareness gives students time to improve skills and make informed choices.',
        'date': '2026-04-03'
    },
    {
        'slug': 'why-career-counselling-is-important-for-students',
        'category': 'Counselling',
        'title': 'Why Career Counselling Is Important for Students?',
        'excerpt': 'Counselling supports students beyond test scores by turning insights into practical action.',
        'content': 'A test shows data, but counselling explains what to do next. It helps students and parents understand report findings, compare options, and create realistic study plans. Good counselling turns confusion into direction.',
        'date': '2026-04-05'
    },
    {
        'slug': 'how-psychometric-tests-help-students-choose-better',
        'category': 'Assessment',
        'title': 'How Psychometric Tests Help Students Choose Better',
        'excerpt': 'Psychometric assessments provide a scientific starting point for self-discovery.',
        'content': 'Psychometric tests help identify strengths, working styles, and interests. This can reduce guesswork and support better academic and career planning.',
        'date': '2026-04-07'
    },
    {
        'slug': 'common-career-mistakes-students-should-avoid',
        'category': 'Career',
        'title': 'Common Career Mistakes Students Should Avoid',
        'excerpt': 'Many students copy others without understanding their own profile. That often leads to poor fit.',
        'content': 'Students should avoid choosing careers only because of trends, pressure, or assumptions. A better approach is to combine self-understanding, guidance, and practical planning.',
        'date': '2026-04-08'
    },
    {
        'slug': 'stream-selection-after-10th-made-easier',
        'category': 'Student',
        'title': 'Stream Selection After 10th Made Easier',
        'excerpt': 'Choosing science, commerce, or arts becomes easier when strengths and interests are understood clearly.',
        'content': 'Stream selection should not be fear-based. It should be based on aptitude, personality, goals, and learning preferences. Assessments and counselling can make this process smoother.',
        'date': '2026-04-09'
    },
]

TESTS = {
    'aptitude-pro': {
        'slug': 'aptitude-pro',
        'name': 'Pattern Hunter Exam',
        'tag': 'Pattern IQ',
        'package': 'Starter Package',
        'price': 299,
        'desc': 'An engaging exam focused on visual patterns, number logic, and quick analytical thinking.',
        'questions': [
            {'text': 'I can quickly notice which shape or symbol is different from the rest.', 'weight': 5},
            {'text': 'When a number series changes in a pattern, I can usually predict the next value.', 'weight': 5},
            {'text': 'I enjoy finding the missing figure in a puzzle or sequence.', 'weight': 5},
            {'text': 'I can compare multiple options and identify the odd one out with confidence.', 'weight': 5},
            {'text': 'Rotating shapes or mirrored designs in my mind feels manageable to me.', 'weight': 5},
            {'text': 'I stay calm while solving time-based pattern questions.', 'weight': 5},
            {'text': 'I can break a difficult puzzle into smaller clues and solve it step by step.', 'weight': 5},
            {'text': 'Logical pattern questions feel interesting rather than stressful to me.', 'weight': 5},
        ],
    },
    'personality-plus': {
        'slug': 'personality-plus',
        'name': 'Tech Mindset Exam',
        'tag': 'IT Skills',
        'package': 'Growth Package',
        'price': 499,
        'desc': 'A modern test that mixes technology awareness, problem solving, focus, and communication style.',
        'questions': [
            {'text': 'I enjoy learning how apps, websites, or digital tools work behind the scenes.', 'weight': 5},
            {'text': 'When a technical problem happens, I like troubleshooting instead of giving up quickly.', 'weight': 5},
            {'text': 'I can follow step-by-step instructions to install, configure, or test a system.', 'weight': 5},
            {'text': 'I am interested in topics such as coding, cybersecurity, AI, databases, or networking.', 'weight': 5},
            {'text': 'I prefer clean organization when working with files, folders, or project tasks.', 'weight': 5},
            {'text': 'I can explain a technical idea in simple words to someone else.', 'weight': 5},
            {'text': 'I like checking details carefully because one small error can affect the full output.', 'weight': 5},
            {'text': 'I enjoy improving digital work by making it faster, easier, or more user-friendly.', 'weight': 5},
        ],
    },
    'career-pathfinder': {
        'slug': 'career-pathfinder',
        'name': 'Future Ready Exam',
        'tag': 'Career Fit',
        'package': 'Premium Package',
        'price': 799,
        'desc': 'A richer career assessment with decision making, strengths discovery, and practical future planning.',
        'questions': [
            {'text': 'I often think about which career will match both my skills and my interests.', 'weight': 5},
            {'text': 'Before choosing a field, I like to compare growth, salary, and future opportunities.', 'weight': 5},
            {'text': 'I enjoy discovering what kind of work environment suits me best.', 'weight': 5},
            {'text': 'I am open to exploring new-age careers such as data analytics, UI/UX, AI, digital marketing, or cloud roles.', 'weight': 5},
            {'text': 'I want guidance that helps me choose a path based on strengths instead of pressure from others.', 'weight': 5},
            {'text': 'I like planning my future step by step instead of making random career decisions.', 'weight': 5},
            {'text': 'I am curious about building both technical skills and soft skills for long-term success.', 'weight': 5},
            {'text': 'I feel more confident when career decisions are based on clear self-understanding.', 'weight': 5},
        ],
    },
}


PARTNERS = ['HolyTech', 'Pathwise', 'FutureBridge', 'MindTrack', 'SkillHive', 'CareerNest']
TESTIMONIALS = [
    ('Career Guidance Test', 'This career guidance is a game-changer! It matched my interests to Management studies I never considered. Now I am pursuing a BBA with clear direction.', 'Ronak Shah - Class 12', 'Ahmedabad'),
    ('Personality Assessment', 'Finally understood my introverted strengths through the personality test. It recommended counselling paths that feel authentic and super insightful!', 'Shilpa Matre, B.Com Student', 'Vadodara'),
    ('Aptitude Test', 'My aptitude test report revealed hidden analytical skills. Switched from arts to data analytics and scored well in mocks already!', 'Nina Maheshwari', 'Surat'),
    ('Career Guidance Test', 'Confused post-10th? This test outlined 5 viable paths with study plans. Chose commerce and loving it. thanks to expert design!', 'Gaurav Prasad', 'Surat'),
    ('Personality Assessment', 'The personality report showed my leadership traits perfectly. feels like it knows me!', 'Ravindra Patel', 'Gandhinagar'),
    ('Aptitude Test', 'Struggled with streams until the aptitude test. Now preparing for NEET.', 'Shruti Patel', 'Vadodara'),
]




def build_report_pdf(user_name, row):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_fill_color(36, 87, 255)
    pdf.rect(10, 10, 190, 24, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_xy(16, 17)
    pdf.cell(0, 8, 'CGAAT Assessment Report', ln=1)

    pdf.set_text_color(20, 32, 51)
    pdf.ln(12)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f'Student Name: {user_name}', ln=1)
    pdf.cell(0, 8, f'Test Name: {row["test_name"]}', ln=1)
    pdf.cell(0, 8, f'Package: {row["package_name"]}', ln=1)
    pdf.cell(0, 8, f'Date: {row["created_at"]}', ln=1)

    pdf.ln(4)
    pdf.set_fill_color(234, 240, 255)
    pdf.rect(14, pdf.get_y(), 182, 22, 'F')
    y = pdf.get_y() + 5
    pdf.set_xy(22, y)
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 7, f'Result Category: {row["category"]}', ln=1)
    pdf.set_x(22)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 7, f'Score: {row["score"]}', ln=1)

    pdf.ln(10)
    sections = [
        ('Strengths', row['strengths']),
        ('Recommendation', row['recommendation']),
    ]

    try:
        answers = json.loads(row['answers_json']) if row['answers_json'] else {}
    except Exception:
        answers = {}
    answer_line = ', '.join([f'{k.upper()}: {v}' for k, v in answers.items()]) or 'No answer details available.'
    sections.append(('Response Summary', answer_line))

    for heading, body in sections:
        pdf.set_font('Helvetica', 'B', 13)
        pdf.cell(0, 8, heading, ln=1)
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 7, body)
        pdf.ln(3)

    pdf.ln(3)
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(14, pdf.get_y(), 182, 24, 'F')
    pdf.set_xy(22, pdf.get_y() + 5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 7, 'Next Step', ln=1)
    pdf.set_x(22)
    pdf.set_font('Helvetica', '', 11)
    pdf.multi_cell(164, 7, 'Use this report to discuss strengths, preferences, and future study direction. This PDF can be shared during counselling or saved for later reference.')

    content = pdf.output(dest='S')
    if isinstance(content, str):
        content = content.encode('latin-1')
    return BytesIO(content)

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return get_db().execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user['role'] != 'admin':
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


def evaluate_score(score):
    if score >= 85:
        return (
            'Excellent',
            'Strong alignment, confidence, self-awareness, and decision readiness.',
            'Move ahead with focused counselling, expert discussion, and a clear action plan.'
        )
    if score >= 70:
        return (
            'Good',
            'Healthy alignment with a good base of strengths, interest, and clarity.',
            'Refine your top options and compare matching academic paths.'
        )
    if score >= 50:
        return (
            'Average',
            'Some areas are promising, but more exploration is needed.',
            'Take deeper guidance, compare options, and build more confidence before finalizing.'
        )
    return (
        'Below Average',
        'Your profile needs more exploration before final decisions.',
        'Start with counselling, self-discovery, and gradual exploration before choosing a direction.'
    )


@app.context_processor
def inject_globals():
    return {
        'current_user': current_user(),
        'year': datetime.now().year,
        'all_tests': list(TESTS.values())
    }


@app.route('/')
def home():
    return render_template('home.html', posts=BLOG_POSTS[:3], tests=list(TESTS.values()), testimonials=TESTIMONIALS, partners=PARTNERS)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/tests')
def tests():
    return render_template('tests.html', tests=list(TESTS.values()))


@app.route('/buy-package/<slug>', methods=['POST'])
@login_required
def buy_package(slug):
    test = TESTS.get(slug)
    if not test:
        abort(404)
    db = get_db()
    db.execute(
        'INSERT INTO subscriptions (user_id, test_slug, package_name, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (session['user_id'], slug, test['package'], test['price'], 'Active', datetime.now().isoformat(timespec='seconds'))
    )
    db.commit()
    flash(f"{test['package']} activated for {test['name']}.", 'success')
    return redirect(url_for('take_test', slug=slug))


@app.route('/online-test/<slug>', methods=['GET', 'POST'])
@login_required
def take_test(slug):
    test = TESTS.get(slug)
    if not test:
        abort(404)

    result = None
    if request.method == 'POST':
        scores = []
        answers = {}
        for idx, q in enumerate(test['questions'], start=1):
            value = request.form.get(f'q{idx}', '0')
            value = int(value) if value.isdigit() else 0
            answers[f'q{idx}'] = value
            scores.append(value * q['weight'])
        score = sum(scores)
        category, strengths, recommendation = evaluate_score(score)
        db = get_db()
        db.execute(
            '''INSERT INTO test_attempts (user_id, test_slug, test_name, package_name, answers_json, score, category, strengths, recommendation, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                session['user_id'],
                test['slug'],
                test['name'],
                test['package'],
                json.dumps(answers),
                score,
                category,
                strengths,
                recommendation,
                datetime.now().isoformat(timespec='seconds')
            )
        )
        db.commit()
        attempt_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return redirect(url_for('result_detail', attempt_id=attempt_id))
    return render_template('online_test.html', test=test, result=result)


@app.route('/results')
@login_required
def results():
    rows = get_db().execute(
        'SELECT * FROM test_attempts WHERE user_id = ? ORDER BY id DESC',
        (session['user_id'],)
    ).fetchall()
    return render_template('results.html', results=rows)


@app.route('/result/<int:attempt_id>')
@login_required
def result_detail(attempt_id):
    row = get_db().execute(
        'SELECT * FROM test_attempts WHERE id = ? AND user_id = ?',
        (attempt_id, session['user_id'])
    ).fetchone()
    if not row:
        abort(404)
    return render_template('result_detail.html', row=row)




@app.route('/result/<int:attempt_id>/pdf')
@login_required
def download_result_pdf(attempt_id):
    row = get_db().execute(
        'SELECT * FROM test_attempts WHERE id = ? AND user_id = ?',
        (attempt_id, session['user_id'])
    ).fetchone()
    if not row:
        abort(404)
    user = current_user()
    pdf_io = build_report_pdf(user['name'], row)
    filename = f"cgaat_report_{attempt_id}.pdf"
    return send_file(pdf_io, mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user = current_user()
    attempts = db.execute('SELECT * FROM test_attempts WHERE user_id = ? ORDER BY id DESC LIMIT 5', (user['id'],)).fetchall()
    subscriptions = db.execute('SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id DESC', (user['id'],)).fetchall()
    total_tests = db.execute('SELECT COUNT(*) FROM test_attempts WHERE user_id = ?', (user['id'],)).fetchone()[0]
    active_packages = db.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id = ? AND status = 'Active'", (user['id'],)).fetchone()[0]
    highest_score = db.execute('SELECT COALESCE(MAX(score), 0) FROM test_attempts WHERE user_id = ?', (user['id'],)).fetchone()[0]
    return render_template(
        'dashboard.html',
        user=user,
        attempts=attempts,
        subscriptions=subscriptions,
        total_tests=total_tests,
        active_packages=active_packages,
        highest_score=highest_score,
    )


@app.route('/blog')
def blog():
    page = max(request.args.get('page', 1, type=int), 1)
    per_page = 3
    total_pages = ceil(len(BLOG_POSTS) / per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    posts = BLOG_POSTS[start:start + per_page]
    return render_template('blog.html', posts=posts, page=page, total_pages=total_pages)


@app.route('/blog/<slug>')
def blog_detail(slug):
    post = next((p for p in BLOG_POSTS if p['slug'] == slug), None)
    if not post:
        abort(404)
    return render_template('blog_detail.html', post=post)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        get_db().execute(
            'INSERT INTO contacts (name, email, subject, message, created_at) VALUES (?, ?, ?, ?, ?)',
            (
                request.form.get('name', '').strip(),
                request.form.get('email', '').strip(),
                request.form.get('subject', '').strip(),
                request.form.get('message', '').strip(),
                datetime.now().isoformat(timespec='seconds')
            )
        )
        get_db().commit()
        flash('Your message has been submitted successfully.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')


@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/terms')
def terms():
    return render_template('terms.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')


@app.route('/sitemap')
def sitemap():
    return render_template('sitemap.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not (name and email and password):
            flash('Please fill all required fields.', 'error')
            return redirect(url_for('register'))
        db = get_db()
        exists = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if exists:
            flash('This email is already registered.', 'error')
            return redirect(url_for('register'))
        db.execute(
            'INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
            (name, email, generate_password_hash(password), 'user', datetime.now().isoformat(timespec='seconds'))
        )
        db.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = get_db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            flash('Logged in successfully.', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'users': db.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
        'attempts': db.execute('SELECT COUNT(*) FROM test_attempts').fetchone()[0],
        'contacts': db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0],
        'subscriptions': db.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0],
    }
    recent_attempts = db.execute(
        '''SELECT test_attempts.*, users.name AS user_name
           FROM test_attempts JOIN users ON users.id = test_attempts.user_id
           ORDER BY test_attempts.id DESC LIMIT 10'''
    ).fetchall()
    return render_template('admin_dashboard.html', stats=stats, recent_attempts=recent_attempts)


@app.route('/admin/users')
@admin_required
def admin_users():
    users = get_db().execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    return render_template('admin_users.html', users=users)


@app.route('/admin/attempts')
@admin_required
def admin_attempts():
    rows = get_db().execute(
        '''SELECT test_attempts.*, users.name AS user_name, users.email AS user_email
           FROM test_attempts JOIN users ON users.id = test_attempts.user_id
           ORDER BY test_attempts.id DESC'''
    ).fetchall()
    return render_template('admin_attempts.html', rows=rows)


@app.route('/admin/contacts')
@admin_required
def admin_contacts():
    rows = get_db().execute('SELECT * FROM contacts ORDER BY id DESC').fetchall()
    return render_template('admin_contacts.html', rows=rows)


@app.errorhandler(403)
def forbidden(error):
    return render_template('403.html'), 403


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
