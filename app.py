import os
import uuid
import json

import bleach
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, session, abort, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)

from config import Config
from models import db, User, Product, ProductKey, Order, OrderItem
from utils.email_utils import send_order_email
from utils.invoice_utils import generate_invoice

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# Ensure required directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['INVOICE_FOLDER'], exist_ok=True)

_app_initialized = False

@app.before_request
def initialize():
    global _app_initialized
    if _app_initialized:
        return
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username='admin',
                email='admin@achete-license.com',
                password=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print('Admin user created: admin / admin123')

        if not User.query.filter_by(username='dev').first():
            dev = User(
                username='dev',
                email='dev@achete-license.com',
                password=generate_password_hash('dev123'),
                is_admin=False
            )
            db.session.add(dev)
            db.session.commit()
            print('Dev user created: dev / dev123')
    _app_initialized = True

@app.context_processor
def inject_globals():
    return {
        'app_url': app.config['APP_URL'],
        'bank_info': {
            'holder': app.config['BANK_ACCOUNT_HOLDER'],
            'bank': app.config['BANK_NAME'],
            'rib': app.config['BANK_RIB'],
            'iban': app.config['BANK_IBAN'],
            'bic': app.config['BANK_BIC'],
            'email': app.config['BANK_EMAIL'],
        }
    }

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def sanitize_html(text):
    if not text:
        return ''
    return bleach.clean(text, tags=[], strip=True)

def create_bank_transfer_order(cart, email, name=None):
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    order = Order(
        total_amount=total,
        customer_email=email,
        customer_name=name or email,
        status='pending',
        payment_method='bank_transfer'
    )

    if current_user.is_authenticated:
        order.user_id = current_user.id

    for item in cart.values():
        product = Product.query.with_for_update().get(item['product_id'])
        if not product or product.available_keys_count < item['quantity']:
            db.session.rollback()
            return None, f'Insufficient stock for {item["name"]}'

        order_item = OrderItem(
            product_id=product.id,
            product_name=product.name,
            quantity=item['quantity'],
            price=item['price'],
            license_key=None
        )
        order.items.append(order_item)

    db.session.add(order)
    db.session.commit()
    return order, None

# ---------- Routes ----------

@app.route('/')
def index():
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all()
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'shop'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin_dashboard' if user.is_admin else 'shop'))
        flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('shop'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('register.html')

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            is_admin=False
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('shop'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ---------- Admin Routes ----------

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).filter_by(status='completed').scalar() or 0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    all_active = Product.query.filter_by(is_active=True).all()
    low_stock = sum(1 for p in all_active if p.available_keys_count <= 3)
    return render_template('admin/dashboard.html',
                         total_products=total_products,
                         total_orders=total_orders,
                         total_revenue=total_revenue,
                         recent_orders=recent_orders,
                         low_stock=low_stock)

@app.route('/admin/products')
@login_required
def admin_products():
    if not current_user.is_admin:
        abort(403)
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        name = sanitize_html(request.form.get('name'))
        description = sanitize_html(request.form.get('description'))
        price = float(request.form.get('price', 0))
        category = request.form.get('category', 'General')
        license_type = request.form.get('license_type', 'standard')

        image_file = 'default.png'
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                image_file = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_file))

        product = Product(
            name=name,
            description=description,
            price=price,
            quantity=0,
            category=category,
            license_type=license_type,
            image_file=image_file
        )
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', product=None)

@app.route('/admin/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    if not current_user.is_admin:
        abort(403)
    product = Product.query.get_or_404(id)

    if request.method == 'POST':
        product.name = sanitize_html(request.form.get('name'))
        product.description = sanitize_html(request.form.get('description'))
        product.price = float(request.form.get('price', 0))
        product.category = request.form.get('category', 'General')
        product.license_type = request.form.get('license_type', 'standard')

        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                image_file = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_file))
                product.image_file = image_file

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', product=product)

