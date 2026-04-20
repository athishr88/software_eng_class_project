"""Steward free-book pool, eligibility, and cart-only privilege helpers."""

import random
from datetime import timedelta
from typing import Optional, TypedDict

from django.utils import timezone

FREE_BOOK_COOLDOWN = timedelta(days=30)
INITIAL_POOL_CENTS = 100_000_000  # $1,000,000.00


def get_steward_pool():
    from General.models import StewardPool

    obj, _ = StewardPool.objects.get_or_create(
        pk=1, defaults={"pool_cents": INITIAL_POOL_CENTS}
    )
    return obj


def user_free_book_eligible(user) -> bool:
    if not user.is_authenticated or not user.steward_verified:
        return False
    t = user.last_free_book_redeemed_at
    if t is None:
        return True
    return timezone.now() >= t + FREE_BOOK_COOLDOWN


def free_book_cooldown_progress_percent(user) -> int:
    """
    0–100: progress through the 30-day wait after the last free book (100 = eligible now).
    """
    if not user.is_authenticated or not user.steward_verified:
        return 0
    if user.last_free_book_redeemed_at is None:
        return 100
    start = user.last_free_book_redeemed_at
    end = start + FREE_BOOK_COOLDOWN
    now = timezone.now()
    if now >= end:
        return 100
    total = FREE_BOOK_COOLDOWN.total_seconds()
    elapsed = (now - start).total_seconds()
    return min(100, max(0, int(100 * elapsed / total)))


def next_free_book_eligible_at(user):
    """Datetime when cooldown ends, or None if already eligible / not a steward."""
    if not user.is_authenticated or not user.steward_verified:
        return None
    if user.last_free_book_redeemed_at is None:
        return None
    end = user.last_free_book_redeemed_at + FREE_BOOK_COOLDOWN
    if timezone.now() >= end:
        return None
    return end


class StewardAttribution(TypedDict):
    first_name: str
    city: Optional[str]


def random_steward_attribution(*, exclude_user_id: Optional[int] = None) -> Optional[StewardAttribution]:
    """
    Random verified steward for order-confirmation thank-you copy (steward free book).
    Prefers a steward other than exclude_user_id when any exist.
    """
    from General.models import User

    base = User.objects.filter(steward_verified=True, is_active=True)
    qs = base.exclude(pk=exclude_user_id) if exclude_user_id else base
    if exclude_user_id and not qs.exists():
        qs = base
    ids = list(qs.values_list("pk", flat=True)[:500])
    if not ids:
        return None
    uid = random.choice(ids)
    row = User.objects.filter(pk=uid).values("first_name", "steward_city").first()
    if not row:
        return None
    fn = (row.get("first_name") or "").strip()
    if not fn:
        return None
    city_raw = (row.get("steward_city") or "").strip()
    return StewardAttribution(first_name=fn, city=city_raw or None)


def cart_steward_privilege_row(
    user, line: dict, cart_free_book_id: Optional[int], pool_cents: int
) -> dict:
    """
    Cart-only UI for steward free book: line is a db_cart_lines dict (id = book id).
    """
    out = {
        "show": False,
        "is_free_line": bool(line.get("is_steward_free")),
        "select_disabled": True,
        "hint": "",
    }
    if not user.is_authenticated or not user.steward_verified:
        return out
    out["show"] = True
    if out["is_free_line"]:
        return out

    book = line["book"]
    bid = line["id"]
    if cart_free_book_id is not None and cart_free_book_id != bid:
        out["hint"] = "Another line is already your steward free book. Deselect it to choose this one."
        return out
    if not user_free_book_eligible(user):
        out["hint"] = "Next free book unlocks after your 30-day cooldown."
        return out
    if pool_cents < book.base_price_cents:
        out["hint"] = "Steward pool balance doesn’t cover this list price."
        return out
    if book.stock_quantity < line["quantity"]:
        out["hint"] = "Not enough stock for this quantity."
        return out
    if line["quantity"] != 1:
        out["hint"] = "Set quantity to 1 on this line to use your steward free book."
        return out
    out["select_disabled"] = False
    out["hint"] = "Use your steward free book on this line. Checkout fees are $0 for that order; only tax applies on paid lines."
    return out
