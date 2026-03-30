import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from Buyer.cart_helpers import add_book_to_db_cart, clear_db_cart, db_cart_lines
from Buyer.models import (
    CartItem,
    Order,
    OrderItem,
    OrderItemBookSnapshot,
    OrderShippingAddress,
    PaymentMethod,
    ReturnRequest,
)
from General.models import Address, Book, Inventory, User

_STEWARD_CONTRIBUTION_DEFAULT = Decimal("2.00")
_STEWARD_CONTRIBUTION_MAX = Decimal("100.00")


def _parse_steward_contribution_dollars(raw):
    """
    Parse checkout steward contribution. Blank → default $2.00.
    Returns (Decimal value in dollars, is_invalid).
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return _STEWARD_CONTRIBUTION_DEFAULT, False
    try:
        v = Decimal(str(raw).strip())
    except InvalidOperation:
        return None, True
    if v < 0:
        return None, True
    if v > _STEWARD_CONTRIBUTION_MAX:
        v = _STEWARD_CONTRIBUTION_MAX
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), False


def _steward_cents_from_dollars(dollars: Decimal) -> int:
    return int((dollars * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _steward_points_from_contribution_cents(cents: int) -> int:
    return cents // 10


def _buyer_return_status_label(return_request):
    if not return_request:
        return None
    if return_request.status == "refunded":
        return "Return complete"
    if return_request.status == "rejected":
        return "Return declined"
    return "Return requested"


def _addresses_for_user(user):
    return Address.objects.filter(user=user).order_by("-is_default", "-updated_at")


def _payment_methods_for_user(user):
    return PaymentMethod.objects.filter(user=user).order_by("-is_default", "-updated_at")


def _order_items_from_snapshots(order):
    """
    Line items for display using OrderItemBookSnapshot for title/author when present
    (so seller edits to Book do not change past orders). Prices come from OrderItem.
    """
    items = []
    for oi in order.orderitem.all().select_related("book", "book_snapshot"):
        snap = getattr(oi, "book_snapshot", None)
        book = oi.book
        title = snap.title if snap else (oi.title or book.title)
        author = snap.author if snap else (oi.author or book.author)
        items.append(
            {
                "title": title,
                "author": author,
                "deposit_required": getattr(oi, "deposit_required", False),
                "deposit_amount": round(getattr(oi, "deposit_amount_cents", 0) / 100.0, 2),
                "quantity": oi.quantity,
                "unit_price_cents": oi.unit_price_cents,
                "unit_price": oi.unit_price_cents / 100.0,
                "line_total_cents": oi.line_total_cents,
                "line_total": oi.line_total_cents / 100.0,
            }
        )
    return items


def _checkout_page_context(
    user,
    cart_items,
    subtotal_cents,
    steward_raw,
    *,
    addresses=None,
    selected_address=None,
    payment_methods=None,
    selected_payment=None,
    checkout_error=None,
):
    if addresses is None:
        addresses = list(_addresses_for_user(user))
    if payment_methods is None:
        payment_methods = list(_payment_methods_for_user(user))

    tax_cents = int(round(subtotal_cents * 0.07))
    fees_cents = 299 if cart_items else 0
    base_total_cents = subtotal_cents + tax_cents + fees_cents
    cart_subtotal = subtotal_cents / 100.0
    tax = round(tax_cents / 100.0, 2)
    fees = round(fees_cents / 100.0, 2)

    steward_d, steward_invalid = _parse_steward_contribution_dollars(steward_raw)
    if steward_invalid:
        steward_display = str(steward_raw).strip() if steward_raw is not None else ""
        steward_contribution_cents = 0
        steward_points_preview = 0
        steward_line_dollars_display = "0.00"
    else:
        steward_display = str(steward_d)
        steward_contribution_cents = _steward_cents_from_dollars(steward_d)
        steward_points_preview = _steward_points_from_contribution_cents(steward_contribution_cents)
        steward_line_dollars_display = f"{steward_contribution_cents / 100:.2f}"

    total_cents = base_total_cents + steward_contribution_cents
    final_total = round(total_cents / 100.0, 2)

    return {
        "cart_items": cart_items,
        "cart_subtotal": cart_subtotal,
        "tax": tax,
        "fees": fees,
        "final_total": final_total,
        "addresses": addresses,
        "selected_address": selected_address,
        "payment_methods": payment_methods,
        "selected_payment": selected_payment,
        "checkout_error": checkout_error,
        "steward_contribution_value": steward_display,
        "steward_points_preview": steward_points_preview,
        "steward_line_dollars_display": steward_line_dollars_display,
        "base_total_cents": base_total_cents,
        "steward_contribution_invalid": steward_invalid,
    }


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
    steward_raw_get = request.GET.get("steward_contribution") if request.method != "POST" else None

    addresses = list(_addresses_for_user(request.user))
    payment_methods = list(_payment_methods_for_user(request.user))

    selected_address = None
    if addresses:
        sel = (request.POST.get("shipping_address_id") if request.method == "POST" else None) or request.GET.get(
            "shipping_address_id"
        )
        if sel:
            selected_address = next((a for a in addresses if str(a.id) == str(sel)), None)
        if not selected_address:
            selected_address = next((a for a in addresses if a.is_default), None) or addresses[0]

    selected_payment = None
    if payment_methods:
        sel_pm = (request.POST.get("payment_method_id") if request.method == "POST" else None) or request.GET.get(
            "payment_method_id"
        )
        if sel_pm:
            selected_payment = next((p for p in payment_methods if str(p.id) == str(sel_pm)), None)
        if not selected_payment:
            selected_payment = next((p for p in payment_methods if p.is_default), None) or payment_methods[0]

    pay_method = None

    if request.method == "POST":
        post_steward = request.POST.get("steward_contribution")
        if not cart_items:
            return render(
                request,
                "checkout/buyer_checkout.html",
                _checkout_page_context(
                    request.user,
                    [],
                    0,
                    post_steward,
                    addresses=addresses,
                    selected_address=selected_address,
                    payment_methods=payment_methods,
                    selected_payment=selected_payment,
                    checkout_error="Your cart is empty.",
                ),
            )
        addr_id = request.POST.get("shipping_address_id")
        if not addr_id:
            return render(
                request,
                "checkout/buyer_checkout.html",
                _checkout_page_context(
                    request.user,
                    cart_items,
                    subtotal_cents,
                    post_steward,
                    addresses=addresses,
                    selected_address=selected_address,
                    payment_methods=payment_methods,
                    selected_payment=selected_payment,
                    checkout_error="Please select a shipping address.",
                ),
            )
        try:
            ship_addr = Address.objects.get(pk=int(addr_id), user=request.user)
        except (Address.DoesNotExist, ValueError, TypeError):
            return render(
                request,
                "checkout/buyer_checkout.html",
                _checkout_page_context(
                    request.user,
                    cart_items,
                    subtotal_cents,
                    post_steward,
                    addresses=addresses,
                    selected_address=selected_address,
                    payment_methods=payment_methods,
                    selected_payment=selected_payment,
                    checkout_error="Invalid shipping address.",
                ),
            )

        pm_id = request.POST.get("payment_method_id")
        if not pm_id:
            return render(
                request,
                "checkout/buyer_checkout.html",
                _checkout_page_context(
                    request.user,
                    cart_items,
                    subtotal_cents,
                    post_steward,
                    addresses=addresses,
                    selected_address=ship_addr,
                    payment_methods=payment_methods,
                    selected_payment=selected_payment,
                    checkout_error="Please select a payment method.",
                ),
            )
        try:
            pay_method = PaymentMethod.objects.get(pk=int(pm_id), user=request.user)
        except (PaymentMethod.DoesNotExist, ValueError, TypeError):
            return render(
                request,
                "checkout/buyer_checkout.html",
                _checkout_page_context(
                    request.user,
                    cart_items,
                    subtotal_cents,
                    post_steward,
                    addresses=addresses,
                    selected_address=ship_addr,
                    payment_methods=payment_methods,
                    selected_payment=selected_payment,
                    checkout_error="Invalid payment method.",
                ),
            )

        steward_d, steward_invalid = _parse_steward_contribution_dollars(post_steward)
        if steward_invalid:
            return render(
                request,
                "checkout/buyer_checkout.html",
                _checkout_page_context(
                    request.user,
                    cart_items,
                    subtotal_cents,
                    post_steward,
                    addresses=addresses,
                    selected_address=ship_addr,
                    payment_methods=payment_methods,
                    selected_payment=pay_method,
                    checkout_error="Enter a valid steward contribution (0 to $100).",
                ),
            )
        steward_contribution_cents = _steward_cents_from_dollars(steward_d)
        tax_cents = int(round(subtotal_cents * 0.07))
        fees_cents = 299 if cart_items else 0
        total_cents = subtotal_cents + tax_cents + fees_cents + steward_contribution_cents

        became_steward = False
        try:
            with transaction.atomic():
                buyer_locked = User.objects.select_for_update().get(pk=request.user.pk)
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
                    payment_method=pay_method,
                    steward_contribution=None,
                    status="paid",
                    subtotal_cents=subtotal_cents,
                    tax_cents=tax_cents,
                    fees_cents=fees_cents,
                    discount_cents=0,
                    steward_contribution_cents=steward_contribution_cents,
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
                        title=book.title,
                        author=book.author,
                        deposit_required=getattr(book, "deposit_required", False),
                        deposit_amount_cents=getattr(book, "deposit_amount_cents", 0),
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

                pts = _steward_points_from_contribution_cents(steward_contribution_cents)
                was_steward_verified = buyer_locked.steward_verified
                if pts:
                    buyer_locked.steward_progress = min(100, buyer_locked.steward_progress + pts)
                if buyer_locked.steward_progress >= 100:
                    buyer_locked.steward_verified = True
                    buyer_locked.steward_progress = 100
                progress_update_fields = ["steward_progress", "updated_at"]
                if buyer_locked.steward_verified != was_steward_verified:
                    progress_update_fields.append("steward_verified")
                buyer_locked.save(update_fields=progress_update_fields)
                became_steward = buyer_locked.steward_verified and not was_steward_verified

        except ValueError as e:
            return render(
                request,
                "checkout/buyer_checkout.html",
                _checkout_page_context(
                    request.user,
                    cart_items,
                    subtotal_cents,
                    post_steward,
                    addresses=addresses,
                    selected_address=ship_addr,
                    payment_methods=payment_methods,
                    selected_payment=pay_method or selected_payment,
                    checkout_error=str(e),
                ),
            )

        clear_db_cart(request.user)
        request.session["cart"] = {}
        request.session.modified = True
        if became_steward:
            request.session["steward_milestone_order_id"] = order.id
            return redirect("steward_welcome")
        messages.success(request, "Thank you! Your order has been placed.")
        return redirect("order_confirmation", order_id=order.id)

    return render(
        request,
        "checkout/buyer_checkout.html",
        _checkout_page_context(
            request.user,
            cart_items,
            subtotal_cents,
            steward_raw_get,
            addresses=addresses,
            selected_address=selected_address,
            payment_methods=payment_methods,
            selected_payment=selected_payment,
            checkout_error=None,
        ),
    )


@login_required(login_url="login")
def steward_welcome(request):
    """
    One-time style welcome after `steward_progress` reaches 100 and `steward_verified` is set.
    Collects required `steward_city`, then sends the buyer to order confirmation or dashboard.
    """
    user = request.user
    if not user.steward_verified:
        return redirect("catalog")

    pending_order_id = request.session.get("steward_milestone_order_id")
    if pending_order_id is not None and not Order.objects.filter(
        pk=pending_order_id, user=user
    ).exists():
        del request.session["steward_milestone_order_id"]
        request.session.modified = True
        pending_order_id = None

    if request.method == "POST":
        city = (request.POST.get("steward_city") or "").strip()
        if not city:
            return render(
                request,
                "steward/steward_welcome.html",
                {
                    "city_error": "City is required so we can show your support in the right community.",
                    "steward_city_value": (request.POST.get("steward_city") or "").strip(),
                    "pending_order_id": pending_order_id,
                },
            )
        user.steward_city = city[:120]
        user.save(update_fields=["steward_city", "updated_at"])

        pop_id = request.session.pop("steward_milestone_order_id", None)
        request.session.modified = True
        if pop_id and Order.objects.filter(pk=pop_id, user=user).exists():
            messages.success(
                request,
                "You're all set—welcome to the steward community. Your order details are next.",
            )
            return redirect("order_confirmation", order_id=pop_id)
        messages.success(request, "Thanks—your steward profile is updated.")
        return redirect("buyer_dashboard")

    return render(
        request,
        "steward/steward_welcome.html",
        {
            "city_error": None,
            "steward_city_value": user.steward_city or "",
            "pending_order_id": pending_order_id,
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
    """List saved PaymentMethod rows."""
    return render(
        request,
        "checkout/buyer_payments.html",
        {"payment_methods": list(_payment_methods_for_user(request.user))},
    )


@login_required(login_url="login")
def buyer_add_payment_method(request):
    """Form to add a PaymentMethod (last4 + meta only; full card number and CVV are not stored)."""
    next_url_param = (request.POST.get("next") or request.GET.get("next") or "").strip()

    if request.method == "POST":
        cardholder_name = (request.POST.get("cardholder_name") or "").strip()
        card_number = (request.POST.get("card_number") or "").strip()
        brand = (request.POST.get("brand") or "").strip()
        cvv = (request.POST.get("cvv") or "").strip()
        exp_month_raw = (request.POST.get("exp_month") or "").strip()
        exp_year_raw = (request.POST.get("exp_year") or "").strip()
        is_default = request.POST.get("is_default") == "on"

        errs = []
        if not cardholder_name:
            errs.append("Cardholder name is required.")
        if not brand:
            errs.append("Brand is required.")
        if not cvv or len(cvv) < 3:
            errs.append("CVV is required (not stored).")
        digits = re.sub(r"\D", "", card_number)
        if len(digits) < 13:
            errs.append("Enter a valid card number (full number is not stored; only last 4 digits are saved).")
        try:
            exp_month = int(exp_month_raw)
            if not 1 <= exp_month <= 12:
                raise ValueError
        except (TypeError, ValueError):
            errs.append("Enter a valid expiration month (1–12).")
        try:
            exp_year = int(exp_year_raw)
            if exp_year < 2000 or exp_year > 2100:
                raise ValueError
        except (TypeError, ValueError):
            errs.append("Enter a valid 4-digit expiration year.")
        today = date.today()
        if not errs:
            if exp_year < today.year or (exp_year == today.year and exp_month < today.month):
                errs.append("This card appears to be expired.")

        if errs:
            for e in errs:
                messages.error(request, e)
            return render(
                request,
                "checkout/buyer_add_payment_method.html",
                {"next": next_url_param},
            )

        last4 = digits[-4:]
        if is_default:
            PaymentMethod.objects.filter(user=request.user, is_default=True).update(is_default=False)

        PaymentMethod.objects.create(
            user=request.user,
            cardholder_name=cardholder_name[:120],
            brand=brand[:40],
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
        )
        messages.success(request, "Payment method saved.")
        if next_url_param and next_url_param.startswith("/"):
            return redirect(next_url_param)
        return redirect("buyer_payments")

    return render(
        request,
        "checkout/buyer_add_payment_method.html",
        {"next": next_url_param},
    )


@login_required(login_url="login")
def set_default_payment_method(request, payment_method_id):
    if request.method != "POST":
        return redirect("buyer_payments")
    pm = get_object_or_404(PaymentMethod, pk=payment_method_id, user=request.user)
    PaymentMethod.objects.filter(user=request.user).update(is_default=False)
    pm.is_default = True
    pm.save(update_fields=["is_default", "updated_at"])
    messages.success(request, "Default payment method updated.")
    return redirect("buyer_payments")


@login_required(login_url="login")
def delete_payment_method(request, payment_method_id):
    if request.method != "POST":
        return redirect("buyer_payments")
    pm = get_object_or_404(PaymentMethod, pk=payment_method_id, user=request.user)
    pm.delete()
    messages.success(request, "Payment method removed.")
    return redirect("buyer_payments")


@login_required(login_url="login")
def buyer_shipping(request):
    """List saved shipping Address rows for the logged-in user."""
    return render(
        request,
        "checkout/buyer_shipping.html",
        {"addresses": _addresses_for_user(request.user)},
    )


@login_required(login_url="login")
def buyer_add_shipping_address(request):
    """Form to add a shipping Address for the logged-in user."""
    next_url_param = (request.POST.get("next") or request.GET.get("next") or "").strip()

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
            return render(
                request,
                "checkout/buyer_add_shipping_address.html",
                {"next": next_url_param},
            )

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

        if next_url_param and next_url_param.startswith("/"):
            return redirect(next_url_param)
        return redirect("buyer_shipping")

    return render(
        request,
        "checkout/buyer_add_shipping_address.html",
        {"next": next_url_param},
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
    ctx["store_credit_display"] = f"{(user.store_credit_cents or 0) / 100:.2f}"
    return render(request, "account/buyer_profile.html", ctx)


@login_required(login_url="login")
def order_confirmation(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("shipping_snapshot").prefetch_related(
            Prefetch(
                "orderitem",
                queryset=OrderItem.objects.select_related("book", "book_snapshot"),
            )
        ),
        pk=order_id,
        user=request.user,
    )
    shipping = getattr(order, "shipping_snapshot", None)
    order_items = _order_items_from_snapshots(order)
    steward_pts = order.steward_contribution_cents // 10
    return render(
        request,
        "orders/orderConfirmation.html",
        {
            "order": order,
            "shipping": shipping,
            "order_items": order_items,
            "order_total_display": f"{order.total_cents / 100:.2f}",
            "steward_points_earned": steward_pts,
            "steward_contribution_display": f"{order.steward_contribution_cents / 100:.2f}",
        },
    )


@login_required(login_url="login")
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related(
            "shipping_address",
            "shipping_snapshot",
            "returnrequest",
        ).prefetch_related(
            Prefetch(
                "orderitem",
                queryset=OrderItem.objects.select_related("book", "book_snapshot"),
            )
        ),
        pk=order_id,
        user=request.user,
    )
    shipping = getattr(order, "shipping_snapshot", None)
    items = _order_items_from_snapshots(order)
    try:
        return_request = order.returnrequest
    except ObjectDoesNotExist:
        return_request = None
    has_return = return_request is not None
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
            "return_request": return_request,
            "return_status_label": _buyer_return_status_label(return_request),
        },
    )


@login_required(login_url="login")
def order_history(request):
    qs = (
        Order.objects.filter(user=request.user)
        .annotate(item_count=Count("orderitem"))
        .order_by("-created_at")
    )

    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)

    date_from = (request.GET.get("from") or "").strip()
    if date_from:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date()
            qs = qs.filter(created_at__date__gte=start)
        except ValueError:
            pass

    date_to = (request.GET.get("to") or "").strip()
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").date()
            qs = qs.filter(created_at__date__lte=end)
        except ValueError:
            pass

    orders = list(qs[:200])
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
