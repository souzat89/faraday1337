# Faraday Penetration Test IDE
# Copyright (C) 2017  Infobyte LLC (http://www.infobytesec.com/)
# See the file 'doc/LICENSE' for the license information
from flask import abort, Blueprint
from marshmallow import fields, ValidationError
from marshmallow.validate import OneOf


from faraday.server.models import db, Host, Service, VulnerabilityGeneric
from faraday.server.api.base import (
    AutoSchema,
    ReadWriteWorkspacedView,
    InvalidUsage, CreateWorkspacedMixin, GenericWorkspacedView, PatchableWorkspacedMixin)
from faraday.server.models import Comment
comment_api = Blueprint('comment_api', __name__)


class CommentSchema(AutoSchema):
    _id = fields.Integer(dump_only=True, attribute='id')
    object_id = fields.Integer(attribute='object_id', required=True)
    object_type = fields.String(attribute='object_type',
                                validate=OneOf(['host', 'service', 'comment', 'vulnerability']),
                                required=True)
    text = fields.String(attribute='text', required=True)

    class Meta:
        model = Comment
        fields = (
            'id', 'text', 'object_type', 'object_id'
        )


class CommentCreateMixing(CreateWorkspacedMixin):

    def _perform_create(self, data, workspace_name):
        model = {
            'host': Host,
            'service': Service,
            'vulnerability': VulnerabilityGeneric,
            'comment': Comment
        }
        obj = db.session.query(model[data['object_type']]).get(
            data['object_id'])
        workspace = self._get_workspace(workspace_name)
        if not obj:
            raise InvalidUsage('Can\'t comment inexistent object')
        if obj.workspace != workspace:
            raise InvalidUsage('Can\'t comment object of another workspace')
        return super()._perform_create(data, workspace_name)


class CommentView(CommentCreateMixing, ReadWriteWorkspacedView):
    route_base = 'comment'
    model_class = Comment
    schema_class = CommentSchema
    order_field = 'create_date'


class UniqueCommentView(GenericWorkspacedView, CommentCreateMixing):
    """
        This view is used by the plugin engine to avoid duplicate comments
        when the same plugin and data was ran multiple times.
    """
    route_base = 'comment_unique'
    model_class = Comment
    schema_class = CommentSchema

    def _perform_create(self, data, workspace_name):
        comment = db.session.query(Comment).filter_by(
            text=data['text'],
            object_type=data['object_type'],
            object_id=data['object_id'],
            workspace=self._get_workspace(workspace_name)
        ).first()

        if comment is not None:
            abort(409, ValidationError(
                {
                    'message': 'Comment already exists',
                    'object': self.schema_class().dump(comment),
                }
            ))
        res = super()._perform_create(data, workspace_name)
        return res


class CommentV3View(CommentView, PatchableWorkspacedMixin):
    route_prefix = '/v3/ws/<workspace_name>/'
    trailing_slash = False


class UniqueCommentV3View(UniqueCommentView, PatchableWorkspacedMixin):
    route_prefix = '/v3/ws/<workspace_name>/'
    trailing_slash = False


CommentView.register(comment_api)
UniqueCommentView.register(comment_api)
CommentV3View.register(comment_api)
UniqueCommentV3View.register(comment_api)
