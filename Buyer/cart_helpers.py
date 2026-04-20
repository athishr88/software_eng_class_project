"""Persisted cart (Cart / CartItem) helpers for logged-in users."""

from django.db import transaction

from Buyer.models import Cart, CartItem
from General.models import Book


def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user, defaults={"status": "active"})
    return cart


def merge_session_cart_into_db(user, session):
    """Move session cart lines into the user's Cart, then clear the session cart."""
    raw = session.get("cart") or {}
    if not raw:
        return
    cart = get_or_create_cart(user)
    with transaction.atomic():
        for bid, data in raw.items():
            try:
                book = Book.objects.get(pk=int(bid), is_active=True)
            except (Book.DoesNotExist, ValueError, TypeError):
                continue
            try:
                qty = max(1, int(data.get("quantity", 1)))
            except (TypeError, ValueError):
                qty = 1
            ci, created = CartItem.objects.get_or_create(
                cart=cart,
                book=book,
                defaults={
                    "quantity": qty,
                    "unit_price_cents": book.base_price_cents,
                    "is_steward_free": False,
                    "steward_free_list_price_cents": 0,
                },
            )
            if not created:
                if ci.is_steward_free:
                    continue
                ci.quantity += qty
                ci.unit_price_cents = book.base_price_cents
                ci.save(update_fields=["quantity", "unit_price_cents", "updated_at"])
    session["cart"] = {}
    session.modified = True


def db_cart_lines(user):
    """
    Build cart lines from CartItem rows.
    Same shape as session _cart_lines: id (book id), book, quantity, price, subtotal, line_subtotal_cents.
    """
    lines = []
    subtotal_cents = 0
    cart = Cart.objects.filter(user=user).first()
    if not cart:
        return lines, subtotal_cents

    stale_ids = []
    for ci in cart.cartitem_set.select_related("book", "book__inventory").all():
        book = ci.book
        if not book.is_active:
            stale_ids.append(ci.pk)
            continue
        qty = ci.quantity
        line_cents = ci.unit_price_cents * qty
        subtotal_cents += line_cents
        price = ci.unit_price_cents / 100.0
        lines.append(
            {
                "id": book.id,
                "book": book,
                "quantity": qty,
                "price": price,
                "subtotal": line_cents / 100.0,
                "line_subtotal_cents": line_cents,
                "is_steward_free": ci.is_steward_free,
                "steward_free_list_price_cents": ci.steward_free_list_price_cents,
            }
        )

    if stale_ids:
        CartItem.objects.filter(pk__in=stale_ids).delete()

    return lines, subtotal_cents


def clear_db_cart(user):
    CartItem.objects.filter(cart__user=user).delete()


def add_book_to_db_cart(user, book, quantity):
    """
    Add quantity to user's cart; refreshes unit_price_cents from the book.
    Returns False if this title is already in the cart as a steward free line (paid add blocked).
    """
    if quantity < 1:
        quantity = 1
    cart = get_or_create_cart(user)
    ci, created = CartItem.objects.get_or_create(
        cart=cart,
        book=book,
        defaults={
            "quantity": quantity,
            "unit_price_cents": book.base_price_cents,
            "is_steward_free": False,
            "steward_free_list_price_cents": 0,
        },
    )
    if not created and ci.is_steward_free:
        return False
    if not created:
        ci.quantity += quantity
        ci.unit_price_cents = book.base_price_cents
        ci.save(update_fields=["quantity", "unit_price_cents", "updated_at"])
    return True
