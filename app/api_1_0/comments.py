from flask import request, current_app, url_for, jsonify, g

from . import api
from ..models import Comment, Post, Permission
from .. import db
from .decorators import permission_required


@api.route('/comments/')
def get_comments():
    page = request.args_get('page', 1, type=int)
    pagination = Comment.query.order_by(Comments.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'], error_out=False)
    comments = pagination.items
    prevPage = None
    if pagination.has_prev:
        pervPage = url_for('api.get_comments', page=page-1, _external=True)
    nextPage = None
    if pagination.has_next:
        nextPage = url_for('api.get_comments', page=page+1, _external=False)
    return jsonify({'comments': [comment.to_json() for comment in comments],
                    'prev': prevPage,
                    'next': nextPage,
                    'count': pagination.total})
 
@api.route('/comments/<int:id>')
def get_comment(id):
    comment = Comment.query.get_or_404(id)
    return jsonify(comment.to_json())

@api.route('/posts/<int:id>/comments')
def get_post_comments(id):
    post = Post.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
            page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'], error_out=False)
    comments = paginate.items
    prevPage = None
    if paginate.has_prev:
        prevPage = url_for('api.get_post_comments', id=id, page=page-1, _external=True)
    nextPage = None
    if paginate.has_next:
        nextPage = url_for('api.get_post_comments', id=id, page=page+1, _external=True)
    return jsonify({'comments': [comment.to_json() for comment in comments],
                    'prev': prevPage,
                    'next': nextPage,
                    'count': paginate.total})

@api.route('/posts/<int:id>/comments/', methods=['POST'])
@permission_required(Permission.COMMENT)
def new_post_comment(id):
    post = Post.query.get_or_404(id)
    comment = Comment.from_json(request.json)
    comment.author = g.current_user
    comment.post = post
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_json()), 201, {'Location': url_for('api.get_comment', id=comment.id, _external=True)}
