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
    path(
        "checkout/payments/set-default/<int:payment_method_id>/",
        views.set_default_payment_method,
        name="set_default_payment_method",
    ),
    path(
        "checkout/payments/delete/<int:payment_method_id>/",
        views.delete_payment_method,
        name="delete_payment_method",
    ),
    path("checkout/shipping/", views.buyer_shipping, name="buyer_shipping"),
    path(
        "checkout/shipping/set-default/<int:address_id>/",
        views.set_default_shipping_address,
        name="set_default_address",
    ),
    path(
        "checkout/shipping/delete/<int:address_id>/",
        views.delete_shipping_address,
        name="delete_address",
    ),
    path("profile/", views.buyer_profile, name="buyer_profile"),
    path("orders/", views.order_history, name="order_history"),
    path(
        "orders/confirmation/<int:order_id>/",
        views.order_confirmation,
        name="order_confirmation",
    ),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path(
        "orders/<int:order_id>/return/",
        views.return_request_view,
        name="return_request",
    ),
    path("reviews/submit/", views.review_submission, name="review_submission"),
]
