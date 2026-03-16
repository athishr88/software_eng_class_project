from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.staff_login, name="staff_login"),
    path("logout/", views.staff_logout, name="staff_logout"),
    path("", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("reports/", views.reports_flags, name="reports_flags"),
    path("users/", views.user_monitoring, name="user_monitoring"),
    path("users/list/", views.admin_users, name="admin_users"),
    path("books/", views.admin_books, name="admin_books"),
    path("inventory/", views.admin_inventory, name="admin_inventory"),
    path("returns/", views.admin_returns, name="admin_returns"),
    path("payments/", views.admin_payments, name="admin_payments"),
    path("notifications/", views.admin_notifications, name="admin_notifications"),
    path("audit/", views.admin_audit_logs, name="admin_audit_logs"),
    path("settings/", views.admin_settings, name="admin_settings"),
    path("stewards/", views.steward_application, name="steward_application"),
    path("moderation/abuse/", views.abuse_detection, name="abuse_detection"),
    path("disputes/", views.return_disputes, name="return_disputes"),
    path("audit/legacy/", views.activity_logs, name="activity_logs"),
]
