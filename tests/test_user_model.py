import unittest
import time
from datetime import datetime

from app.models import User, AnonymousUser, Role, Permission, Follow
from app import create_app, db


class UserModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # 以test_开头的方法都是要测试的
    def test_password_setter(self):
        # 这里为什么可以用password做初始化参数
        # User的__init__并没有写  难道是父类Model的？
        # /usr/local/lib/python3.5/site-packages/flask_sqlalchemy/Model.py
        u = User(password='cat')
        self.assertTrue(u.password_hash is not None)

    # 测试不能直接操作password属性
    def test_no_password_getter(self):
        u = User(password = 'cat')
        with self.assertRaises(AttributeError):
            u.password

    # 测试密码验证
    def test_password_verification(self):
        u = User(password = 'cat')
        self.assertTrue(u.verify_password('cat'))
        self.assertFalse(u.verify_password('dog'))

    # 测试密码hash是随机
    def test_password_salts_are_random(self):
        u = User(password = 'cat')
        u2 = User(password = 'cat')
        self.assertTrue(u.password_hash != u2.password_hash)

    # 测试更换密码令牌验证
    def test_valid_confirmation_token(self):
        u = User(password='cat')
        db.session.add(u)
        db.session.commit()
        token = u.generate_confirmation_token()
        self.assertTrue(u.confirm(token))

    # 测试更换密码令牌验证
    def test_invalid_confirmation_token(self):
        u1 = User(password='cat')
        u2 = User(password='dog')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        token = u1.generate_confirmation_token()
        self.assertFalse(u2.confirm(token))

    # 测试更换密码令牌失效验证
    def test_expired_confirmation_token(self):
        u = User(password='cat')
        db.session.add(u)
        db.session.commit()
        token = u.generate_confirmation_token(1)
        time.sleep(2)
        self.assertFalse(u.confirm(token))

    # 测试重置密码令牌验证
    def test_valid_reset_token(self):
        u = User(password='cat')
        db.session.add(u)
        db.session.commit()
        token = u.generate_reset_token()
        self.assertTrue(u.reset_password(token, 'dog'))
        self.assertTrue(u.verify_password('dog'))

    # 测试重置密码令牌验证
    def test_invalid_reset_token(self):
        u1 = User(password='cat')
        u2 = User(password='dog')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        token = u1.generate_reset_token()
        self.assertFalse(u2.reset_password(token, 'horse'))
        self.assertTrue(u2.verify_password('dog'))
        
    # 测试更换邮箱令牌验证
    def test_valid_email_change_token(self):
        u = User(email='123@abc.com', password='cat')
        db.session.add(u)
        db.session.commit()
        token = u.generate_email_change_token('234@abc.com')
        self.assertTrue(u.change_email(token))
        self.assertTrue(u.email=='234@abc.com')

    # 测试更换邮箱
    def test_invalid_email_change_token(self):
        u1 = User(email='123@abc.com', password='cat')
        u2 = User(email='234@abc.com', password='dog')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        token = u1.generate_email_change_token('345@abc.com')
        self.assertFalse(u2.change_email(token))
        self.assertTrue(u2.email=='234@abc.com')

    # 测试更换邮箱
    def test_duplicate_email_change_token(self):
        u1 = User(email='123@abc.com', password='cat')
        u2 = User(email='234@abc.com', password='dog')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        token = u2.generate_email_change_token('123@abc.com')
        self.assertFalse(u2.change_email(token))
        self.assertTrue(u2.email == '234@abc.com')

    # 测试用户角色 权限
    def test_roles_and_permissions(self):
        Role.insert_roles()
        u = User(email='123@abc.com', password='cat')
        self.assertTrue(u.can(Permission.WRITE_ARTICLES))
        self.assertFalse(u.can(Permission.MODERATE_COMMENTS))

    # 测试未登录用户
    def test_anonymous_user(self):
        u = AnonymousUser()
        self.assertFalse(u.can(Permission.FOLLOW))
    
    # 测试用户登录时间
    def test_timestamps(self):
        u = User(password='cat')
        db.session.add(u)
        db.session.commit()
        self.assertTrue((datetime.utcnow()-u.member_since).total_seconds() < 3)
        self.assertTrue((datetime.utcnow()-u.last_seen).total_seconds() < 3)

    # 测试更新用户登录时间
    def test_ping(self):
        u = User(password='cat')
        db.session.add(u)
        db.session.commit()
        time.sleep(2)
        last_seen_before = u.last_seen
        u.ping()
        self.assertTrue(u.last_seen > last_seen_before)

    # 测试头像
    def test_gravatar(self):
        u = User(email='john@example.com', password='cat')
        with self.app.test_request_context('/'):
            gravatar = u.gravatar()
            gravatar_256 = u.gravatar(size=256)
            gravatar_pg = u.gravatar(rating='pg')
            gravatar_retro = u.gravatar(default='retro')
        with self.app.test_request_context('/', base_url='https://example.com'):
            gravatar_ssl = u.gravatar()
        self.assertTrue('http://www.gravatar.com/avatar/' +
                    'd4c74594d841139328695756648b6bd6' in gravatar)
        self.assertTrue('s=256' in gravatar_256)
        self.assertTrue('r=pg' in gravatar_pg)
        self.assertTrue('d=retro' in gravatar_retro)
        self.assertTrue('https://secure.gravatar.com/avatar/' +
                    'd4c74594d841139328695756648b6bd6' in gravatar_ssl)
     
    # 测试关注
    def test_follows(self):
        u1 = User(email='123@abc.com', password='cat')
        u2 = User(email='234@abc.com', password='dog')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        self.assertFalse(u1.is_following(u2))
        self.assertFalse(u2.is_followed_by(u1))
        timestamp_before = datetime.utcnow()
        u1.follow(u2)
        db.session.add(u1)
        db.session.commit()
        timestamp_after = datetime.utcnow()
        self.assertTrue(u1.is_following(u2))
        self.assertFalse(u1.is_followed_by(u2))
        self.assertTrue(u2.is_followed_by(u1))
        self.assertTrue(u1.followed.count()==1)
        self.assertTrue(u2.followers.count()==1)
        f = u1.followed.all()[-1]
        self.assertTrue(f.followed == u2)
        self.assertTrue(timestamp_before <= f.timestamp <= timestamp_after)
        f = u2.followers.all()[-1]
        self.assertTrue(f.follower == u1)
        u1.unfollow(u2)
        db.session.add(u1)
        db.session.commit()
        self.assertTrue(u1.followed.count() == 0)
        self.assertTrue(u2.followers.count() == 0)
        self.assertTrue(Follow.query.count() == 0)
        u2.follow(u1)
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        db.session.delete(u2)
        db.session.commit()
        self.assertTrue(Follow.query.count() == 0)

    def test_to_json(self):
        u = User(email='123@abc.com', password='cat')
        db.session.add(u)
        db.session.commit()
        json_user = u.to_json()
        expected_keys = ['url', 'username', 'member_since', 'last_seen',
                         'posts', 'followed_posts', 'post_count']
        self.assertEqual(sorted(json_user.keys()), sorted(expected_keys))
        #self.assertTrue('api/v1.0/users' in json_user['url'])
