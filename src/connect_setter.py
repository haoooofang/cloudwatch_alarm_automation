import json
from src.config import config
import boto3
import logging
from botocore.exceptions import ClientError
import os
from zipfile import ZipFile
from src.utils import role_create
import secrets
from time import sleep

logging.basicConfig(level=config.LOGLEVEL)
logger = logging.getLogger(__name__)

session = boto3.Session(region_name=config.REGION_NAME)


class ConnectSetter(object):
    # 输入:
    #   args -- ak, sk, e164_phone_number, topic
    def __init__(self, args):
        self._param_name = config.AKSK_PARAMETER_NAME
        self._env_params = config.CONNECT_CONFIG
        self._connect_instance_id = self._env_params['Instance_Id']
        self._contact_flow_content = config.CONTACT_FLOW_CONTENT
        self._role_config = config.LAMBDA_ROLE_CONFIG
        self._ak = args['ak']
        self._sk = args['sk']
        self._e164_phone_number = args['e164_phone_number']
        self._topic = args['topic']
        self._function_name = config.LAMBDA_FUNCTION_NAME
        self._sns = session.resource('sns')
        self._iam = session.resource('iam')
        self._ssm_client = session.client('ssm')
        self._lambda_client = session.client('lambda')
        self._connect_client = boto3.Session(
            region_name=self._env_params['Region_Name'],
            aws_access_key_id=self._ak,
            aws_secret_access_key=self._sk
        ).client('connect')

    # 写入 AKSK 到 Parameter Store
    def _parameter_put(self):
        ak_sk = json.dumps(
            {
                'ak': self._ak,
                'sk': self._sk
            }
        )
        try:
            self._ssm_client.put_parameter(
                Name=self._param_name,
                Description='AK/SK used with Amazon Connect.',
                Value=ak_sk,
                Type='SecureString',
                Overwrite=True
            )
            logger.info('成功存储参数: {}'.format(self._param_name))
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
        return self._param_name

    # 创建 Amazon Connect Contact Flow
    def _contact_flow_create(self):
        try:
            response = self._connect_client.create_contact_flow(
                InstanceId=self._connect_instance_id,
                Name='contact_flow_callout'+'_'+secrets.token_urlsafe(),
                Type='CONTACT_FLOW',
                Description='Contact Flow created by Python Script',
                Content=json.dumps(self._contact_flow_content)
            )
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
        return response.get('ContactFlowId', '')

    # 创建 Lambda Function
    def _function_create(self):
        param_name = self._parameter_put()
        response = self._ssm_client.get_parameter(
            Name=param_name,
            WithDecryption=True
        )
        param_arn = response.get('Parameter').get('ARN')
        self._env_params['Destination_Number'] = self._e164_phone_number
        self._env_params['Parameter_Name'] = param_name
        self._env_params['Contact_Flow_Id'] = self._contact_flow_create()
        role = role_create(self._role_config)
        # 添加或更新 inline policy , 增加 SSM Parameter 读权限
        try:
            policy_name = self._function_name
            role_policy = self._iam.RolePolicy(role.role_name, policy_name)
            policy_content = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:GetParameter"
                        ],
                        "Resource": param_arn
                    }
                ]
            }
            role_policy.put(
                PolicyDocument=json.dumps(policy_content)
            )
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
        fun_file_name = 'fun_outbound.py'
        zip_file_name = 'code.zip'
        with ZipFile(zip_file_name, 'w') as z:
            z.write(fun_file_name)
        with open(zip_file_name, 'rb') as f:
            content = f.read()
        os.remove(zip_file_name)
        for i in range(10):
            try:
                response = self._lambda_client.create_function(
                    FunctionName=self._function_name,
                    Runtime='python3.8',
                    Role=role.arn,
                    Handler='fun_outbound.handler',
                    Code={
                        'ZipFile': content
                    },
                    Description='Function created by Python script',
                    Timeout=10,
                    MemorySize=128,
                    Publish=True,
                    Environment={
                        'Variables': self._env_params
                    },
                    TracingConfig={
                        'Mode': 'Active'
                    }
                )
            except ClientError as error:
                if error.response['Error']['Code'] in ['InvalidParameterValueException']:
                    sleep(5)
                    continue
                else:
                    print(error.response['Error']['Code'])
                    raise error
            break
        return response.get('FunctionName'), response.get('FunctionArn')

    # 订阅 SNS Topic
    def sns_subscribe(self):
        function_name, function_arn = self._function_create()
        self._lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=secrets.token_urlsafe(),
            Action='lambda:InvokeFunction',
            Principal='sns.amazonaws.com',
            SourceArn=self._topic.arn
        )
        subscription = self._topic.subscribe(
            Protocol='lambda',
            Endpoint=function_arn,
            ReturnSubscriptionArn=False
        )
        return subscription
