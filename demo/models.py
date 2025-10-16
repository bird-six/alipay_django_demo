import uuid
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=256)
    price = models.DecimalField(max_digits=11, decimal_places=2)  # 精确到分(支付宝限制参数)

class Order(models.Model):
    order_id = models.CharField(max_length=64, unique=True)
    total_amount = models.DecimalField(max_digits=11, decimal_places=2)  # 精确到分(支付宝限制参数)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)


    # 订单状态选择：待支付、已支付、已取消
    ORDER_STATUS_CHOICES = [
        ("待支付", "待支付"),
        ("已支付", "已支付"),
        ("已取消", "已取消"),
    ]
    status = models.CharField(max_length=20, default="待支付", choices=ORDER_STATUS_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    # 单号随机生成且不重复，使用uuid4
    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"{uuid.uuid4().hex[:16].upper()}"
        super().save(*args, **kwargs)
