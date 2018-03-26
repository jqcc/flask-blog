from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, BooleanField, SelectField
from wtforms import ValidationError
from wtforms.validators import Required, Length, Email, Regexp
from flask_pagedown.fields import PageDownField

from ..models import Role, User

class NameForm(FlaskForm):
    name = StringField('请输入您的名字', validators=[Required()])
    submit = SubmitField('提交')

# 编辑个人信息表单
class EditProfileForm(FlaskForm):
    name = StringField('真实姓名/Real name: ', validators=[Length(0,64)])
    location = StringField('位置/Location: ', validators=[Length(0,64)])
    about_me = TextAreaField('关于我/About me: ')
    submit = SubmitField('提交')

# 编辑个人信息(管理员权限)表单
class EditProfileAdminForm(FlaskForm):
    email = StringField('邮箱/Email', validators=[Required(), Length(1,64), Email()])
    username = StringField('用户名/Username', validators=[Required(), Length(1,64),
            Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0, '用户名必须由数字字母下划线及.组成,且必须以字母开头')])
    confirmed = BooleanField('认证/Confirmed')
    role = SelectField('身份/Role', coerce=int) #<select>标签 必须在choices属性中设置选项值 元组
    name = StringField('真实姓名/Real name', validators=[Length(0,64)])
    location = StringField('位置/Location', validators=[Length(0,64)])
    about_me = TextAreaField('关于我/About me', validators=[Length(0, 64)])
    submit = SubmitField('提交')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        # 各元组都包含两个元素: 选项的标识符 显示在控件中的文本字符串
        # 元组中标识符为角色id 因为是个整数 所以在构造函数中添加corece=int参数 
        # 从而把字段值转换为整数 而不是默认字符串
        self.role.choices = [(role.id, role.name) for role in Role.query.order_by(Role.name).all()]
        self.user = user

    # 验证email和username时 要注意这两个参数是否发生了变化
    def validate_email(self, field):
        if field.data != self.user.email and \
                User.query.filter_by(email=field.data).first():
            raise ValidationError('此邮箱已被注册')

    def validate_username(self, field):
        if field.data != self.user.username and \
                User.query.filter_by(username=field.data).first():
            raise ValidationError('此用户名已被占用')
    
# 博客文章表单
class PostForm(FlaskForm):
    body = PageDownField('写点什么: ', validators=[Required()])
    submit = SubmitField('提交')


# 评论输入表单
class CommentForm(FlaskForm):
    body = StringField('评论', validators=[Required()])
    submit = SubmitField('提交')
