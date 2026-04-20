import hashlib
import hmac
import json
import logging

import requests
from django.db import transaction
from django.db.models import Prefetch

from Buyer.models import Order, OrderItem

from .models import SellerProfile

logger = logging.getLogger(__name__)


def serialize_webhook_body(payload: dict) -> bytes:
    """Stable JSON bytes for the request body and HMAC input."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def post_seller_webhook(url: str, secret: str, payload: dict) -> tuple[bool, str | None]:
    """
    POST application/json to url. If secret is non-empty, set X-Webhook-Signature
    to hex HMAC-SHA256 of the exact body bytes.
    """
    body = serialize_webhook_body(payload)
    headers = {"Content-Type": "application/json"}
    sec = (secret or "").strip()
    if sec:
        digest = hmac.new(sec.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = digest
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return False, str(exc)
    return True, None


def _ship_block_from_order(order: Order) -> dict:
    snap = getattr(order, "shipping_snapshot", None)
    if not snap:
        return {
            "name": "",
            "line1": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "country": "",
        }
    line1 = snap.shipping_line1 or ""
    if snap.shipping_line2:
        line1 = f"{line1}, {snap.shipping_line2}".strip(", ")
    return {
        "name": (snap.shipping_name or "").strip(),
        "line1": line1,
        "city": snap.shipping_city or "",
        "state": snap.shipping_state or "",
        "postal_code": snap.shipping_postal_code or "",
        "country": snap.shipping_country or "",
    }


def _display_title_for_item(oi: OrderItem) -> str:
    snap = getattr(oi, "book_snapshot", None)
    title = (snap.title if snap else oi.title) or "Unknown"
    if oi.quantity and oi.quantity > 1:
        return f"{title} (×{oi.quantity})"
    return title


def build_order_placed_payload(order: Order, seller_user_id: int) -> dict:
    titles = []
    for oi in order.orderitem.all():
        su = getattr(oi.book, "seller_user_id", None)
        if su == seller_user_id:
            titles.append(_display_title_for_item(oi))
    product_name = ", ".join(titles) if titles else "Order item"
    placed_at = order.created_at
    if placed_at is not None and hasattr(placed_at, "isoformat"):
        ts = placed_at.isoformat()
    else:
        ts = ""
    return {
        "event": "order.placed",
        "product_name": product_name,
        "order_placed_at": ts,
        "ship_to_address": _ship_block_from_order(order),
    }


def build_test_webhook_payload() -> dict:
    from django.utils import timezone

    return {
        "event": "webhook.test",
        "product_name": "Pass It On — webhook test (no order)",
        "order_placed_at": timezone.now().isoformat(),
        "ship_to_address": {
            "name": "Test Recipient",
            "line1": "123 Example Street",
            "city": "Sample City",
            "state": "CA",
            "postal_code": "90001",
            "country": "US",
        },
    }


def send_order_placed_webhooks_for_order(order_id: int) -> None:
    """
    Notify each seller who has items on this order, if their webhook is configured.
    Failures are logged only; callers should not treat this as fatal.
    """
    try:
        order = (
            Order.objects.filter(pk=order_id)
            .select_related("shipping_snapshot")
            .prefetch_related(
                Prefetch(
                    "orderitem",
                    queryset=OrderItem.objects.select_related("book", "book_snapshot"),
                )
            )
            .get()
        )
    except Order.DoesNotExist:
        logger.warning("Webhook: order %s not found", order_id)
        return
    except Exception:
        logger.exception("Webhook: could not load order %s", order_id)
        return

    seller_ids: set[int] = set()
    for oi in order.orderitem.all():
        su = getattr(oi.book, "seller_user_id", None)
        if su:
            seller_ids.add(int(su))

    if not seller_ids:
        return

    profiles = SellerProfile.objects.select_related("user").filter(user_id__in=seller_ids)
    by_user_id = {p.user_id: p for p in profiles}

    for uid in seller_ids:
        profile = by_user_id.get(uid)
        if not profile or not profile.webhook_enabled:
            continue
        url = (profile.webhook_url or "").strip()
        if not url:
            continue
        payload = build_order_placed_payload(order, uid)
        ok, err = post_seller_webhook(url, profile.webhook_secret, payload)
        if not ok:
            logger.warning(
                "Webhook order.placed failed for seller user_id=%s order_id=%s: %s",
                uid,
                order_id,
                err,
            )


def schedule_order_placed_webhooks(order_id: int) -> None:
    """Run after DB commit so the order exists for concurrent readers."""
    transaction.on_commit(lambda: send_order_placed_webhooks_for_order(order_id))
