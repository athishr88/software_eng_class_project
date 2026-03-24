from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from Buyer.cart_helpers import add_book_to_db_cart, clear_db_cart, db_cart_lines
from Buyer.models import (
    CartItem,
    Order,
    OrderItem,
    OrderItemBookSnapshot,
    OrderShippingAddress,
    ReturnRequest,
)
from General.models import Address, Book, Inventory


def _addresses_for_user(user):
    return Address.objects.filter(user=user).order_by("-is_default", "-updated_at")


def _cart_lines(session_cart):
    """Build cart lines from session; returns (lines, subtotal_cents). Each line: book, quantity, line_subtotal_cents."""
    lines = []
    subtotal_cents = 0
    for book_id, item_data in session_cart.items():
        try:
            book = Book.objects.select_related("inventory").get(
                pk=int(book_id), is_active=True
            )
        except (Book.DoesNotExist, ValueError, TypeError):
            continue
        qty = max(1, int(item_data.get("quantity", 1)))
        line_cents = book.base_price_cents * qty
        subtotal_cents += line_cents
        price = book.base_price_cents / 100.0
        lines.append(
            {
                "id": book.id,
                "book": book,
                "quantity": qty,
                "price": price,
                "subtotal": line_cents / 100.0,
                "line_subtotal_cents": line_cents,
            }
        )
    return lines, subtotal_cents


def home(request):
    """Buyer home / dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")


def buyer_dashboard(request):
    """Buyer dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")


def add_to_cart(request, book_id):
    if request.method == "POST":
        book = get_object_or_404(Book, pk=book_id, is_active=True)
        try:
            quantity = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        if quantity < 1:
            quantity = 1
        if request.user.is_authenticated:
            add_book_to_db_cart(request.user, book, quantity)
        else:
            cart = request.session.get("cart", {})
            book_id_str = str(book_id)
            if book_id_str in cart:
                cart[book_id_str]["quantity"] += quantity
            else:
                cart[book_id_str] = {"quantity": quantity}
            request.session["cart"] = cart
            request.session.modified = True
    return redirect("cart")


def buyer_cart(request):
    if request.user.is_authenticated:
        cart_items, subtotal_cents = db_cart_lines(request.user)
    else:
        session_cart = request.session.get("cart", {})
        cart_items, subtotal_cents = _cart_lines(session_cart)
    cart_subtotal = subtotal_cents / 100.0
    tax = round(cart_subtotal * 0.07, 2)
    fees = 0.00
    cart_total = round(cart_subtotal + tax + fees, 2)
    total_items = sum(item["quantity"] for item in cart_items)

    context = {
        "cart_items": cart_items,
        "cart_subtotal": cart_subtotal,
        "cart_total": cart_subtotal,
        "tax": tax,
        "fees": fees,
        "total_items": total_items,
        "addresses": [],
        "payment_methods": [],
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

    addresses = list(_addresses_for_user(request.user))
    selected_address = None
    if addresses:
        sel = (request.POST.get("shipping_address_id") if request.method == "POST" else None) or request.GET.get(
            "shipping_address_id"
        )
        if sel:
            selected_address = next((a for a in addresses if str(a.id) == str(sel)), None)
        if not selected_address:
            selected_address = next((a for a in addresses if a.is_default), None) or addresses[0]

    if request.method == "POST":
        if not cart_items:
            return render(
                request,
                "checkout/buyer_checkout.html",
                {
                    "cart_items": [],
                    "cart_subtotal": 0,
                    "tax": 0,
                    "fees": 0,
                    "final_total": 0,
                    "addresses": addresses,
                    "selected_address": selected_address,
                    "checkout_error": "Your cart is empty.",
                },
            )
        addr_id = request.POST.get("shipping_address_id")
        if not addr_id:
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
                    "checkout_error": "Please select a shipping address.",
                },
            )
        try:
            ship_addr = Address.objects.get(pk=int(addr_id), user=request.user)
        except (Address.DoesNotExist, ValueError, TypeError):
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
                    "checkout_error": "Invalid shipping address.",
                },
            )

        tax_cents = int(round(subtotal_cents * 0.07))
        fees_cents = 299 if cart_items else 0
        total_cents = subtotal_cents + tax_cents + fees_cents

        try:
            with transaction.atomic():
                locked_books = {}
                for line in cart_items:
                    inv = (
                        Inventory.objects.select_for_update()
                        .select_related("book")
                        .filter(book_id=line["book"].id)
                        .first()
                    )
                    if not inv:
                        raise ValueError(
                            f"No inventory record for “{line['book'].title}”. Ask the seller to restock."
                        )
                    if inv.quantity_available < line["quantity"]:
                        raise ValueError(
                            f"Not enough stock for “{line['book'].title}” (available {inv.quantity_available})."
                        )
                    locked_books[line["book"].id] = (inv, line)

                order = Order.objects.create(
                    user=request.user,
                    shipping_address=ship_addr,
                    steward_contribution=None,
                    status="paid",
                    subtotal_cents=subtotal_cents,
                    discount_cents=0,
                    total_cents=total_cents,
                )

                ship_name = (
                    ship_addr.label
                    or request.user.get_full_name().strip()
                    or request.user.email
                )
                OrderShippingAddress.objects.create(
                    order=order,
                    shipping_name=ship_name[:100] if ship_name else None,
                    shipping_line1=ship_addr.line1,
                    shipping_line2=ship_addr.line2,
                    shipping_city=ship_addr.city,
                    shipping_state=ship_addr.state,
                    shipping_postal_code=ship_addr.postal_code,
                    shipping_country=ship_addr.country,
                    source_address=ship_addr,
                )

                for book_id, (inv, line) in locked_books.items():
                    book = line["book"]
                    oi = OrderItem.objects.create(
                        order=order,
                        book=book,
                        quantity=line["quantity"],
                        unit_price_cents=book.base_price_cents,
                        line_total_cents=line["line_subtotal_cents"],
                    )
                    OrderItemBookSnapshot.objects.create(
                        order_item=oi,
                        source_book=book,
                        title=book.title,
                        author=book.author,
                        description=book.description,
                        isbn=book.isbn,
                        language=book.language,
                        publisher=book.publisher,
                        publication_year=book.publication_year,
                        cover_image_url=book.cover_image_url,
                        condition=book.condition,
                    )
                    inv.quantity_available -= line["quantity"]
                    inv.save(update_fields=["quantity_available", "updated_at"])

        except ValueError as e:
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
                    "selected_address": ship_addr,
                    "checkout_error": str(e),
                },
            )

        clear_db_cart(request.user)
        request.session["cart"] = {}
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


