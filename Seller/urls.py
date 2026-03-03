from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="seller_home"),
    path("dashboard/", views.dashboard, name="seller_dashboard"),
    path("inventory/", views.manage_inventory, name="manage_inventory"),
    path("inventory/add/", views.add_books, name="add_books"),
    path("orders/", views.orders, name="seller_orders"),
    path("orders/<int:order_id>/", views.order_details, name="seller_order_details"),
]
