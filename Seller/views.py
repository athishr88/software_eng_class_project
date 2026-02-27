from django.shortcuts import render


def home(request):
    """Placeholder: Seller dashboard / listings."""
    return render(request, "Seller/home/index.html")
