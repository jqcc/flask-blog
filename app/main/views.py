from datetime import datetime
from flask import render_template, redirect, url_for, abort, make_response
from flask import session, flash, request, current_app
from flask_login import login_required, current_user

from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, CommentForm
from .. import db
from ..models import Permission, User, Post, Comment
from ..email import send_email
from ..decorators import admin_required, permission_required

@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        # current_user由flask-login提供 上下文变量 通过线程内的代理对象实现
        # 这个对象表现类似用户对象 但实际上是一个轻度包装 包含真正的用户对象
        # 数据库需要真正的用户对象 因此要调用_get_current_object()方法
        post = Post(body=form.body.data, author=current_user._get_current_object())
        db.session.add(post)
        return redirect(url_for('.index'))
    # 渲染的页数从请求的查询字符串中获取 如果没有明确指定则渲染第一页
    # type=int 保证参数无法转换成整数时 返回默认值
    page = request.args.get('page', 1, type=int)
    
    show_pages = 0
    if current_user.is_authenticated:
        show_pages = int(request.cookies.get('show_pages', '0'))
    # 显示关注用户的文章
    if show_pages == 1:
        query = current_user.followed_posts
    elif show_pages == 0:
        query = Post.query
    elif show_pages == 2:
        query = current_user.posts
    

    # 要显示某页中的记录 要把all换成()换成Flask-SQLAlchemy提供的paginate()方法
    # 页数是第一个参数 也是唯一必须的参数 可选参数per_page用来指定每页显示的记录数 如果没有指定就默认20
    # 另一个可选参数error_out当设置为True(默认)时 如果请求页数超过了范围 会返回404
    # 如果设置为False 页面超出时会返回一个空列表
    # 若想要查看第2页的文章 要在浏览器地址栏中的URL后加上查询字符串 ?page=2`
    pagination = query.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'], error_out=False)
    # posts = Post.query.order_by(Post.timestamp.desc()).all()
    posts = pagination.items
    return render_template('index.html', form=form, posts=posts, 
            show_pages=show_pages, pagination=pagination)
    

# 资料页面
@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        about(404)
    # 可以简写为
    # user = User.query.filter_by(username=username).first_or_404()
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    return render_template('user.html', user=user, posts=posts)

# 修改个人信息
@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('信息修改成功')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


# 管理员的资料编辑路由
@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    # 如果id不正确会返回404错误
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('信息修改成功')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


# 每篇文章一个对应连接 使用文章在数据库中的id
@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data, post=post, author=current_user._get_current_object())
        db.session.add(comment)
        flash('评论成功')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count()-1) // current_app.config['FLASKY_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(page, 
            per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'], error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form, comments=comments, pagination=pagination)


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('保存成功')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('不存在此用户')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('你已经关注了此用户，无须再次关注')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash('你成功关注了用户 %s.'%username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('不存在此用户')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('你没有关注此用户,无法取消关注')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash('你已成功取消关注用户 %s.'%username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('不存在此用户')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'], error_out=False)
    follows = [{'user':item.follower, 'timestamp':item.timestamp} for item in pagination.items]
    return render_template('followers.html', user=user, title='Followers of', endpoint='.followers',
            pagination=pagination, follows=follows)

@main.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('不存在此用户')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'], error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp} for item in pagination.items]
    return render_template('followers.html', user=user, title='Followed by', endpoint='.followed_by',
            pagination=pagination, follows=follows)


# cookie只能在响应对象中设置 因此这两个路由不能依赖Flask
# 要使用make_response()方法创建响应对象
@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    # set_cookie函数的前两个参数分别是cookie名和值 可选参数max_age参数设置cookie的过期时间 单位为秒
    # 如果不指定max_age 浏览器关闭后cookie就会过期
    resp.set_cookie('show_pages', '0', max_age=30*24*60*60)
    return resp

@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_pages', '1', max_age=30*24*60*60)
    return resp


@main.route('/myself')
@login_required
def show_myself():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_pages', '2', max_age=30*24*60*60)
    return resp


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(page,
            per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'], error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments, pagination=pagination, page=page)


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    return redirect(url_for('.moderate', page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('.moderate', page=request.args.get('page', 1, type=int)))
