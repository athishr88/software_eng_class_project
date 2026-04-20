from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="general_home"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register, name="register"),
    path("email-verification/", views.email_verification, name="email_verif"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<int:pk>/", views.book_detail, name="book_detail"),
    path("catalog/<int:pk>/flag/", views.flag_book, name="flag_book"),
    path("steward/contribute/", views.steward_contribute, name="steward_contribute"),
    path("book_covers/<path:path>", views.serve_book_cover, name="serve_book_cover"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("logout/", views.logout_view, name="logout"),
]
