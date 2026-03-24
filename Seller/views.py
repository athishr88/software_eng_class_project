from django.shortcuts import render


def home(request):
    """Seller home / dashboard."""
    return render(request, "dashboard/dashboard.html")


def dashboard(request):
    """Seller dashboard."""
    return render(request, "dashboard/dashboard.html")


def add_books(request):
    """Form to add books for sale."""
    return render(request, "inventory/addBooks.html")


def manage_inventory(request):
    """Manage inventory / listings."""
    return render(request, "inventory/manageInventory.html")


def orders(request):
    """Orders list."""
    return render(request, "orders/orders.html")


def order_details(request, order_id=None):
    """Single order detail."""
    return render(request, "orders/orderDetails.html")
