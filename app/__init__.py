from flask import Flask
from urllib.parse import quote
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import cloudinary
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import os
from urllib.parse import quote


load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = quote(os.getenv("DB_PASSWORD"))
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")

app = Flask(__name__)
app.secret_key = 'nhom6@321'
#app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:%s@localhost/oufooddb?charset=utf8mb4" % quote("Admin@123")
#app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://thanhdan:%s@mysql/oufooddb?charset=utf8mb4" % quote("123456")
app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
app.config["PAGE_SIZE"] = 8

# app.config['VNPAY_RETURN_URL'] = os.environ.get('VNPAY_RETURN_URL')
# app.config['VNPAY_PAYMENT_URL'] = os.environ.get('VNPAY_PAYMENT_URL')
# app.config['VNPAY_TMN_CODE'] = os.environ.get('VNPAY_TMN_CODE')
# app.config['VNPAY_HASH_SECRET_KEY'] = os.environ.get('VNPAY_HASH_SECRET_KEY')

app.config["VNPAY_TMN_CODE"] = "PRGWN1DK"
app.config["VNPAY_HASH_SECRET_KEY"] = "9R0EULLFYS4PPLP9QJVESN08J83EQ8HU"
app.config["VNPAY_PAYMENT_URL"] = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
app.config["VNPAY_RETURN_URL"] = "http://localhost:8000/vnpay_payment_return"


app.config['MOMO_RETURN_URL'] = os.environ.get('MOMO_RETURN_URL')
app.config['MOMO_PAYMENT_URL'] = os.environ.get('MOMO_PAYMENT_URL')
app.config['MOMO_ACCESS_KEY'] = os.environ.get('MOMO_ACCESS_KEY')
app.config['MOMO_SECRET_KEY'] = os.environ.get('MOMO_SECRET_KEY')

oauth = OAuth(app)

db = SQLAlchemy(app=app)
migrate = Migrate(app, db)
login = LoginManager(app=app)

# Configuration
cloudinary.config(
    cloud_name="dnwyvuqej",
    api_key="559324578186686",
    api_secret="tjXbrfktUPN8lYMmE9SN-33QXjc",
    secure=True
)

google = oauth.register(
    name='google',
    client_id=os.environ.get('CLIENT_ID_GG'),
    client_secret=os.environ.get('CLIENT_SECRET_GG'),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
)

from app import models