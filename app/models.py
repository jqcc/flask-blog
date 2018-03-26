# 数据库对象模型
import hashlib
from datetime import datetime

from flask_login import UserMixin, AnonymousUserMixin 
from flask import current_app, request, jsonify, url_for
# 根据密码散列
from werkzeug.security import generate_password_hash, check_password_hash
# 生成令牌
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from markdown import markdown
import bleach

from . import db, login_manager
from .exceptions import ValidationError


'''
程序权限:
  操作           位 值              说明
关注用户    0b00000001(0x01)    关注其他用户
发表评论    0b00000010(0x02)    在他人撰写的文章下发表评论
撰写文章    0b00000100(0x04)    写原创文章
管理评论    0b00001000(0x08)    查处他人发表的不当评论
 管理员     0b10000000(0x80)    管理网站

用户角色:       
用户角色         权 限              说明
  匿名      0b00000000(0x00)    未登录的用户 在程序中只有阅读权限
  用户      0b00000111(0x07)    具有发布文章 发表评论和关注其他用户的权限 这是新用户的默认角色
 协管员     0b00001111(0x0f)    增加审查不当评论的权限
 管理员     0b11111111(0xff)    具有所有权限 包括修改其他用户所属角色的权限
'''
class Permission:
    FOLLOW = 0x01
    COMMENT = 0x02
    WRITE_ARTICLES = 0x04
    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    # 只有一个角色的default字段要设置为True 其他都设为False 用户注册时 其角色会被设置为默认角色
    default = db.Column(db.Boolean, default=False, index=True)
    # 整形 采用位于的方式决定用户权限
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    # 在数据库中创建角色  若想把角色写入数据库 需在shell中调用一次
    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.FOLLOW | 
                     Permission.COMMENT |
                     Permission.WRITE_ARTICLES, True),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.MODERATE_COMMENTS, False),
            'Administrator': (0xff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


# 关注关系模型
class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)



'''
想要使用flask-login扩展 程序的User模型必须实现几个功能：
(原书中注明是方法 但经测试前三个均为bool变量 最后一个为函数)

is_authenticated    如果已登录 则为True 否则为False
is_active           如果允许登录 则为True 否则为False 如果要禁用账号可以设置为False
is_anonymous        对普通用户必须为False
get_id()            必须返回用户的唯一标识符 用unicode编码字符串

这四个方法可模型类中作为方法直接实现 不过还有一种更简单的替代方案
flask-login提供了一个UserMixin类 其中包含这些方法的默认实现
'''

