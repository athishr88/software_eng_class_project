from django.urls import path
from . import views

urlpatterns = [
    path("", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("reports/", views.reports_flags, name="reports_flags"),
    path("users/", views.user_monitoring, name="user_monitoring"),
    path("stewards/", views.steward_application, name="steward_application"),
    path("moderation/abuse/", views.abuse_detection, name="abuse_detection"),
    path("disputes/", views.return_disputes, name="return_disputes"),
    path("audit/", views.activity_logs, name="activity_logs"),
]
