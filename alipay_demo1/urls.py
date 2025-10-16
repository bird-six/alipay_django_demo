from django.contrib import admin
from django.urls import path
from demo import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('product/', views.product, name="product"),
    path('order/<int:product_id>/', views.order, name="order"),
    path('order_list/', views.order_list, name="order_list"),

    path('pay/success/', views.success, name="success"),
    path('pay/fail/', views.fail, name="fail"),
    path('pay/<str:order_id>/', views.pay, name="pay"),
    path('alipay/notify/', views.alipay_notify, name="alipay_notify"),
]
