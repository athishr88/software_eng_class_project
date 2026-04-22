from datetime import timedelta
from functools import wraps
from pyexpat.errors import messages

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from urllib.parse import quote
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.contrib.auth.hashers import make_password
from django.contrib.auth import update_session_auth_hash

from Admin.models import FlagReport
from Buyer.models import Order, ReturnRequest
from General.models import Book, Notification, User


def staff_required(view_func):
    """Require an authenticated user with role=admin and is_staff. Redirect to staff login otherwise."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse("staff_login") + "?next=" + quote(request.get_full_path()))
        if getattr(request.user, "role", None) != "admin" or not getattr(request.user, "is_staff", False):
            logout(request)
            return redirect("staff_login")
        return view_func(request, *args, **kwargs)
    return _wrapped

@never_cache
def staff_login(request):
    """Staff-only login at /staff/login. Only users with role=admin and is_staff can log in."""
    return redirect("login")

def staff_logout(request):
    """Log out and redirect to staff login."""
    logout(request)
    return redirect("staff_login")

def _format_status(s):
    """Map FlagReport status to display label."""
    return {"open": "Open", "reviewing": "Triage", "resolved": "Resolved", "dismissed": "Dismissed"}.get(
        (s or "").lower(), s or "Open"
    )

def _flag_to_steward_row(flag):
    target = flag.target_user
    return {
        "username": target.email if target else "—",
        "user_id": target.id if target else "—",
        "reason": flag.details or "—",
        "severity": getattr(flag, "severity", None) or "Medium",
        "status": _format_status(flag.status),
        "flagged_date": flag.created_at.strftime("%b %d, %Y"),
    }

def _flag_to_payment_row(flag):
    target = flag.target_user
    return {
        "username": target.email if target else "—",
        "user_id": target.id if target else "—",
        "signal": flag.details or "—",
        "severity": getattr(flag, "severity", None) or "Medium",
        "status": _format_status(flag.status),
        "flagged_date": flag.created_at.strftime("%b %d, %Y"),
    }

def _flag_to_all_row(flag):
    if flag.target_user:
        target = flag.target_user.email
    elif flag.target_book:
        target = f"Book ID {flag.target_book.id}"
    else:
        target = "—"
    return {
        "flag_id": f"F{flag.id}",
        "type": flag.flag_type or "—",
        "target": target,
        "reason": flag.details or "—",
        "severity": getattr(flag, "severity", None) or "Medium",
        "status": _format_status(flag.status),
        "date": flag.created_at.strftime("%b %d, %Y"),
    }


@staff_required
def admin_dashboard(request):
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = User.objects.count()
    active_users_30d = User.objects.filter(last_login__gte=thirty_days_ago).count()
    users_this_week = User.objects.filter(created_at__gte=week_ago).count()
    active_pct = (active_users_30d / total_users * 100) if total_users else 0

    books_listed = Book.objects.filter(is_active=True).count()
    books_available = Book.objects.filter(
        inventory__quantity_available__gt=0
    ).count()
    books_today = Book.objects.filter(is_active=True, created_at__gte=today_start).count()

    orders_month = Order.objects.filter(created_at__gte=start_of_month).count()
    orders_today = Order.objects.filter(created_at__gte=today_start).count()

    returns_month = ReturnRequest.objects.filter(created_at__gte=start_of_month).count()
    return_rate = (returns_month / orders_month * 100) if orders_month else 0

    open_flags_count = FlagReport.objects.filter(status__in=("open", "reviewing")).count()

    
    revenue_result = (
        Order.objects.filter(
            created_at__gte=start_of_month,
            status__in=("paid", "shipped", "delivered"),
        ).aggregate(Sum("total_cents"))
    )
    revenue_cents = revenue_result["total_cents__sum"] or 0
    revenue_month = f"${revenue_cents / 100:,.0f}"

    steward_flags_qs = (
        FlagReport.objects.filter(flag_type__icontains="steward")
        .select_related("target_user")
        .order_by("-created_at")[:5]
    )
    steward_flags = [_flag_to_steward_row(f) for f in steward_flags_qs]

    payment_flags_qs = (
        FlagReport.objects.filter(flag_type__icontains="payment")
        .select_related("target_user")
        .order_by("-created_at")[:5]
    )
    payment_flags = [_flag_to_payment_row(f) for f in payment_flags_qs]

    recent_books = (
        Book.objects.filter(is_active=True)
        .select_related("seller_user")
        .order_by("-created_at")[:5]
    )
    recent_listings = [
        {
            "title": b.title,
            "book_id": f"B {b.id}",
            "seller": b.seller_user.email if b.seller_user else "—",
            "condition": b.condition or "—",
            "status": "Live" if b.is_active else "Hidden",
            "created_date": b.created_at.strftime("%b %d, %Y"),
        }
        for b in recent_books
    ]
    pending_seller_approvals = User.objects.filter(role="seller", seller_approved=False).count()
    pending_buyer_approvals = User.objects.filter(role="buyer", buyer_approved=False).count()
    pending_sellers_preview = User.objects.filter(role="seller", seller_approved=False).order_by("created_at")[:5]
    pending_buyers_preview = User.objects.filter(role="buyer", buyer_approved=False).order_by("created_at")[:5]

    admin_name = "Admin"
    if request.user.is_authenticated:
        admin_name = getattr(request.user, "get_full_name", lambda: request.user.email)() or request.user.email

    context = {
        "admin_name": admin_name,
        "nav_active": "dashboard",
        "steward_flags": steward_flags,
        "payment_flags": payment_flags,
        "recent_listings": recent_listings,
        "pending_sellers_preview": pending_sellers_preview,
        "pending_buyers_preview": pending_buyers_preview,
        "metrics": {
            "total_users": f"{total_users:,}",
            "active_users_30d": f"{active_users_30d:,}",
            "books_listed": f"{books_listed:,}",
            "books_available": f"{books_available:,}",
            "orders_month": f"{orders_month:,}",
            "returns_month": f"{returns_month:,}",
            "open_flags": f"{open_flags_count}",
            "revenue_month": revenue_month,
            "pending_seller_approvals": f"{pending_seller_approvals:,}",
            "pending_buyer_approvals": f"{pending_buyer_approvals:,}",
            "total_users_note": f"+{users_this_week} this week",
            "active_users_note": f"{active_pct:.0f}% of total",
            "books_listed_note": f"+{books_today} today",
            "books_available_note": "In stock listings",
            "orders_month_note": f"{orders_today} today",
            "returns_month_note": f"{return_rate:.1f}% return rate",
            "open_flags_note": "Needs review",
            "revenue_month_note": "Platform fees",

        },
        
    }
    return render(request, "dashboard/admin_dashboard.html", context)


def _admin_context(request):
    admin_name = "Admin"
    if request.user.is_authenticated:
        admin_name = getattr(request.user, "get_full_name", lambda: request.user.email)() or request.user.email
    return {"admin_name": admin_name}

@staff_required
def seller_approvals(request):
    pending_sellers = User.objects.filter(role="seller", seller_approved=False).order_by("created_at")
    approved_sellers = User.objects.filter(role="seller", seller_approved=True).order_by("-seller_approved_at", "-created_at")
    return render(
        request,
        "users/seller_approvals.html",
        {
            "pending_sellers": pending_sellers,
            "approved_sellers": approved_sellers,
        },
    )

@staff_required
def buyer_approvals(request):
    pending_buyers = User.objects.filter(role="buyer", buyer_approved=False).order_by("created_at")
    return render(
        request,
        "users/buyer_approvals.html",
        {
            "pending_buyers": pending_buyers,
        },
    )


@staff_required
def approve_seller(request, user_id):
    if request.method != "POST":
        return redirect("seller_approvals")
    
    user = get_object_or_404(User, id=user_id, role="seller")
    if user:
        user.seller_approved = True
        user.seller_approved_at = timezone.now()
        user.save(update_fields=["seller_approved", "seller_approved_at"])

    messages.success(request, f"Seller account for {user.email} has been approved.")
    return redirect("seller_approvals")


@staff_required
def approve_buyer(request, user_id):
    if request.method != "POST":
        return redirect("buyer_approvals")

    user = get_object_or_404(User, id=user_id, role="buyer")
    if user:
        user.buyer_approved = True
        user.buyer_approved_at = timezone.now()
        user.save(update_fields=["buyer_approved", "buyer_approved_at"])

    messages.success(request, f"Buyer account for {user.email} has been approved.")
    return redirect("buyer_approvals")

@staff_required
def reports_flags(request):
    all_flags_qs = (
        FlagReport.objects.all()
        .select_related("reporter_user", "target_user", "target_book")
        .order_by("-created_at")
    )
    all_flags = [_flag_to_all_row(f) for f in all_flags_qs]

    admin_name = "Admin"
    if request.user.is_authenticated:
        admin_name = getattr(request.user, "get_full_name", lambda: request.user.email)() or request.user.email

    context = {
        "admin_name": admin_name,
        "nav_active": "reports_flags",
        "all_flags": all_flags,
    }
    return render(request, "dashboard/reports_flags.html", context)


@staff_required
def admin_users(request):
    users = User.objects.all().order_by("-created_at")[:200]
    ctx = {**_admin_context(request), "nav_active": "users", "users": users}
    return render(request, "users/users.html", ctx)


@staff_required
def toggle_user_freeze(request, user_id):
    if request.method != "POST":
        return redirect("admin_users")

    user = get_object_or_404(User, id=user_id)
    if user.id == request.user.id:
        messages.error(request, "You cannot freeze your own admin account.")
        return redirect("admin_users")

    user.is_active = not user.is_active
    user.save(update_fields=["is_active", "updated_at"])
    if user.is_active:
        messages.success(request, f"User {user.email} has been unfrozen.")
    else:
        messages.success(request, f"User {user.email} has been frozen.")
    return redirect("admin_users")


@staff_required
def admin_books(request):
    books = Book.objects.all().select_related("seller_user").order_by("-created_at")[:200]
    ctx = {**_admin_context(request), "nav_active": "books", "books": books}
    return render(request, "books/books.html", ctx)


@staff_required
def toggle_book_freeze(request, book_id):
    if request.method != "POST":
        return redirect("admin_books")

    book = get_object_or_404(Book, id=book_id)
    book.is_active = not book.is_active
    book.save(update_fields=["is_active", "updated_at"])
    if book.is_active:
        messages.success(request, f"Book '{book.title}' is now unfrozen and visible.")
    else:
        messages.success(request, f"Book '{book.title}' has been frozen.")
    return redirect("admin_books")


@staff_required
def admin_inventory(request):
    from General.models import Inventory

    inventory = Inventory.objects.select_related("book").order_by("book__title")[:200]
    ctx = {**_admin_context(request), "nav_active": "inventory", "inventory": inventory}
    return render(request, "inventory/inventory.html", ctx)


@staff_required
def admin_returns(request):
    returns = ReturnRequest.objects.select_related("order").order_by("-created_at")[:200]
    ctx = {**_admin_context(request), "nav_active": "returns", "returns": returns}
    return render(request, "returns/returns.html", ctx)


@staff_required
def admin_payments(request):
    paid = Order.objects.filter(status__in=("paid", "shipped", "delivered")).select_related("user").order_by("-created_at")[:200]
    
    ctx = {**_admin_context(request), "nav_active": "payments", "payments": paid}
    return render(request, "payments/payments.html", ctx)


@staff_required
def admin_notifications(request):
    notifications = Notification.objects.select_related("user").order_by("-created_at")[:200]
    ctx = {**_admin_context(request), "nav_active": "notifications", "notifications": notifications}
    return render(request, "notifications/notifications.html", ctx)


@staff_required
def admin_audit_logs(request):
    audit_logs = FlagReport.objects.all().select_related("reporter_user", "target_user", "target_book").order_by("-created_at")[:200]
    ctx = {**_admin_context(request), "nav_active": "audit", "audit_logs": audit_logs}
    return render(request, "audit/audit_logs.html", ctx)


@staff_required
def admin_settings(request):
    user = request.user
    ctx = {**_admin_context(request), "nav_active": "settings"}

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "password":
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
                ctx["passwrod_error"] - " ".join(errs)
            
            else:
                user.set_password(new_pw)
                user.save()

                update_session_auth_hash(request, user)

                messages.success(request, "Password updated successfully.")
                return redirect("admin_settings")

        elif action == "security":
            question = (request.POST.get("security_question") or "").strip()
            answer = (request.POST.get("security_answer") or "").strip()

            errs = []

            if not question:
                errs.append("Please chose a security question.")
            
            if not answer:
                errs.append("Please enter a security answer.")
            
            if errs:
                ctx["security_error"] = " ".join(errs)

            else:
                user.security_question = question
                user.security_answer_hash = make_password(answer.lower())
                user.save(update_fields=["security_question", "security_answer_hash"])

                messages.success(request, "Security question updated.")
                return redirect("admin_settings")
        
    ctx["security_question_choices"] = [
        ("city", "What city were you born in?"),
        ("pet", "What was the name of your first pet?"),
        ("mother_maiden", "What was your mothers maiden name?"),
    ]

    ctx["selected_security_question"] = user.security_question or ""

    return render(request, "settings/settings.html", ctx)


@staff_required
def user_monitoring(request):
    """User monitoring page."""
    return render(request, "users/userMonitering.html")


@staff_required
def steward_application(request):
    """Steward applications."""
    return render(request, "stewards/stewardApplication.html")


@staff_required
def abuse_detection(request):
    """Abuse detection / moderation."""
    return render(request, "moderation/abuseDetection.html")


@staff_required
def return_disputes(request):
    """Return disputes."""
    return render(request, "disputes/returnDisputes.html")


@staff_required
def activity_logs(request):
    """Activity / audit logs."""
    return render(request, "audit/activityLogs.html")
