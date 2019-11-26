from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_jwt.settings import api_settings
from rest_framework.generics import GenericAPIView

from .utils import OAuthQQ
from .exceptions import QQAPIError
from .models import OAuthQQUser
from .serializers import OAuthQQUserSerializer
from carts.utils import merge_cart_cookie_to_redis

class QQAuthURLView(APIView):

    def get(self, request):
        # 获取next参数，next可以为空，所以不用校验
        next = request.query_params.get('next')
        oauth = OAuthQQ(state=next)
        login_url = oauth.get_login_url()
        return Response({'login_url': login_url})



class QQAuthUserView(GenericAPIView):
    """
    QQ登录的用户
    """
    serializer_class = OAuthQQUserSerializer
    def get(self, request):
        """
        获取qq登录的用户数据
        """
        code = request.query_params.get('code')
        if not code:
            return Response({'message': '缺少code'}, status=status.HTTP_400_BAD_REQUEST)

        oauth = OAuthQQ()

        # 获取用户openid
        try:
            access_token = oauth.get_access_token(code)
            openid = oauth.get_openid(access_token)
        except QQAPIError:
            return Response({'message': 'QQ服务异常'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 判断用户是否存在
        try:
            qq_user = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            # 用户第一次使用QQ登录
            token = oauth.generate_save_user_token(openid)
            return Response({'access_token': token})
        else:
            # 找到用户, 生成token
            user = qq_user.user
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)

            response = Response({
                'token': token,
                'user_id': user.id,
                'username': user.username
            })
            # 合并购物车
            response = merge_cart_cookie_to_redis(request, user, response)

            return response


    # def post(self, request):
    #     """
    #     QQ扫描之后，如果没有openid,就post请求登陆
    #     保存QQ登录用户数据
    #     """
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     user = serializer.save()

    #     # 生成已登录的token
    #     jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
    #     jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

    #     payload = jwt_payload_handler(user)
    #     token = jwt_encode_handler(payload)

    #     response = Response({
    #         'token': token,
    #         'user_id': user.id,
    #         'username': user.username
    #     })

    #     # 合并购物车
    #     response = merge_cart_cookie_to_redis(request, user, response)

    #     return response

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # 合并购物车
        user = self.user
        response = merge_cart_cookie_to_redis(request, user, response)

        return response
