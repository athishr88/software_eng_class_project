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


@login_required(login_url="login")
def buyer_checkout(request):
    cart_items, subtotal_cents = db_cart_lines(request.user)
    cart_subtotal = subtotal_cents / 100.0
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
        messages.success(request, "Order placed.")
        return redirect("order_confirmation", order_id=order.id)

    return render(
        request,
        "checkout/buyer_checkout.html",
        {
            "cart_items": cart_items,
            "cart_subtotal": cart_subtotal,
            "tax": tax,
            "fees": fees,
            "final_total": final_total,
            "addresses": addresses,
            "selected_address": selected_address,
            "checkout_error": None,
        },
    )


def remove_cart_item(request, item_id):
    if request.method == "POST":
        if request.user.is_authenticated:
            CartItem.objects.filter(cart__user=request.user, book_id=item_id).delete()
        else:
            cart = request.session.get("cart", {})
            item_id_str = str(item_id)
            if item_id_str in cart:
                del cart[item_id_str]
            request.session["cart"] = cart
            request.session.modified = True
    return redirect("cart")


def update_cart_item(request, item_id):
    if request.method == "POST":
        try:
            quantity = int(request.POST.get("quantity", 1))
            if quantity < 1:
                quantity = 1
        except (TypeError, ValueError):
            quantity = 1

        if request.user.is_authenticated:
            ci = CartItem.objects.filter(
                cart__user=request.user, book_id=item_id
            ).select_related("book").first()
            if ci:
                ci.quantity = quantity
                ci.unit_price_cents = ci.book.base_price_cents
                ci.save(update_fields=["quantity", "unit_price_cents", "updated_at"])
        else:
            cart = request.session.get("cart", {})
            item_id_str = str(item_id)
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


    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "profile":
            fn = (request.POST.get("first_name") or "").strip()
            ln = (request.POST.get("last_name") or "").strip()
            phone = (request.POST.get("phone") or "").strip() or None
            steward_city = (request.POST.get("steward_city") or "").strip() or None
            errs = []
            if not fn:
                errs.append("First name is required.")
            if not ln:
                errs.append("Last name is required.")
            if errs:
                ctx["profile_error"] = " ".join(errs)
            else:
                user.first_name = fn[:100]
                user.last_name = ln[:100]
                user.phone = phone[:50] if phone else None
                user.steward_city = steward_city[:120] if steward_city else None
                user.save()
                messages.success(request, "Profile updated.")
                return redirect("buyer_profile")

        elif action == "password":
            current = request.POST.get("current_password") or ""
            new_pw = request.POST.get("new_password") or ""
            confirm = request.POST.get("confirm_password") or ""
            errs = []
            if not user.check_password(current):
                errs.append("Current password is incorrect.")
            if len(new_pw) < 8:
                errs.append("New password must be at least 8 characters.")
            if new_pw != confirm:
                errs.append("New passwords do not match.")
            if errs:
                ctx["password_error"] = " ".join(errs)
            else:
                user.set_password(new_pw)
                user.save()
                messages.success(request, "Password updated.")
                from django.contrib.auth import update_session_auth_hash

                update_session_auth_hash(request, user)
                return redirect("buyer_profile")

    ctx["profile_user"] = user
    return render(request, "account/buyer_profile.html", ctx)


@login_required(login_url="login")
def order_confirmation(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("shipping_snapshot"),
        pk=order_id,
        user=request.user,
    )
    shipping = getattr(order, "shipping_snapshot", None)
    order_items = []
    for oi in order.orderitem_set.all().select_related("book"):
        snap = getattr(oi, "book_snapshot", None)
        order_items.append(
            {
                "title": snap.title if snap else oi.book.title,
                "quantity": oi.quantity,
                "line_total": f"{oi.line_total_cents / 100:.2f}",
            }
        )
    return render(
        request,
        "orders/orderConfirmation.html",
        {
            "order": order,
            "shipping": shipping,
            "order_items": order_items,
            "order_total_display": f"{order.total_cents / 100:.2f}",
        },
    )


@login_required(login_url="login")
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related(
            "shipping_address",
            "shipping_snapshot",
        ).prefetch_related(
            Prefetch(
                "orderitem_set",
                queryset=OrderItem.objects.select_related("book", "book_snapshot"),
            )
        ),
        pk=order_id,
        user=request.user,
    )
    shipping = getattr(order, "shipping_snapshot", None)
    items = []
    for oi in order.orderitem_set.all():
        snap = getattr(oi, "book_snapshot", None)
        items.append(
            {
                "title": snap.title if snap else oi.book.title,
                "quantity": oi.quantity,
                "line_total": oi.line_total_cents / 100.0,
            }
        )
    has_return = hasattr(order, "returnrequest")
    can_request_return = order.status in ("paid", "shipped", "delivered") and not has_return

    return render(
        request,
        "orders/orderDetail.html",
        {
            "order": order,
            "shipping": shipping,
            "order_items": items,
            "order_total_display": f"{order.total_cents / 100:.2f}",
            "order_subtotal_display": f"{order.subtotal_cents / 100:.2f}",
            "can_request_return": can_request_return,
            "can_leave_review": False,
        },
    )


@login_required(login_url="login")
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


    if request.method == "POST":
        category = (request.POST.get("reason_category") or "").strip()
        details = (request.POST.get("reason_details") or "").strip()
        parts = []
        if category:
            parts.append(f"[{category}]")
        if details:
            parts.append(details)
        reason = "\n".join(parts).strip()
        if not reason:
            return render(
                request,
                "orders/ReturnRequest.html",
                {
                    "order": order,
                    "return_error": "Please describe your return reason.",
                },
            )
        ReturnRequest.objects.create(order=order, reason=reason[:4000])
        messages.success(request, "Return request submitted.")
        return redirect("order_detail", order_id=order.id)

    return render(request, "orders/ReturnRequest.html", {"order": order})


def review_submission(request):
    """Submit a review (no Review model in project schema yet)."""
    return render(request, "reviews/reviewSubmission.html")
