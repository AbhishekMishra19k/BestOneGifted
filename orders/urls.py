from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('success/<int:order_id>/<str:token>/', views.order_success, name='order_success'),
    path('my-orders/', views.order_history, name='order_history'),
    path('my-orders/<int:order_id>/', views.order_detail, name='order_detail'),
]
