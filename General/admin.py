from django.contrib import admin
from .models import User, Address, Book, Inventory, StewardContribution, Notification

admin.site.register(User)
admin.site.register(Address)
admin.site.register(Book)
admin.site.register(Inventory)
admin.site.register(StewardContribution)
admin.site.register(Notification)