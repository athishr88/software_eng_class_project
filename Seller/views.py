from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404, redirect, render

from Buyer.models import Order, OrderItem, ReturnRequest, SellerReturnReceipt
from General.models import Book, Inventory, User

# Line revenue counted toward “total sales” for sellers.
_SALE_RECOGNIZED_STATUSES = ("paid", "shipped", "delivered")


def _require_seller(user):
    return user.is_authenticated and getattr(user, "role", None) == "seller"


def _sanitize_book_title_for_filename(title: str) -> str:
    """Make a safe filename stem from a book title (Windows-friendly)."""
    if not title:
        return "book"
    # Windows-invalid chars: < > : " / \ | ? * and ASCII control chars
    invalid_chars = set('<>:"/\\|?*')
    cleaned_chars = []
    for ch in title:
        if ch in invalid_chars or ord(ch) < 32:
            cleaned_chars.append("_")
        else:
            cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars).strip().strip(".")
    return cleaned or "book"


def _get_book_images_dir() -> Path:
    """Return the on-disk directory used for storing covers."""
    d = Path(settings.BASE_DIR) / "book_images"
    if not d.exists():
        d = Path(settings.BASE_DIR).parent / "book_images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _order_distinct_seller_user_ids(order):
    return set(
        OrderItem.objects.filter(order=order, book__seller_user__isnull=False)
        .values_list("book__seller_user_id", flat=True)
        .distinct()
    )


def _seller_line_total_cents_for_order(order, seller_user) -> int:
    total = (
        OrderItem.objects.filter(order=order, book__seller_user=seller_user).aggregate(
            s=Sum("line_total_cents")
        ).get("s")
    )
    return int(total or 0)


def _maybe_finalize_buyer_return(return_request):
    """Set return to refunded (buyer: Return complete) when every seller in the order has acknowledged."""
    if return_request.status == "rejected":
        return
    order = return_request.order
    needed = _order_distinct_seller_user_ids(order)
    if not needed:
        return
    acknowledged = set(return_request.seller_receipts.values_list("seller_id", flat=True))
    if needed <= acknowledged and return_request.status != "refunded":
        return_request.status = "refunded"
        return_request.save(update_fields=["status", "updated_at"])


def _pending_return_requests_qs(seller_user):
    return (
        ReturnRequest.objects.filter(
            order__orderitem__book__seller_user=seller_user,
        )
        .exclude(status="rejected")
        .exclude(seller_receipts__seller=seller_user)
        .select_related("order", "order__user")
        .prefetch_related("order__orderitem__book")
        .distinct()
        .order_by("-created_at")
    )


def _seller_dashboard_stats(seller_user):
    seller_books = Book.objects.filter(seller_user=seller_user)

    published_books = seller_books.filter(is_active=True).count()
    unpublished_books = seller_books.filter(is_active=False).count()

    # Only count inventory for active listings.
    seller_inventory = Inventory.objects.filter(book__seller_user=seller_user, book__is_active=True)
    low_stock_count = seller_inventory.filter(quantity_available__lte=3, quantity_available__gt=0).count()
    out_of_stock_count = seller_inventory.filter(quantity_available=0).count()

    pending_returns = _pending_return_requests_qs(seller_user).count()

    return {
        "published_books": published_books,
        "unpublished_books": unpublished_books,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "open_order": 0,
        "shipped_orders": 0,
        "pending_returns_count": pending_returns,
    }


@login_required(login_url="login")
def home(request):
    """Seller home / dashboard."""
    if not _require_seller(request.user):
        messages.error(request, "A seller account is required.")
        return redirect("buyer_home")

    stats = _seller_dashboard_stats(request.user)
    recent_orders = (
        Order.objects.filter(orderitem__book__seller_user=request.user)
        .annotate(
            seller_revenue_cents=Sum(
                "orderitem__line_total_cents",
                filter=Q(orderitem__book__seller_user=request.user),
            )
        )
        .select_related("user")
        .order_by("-created_at")[:25]
    )
    return render(
        request,
        "dashboard/dashboard.html",
        {
            "stats": stats,
            "recent_orders": recent_orders,
            "return_requests_preview": _pending_return_requests_qs(request.user)[:8],
            "total_sales": _format_cents_as_dollars(_seller_sales_total_cents(request.user))
        },
    )