@app.route('/admin/products/toggle/<int:id>')
@login_required
def toggle_product(id):
    if not current_user.is_admin:
        abort(403)
    product = Product.query.get_or_404(id)
    product.is_active = not product.is_active
    db.session.commit()
    return redirect(url_for('admin_products'))

@app.route('/admin/products/delete/<int:id>')
@login_required
def delete_product(id):
    if not current_user.is_admin:
        abort(403)
    product = Product.query.get_or_404(id)
    # Delete associated product keys
    ProductKey.query.filter_by(product_id=product.id).delete()
    # Delete associated order items
    OrderItem.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/<int:id>/keys')
@login_required
def admin_product_keys(id):
    if not current_user.is_admin:
        abort(403)
    product = Product.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')

    query = ProductKey.query.filter_by(product_id=id)
    if status_filter == 'available':
        query = query.filter_by(is_sold=False)
    elif status_filter == 'sold':
        query = query.filter_by(is_sold=True)

    keys = query.order_by(ProductKey.created_at.desc()).all()
    return render_template('admin/product_keys.html', product=product, keys=keys,
                         status_filter=status_filter)

@app.route('/admin/products/<int:id>/keys/add', methods=['POST'])
@login_required
def admin_add_keys(id):
    if not current_user.is_admin:
        abort(403)
    product = Product.query.get_or_404(id)

    keys_text = request.form.get('keys', '').strip()
    if not keys_text:
        flash('No keys provided', 'error')
        return redirect(url_for('admin_product_keys', id=id))

    lines = [line.strip() for line in keys_text.replace('\r\n', '\n').split('\n') if line.strip()]
    added = 0
    for line in lines:
        key = ProductKey(product_id=id, key_value=line)
        db.session.add(key)
        added += 1

    product.quantity = product.available_keys_count
    db.session.commit()
    flash(f'{added} activation key(s) added successfully!', 'success')
    return redirect(url_for('admin_product_keys', id=id))

@app.route('/admin/products/<int:id>/keys/upload', methods=['POST'])
@login_required
def admin_upload_keys(id):
    if not current_user.is_admin:
        abort(403)
    product = Product.query.get_or_404(id)

    if 'keys_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin_product_keys', id=id))

    file = request.files['keys_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_product_keys', id=id))

    content = file.read().decode('utf-8', errors='ignore')
    lines = [line.strip() for line in content.replace('\r\n', '\n').split('\n') if line.strip()]
    added = 0
    for line in lines:
        key = ProductKey(product_id=id, key_value=line)
        db.session.add(key)
        added += 1

    product.quantity = product.available_keys_count
    db.session.commit()
    flash(f'{added} activation key(s) imported from file!', 'success')
    return redirect(url_for('admin_product_keys', id=id))

@app.route('/admin/products/<int:id>/keys/delete/<int:key_id>')
@login_required
def admin_delete_key(id, key_id):
    if not current_user.is_admin:
        abort(403)
    key = ProductKey.query.get_or_404(key_id)
    if key.is_sold:
        flash('Cannot delete a sold key', 'error')
        return redirect(url_for('admin_product_keys', id=id))

    db.session.delete(key)
    product = Product.query.get(id)
    product.quantity = product.available_keys_count
    db.session.commit()
    flash('Key deleted', 'success')
    return redirect(url_for('admin_product_keys', id=id))

@app.route('/admin/products/<int:id>/keys/clear', methods=['POST'])
@login_required
def admin_clear_keys(id):
    if not current_user.is_admin:
        abort(403)
    product = Product.query.get_or_404(id)

    ProductKey.query.filter_by(product_id=id, is_sold=False).delete()
    product.quantity = product.available_keys_count
    db.session.commit()
    flash('All available keys cleared', 'success')
    return redirect(url_for('admin_product_keys', id=id))

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        abort(403)
    query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    q = Order.query
    if status_filter:
        q = q.filter(Order.status == status_filter)
    if query:
        like = f'%{query}%'
        q = q.filter(
            db.or_(
                Order.customer_name.ilike(like),
                Order.customer_email.ilike(like),
                db.cast(Order.id, db.String).ilike(like),
            )
        )
    orders = q.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders, query=query, status_filter=status_filter)

