#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿里云日志服务(SLS)日志查询脚本
使用阿里云官方 SDK 查询应用错误日志

使用方式:
    python query_sls_logs.py --config <config_file> --logstore <logstore> [--query <query>] [--from <from_time>] [--to <to_time>]

依赖安装:
    pip3 install -r requirements.txt

参数:
    --config: 配置文件路径 (必需)
    --logstore: SLS logstore 名称 (必需)
    --query: 查询语句 (可选，默认查询 ERROR 级别日志)
    --from: 开始时间 Unix时间戳 (可选，默认1小时前)
    --to: 结束时间 Unix时间戳 (可选，默认当前时间)
    --line: 返回日志条数 (可选，默认100)
"""

import argparse
import json
import os
import sys
import time
import subprocess


def get_venv_python():
    """
    查找并返回虚拟环境中的 Python 解释器路径。
    优先级: .venv > venv
    如果找不到虚拟环境，返回 None。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 检查 .venv
    venv_python = os.path.join(script_dir, '.venv', 'bin', 'python3')
    if os.path.isfile(venv_python):
        return venv_python

    # 检查 venv
    venv_python = os.path.join(script_dir, 'venv', 'bin', 'python3')
    if os.path.isfile(venv_python):
        return venv_python

    return None


def is_in_venv():
    """检查当前是否在虚拟环境中运行"""
    return sys.prefix != sys.base_prefix


def ensure_venv():
    """
    确保脚本在虚拟环境中运行。
    如果当前不在虚拟环境中，自动切换到虚拟环境执行。
    """
    # 如果已经在虚拟环境中，直接返回
    if is_in_venv():
        return True

    # 查找虚拟环境
    venv_python = get_venv_python()
    if venv_python:
        # 使用虚拟环境的 Python 重新执行脚本
        result = subprocess.run([venv_python] + sys.argv)
        sys.exit(result.returncode)

    # 没有虚拟环境，返回 False 让后续逻辑处理
    return False


# 确保在虚拟环境中运行
ensure_venv()

try:
    from alibabacloud_sls20201230.client import Client as SlsClient
    from alibabacloud_credentials.client import Client as CredentialClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_sls20201230 import models as sls_models
    from alibabacloud_tea_util import models as util_models
except ImportError as e:
    venv_python = get_venv_python()
    if venv_python:
        error_hint = f"虚拟环境已找到 ({venv_python})，但依赖未安装。请运行: {venv_python} -m pip install -r requirements.txt"
    else:
        error_hint = "未找到虚拟环境。请在 scripts 目录下创建虚拟环境: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"

    print(json.dumps({
        'success': False,
        'error': f'缺少依赖: {str(e)}',
        'hint': error_hint
    }, ensure_ascii=False))
    sys.exit(1)


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    config_path = os.path.expanduser(config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    if 'sls' not in config:
        raise ValueError("配置文件缺少 'sls' 字段")

    sls_config = config['sls']
    if 'project' not in sls_config:
        raise ValueError("配置文件缺少 'sls.project' 字段")

    return config


def create_client() -> SlsClient:
    """创建 SLS 客户端（使用无AK凭据方式）"""
    credential = CredentialClient()
    config = open_api_models.Config(credential=credential)
    config.endpoint = 'your-region.log.aliyuncs.com'  # e.g., cn-shanghai.log.aliyuncs.com
    return SlsClient(config)


def query_sls_logs(
    project: str,
    logstore: str,
    client: SlsClient,
    query: str,
    from_time: int,
    to_time: int,
    line: int = 100
) -> dict:
    """查询 SLS 日志"""
    try:
        get_logs_request = sls_models.GetLogsRequest(
            from_=from_time,
            to=to_time,
            query=query,
            line=line
        )

        runtime = util_models.RuntimeOptions()
        headers = {}

        response = client.get_logs_with_options(project, logstore, get_logs_request, headers, runtime)

        logs = []
        if response.body and isinstance(response.body, list):
            logs = response.body

        return {
            'success': True,
            'logs': logs,
            'count': len(logs)
        }

    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'message'):
            error_msg = e.message
        elif hasattr(e, 'error_info'):
            error_msg = e.error_info

        return {
            'success': False,
            'error': error_msg
        }


def main():
    parser = argparse.ArgumentParser(description='查询阿里云SLS日志')
    parser.add_argument('--config', required=True, help='配置文件路径')
    parser.add_argument('--logstore', required=True, help='SLS logstore名称')
    parser.add_argument('--query', default=None, help='查询语句')
    parser.add_argument('--from', dest='from_time', type=int, default=None, help='开始时间(Unix时间戳)')
    parser.add_argument('--to', dest='to_time', type=int, default=None, help='结束时间(Unix时间戳)')
    parser.add_argument('--line', type=int, default=100, help='返回日志条数')

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(json.dumps({
            'success': False,
            'error': f'配置加载失败: {str(e)}'
        }, ensure_ascii=False))
        sys.exit(1)

    sls_config = config['sls']
    project = sls_config['project']
    logstore = args.logstore

    to_time = args.to_time or int(time.time())
    from_time = args.from_time or (to_time - 3600)

    query = args.query or 'ERROR'

    try:
        client = create_client()
    except Exception as e:
        print(json.dumps({
            'success': False,
            'error': f'创建SLS客户端失败: {str(e)}'
        }, ensure_ascii=False))
        sys.exit(1)

    result = query_sls_logs(
        project=project,
        logstore=logstore,
        client=client,
        query=query,
        from_time=from_time,
        to_time=to_time,
        line=args.line
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()