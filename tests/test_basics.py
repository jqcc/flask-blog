import unittest
from flask import current_app
from app import create_app, db

class BasicsTestCase(unittest.TestCase):
    # 在测试前被执行 创建测试环境
    # 创建程序 激活上下文 创建数据库
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    # 测试后执行 删除资源
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        self.assertFalse(current_app is None)

    def test_app_is_testing(self):
        self.assertTrue(current_app.config['TESTING'])