@app.route('/admin/orders/<int:id>/status', methods=['POST'])
@login_required
def update_order_status(id):
    if not current_user.is_admin:
        abort(403)
    order = Order.query.get_or_404(id)
    new_status = request.form.get('status')

    if new_status == 'completed' and order.status != 'completed':
        for item in order.items:
            if item.license_key:
                continue
            product = Product.query.get(item.product_id)
            if not product:
                continue
            available_keys = ProductKey.query.filter_by(
                product_id=product.id, is_sold=False
            ).limit(item.quantity).all()
            if len(available_keys) < item.quantity:
                flash(f'Not enough keys for {item.product_name}', 'error')
                return redirect(url_for('admin_orders'))
            keys_joined = '\n'.join(pk.key_value for pk in available_keys)
            item.license_key = keys_joined
            for pk in available_keys:
                pk.is_sold = True
                pk.order_item_id = item.id
                pk.sold_at = datetime.utcnow()
            product.quantity = product.available_keys_count

        order.paid_at = datetime.utcnow()
        pdf_path = generate_invoice(order)
        order.invoice_path = pdf_path
        send_order_email(order, pdf_path)

    order.status = new_status
    db.session.commit()
    return redirect(url_for('admin_orders'))

@app.route('/admin/orders/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_order(id):
    if not current_user.is_admin:
        abort(403)
    order = Order.query.get_or_404(id)
    for item in order.items:
        if item.license_key:
            keys = item.license_key.split('\n')
            for key_val in keys:
                pk = ProductKey.query.filter_by(product_id=item.product_id, key_value=key_val, is_sold=True).first()
                if pk:
                    pk.is_sold = False
                    db.session.add(pk)
        db.session.delete(item)
    db.session.delete(order)
    db.session.commit()
    flash('Order deleted successfully.', 'success')
    return redirect(url_for('admin_orders'))

# ---------- Admin User Management ----------

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        username = sanitize_html(request.form.get('username', '').strip())
        email = sanitize_html(request.form.get('email', '').strip())
        password = request.form.get('password', '').strip()

        if username:
            existing = User.query.filter(User.username == username, User.id != id).first()
            if existing:
                flash('Username already taken.', 'error')
            else:
                user.username = username
        if email:
            existing = User.query.filter(User.email == email, User.id != id).first()
            if existing:
                flash('Email already taken.', 'error')
            else:
                user.email = email
        if password:
            user.password = generate_password_hash(password)

        db.session.commit()
        flash('User updated successfully.', 'success')
        return redirect(url_for('admin_users'))

    return render_template('admin/user_edit.html', user=user)

@app.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_user(id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('You cannot delete yourself.', 'error')
        return redirect(url_for('admin_users'))
    if user.is_admin:
        flash('Cannot delete an admin user.', 'error')
        return redirect(url_for('admin_users'))
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))

# ---------- User Routes ----------

@app.route('/shop')
def shop():
    category = request.args.get('category')
    query = Product.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.created_at.desc()).all()
    categories = db.session.query(Product.category).filter_by(is_active=True).distinct().all()
    return render_template('user/shop.html', products=products, categories=[c[0] for c in categories])

@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('user/product_detail.html', product=product)