# flask-login要求程序实现一个回调函数 使用指定的 加载用户
# 加载用户的回调函数接收以unicode字符串形式表示的用户标识符
# 如果能找到用户 这个函数必须返回用户对象 否则返回None
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True) # int 主键
    email = db.Column(db.String(64), unique=True, index=True) # str(64) 唯一 建立索引
    username = db.Column(db.String(64), unique=True, index=True) # str(64) 唯一 建立索引
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))  # int 外键
    password_hash = db.Column(db.String(128))# 密码
    confirmed = db.Column(db.Boolean, default=False)# 校验
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text()) # 与str的区别是不需要指定最大长度
    member_since = db.Column(db.DateTime(), default=datetime.utcnow) # 注册日期
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow) # 最后登录日期
    avatar_hash = db.Column(db.String(32)) # 邮件对应头像hash 缓存到成员变量中减少计算量
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    followed = db.relationship('Follow', foreign_keys=[Follow.follower_id], 
            backref=db.backref('follower', lazy='joined'), lazy='dynamic', cascade='all, delete-orphan')
    followers = db.relationship('Follow', foreign_keys=[Follow.followed_id],
            backref=db.backref('followed', lazy='joined'), lazy='dynamic', cascade='all, delete-orphan')
    follow_self = db.Column(db.Boolean, default=False)# 关注自己
    comments = db.relationship('Comment', backref='author', lazy='dynamic')

    # 动态绑定属性: role password(property属性) followed_posts(property属性)


    # 管理员由保存在环境变量中的FLASKY_ADMIN中的电子邮件地址识别
    # 只要这个电子邮件地址出现在注册请求中 就会被赋予管理员角色
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        # 动态绑定role属性
        if self.role is None:
            if self.email == current_app.config['FLASKY_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        # 缓存邮件对应头像hash 减少计算量
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(self.email.encode('utf-8')).hexdigest()
        
        # 用户创建时自动关注自己
        # 注意 如果启用了此功能 需修改单元测试 关注测试
        #self.followed.append(Follow(followed=self))

    def __repr__(self):
        return '<User %r>' % self.username

    # 将函数变成对象字段属性
    # 只写
    @property
    def password(self):
        raise AttributeError('password is not readable attribute')

    # 修改
    @password.setter
    def password(self, password):
        # 根据密码生成hash值
        self.password_hash = generate_password_hash(password)

    # 根据密码和数据库中存储的散列值匹配 密码正确返回True
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


    '''
    验证邮箱功能 注册后不立即激活账户 而是设置为待确定状态
    发送一封确认邮件  点击邮件中 包含确认令牌的特殊url链接
    处理这个路由的视图函数收到令牌确认用户id(数据库分配)
    根据这个id将用户状态设置为已确认
    一般不直接把id直接放在连接中这样不安全 
    而是把id换成将相同信息安全加密后得到的令牌
    下面使用itsdangerous包生成包含用户id的安全令牌
    使用其中的TimedJSONWebSignatureSerializer类生成具有过期时间的JSON Web 签名
    '''
    def generate_confirmation_token(self, expiration=3600):
        # 参数: 密钥 令牌过期时间(s)
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        # dumps()方法为指定的数据生成一个加密前面 然后再对数据和签名进行序列化 生成令牌字符串
        return s.dumps({'confirm':self.id})

    # 验证令牌
    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            # 为了解码令牌 序列化对象提供了loads()方法 其唯一参数是令牌字符串
            # 这个方法会检验签名和过期时间 如果通过返回原始数据
            # 如果令牌不正确或者过期了 会抛出异常
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True


    # 生成重置密码的令牌    
    def generate_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset':self.id})

    # 重置密码
    def reset_password(self, token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        return True

    # 生成更换邮箱的令牌
    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email':self.id, 'new_email':new_email})

    # 更换邮箱
    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_hash = hashlib.md5(self.email.encode('utf-8')).hexdigest()
        db.session.add(self)
        return True
    
    # 生成验证令牌
    def generate_auth_token(self, expiration):
        s = Serializer(current_app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'id': self.id}).decode('ascii')

    # 设置为静态方法 因为在解码之前 不知道是对象是谁
    # 所以没有调用函数的对象  所以设置为静态方法
    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])


    # 判断用户权限
    def can(self, permissions):
        return self.role is not None and \
                (self.role.permissions & permissions) == permissions

    # 是否为管理员权限
    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    # 更新用户最后登录时间
    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    '''
    Gravatar头像服务 把头像和电子邮件关联起来
    要生成头像的url时要计算电子邮件的MD5散列值:
    import hashlib
    hash = hashlib.md5(email.encode('utf-8')).hexdigest()
    生成的头像url是在http://www.gravatar.com/avatar或https://secure.gravatar.com/avatar
    之后加上这个MD5散列值 如果这个电子邮件没有对应头像则会显示一个默认图片
    头像url的查询字符串中可以包含多个参数以配置头像图片的特征
    s   图片大小 单位为像素
    r   图像级别 可选值有"g", "pg", "r"和 "x"
    d   没有注册Gravatar服务的用户使用的默认图片生成方式 可选值有 404 返回404错误
        默认图片的url 图片生成器"mm", "identicon", "monsterid", "wavatar", "retro"或 "blank"之一
    fd  强制使用默认图片
    '''
    # 生成用户头像
    # 由于这是一项CPU密集型操作 如果在某个页面生成大量头像 计算量会非常大
    # 由于邮件对应的MD5散列值是不变的 故将其缓存在User模型中 成员属性avatar_hash
    # 若该变量不为None 则无需计算 直接返回
    def gravatar(self, size=100, default='identicon', rating='g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(self.email.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
                url=url,hash=hash,size=size,default=default,rating=rating)

    # 生成虚拟用户
    @staticmethod
    def generate_fake(count=100):
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py

        seed()
        for i in range(count):
            u = User(email=forgery_py.internet.email_address(),
                    username=forgery_py.internet.user_name(True),
                    confirmed=True,
                    name=forgery_py.name.full_name(),
                    location=forgery_py.lorem_ipsum.sentence(),
                    member_since=forgery_py.date.date(True))
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                
    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower=self, followed=user)
            db.session.add(f)

    def unfollow(self, user):
        f = self.followed.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)

    def is_following(self, user):
        return self.followed.filter_by(followed_id=user.id).first() is not None

    def is_followed_by(self, user):
        return self.followers.filter_by(follower_id=user.id).first() is not None

    # 让所有用户都关注自己
    @staticmethod
    def all_add_self_follows():
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)
                user.follow_self = True
                db.session.add(user)
                db.session.commit()
    
    # 指定某个用户关注自己
    @staticmethod
    def add_user_self_follows(username):
        u = User.query.filter_by(username=username).first()
        if u.is_following(u):
            print("该用户已关注自己")
            return True
        if u is not None:
            u.follow(u)
            u.follow_self = True
            db.session.add(u)
            db.session.commit()
            return True
        else:
            print("系统中无此用户")
            return False

    # 自己关注自己
    def add_self_follows(self):
        if not self.is_following(self):
            self.follow(self)
            self.follow_self = True
            db.session.add(self)
            db.session.commit()
            return True
        return Flase
   

    ###                        ###
    #                            #
    #   同理可以写三个取关操作   #
    #                            #
    ###                        ###


    # 把用户转换成json格式的序列化字典
    def to_json(self):
        json_user = {
            'url' : url_for('api.get_post', id=self.id, _externam=True),
            'username': self.username,
            'member_since': self.member_since,
            'last_seen': self.last_seen,
            'posts': url_for('api.get_user_posts', id=self.id, _external=True),
            'followed_posts': url_for('api.get_user_followed_posts', id=self.id, _external=True),
            'post_count': self.posts.count()
        }
        return json_user


    @property
    def followed_posts(self):
        return Post.query.join(Follow, Follow.followed_id == Post.author_id)\
                .filter(Follow.follower_id == self.id)