@login_required(login_url="login")
def buyer_payments(request):
    """Payment methods page. Card storage is not wired to a model yet."""
    if request.method == "POST":
        messages.info(
            request,
            "Saved payment methods are not stored in the database in this project yet.",
        )
        next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("buyer_payments")
    return render(
        request,
        "checkout/buyer_payments.html",
        {"payment_methods": []},
    )


@login_required(login_url="login")
def buyer_shipping(request):
    """Shipping / addresses: list and create Address rows for the logged-in user."""
    if request.method == "POST":
        label_raw = (request.POST.get("label") or "").strip()
        line1 = (request.POST.get("line1") or "").strip()
        line2_raw = (request.POST.get("line2") or "").strip()
        city = (request.POST.get("city") or "").strip()
        state = (request.POST.get("state") or "").strip()
        postal_code = (request.POST.get("postal_code") or "").strip()
        country = (request.POST.get("country") or "").strip()
        is_default = request.POST.get("is_default") == "on"

        if not all([line1, city, state, postal_code, country]):
            messages.error(
                request,
                "Street address, city, state, postal code, and country are required.",
            )
            return redirect("buyer_shipping")

        if is_default:
            Address.objects.filter(user=request.user, is_default=True).update(
                is_default=False
            )

        Address.objects.create(
            user=request.user,
            label=label_raw or None,
            line1=line1,
            line2=line2_raw or None,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            is_default=is_default,
        )
        messages.success(request, "Address saved.")

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("buyer_shipping")

    return render(
        request,
        "checkout/buyer_shipping.html",
        {"addresses": _addresses_for_user(request.user)},
    )


@login_required(login_url="login")
def set_default_shipping_address(request, address_id):
    if request.method != "POST":
        return redirect("buyer_shipping")
    addr = get_object_or_404(Address, pk=address_id, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    addr.is_default = True
    addr.save()
    messages.success(request, "Default shipping address updated.")
    return redirect("buyer_shipping")


@login_required(login_url="login")
def delete_shipping_address(request, address_id):
    if request.method != "POST":
        return redirect("buyer_shipping")
    addr = get_object_or_404(Address, pk=address_id, user=request.user)
    addr.delete()
    messages.success(request, "Address removed.")
    return redirect("buyer_shipping")


@login_required(login_url="login")
def buyer_profile(request):
    """Update User profile fields and password (schema: first_name, last_name, phone)."""
    user = request.user
    ctx = {}

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
    orders = Order.objects.filter(user=request.user).order_by("-created_at")[:200]
    return render(request, "orders/orderHistory.html", {"orders": orders})


@login_required(login_url="login")
def return_request_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if hasattr(order, "returnrequest"):
        return render(
            request,
            "orders/ReturnRequest.html",
            {
                "order": order,
                "return_error": "A return has already been submitted for this order.",
            },
        )

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
