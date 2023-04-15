# Faraday Penetration Test IDE
# Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
# See the file 'doc/LICENSE' for the license information
import time
import datetime

import flask
from flask import Blueprint
from flask_classful import route
from marshmallow import fields, post_load, ValidationError

from faraday.server.api.base import AutoSchema, ReadWriteWorkspacedView, PaginatedMixin, PatchableWorkspacedMixin
from faraday.server.models import Command, Workspace
from faraday.server.schemas import MutableField, PrimaryKeyRelatedField, SelfNestedField, MetadataSchema

commandsrun_api = Blueprint('commandsrun_api', __name__)


class CommandSchema(AutoSchema):
    _id = fields.Integer(dump_only=True, attribute='id')
    itime = fields.Method(serialize='get_itime', deserialize='load_itime', required=True, attribute='start_date')
    duration = MutableField(
        fields.Method(serialize='get_duration'),
        fields.Integer(),
        allow_none=True)
    workspace = PrimaryKeyRelatedField('name', dump_only=True)
    creator = PrimaryKeyRelatedField('username', dump_only=True)
    metadata = SelfNestedField(MetadataSchema())

    def load_itime(self, value):
        try:
            return datetime.datetime.fromtimestamp(value)
        except ValueError:
            raise ValidationError('Invalid Itime Value')

    def get_itime(self, obj):
        return time.mktime(obj.start_date.utctimetuple()) * 1000

    def get_duration(self, obj):
        # obj.start_date can't be None
        if obj.end_date:
            return (obj.end_date - obj.start_date).seconds + ((obj.end_date - obj.start_date).microseconds / 1000000.0)
        else:
            if (datetime.datetime.now() - obj.start_date).total_seconds() > 86400:# 86400 is 1d TODO BY CONFIG
                return 'Timeout'
            return 'In progress'

    @post_load
    def post_load_set_end_date_with_duration(self, data, **kwargs):
        # there is a potential bug when updating, the start_date can be changed.
        duration = data.pop('duration', None)
        if duration:
            data['end_date'] = data['start_date'] + datetime.timedelta(
                seconds=duration)
        return data

    class Meta:
        model = Command
        fields = ('_id', 'command', 'duration', 'itime', 'ip', 'hostname',
                  'params', 'user', 'creator', 'workspace', 'tool', 'import_source', 'metadata')


class CommandView(PaginatedMixin, ReadWriteWorkspacedView):
    route_base = 'commands'
    model_class = Command
    schema_class = CommandSchema
    get_joinedloads = [Command.workspace]
    order_field = Command.start_date.desc()

    def _envelope_list(self, objects, pagination_metadata=None):
        commands = []
        for command in objects:
            commands.append({
                'id': command['_id'],
                'key': command['_id'],
                'value': command
            })
        return {
            'commands': commands,
        }

    @route('/activity_feed/')
    def activity_feed(self, workspace_name):
        """
        ---
          tags: ["Command"]
          description: Gets a summary of the lastest executed commands
          responses:
            200:
              description: Ok
              content:
                application/json:
                  schema: CommandSchema
        """
        res = []
        query = Command.query.join(Workspace).filter_by(name=workspace_name)
        for command in query.all():
            res.append({
                '_id': command.id,
                'user': command.user,
                'import_source': command.import_source,
                'command': command.command,
                'tool': command.tool,
                'params': command.params,
                'vulnerabilities_count': (command.sum_created_vulnerabilities or 0),
                'hosts_count': command.sum_created_hosts or 0,
                'services_count': command.sum_created_services or 0,
                'criticalIssue': command.sum_created_vulnerability_critical or 0,
                'date': time.mktime(command.start_date.timetuple()) * 1000,
            })
        return res

    @route('/last/', methods=['GET'])
    def last_command(self, workspace_name):
        """
        ---
          tags: ["Command"]
          description: Gets the last executed command
          responses:
            200:
               description: Last executed command or an empty json
        """
        command = Command.query.join(Workspace).filter_by(name=workspace_name).order_by(Command.start_date.desc()).first()
        command_obj = {}
        if command:
            command_obj = {
                '_id': command.id,
                'user': command.user,
                'import_source': command.import_source,
                'command': command.command,
                'tool': command.tool,
                'params': command.params,
                'vulnerabilities_count': (command.sum_created_vulnerabilities or 0),
                'hosts_count': command.sum_created_hosts or 0,
                'services_count': command.sum_created_services or 0,
                'criticalIssue': command.sum_created_vulnerability_critical or 0,
                'date': time.mktime(command.start_date.timetuple()) * 1000,
            }
        return flask.jsonify(command_obj)


class CommandV3View(CommandView, PatchableWorkspacedMixin):
    route_prefix = '/v3/ws/<workspace_name>/'
    trailing_slash = False

    @route('/activity_feed')
    def activity_feed(self, workspace_name):
        return super().activity_feed(workspace_name)

    @route('/last', methods=['GET'])
    def last_command(self, workspace_name):
        return super().last_command(workspace_name)

    activity_feed.__doc__ = CommandView.activity_feed.__doc__
    last_command.__doc__ = CommandView.last_command.__doc__


CommandView.register(commandsrun_api)
CommandV3View.register(commandsrun_api)
