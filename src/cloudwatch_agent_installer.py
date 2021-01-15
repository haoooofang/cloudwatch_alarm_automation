import logging
from datetime import datetime, timedelta
from time import sleep
from src.utils import instance_search
import boto3
from botocore.exceptions import ClientError
from dateutil.tz import tzlocal
import json
from src.config import config

logging.basicConfig(level=config.LOGLEVEL)
logger = logging.getLogger(__name__)

session = boto3.Session(region_name=config.REGION_NAME)


class CloudWatchAgentInstaller(object):
    def __init__(self):
        self._ssm_client = session.client('ssm')
        self._ec2 = session.resource('ec2')
        self._param_name = config.CWAC_PARAMETER_NAME
        self._cwa_config = config.CWA_CONFIG
        self._tag = config.MANAGE_TAG
        self._ping_timeout_in_minutes = config.SSMA_PING_TIMEOUT_IN_MINUTES

    # 保存 CW Agent 参数到 SSM, 如果已存在则覆盖
    def cwa_para_write(self):
        try:
            # overwrite 情况下不能打 tag
            response = self._ssm_client.put_parameter(
                Name=self._param_name,
                Description='Stored by Python script',
                Type='String',
                Overwrite=True,
                Value=json.dumps(self._cwa_config)
            )
            logger.info('成功存储参数: {}'.format(self._param_name))
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
        return response['Version']

    # 从有 tag 且正在运行的实例中, 筛选近 10 分钟有心跳的
    def _ssma_status_check(self):
        managed_instances = instance_search(self._tag, ['running'])
        instance_ids = [instance.id for instance in managed_instances]
        logger.info('被管理实例列表: {}'.format(instance_ids))
        if instance_ids:
            try:
                filters = [{'Key': 'InstanceIds', 'Values': instance_ids}]
                instance_info_list = self._ssm_client.describe_instance_information(Filters=filters) \
                    .get('InstanceInformationList')
                delta = timedelta(minutes=self._ping_timeout_in_minutes)
                instance_ids = [i['InstanceId'] for i in instance_info_list
                                if (datetime.now(tzlocal()) < (i['LastPingDateTime'] + delta))]
                logger.info('其中活动的实例列表: {}'.format(instance_ids))
            except ClientError as error:
                print(error.response['Error']['Code'])
                raise error
        return instance_ids

    # 安装并配置 CW Agent
    def cwa_install(self):
        instance_ids = self._ssma_status_check()
        if instance_ids:
            try:
                # 通过 SSM send-command 安装 CW Agent
                response = self._ssm_client.send_command(
                    InstanceIds=instance_ids,
                    DocumentName="AWS-ConfigureAWSPackage",
                    Comment="Install CloudWatch Agent by Python script",
                    Parameters={
                        "action": ["Install"],
                        "installationType": ["Uninstall and reinstall"],
                        "additionalArguments": ["{}"],
                        "name": ["AmazonCloudWatchAgent"]
                    }
                )
            except ClientError as error:
                print(error.response['Error']['Code'])
                raise error
            command_id = response['Command']['CommandId']
            for instance_id in instance_ids:
                # 每 3 秒轮询一次结果, 100次(5分钟), 可能报 InvocationDoesNotExist 错误
                # 使用 waiter 也会报同样错误, 并且不方便捕获
                status, i = '', 0
                while status != 'Success' and i < 100:
                    try:
                        response = self._ssm_client.get_command_invocation(
                            CommandId=command_id,
                            InstanceId=instance_id
                        )
                        status = response.get('Status', '')
                    except ClientError as error:
                        if error.response['Error']['Code'] in ['InvocationDoesNotExist']:
                            continue
                        print(error.response['Error']['Code'])
                        raise error
                    sleep(3)
                if status != 'Success':
                    raise Exception('The configure command has not yet completed.')
                logger.info('成功安装 CW_Agent 到实例 {} '.format(instance_id))
                self.cwa_config(instance_id)
        return instance_ids

    # 配置 CW Agent
    def cwa_config(self, instance_id):
        try:
            # 通过 SSM send-command 配置 CW Agent
            response = self._ssm_client.send_command(
                InstanceIds=[instance_id],
                DocumentName="AmazonCloudWatch-ManageAgent",
                DocumentVersion="3",
                Comment="Config CloudWatch Agent by Python script",
                Parameters={
                    "action": ["configure"],
                    "mode": ["ec2"],
                    "optionalConfigurationSource": ["ssm"],
                    "optionalConfigurationLocation": [self._param_name],
                    "optionalRestart": ["yes"]}
            )
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
        # 等待命令执行, 有可能出现 plugin_name 错误
        command_id = response['Command']['CommandId']
        status, i = '', 0
        while status != 'Success' and i < 100:
            try:
                response = self._ssm_client.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance_id,
                    PluginName='ControlCloudWatchAgentLinux'
                )
                status = response.get('Status', '')
            except ClientError as error:
                if error.response['Error']['Code'] in ['InvocationDoesNotExist', 'InvalidPluginName']:
                    continue
                print(error.response['Error']['Code'])
                raise error
            sleep(3)
        if status != 'Success':
            raise Exception('The configure command has not yet completed.')
        logger.info('成功配置 CW_Agent 于实例 {} '.format(instance_id))
        return command_id
