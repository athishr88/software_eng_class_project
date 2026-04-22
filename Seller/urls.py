from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="seller_home"),
    path("dashboard/", views.dashboard, name="seller_dashboard"),
    path("dashboard/sales-overview/", views.sales_overview, name="seller_sales_overview"),
    path("profile/", views.seller_profile, name="seller_profile"),
    path("inventory/", views.manage_inventory, name="manage_inventory"),
    path("inventory/add/", views.add_books, name="add_books"),
    path("orders/", views.orders, name="seller_orders"),
    path("orders/<int:order_id>/", views.order_details, name="seller_order_details"),
    path("orders/<int:order_id>/status/update/", views.update_order_status, name="update_order_status"),
    path("returns/", views.return_requests_list, name="seller_return_requests"),
    path("returns/<int:return_id>/", views.return_request_detail, name="seller_return_request_detail"),
    path("webhooks/", views.seller_webhooks, name="seller_webhooks"),
]
