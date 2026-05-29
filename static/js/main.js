// Mobile Nav Toggle
document.addEventListener('DOMContentLoaded', function() {
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.querySelector('.nav-menu');

    if (navToggle) {
        navToggle.addEventListener('click', function() {
            navMenu.classList.toggle('active');
        });
    }

    // Close flash messages
    document.querySelectorAll('.flash-close').forEach(btn => {
        btn.addEventListener('click', function() {
            this.parentElement.remove();
        });
    });

    // Auto-hide flash messages after 5s
    document.querySelectorAll('.flash-message').forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            msg.style.transition = 'all 0.3s';
            setTimeout(() => msg.remove(), 300);
        }, 5000);
    });

    // Update cart count on load
    updateCartCount();

    // If on cart page, load cart
    if (document.getElementById('cartContainer')) {
        loadCartPage();
    }

});

// Cart Functions
function updateCartCount() {
    fetch('/api/cart')
        .then(res => res.json())
        .then(data => {
            const badge = document.getElementById('cartCount');
            if (badge) {
                badge.textContent = data.cart_count || 0;
                badge.style.display = data.cart_count > 0 ? 'flex' : 'none';
            }
        })
        .catch(() => {});
}

function addToCart(productId, quantity = 1) {
    const btn = event?.target?.closest('.btn-add-cart');
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
        btn.disabled = true;
    }

    fetch('/api/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, quantity: quantity })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            updateCartCount();
            showToast('Product added to cart!', 'success');
            if (btn) {
                btn.innerHTML = '<i class="fas fa-check"></i> Added';
                setTimeout(() => {
                    btn.innerHTML = '<i class="fas fa-shopping-cart"></i> Add to Cart';
                    btn.disabled = false;
                }, 2000);
            }
        } else {
            showToast(data.error || 'Failed to add to cart', 'error');
            if (btn) {
                btn.innerHTML = '<i class="fas fa-shopping-cart"></i> Add to Cart';
                btn.disabled = false;
            }
        }
    })
    .catch(() => {
        showToast('Network error', 'error');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-shopping-cart"></i> Add to Cart';
            btn.disabled = false;
        }
    });
}

function loadCartPage() {
    const container = document.getElementById('cartContainer');
    const empty = document.getElementById('cartEmpty');
    const actions = document.getElementById('cartActions');

    fetch('/api/cart')
        .then(res => res.json())
        .then(data => {
            const cart = data.cart;
            const entries = Object.entries(cart);

            if (entries.length === 0) {
                container.innerHTML = '';
                empty.style.display = 'block';
                actions.style.display = 'none';
                return;
            }

            container.innerHTML = '';
            empty.style.display = 'none';
            actions.style.display = 'flex';

            entries.forEach(([id, item]) => {
                const imgSrc = item.image !== 'default.png'
                    ? `/static/uploads/${item.image}`
                    : `https://placehold.co/70x70/1a1a2e/e94560?text=${item.name[0]}`;

                const itemEl = document.createElement('div');
                itemEl.className = 'cart-item';
                itemEl.innerHTML = `
                    <img src="${imgSrc}" alt="${item.name}" class="cart-item-img"
                         onerror="this.src='https://placehold.co/70x70/1a1a2e/e94560?text=P'">
                    <div class="cart-item-info">
                        <h3>${item.name}</h3>
                        <p>$${parseFloat(item.price).toFixed(2)} each</p>
                    </div>
                    <div class="cart-item-qty">
                        <button class="qty-btn" onclick="updateCartItem(${id}, ${item.quantity - 1})">-</button>
                        <span class="qty-value">${item.quantity}</span>
                        <button class="qty-btn" onclick="updateCartItem(${id}, ${item.quantity + 1})">+</button>
                    </div>
                    <div class="cart-item-price">$${(item.price * item.quantity).toFixed(2)}</div>
                    <button class="btn-remove-cart" onclick="removeCartItem(${id})" title="Remove">
                        <i class="fas fa-trash"></i>
                    </button>
                `;
                container.appendChild(itemEl);
            });

            // Add total bar
            const totalBar = document.createElement('div');
            totalBar.className = 'cart-total-bar';
            totalBar.innerHTML = `
                <span>Total:</span>
                <strong>$${parseFloat(data.total).toFixed(2)}</strong>
            `;
            container.appendChild(totalBar);
        })
        .catch(() => {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><h3>Failed to load cart</h3></div>';
        });
}

function updateCartItem(productId, quantity) {
    if (quantity <= 0) {
        removeCartItem(productId);
        return;
    }

    fetch('/api/cart/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, quantity: quantity })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            updateCartCount();
            loadCartPage();
        } else {
            showToast(data.error || 'Failed to update', 'error');
        }
    });
}

function removeCartItem(productId) {
    fetch('/api/cart/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            updateCartCount();
            loadCartPage();
        }
    });
}

// Search / Filter
function filterProducts() {
    const input = document.getElementById('searchInput');
    if (!input) return;

    const query = input.value.toLowerCase();
    const cards = document.querySelectorAll('.product-card');

    cards.forEach(card => {
        const name = card.dataset.name || '';
        if (name.includes(query)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

// Toast Notification
function showToast(message, type = 'success') {
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        <span>${message}</span>
    `;
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        padding: 16px 24px;
        background: ${type === 'success' ? 'rgba(34,197,94,0.95)' : 'rgba(239,68,68,0.95)'};
        color: #fff;
        border-radius: 12px;
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        z-index: 10000;
        animation: slideUp 0.3s ease;
        backdrop-filter: blur(10px);
    `;

    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function placeBankTransfer() {
    const submitBtn = document.getElementById('submitBankTransfer');
    const processing = document.getElementById('bankProcessing');
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!name) {
        showToast('Please enter your full name.', 'error');
        document.getElementById('name').focus();
        return;
    }

    if (!email || !email.includes('@')) {
        showToast('Please enter a valid email address.', 'error');
        document.getElementById('email').focus();
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    processing.style.display = 'flex';

    try {
        const res = await fetch('/api/order/bank-transfer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, name: name })
        });

        const data = await res.json();

        if (data.success && data.redirect) {
            processing.innerHTML = '<i class="fas fa-check-circle"></i> <span>Order placed! Redirecting...</span>';
            setTimeout(() => {
                window.location.href = data.redirect;
            }, 1000);
        } else {
            throw new Error(data.error || 'Failed to place order');
        }

    } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-check"></i> Try Again';
        processing.style.display = 'none';
        showToast(err.message || 'Failed to place order', 'error');
    }
}

function copyBankInfo() {
    const holder = document.querySelector('.bank-info-details .bank-info-value');
    if (!holder) return;

    const info = document.querySelectorAll('.bank-info-row');
    let text = '';
    info.forEach(row => {
        const label = row.querySelector('.bank-info-label');
        const value = row.querySelector('.bank-info-value');
        if (label && value) {
            text += `${label.textContent}: ${value.textContent}\n`;
        }
    });

    navigator.clipboard.writeText(text).then(() => {
        showToast('Bank information copied!', 'success');
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Bank information copied!', 'success');
    });
}

// Copy License Key
document.addEventListener('click', function(e) {
    var btn = e.target.closest('.my-keys-copy');
    if (!btn) return;
    var key = btn.getAttribute('data-key');
    if (!key) return;
    navigator.clipboard.writeText(key).then(function() {
        showToast('License key copied!', 'success');
    }).catch(function() {
        var textarea = document.createElement('textarea');
        textarea.value = key;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('License key copied!', 'success');
    });
});