@login_required(login_url="login")
def dashboard(request):
    """Seller dashboard."""
    if not _require_seller(request.user):
        messages.error(request, "A seller account is required.")
        return redirect("buyer_home")

    stats = _seller_dashboard_stats(request.user)

    recent_orders = (
        Order.objects.filter(orderitem__book__seller_user=request.user)
        .annotate(
            seller_revenue_cents=Sum(
                "orderitem__line_total_cents",
                filter=Q(orderitem__book__seller_user=request.user),
            )
        )
        .select_related("user")
        .order_by("-created_at")[:25]
    )
    
    return render(
        request,
        "dashboard/dashboard.html",
        {
            "stats": stats,
            "recent_orders": recent_orders,
            "return_requests_preview": _pending_return_requests_qs(request.user)[:8],
            "total_sales": _format_cents_as_dollars(_seller_sales_total_cents(request.user))
        },
    )


@login_required(login_url="login")
def add_books(request):
    """Create a Book + Inventory for the logged-in seller."""
    if not _require_seller(request.user):
        messages.error(request, "A seller account is required to add books.")
        return redirect("buyer_home")

    ctx = {"form_values": {}}

    if request.method == "POST":
        post = request.POST

        def strip(name, default=""):
            return (post.get(name) or default).strip()

        title = strip("title")
        author = strip("author")
        description = strip("description") or None
        isbn = strip("isbn") or None
        language = strip("language") or None
        publisher = strip("publisher") or None
        cover_image_url = strip("cover_image_url") or None
        condition = strip("condition")
        publication_year = None
        py = strip("publication_year")
        if py:
            try:
                publication_year = int(py)
            except ValueError:
                pass

        is_active = post.get("is_published") != "0"
        reorder_threshold = 0
        try:
            reorder_threshold = max(0, int(post.get("reorder_threshold") or 0))
        except (TypeError, ValueError):
            reorder_threshold = 0

        cover_image = request.FILES.get("cover_image")

        errs = []
        if not title:
            errs.append("Title is required.")
        if not author:
            errs.append("Author is required.")
        if not condition:
            errs.append("Condition is required.")

        try:
            price = Decimal(str(post.get("price") or "0"))
            base_price_cents = int((price * 100).quantize(0, ROUND_HALF_UP))
            if base_price_cents <= 0:
                errs.append("Enter a price greater than zero.")
        except (InvalidOperation, TypeError):
            errs.append("Enter a valid price.")

        try:
            qty = int(post.get("quantity_available") or post.get("stock_quantity") or 0)
            if qty < 0:
                errs.append("Stock cannot be negative.")
        except (TypeError, ValueError):
            errs.append("Enter a valid stock quantity.")

        # If a file is uploaded, prefer it over the URL field.
        if cover_image:
            allowed_ext = {".jpg", ".jpeg", ".png", ".gif"}
            max_size_bytes = 5 * 1024 * 1024  # 5MB
            if cover_image.size > max_size_bytes:
                errs.append("Cover image file is too large (max 5MB).")

            # Determine extension from filename/content-type.
            ext = Path(cover_image.name).suffix.lower()
            content_type = (cover_image.content_type or "").lower()
            if ext not in allowed_ext:
                if content_type.endswith("png"):
                    ext = ".png"
                elif content_type.endswith("jpeg") or content_type.endswith("jpg"):
                    ext = ".jpg"
                elif content_type.endswith("gif"):
                    ext = ".gif"
                else:
                    ext = ""

            if ext and ext not in allowed_ext:
                errs.append("Cover image must be a jpg, jpeg, png, or gif.")
            elif not ext:
                errs.append("Could not determine a valid cover image file type.")

        ctx["form_values"] = {k: post.get(k, "") for k in post}

        if errs:
            ctx["form_error"] = " ".join(errs)
            return render(request, "inventory/addBooks.html", ctx)

        with transaction.atomic():
            if cover_image:
                images_dir = _get_book_images_dir()
                safe_stem = _sanitize_book_title_for_filename(title)
                cover_filename = f"{safe_stem}{ext}"
                file_path = images_dir / cover_filename

                # Save raw bytes; covers are served as-is by `serve_book_cover`.
                with open(file_path, "wb") as f:
                    for chunk in cover_image.chunks():
                        f.write(chunk)

                # Ensure templates use `cover_serve_url` (filesystem-based) instead of the URL field.
                cover_image_url = None

            book = Book.objects.create(
                seller_user=request.user,
                title=title,
                author=author,
                description=description,
                isbn=isbn,
                language=language,
                publisher=publisher,
                publication_year=publication_year,
                cover_image_url=cover_image_url,
                condition=condition,
                base_price_cents=base_price_cents,
                is_active=is_active,
            )
            Inventory.objects.create(
                book=book,
                quantity_available=qty,
                quantity_reserved=0,
                reorder_threshold=reorder_threshold,
            )

        messages.success(request, "Book listing saved.")
        return redirect("manage_inventory")

    return render(request, "inventory/addBooks.html", ctx)


