from django.shortcuts import render


def home(request):
    """Placeholder: Seller dashboard / listings."""
    return render(request, "Seller/home/index.html")

def add_books(request):
    """Placeholder: Form to add books for sale."""
    return render(request, "addBooks.html")

def dashboard(request):
    """Placeholder: Seller dashboard / listings."""
    return render(request, "addBooks.html")
