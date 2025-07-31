# webank_custom_development
import enum
import json

from flask_restful import Resource, marshal, reqparse
from werkzeug.exceptions import Forbidden, NotFound

from controllers.console.wraps import setup_required
from controllers.inner_api import api
from fields.dataset_fields import dataset_detail_fields
from services.account_service import AccountService, TenantService
from services.dataset_service import DatasetPermissionService, DatasetService
from services.errors.dataset import DatasetNameDuplicateError
from services.external_knowledge_service import ExternalDatasetService


class KBSMsgType(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


def _validate_name(name):
    if not name or len(name) < 1 or len(name) > 100:
        raise ValueError("Name must be between 1 to 100 characters.")
    return name


# 创建外部知识库
class ExternalDatasetApi(Resource):
    @setup_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("msgType", type=str, required=True, nullable=False, location="json",
                            choices=[KBSMsgType.CREATE, KBSMsgType.UPDATE, KBSMsgType.DELETE], help="Invalid Msg type.")
        parser.add_argument("username", type=str, required=True, nullable=False, location="json")
        parser.add_argument("workspace_id", type=str, required=True, nullable=False, location="json")
        parser.add_argument("external_knowledge_api", type=dict, required=False, location="json")
        parser.add_argument("external_dataset", type=dict, required=False, location="json")
        parser.add_argument("permission", type=dict, required=False, location="json")
        args = parser.parse_args()

        current_user = AccountService.get_user_through_name(args["username"])
        # todo 行内测试的时候这里换成getTenantById
        tenant = TenantService.get_tenant_by_name(args['workspace_id'])
        current_user.current_tenant = tenant
        # The role of the current user in the ta table must be admin, owner, or editor, or dataset_operator
        if not current_user.is_dataset_editor:
            raise Forbidden()

        try:
            external_knowledge_api_req = args.get('external_knowledge_api') or {}
            external_dataset_req = args.get('external_dataset') or {}
            permission_req = args.get('permission') or {}

            external_api_id_req = external_knowledge_api_req.get("id")
            external_dataset_id_req = external_dataset_req.get("id")

            if args['msgType'] == KBSMsgType.CREATE:
                external_knowledge_api = None
                dataset = None
                external_knowledge_api_id = None

                # 判断是否需要创建 external_knowledge_api，或仅使用已存在的 ID
                if external_knowledge_api_req:
                    if "id" in external_knowledge_api_req:
                        external_knowledge_api_id = external_knowledge_api_req["id"]
                    elif "settings" in external_knowledge_api_req:
                        ExternalDatasetService.validate_api_list(external_knowledge_api_req["settings"])
                        external_knowledge_api = ExternalDatasetService.create_external_knowledge_api(
                            tenant_id=current_user.current_tenant_id,
                            user_id=current_user.id,
                            args=external_knowledge_api_req
                        )
                        external_knowledge_api_id = external_knowledge_api.id

                # 创建 external_dataset（如果有）
                if external_dataset_req:
                    if not external_knowledge_api_id:
                        raise ValueError("external_knowledge_api_id is required for dataset creation")

                    # 强制绑定 external_knowledge_api_id
                    external_dataset_req["external_knowledge_api_id"] = external_knowledge_api_id

                    dataset = ExternalDatasetService.create_external_dataset(
                        tenant_id=current_user.current_tenant_id,
                        user_id=current_user.id,
                        args=external_dataset_req
                    )

                    # 设置权限（仅当 dataset 创建时才需要）
                    if permission_req:
                        username_list = permission_req.get("partial_member_list")
                        if username_list:
                            new_partial_member_list = []
                            for username in username_list:
                                user = AccountService.get_user_through_name(username)
                                if not user:
                                    raise ValueError(f"User '{username}' not found")
                                new_partial_member_list.append({"user_id": user.id})
                            # 替换原来的用户名列表为 user_id 格式列表
                            permission_req["partial_member_list"] = new_partial_member_list

                        DatasetService.update_dataset_permission(permission_req, current_user, dataset)

                if dataset:
                    # 返回 Dataset 的详细信息
                    return {
                        "data": marshal(dataset, dataset_detail_fields),
                        "message": "success"
                    }, 200
                elif external_knowledge_api:
                    try:
                        settings = json.loads(external_knowledge_api.settings or '{}')
                    except Exception:
                        settings = {}

                    # 构造一个伪 dataset，仅填充 external_knowledge_info 字段
                    fake_dataset = {
                        "external_knowledge_info": {
                            "external_knowledge_id": None,
                            "external_knowledge_api_id": external_knowledge_api.id,
                            "external_knowledge_api_name": external_knowledge_api.name,
                            "external_knowledge_api_endpoint": settings.get("endpoint", "")
                        }
                    }

                    return {
                        "data": marshal(fake_dataset, dataset_detail_fields),
                        "message": "success"
                    }, 200
                else:
                    # 不应到这里
                    return {
                        "data": {},
                        "message": "no action performed"
                    }, 400

            elif args['msgType'] == KBSMsgType.UPDATE:
                if not external_api_id_req or not external_dataset_id_req:
                    raise ValueError("external_knowledge_api.id and external_dataset.id are required")
                ExternalDatasetService.validate_api_list(external_knowledge_api_req["settings"])

                # 1.更新external_knowledge_api
                external_knowledge_api = ExternalDatasetService.update_external_knowledge_api(
                    tenant_id=current_user.current_tenant_id,
                    user_id=current_user.id,
                    external_knowledge_api_id=external_api_id_req,
                    args=external_knowledge_api_req,
                )
                # 2.更新dataset 和 permission
                dataset = DatasetService.get_dataset(external_dataset_id_req)
                if dataset is None:
                    raise NotFound("Dataset not found.")
                # The role of the current user in the ta table must be admin, owner, editor, or dataset_operator
                DatasetPermissionService.check_permission(
                    current_user, dataset, permission_req.get("mode"), external_dataset_req.get("partial_member_list")
                )
                dataset = DatasetService.update_dataset_for_kbs(external_dataset_id_req,
                                                                external_knowledge_api,
                                                                external_dataset_req,
                                                                permission_req,
                                                                current_user)
                return marshal(dataset, dataset_detail_fields), 201
            elif args['msgType'] == KBSMsgType.DELETE:
                if external_api_id_req:
                    ExternalDatasetService.delete_external_knowledge_api(current_user.current_tenant_id,
                                                                         external_api_id_req)
                if external_dataset_id_req:
                    if DatasetService.delete_dataset(external_dataset_id_req, current_user):
                        DatasetPermissionService.clear_partial_member_list(external_dataset_id_req)
                    else:
                        raise NotFound("Dataset not found.")
                return {
                    'retCode': '0',
                    'retDetail': 'success',
                }, 204
        except DatasetNameDuplicateError:
            raise DatasetNameDuplicateError()

        return {
            'retCode': '0',
            'retDetail': 'success',
        }, 200


api.add_resource(ExternalDatasetApi, '/dev/external/datasets')
