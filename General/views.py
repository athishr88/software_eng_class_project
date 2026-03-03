from django.shortcuts import render, redirect
from django.contrib.auth import logout


def home(request):
    """Landing / home (e.g. redirect to login or marketing)."""
    return render(request, "home/index.html")


def login_page(request):
    """General login page (Buyer/Seller/Admin entry)."""
    return render(request, "login/login_page.html")


def register(request):
    """Registration page."""
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
    """Log out and redirect to home."""
    logout(request)
    return redirect("general_home")
