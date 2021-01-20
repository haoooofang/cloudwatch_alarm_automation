""""Lambda Function - 语音报警.

通过 Amazon Connect 呼叫运维人员手机，自动播放报警信息
"""

import logging
import os
from datetime import datetime
import json
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

global_region_name = os.environ.get('Region_Name', '')
instance_id = os.environ.get('Instance_Id', '')
parameter_name = os.environ.get('Parameter_Name', '')
contact_flow_id = os.environ.get('Contact_Flow_Id', '')
destination_number = os.environ.get('Destination_Number', '')
cn_region_name = os.environ['AWS_REGION']

if not global_region_name or not instance_id or not parameter_name or not contact_flow_id or not destination_number:
    raise Exception("Failed to get environment parameters.")

cn_session = boto3.Session(region_name=cn_region_name)

# 获得 AccessKey_Id/AccessKey_Secret
ssm_client = cn_session.client('ssm')
response = ssm_client.get_parameter(
    Name=parameter_name,
    WithDecryption=True
)
ak_sk = json.loads(response['Parameter']['Value'])


global_session = boto3.Session(
    region_name=global_region_name,
    aws_access_key_id=ak_sk.get('ak'),
    aws_secret_access_key=ak_sk.get('sk')
)
connect_client = global_session.client('connect')

response = connect_client.list_phone_numbers(
    InstanceId=instance_id
)
phone_number_list = [i.get('PhoneNumber') for i in response['PhoneNumberSummaryList']]


def handler(event, context):
    logger.info('## EVENT')
    logger.info(event)

    for record in event.get('Records', ''):
        logger.info('### Record')
        logger.info(record)
        message = json.loads(record['Sns']['Message'])
        aws_account_id = message['AWSAccountId']
        alarm_time = datetime.strptime(message['StateChangeTime'], '%Y-%m-%dT%H:%M:%S.%f%z')
        # \"StateChangeTime\":\"2020-10-07T10:45:05.905+0000\"
        region = message['Region']
        description = message['AlarmDescription']

        alarm_content = '<speak>'
        alarm_content += '我们遗憾的通知您，您的 AWS 账号：'
        alarm_content += '<say-as interpret-as="digits">'
        alarm_content += aws_account_id
        alarm_content += '</say-as>，'
        alarm_content += '在区域'
        alarm_content += '<lang xml:lang="en-US">'
        alarm_content += region
        alarm_content += '</lang>'
        alarm_content += '<break time="0.2s"/>于时间：'
        alarm_content += alarm_time.strftime('%Y年%m月%d日%H时%M分%S秒，')
        alarm_content += '触发了一个报警。警报内容为：'
        alarm_content += description
        alarm_content += '</speak>'
        logger.info('### Alarm Content')
        logger.info(alarm_content)

        # 使用 contact flow 而不是 outbound whisper flow
        try:
            connect_client.start_outbound_voice_contact(
                DestinationPhoneNumber=destination_number,
                ContactFlowId=contact_flow_id,
                InstanceId=instance_id,
                SourcePhoneNumber=phone_number_list.pop(),
                Attributes={
                    'alarm_content': alarm_content
                }
            )
            logger.info('### Call is made at {}'.format(datetime.isoformat(datetime.now())))
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
