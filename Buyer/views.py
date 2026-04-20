import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

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
from General.models import Address, Book, Inventory, StewardPool, User
from General.steward import (
    get_steward_pool,
    random_steward_attribution,
    user_free_book_eligible,
)
from Seller.webhook_notify import schedule_order_placed_webhooks

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
    return PaymentMethod.objects.filter(user=user).order_by("-is_default", "-id")

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
                "id": oi.id,
                "book_id": book.id,
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

\
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
    cart_has_steward_free = any(line.get("is_steward_free") for line in cart_items)
    fees_cents = 0 if cart_has_steward_free else (299 if cart_items else 0)
    base_total_cents = subtotal_cents + tax_cents + fees_cents
    cart_subtotal = subtotal_cents / 100.0
    tax = round(tax_cents / 100.0, 2)
    fees = round(fees_cents / 100.0, 2)
    if cart_has_steward_free:
        steward_display = "0.00"
        steward_contribution_cents = 0
        steward_points_preview = 0
        steward_line_dollars_display = "0.00"
        steward_invalid = False
    else:
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
        "cart_has_steward_free": cart_has_steward_free,
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


def _buyer_dashboard_context(user):
    from General.steward import (
        free_book_cooldown_progress_percent,
        get_steward_pool,
        next_free_book_eligible_at,
        user_free_book_eligible,
    )

    ctx = {
        "stats": {"total_orders": 0, "open_orders": 0},
        "credit_balance": "0.00",
    }
    if not user.is_authenticated:
        return ctx
    ctx["credit_balance"] = f"{(user.store_credit_cents or 0) / 100:.2f}"
    ctx["stats"] = {
        "total_orders": Order.objects.filter(user=user).count(),
        "open_orders": Order.objects.filter(user=user)
        .exclude(status__in=["delivered", "cancelled", "refunded"])
        .count(),
    }
    if user.is_steward:
        pool = get_steward_pool()
        ctx["steward_pool_dollars"] = f"{pool.pool_cents / 100:,.2f}"
        ctx["steward_free_book_eligible"] = user_free_book_eligible(user)
        ctx["steward_free_cooldown_progress"] = free_book_cooldown_progress_percent(user)
        ctx["steward_next_free_at"] = next_free_book_eligible_at(user)
    return ctx

@login_required(login_url="login")
@never_cache

def home(request):
    """Buyer home / dashboard."""
    if request.user.is_authenticated:
        ctx = _buyer_dashboard_context(request.user)
        return render(request, "dashboard/buyer_dashboard.html", ctx)
    return render(request, "dashboard/buyer_dashboard.html")

@login_required(login_url="login")
@never_cache

def buyer_dashboard(request):
    """Buyer dashboard."""
    ctx = _buyer_dashboard_context(request.user)
    return render(request, "dashboard/buyer_dashboard.html", ctx)

@login_required(login_url="login")
@never_cache

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
            if not add_book_to_db_cart(request.user, book, quantity):
                messages.error(
                    request,
                    "This title is already in your cart as a steward free book. Remove it before adding a paid copy.",
                )
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

@login_required(login_url="login")
@never_cache

