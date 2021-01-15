from time import sleep

import boto3
from src.utils import role_create
from src.config import TestConfig as Config
from src.cloudwatch_agent_installer import CloudWatchAgentInstaller
from src.iam_role_manger import IamRoleManger

session = boto3.Session(region_name=Config.REGION_NAME)


def notest_cwa_installation():
    # setup
    ec2 = session.resource('ec2')
    ssm = session.client('ssm')
    iam = session.resource('iam')
    filters = [
        {
            'Name': 'route.destination-cidr-block',
            'Values': ['0.0.0.0/0']
        },
        {
            'Name': 'route.state',
            'Values': ['active']
        }
    ]
    route_table = list(ec2.route_tables.filter(Filters=filters))[0]
    subnet_id = route_table.associations_attribute[0].get('SubnetId')
    image_id = 'ami-0b9e03ed3ef793940' if Config.REGION_NAME == 'cn-northwest-1' else 'ami-0f30329b403b2cd2f'
    instance = list(ec2.create_instances(
        InstanceType='t3.nano',
        SubnetId=subnet_id,
        ImageId=image_id,
        MaxCount=1,
        MinCount=1,
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': Config.MANAGE_TAG['Key'],
                        'Value': Config.MANAGE_TAG['Values'][0]
                    },
                ]
            }
        ]
    ))[0]
    instance.wait_until_running()
    cwa_installer = CloudWatchAgentInstaller()
    role_manager = IamRoleManger()
    cwa_installer.cwa_para_write()

    # when there isn't a role
    cwa_installer.cwa_install()
    instance_list = [i['InstanceId'] for i in ssm.describe_instance_information()['InstanceInformationList']]
    assert instance.id not in instance_list
    response = ssm.list_command_invocations(
        InstanceId=instance.id,
        Details=False
    )
    assert not response['CommandInvocations']

    # when everything goes well
    role = role_create(Config.CWA_ROLE_CONFIG)
    role_manager.instances_role_attach()
    filters = [{'Key': 'InstanceIds', 'Values': [instance.id]}]
    ping_status = ''
    while ping_status == '':
        instance_info_list = ssm.describe_instance_information(Filters=filters) \
            .get('InstanceInformationList')
        if instance_info_list:
            ping_status = instance_info_list[0].get('PingStatus', '')
        sleep(5)
    cwa_installer.cwa_install()
    response = ssm.list_command_invocations(
        InstanceId=instance.id,
        Details=False
    )
    assert len(response['CommandInvocations']) == 2
    assert response['CommandInvocations'][0]['Status'] == 'Success'
    assert response['CommandInvocations'][1]['Status'] == 'Success'

    # teardown
    ssm.delete_parameter(
        Name=Config.CWAC_PARAMETER_NAME
    )
    instance_profile = iam.InstanceProfile(Config.CWA_ROLE_CONFIG['Name'])
    instance_profile.remove_role(RoleName=role.role_name)
    for policy_arn in Config.CWA_ROLE_CONFIG['Policy_List']:
        role.detach_policy(PolicyArn=policy_arn)
    role.delete()
    instance_profile.delete()
    instance.terminate()
