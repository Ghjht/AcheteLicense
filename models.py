from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    image_file = db.Column(db.String(100), nullable=True, default='default.png')
    license_type = db.Column(db.String(50), default='standard')
    category = db.Column(db.String(100), default='General')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    keys = db.relationship('ProductKey', backref='product', lazy=True,
                           foreign_keys='ProductKey.product_id')

    @property
    def available_keys_count(self):
        return ProductKey.query.filter_by(product_id=self.id, is_sold=False).count()

    @property
    def total_keys_count(self):
        return ProductKey.query.filter_by(product_id=self.id).count()

    @property
    def sold_keys_count(self):
        return ProductKey.query.filter_by(product_id=self.id, is_sold=True).count()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'quantity': self.available_keys_count,
            'image_file': self.image_file,
            'license_type': self.license_type,
            'category': self.category,
            'is_active': self.is_active
        }

class ProductKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    key_value = db.Column(db.String(300), nullable=False)
    is_sold = db.Column(db.Boolean, default=False)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_item.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sold_at = db.Column(db.DateTime, nullable=True)

    order_item = db.relationship('OrderItem', backref='product_keys', lazy=True,
                                  foreign_keys=[order_item_id])

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(20), default='stripe')
    payment_intent_id = db.Column(db.String(100), nullable=True)
    customer_email = db.Column(db.String(120), nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    invoice_path = db.Column(db.String(200), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    transaction = db.relationship('Transaction', backref='order', uselist=False, lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    license_key = db.Column(db.String(100), nullable=True)

    product = db.relationship('Product')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='usd')
    status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50), nullable=True)
    receipt_url = db.Column(db.String(500), nullable=True)
    raw_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