@login_required(login_url="login")
def manage_inventory(request):
    """List seller books and update price, stock, and active flag."""
    if not _require_seller(request.user):
        messages.error(request, "A seller account is required.")
        return redirect("buyer_home")

    if request.method == "POST":
        book_id = request.POST.get("book_id")
        book = get_object_or_404(Book, pk=book_id, seller_user=request.user)
        inv, _ = Inventory.objects.get_or_create(
            book=book,
            defaults={
                "quantity_available": 0,
                "quantity_reserved": 0,
                "reorder_threshold": 0,
            },
        )
        try:
            price = Decimal(str(request.POST.get("price") or "0"))
            book.base_price_cents = int((price * 100).quantize(0, ROUND_HALF_UP))
            if book.base_price_cents <= 0:
                raise ValueError("price")
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Invalid price.")
            return redirect("manage_inventory")

        try:
            inv.quantity_available = max(0, int(request.POST.get("stock_quantity") or 0))
        except (TypeError, ValueError):
            messages.error(request, "Invalid stock quantity.")
            return redirect("manage_inventory")

        book.is_active = request.POST.get("is_active") == "on"
        book.save()
        inv.save()
        messages.success(request, "Listing updated.")
        return redirect("manage_inventory")

    qs = (
        Book.objects.filter(seller_user=request.user)
        .select_related("inventory")
        .order_by("title")
    )

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author__icontains=q))

    status = (request.GET.get("status") or "").strip()
    if status == "PUBLISHED":
        qs = qs.filter(is_active=True)
    elif status == "UNPUBLISHED":
        qs = qs.filter(is_active=False)
    elif status == "OUT_OF_STOCK":
        qs = qs.filter(inventory__quantity_available=0)
    elif status == "LOW_STOCK":
        qs = qs.filter(inventory__quantity_available__lte=3, inventory__quantity_available__gt=0)

    sort = (request.GET.get("sort") or "title").strip()
    if sort == "newest":
        qs = qs.order_by("-created_at")
    elif sort == "oldest":
        qs = qs.order_by("created_at")
    elif sort == "stock_asc":
        qs = qs.order_by("inventory__quantity_available")
    elif sort == "stock_desc":
        qs = qs.order_by("-inventory__quantity_available")
    elif sort == "price_asc":
        qs = qs.order_by("base_price_cents")
    elif sort == "price_desc":
        qs = qs.order_by("-base_price_cents")
    else:
        qs = qs.order_by("title")

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(request, "inventory/manageInventory.html", {"page_obj": page_obj})


def _seller_sales_total_cents(seller_user) -> int:
    seller_returned_order = SellerReturnReceipt.objects.filter(
        seller=seller_user,
        return_request__order_id=OuterRef("order_id"),
    )
    total = (
        OrderItem.objects.filter(
            book__seller_user=seller_user,
            order__status__in=_SALE_RECOGNIZED_STATUSES,
        )
        .exclude(Exists(seller_returned_order))
        .aggregate(s=Sum("line_total_cents"))
        .get("s")
    )
    return int(total or 0)


def _format_cents_as_dollars(cents: int) -> str:
    return f"{cents / 100:.2f}"


@login_required(login_url="login")
def sales_overview(request):
    """Total sales and recent orders that include this seller's books."""
    if not _require_seller(request.user):
        messages.error(request, "A seller account is required.")
        return redirect("buyer_home")

    total_cents = _seller_sales_total_cents(request.user)

    excluded_item_ids = (
        OrderItem.objects.filter(book__seller_user=request.user)
        .annotate(
            _returned=Exists(
                SellerReturnReceipt.objects.filter(
                    seller=request.user,
                    return_request__order_id=OuterRef("order_id"),
                )
            )
        )
        .filter(_returned=True)
        .values("id")
    )

    recent_sales_orders = (
        Order.objects.filter(orderitem__book__seller_user=request.user)
        .annotate(
            seller_revenue_cents=Sum(
                "orderitem__line_total_cents",
                filter=Q(orderitem__book__seller_user=request.user)
                & ~Q(orderitem__id__in=Subquery(excluded_item_ids)),
            )
        )
        .select_related("user")
        .order_by("-created_at")[:25]
    )

    for o in recent_sales_orders:
        rev = o.seller_revenue_cents or 0
        o.seller_revenue_display = _format_cents_as_dollars(int(rev))
        o.order_total_display = _format_cents_as_dollars(int(o.total_cents))

    return render(
        request,
        "dashboard/sales_overview.html",
        {
            "total_sales_display": _format_cents_as_dollars(total_cents),
            "recent_sales_orders": recent_sales_orders,
        },
    )


