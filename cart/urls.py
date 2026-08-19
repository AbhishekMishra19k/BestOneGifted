from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='cart_detail'),
    path('add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('remove/<str:key>/', views.cart_remove, name='cart_remove'),
    path('update/<str:key>/', views.cart_update, name='cart_update'),
    path('coupon/apply/', views.cart_apply_coupon, name='apply_coupon'),
    path('coupon/remove/', views.cart_remove_coupon, name='remove_coupon'),
    path('drawer/', views.cart_drawer, name='cart_drawer'),
]
