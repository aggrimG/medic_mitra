from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    doctor_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    specialty = db.Column(db.String(100), default='General Radiology')
    hospital = db.Column(db.String(150), default='MedicMitra Health Center')
    password_hash = db.Column(db.String(256), nullable=False)
    is_verified = db.Column(db.Boolean, default=True)
    verification_pin = db.Column(db.String(6), default='123456')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to scans
    scans = db.relationship('ScanRecord', backref='doctor', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.doctor_id} - Dr. {self.name}>"

class ScanRecord(db.Model):
    __tablename__ = 'scan_records'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(64), nullable=False)
    modality = db.Column(db.String(64), default='Chest X-Ray (CXR)')
    original_image = db.Column(db.String(256), nullable=True)
    heatmap_image = db.Column(db.String(256), nullable=True)
    condition_predicted = db.Column(db.String(120), default='Normal / No Infiltration')
    confidence_score = db.Column(db.Float, default=94.2)
    reliability_index = db.Column(db.Float, default=0.95)
    stability = db.Column(db.String(64), default='Stable Finding')
    clinical_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f"<ScanRecord {self.patient_id} - {self.condition_predicted}>"
