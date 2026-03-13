from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from General.models import Book


def home(request):
    """Buyer home / dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")


def buyer_dashboard(request):
    """Buyer dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")

def add_to_cart(request, book_id):
    if request.method == "POST":
        book = get_object_or_404(Book, pk=book_id, is_active=True)
        cart = request.session.get("cart", {})

        book_id_str = str(book_id)
        if book_id_str in cart:
            cart[book_id_str]["quantity"] += 1
        else:
            cart[book_id_str] = {
                "quantity": 1
            }
        request.session["cart"] = cart
        request.session.modified = True
    return redirect("cart")


def buyer_cart(request):
    cart = request.session.get("cart", {})
    cart_items = []
    cart_subtotal = 0.00

    for book_id, item_data in cart.items():
        try:
            book = Book.objects.get(pk=book_id, is_active=True)
            quantity = item_data.get("quantity", 1)
            price = float(book.base_price_cents) / 100
            subtotal = price * quantity

            cart_items.append({
                "id": book.id,
                "book": book,
                "quantity": quantity,
                "price": price,
                "subtotal": subtotal
            })

            cart_subtotal += subtotal
        except Book.DoesNotExist:
            continue
    tax = round(cart_subtotal * 0.07, 2)
    fees = 0.00
    cart_total = round(cart_subtotal + tax + fees, 2)
    
    context = {
        "cart_items": cart_items,
        "cart_subtotal": cart_subtotal,
        "cart_total": cart_subtotal,
        "tax": tax,
        "fees": fees,
        "addresses": [],
        "payment_methods": [],
        "checkout_error": None,
    }

    return render(request, "cart/buyer_cart.html", context)


def buyer_checkout(request):
    cart = request.session.get("cart", {})
    cart_items = []
    cart_subtotal = 0.00

    for book_id, item_data in cart.items():
        try:
            book = Book.objects.get(pk=book_id, is_active=True)
            quantity = item_data.get("quantity", 1)
            price = float(book.base_price_cents) / 100
            subtotal = price * quantity

            cart_items.append({
                "id": book.id,
                "book": book,
                "quantity": quantity,
                "price": price,
                "subtotal": subtotal,
            })

            cart_subtotal += subtotal
        except Book.DoesNotExist:
            continue
    
    tax = round(cart_subtotal * 0.07, 2)
    fees = 2.99 if cart_items else 0.00
    final_total = round(cart_subtotal + tax + fees, 2)

    context = {
        "cart_items": cart_items,
        "cart_subtotal": cart_subtotal,
        "tax": tax,
        "fees": fees,
        "final_total": final_total,
        "addresses": [],
        "payment_methods": [],
        "checkout_error": None,
    }
    return render(request, "checkout/buyer_checkout.html", context)

def remove_cart_item(request, item_id):
    if request.method == "POST":
        cart = request.session.get("cart", {})
        item_id_str = str(item_id)

        if item_id_str in cart:
            del cart[item_id_str]

        request.session["cart"] = cart
        request.session.modified = True
    return redirect("cart")

def update_cart_item(request, item_id):
    if request.method == "POST":
        cart = request.session.get("cart", {})
        item_id_str = str(item_id)

        try:
            quantity = int(request.POST.get("quantity", 1))
            if quantity < 1:
                quantity = 1
        except (TypeError, ValueError):
            quantity = 1

        if item_id_str in cart:
            cart[item_id_str]["quantity"] = quantity
        
        request.session["cart"] = cart
        request.session.modified = True
    return redirect("cart")

def buyer_payments(request):
    """Payment methods / step."""
    return render(request, "checkout/buyer_payments.html")


def buyer_shipping(request):
    """Shipping / addresses step."""
    return render(request, "checkout/buyer_shipping.html")


def buyer_profile(request):
    """Buyer profile."""
    return render(request, "account/buyer_profile.html")


def order_confirmation(request):
    """Order confirmation after place order."""
    return render(request, "orders/orderConfirmation.html")


def order_detail(request, order_id=None):
    """Single order detail."""
    return render(request, "orders/orderDetail.html")


def order_history(request):
    """Order history list."""
    return render(request, "orders/orderHistory.html")


def return_request(request):
    """Request a return."""
    return render(request, "orders/ReturnRequest.html")


def review_submission(request):
    """Submit a review."""
    return render(request, "reviews/reviewSubmission.html")

