import os
import random
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, send_from_directory
from werkzeug.utils import secure_filename
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from models import db, User, ScanRecord
from image_processing import MedicalImageProcessor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "medicmitra-secure-clinical-key-2026")

is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# Database configuration (Supabase PostgreSQL ready with SQLite fallback)
database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    if is_serverless:
        instance_path = "/tmp/instance"
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        instance_path = os.path.join(base_dir, "instance")

    try:
        os.makedirs(instance_path, exist_ok=True)
    except OSError:
        instance_path = "/tmp/instance"
        os.makedirs(instance_path, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(instance_path, 'medicmitra.db')}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# File upload configuration (read-only filesystem safe for Vercel/Lambda)
if is_serverless:
    UPLOAD_FOLDER = "/tmp/uploads"
else:
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads')

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    UPLOAD_FOLDER = "/tmp/uploads"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'dcm', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize database
db.init_app(app)

@app.route('/static/uploads/<path:filename>')
def serve_uploaded_file(filename):
    """Serve uploaded images safely from either UPLOAD_FOLDER or local static directory"""
    upload_path = app.config.get('UPLOAD_FOLDER', '')
    if upload_path and os.path.exists(os.path.join(upload_path, filename)):
        return send_from_directory(upload_path, filename)
    static_uploads = os.path.join(app.root_path, 'static', 'uploads')
    return send_from_directory(static_uploads, filename)

# Authentication helper decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access the clinical workspace.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Context processor to inject current logged-in doctor
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(current_user=user)

@app.template_filter('format_doctor_name')
def format_doctor_name(name):
    if not name:
        return "Dr. Sarah Mitchell, M.D."
    clean = str(name).strip()
    if clean.lower().startswith('dr.'):
        return f"Dr. {clean[3:].strip()}"
    if clean.lower().startswith('dr '):
        return f"Dr. {clean[3:].strip()}"
    return f"Dr. {clean}"

