# webank_custom_development
import hashlib
import json
import logging
import os
from datetime import datetime

from flask_restful import Resource, fields, marshal, reqparse

from controllers.console.wraps import setup_required
from controllers.inner_api import api
from controllers.inner_api.wraps import enterprise_inner_api_only
from events.tenant_event import tenant_was_created
from libs.helper import TimestampField
from models.account import Account
from services.account_service import TenantService

workspace_fields = {
    'id': fields.String,
    'name': fields.String,
    'dept_id': fields.String,
    'status': fields.String,
    'created_at': TimestampField
}
def sha256_encrypt(input_string: str):
    input_bytes = input_string.encode('utf-8')
    sha256_hash = hashlib.sha256()
    sha256_hash.update(input_bytes)
    return sha256_hash.hexdigest()
def validate_request(args):
    # 1. 检查必需的 headers（sign 和 timeStamp）
    timeStamp = args.get('timeStamp')
    sign = args.get('sign')

    if not sign:
        error_response = {
            'data': '',
            'retCode': -1,
            'retDetail': 'no sign in headers'
        }
        return False, error_response, 400

    if not timeStamp:
        error_response = {
            'data': '',
            'retCode': -1,
            'retDetail': 'no timeStamp in headers'
        }
        return False, error_response, 400

    # 2. 验证 sign 是否匹配
    expected_sign = sha256_encrypt("977729488c6653fcf6523ea4fe8439992256c1a08180c0f5fe76eaed99be95d0" + timeStamp)
    if sign != expected_sign:
        error_response = {
            'data': '',
            'retCode': 403,
            'retDetail': 'sign mismatch with timestamp'
        }
        return False, error_response, 403

    # 3. 验证 timestamp 是否在 5 分钟以内
    try:
        timestamp_int = int(timeStamp)
        if timestamp_int > 1e12:
            timestamp_int = timestamp_int / 1000

        timestamp_datetime = datetime.fromtimestamp(timestamp_int)
        current_time = datetime.now()

        if abs((current_time - timestamp_datetime).total_seconds()) > 300:
            error_response = {
                'data': '',
                'retCode': 500,
                'retDetail': 'timeStamp is timeout by 5min'
            }
            return False, error_response, 500
    except (ValueError, TypeError):
        error_response = {
            'data': '',
            'retCode': 500,
            'retDetail': 'invalid timestamp format'
        }
        return False, error_response, 500

    # 4. 检查请求体是否为空
    if not args.get('data'):
        error_response = {
            'data': '',
            'retCode': 500,
            'retDetail': 'body is null'
        }
        return False, error_response, 500

    # 所有校验通过
    return True, None, None
class QueryWorkspaceListApi(Resource):
    @setup_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('data', type=str, required=False, location='json')
        parser.add_argument('timeStamp', type=str, required=False, location='headers')
        parser.add_argument('sign', type=str, required=False, location='headers')
        args = parser.parse_args()

        # itsm回调 接口鉴权
        is_valid, error_response, status_code = validate_request(args)
        if not is_valid:
            return error_response, status_code

        tenants = TenantService.get_all_tenants()
        return {
            'code': '0',
            'message': 'success',
            'data': {
                'workspaceList': marshal(tenants, workspace_fields)}
        }, 200
class CreateWorkspaceApi(Resource):
    admin_username = os.environ.get("ADMIN_USERNAME", "ADMIN_USERNAME")

    @setup_required
    @enterprise_inner_api_only
    def post(self):
        # 创建工作空间，使用admin账户作为owner
        parser = reqparse.RequestParser()
        parser.add_argument('dept_id', type=str, required=True, location='json')
        parser.add_argument('dept_full_name', type=str, required=True, location='json')
        parser.add_argument('data', type=str, required=False, location='json')

        args = parser.parse_args()
        if args['data']:
            logging.info(f"args;{args}")
            return {'code': '400'}, 200

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
    @enterprise_inner_api_only
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
    @enterprise_inner_api_only
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
    @enterprise_inner_api_only
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

class ItsmWorkspaceApi(Resource):
    @setup_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('data', type=str, required=False, location='json')
        parser.add_argument('tiameStamp', type=str, required=False, location='headers')
        parser.add_argument('sign', type=str, required=False, location='headers')
        args = parser.parse_args()

        # itsm回调 接口鉴权
        is_valid, error_response, status_code = validate_request(args)
        if not is_valid:
            return error_response, status_code

        if args['data']:
            try:
                data_dict = json.loads(args['data'])
                args['data'] = data_dict
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string")

        data_list = args['data']['dataList']
        for item in data_list:
            try:
                # todo：根据表单配置获取参数，创建工作空间，加入用户  根据change_type判断对应操作
                print(f"item:{item}")
                tenant = TenantService.get_tenant_by_name(item['workspace_name'])
                if tenant:
                    return {'retCode': '400', 'retDetail': 'Workspace with this name already exists'}, 400
                tenant = TenantService.create_tenant(args['name'])

            except Exception as e:
                logging.exception(f"Error processing item {item}: {str(e)}")
                continue  # 跳过当前项，继续处理下一个

        return {
            'retCode': '0',
            'retDetail': 'success',
            'data': {
                'workspace_id': 'tenant.id'
            }
        }, 200

api.add_resource(ItsmWorkspaceApi, '/dev/itsm/workspace')
api.add_resource(CreateWorkspaceApi, '/dev/create/workspace')
api.add_resource(UpdateWorkspaceApi, '/dev/update/workspace')
api.add_resource(WorkspaceApi, '/dev/workspace/<string:dept_id>')
api.add_resource(QueryWorkspaceListApi, '/dev/all-workspaces')