import json
import hashlib
import sys
import random
from datetime import datetime
import os
from typing import Dict, List
from dataclasses import dataclass

from certbot import errors
from certbot.plugins import dns_common

import tencentcloud.common.exception.tencent_cloud_sdk_exception as tc_err
from tencentcloud.common import credential
from tencentcloud.dnspod.v20210323 import dnspod_client, models

class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for TencentCloud

    This Authenticator uses the TencentCloud API to fulfill a dns-01 challenge.
    """

    description = (
        "Obtain certificates using a DNS TXT record (if you are "
        "using TencentCloud for DNS)."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.secret_id = None
        self.secret_key = None
        self.cleanup_maps = {}

    @classmethod
    def add_parser_arguments(cls, add):  # pylint: disable=arguments-differ
        super(Authenticator, cls).add_parser_arguments(add)
        add(
            "credentials",
            help="TencentCloud credentials INI file. If omitted, the environment variables TENCENTCLOUD_SECRET_ID and TENCENTCLOUD_SECRET_KEY will be tried",
        )
        add(
            "debug",
            help="turn on debug mode (print some debug info)",
            type=bool,
            default=False,
        )

    # pylint: disable=no-self-use
    def more_info(self):  # pylint: disable=missing-function-docstring
        return (
            "This plugin configures a DNS TXT record to respond to a dns-01 challenge using "
            + "the TencentCloud API."
        )

    def _validate_credentials(self, credentials):
        self.chk_exist(credentials, "secret_id")
        self.chk_exist(credentials, "secret_key")

    def chk_exist(self, credentials, arg):
        v = credentials.conf(arg)
        if not v:
            raise errors.PluginError("{} is required".format(arg))

    def chk_environ_exist(self, arg):
        if os.environ.get(arg) is None:
            print(os.environ)
            raise errors.PluginError("The environment {} is required".format(arg))

    def chk_base_domain(self, base_domain, validation_name):
        if not validation_name.endswith("." + base_domain):
            raise errors.PluginError(
                "validation_name not ends with base domain name, please report to dev. "
                f"real_domain: {base_domain}, validation_name: {validation_name}"
            )

    def create_tencentcloud_client(self) -> dnspod_client:
        # 初始化 API 认证
        cred = credential.Credential(
            self.secret_id,
            self.secret_key)
        return dnspod_client.DnspodClient(cred, "")

    def describe_record_list(self, client: dnspod_client, domain: str) -> List[Dict]:
        offset = 0
        records = []
        try:
            request = models.DescribeRecordListRequest()
            request.Domain = domain
            response = client.DescribeRecordList(request)
            resp = json.loads(response.to_json_string())
            records.extend(resp["RecordList"])
            while resp["RecordCountInfo"]["TotalCount"] > len(records):
                request.Offset = len(records)
                resp = client.DescribeRecordList(request)
                records.extend(resp["RecordList"])
        except Exception as e:
            print(f"❌ get record list for {domain} error: {e}")
            raise APIException(e)
        return records
    
    def determine_base_domain(self, domain):
        if self.conf("debug"):
            print("finding base domain")

        segments = domain.split(".")
        tried = []
        i = len(segments) - 2
        client = self.create_tencentcloud_client()
        while i >= 0:
            dt = ".".join(segments[i:])
            tried.append(dt)
            i -= 1
            try:
                # 获取域名列表
                resp = self.describe_record_list(client, dt)
            # if error, we don't seem to own this domain
            except APIException as _:
                continue
            return dt, resp
        raise errors.PluginError(
            "failed to determine base domain, please report to dev. " f"Tried: {tried}"
        )

    # pylint: enable=no-self-use

    def _setup_credentials(self):
        if self.conf("credentials"):
            credentials = self._configure_credentials(
                "credentials",
                "TencentCloud credentials INI file",
                None,
                self._validate_credentials,
            )
            self.secret_id = credentials.conf("secret_id")
            self.secret_key = credentials.conf("secret_key")
        else:
            self.chk_environ_exist("TENCENTCLOUD_SECRET_ID")
            self.chk_environ_exist("TENCENTCLOUD_SECRET_KEY")
            self.secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID")
            self.secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY")

    def _perform(self, domain, validation_name, validation):
        if self.conf("debug"):
            print("perform", domain, validation_name, validation)
        base_domain, _ = self.determine_base_domain(domain)
        self.chk_base_domain(base_domain, validation_name)

        sub_domain = validation_name[: -(len(base_domain) + 1)]

        try:
            client = self.create_tencentcloud_client()
            self.delete_record(client, base_domain, sub_domain)
            # 创建请求对象
            request = models.CreateRecordRequest()
            request.Domain = base_domain
            request.SubDomain = sub_domain
            request.RecordType = 'TXT'
            request.RecordLine = "默认"
            request.Value = validation
            request.TTL = 600

            # 发送请求
            response = client.CreateRecord(request)

            # 解析返回数据
            response_data = json.loads(response.to_json_string())
            record_id = response_data.get("RecordId")
            self.cleanup_maps[validation_name] = (base_domain, record_id)
            if self.conf("debug"):
                print(f"add cleanup map: {validation_name}->({base_domain}, {record_id})")
                print(f"create record {validation_name} id {record_id}")
            #r = client.create_record(base_domain, sub_domain, "TXT", validation)
            #self.cleanup_maps[validation_name] = (base_domain, r["RecordId"])
        except Exception as e:
            print(f"❌ challenge {validation_name} error: {e}")
            raise APIException(e)

    def delete_record(self, client: dnspod_client, domain: str, subdomain: str):
            if self.conf("debug"):
                print(f"delete record {subdomain} in {domain}")
            records = self.describe_record_list(client, domain)
            for record in records:
                if record['Name'] == subdomain:
                    if record['Type'] != 'TXT':
                        raise APIException(f"{subdomain} of {domain} Type is {record['Type']}")
                    # 删除 DNS 记录
                    delete_req = models.DeleteRecordRequest()
                    delete_req.Domain = domain
                    delete_req.RecordId = record['RecordId']
                    delete_response = client.DeleteRecord(delete_req)       

    def _cleanup(self, domain, validation_name, validation):
        if self.conf("debug"):
            print("cleanup", domain, validation_name, validation)
        if validation_name in self.cleanup_maps:
            try:
                base_domain, record_id = self.cleanup_maps[validation_name]
                client = self.create_tencentcloud_client()
                # 删除 DNS 记录
                delete_req = models.DeleteRecordRequest()
                delete_req.Domain = base_domain
                delete_req.RecordId = record_id
                delete_response = client.DeleteRecord(delete_req)
                #client.delete_record(base_domain, record_id)
                if not delete_response:
                    print(f"❌ clean up {validation_name} id {record_id} error.")
                    raise APIException()
            except Exception as e:
                print(f"❌ clean up {validation_name} id {record_id} error: {e}")
                raise APIException(e)

        else:
            print("record id not found during cleanup, cleanup probably failed")


class APIException(Exception):
    pass


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <domain>")
        sys.exit(1)
