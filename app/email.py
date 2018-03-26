from threading import Thread

from flask import current_app, render_template
from flask_mail import Message

from . import mail

# 在实际项目中如果哟啊发送大量电子邮件时 使用专门发送电子邮件的作业比给每份邮件创建一个线程合适
# 例如把直线send_async_email()函数的操作发给Celery(http://www.celeryproject.org/)任务队列
# 异步发送电子邮件
def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

# 发送邮件 参数: [收件人地址], '主题', 渲染正文模板, {关键字参数列表}
# 指定模板时不佳扩展名 这样才能使用两个模板分别渲染纯文本正文和富文本正文
# 调用者将关键字参数传给render_template()函数 以便在模板中使用 进而生成电子邮件正文
def send_email(to, subject, template, **kwargs):
    app = current_app._get_current_object()
    msg = Message(app.config['FLASKY_MAIL_SUBJECT_PREFIX']+subject, 
                sender=app.config['FLASKY_MAIL_SENDER'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    # 原:同步发送 在发送邮件时会停滞几秒钟 为避免处理请求过程中不必要的延迟 采用异步发送
    # 将发送电子邮件的函数移到后台线程中
    #mail.send(msg)
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr
