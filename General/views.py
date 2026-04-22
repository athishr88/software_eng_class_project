from pathlib import Path
from urllib.parse import quote
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django import forms
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from rest_framework_simplejwt.tokens import RefreshToken
from django.middleware.csrf import get_token
from .forms import ForgotPasswordEmailForm, RegisterForm, SecurityQuestionResetForm, SecurityQuestionForm
from Admin.models import FlagReport
from .models import Book, StewardContribution
from Buyer.models import Order, OrderItem, Review
from django.views.decorators.cache import never_cache

User = get_user_model()

# Directory for local book cover images (name = book title + extension)
_BOOK_IMAGES_DIR = Path(settings.BASE_DIR) / "book_images"
if not _BOOK_IMAGES_DIR.exists():
    _BOOK_IMAGES_DIR = Path(settings.BASE_dsDIR).parent / "book_images"

SECURITY_QUESTION_CHOICES = {
    "city": "In what city were you born?",
    "mother_maiden": "What is your mother's maiden name?",
    "first_pet": "What was the name of your first pet?",
}
def _sanitize_book_title_for_filename(title: str) -> str:
    """Make a safe filename stem from a book title (Windows-friendly)."""
    if not title:
        return "book"
    invalid_chars = set('<>:"/\\|?*')
    cleaned_chars = []
    for ch in title:
        if ch in invalid_chars or ord(ch) < 32:
            cleaned_chars.append("_")
        else:
            cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars).strip().strip(".")
    return cleaned or "book"


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

    # Try direct title match first (for existing filenames), then fallback to
    # sanitized-title match (for uploaded covers).
    candidates = [book_title, book_title.lower()]
    safe_title = _sanitize_book_title_for_filename(book_title)
    candidates.extend([safe_title, safe_title.lower()])
    for c in candidates:
        if c in title_to_name:
            return title_to_name[c]
    return None


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
    return render(request, "login/login_page.html")


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

@never_cache
def login_page(request):
    """Login: GET shows form; POST authenticates, session login, JWT cookies, redirect by role or next."""
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if request.user.is_authenticated:
        if request.user.role == "admin":
            return redirect("admin_dashboard")
        elif request.user.role == "seller":
            if getattr(request.user, "seller_approved", False):
                return redirect("seller_home")
            messages.error(request, "Your account is pending approval.")
            return redirect("buyer_home")
        return redirect("buyer_home")
    
    if request.method == "POST":
        identifier = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=identifier, password=password)
        
        if user is not None and user.is_active:
            if user.role == "buyer" and not user.buyer_approved:
                messages.error(request, "Your buyer account is pending admin approval.")
                logout(request)
                return redirect("login")
            login(request, user)

            from Buyer.cart_helpers import merge_session_cart_into_db

            merge_session_cart_into_db(user, request.session)
            if next_url and next_url.startswith("/"):
                response = redirect(next_url)
            elif user.role == "admin":
                response = redirect("admin_dashboard")
            elif user.role == "seller":
                if getattr(user, "seller_approved", False):
                    response = redirect("seller_home")
                else:
                    messages.error(request, "Your seller account is pending approval.")
                    response = redirect("buyer_home")
            else:
                response = redirect("buyer_home")
            return _set_jwt_cookies(response, user)
        return render(
            request,
            "login/login_page.html",
            {"error": "Invalid email or password.", "next": next_url},
        )

    get_token(request)
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
        security_question = (request.POST.get("security_question") or "").strip()
        security_answer = (request.POST.get("security_answer") or "").strip()

        if role not in ("buyer", "seller"):
            role = "buyer"
        phone = (request.POST.get("phone") or "").strip() or None
        store_name = (request.POST.get("store_name") or "").strip() or None

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
        if not security_question:
            errors.append("Security question is required.")
        if not security_answer:
            errors.append("Security answer is required.")
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
        user.security_question = security_question
        user.security_answer_hash = make_password(security_answer.strip().lower())
        user.save(update_fields=["security_question", "security_answer_hash"])

        if role == "seller":
            from Seller.models import SellerProfile
            user.seller_approved = False
            user.save(update_fields=["seller_approved"])

            SellerProfile.objects.update_or_create(
                user=user,
                defaults={"store_name": store_name},
            )
    
        login(request, user)

        from Buyer.cart_helpers import merge_session_cart_into_db
        merge_session_cart_into_db(user, request.session)

        if user.role == "seller":
            response = redirect("seller_home")
        else:
            response = redirect("buyer_home")

        return _set_jwt_cookies(response, user)
    return render(request, "auth/register.html")


def email_verification(request):
    """Email verification page."""
    return render(request, "auth/email_verification.html")

