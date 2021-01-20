"""" 工具类

"""
import logging

import boto3
from botocore.exceptions import ClientError

from src.config import config

logging.basicConfig(level=config.LOGLEVEL)
logger = logging.getLogger(__name__)

session = boto3.Session(region_name=config.REGION_NAME)


# 输入:
#   Name
#   Assume_Policy
#   Policy_List
# 输出:
#   role
def role_create(role_config):
    role_name = role_config.get('Name', '')
    assume_policy = role_config.get('Assume_Policy', '')
    policy_list = role_config.get('Policy_List', '')
    iam = session.resource('iam')
    role = iam.Role(role_name)
    # 如果不存在则创建 role
    if role not in iam.roles.all():
        try:
            role = iam.create_role(
                RoleName=role.role_name,
                AssumeRolePolicyDocument=assume_policy,
                Description='Create by cwa_install script'
            )
            # 最终一致性
            waiter = iam.meta.client.get_waiter('role_exists')
            waiter.wait(
                RoleName=role.role_name
            )
            logger.info('成功完成 role {} 创建.'.format(role.role_name))
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
    if policy_list:
        for policy_arn in policy_list:
            policy = iam.Policy(policy_arn)
            if policy not in role.attached_policies.all():
                try:
                    role.attach_policy(
                        PolicyArn=policy_arn
                    )
                    logger.info('成功绑定内置策略 {} 到角色 {}.'.format(
                        policy.policy_name, role.role_name
                    ))
                except ClientError as error:
                    print(error.response['Error']['Code'])
                    raise error
    return role


# 输入:
#   profile_name
# 输出:
#   instance_profile
# profile 容器创建, 会绑定同名 role
def instance_profile_create(profile_name):
    role_name = profile_name
    iam = session.resource('iam')
    role = iam.Role(role_name)
    instance_profile = iam.InstanceProfile(profile_name)
    # 如果不存在则创建 profile
    if instance_profile not in iam.instance_profiles.all():
        try:
            instance_profile = iam.create_instance_profile(
                InstanceProfileName=profile_name
            )
            waiter = iam.meta.client.get_waiter('instance_profile_exists')
            waiter.wait(
                InstanceProfileName=profile_name,
            )
            logger.info('成功完成 profile {} 创建.'.format(instance_profile.name))
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
    # 如果已有奇怪的 role 在 profile 内, 先删除之. 一个 profile 只能有一个 role
    if instance_profile.roles and instance_profile.roles[0].name != role.role_name:
        try:
            instance_profile.remove_role(instance_profile.roles[0].name)
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
    # 如果没有 role 在 profile 容器中, 添加 role
    if not instance_profile.roles:
        try:
            instance_profile.add_role(
                RoleName=role.role_name
            )
            logger.info('成功添加 role {} 到 profile {}.'.format(
                role.role_name, instance_profile.name
            ))
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
    return instance_profile


# 输入:
#   tag
#   state
# 输出:
#   managed_instances
# 查找已打标签并正在运行 / 已停止的 EC2 实例
def instance_search(tag=config.MANAGE_TAG, state=['running']):
    ec2 = session.resource('ec2')
    tag_key = tag.get('Key', '')
    tag_values, states = [], []
    tag_values.extend(tag.get('Values'))
    states.extend(state)
    filter_tag = {
        'Name': 'tag:{}'.format(tag_key),
        'Values': tag_values
    }
    filter_state = {
        'Name': 'instance-state-name',
        'Values': states
    }
    filters = [filter_state, filter_tag]
    managed_instances = ec2.instances.filter(Filters=filters)
    logger.info('已打标签的实例列表：{}'.format(
        [instance.id for instance in managed_instances]
    ))
    return managed_instances


# 创建 SNS topic, 订阅请自行创建
def topic_create(topic_name=config.SNS_TOPIC_NAME):
    sns = session.resource('sns')
    try:
        topics = sns.topics.all()
        # topic 没有 name 属性
        result = [t for t in topics if t.attributes.get('TopicArn', '').split(':')[-1:][0] == topic_name]
        # 如果没有就创建
        if not result:
            topic = sns.create_topic(
                Name=topic_name
            )
            logger.info('成功创建 SNS topic {}.'.format(topic.arn))
        else:
            topic = result.pop()
            logger.info('已有 topic {}.'.format(topic.arn))
    except ClientError as error:
        print(error.response['Error']['Code'])
        raise error
    return topic
