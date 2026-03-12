from django.shortcuts import render


def home(request):
    """Buyer home / dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")


def buyer_dashboard(request):
    """Buyer dashboard."""
    return render(request, "dashboard/buyer_dashboard.html")


def buyer_cart(request):
    """Cart page. Pass default context so template lookups never fail."""
    context = {
        "cart_items": [],
        "cart_subtotal": "0.00",
        "cart_total": "0.00",
    }
    # TODO: load real cart for request.user and set cart_items, cart_subtotal, cart_total
    return render(request, "cart/buyer_cart.html", context)


def buyer_checkout(request):
    """Checkout page. Pass default context so template lookups never fail."""
    context = {
        "cart_items": [],
        "cart_subtotal": "0.00",
        "cart_total": "0.00",
        "addresses": [],
        "payment_methods": [],
        "checkout_error": None,
    }
    # TODO: load real cart, addresses, payment methods for request.user
    return render(request, "checkout/buyer_checkout.html", context)


def buyer_payments(request):
    """Payment methods / step."""
    return render(request, "checkout/buyer_payments.html")


def buyer_shipping(request):
    """Shipping / addresses step."""
    return render(request, "checkout/buyer_shipping.html")


def buyer_profile(request):
    """Buyer profile."""
    return render(request, "account/buyer_profile.html")


def order_confirmation(request):
    """Order confirmation after place order."""
    return render(request, "orders/orderConfirmation.html")


def order_detail(request, order_id=None):
    """Single order detail."""
    return render(request, "orders/orderDetail.html")


def order_history(request):
    """Order history list."""
    return render(request, "orders/orderHistory.html")


def return_request(request):
    """Request a return."""
    return render(request, "orders/ReturnRequest.html")


def review_submission(request):
    """Submit a review."""
    return render(request, "reviews/reviewSubmission.html")

