from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="seller_home"),
    path("addbooks/", views.add_books, name="add_books"),
    path("dashboard/", views.dashboard, name="seller_dashboard"),
]
