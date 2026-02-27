from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="seller_home"),
]
