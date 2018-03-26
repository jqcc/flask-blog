
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from wtforms import ValidationError

from ..models import User

'''
PasswordField类表示属性为 type="password"的<input>元素
BooleanField类表示复选框
'''

# 登录表单
class LoginForm(FlaskForm):
    email = StringField('邮箱/Email: ', validators=[Required(), Length(1, 64), Email()])
    password = PasswordField('密码/Password: ', validators=[Required()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')


# 用户注册表单
class RegistrationForm(FlaskForm):
    email = StringField('邮箱/Email: ', validators=[Required(), Length(1, 64), Email()])
    username = StringField('用户名/Username: ', validators=[Required(), Length(1,64),
            Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0, '用户名必须由字符、数字、.或_组成，且必须以字母开头')])
    password = PasswordField('密码/Password: ', validators=[Required()])
    password2 = PasswordField('确认密码: ', validators=[Required(),
            EqualTo('password', message='两次输入密码不一致,请重新输入')])
    submit = SubmitField('注册')

    # 以validate_开头且后面跟着字段名的方法 这个方法就和常规验证函数一起调用
    def validate_email(self, field):
        # 判断数据库中是否已经有这个邮箱
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('该邮箱已被注册.')
    
    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('该用户名已存在.')


# 修改密码表单
class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('当前密码: ', validators=[Required()])
    # 这里如何添加验证函数 保证新密码与当前密码相同
    new_password = PasswordField('新的密码: ', validators=[Required()])
    new_password2 = PasswordField('确认密码: ', validators=[Required(),
            EqualTo('new_password', message='两次输入密码不一致,请重新输入')])
    submit = SubmitField('提交')


# 请求重设密码
class PasswordResetRequestForm(FlaskForm):
    email = StringField('邮箱: ', validators=[Required(), Length(1,64), Email()])
    submit = SubmitField('忘记密码')


# 重设密码
class PasswordResetForm(FlaskForm):
    email = StringField('邮箱: ', validators=[Required(), Length(1,64), Email()])
    new_password = PasswordField('新的密码: ', validators=[Required()])
    new_password2 = PasswordField('确认密码: ', validators=[Required(), 
            EqualTo('new_password', '两次输入密码不一致,请重新输入')])
    Submit = SubmitField('提交')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError('此邮箱不存在,请确认后重新输入')
    

# 修改邮箱
class ChangeEmailForm(FlaskForm):
    email = StringField('邮箱: ', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('密码: ', validators=[Required()])
    submit = SubmitField('修改邮箱地址')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is not None:
            raise ValidationError('此邮箱已被注册,请重新输入')




