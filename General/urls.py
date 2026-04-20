from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

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
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="auth/password_reset_form.html",
        email_template_name="auth/password_reset_email.txt",
        subject_template_name="auth/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="auth/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="auth/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="auth/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

]
