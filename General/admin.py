from django.contrib import admin
from .models import User, Address, Book, Inventory

admin.site.register(User)
admin.site.register(Address)
admin.site.register(Book)
admin.site.register(Inventory)