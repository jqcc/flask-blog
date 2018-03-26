from flask import g, jsonify
from flask_httpauth import HTTPBasicAuth

from ..models import User, AnonymousUser
from . import api
from .errors import unauthorized, forbidden

auth = HTTPBasicAuth()

# 第一个参数为邮箱或认证令牌
# 在这种实现方式中 基于令牌的认证是可选的 由客户端决定是否使用
# 为了让视图函数能区分这两种认证方法 添加了g.token_used变量
@auth.verify_password
def verify_password(email_or_token, password):
    # 如果第一个参数为空 则假定为匿名用户
    if email_or_token == '':
        # g为Flask全局对象
        g.current_user = AnonymousUser()
        return True
    # 如果密码为空 则假定第一个参数提供的是令牌 按照令牌的方式进行认证
    if password == '':
        g.current_user = User.verify_auth_token(email_or_token)
        g.token_used = True
        return g.current_user is not None
    # 如果两个参数都不为空 则假定使用常规的邮件地址和密码进行认证
    user = User.query.filter_by(email = email_or_token).first()
    if not user:
        return False
    g.current_user = user
    g.token_used = False
    return user.verify_password(password)

# 如果认证密令不正确 服务器向客户端返回401错误
# 默认情况下 Flask-HTTPAuth 自动生成这个状态码
# 但为了和API返回的其它错误一致 这里采用自定义这个错误
@auth.error_handler
def auth_error():
    return unauthorized('Invalid credentials')


# 在before_request处理程序中使用一次login_required修饰器 应用到整个蓝本
# 这样API蓝本中的所有路由都能进行自动认证 而且作为附加认证 before_request
# 处理程序还会拒绝已通过认证但没有确认账户的用户
@api.before_request
@auth.login_required
def before_request():
    if not g.current_user.is_anonymous and not g.current_user.confirmed:
        return forbidden('Unconfirmed account')


# 由于这个路由也在蓝本中 所以添加到before_request处理程序上的认证机制也会用在这个路由上
# 为了避免客户端使用旧令牌申请新令牌 要在视图函数中检查g.token_used变量的值
# 如果使用令牌进行认证就拒绝请求 这个视图函数返回json格式的响应 其中包含了过期时间为1个小时的令牌
@api.route('/token')
def get_token():
    if g.current_user.is_anonymous or g.token_used:
        return unauthorized('Invalid credentials')
    return jsonify({'token': g.current_user.generate_auth_token(
            expiration=3600), 'expiration': 3600})

