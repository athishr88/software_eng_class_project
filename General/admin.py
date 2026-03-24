from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Address, Book, Inventory, StewardContribution, Notification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")
    # auto_now_add / auto_now fields are not editable; they must be readonly to appear on the form.
    readonly_fields = ("last_login", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        ("Role & status", {"fields": ("role", "steward_verified", "steward_city", "is_active", "is_staff")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
        ("Permissions", {"fields": ("groups", "user_permissions", "is_superuser")}),
    )

    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "password1", "password2")}),
        ("Role & status", {"fields": ("role", "is_active", "is_staff")}),
    )


admin.site.register(Address)
admin.site.register(Book)
admin.site.register(Inventory)
admin.site.register(StewardContribution)
admin.site.register(Notification)