"""IAM Role 创建测试

"""
import boto3

from src.config import TestConfig as Config
from src.utils import role_create
session = boto3.Session(region_name=Config.REGION_NAME)


def notest_role_creation():
    # setup
    iam = session.resource('iam')
    role = iam.Role(Config.CWA_ROLE_CONFIG['Name'])
    profile = iam.InstanceProfile(Config.CWA_ROLE_CONFIG['Name'])
    policy_list = Config.CWA_ROLE_CONFIG['Policy_List']
    if profile in iam.instance_profiles.all():
        profile.remove_role(
            RoleName=role.role_name
        )
    if role in iam.roles.all():
        for policy_arn in policy_list:
            role.detach_policy(PolicyArn=policy_arn)
        role.delete()

    # when role doesn't exist
    role = role_create(Config.CWA_ROLE_CONFIG)
    for policy_arn in policy_list:
        assert iam.Policy(policy_arn) in role.attached_policies.all()

    # when role exists already
    role = role_create(Config.CWA_ROLE_CONFIG)
    for policy_arn in policy_list:
        assert iam.Policy(policy_arn) in role.attached_policies.all()

    # teardown
    if profile in iam.instance_profiles.all():
        profile.remove_role(
            RoleName=role.role_name
        )
    for policy_arn in policy_list:
        role.detach_policy(PolicyArn=policy_arn)
    role.delete()
