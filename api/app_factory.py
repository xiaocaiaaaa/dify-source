import logging
import time

from flask import request

from configs import dify_config
from contexts.wrapper import RecyclableContextVar
from dify_app import DifyApp


# ----------------------------
# Application Factory Function
# ----------------------------
def create_flask_app_with_configs() -> DifyApp:
    """
    create a raw flask app
    with configs loaded from .env file
    """
    dify_app = DifyApp(__name__)
    dify_app.config.from_mapping(dify_config.model_dump())

    # add before request hook
    @dify_app.before_request
    def before_request():
        RecyclableContextVar.increment_thread_recycles()
        # 放掉预检请求
        if request.method == 'OPTIONS':
            return '', 200
        # 用于请求追踪
        # request._request_id = str(uuid.uuid4())[:8]  # 也可以全长 uuid
        # logging.info(
        #     f"[{request._request_id}] Incoming {request.method} {request.path} "
        # )
        # print("current_user:", current_user.id, current_user.name)
        #
        # raw_body = request.get_data(as_text=True)
        # print("Raw body:", raw_body)

    @dify_app.after_request
    def after_request(response):
        # request_id = getattr(request, "_request_id", "-")
        # logging.info(
        #     f"[{request_id}] Response status: {response.status_code} | {request.method} {request.path}"
        # )
        return response
    return dify_app



def create_app() -> DifyApp:
    start_time = time.perf_counter()
    app = create_flask_app_with_configs()
    initialize_extensions(app)
    end_time = time.perf_counter()
    if dify_config.DEBUG:
        logging.info(f"Finished create_app ({round((end_time - start_time) * 1000, 2)} ms)")
    return app


def initialize_extensions(app: DifyApp):
    from extensions import (
        ext_app_metrics,
        ext_blueprints,
        ext_celery,
        ext_code_based_extension,
        ext_commands,
        ext_compress,
        ext_database,
        ext_hosting_provider,
        ext_import_modules,
        ext_logging,
        ext_login,
        ext_mail,
        ext_migrate,
        ext_otel,
        ext_proxy_fix,
        ext_redis,
        ext_request_logging,
        ext_sentry,
        ext_set_secretkey,
        ext_storage,
        ext_timezone,
        ext_warnings,
    )

    extensions = [
        ext_timezone,
        ext_logging,
        ext_warnings,
        ext_import_modules,
        ext_set_secretkey,
        ext_compress,
        ext_code_based_extension,
        ext_database,
        ext_app_metrics,
        ext_migrate,
        ext_redis,
        ext_storage,
        ext_celery,
        ext_login,
        ext_mail,
        ext_hosting_provider,
        ext_sentry,
        ext_proxy_fix,
        ext_blueprints,
        ext_commands,
        ext_otel,
        ext_request_logging,
    ]
    for ext in extensions:
        short_name = ext.__name__.split(".")[-1]
        is_enabled = ext.is_enabled() if hasattr(ext, "is_enabled") else True
        if not is_enabled:
            if dify_config.DEBUG:
                logging.info(f"Skipped {short_name}")
            continue

        start_time = time.perf_counter()
        ext.init_app(app)
        end_time = time.perf_counter()
        if dify_config.DEBUG:
            logging.info(f"Loaded {short_name} ({round((end_time - start_time) * 1000, 2)} ms)")


def create_migrations_app():
    app = create_flask_app_with_configs()
    from extensions import ext_database, ext_migrate

    # Initialize only required extensions
    ext_database.init_app(app)
    ext_migrate.init_app(app)

    return app