# 未登录用户
class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False


login_manager.anonymous_user = AnonymousUser




# 文章模型
# 博客文章包含正文 时间戳 以及和User模型之间的一对多关系 
# body字段的定义类型是db.Text 所以不限制长度
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text) # 缓存markdown格式的文章转换成html后的代码
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comments = db.relationship('Comment', backref='post', lazy='dynamic')

    # 生成博客文章
    @staticmethod
    def generate_fake(count=100):
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count-1)).first()
            p = Post(body=forgery_py.lorem_ipsum.sentences(randint(1,3)),
                    timestamp=forgery_py.date.date(True), author=u)
            db.session.add(p)
            db.session.commit()

    # 把文章转换成json格式的序列化字典
    def to_json(self):
        json_post = {
            'url': url_for('api.get_post', id=self.id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id, _external=True),
            'comments': url_for('api.get_post_comments', id=self.id, _external=True),
            'comment_count': self.comments.count()
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post does not have a body')
        return Post(body=body)
    
    
    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'addr', 'acronym', 'b', 'blockquote', 'code', 'em', 
                'i', 'li', 'ol', 'pre', 'strong', 'ul', 'h1', 'h2', 'h3', 'p' ]
        # 转换过程分三步: 首先markdown()函数初步把markdown文本转换成HTML
        # 然后把得到的结果和允许使用的HTML标签列表传给clean()函数
        # clean()函数删去所有不在白名单上的标签
        # 最后由linkify()函数将重文本中的URL转换成适当的<a>标签 这个函数由Bleach提供
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format='html'), 
                tags=allowed_tags, strip=True))

# on_changed_body函数注册set事件监听程序在body字段上
# 只要这个类的实例的body字段设置了新值 函数就会自动调用
# on_changed_body函数把body字段中的文本渲染成HTML格式 结果保存在body_html中
db.event.listen(Post.body, 'set', Post.on_changed_body)



class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))

    def to_json(self):
        json_comment = {
            'url' : url_for('api.get_comment', id=self.id, _external=True),
            'post' : url_for('api.get_post', id=self.post_id, _external=True),
            'body' : self.body,
            'body_html' : self.body_html,
            'timestamp' : self.timestamp,
            'author': url_for('api.get_user', id=self.author_id, _external=True)
        }
        return json_comment

    @staticmethod
    def from_json(json_comment):
        body = json_comment.get('body')
        if body is None or body == '':
            raise ValidationError('comment does not have a body')
        return Comment(body=body)

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i', 'strong']
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format='html'),
                tags=allowed_tags, strip=True))

db.event.listen(Comment.body, 'set', Comment.on_changed_body)
