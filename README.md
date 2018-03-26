# flasky-blog

## 环境要求

+ python

+ flask

+ smtp服务

## 使用

### 环境安装

1. [安装python3](https://www.python.org/downloads/)

2. clone code，安装依赖

    sudo pip3 install -r requirments/dev.txt

### 运行程序

#### 准备

第一次运行程序时 需在命令行模式下创建数据库 将用户角色写入数据库中

``` bash
    $ python3 manage shell  # 进入命令行模式
    $ db.create_all()       # 创建数据库
    $ Role.insert_roles()   # 插入角色
```

#### 运行

``` bash
    # 直接运行程序:
    python3 manage.py runserver #查看 http://127.0.0.1:5000/
    # 指定程序端口:
    python3 manage.py runserver --port xx #查看 http://127.0.0.1:xx/
    # 指定公网ip：
    python3 manage.py runserver --host 0.0.0.0 #查看 http://a.b.c.d:5000/ a.b.c.d是服务器所在的公网ip

    # 运行单元测试
    python3 manage.py test
```

### 更新依赖

记录依赖包及其版本号(安装或升级后最好更新这个文件):
    `pip3 freeze > requirments.txt`

### api服务

Web REST架构 api服务:
1. `http --json --auth 123@abc.com:123 GET http://127.0.0.1:5000/api/v1.0/posts/`    获取所有文章json格式
2. `http --json --auth : GET http://127.0.0.1:5000/api/v1.0/posts/`                  匿名访问
3. `http --json --auth 123@abc.com:123 GET http://127.0.0.1:5000/api/v1.0/token`     获取当前用户认证token
4. `http --json --auth token: GET http://127.0.0.1:5000/api/v1.0/posts/`             使用上一步获取的token访问

### 数据库服务

数据库相关操作(命令行模式下):
1. 进入命令行: `python3 manage.py shell`
2. 创建数据库: `db.create_all()`                               若数据库已存在则不会产生任何操作
3. 删除数据库: `db.drop_all()`                                 删除已存在的数据库
4. 查找所有行: `tablename.query.all()`                         tablename为具体表名
5. 按条件查找: `tablename.query.filter_by(attr=val)`           查找tablename表中属性attr值为val的值
6. 按条件查找: `tablename.query.filter_by(attr=val).first()`   直接查找是列表 first()取出第一个
7. 将变动添加: `db.session.add(obj)`                           类似git的add
8. 将变动提交: `db.session.commit()`                           类似git的commit 但不需要-m 指定
9. 回滚操作: `db.session.rollback()`                         回滚
10. 数据库迁移:
    + (1)创建迁移仓库: `python3 manage.py db init`              只需第一次创建迁移仓库时调用
    + (2)创建迁移脚本: `python3 manage.py db migrate -m ""`     每次数据库变动迁移时调用 -m 指定信息
    + (3)开始执行迁移: `python3 manage.py db upgrade`           迁移

### 环境变量设置

需设置的环境变量:\
(必选):
>MAIL\_USERNAME: smtp服务器账号\
>MAIL\_PASSOWRD: smtp服务器密码\
>FLASKY\_ADMIN: 管理员邮箱(注册时自动成为管理员, 也可以通过shell设置role)\

(可选):
>SECRET\_KEY: 加密字符串\
>DEV\_DATABASE\_URL: 开发环境数据库位置\
>TEST\_DATABASE\_URL: 测试环境数据库位置\
>DATABASE\_URL: 发布环境数据库位置

### 程序相关操作

u 为要操作的User对象
数据库相关操作需要将变动添加提交才能起效  或等程序运行结束SQLAlchemy会自动添加 下次运行即可起效
1. 查找指定用户: `u = User.query.filter_by(email=email).first()` 此处使用email查找可以换为username等
2. 设置用户为已认证: `u.confirmed = True`
3. 设置用户管理员权限: `u.role = Role.query.filter_by(name='Administrator').first()`
4. 添加大量用户: `User.generate_fake(100)` # 生成100个用户
5. 添加大量文章: `Post.generate_fake(100)` # 生成100篇文章
6. 所有人关注自己: `User.all_add_self_follows()`
7. 自己关注自己: `u.add_self_follows()`
8. 指定人关注自己: `User.add_user_self_follows(username)`
