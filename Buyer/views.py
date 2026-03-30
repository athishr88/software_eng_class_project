from urllib import request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from General.models import Book, Inventory
from .models import ShippingAddress, PaymentMethod, Order, OrderItem, ReturnRequest, Cart, Review
from django.http import HttpResponse
import uuid
from decimal import Decimal
from datetime import datetime



@login_required
def home(request):
    """Buyer home / dashboard."""
    orders = Order.objects.filter(user=request.user).order_by("-created_at")

    stats = {
        "total_orders": orders.count(),
        "open_orders": orders.filter(status__in=["pending", "paid", "shipped"]).count(),
    }
    recent_orders = orders[:5]

    default_address = ShippingAddress.objects.filter(
        user=request.user,
        is_default=True
    ).first()

    default_payment = PaymentMethod.objects.filter(
        user=request.user,
        is_default=True,
    ).first()

    return buyer_dashboard(request)
    
@login_required
def buyer_dashboard(request):
    """Buyer dashboard."""
    all_orders = Order.objects.filter(user=request.user).order_by("created_at")
    
    
    numbered_orders = []

    for index, order in enumerate(all_orders, start=1):
        numbered_orders.append({
            "display_number": index,
            "order": order,
        })
    recent_orders = numbered_orders[::-1][:5]

    stats = {
        "total_orders": len(all_orders),
        "open_orders": all_orders.filter(status__in=["pending", "paid", "shipped"]).count(),
    }

    default_address = ShippingAddress.objects.filter(
        user=request.user,
        is_default=True
    ).first()

    default_payment = PaymentMethod.objects.filter(
        user=request.user,
        is_default=True,
    ).first()

    context = {
        "stats": stats,
        "credit_balance": 0,
        "recent_orders": recent_orders,
        "default_address": default_address,
        "default_payment": default_payment,
    }
    return render(request, "dashboard/buyer_dashboard.html", context)

@login_required
def buyer_profile(request):
    return render(request, "account/buyer_profile.html")

def add_to_cart(request, book_id):
    if request.method == "POST":
        book = get_object_or_404(Book, pk=book_id)
        inventory = get_object_or_404(Inventory, book=book)

        cart = request.session.get("cart", {})
        quantity = int(request.POST.get("quantity", 1))

        book_id_str = str(book.id)
        current_qty = cart.get(book_id_str, {}).get("quantity", 0)
        new_qty = current_qty + quantity

        if new_qty > inventory.quantity_available:
            messages.error(request, f"Cannot add {quantity} of {book.title} to cart. Only {inventory.quantity_available - current_qty} available.")
            return redirect("cart")

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
    cart_subtotal = Decimal("0.00")
    total_items = 0

    for book_id, item in cart.items():
        book = get_object_or_404(Book, id=book_id)
        inventory = get_object_or_404(Inventory, book=book)
        quantity = int(item["quantity"])
        price = Decimal(book.base_price_cents) / Decimal("100")
        subtotal = (price * quantity).quantize(Decimal("0.01"))

        cart_items.append({
            "id": book.id,
            "book": book,
            "quantity": quantity,
            "price": price,
            "subtotal": subtotal,
            "available_stock": inventory.quantity_available,
        })

        cart_subtotal += subtotal
        total_items += quantity

    tax = (cart_subtotal * Decimal("0.07")).quantize(Decimal("0.01"))
    fees = Decimal("2.99") if cart_items else Decimal("0.00")
    cart_total = (cart_subtotal + tax + fees).quantize(Decimal("0.01"))

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
                messages.success(request, "Item quantity updated in cart.")
            else:
                del cart[item_id_str]
                messages.success(request, "Item removed from cart.")
        
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
@transaction.atomic
def place_order(request):
    if request.method != "POST":
        return redirect("checkout")
    
    cart = request.session.get("cart", {})
    
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    shipping_address = ShippingAddress.objects.filter(user=request.user, is_default=True).first()
    payment_method = PaymentMethod.objects.filter(user=request.user, is_default=True).first()

    if not shipping_address:
        messages.error(request, "Please select a shipping address.")
        return redirect("checkout")

    if not payment_method:
        messages.error(request, "Please select a payment method.")
        return redirect("checkout")
    
    subtotal = Decimal("0.00")
    
    for book_id, item in cart.items():
        book = get_object_or_404(Book, id=book_id)
        quantity = int(item["quantity"])
        inventory = get_object_or_404(Inventory, book_id=book_id)

        if inventory.quantity_available < quantity:
            messages.error(request, f"Not enough stock for {book.title}.")
            return redirect("cart")

        price = Decimal(book.base_price_cents) / Decimal("100")
        line_total = price * quantity
        subtotal += line_total

    tax = (subtotal * Decimal("0.07")).quantize(Decimal("0.01"))
    fees = Decimal("2.99") if cart else Decimal("0.00")
    total = (subtotal + tax + fees).quantize(Decimal("0.01"))
    
    order = Order.objects.create(
        user=request.user,
        shipping_address=shipping_address,
        payment_method=payment_method,
        status="pending",
        subtotal=subtotal,
        tax = tax,
        fees = fees,
        total = total,
    )
    for book_id, item in cart.items():
        quantity = int(item["quantity"])
        book = get_object_or_404(Book, id=book_id)
        inventory = get_object_or_404(Inventory, book=book)

        price = Decimal(book.base_price_cents) / Decimal("100")
        line_total = (price * quantity).quantize(Decimal("0.01"))

        OrderItem.objects.create(
            order=order,
            book=book,
            quantity=quantity,
            price=price,
            subtotal=line_total,
        )
        
        inventory.quantity_available -= quantity
        inventory.save()

    request.session["cart"] = {}
    request.session.modified = True

    messages.success(request, "Order placed successfully.")
    return redirect("order_detail", order_id=order.id)

