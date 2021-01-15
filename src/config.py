import logging
import json


class BaseConfig(object):
    # AWS 区域, 限 cn-northwest-1, cn-north-1
    REGION_NAME = 'cn-north-1'

    # CloudWatch 需要的 IAM Role
    _assume_policy = {
        "Version": "2008-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com.cn"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    CWA_ROLE_CONFIG = {
        'Name': 'CloudWatchAgentServerRole',
        'Assume_Policy': json.dumps(_assume_policy),
        'Policy_List': [
            'arn:aws-cn:iam::aws:policy/CloudWatchAgentServerPolicy',
            'arn:aws-cn:iam::aws:policy/AmazonSSMManagedInstanceCore'
        ]
    }

    # 通过此 tag 选择被管理的 EC2
    MANAGE_TAG = {
        'Key': 'Managed',
        'Values': ['Yes']
    }

    # 存储在 SSM Parameter Store 中的 CloudWatch Agent 参数名称
    CWAC_PARAMETER_NAME = 'CloudWatch-Agent-Configure'

    # 允许 SSM Agent 失联分钟数
    SSMA_PING_TIMEOUT_IN_MINUTES = 10

    # CloudWatch Agent 参考设置
    CWA_CONFIG = {
        "agent": {
            "metrics_collection_interval": 60,
            "run_as_user": "root"
        },
        "metrics": {
            "append_dimensions": {
                "InstanceId": "${aws:InstanceId}"
            },
            "metrics_collected": {
                "mem": {
                    "measurement": [
                        "mem_used_percent"
                    ],
                    "metrics_collection_interval": 60
                },
                "swap": {
                    "measurement": [
                        "swap_used_percent"
                    ],
                    "metrics_collection_interval": 60
                }
            }
        },
        "logs": {
            "logs_collected": {
                "files": {
                    "collect_list": [
                        {
                            "file_path": "/var/log/messages",
                            "log_group_name": "amazon-cloudwatch-agent",
                            "log_stream_name": "messages.log",
                            "timezone": "UTC"
                        },
                        {
                            "file_path": "/opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log",
                            "log_group_name": "amazon-cloudwatch-agent",
                            "log_stream_name": "amazon-cloudwatch-agent.log",
                            "timezone": "Local"
                        }
                    ]
                }
            },
            "log_stream_name": "cw_agent_ec2_logs",
            "force_flush_interval": 15
        }
    }

    # SNS 报警 Topic 名称
    SNS_TOPIC_NAME = 'CloudWatch-Alarms'

    # 存海外区域 AK/SK 的参数名
    AKSK_PARAMETER_NAME = 'Global-AccessKeySecretKey-Pair'

    # Amazon Connect 配置
    CONNECT_CONFIG = {
        'Region_Name': 'ap-northeast-1',
        'Instance_Id': '44f835ce-e848-4fc1-a251-022b6bcf87d2',
        'Attribute_Name': 'alarm_content'
    }

    # Amazon Connect Contact Flow content
    CONTACT_FLOW_CONTENT = {
        "Version": "2019-10-30",
        "StartAction": "c6ab0cc6-24e2-4519-a5a1-a99b0ab94d4e",
        "Actions": [
            {
                "Identifier": "806a6d97-dd49-4ce3-b3d8-34cf83dfb47a",
                "Parameters": {
                    "SSML": "$.Attributes.{}".format(CONNECT_CONFIG['Attribute_Name'])
                },
                "Transitions": {
                    "NextAction": "7cdafb0a-ab10-4e0d-aa95-e9c80dc12d05",
                    "Errors": [],
                    "Conditions": []
                },
                "Type": "MessageParticipant"
            },
            {
                "Identifier": "e14a0513-6ec4-4666-92e3-5abda0ceb063",
                "Type": "DisconnectParticipant",
                "Parameters": {},
                "Transitions": {}
            },
            {
                "Identifier": "7cdafb0a-ab10-4e0d-aa95-e9c80dc12d05",
                "Parameters": {"LoopCount": "2"},
                "Transitions": {
                    "NextAction": "e14a0513-6ec4-4666-92e3-5abda0ceb063",
                    "Errors": [],
                    "Conditions": [
                        {
                            "NextAction": "e14a0513-6ec4-4666-92e3-5abda0ceb063",
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["DoneLooping"]
                            }
                        },
                        {
                            "NextAction": "806a6d97-dd49-4ce3-b3d8-34cf83dfb47a",
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["ContinueLooping"]
                            }
                        }
                    ]
                },
                "Type": "Loop"
            },
            {
                "Identifier": "778d8127-cce4-4e3e-9d01-e6971b543bfe",
                "Parameters": {
                    "SSML": "<speak>您好，我是知语，来自于<lang xml:lang=\"en-US\">Amazon Connect</lang></speak>"
                },
                "Transitions": {
                    "NextAction": "7cdafb0a-ab10-4e0d-aa95-e9c80dc12d05",
                    "Errors": [],
                    "Conditions": []
                },
                "Type": "MessageParticipant"
            },
            {
                "Identifier": "c6ab0cc6-24e2-4519-a5a1-a99b0ab94d4e",
                "Parameters": {"TextToSpeechVoice": "Zhiyu"},
                "Transitions": {
                    "NextAction": "778d8127-cce4-4e3e-9d01-e6971b543bfe",
                    "Errors": [],
                    "Conditions": []
                },
                "Type": "UpdateContactTextToSpeechVoice"
            },
            {
                "Identifier": "f5c4308e-a367-478f-91b6-a56115c81169",
                "Parameters": {
                    "FlowLoggingBehavior": "Enabled"
                },
                "Transitions": {
                    "NextAction": "c6ab0cc6-24e2-4519-a5a1-a99b0ab94d4e",
                    "Errors": [],
                    "Conditions": []
                },
                "Type": "UpdateFlowLoggingBehavior"
            }
        ]
    }

    # Lambda 需要的 IAM role
    LAMBDA_ROLE_CONFIG = {
            'Name': 'LambdaFunctionCalloutExecutionRole',
            'Assume_Policy': json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "lambda.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole"
                        }
                    ]
                }
            ),
            'Policy_List': [
                'arn:aws-cn:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
                'arn:aws-cn:iam::aws:policy/AWSXRayDaemonWriteAccess'
            ]
        }

    # Lambda Function 名称
    LAMBDA_FUNCTION_NAME = 'fun-connect-outbound'


class DevConfig(BaseConfig):
    DEBUG = True
    LOGLEVEL = logging.DEBUG


class TestConfig(BaseConfig):
    LOGLEVEL = logging.DEBUG


class ProdConfig(BaseConfig):
    LOGLEVEL = logging.ERROR


config = DevConfig()