def orders(request):
    """Orders list."""

    q = (request.GET.get("q") or "").strip()
    qs = (
        Order.objects.filter(orderitem__book__seller_user=request.user)
        .annotate(
            seller_revenue_cents=Sum(
                "orderitem__line_total_cents",
                filter=Q(orderitem__book__seller_user=request.user),
            )
        )
        .order_by("-created_at")
        .select_related("user")
    )

    if q:
        qs = qs.filter(Q(user__email__icontains=q) | Q(orderitem__book__title__icontains=q)).distinct()
    
    sort = (request.GET.get("sort") or "newest").strip()

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    for order in page_obj:
        order.seller_revenue = _format_cents_as_dollars(int(order.seller_revenue_cents or 0))
    return render(request, "orders/orders.html", {
        "page_obj": page_obj,
    })


def order_details(request, order_id=None):
    """Single order detail."""
    
    order = Order.objects.filter(id=order_id).select_related("user").prefetch_related("orderitem__book").first()
    if not order:
        messages.error(request, "Order not found.")
        return redirect("orders")
    return render(request, "orders/orderDetails.html", {
        "order": order
    })


@login_required(login_url="login")
def return_requests_list(request):
    if not _require_seller(request.user):
        messages.error(request, "A seller account is required.")
        return redirect("buyer_home")

    pending = _pending_return_requests_qs(request.user)
    return render(
        request,
        "returns/return_requests_list.html",
        {"return_requests": pending},
    )


@login_required(login_url="login")
def return_request_detail(request, return_id):
    if not _require_seller(request.user):
        messages.error(request, "A seller account is required.")
        return redirect("buyer_home")

    rr = get_object_or_404(
        ReturnRequest.objects.select_related("order", "order__user").prefetch_related(
            "order__orderitem__book", "seller_receipts"
        ),
        pk=return_id,
    )
    order = rr.order
    seller_total = _seller_line_total_cents_for_order(order, request.user)
    if seller_total <= 0:
        messages.error(request, "This return does not include any of your listings.")
        return redirect("seller_return_requests")

    already = rr.seller_receipts.filter(seller=request.user).first()

    if request.method == "POST" and request.POST.get("action") == "book_received":
        if rr.status == "rejected":
            messages.error(request, "This return was rejected.")
            return redirect("seller_return_request_detail", return_id=rr.id)
        if already:
            messages.info(request, "You already marked this return as received.")
            return redirect("seller_return_request_detail", return_id=rr.id)

        with transaction.atomic():
            rr_locked = ReturnRequest.objects.select_for_update().get(pk=rr.id)
            if SellerReturnReceipt.objects.filter(return_request=rr_locked, seller=request.user).exists():
                messages.info(request, "You already marked this return as received.")
                return redirect("seller_return_request_detail", return_id=rr.id)

            amount = _seller_line_total_cents_for_order(rr_locked.order, request.user)
            if amount <= 0:
                messages.error(request, "No matching lines to credit for your account.")
                return redirect("seller_return_requests")

            buyer = User.objects.select_for_update().get(pk=rr_locked.order.user_id)
            SellerReturnReceipt.objects.create(
                return_request=rr_locked,
                seller=request.user,
                amount_credited_cents=amount,
            )
            buyer.store_credit_cents = (buyer.store_credit_cents or 0) + amount
            buyer.save(update_fields=["store_credit_cents", "updated_at"])

            for oi in OrderItem.objects.filter(order=rr_locked.order, book__seller_user=request.user).select_related(
                "book"
            ):
                inv, _ = Inventory.objects.get_or_create(
                    book=oi.book,
                    defaults={
                        "quantity_available": 0,
                        "quantity_reserved": 0,
                        "reorder_threshold": 0,
                    },
                )
                inv.quantity_available = (inv.quantity_available or 0) + oi.quantity
                inv.save(update_fields=["quantity_available", "updated_at"])

            _maybe_finalize_buyer_return(rr_locked)

        messages.success(
            request,
            "Book received. The buyer was credited and your sales total was adjusted for these lines.",
        )
        return redirect("seller_return_request_detail", return_id=rr.id)

    return render(
        request,
        "returns/return_request_detail.html",
        {
            "return_request": rr,
            "order": order,
            "seller_lines_total_display": _format_cents_as_dollars(seller_total),
            "already_received": already,
            "amount_credited_display": _format_cents_as_dollars(already.amount_credited_cents) if already else None,
        },
    )
