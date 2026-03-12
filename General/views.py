from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def home(request):
    """Landing: only Customer or Admin choice."""
    return render(request, "home/index.html")


def _set_jwt_cookies(response, user):
    """Set JWT access and refresh tokens in httpOnly cookies."""
    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)
    refresh_str = str(refresh)
    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        max_age=30 * 60,
        samesite="Lax",
    )
    response.set_cookie(
        "refresh_token",
        refresh_str,
        httponly=True,
        max_age=24 * 3600,
        samesite="Lax",
    )
    return response


def login_page(request):
    """Login: GET shows form; POST authenticates, session login, JWT cookies, redirect by role or next."""
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if request.method == "POST":
        email = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=email, password=password)
        if user is not None and user.is_active:
            login(request, user)
            if next_url and next_url.startswith("/"):
                response = redirect(next_url)
            elif user.role == "admin":
                response = redirect("admin_dashboard")
            elif user.role == "seller":
                response = redirect("seller_home")
            else:
                response = redirect("buyer_home")
            return _set_jwt_cookies(response, user)
        return render(
            request,
            "login/login_page.html",
            {"error": "Invalid email or password.", "next": next_url},
        )
    return render(request, "login/login_page.html", {"next": next_url})


def register(request):
    """Register: GET shows form; POST creates user, login, JWT, redirect to buyer/seller home."""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        password = request.POST.get("password") or ""
        confirm = request.POST.get("confirm_password") or ""
        role = (request.POST.get("role") or "buyer").strip().lower()
        if role not in ("buyer", "seller"):
            role = "buyer"
        phone = (request.POST.get("phone") or "").strip() or None
        errors = []
        if not email:
            errors.append("Email is required.")
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.objects.filter(email__iexact=email).exists():
            errors.append("An account with this email already exists.")
        if errors:
            return render(
                request,
                "auth/register.html",
                {"form_errors": " ".join(errors), "post": request.POST},
            )
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone=phone,
        )
        login(request, user)
        if user.role == "seller":
            response = redirect("seller_home")
        else:
            response = redirect("buyer_home")
        return _set_jwt_cookies(response, user)
    return render(request, "auth/register.html")


def email_verif(request):
    """Email verification page."""
    return render(request, "auth/email_verif.html")


def catalog(request):
    """Book catalog / browse."""
    return render(request, "catalog/catalog.html")


def book_detail(request, pk=None):
    """Single book detail (pk optional for now)."""
    return render(request, "catalog/book_detail.html")


def logout_view(request):
    """Log out, clear JWT cookies, and redirect to home."""
    logout(request)
    response = redirect("general_home")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
