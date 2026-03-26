from django.contrib import admin
from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderItemBookSnapshot,
    OrderShippingAddress,
    PaymentMethod,
    ReturnRequest,
    SellerReturnReceipt,
)

admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(PaymentMethod)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(OrderShippingAddress)
admin.site.register(OrderItemBookSnapshot)
admin.site.register(ReturnRequest)
admin.site.register(SellerReturnReceipt)