def buyer_cart(request):
    from General.steward import cart_steward_privilege_row

    if request.user.is_authenticated:
        cart_items, subtotal_cents = db_cart_lines(request.user)
    else:
        session_cart = request.session.get("cart", {})
        cart_items, subtotal_cents = _cart_lines(session_cart)
    cart_subtotal = subtotal_cents / 100.0
    tax = round(cart_subtotal * 0.07, 2)
    cart_has_steward_free = any(item.get("is_steward_free") for item in cart_items)
    fees = 0.00 if cart_has_steward_free else (2.99 if cart_items else 0.00)
    cart_total = round(cart_subtotal + tax + fees, 2)
    total_items = sum(item["quantity"] for item in cart_items)

    pool_cents = 0
    cart_free_book_id = None
    if request.user.is_authenticated and cart_items:
        pool_cents = get_steward_pool().pool_cents
        cart_free_book_id = next(
            (item["id"] for item in cart_items if item.get("is_steward_free")), None
        )
        for item in cart_items:
            item["steward_priv"] = cart_steward_privilege_row(
                request.user, item, cart_free_book_id, pool_cents
            )
    else:
        for item in cart_items:
            item["steward_priv"] = {
                "show": False,
                "is_free_line": bool(item.get("is_steward_free")),
                "select_disabled": True,
                "hint": "",
            }

    context = {
        "cart_items": cart_items,
        "cart_subtotal": cart_subtotal,
        "cart_total": cart_total,
        "tax": tax,
        "fees": fees,
        "total_items": total_items,
        "cart_has_steward_free": cart_has_steward_free,
        "addresses": [],
        "payment_methods": [],
        "checkout_error": None,
    }

    return render(request, "cart/buyer_cart.html", context)