@login_required(login_url="login")
def profile_settings(request):
    user = request.user

    if user.role == "admin":
        template_name = "auth/admin_profile.html"
    elif user.role == "seller":
        template_name = "auth/seller_profile.html"
    else:
        template_name = "auth/buyer_profile.html"
    
    if request.method == "POST":
        form = SecurityQuestionForm(request.POST)
        if form.is_valid():
            user.security_question = form.cleaned_data["security_question"]
            user.security_answer_hash = make_password(form.cleaned_data["security_answer"].strip().lower())
            user.save(update_fields=["security_question", "security_answer_hash"])

            messages.success(request, "Your security question has been updated.")
            return redirect("profile_settings")
        
    else:
        form = SecurityQuestionForm(initial={
            "security_question": user.security_question or "",
        })

    return render(request, template_name, {"form": form})

@login_required(login_url="login")
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
    
    compare_list = request.session.get("compare_list", [])
    compare_count = len(compare_list)

    return render(
        request, 
        "catalog/catalog.html", 
        {
            "page_obj": page_obj,
            "compare_count": len(request.session.get("compare_list", [])),
        }
    )

@login_required(login_url="login")
def book_detail(request, pk=None):
    """Single book detail by pk."""
    book = get_object_or_404(Book.objects.filter(is_active=True ), pk=pk)
    seller_display_name = (
        f"{book.seller_user.first_name} {book.seller_user.last_name}".strip()
        if book.seller_user else "—"
    )
    cover_static_path = _get_book_cover_static_path(book.title)
    cover_serve_filename = _get_book_cover_filename(book.title) or "default.jpg"
    cover_serve_url = request.build_absolute_uri(f"/book_covers/{quote(cover_serve_filename, safe='')}")
    
    reviews = Review.objects.filter(
        order_item__book=book
    ).select_related("user").order_by("created_at")
    
    return render(
        request,
        "catalog/book_detail.html",
        {
            "book": book,
            "seller_display_name": seller_display_name,
            "cover_static_path": cover_static_path,
            "cover_serve_filename": cover_serve_filename,
            "cover_serve_url": cover_serve_url,
            "reviews": reviews,
        },
    )

def add_to_compare(request, book_id):
    compare_list = request.session.get("compare_list", [])

    compare_list = [int(x) for x in compare_list]

    if book_id not in compare_list:
        compare_list.append(book_id)
    
    if len(compare_list) > 4:
        compare_list = compare_list[:4]

    request.session["compare_list"] = compare_list
    request.session.mofified = True
    return redirect(request.META.get("HTTP_REFERER", "catalog"))

def remove_from_compare(request, book_id):
    compare_list = request.session.get("compare_list", [])
    compare_list = [int(x) for x in compare_list]

    if book_id in compare_list:
        compare_list.remove(book_id)
    
    request.session["compare_list"] = compare_list
    request.session.modified = True

    return redirect("compare_products")

def clear_compare(request):
    request.session["compare_list"] = []
    request.session.modified = True
    return redirect("compare_products")

def compare_products(request):
    compare_list = request.session.get("compare_list", [])
    compare_list = [int(x) for x in compare_list]
    books = Book.objects.filter(id__in=compare_list, is_active=True)

    books_by_id = {book.id: book for book in books}
    
    compared_books = []
    for book_id in compare_list:
        book = books_by_id.get(book_id)
        if not book:
            continue

        reviews = Review.objects.filter(order_item__book=book)
        avg_rating = reviews.aggregate(avg=Avg("rating"))["avg"]

        if avg_rating:
            rating_display = f"{round(avg_rating,1)} / 5"
        else:
            rating_display = "No Ratings"
        cover_serve_filename = _get_book_cover_filename(book.title) or "default.jpg"
        cover_serve_url = request.build_absolute_uri(
            f"/book_covers/{quote(cover_serve_filename, safe='')}"
        )

        compared_books.append({
            "book": book,
            "rating_display": rating_display,
            "price_dollars": book.base_price_cents / 100,
            "stock_quantity": book.stock_quantity,
            "cover_serve_url": cover_serve_url
        })
    
    context = {
        "compared_books": compared_books,
    }
    return render(request, "compare/compare_products.html", {"compared_books": compared_books,})

@login_required(login_url="login")
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
@login_required(login_url="login")
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

@login_required(login_url="login")
def logout_view(request):
    """Log out, clear JWT cookies, and redirect to home."""
    logout(request)
    response = redirect("login")
    response.delete_cookie("sessionid")
    response.delete_cookie("csrftoken")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@login_required(login_url="login")
