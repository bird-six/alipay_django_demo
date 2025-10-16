import logging
from alipay.aop.api.util.SignatureUtils import verify_with_rsa
from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from demo.models import Product, Order
from alipay_demo1 import settings

# 初始化客户端配置对象AlipayClientConfig
alipay_client_config = AlipayClientConfig()     # 初始化支付宝客户端配置对象
alipay_client_config.server_url = 'https://openapi-sandbox.dl.alipaydev.com/gateway.do'     # 沙箱环境
alipay_client_config.app_id = settings.ALIPAY_SETTINGS['appid']    # 应用ID
alipay_client_config.app_private_key = settings.ALIPAY_SETTINGS['app_private_key']    # 应用私钥
alipay_client_config.alipay_public_key = settings.ALIPAY_SETTINGS['alipay_public_key']    # 支付宝公钥
alipay_client_config.sign_type = settings.ALIPAY_SETTINGS['sign_type']  # 签名类型（默认RSA2）

# 创建客户端DefaultAlipayClient实例（一个配置对应一个客户端，配置不可动态修改）
# 如果想使用不同的配置，请定义不同的DefaultAlipayClient
alipay_client = DefaultAlipayClient(alipay_client_config)     # 创建默认的支付宝客户端对象实例



def product(request):
    products = Product.objects.all()
    return render(request, "product.html", {"products": products})

def order(request, product_id):
    product = Product.objects.get(id=product_id)
    order = Order.objects.create(total_amount=product.price, product=product)
    return render(request, "order.html", {"order_id": order.order_id, "product": product})

def order_list(request):
    orders = Order.objects.all()
    return render(request, "order_list.html", {"orders": orders})

def pay(request, order_id):
    if request.method == 'POST':
        # 获取订单数据
        order = Order.objects.get(order_id=order_id)

        # 1. 创建订单参数模型（AlipayTradePagePayModel）
        page_pay_model = AlipayTradePagePayModel()
        page_pay_model.out_trade_no = order_id  # 商户订单号（唯一）
        page_pay_model.total_amount = "{0:.2f}".format(order.total_amount)  # 订单金额
        page_pay_model.subject = order.product.name  # 订单标题
        page_pay_model.product_code = "FAST_INSTANT_TRADE_PAY"  # 销售产品码，电脑网站固定为FAST_INSTANT_TRADE_PAY

        # 2. 创建支付请求对象
        page_pay_request = AlipayTradePagePayRequest(biz_model=page_pay_model)  # 关联订单参数模型
        page_pay_request.return_url = settings.ALIPAY_SETTINGS["app_return_url"]  # 同步回调地址（用户支付后跳转）
        page_pay_request.notify_url = settings.ALIPAY_SETTINGS["app_notify_url"]  # 异步通知地址（核心状态通知）

        # 3. 生成支付链接，前端跳转支付页面
        pay_url = alipay_client.page_execute(page_pay_request, http_method='GET')  # 调用page_execute方法生成支付链接（http_method可选"GET"或"POST"）

        return HttpResponse(f'<script>window.location.href="{pay_url}";</script>')  # 返回支付URL，前端跳转至支付宝支付页面

def success(request):
    # 从支付宝返回的参数中获取订单号（out_trade_no）
    out_trade_no = request.GET.get('out_trade_no')
    order = get_object_or_404(Order, order_id=out_trade_no)
    return render(request, "success.html", {"order": order})

def fail(request):
    return render(request, "fail.html")

# 通知参数处理函数
def get_dic_sorted_params(org_dic_params):
    content = ''
    org_dic_params.pop('sign')
    org_dic_params.pop('sign_type')  # 去除sign、sigh_type
    new_list = sorted(org_dic_params, reverse=False)  # 待验签参数进行排序
    for i in new_list:
        p = i + '=' + org_dic_params.get(i) + '&'
        content += p
    sorted_params = content.strip('&')  # 重组字符串，将{k:v}形式的字典类型原始响应值--》转换成'k1=v1&k2=v2'形式的字符串格式
    return sorted_params


# 支付宝同步通知回调视图函数
def alipay_return(request):
    # 获取支付宝返回的所有参数
    params = request.GET.dict()
    # 提取签名
    sign = params.get('sign')
    # 对通知参数进行处理
    org_message = get_dic_sorted_params(params)
    # 转换成字节串
    message = bytes(org_message, encoding='utf-8')

    # 验证签名
    verified = verify_with_rsa(
        public_key=settings.ALIPAY_SETTINGS['alipay_public_key'],
        message=message,
        sign=sign,
    )

    if verified and params["trade_status"] in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
        # 验签成功且交易状态有效（仅用于前端展示）
        order_id = params.get("out_trade_no")  # 商户订单号
        order = get_object_or_404(Order, order_id=order_id)
        return render(request, "success.html", {"order": order})
    else:
        # 验签失败或交易状态异常
        return render(request, "fail.html")


# 支付宝异步通知回调视图函数
@csrf_exempt    # 禁用CSRF防护，确保支付宝异步通知可以正常接收
def alipay_notify(request):
    if request.method == 'POST':
        # 1. 获取支付宝发送的通知参数（POST形式）
        params = request.POST.dict()
        # 2. 提取签名（用于验证）
        sign = params.get('sign')
        # 3. 对通知参数进行处理
        org_message = get_dic_sorted_params(params)
        # 4. 转换成字节串
        message = bytes(org_message, encoding='utf-8')

        # 5. verify_with_rsa方法验证签名
        verified = verify_with_rsa(
            public_key=settings.ALIPAY_SETTINGS['alipay_public_key'],
            message=message,
            sign=sign,
        )

        # 6. 检查验证状态
        if not verified:
            print("支付宝异步通知：签名验证失败")
            return HttpResponse("fail")  # 签名验证失败返回fail，这是支付宝接口的硬性要求

        trade_status = params.get('trade_status')
        if trade_status not in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
            logging.info(f"支付未成功，状态：{trade_status}")
            return HttpResponse("success")  # 支付宝要求非成功状态也返回success

        # 7. 数据更新逻辑
        try:
            out_trade_no = params.get('out_trade_no')
            order = Order.objects.get(order_id=out_trade_no)

            # 幂等性处理：如果已经支付成功，直接返回
            if order.status == "已支付":
                return HttpResponse("success")

            order.status = "已支付"  # 更新订单状态
            order.save()
            logging.info(f"订单{out_trade_no}支付成功，状态已更新")
        except Exception as e:
            logging.error(f"处理订单失败：{str(e)}")
            return HttpResponse("fail")
        return HttpResponse("success")
    return HttpResponse("fail")  # 非POST请求返回fail