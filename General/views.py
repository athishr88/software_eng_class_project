from pathlib import Path
from urllib.parse import quote
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Book

User = get_user_model()

# Directory for local book cover images (name = book title + extension)
_BOOK_IMAGES_DIR = Path(settings.BASE_DIR) / "book_images"
if not _BOOK_IMAGES_DIR.exists():
    _BOOK_IMAGES_DIR = Path(settings.BASE_DIR).parent / "book_images"


def _get_book_cover_static_path(book_title):
    """Return static path like 'book_images/Title.jpg' if a file exists whose stem matches book title, else None."""
    name = _get_book_cover_filename(book_title)
    return ("book_images/" + name) if name else None


def _get_book_cover_filename(book_title):
    """Return filename (e.g. '1984.jpg') if a cover exists in book_images, else None. Caller uses default.jpg when None."""
    if not book_title or not _BOOK_IMAGES_DIR.exists():
        return None
    suffix_ok = (".jpg", ".jpeg", ".png", ".gif")
    title_to_name = {}
    for f in _BOOK_IMAGES_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in suffix_ok:
            stem, name = f.stem, f.name
            title_to_name[stem] = name
            title_to_name[stem.lower()] = name
    return title_to_name.get(book_title) or title_to_name.get(book_title.lower())


def serve_book_cover(request, path):
    """Serve a book cover image from the book_images directory (avoids STATICFILES lookup)."""
    if not _BOOK_IMAGES_DIR.exists():
        raise Http404("Book images directory not found")
    # Prevent path traversal: only allow a single filename (no slashes, no ..)
    if not path or ".." in path or "/" in path or "\\" in path:
        raise Http404("Invalid path")
    root = _BOOK_IMAGES_DIR.resolve()
    file_path = (root / path).resolve()
    try:
        file_path.relative_to(root)
    except ValueError:
        raise Http404("File not found")
    if not file_path.is_file():
        raise Http404("File not found")
    return FileResponse(open(file_path, "rb"), as_attachment=False)


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


def email_verification(request):
    """Email verification page."""
    return render(request, "auth/email_verification.html")


def catalog(request):
    """Book catalog / browse: list all active books from DB with filters and pagination."""
    qs = Book.objects.filter(is_active=True).select_related("seller_user").prefetch_related("inventory").order_by("title").distinct()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(description__icontains=q))

    min_price = request.GET.get("min_price")
    if min_price is not None and min_price != "":
        try:
            qs = qs.filter(base_price_cents__gte=int(float(min_price) * 100))
        except (ValueError, TypeError):
            pass
    max_price = request.GET.get("max_price")
    if max_price is not None and max_price != "":
        try:
            qs = qs.filter(base_price_cents__lte=int(float(max_price) * 100))
        except (ValueError, TypeError):
            pass

    if request.GET.get("in_stock"):
        qs = qs.filter(inventory__quantity_available__gt=0).distinct()

    sort = request.GET.get("sort") or ""
    if sort == "price_asc":
        qs = qs.order_by("base_price_cents")
    elif sort == "price_desc":
        qs = qs.order_by("-base_price_cents")
    elif sort == "newest":
        qs = qs.order_by("-created_at")
    elif sort == "rating_desc":
        pass  # keep default if no ratings yet
    else:
        qs = qs.order_by("title")

    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page", 1)
    if not page_number or page_number == "0":
        page_number = 1
    page_obj = paginator.get_page(page_number)

    for book in page_obj.object_list:
        fn = _get_book_cover_filename(book.title) or "default.jpg"
        book.cover_serve_url = request.build_absolute_uri(f"/book_covers/{quote(fn, safe='')}")

        ##book.cover_serve_url = f"/book_images/{quote(fn, safe='')}"
        

    return render(
        request, 
        "catalog/catalog.html", 
        {
            "page_obj": page_obj,
        }
    )


def book_detail(request, book_id):
    """Single book detail by pk."""
    book = get_object_or_404(Book, pk=book_id)
    seller_display_name = (
        f"{book.seller_user.first_name} {book.seller_user.last_name}".strip()
        if book.seller_user else "—"
    )
    cover_static_path = _get_book_cover_static_path(book.title)
    cover_serve_filename = _get_book_cover_filename(book.title) or "default.jpg"
    cover_serve_url = request.build_absolute_uri(f"/book_covers/{quote(cover_serve_filename, safe='')}")
    return render(
        request,
        "catalog/book_detail.html",
        {
            "book": book,
            "seller_display_name": seller_display_name,
            "cover_static_path": cover_static_path,
            "cover_serve_filename": cover_serve_filename,
            "cover_serve_url": cover_serve_url,
            "reviews": [],
        },
    )
    


def cart(request):
    """TEMP BUYER CART PAGE"""
    cart_items = []
    subtotal = 0.00

    return render(
        request,
        "catalog/cart.html",
        {
            "cart_items": cart_items,
            "subtotal": subtotal,
        },
    )

def checkout(request):
    """TEMP CHECKOUT SUMMARY PAGE"""
    cart_items = []
    subtotal = 0.00
    tax = 0.00
    fees = 0.00
    final_total = 0.00

    return render(
        request,
        "catalog/cart.html",
        {
            "cart_items": cart_items,
            "subtotal": subtotal,
            "tax": tax,
            "fees": fees,
            "final_total": final_total,
        },
    )


def logout_view(request):
    """Log out, clear JWT cookies, and redirect to home."""
    logout(request)
    response = redirect("general_home")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
