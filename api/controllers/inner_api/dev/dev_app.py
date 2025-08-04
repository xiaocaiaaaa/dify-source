#webank_custom_development
from ctypes import cast

import yaml
from flask_login import current_user
from flask_restful import Resource, inputs, marshal, marshal_with, reqparse, fields
import services
import contexts
from controllers.console.wraps import setup_required
from controllers.inner_api import api
from controllers.inner_api.wraps import enterprise_inner_api_only
from fields.app_fields import (
    app_detail_fields,
    app_detail_fields_with_site,
    app_pagination_fields,
    app_partial_fields,
)
from sqlalchemy.orm import Session

from services.app_dsl_service import AppDslService
from services.app_service import AppService
from services.account_service import TenantService, AccountService

from libs.helper import TimestampField

from models.account import TenantAccountJoin ##webank_custom_development
from extensions.ext_database import db
from controllers.console.app.wraps import get_app_model
from controllers.console.wraps import (
    account_initialization_required,
    cloud_edition_billing_resource_check,
    setup_required,
)
from extensions.ext_database import db
from fields.app_fields import app_import_check_dependencies_fields, app_import_fields
from libs.login import login_required
from models import Account
from models.model import App
from services.app_dsl_service import AppDslService, ImportStatus
from services.enterprise.enterprise_service import EnterpriseService
from services.feature_service import FeatureService


model_config_partial_fields = {
    'model': fields.Raw(attribute='model_dict'),
    'pre_prompt': fields.String,
}

tag_fields = {
    'id': fields.String,
    'name': fields.String,
    'type': fields.String
}



class AppListApi(Resource):
    @setup_required
    @enterprise_inner_api_only
    def get(self):
        """Get app list"""
        parser = reqparse.RequestParser()
        parser.add_argument('w_id', type=str, location='args', required=True)
        args = parser.parse_args()
        tenant_id = args['w_id']
        # get app list
        app_service = AppService()
        all_app = app_service.get_all_apps(tenant_id)
        if not all_app:
            return {
            'code': '0',
            'message': 'success',
            'data': {
                "app": []
                }
            }, 200
        return {
            'code': '0',
            'message': 'success',
            'data': {
                "app": marshal(all_app, app_detail_fields)
            }
        }, 200


class AppImportApi(Resource):

    @setup_required
    # @enterprise_inner_api_only
    def post(self):
        """Import app"""
        parser = reqparse.RequestParser()
        parser.add_argument('data', type=str, required=True, nullable=False, location='json')
        parser.add_argument('name', type=str, location='json')
        parser.add_argument('description', type=str, location='json')
        parser.add_argument('icon', type=str, location='json')
        parser.add_argument('icon_background', type=str, location='json')
        parser.add_argument('user_id', type=str, location='json')
        parser.add_argument('workspace_id', type=str, location='json')
        args = parser.parse_args()
        # contexts.tenant_id.set(args['workspace_id'])

        account = AccountService.get_user_through_email(args['user_id'])
        tenant = TenantService.get_tenant_by_workspace_id(args['workspace_id'])
        account.current_tenant = tenant
        if account is None:
            return {
                'code': '404',
                'message': 'User Not Exist'
            }, 200

        data_str = args["data"]
        # 去除首尾多余的引号（如果需要）
        data_str = data_str.strip('"')
        # 将转义的双引号还原
        data_str = data_str.replace('\\"', '"')
        # 将转义的反斜杠还原
        data_str = data_str.replace('\\\\', '\\')

        try:
            import_data = yaml.safe_load(data_str)
        except yaml.YAMLError:
            raise ValueError("Invalid YAML format in data argument")
        args.mode = import_data.get("app").get("mode")
        args.name = import_data.get("app").get("name")
        # Create service with session
        with Session(db.engine) as session:
            import_service = AppDslService(session)

            # Import app
            result = import_service.import_app(
                account=account,
                import_mode="yaml-content",
                yaml_content=data_str,
                yaml_url=args.get("yaml_url"),
                name=args.get("name"),
                description=args.get("description"),
                icon_type=args.get("icon_type"),
                icon=args.get("icon"),
                icon_background=args.get("icon_background"),
                app_id=args.get("app_id"),
            )
            session.commit()
        if result.app_id and FeatureService.get_system_features().webapp_auth.enabled:
            # update web app setting as private
            EnterpriseService.WebAppAuth.update_app_access_mode(result.app_id, "private")
        # Return appropriate status code based on result
        status = result.status
        if status == ImportStatus.FAILED.value:
            return result.model_dump(mode="json"), 400
        elif status == ImportStatus.PENDING.value:
            return result.model_dump(mode="json"), 202

        app = db.session.query(App).filter_by(id=result.app_id).first()
        return result.model_dump(mode="json"), 200

        # return {
        #     'code': '0',
        #     'message': 'success',
        #     'data': {
        #         "app": marshal(app, app_detail_fields_with_site)
        #     }
        # }, 200


