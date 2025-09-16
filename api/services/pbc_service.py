import os
from typing import Literal

import httpx
from tenacity import retry, retry_if_exception_type, stop_before_delay, wait_fixed
from configs import dify_config

from extensions.ext_database import db
from libs.helper import RateLimiter
from models.account import Account, TenantAccountJoin, TenantAccountRole


class PbcService:
    # base_url = os.environ.get("BILLING_API_URL", "BILLING_API_URL")
    # secret_key = os.environ.get("BILLING_API_SECRET_KEY", "BILLING_API_SECRET_KEY")
    base_url = os.environ.get("PBC_SERVER_URL", "PBC_SERVER_URL")
    sys_code = os.environ.get("SYS_CODE", "SYS_CODE")
    secret = os.environ.get("SECRET", "SECRET")
    parse_token_path = os.environ.get("PARSE_TOKEN_PATH", "PARSE_TOKEN_PATH")

    @classmethod
    def parse_token(cls, token: str):
        return cls._send_request("GET", token)

    @classmethod
    @retry(
        wait=wait_fixed(2),
        stop=stop_before_delay(10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    def _send_request(cls, method: Literal["GET", "POST", "DELETE"], token: str, json=None, params=None):
        headers = {
            "Authorization": 'Bearer ' + token,
            "sysCode": cls.sys_code,
            'secret': cls.secret,
        }

        url = f"{cls.base_url}{cls.parse_token_path}"
        response = httpx.request(method, url, json=json, params=params, headers=headers)

        if method == "GET" and response.status_code != httpx.codes.OK:
            raise ValueError("Unable to retrieve billing information. Please try again later or contact support.")
        return response.json()
