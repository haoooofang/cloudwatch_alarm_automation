"""IAM Role 关联测试

"""
from time import sleep

import boto3
from src.utils import role_create
from src.config import TestConfig as Config
from src.iam_role_manger import IamRoleManger

session = boto3.Session(region_name=Config.REGION_NAME)


# 标记实例
def tag(instance, s):
    if s == 'create':
        instance.create_tags(
            Tags=[
                {
                    'Key': Config.MANAGE_TAG['Key'],
                    'Value': Config.MANAGE_TAG['Values'][0]
                },
            ]
        )
    elif s == 'delete':
        instance.delete_tags(
            Tags=[
                {
                    'Key': Config.MANAGE_TAG['Key'],
                    'Value': Config.MANAGE_TAG['Values'][0]
                },
            ]
        )


# 等待绑定完成
def wait_for(client, r):
    association_id = r['IamInstanceProfileAssociation']['AssociationId']
    association_state = r['IamInstanceProfileAssociation']['State']
    while association_state != 'associated':
        sleep(0.5)
        associations = client.describe_iam_instance_profile_associations(
            AssociationIds=[association_id]
        )
        if associations:
            association_state = associations['IamInstanceProfileAssociations'][0]['State']


def notest_role_association():
    # setup
    ec2 = session.resource('ec2')
    iam = session.resource('iam')
    ec2_client = ec2.meta.client
    subnet_id = list(ec2.subnets.all())[0].subnet_id
    image_id = 'ami-0b9e03ed3ef793940' if Config.REGION_NAME == 'cn-northwest-1' else 'ami-0f30329b403b2cd2f'
    instances = ec2.create_instances(
        InstanceType='t3.nano',
        SubnetId=subnet_id,
        ImageId=image_id,
        MaxCount=4,
        MinCount=4,
    )
    role_manager = IamRoleManger()
    instance_profiles = iam.instance_profiles.all()
    instance_profile = iam.InstanceProfile(Config.CWA_ROLE_CONFIG['Name'])
    role = role_create(Config.CWA_ROLE_CONFIG)

    # when incorrect profile is associated
    instance = instances[0]
    instance.wait_until_running()
    tag(instance, 'create')
    for p in instance_profiles:
        if p.name != Config.CWA_ROLE_CONFIG['Name']:
            response = ec2_client.associate_iam_instance_profile(
                IamInstanceProfile={'Name': p.name},
                InstanceId=instance.id
            )
            wait_for(ec2_client, response)
            break
    role_manager.instances_role_attach()
    for i in range(100):
        sleep(0.5)
    assert instance.iam_instance_profile['Arn'] == instance_profile.arn
    tag(instance, 'delete')

    # when correct profile is associated
    instance = instances[1]
    instance.wait_until_running()
    tag(instance, 'create')
    response = ec2_client.associate_iam_instance_profile(
        IamInstanceProfile={'Name': Config.CWA_ROLE_CONFIG['Name']},
        InstanceId=instance.id
    )
    wait_for(ec2_client, response)
    role_manager.instances_role_attach()
    assert instance.iam_instance_profile['Arn'] == instance_profile.arn
    tag(instance, 'delete')

    # no profile is associated
    instance = instances[2]
    instance.wait_until_running()
    tag(instance, 'create')
    role_manager.instances_role_attach()
    for i in range(100):
        sleep(0.5)
    assert instance.iam_instance_profile['Arn'] == instance_profile.arn
    tag(instance, 'delete')

    # no tag at all
    instance = instances[3]
    instance.wait_until_running()
    role_manager.instances_role_attach()
    assert instance.iam_instance_profile is None

    # teardown
    for instance in instances:
        instance.terminate()
    instance_profile.remove_role(RoleName=Config.CWA_ROLE_CONFIG['Name'])
    for policy_arn in Config.CWA_ROLE_CONFIG['Policy_List']:
        role.detach_policy(PolicyArn=policy_arn)
    role.delete()
    instance_profile.delete()
