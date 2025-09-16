import logging
import os
from typing import Literal

import httpx
from flask_restful import Resource, reqparse  # type: ignore
from tenacity import retry, retry_if_exception_type, stop_before_delay, wait_fixed

from constants.languages import languages
from controllers.console.wraps import setup_required
from controllers.inner_api import api
from controllers.inner_api.wraps import enterprise_inner_api_only
from services.account_service import AccountService, TenantService


class UpdateUser(Resource):
    default_password = os.environ.get("DEFAULT_PASSWORD", "DEFAULT_PASSWORD")
    email_suffix = os.environ.get("EMAIL_SUFFIX", "EMAIL_SUFFIX")

    @setup_required
    @enterprise_inner_api_only
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("userInfo", type=dict, required=True, location="json")
        parser.add_argument("msgType", type=str, required=True, location="json")
        args = parser.parse_args()
        logging.info(f"args: {args}")

        update_user = args["userInfo"]
        msg_type = args["msgType"]
        dept_id = str(update_user['deptId'])
        if dept_id is None or dept_id == "":
            return {
                'code': '400',
                'message': 'dept_id can not be null'
            }, 400

        tenant = TenantService.get_tenant(dept_id)
        if tenant is None:
            logging.error(f"workspace not found with given deptId: {str(update_user['deptId'])}")

            return {
                'code': '400',
                'message': 'workspace not found'
            }, 400

        account = AccountService.get_user_through_name(update_user['username'])

        if msg_type == "DELETE" and account is not None:
            AccountService.pbc_delete_account(account)
            return {"message": "user deleted."}
        elif msg_type == "CREATE_OR_UPDATE" and account is not None:
            tenant_list = TenantService.get_join_tenants(account)
            ori_tenant = next((t for t in tenant_list if t.name != "公共工作空间"), None)
            # 除了公共工作空间没有其他的工作空间，直接加入到新的工作空间
            if ori_tenant is None:
                TenantService.create_tenant_member(tenant, account, role="normal")
                return {"message": "user updated."}
            # 原本有工作空间，和传入的工作空间不同就更新
            if tenant != ori_tenant and ori_tenant is not None:
                TenantService.pbc_remove_member_from_tenant(ori_tenant, account)
                TenantService.create_tenant_member(tenant, account, role="normal")
                return {"message": "user updated."}
        elif msg_type == "CREATE_OR_UPDATE" and account is None:
            new_account = AccountService.create_pbc_account(update_user['username'] + self.email_suffix, update_user['username'],
                                              languages[0], self.default_password)
            # 新增用户需要添加到公共工作空间，normal权限
            public_tenant = TenantService.get_tenant_by_name("公共工作空间")
            TenantService.create_tenant_member(public_tenant, new_account, role="normal")
            TenantService.create_tenant_member(tenant, new_account, role="normal")
            return {"message": "user created."}
        # 否则什么操作都不做
        return {"message": "user has no change."}

class UpdateDept(Resource):
    admin_username = os.environ.get("ADMIN_USERNAME", "ADMIN_USERNAME")

    @setup_required
    @enterprise_inner_api_only
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("deptInfo", type=dict, required=True, location="json")
        parser.add_argument("msgType", type=str, required=True, location="json")
        args = parser.parse_args()
        logging.info(f"args: {args}")

        update_dept = args["deptInfo"]
        msg_type = args["msgType"]
        dept_id = str(update_dept['deptId'])
        new_dept_full_name = update_dept['deptFullName']

        if dept_id is None or dept_id == "" or new_dept_full_name is None or new_dept_full_name == "":
            return {
                'code': '400',
                'message': 'deptId or deptFullName can not be null'
            }, 400

        tenant = TenantService.get_tenant(dept_id)

        # 删除部门，同时删除account_tenant_join
        if msg_type == "DELETE" and tenant is not None:
            TenantService.delete_tenant(tenant)
        # 部门为空就是新增部门
        elif msg_type == "CREATE_OR_UPDATE" and tenant is None:
            dept_tenant = TenantService.create_tenant(
                name=new_dept_full_name,
                dept_id=update_dept['deptId'],
                is_from_dashboard=True
            )
            # 然后把admin作为新增部门的owner
            admin_account = AccountService.get_user_through_name(self.admin_username)
            TenantService.create_tenant_member(dept_tenant, admin_account, role="owner")
        # 否则就是部门改名
        elif msg_type == "CREATE_OR_UPDATE" and tenant is not None:
            tenant.name = new_dept_full_name
            TenantService.update_tenant(tenant)
        return {"message": "workspace updated success."}

