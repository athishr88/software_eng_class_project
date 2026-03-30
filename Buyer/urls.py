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
    path("checkout/save-payment-method/", views.save_payment_method, name="save_payment_method"),
    path("checkout/payment/delete/<int:method_id>/", views.action_delete_payment_method, name="action_delete_payment_method"),
    path("checkout/payments/default/<int:method_id>/", views.set_default_payment_method, name="set_default_payment_method"),
    path("checkout/shipping/", views.buyer_shipping, name="buyer_shipping"),
    path("checkout/save-shipping-address/", views.save_shipping_address, name="save_shipping_address"),
    path("checkout/shipping/delete/<int:addr_id>/", views.action_delete_address, name="action_delete_address"),
    path("checkout/shipping/default/<int:addr_id>/", views.set_default_address, name="set_default_address"),
    path("checkout/place-order/", views.place_order, name="place_order"),
    path("profile/", views.buyer_profile, name="buyer_profile"),
    path("orders/", views.order_history, name="order_history"),
    path("orders/confirmation/", views.order_confirmation, name="order_confirmation"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/return-request/", views.return_request, name="return_request"),
    path("orders/<int:order_id>/return-request-submit/", views.return_request_submit, name="return_request_submit"),
    path("orders/<int:order_id>/review/save/", views.save_inline_review, name="save_inline_review"),

]