@login_required
def buyer_orders(request):
    order = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "orders/orderHistory.html", {"order": order})

def order_confirmation(request):
    """Order confirmation after place order."""
    return render(request, "orders/orderConfirmation.html")

@login_required
def order_detail(request, order_id=None):
    """Single order detail."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = order.items.all()

    reviews = Review.objects.filter(user=request.user, order=order)
    review_map = {review.order_item_id: review for review in reviews}

    for item in items:
        item.user_review = review_map.get(item.id)

    buyer_orders = Order.objects.filter(user=request.user).order_by("created_at")
    display_number = 1

    for index, buyer_order in enumerate(buyer_orders, start=1):
        if buyer_order.id == order.id:
            display_number = index
            break
    return render(request, "orders/orderDetail.html", {
        "order": order,
        "items": items,
        "display_number": display_number,
        })


def order_history(request):
    orders = Order.objects.filter(user=request.user)

    status = request.GET.get("status")
    from_date = request.GET.get("from")
    to_date = request.GET.get("to")

    if status:
        orders = orders.filter(status=status)

    if from_date:
        try:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            orders = orders.filter(created_at__date__gte=from_date)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
            orders = orders.filter(created_at__date__lte=to_date)
        except ValueError:
            pass

    orders_oldest_first = list(orders.order_by("created_at"))
    orders = orders.prefetch_related("items__book").order_by("-created_at")
    reviews = Review.objects.filter(user=request.user)
    review_map = {review.order_item_id: review for review in reviews}
    numbered_orders = []

    for index, order in enumerate(orders_oldest_first, start=1):
        numbered_orders.append({
            "display_number": index,
            "order": order,
        })

    numbered_orders.reverse()
    return render(request, "orders/orderHistory.html", {"numbered_orders": numbered_orders, "review_map": review_map})

@login_required
def return_request(request, order_id):
    """Request a return."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()

    existing_request = ReturnRequest.objects.filter(order=order, user=request.user).first()

    if existing_request:
        messages.info(request, "A return request already exists for this order.")
        return redirect("order_detail", order_id=order.id)
    
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()

        if not reason:
            messages.error(request, "Please provide a reason for the return.")
            return render(request, "orders/ReturnRequest.html", {"order": order})
        
        ReturnRequest.objects.create(
            order=order,
            user=request.user,
            reason=reason,
            status="pending"
        )
        messages.success(request, "Your return request has been submitted.")
        return redirect("order_detail", order_id=order.id)
    return render(request, "orders/ReturnRequest.html", {"order": order, "order_items": order_items,})

@login_required
def return_request_submit(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if request.method != "POST":
        return redirect("return_request", order_id, user=request.user)
    
    order_item_id = request.POST.get("order_item_id")
    reason = request.POST.get("reason", "").strip()
    order_item = get_object_or_404(OrderItem, id=order_item_id, order=order)
    details = request.POST.get("details", "").strip()

    quantity = request.POST.get(f"quantity_{order_item.id}", "1")
    quantity = int(quantity)

    if quantity > order_item.quantity:
        messages.error(request, "Invalid quantity selected.")
        return redirect("return_request", order_id=order.id)

    
    ###if not reason:
        return render(request, "orders/ReturnRequest.html", {
            "order": order,
            "order_items": order_items,
            "return_error": "Please select a reason for the return.",
            })####
        
    ReturnRequest.objects.create(
        order=order,
        user=request.user,
        order_item=order_item,
        reason=reason,
        details=details,
        quantity=quantity,
        status="pending",
    )

    messages.success(request, "Your return request was submitted.")
    return redirect("order_detail", order_id=order.id)
   
@login_required
def save_inline_review(request, order_id):
    if request.method != "POST":
        return redirect("order_detail", order_id=order_id)
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_item_id = request.POST.get("order_item_id")
    rating = request.POST.get("rating")
    comment = request.POST.get("comment", "").strip()

    print("POST DATA:", request.POST)
    print("ORDER ITEM ID:", request.POST.get("order_item_id"))
    print("RATING:", request.POST.get("rating"))
    print("COMMENT:", request.POST.get("comment"))
    if not order_item_id:
        messages.error(request, "Please select a rating.")
        return redirect("order_detail", order_id=order.id)
        
    order_item = get_object_or_404(OrderItem, id=order_item_id, order=order)

    if not rating:
        messages.error(request, "Please select a rating.")
        return redirect("order_detail", order_id=order.id)
    try:
        rating = int(rating)
        
    except ValueError:
        messages.error(request, "Invalid rating.")
        return redirect("order_detail", order_id=order.id)
        
    if rating < 1 or rating > 5:
        messages.error(request, "Rating must be between 1 and 5.")
        return redirect("order_detail", order_id=order.id)

    review = Review.objects.filter(user=request.user, order_item=order_item).first()
    if review:
        review.rating = rating
        review.comment = comment
        review.save()
        messages.success(request, "Your review has been updated.")
    else:
        Review.objects.create(
            user=request.user,
            book=order_item.book,
            order=order,
            order_item=order_item,
            rating=rating,
            comment=comment,
        )
        messages.success(request, "Your review has been submitted.")
    return redirect("order_detail", order_id=order.id)
   



def review_submission(request):
    """Submit a review."""
    return render(request, "reviews/reviewSubmission.html")

