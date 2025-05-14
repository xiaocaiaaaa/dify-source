# webank_custom_development
import os

from flask_restful import Resource, reqparse, fields, marshal, reqparse

from controllers.console.wraps import setup_required
from controllers.inner_api import api
from controllers.inner_api.wraps import inner_api_only
from events.tenant_event import tenant_was_created
from services.account_service import TenantService, AccountService
from libs.helper import TimestampField
from configs import dify_config
from models.account import Account, TenantAccountJoin, TenantAccountRole

workspace_fields = {
    'id': fields.String,
    'name': fields.String,
    'dept_id': fields.String,
    'status': fields.String,
    'created_at': TimestampField
}

class CreateWorkspaceApi(Resource):
    admin_username = os.environ.get("ADMIN_USERNAME", "ADMIN_USERNAME")

    @setup_required
    @inner_api_only
    def post(self):
        # 创建工作空间，使用admin账户作为owner
        parser = reqparse.RequestParser()
        parser.add_argument('dept_id', type=str, required=True, location='json')
        parser.add_argument('dept_full_name', type=str, required=True, location='json')
        args = parser.parse_args()

        tenant = TenantService.get_tenant(args['dept_id'])
        if tenant:
            return {'code': '400', 'message': 'Workspace with this dept_id already exists'}, 200

        account = Account.query.filter_by(name=self.admin_username).first()

        if account is None:
            return {'code': '400', 'message': 'admin user has not setup'}, 200
        else:
            tenant = TenantService.create_tenant(args['dept_full_name'], args['dept_id'], is_from_dashboard=True)
            TenantService.create_tenant_member(tenant, account, role='owner')
            tenant_was_created.send(tenant)

            return {
                'code': '0',
                'message': 'success',
                'data': {
                    'workspace_id': tenant.id
                }
            }, 200

class UpdateWorkspaceApi(Resource):
    @setup_required
    @inner_api_only
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('dept_id', type=str, required=True, location='json')
        parser.add_argument('new_dept_full_name', type=str, required=True, location='json')
        args = parser.parse_args()

        tenant = TenantService.get_tenant(args['dept_id'])
        if not tenant:
            return {'code': '400', 'message': 'Workspace with this name do not exists'}, 200

        tenant.name = args['new_dept_full_name']
        TenantService.update_tenant(tenant)

        return {
            'code': '0',
            'message': 'success',
            'data': {
                'workspace_id': tenant.id
            }

        }, 200

class WorkspaceApi(Resource):
    @setup_required
    @inner_api_only
    def get(self, dept_id):
        tenant = TenantService.get_tenant(dept_id)
        if tenant is None:
            return {
                'code': '404',
                'message': 'workspace not found'
            }, 404
        return {
            'code': '0',
            'message': 'success',
            'data': {
                'workspace': marshal(tenant, workspace_fields)
            }
        }, 200

    @setup_required
    @inner_api_only
    def delete(self, dept_id):
        tenant = TenantService.get_tenant(dept_id)
        if tenant is None:
            return {
                'code': '404',
                'message': 'Workspace not found'
            }, 200
        TenantService.delete_tenant(tenant)
        return {
            'code': '0',
            'message': 'workspace delete success'
        }, 200

class QueryWorkspaceListApi(Resource):
    @setup_required
    @inner_api_only
    def get(self):
        tenants = TenantService.get_all_tenants()
        return {
            'code': '0',
            'message': 'success',
            'data': {
                'workspaceList': marshal(tenants, workspace_fields)}
        }, 200

api.add_resource(CreateWorkspaceApi, '/dev/create/workspace')
api.add_resource(UpdateWorkspaceApi, '/dev/update/workspace')
api.add_resource(WorkspaceApi, '/dev/workspace/<string:dept_id>')
api.add_resource(QueryWorkspaceListApi, '/dev/all-workspaces')