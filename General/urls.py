from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="general_home"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register, name="register"),
    path("email-verification/", views.email_verification, name="email_verif"),
    path("profile/settings/", views.profile_settings, name="profile_settings"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<int:pk>/", views.book_detail, name="book_detail"),
    path("catalog/<int:pk>/flag/", views.flag_book, name="flag_book"),
    path("steward/contribute/", views.steward_contribute, name="steward_contribute"),
    path("book_covers/<path:path>", views.serve_book_cover, name="serve_book_cover"),
    path("compare/", views.compare_products, name="compare_products"),
    path("compare/add/<int:book_id>/", views.add_to_compare, name="add_to_compare"),
    path("compare/remove/<int:book_id>/", views.remove_from_compare, name="remove_from_compare"),
    path("compare/clear/", views.clear_compare, name="clear_compare"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("logout/", views.logout_view, name="logout"),
    path("forgot-password/", views.forgot_password_email, name="forgot_password_email"),
    path("forgot-password/question/", views.forgot_password_question, name="forgot_password_question"),
    path("forgot-password/done/", views.forgot_password_done, name="forgot_password_done"),
    path("account/security/", views.account_security, name="account_security"),
]