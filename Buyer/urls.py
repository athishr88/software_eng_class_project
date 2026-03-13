from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="buyer_home"),
    path("dashboard/", views.buyer_dashboard, name="buyer_dashboard"),
    path("cart/", views.buyer_cart, name="cart"),
    path("cart/add/<int:book_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/remove/<int:item_id>/", views.remove_cart_item, name="remove_cart_item"),
    path("cart/update/<int:item_id>/", views.update_cart_item, name="update_cart_item"),
    path("checkout/", views.buyer_checkout, name="checkout"),
    path("checkout/payments/", views.buyer_payments, name="buyer_payments"),
    path("checkout/shipping/", views.buyer_shipping, name="buyer_shipping"),
    path("profile/", views.buyer_profile, name="buyer_profile"),
    path("orders/", views.order_history, name="order_history"),
    path("orders/confirmation/", views.order_confirmation, name="order_confirmation"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/return/", views.return_request, name="return_request"),
    path("reviews/submit/", views.review_submission, name="review_submission"),
]