@login_required(login_url="login")
@never_cache

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

        cart_has_free = any(line.get("is_steward_free") for line in cart_items)
        if cart_has_free:
            steward_d = Decimal("0")
            steward_invalid = False
            steward_contribution_cents = 0
        else:
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

        became_steward = False
        try:
            with transaction.atomic():
                buyer_locked = User.objects.select_for_update().get(pk=request.user.pk)
                pool = StewardPool.objects.select_for_update().get(pk=1)

                cis = list(
                    CartItem.objects.filter(cart__user=request.user)
                    .select_related("book", "book__inventory")
                    .select_for_update()
                )
                if not cis:
                    raise ValueError("Your cart is empty.")

                subtotal_cents_locked = 0
                free_deduction = 0
                steward_free_lines = 0
                locked_books = {}
                for ci in cis:
                    book = ci.book
                    if not book.is_active:
                        raise ValueError(
                            f"“{book.title}” is no longer available. Remove it from your cart."
                        )
                    line_cents = ci.unit_price_cents * ci.quantity
                    subtotal_cents_locked += line_cents
                    if ci.is_steward_free:
                        steward_free_lines += 1
                        if ci.quantity != 1:
                            raise ValueError("Steward free books must be quantity 1.")
                        list_px = ci.steward_free_list_price_cents or book.base_price_cents
                        free_deduction += list_px * ci.quantity
                    inv = (
                        Inventory.objects.select_for_update()
                        .select_related("book")
                        .filter(book_id=book.id)
                        .first()
                    )
                    if not inv:
                        raise ValueError(
                            f"No inventory record for “{book.title}”. Ask the seller to restock."
                        )
                    if inv.quantity_available < ci.quantity:
                        raise ValueError(
                            f"Not enough stock for “{book.title}” (available {inv.quantity_available})."
                        )
                    locked_books[book.id] = (inv, ci)

                if steward_free_lines > 1:
                    raise ValueError("Only one steward free book per order.")
                if steward_free_lines and not user_free_book_eligible(buyer_locked):
                    raise ValueError(
                        "You are not eligible for a free book right now. Remove the steward free line from your cart."
                    )

                new_pool = pool.pool_cents + steward_contribution_cents - free_deduction
                if new_pool < 0:
                    raise ValueError(
                        "The steward pool cannot cover this free book right now. Remove the free book or try another title."
                    )
                pool.pool_cents = new_pool
                pool.save(update_fields=["pool_cents"])

                tax_cents = int(round(subtotal_cents_locked * 0.07))
                fees_cents = 0 if steward_free_lines else (299 if cis else 0)
                total_cents = subtotal_cents_locked + tax_cents + fees_cents + steward_contribution_cents

                order = Order.objects.create(
                    user=request.user,
                    shipping_address=ship_addr,
                    payment_method=pay_method,
                    steward_contribution=None,
                    status="paid",
                    subtotal_cents=subtotal_cents_locked,
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

                for book_id, (inv, ci) in locked_books.items():
                    book = ci.book
                    line_total = ci.unit_price_cents * ci.quantity
                    oi = OrderItem.objects.create(
                        order=order,
                        book=book,
                        title=book.title,
                        author=book.author,
                        deposit_required=getattr(book, "deposit_required", False),
                        deposit_amount_cents=getattr(book, "deposit_amount_cents", 0),
                        quantity=ci.quantity,
                        unit_price_cents=ci.unit_price_cents,
                        line_total_cents=line_total,
                        is_steward_free=ci.is_steward_free,
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
                    inv.quantity_available -= ci.quantity
                    inv.save(update_fields=["quantity_available", "updated_at"])

                if steward_free_lines:
                    buyer_locked.last_free_book_redeemed_at = timezone.now()

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
                if steward_free_lines:
                    progress_update_fields.append("last_free_book_redeemed_at")
                buyer_locked.save(update_fields=progress_update_fields)
                became_steward = buyer_locked.steward_verified and not was_steward_verified

                CartItem.objects.filter(cart__user=request.user).delete()

                schedule_order_placed_webhooks(order.id)

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
@never_cache

def cart_steward_free_select(request, book_id):
    if request.method != "POST":
        return redirect("cart")

    def _fail(msg):
        messages.error(request, msg)
        return redirect("cart")

    if not request.user.steward_verified:
        return _fail("Only verified stewards can use this.")
    if not user_free_book_eligible(request.user):
        return _fail("Your next free book unlocks after the 30-day cooldown.")

    with transaction.atomic():
        pool = StewardPool.objects.select_for_update().get(pk=1)
        ci = (
            CartItem.objects.filter(cart__user=request.user, book_id=book_id)
            .select_for_update()
            .select_related("book", "book__inventory")
            .first()
        )
        if not ci:
            return _fail("That book is not in your cart.")
        book = ci.book
        if not book.is_active:
            return _fail("That listing is no longer available.")
        if ci.quantity != 1:
            return _fail("Set quantity to 1 on this line to use your steward free book.")
        if book.stock_quantity < 1:
            return _fail("This book is out of stock.")
        if pool.pool_cents < book.base_price_cents:
            return _fail("The steward pool doesn’t cover this list price right now.")

        for other in CartItem.objects.filter(cart__user=request.user, is_steward_free=True).select_related(
            "book"
        ):
            other.is_steward_free = False
            other.steward_free_list_price_cents = 0
            other.unit_price_cents = other.book.base_price_cents
            other.save(
                update_fields=[
                    "is_steward_free",
                    "steward_free_list_price_cents",
                    "unit_price_cents",
                    "updated_at",
                ]
            )

        ci.is_steward_free = True
        ci.steward_free_list_price_cents = book.base_price_cents
        ci.unit_price_cents = 0
        ci.save(
            update_fields=[
                "is_steward_free",
                "steward_free_list_price_cents",
                "unit_price_cents",
                "updated_at",
            ]
        )

    messages.success(
        request,
        "This line is your steward free book. Checkout fees are waived; only tax applies on what you still pay for.",
    )
    return redirect("cart")


@login_required(login_url="login")
@never_cache

def cart_steward_free_deselect(request, book_id):
    if request.method != "POST":
        return redirect("cart")
    ci = (
        CartItem.objects.filter(
            cart__user=request.user, book_id=book_id, is_steward_free=True
        )
        .select_related("book")
        .first()
    )
    if not ci:
        return redirect("cart")
    ci.is_steward_free = False
    ci.steward_free_list_price_cents = 0
    ci.unit_price_cents = ci.book.base_price_cents
    ci.save(
        update_fields=[
            "is_steward_free",
            "steward_free_list_price_cents",
            "unit_price_cents",
            "updated_at",
        ]
    )
    messages.success(request, "Steward free book cleared. You can choose another line in your cart.")
    return redirect("cart")


@login_required(login_url="login")
@never_cache

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

@login_required(login_url="login")
@never_cache

def remove_cart_item(request, item_id):
    if request.method == "POST":
        if request.user.is_authenticated:
            ci = CartItem.objects.filter(cart__user=request.user, book_id=item_id).first()
            
            if ci:
                if ci.quantity > 1:
                    ci.quantity -= 1
                    ci.save(update_fields=["quantity", "updated_at"])
                else:
                    ci.delete()
        else:
            cart = request.session.get("cart", {})
            item_id_str = str(item_id)

            if item_id_str in cart:
                item = cart[item_id_str]

                if isinstance(item, dict):
                    qty = item.get("quantity", 1)
                    if qty > 1:
                        cart[item_id_str]["quantity"] = qty - 1
                    else:
                        del cart[item_id_str]
                else:
                    if item > 1:
                        cart[item_id_str] = item - 1
                    else:
                        del cart[item_id_str]

            request.session["cart"] = cart
            request.session.modified = True
    return redirect("cart")

@login_required(login_url="login")
@never_cache

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
                if ci.is_steward_free:
                    ci.quantity = 1

                else:
                    ci.quantity = quantity
                    ci.unit_price_cents = ci.book.base_price_cents

                ci.save(update_fields=["quantity", "unit_price_cents", "updated_at"])
        else:
            cart = request.session.get("cart", {})
            item_id_str = str(item_id)

            if item_id_str in cart:
                if isinstance(cart[item_id_str], dict):
                    cart[item_id_str]["quantity"] = quantity
                else:
                    cart[item_id_str] = quantity
                    
            request.session["cart"] = cart
            request.session.modified = True
    return redirect("cart")


@login_required(login_url="login")
@never_cache
def buyer_payments(request):
    """List saved PaymentMethod rows."""
    return render(
        request,
        "checkout/buyer_payments.html",
        {"payment_methods": list(_payment_methods_for_user(request.user))},
    )


@login_required(login_url="login")
@never_cache
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
@never_cache

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
@never_cache

def delete_payment_method(request, payment_method_id):
    if request.method != "POST":
        return redirect("buyer_payments")
    pm = get_object_or_404(PaymentMethod, pk=payment_method_id, user=request.user)
    pm.delete()
    messages.success(request, "Payment method removed.")
    return redirect("buyer_payments")


@login_required(login_url="login")
@never_cache

def buyer_shipping(request):
    """List saved shipping Address rows for the logged-in user."""
    return render(
        request,
        "checkout/buyer_shipping.html",
        {"addresses": _addresses_for_user(request.user)},
    )


@login_required(login_url="login")
@never_cache

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
@never_cache

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
@never_cache

def delete_shipping_address(request, address_id):
    if request.method != "POST":
        return redirect("buyer_shipping")
    addr = get_object_or_404(Address, pk=address_id, user=request.user)
    addr.delete()
    messages.success(request, "Address removed.")
    return redirect("buyer_shipping")


@login_required(login_url="login")
@never_cache

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
@never_cache

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
    had_steward_free_book = order.orderitem.filter(is_steward_free=True).exists()
    free_book_attribution = (
        random_steward_attribution(exclude_user_id=request.user.pk)
        if had_steward_free_book
        else None
    )
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
            "free_book_attribution": free_book_attribution,
        },
    )


@login_required(login_url="login")
@never_cache

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
    can_leave_review = order.status == "delivered"

    user_orders = list(
        Order.objects.filter(user=request.user).order_by("-created_at", "-id")
    )
    position = None
    for index, user_order in enumerate(user_orders, start=1):
        if user_order.id == order.id:
            position = index
            break
    display_order_number = len(user_orders) - position + 1 if position is not None else None
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
            "can_leave_review": can_leave_review,
            "return_request": return_request,
            "return_status_label": _buyer_return_status_label(return_request),
            "display_order_number": display_order_number,
        },
    )


@login_required(login_url="login")
@never_cache

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
@never_cache

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

@login_required(login_url="login")
@never_cache

def review_submission(request):
    """Submit a review (no Review model in project schema yet)."""
    return render(request, "reviews/reviewSubmission.html")