class InitPbcData(Resource):
    base_url = os.environ.get("PBC_SERVER_URL", "PBC_SERVER_URL")
    default_password = os.environ.get("DEFAULT_PASSWORD", "DEFAULT_PASSWORD")
    sys_code = os.environ.get("SYS_CODE", "SYS_CODE")
    secret = os.environ.get("SECRET", "SECRET")
    init_dept_path = os.environ.get("INIT_DEPT_PATH", "INIT_DEPT_PATH")
    init_user_path = os.environ.get("INIT_USER_PATH", "INIT_USER_PATH")
    email_suffix = os.environ.get("EMAIL_SUFFIX", "EMAIL_SUFFIX")
    admin_username = os.environ.get("ADMIN_USERNAME", "ADMIN_USERNAME")

    @setup_required
    @enterprise_inner_api_only
    def post(self):
        department_resp = self._send_request("GET", self.init_dept_path)
        filtered_dept_data = [dept for dept in department_resp['data'] if dept['deptCode'] == 'A001']
        dept_data = filtered_dept_data[0].get('children')

        user_resp = self._send_request("GET", self.init_user_path)
        user_data = user_resp['data']

        def create_workspaces(departments, admin_account):
            for dept in departments:
                dept_name = dept.get("deptFullName")
                if not dept_name:
                    continue
                dept_tenant = TenantService.create_tenant(
                    name=dept_name,
                    dept_id=dept.get("deptId"),
                    is_from_dashboard=True
                )
                # admin用户作为所有工作空间的owner
                TenantService.create_tenant_member(dept_tenant, admin_account, role="owner")

                filtered_users = [user for user in user_data if user.get("deptId") == dept['deptId']]
                for filtered_user in filtered_users:
                    # 部门内用户作为normal权限
                    filtered_account = AccountService.get_user_through_name(filtered_user['username'])
                    TenantService.create_tenant_member(dept_tenant, filtered_account, role="normal")

                # 递归处理子部门
                # children = dept.get("children", [])
                # if children:
                #     create_workspaces(children)

        # 1、先创建公共工作空间和admin账户，并且把admin账户添加到公共工作空间作为owner
        public_tenant = TenantService.create_tenant("公共工作空间", is_from_dashboard=True)
        admin_account = AccountService.create_pbc_account(self.admin_username + self.email_suffix, self.admin_username,
                                                    languages[0], self.default_password)
        TenantService.create_tenant_member(public_tenant, admin_account, role="owner")

        # 2、然后遍历并创建所有用户，且加入到公共工作空间，权限默认都是normal
        for user in user_data:
            account = AccountService.create_pbc_account(user['username'] + self.email_suffix, user['username'], languages[0], self.default_password)
            TenantService.create_tenant_member(public_tenant, account, role="normal")

        # 3、然后遍历所有的部门创建子工作空间，把admin账户作为owner加入子工作空间，部门员工作为normal加入子工作空间
        create_workspaces(dept_data, admin_account)
        return {"message": "data init success."}

    @classmethod
    @retry(
        wait=wait_fixed(2),
        stop=stop_before_delay(10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    def _send_request(cls, method: Literal["GET", "POST", "DELETE"], endpoint: str, json=None, params=None):
        headers = {
            "sysCode": cls.sys_code,
            'secret': cls.secret
        }

        url = f"{cls.base_url}{endpoint}"
        response = httpx.request(method, url, json=json, params=params, headers=headers)

        if method == "GET" and response.status_code != httpx.codes.OK:
            raise ValueError("Unable to retrieve billing information. Please try again later or contact support.")
        return response.json()

api.add_resource(InitPbcData, "/dev/init")
api.add_resource(UpdateUser, "/dev/update_user")
api.add_resource(UpdateDept, "/dev/update_dept")
