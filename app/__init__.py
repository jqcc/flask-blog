from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from flask_mail import Mail
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_pagedown import PageDown

from config import config

bootstrap = Bootstrap()
mail = Mail()
moment = Moment()
db = SQLAlchemy()
pagedown = PageDown()


login_manager = LoginManager()
# 此值可以为 None 'basic' 'strong' 以提供不同安全等级防止用户会话遭篡改
# 设置为strong时会记录客户端ip 和浏览器用户代理信息 发现异动就登出用户
login_manager.session_protection = 'strong'
# 设置登录页面的端点 要加上蓝本的名字
login_manager.login_view = 'auth.login'

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    bootstrap.init_app(app)
    mail.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    pagedown.init_app(app)

    # 这里一创建数据库就会报错
    #db.create_all()

    # 附加路由和自定义的错误页面
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # 认证蓝本 url_prefix是可选参数 加上之后 所有路由都会加上这个指定前缀
    # 比如 /login路由会被注册成 /auth/login
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .api_1_0 import api as api_1_0_blueprint
    app.register_blueprint(api_1_0_blueprint, url_prefix='/api/v1.0')

    return app


