import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'achete-license-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///achete_license.db'
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    _base = os.path.abspath(os.path.dirname(__file__))
    _tmp = '/tmp' if os.environ.get('VERCEL') else _base
    UPLOAD_FOLDER = os.path.join(_tmp, 'static', 'uploads')
    INVOICE_FOLDER = os.path.join(_tmp, 'invoices')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or ''
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or ''
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'AcheteLicense <noreply@achete-license.com>'

    APP_URL = os.environ.get('APP_URL') or 'http://localhost:5000'

    BANK_ACCOUNT_HOLDER = os.environ.get('BANK_ACCOUNT_HOLDER') or 'Support AcheteLicense'
    BANK_NAME = os.environ.get('BANK_NAME') or 'BMCE Bank'
    BANK_RIB = os.environ.get('BANK_RIB') or '011 810 0000042000012931 90'
    BANK_IBAN = os.environ.get('BANK_IBAN') or 'MA64 0118 1000 0004 2000 0129 3190'
    BANK_BIC = os.environ.get('BANK_BIC') or 'BMCEMAMC'
    BANK_EMAIL = os.environ.get('BANK_EMAIL') or 'helpstechit@gmail.com'
