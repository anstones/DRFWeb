#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from rest_framework import serializers
from django_redis import get_redis_connection
from rest_framework_jwt.settings import api_settings
from users.models import User
from .utils import OAuthQQ
from .models import OAuthQQUser

class OAuthQQUserSerializer(serializers.Serializer):
    """
    QQ登录创建用户序列化器
    """
    access_token = serializers.CharField(label='操作凭证')
    mobile = serializers.RegexField(label='手机号', regex=r'^1[3-9]\d{9}$')
    password = serializers.CharField(label='密码', max_length=20, min_length=8)
    sms_code = serializers.CharField(label='短信验证码')

    def validate(self, data):
        # 检验access_token
        access_token = data['access_token']
        openid = OAuthQQ.check_save_user_token(access_token)
        if not openid:
            raise serializers.ValidationError('无效的access_token')

        data['openid'] = openid

        # 检验短信验证码
        mobile = data['mobile']
        sms_code = data['sms_code']
        redis_conn = get_redis_connection('verify_codes')
        real_sms_code = redis_conn.get('sms_%s' % mobile)
        if real_sms_code.decode() != sms_code:
            raise serializers.ValidationError('短信验证码错误')

        # 如果用户存在，检查用户密码
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            pass
        else:
            password = data['password']
            if not user.check_password(password):
                raise serializers.ValidationError('密码错误')
            data['user'] = user
        return data

    # def create(self, validated_data):
    #     user = validated_data.get('user')
    #     if not user:
    #         # 用户不存在，创建用户
    #         user = User.objects.create_user(
    #             username=validated_data['mobile'],
    #             password=validated_data['password'],
    #             mobile=validated_data['mobile'],
    #         )

    #     OAuthQQUser.objects.create(
    #         openid=validated_data['openid'],
    #         user=user
    #     )
    #     return user

    def create(self, validated_data):

        openid = validated_data['openid']
        user = validated_data.get('user')
        mobile = validated_data['mobile']
        password = validated_data['password']

        # 判断用户是否存在
        if not user:
            user = User.objects.create_user(username=mobile, mobile=mobile, password=password)

        OAuthQQUser.objects.create(user=user, openid=openid)

        # 签发JWT token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)

        user.token = token

        self.context['view'].user = user

        return user
