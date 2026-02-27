from django.shortcuts import render


def login_page(request):
    """General login page (Buyer/Seller/Admin entry)."""
    return render(request, "login/login_page.html")


def home(request):
    """Landing / home (e.g. redirect to login or marketing)."""
    return render(request, "home/index.html")