def steward_contribute(request):
    """Record a steward contribution (General.StewardContribution)."""
    if request.method == "POST":
        name = (request.POST.get("contributor_name") or "").strip()
        city = (request.POST.get("contributor_city") or "").strip()
        amount_raw = (request.POST.get("amount_dollars") or "").strip()
        message = (request.POST.get("message") or "").strip() or None
        errs = []
        if not name:
            errs.append("Contributor name is required.")
        if not city:
            errs.append("City is required.")
        try:
            amt = Decimal(amount_raw or "0")
            amount_cents = int((amt * 100).quantize(0, ROUND_HALF_UP))
            if amount_cents <= 0:
                errs.append("Enter a contribution amount greater than zero.")
        except (InvalidOperation, TypeError):
            errs.append("Enter a valid dollar amount.")
        if errs:
            for e in errs:
                messages.error(request, e)
            return render(
                request,
                "steward/steward_contribute.html",
                {"post": request.POST},
            )
        StewardContribution.objects.create(
            steward_user=request.user,
            contributor_name=name[:120],
            contributor_city=city[:120],
            amount_cents=amount_cents,
            message=message[:255] if message else None,
        )
        messages.success(request, "Thank you — your contribution was recorded.")
        return redirect("steward_contribute")

    return render(request, "steward/steward_contribute.html")


@login_required(login_url="login")
def flag_book(request, pk):
    """Create Admin.FlagReport for a listing (POST)."""
    if request.method != "POST":
        return redirect("book_detail", pk=pk)

    book = get_object_or_404(Book.objects.filter(is_active=True), pk=pk)
    flag_type = (request.POST.get("flag_type") or "other").strip()[:80]
    details = (request.POST.get("details") or "").strip() or None

    FlagReport.objects.create(
        reporter_user=request.user,
        target_user=book.seller_user,
        target_book=book,
        flag_type=flag_type or "other",
        details=details,
    )
    messages.success(request, "Thanks — your report was submitted for review.")
    return redirect("book_detail", pk=pk)

class ForgotPasswordEmailForm(forms.Form):
    email = forms.EmailField(label="Email")

class SecurityQuestionResetForm(forms.Form):
    answer = forms.CharField(label="Security Question Answer", max_length=255)
    new_password1 = forms.CharField(label="New Password", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="Confirm New Password", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        pw1 = cleaned_data.get("new_password1")
        pw2 = cleaned_data.get("new_password2")

        if pw1 and pw2 and pw1 != pw2:
            self.add_error("new_password2", "Passwords do not match.")
        
        if pw1:
            validate_password(pw1)
        
        return cleaned_data

def forgot_password_email(request):
    if request.method == "POST":
        form = ForgotPasswordEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            try:
                user = User.objects.get(email__iexact=email, is_active=True)
                request.session["password_reset_user_id"] = user.id
                return redirect("forgot_password_question")
            except User.DoesNotExist:
                form.add_error("email", "No account found with that email.")
    else:
        form = ForgotPasswordEmailForm()
    return render(request, "auth/forgot_password_email.html", {"form": form})

def forgot_password_question(request):
    user_id = request.session.get("password_reset_user_id")
    if not user_id:
        return redirect("forgot_password_email")
    try:
        user = get_object_or_404(User, id=user_id, is_active=True)
    except User.DoesNotExist:
        request.session.pop("password_reset_user_id", None)
        return redirect("forgot_password_email")
    
    if not user.security_question or not user.security_answer_hash:
        return render(request, "auth/forgot_password_question.html", {"form": SecurityQuestionResetForm(), "security_question": "", "no_question_set": True})
    

    if request.method == "POST":
        form = SecurityQuestionResetForm(request.POST)
        if form.is_valid():
            answer = form.cleaned_data["answer"].strip().lower()

            if check_password(answer, user.security_answer_hash):
                user.set_password(form.cleaned_data["new_password1"])
                user.save()
                request.session.pop("password_reset_user_id", None)
                return redirect("forgot_password_done")
            else:
                form.add_error("answer", "Incorrect security answer.")
    else:
        form = SecurityQuestionResetForm()
    return render(request, "auth/forgot_password_question.html", {"form": form, "security_question": SECURITY_QUESTION_CHOICES.get(user.security_question, user.security_question), "no_question_set": False})

def forgot_password_done(request):
    return render(request, "auth/forgot_password_done.html")

def _save_security_question(user, form):
    user.security_question = form.cleaned_data["security_question"]
    user.security_answer_hash = make_password(form.cleaned_data["security_answer"].strip().lower())
    user.save(update_fields=["security_question", "security_answer_hash"])
    
def account_security(request):
    user = request.user
    if request.method == "POST":
        form = SecurityQuestionForm(request.POST)
        if form.is_valid():
            user.security_question = form.cleaned_data["security_question"]
            user.security_answer_hash = make_password(form.cleaned_data["security_answer"].strip().lower())
            user.save()
            messages.success(request, "Security question updated.")
            return redirect("account_security")
        
    else:
        initial_data = {}
        if user.security_question:
            initial_data["security_question"] = user.security_question
        form = SecurityQuestionForm(initial=initial_data)

    return render(request, "auth/account_security.html", {"form": form})