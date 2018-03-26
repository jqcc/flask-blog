
from . import api

@api.route('/users/<int:id>')
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify(user.to_json())

@api.route('/users/<int:id>/posts/')
def get_user_posts(id):
    user = User.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items
    prevPage = None
    if pagination.has_prev:
        prevPage = url_for('api.get_user_posts', id=id, page=page-1, _external=True)
    nextPage = None
    if pagination.has_next:
        nextPage = url_for('api.get_user_posts', id=id, page=page+1, _external=True)
    return jsonify({'posts': [post.to_json for post in posts],
                    'prev': prevPage,
                    'next': nextPage,
                    'count': pagination.total})

@api.route('/users/<int:id>/timeline')
def get_user_followed_posts(id):
    user = User.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    pagination = user.followed_posts.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items
    prevPage = None
    if pagination.has_prev:
        prevPage = url_for('api.get_user_followed_posts', id=id, page=page-1, _external=True)
    nextPage = None
    if pagination.has_next:
        nextPage = url_for('api.get_user_followed_posts', id=id, page=page+1, _external=True)
    return jsonify({'posts': [post.to_json for post in posts],
                    'prev': prevPage,
                    'next': nextPage,
                    'count': pagination.total})
