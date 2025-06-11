# webank_custom_development
import logging

from flask import request
from flask_restful import Resource, fields

from configs import dify_config
from controllers.console.wraps import setup_required
from controllers.inner_api import api
from controllers.inner_api.wraps import enterprise_inner_api_only
from libs.helper import TimestampField
from services.account_service import TenantService
from services.plugin.plugin_service import PluginService

workspace_fields = {
    'id': fields.String,
    'name': fields.String,
    'dept_id': fields.String,
    'status': fields.String,
    'created_at': TimestampField
}

class BatchPluginInstallApi(Resource):
    @setup_required
    @enterprise_inner_api_only
    def post(self):
        # 1. 获取上传的文件
        if 'pkg' not in request.files:
            return {
                "code": "400",
                "message": "Missing plugin package file"
            }, 400

        file = request.files["pkg"]

        # 2. 文件大小校验
        if file.content_length > dify_config.PLUGIN_MAX_PACKAGE_SIZE:
            return {
                "code": "413",
                "message": "File size exceeds the maximum allowed size"
            }, 413

        # 3. 读取文件内容（注意：这里将整个文件读入内存）
        try:
            content = file.read()
        except Exception as e:
            return {
                "code": "500",
                "message": f"Failed to read plugin package file: {str(e)}"
            }, 500

        # 4. 获取所有租户
        tenants = TenantService.get_all_tenants()
        results = {
            "success": [],
            "failed": []
        }

        for tenant in tenants:
            tenant_id = tenant.id
            try:
                # 5. 调用服务层安装插件包
                upload_response = PluginService.upload_pkg(tenant_id, content)

                # 6. 从响应中提取 plugin_unique_identifier
                plugin_unique_identifiers = upload_response.unique_identifier
                if not isinstance(plugin_unique_identifiers, list):
                    plugin_unique_identifiers = [plugin_unique_identifiers]

                # 7. 校验 plugin_unique_identifiers 是否为字符串列表
                for uid in plugin_unique_identifiers:
                    if not isinstance(uid, str):
                        raise ValueError(f"Invalid plugin unique identifier: {uid}")

                # 8. 调用 install_from_local_pkg 接口安装插件
                install_response = PluginService.install_from_local_pkg(
                    tenant_id, plugin_unique_identifiers
                )

                # 9. 记录成功日志
                logging.info(
                    f"Successfully installed plugin package for tenant {tenant_id}, "
                    f"plugin_unique_identifiers: {plugin_unique_identifiers}, "
                    f"install_response: {install_response}"
                )
                results["success"].append(tenant_id)

            except Exception as e:
                logging.exception(
                    f"Unexpected error for tenant {tenant_id}: {str(e)}"
                )
                results["failed"].append({
                    "tenant_id": tenant_id,
                    "error": str(e)
                })

                # 11. 返回批量安装结果
        return {
                "code": "0",
                "message": "Batch install completed",
                "data": results
            }, 200


api.add_resource(BatchPluginInstallApi, "/batch-plugin/install")