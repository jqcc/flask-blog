
from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from . import auth
from ..models import User
from ..email import send_email
from .forms import LoginForm, RegistrationForm, ChangePasswordForm, \
        PasswordResetRequestForm, PasswordResetForm, ChangeEmailForm
from .. import db


'''
flask-login中的login_user()函数 在用户会话中把用户标记为已登录
login_user函数的参数是要登录的用户 已经可选的"记住我"布尔值
如果值为False 那么关闭浏览器后用户会话就过期了 所以下次用户访问时要重新登录
如果值为True  那么会在用户浏览器中写入一个长期有效的cookie 使用这个cookie可以复现用户会话

防止刷新重复发送数据 使用Post/重定向/Get模式 提交登录密令的POST请求也做了重定向
不过目标URL有两种可能 用户访问未授权的URL时会显示登录表单 
flask-login会把原地址保存在查询字符串的next参数中 这个参数可以从request.args字典中读取
如果查询字符串中没有next参数 则重定向到首页 如果用户输入的邮箱和密码不正确 
程序会设定一个flash消息 再次渲染表单 让用户重新登录

'''
# 登录路由
@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('main.index'))
            #return redirect(url_for('main.index'))
        flash('无效的账号或密码.')
    return render_template('auth/login.html', form=form)



'''
flask-login中的logout_user()函数 登出用户 删除并重设用户会话
随后显示一个flash消息 确认本次操作 再重定向到首页 即完成登出
'''
# 登出路由
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('你已退出.')
    return redirect(url_for('main.index'))


# 用户注册路由
@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,
                    username=form.username.data,
                    password=form.password.data)
        db.session.add(user)
        # 原本通过配置 程序已经可以在请求末尾自动提交数据库变化
        # 但这里仍需要调用commit() 因为后面生成令牌需要用到用户id
        # 而只有在提交数据库之后才能赋予新用户id值 所以不能延后提交
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, '确认账号', 'auth/email/confirm', user=user, token=token)
        flash('请到邮箱中确认注册邮件')
        return redirect(url_for('main.index'))
    return render_template('auth/register.html', form=form)

'''
这个函数先检查已登录的用户是否已经确认过 如果已经确认 则重定向到首页 
因为这时不需要任何操作 这样处理可以避免用户不小心多次点击确认令牌带来的额外工作
由于令牌去人完全在User模型中完成 所以视图函数只需要调用confirm()方法即可
然后再根据确认结果显示不同的flash消息 确认成功后 User模型中confirmed属性的值会被修改并添加到会话中
请求处理完后 这两个操作被提交到数据库
'''
# 确认用户的账户
# login_required修饰器会保护这个路由 只有先登录才能执行这个视图函数
@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        flash('您已经验证了注册!')
    else:
        flash('确认链接无效或已过期')
    return redirect(url_for('main.index'))

'''
每个程序都可以决定用户确认账户之前可以做哪些操作 比如 允许未确认的用户登录
但只显示一个页面 这个页面要求用户在获取权限之前先确认账户
这一步可以使用flask提供的before_request钩子完成 对蓝本来说 before_request钩子只能应用到属于蓝本的请求上
若想在蓝本中使用针对程序全局请求的钩子 必须使用before_app_request修饰器

同时满足以下3个条件时 before_app_request处理程序会拦截请求
(1) 用户已登录 (current_user.is_authenticated 为 True)
(2) 用户的账户还未确认
(3) 请求的端点(使用request.endpoint获取)不在认证蓝本中 访问认证路由要获取权限 
    因为这些路由的作用是让用户确认账户或直线其它账户管理操作
如果请求满足以上3个条件 则会被重定向到/auth/unconfirmed路由 显示一个确认账户相关信息的页面

如果before_request或before_app_request的回调返回响应或重定向
flask会直接将其发送至客户端 而不会调用请求的视图函数 因此这些回调可在必要时拦截
'''

@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.ping() # 更新用户最后登录时间
        if not current_user.confirmed \
                and request.endpoint \
                and request.endpoint[:5] != 'auth.' \
                and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html')


# 显示给未确认用户的页面只渲染一个模板 其中有如何确认账户的说明 
# 此外还提供了一个链接 用于请求发送新的确认邮件 以防止之前的邮件丢失 
@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, '确认账号', 'auth/email/confirm', user=current_user, token=token)
    flash('新的验证邮件已发送请去查看')
    return redirect(url_for('main.index'))


# 修改密码
@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # 验证当前密码是否正确
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.new_password.data
            db.session.add(current_user)
            flash('修改密码成功')
            return redirect(url_for('main.index'))
        else:
            flash('当前密码不正确')
    return render_template('auth/change_password.html', form=form)



# 忘记密码
@auth.route('/reset', methods=['GET', 'POST'])
def password_reset_request():
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))

    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, '重设密码', 'auth/email/reset_password', 
                    user=user, token=token, next=request.args.get('next'))
            flash('重设密码邮件已发送,请到邮箱中查看')
            return redirect(url_for('auth.login'))
        else:
            flash('系统中无此邮箱l,请确认后重新填写')
            # 查无此邮箱之后 是否该清空该字段呢？
            form.email.data=""
    return render_template('auth/reset_password.html', form=form)


# 验证账户 重设密码
@auth.route('/reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))

    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            return redirect(url_for('main.index'))
        if user.reset_password(token, form.new_password.data):
            flash('重设密码成功')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html', form=form)
        

# 修改密码
@auth.route('/change-email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        # 验证填写的密码是否正确
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, '修改邮箱地址', 'auth/email/change_email', 
                    user=current_user, token=token)
            flash('修改邮箱地址确认邮件已发送到新邮箱,请前去确认')
            redirect(url_for('main.index'))
        else:
            flash('密码错误')
    return render_template('auth/change_email.html', form=form)
    

@auth.route('/change-email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        flash('你的邮箱更改成功')
    else:
        flash('验证失败')
    return redirect(url_for('main.index'))