# ---------- Cart API ----------

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    product = Product.query.get(product_id)
    if not product or not product.is_active:
        return jsonify({'error': 'Product not found'}), 404
    if product.available_keys_count < quantity:
        return jsonify({'error': 'Not enough stock'}), 400

    cart = session.get('cart', {})
    product_key = str(product_id)
    if product_key in cart:
        new_qty = cart[product_key]['quantity'] + quantity
        if new_qty > product.available_keys_count:
            return jsonify({'error': 'Not enough stock'}), 400
        cart[product_key]['quantity'] = new_qty
    else:
        cart[product_key] = {
            'product_id': product_id,
            'name': product.name,
            'price': product.price,
            'image': product.image_file,
            'quantity': quantity
        }
    session['cart'] = cart
    total_items = sum(item['quantity'] for item in cart.values())
    return jsonify({'success': True, 'cart_count': total_items, 'cart': cart})

@app.route('/api/cart/update', methods=['POST'])
def update_cart():
    data = request.get_json()
    product_id = str(data.get('product_id'))
    quantity = data.get('quantity', 1)

    cart = session.get('cart', {})
    if product_id not in cart:
        return jsonify({'error': 'Product not in cart'}), 404

    product = Product.query.get(int(product_id))
    if product and quantity > product.available_keys_count:
        return jsonify({'error': 'Not enough stock'}), 400

    if quantity <= 0:
        del cart[product_id]
    else:
        cart[product_id]['quantity'] = quantity

    session['cart'] = cart
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    total_items = sum(item['quantity'] for item in cart.values())
    return jsonify({'success': True, 'cart': cart, 'total': total, 'cart_count': total_items})

@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    data = request.get_json()
    product_id = str(data.get('product_id'))
    cart = session.get('cart', {})
    if product_id in cart:
        del cart[product_id]
    session['cart'] = cart
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    total_items = sum(item['quantity'] for item in cart.values())
    return jsonify({'success': True, 'cart': cart, 'total': total, 'cart_count': total_items})

@app.route('/api/cart')
def get_cart():
    cart = session.get('cart', {})
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    total_items = sum(item['quantity'] for item in cart.values())
    return jsonify({'cart': cart, 'total': total, 'cart_count': total_items})

# ---------- Bank Transfer Order ----------

@app.route('/api/order/bank-transfer', methods=['POST'])
def place_bank_transfer_order():
    cart = session.get('cart', {})
    if not cart:
        return jsonify({'error': 'Cart is empty'}), 400

    data = request.get_json()
    email = data.get('email', '').strip()
    name = data.get('name', '').strip()

    if not email or not name:
        return jsonify({'error': 'Name and email are required'}), 400

    for item in cart.values():
        product = Product.query.get(item['product_id'])
        if not product or product.available_keys_count < item['quantity']:
            return jsonify({'error': f'Insufficient stock for {item["name"]}'}), 400

    order, error = create_bank_transfer_order(cart, email, name)
    if error:
        return jsonify({'error': error}), 400

    session.pop('cart', None)
    return jsonify({
        'success': True,
        'order_id': order.id,
        'redirect': url_for('order_success', order_id=order.id)
    })

# ---------- Checkout ----------

@app.route('/cart')
def view_cart():
    return render_template('user/cart.html')

@app.route('/checkout', methods=['GET'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('shop'))

    total = sum(item['price'] * item['quantity'] for item in cart.values())
    return render_template('user/checkout.html', cart=cart, total=total)

@app.route('/order/success/<int:order_id>')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('user/order_success.html', order=order)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/order/invoice/<int:order_id>')
def download_invoice(order_id):
    order = Order.query.get_or_404(order_id)

    if order.customer_email != current_user.email and not current_user.is_authenticated:
        abort(403)

    if not order.invoice_path or not os.path.exists(order.invoice_path):
        pdf_path = generate_invoice(order)
        order.invoice_path = pdf_path
        db.session.commit()

    return send_from_directory(
        app.config['INVOICE_FOLDER'],
        f'invoice_{order.id}.pdf',
        as_attachment=True,
        download_name=f'invoice_{order.id}.pdf'
    )

@app.route('/my-orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('user/my_orders.html', orders=orders)

# ---------- Error Handlers ----------

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

# ---------- Main ----------

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
