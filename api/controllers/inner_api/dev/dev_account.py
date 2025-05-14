# webank_custom_development
import os

from flask_restful import Resource, fields, marshal, reqparse

from constants.languages import languages
from controllers.console.wraps import setup_required
from controllers.inner_api import api
from controllers.inner_api.wraps import inner_api_only
from libs.helper import TimestampField
from models.account import Account
from services.account_service import AccountService, TenantService

account_fields = {
    'id': fields.String,
    'name': fields.String,
    'status': fields.String,
    'email': fields.String,
    'created_at': TimestampField
}

class CreateAccountApi(Resource):
    email_suffix = os.environ.get("EMAIL_SUFFIX", "EMAIL_SUFFIX")
    default_password = os.environ.get("DEFAULT_PASSWORD", "DEFAULT_PASSWORD")

    @setup_required
    @inner_api_only
    def post(self):
        # 使用传参username创建用户，不做任何关联
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, location='json')
        args = parser.parse_args()
        username = args['username']

        account = Account.query.filter_by(name=username).first()
        tenant = TenantService.get_tenant_by_name('公共工作空间')

        if account is not None:
            return {'code': '400', 'message': 'account with this name already exist'}, 200
        else:
            account = AccountService.create_pbc_account(username + self.email_suffix, username, languages[0], self.default_password)
            TenantService.create_tenant_member(tenant, account, role="admin")
            return {
                'code': '0',
                'message': 'success',
                'data': {
                    'account_id': account.id
                }
            }, 200


class UpdateAccountApi(Resource):
    # 把用户从对应工作空间解绑
    @setup_required
    @inner_api_only
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('dept_id', type=str, required=True, location='json')
        parser.add_argument('username', type=str, required=True, location='json')
        args = parser.parse_args()

        # 查到用户
        account = AccountService.get_user_through_name(args['username'])
        if not account:
            return {'code': '400', 'message': "Account with this name doesn't exists"}, 200

        # 查到对应工作空间
        tenant = TenantService.get_tenant(args['dept_id'])
        if tenant is not None:
            TenantService.pbc_remove_member_from_tenant(tenant, account)
            return {
                'code': '0',
                'message': 'success',
                'data': {
                    'removed_tenant_id': tenant.id
                }
            }, 200

class AccountApi(Resource):
    @setup_required
    @inner_api_only
    def get(self, name):
        account = AccountService.get_user_through_name(name)
        if account is None:
            return {
                'code': '404',
                'message': 'account not found'
            }, 404
        return {
            'code': '0',
            'message': 'success',
            'data': {
                'account': marshal(account, account_fields)
            }
        }, 200

    @setup_required
    @inner_api_only
    def delete(self, name):
        account = AccountService.get_user_through_name(name)
        if account is None:
            return {
                'code': '404',
                'message': 'Account not found'
            }, 200
        AccountService.pbc_delete_account(account)
        return {
            'code': '0',
            'message': 'account delete success'
        }, 200

class QueryAccountListApi(Resource):
    @setup_required
    @inner_api_only
    def get(self):
        accounts = AccountService.get_all_accounts()
        return {
            'code': '0',
            'message': 'success',
            'data': {
                'accountList': marshal(accounts, account_fields)}
        }, 200

api.add_resource(CreateAccountApi, '/dev/create/account')
api.add_resource(UpdateAccountApi, '/dev/update/account')
api.add_resource(AccountApi, '/dev/account/<string:name>')
api.add_resource(QueryAccountListApi, '/dev/all-accounts')