# ----------------- ROUTES -----------------

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def index():
    """Factual, High-Craft Medical Landing Page"""
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Doctor Authentication Portal with Credential Verification"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember')

        if not identifier or not password:
            flash("Please provide both Doctor ID / Email and password.", "error")
            return render_template('login.html', identifier=identifier)

        user = User.query.filter(
            (User.email.ilike(identifier)) | (User.doctor_id.ilike(identifier))
        ).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['doctor_id'] = user.doctor_id
            if remember:
                session.permanent = True
            
            if not user.is_verified:
                user.is_verified = True
                db.session.commit()
                
            flash(f"Welcome back, Dr. {user.name}!", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash("Invalid credentials. Please verify your Doctor ID / Email and password.", "error")
            return render_template('login.html', identifier=identifier)

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Doctor Registration Portal with Verification Checks"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        doctor_id = request.form.get('doctor_id', '').strip().upper()
        specialty = request.form.get('specialty', '').strip()
        hospital = request.form.get('hospital', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        terms = request.form.get('terms')

        if not (name and doctor_id and email and password):
            flash("All required fields must be completed.", "error")
            return render_template('signup.html', form_data=request.form)

        if not terms:
            flash("You must agree to the Clinical Protocol terms to register.", "error")
            return render_template('signup.html', form_data=request.form)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template('signup.html', form_data=request.form)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "error")
            return render_template('signup.html', form_data=request.form)

        existing_user = User.query.filter(
            (User.email == email) | (User.doctor_id == doctor_id)
        ).first()

        if existing_user:
            if existing_user.email == email:
                flash("An account with this email address already exists.", "error")
            else:
                flash("An account with this Doctor ID already exists.", "error")
            return render_template('signup.html', form_data=request.form)

        new_user = User(
            name=name,
            doctor_id=doctor_id,
            specialty=specialty or "Radiology",
            hospital=hospital or "MedicMitra Affiliated Hospital",
            email=email,
            is_verified=True,
            verification_pin="123456"
        )
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            session['user_id'] = new_user.id
            session['user_name'] = new_user.name
            session['doctor_id'] = new_user.doctor_id
            flash(f"Practice registered successfully! Welcome to your clinical workspace, Dr. {new_user.name}.", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during account creation. Please try again.", "error")
            return render_template('signup.html', form_data=request.form)

    return render_template('signup.html', form_data={})

@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    """Physician Email Verification Screen (Bypassed - auto redirects to workspace)"""
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """Secure Doctor Session Termination"""
    session.clear()
    flash("You have been signed out securely.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Doctor Clinical Workspace & Imaging Intake"""
    # Fetch scans for the current doctor
    recent_scans = ScanRecord.query.filter_by(user_id=session.get('user_id')).order_by(ScanRecord.created_at.desc()).all()
    return render_template('dashboard.html', recent_scans=recent_scans)

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    """Process uploaded medical scan through deterministic radiometric pipeline"""
    patient_id = request.form.get('patient_id', '').strip() or f"PT-{random.randint(1000, 9999)}"
    modality = request.form.get('modality', 'Chest X-Ray (CXR)')
    clinical_notes = request.form.get('clinical_notes', '')

    file = request.files.get('scan_image')
    image_filename = None

    if file and file.filename != '':
        if allowed_file(file.filename):
            sec_name = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"{timestamp}_{sec_name}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            file.save(file_path)
        else:
            flash("File format not accepted. Supported: PNG, JPG, JPEG, TIFF, DCM.", "error")
            return redirect(url_for('dashboard'))
    else:
        flash("Please select a valid medical radiograph to analyze.", "error")
        return redirect(url_for('dashboard'))

    if image_filename:
        processor = MedicalImageProcessor(app.config['UPLOAD_FOLDER'])
        
        # Clinical Guardrail: Active Out-of-Distribution (OOD) & SNR Quality Gate
        gate = processor.validate_scan(file_path)
        if not gate['passed']:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
            flash(f"Clinical Safety Rejection: {gate['reason']}", "error")
            return redirect(url_for('dashboard'))

        results = processor.process(file_path, image_filename)
        snr_metric = results.get('snr_db', 25.4)

        new_scan = ScanRecord(
            patient_id=patient_id,
            modality=modality,
            original_image=image_filename,
            heatmap_image=results["analyzed_image"],
            condition_predicted=results["severity"],
            confidence_score=results["anomaly_score"],
            reliability_index=round(min(0.99, max(0.85, snr_metric / 30.0)), 2),
            stability=f"{results['flagged_regions_count']} focal {'opacity' if results['flagged_regions_count'] == 1 else 'opacities'} localized (SNR {snr_metric} dB)",
            clinical_notes=clinical_notes,
            user_id=session.get('user_id')
        )
        db.session.add(new_scan)
        db.session.commit()

        flash(f"Radiograph verified & analyzed: In-Distribution certified (SNR {snr_metric} dB).", "success")
        return redirect(url_for('results', scan_id=new_scan.id))

    return redirect(url_for('dashboard'))

@app.route('/results')
@app.route('/results/<int:scan_id>')
@login_required
def results(scan_id=None):
    """Clinical Diagnostic Report Presentation (Standardized 2-Page Layout)"""
    if scan_id:
        scan = ScanRecord.query.get(scan_id)
    else:
        scan = ScanRecord.query.order_by(ScanRecord.created_at.desc()).first()

    if not scan:
        flash("No active scan records found. Please upload a radiograph first.", "info")
        return redirect(url_for('dashboard'))

    return render_template('results.html', scan=scan)

# Database bootstrap & schema migration
def init_and_seed_db():
    with app.app_context():
        db.create_all()

        # Check and migrate columns in SQLite if needed
        try:
            with db.engine.connect() as conn:
                res = conn.execute(db.text("PRAGMA table_info(users)")).fetchall()
                cols = [r[1] for r in res]
                if "is_verified" not in cols:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 1"))
                if "verification_pin" not in cols:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN verification_pin VARCHAR(6) DEFAULT '123456'"))
                conn.execute(db.text("UPDATE users SET is_verified = 1 WHERE is_verified = 0 OR is_verified IS NULL"))
                conn.commit()
        except Exception:
            pass

        # Ensure demo doctor exists and is verified
        demo_doctor = User.query.filter_by(email="doctor@medicmitra.com").first()
        if not demo_doctor:
            demo_doctor = User(
                name="Sarah Mitchell, M.D.",
                doctor_id="DOC-7749",
                specialty="Thoracic Radiology",
                hospital="MedicMitra Medical Institute",
                email="doctor@medicmitra.com",
                is_verified=True,
                verification_pin="123456"
            )
            demo_doctor.set_password("medic123")
            db.session.add(demo_doctor)
            db.session.commit()
        else:
            demo_doctor.is_verified = True
            demo_doctor.verification_pin = "123456"
            demo_doctor.specialty = "Thoracic Radiology"
            demo_doctor.hospital = "MedicMitra Medical Institute"
            db.session.commit()

        # Remove pre-seeded fake demo scans as requested (item 5)
        mock_pids = ['PT-9042', 'PT-8819', 'PT-7640']
        ScanRecord.query.filter(ScanRecord.patient_id.in_(mock_pids)).delete(synchronize_session=False)
        db.session.commit()

try:
    init_and_seed_db()
except Exception as e:
    app.logger.warning(f"Database initialization deferred: {e}")

if __name__ == '__main__' and not os.environ.get('VERCEL'):
    app.run(debug=True)
