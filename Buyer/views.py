from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from General.models import Book
from .models import ShippingAddress, PaymentMethod, Order, OrderItem
from django.http import HttpResponse
import uuid
from decimal import Decimal
from datetime import datetime




def home(request):
    """Buyer home / dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")


def buyer_dashboard(request):
    """Buyer dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")

@login_required
def buyer_profile(request):
    return render(request, "account/buyer_profile.html")

def add_to_cart(request, book_id):
    if request.method == "POST":
        print("ADD TO CART book_id:", book_id)

        book = get_object_or_404(Book, pk=book_id)

        cart = request.session.get("cart", {})
        quantity = int(request.POST.get("quantity", 1))

        book_id_str = str(book.id)

        if book_id_str in cart:
            cart[book_id_str]["quantity"] += quantity
        else:
            cart[book_id_str] = {
                "quantity": quantity
            }
        request.session["cart"] = cart
        request.session.modified = True
        messages.success(request, f"{book.title} added to cart.")
    return redirect("cart")


def buyer_cart(request):
    cart = request.session.get("cart", {})
    cart_items = []
    cart_subtotal = 0.00
    total_items = 0

    for book_id, item_data in cart.items():
        try:
            book = Book.objects.get(pk=book_id, is_active=True)
            quantity = item_data.get("quantity", 1)
            total_items += quantity
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
    fees = 2.99 if cart_items else 0.00
    cart_total = round(cart_subtotal + tax + fees, 2)

    addresses = ShippingAddress.objects.filter(user=request.user)
    payment_method = PaymentMethod.objects.filter(user=request.user)

    
    context = {
        "cart_items": cart_items,
        "total_items": total_items,
        "cart_subtotal": cart_subtotal,
        "cart_total": cart_total,
        "tax": tax,
        "fees": fees,
        "addresses": addresses,
        "payment_method": payment_method,
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

    addresses = ShippingAddress.objects.filter(user=request.user)
    payment_method = PaymentMethod.objects.filter(user=request.user)
    selected_payment = payment_method.filter(is_default=True).first() or addresses.first()
    selected_address = addresses.filter(is_default=True).first() or payment_method.first()

    context = {
        "cart_items": cart_items,
        "cart_subtotal": cart_subtotal,
        "tax": tax,
        "fees": fees,
        "final_total": final_total,
        "addresses": addresses,
        "payment_method": payment_method,
        "selected_address": selected_address,
        "selected_payment": selected_payment,
        "checkout_error": None,
    }

    return render(request, "checkout/buyer_checkout.html", context)

def remove_cart_item(request, item_id):
    if request.method == "POST":
        cart = request.session.get("cart", {})
        item_id_str = str(item_id)

        if item_id_str in cart:
            current_quantity = cart[item_id_str].get("quantity", 1)

            if current_quantity > 1:
                cart[item_id_str]["quantity"] = current_quantity - 1
            else:
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

@login_required
def buyer_payments(request):
    payment_method = PaymentMethod.objects.filter(user=request.user)
    
    context = {
        "payment_method": payment_method,
    }
    return render(request, "checkout/buyer_payments.html", context)

@login_required
def save_payment_method(request):
    if request.method == "POST":
        cardholder = request.POST.get("cardholder", "").strip()
        card_number = request.POST.get("card_number", "").replace(" ", "").strip()
        brand = request.POST.get("brand", "").strip()
        cvv = request.POST.get("cvv", "").strip()
        exp_month = request.POST.get("exp_month", "").strip()
        exp_year = request.POST.get("exp_year", "").strip()
        next_url = request.POST.get("next")

        if not cardholder or not card_number or not brand or not cvv or not exp_month or not exp_year:
            messages.error(request, "Please fill in all required fields.")
            return redirect(next_url or "buyer_payments")
        
        if len(card_number) < 4:
            messages.error(request, "Please enter a valid card number.")
            return redirect("buyer_payments")
        
        last4 = card_number[-4:]
        processor_token = f"tok_{uuid.uuid4().hex[:12]}"
        
        is_first_payment = not PaymentMethod.objects.filter(user=request.user).exists()


        PaymentMethod.objects.create(
            user=request.user,
            cardholder=cardholder,
            processor_token=processor_token,
            brand=brand,
            last4=last4,
            exp_month=int(exp_month),
            exp_year=int(exp_year),
            is_default=is_first_payment,
        )

        messages.success(request, "Payment method saved.")

        if next_url:
            return redirect(next_url)
        
        return redirect("buyer_payments")
    return redirect("buyer_payments")

@login_required
def action_delete_payment_method(request, method_id):
    if request.method == "POST":
        method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
        
        if Order.objects.filter(payment_method_id=method.id).exists():
            messages.error(request, "Cannot delete payment method in use.")
            return redirect("buyer_payments")
        method.delete()
        messages.success(request, "Payment method deleted.")
        return redirect("buyer_payments")
    
    messages.error(request, "Invalid request.")
    return redirect("buyer_payments")

@login_required
def set_default_payment_method(request, method_id):
    if request.method == "POST":
        PaymentMethod.objects.filter(user=request.user).update(is_default=False)
        method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
        method.is_default = True
        method.save()
        messages.success(request, "Default payment method updated.")
    return redirect("buyer_payments")

@login_required
def buyer_shipping(request):
    addresses = ShippingAddress.objects.filter(user=request.user)

    return render(request, "checkout/buyer_shipping.html", {
        "addresses": addresses,
    })

@login_required
def save_shipping_address(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        address_line_1 = request.POST.get("address_line_1", "").strip()
        address_line_2 = request.POST.get("address_line_2", "").strip()
        country = request.POST.get("country", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        zip_code = request.POST.get("zip_code", "").strip()

        next_url = request.POST.get("next")

        if not full_name or not address_line_1 or not country or not city or not state or not zip_code:
            messages.error(request, "Please fill in all required fields.")
            return redirect("buyer_shipping")
        
        has_addresses = ShippingAddress.objects.filter(user=request.user).exists()
        
        if not has_addresses:
            ShippingAddress.objects.filter(user=request.user).update(is_default=False)
        
        address = ShippingAddress.objects.create(
            user=request.user,
            full_name=full_name,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
            is_default=not has_addresses,
        )
        
        messages.success(request, "Shipping address saved.")

        if next_url:
            return redirect(next_url)
        
        return redirect("buyer_shipping")
    return redirect("buyer_shipping")

@login_required
def action_delete_address(request, addr_id):
    if request.method == "POST":
        address = get_object_or_404(ShippingAddress, id=addr_id, user=request.user)
        address.delete()
        messages.success(request, "Shipping address deleted.")
        return redirect("buyer_shipping")
    messages.error(request, "Invalid request.")
    return redirect("buyer_shipping")

@login_required
def set_default_address(request, addr_id):
    if request.method == "POST":
        ShippingAddress.objects.filter(user=request.user).update(is_default=False)
        address = get_object_or_404(ShippingAddress, id=addr_id, user=request.user)
        address.is_default = True
        address.save()
        messages.success(request, "Default shipping address updated.")
    return redirect("buyer_shipping")

def proccess_payment(token, amount):
    if token.startswith("tok_"):
        return True
    return False

@login_required
def place_order(request):
    if request.method != "POST":
        return redirect("checkout")
    
    shipping_address_id = request.POST.get("shipping_address_id")
    payment_method_id = request.POST.get("payment_method_id")

    if not shipping_address_id or not payment_method_id:
        messages.error(request, "Please select a shipping address and payment method.")
        return redirect("checkout")
    
    shipping_address = get_object_or_404(
        ShippingAddress, id=shipping_address_id, user=request.user
    )
    payment_method = get_object_or_404(
        PaymentMethod, id=payment_method_id, user=request.user
    )

    if not payment_method.processor_token or not payment_method.processor_token.startswith("tok_"):
        messages.error(request, "Payment could not be processed.")
        return redirect("checkout")
    cart = request.session.get("cart", {})
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("cart")
    
    cart_items = []
    cart_subtotal = Decimal("0.00")

    for book_id, item_data in cart.items():
        try:
            book = Book.objects.get(pk=book_id, is_active=True)
            quantity = int(item_data.get("quantity", 1))
            price = Decimal(book.base_price_cents) / Decimal("100")
            subtotal = price * quantity

            cart_items.append({
                "book": book,
                "quantity": quantity,
                "price": price,
                "subtotal": subtotal,
            })

            cart_subtotal += subtotal
        except Book.DoesNotExist:
            continue

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("cart")
    
    tax = (cart_subtotal * Decimal("0.07")).quantize(Decimal("0.01"))
    fees = Decimal("2.99") if cart_items else Decimal("0.00")
    total = (cart_subtotal + tax + fees).quantize(Decimal("0.01"))

    order = Order.objects.create(
        user=request.user,
        shipping_address=shipping_address,
        payment_method=payment_method,
        subtotal=cart_subtotal,
        tax=tax,
        fees=fees,
        total=total,
        status="pending",
    )

    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            book=item["book"],
            quantity=item["quantity"],
            price=item["price"],
            subtotal=item["subtotal"],
        )

    request.session["cart"] = {}
    request.session.modified = True

    messages.success(request, "Order placed successfully.")

    return redirect("order/orderDetail.html", order_id=order.id)
@login_required
def buyer_orders(request):
    order = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "orders/orderHistory.html", {"orders": orders})

def order_confirmation(request):
    """Order confirmation after place order."""
    return render(request, "orders/orderConfirmation.html")

@login_required
def order_detail(request, order_id=None):
    """Single order detail."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = order.items.all()
    return render(request, "orders/orderDetail.html", {"order": order, "items": items,})


def order_history(request):
    orders = Order.objects.filter(user=request.user)

    status = request.GET.get("status")
    from_date = request.GET.get("from")
    to_date = request.GET.get("to")

    if status:
        orders=orders.filter(status=status)

    if from_date:
        try:
            from_date = datetime.strptime(from_date, "%Y-%m-%d")
            orders = orders.filter(created_at__date__gte=from_date)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date = datetime.strptime(to_date, "%Y-%m-%d")
            orders = orders.filter(created_at__date__lte=to_date)
        except ValueError:
            pass

    orders = orders.order_by("-created_at")
    return render(request, "orders/orderHistory.html", {"orders": orders})


def return_request(request):
    """Request a return."""
    return render(request, "orders/ReturnRequest.html")


def review_submission(request):
    """Submit a review."""
    return render(request, "reviews/reviewSubmission.html")