class AppExportApi(Resource):

    @setup_required
    @enterprise_inner_api_only
    @get_app_model
    def get(self, app_model):
        """Export app"""
        parser = reqparse.RequestParser()
        parser.add_argument('include_secret', type=inputs.boolean, default=False, location='args')
        args = parser.parse_args()

        return {
            'code': '0',
            'message': 'success',
            "data": AppDslService.export_dsl(app_model=app_model, include_secret=args['include_secret'])
        }


class AppSiteStatus(Resource):
    @setup_required
    @enterprise_inner_api_only
    @get_app_model
    def post(self, app_model):
        parser = reqparse.RequestParser()
        parser.add_argument('enable_site', type=bool, required=True, location='json')
        args = parser.parse_args()

        app_service = AppService()
        current_owner_join = db.session.query(TenantAccountJoin).filter_by(tenant_id=app_model.tenant_id, role="owner").first()
        app_model = app_service.update_app_site_status(app_model, current_owner_join.account_id, args.get('enable_site'))

        return {
            'code': '0',
            'message': 'success',
            'data': {
                "app": marshal(app_model, app_detail_fields_with_site)
            }
        }, 200


class AppApiStatus(Resource):
    @setup_required
    @enterprise_inner_api_only
    @get_app_model
    def post(self, app_model):
        parser = reqparse.RequestParser()
        parser.add_argument('enable_api', type=bool, required=True, location='json')
        args = parser.parse_args()

        app_service = AppService()
        current_owner_join = db.session.query(TenantAccountJoin).filter_by(tenant_id=app_model.tenant_id, role="owner").first()
        app_model = app_service.update_app_api_status(app_model, current_owner_join.account_id, args.get('enable_api'))

        return {
            'code': '0',
            'message': 'success',
            'data': {
                "app": marshal(app_model, app_detail_fields_with_site)
            }
        }, 200


class AppApi(Resource):

    @setup_required
    @enterprise_inner_api_only
    @get_app_model
    def get(self, app_model):
        """Get app detail"""
        app_service = AppService()

        app_model = app_service.get_app(app_model)

        return {
            'code': '0',
            'message': 'success',
            'data': {
                "app": marshal(app_model, app_detail_fields_with_site)
            }
        }, 200

    @setup_required
    @enterprise_inner_api_only
    @get_app_model
    def delete(self, app_model):
        """Delete app"""

        app_service = AppService()
        app_service.delete_app(app_model)

        return {
            'code': '0',
            'message': 'success'
        }, 200


api.add_resource(AppListApi, '/dev/apps')
api.add_resource(AppImportApi, '/dev/apps/import')
api.add_resource(AppExportApi, '/dev/apps/<uuid:app_id>/export')
api.add_resource(AppSiteStatus, '/dev/apps/<uuid:app_id>/site-enable')
api.add_resource(AppApiStatus, '/dev/apps/<uuid:app_id>/api-enable')
api.add_resource(AppApi, '/dev/apps/<uuid:app_id>')
