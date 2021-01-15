import logging
from time import sleep
from src.utils import instance_search, role_create, instance_profile_create
import boto3
from botocore.exceptions import ClientError

from src.config import config

logging.basicConfig(level=config.LOGLEVEL)
logger = logging.getLogger(__name__)

session = boto3.Session(region_name=config.REGION_NAME)


class IamRoleManger(object):
    def __init__(self):
        self._iam = session.resource('iam')
        self._ec2 = session.resource('ec2')
        self._cwa_role_config = config.CWA_ROLE_CONFIG
        self._tag = config.MANAGE_TAG

    # 绑定在打有 Managed:Yes 标签，且正在运行 / 已停止的实例上
    def instances_role_attach(self):
        role = role_create(self._cwa_role_config)
        profile_name = role.role_name
        instance_profile = instance_profile_create(profile_name)
        instance_list = instance_search(tag=self._tag, state=['running', 'stopped'])
        for instance in instance_list:
            # ***如果 profile 不是 CloudWatchAgentServerRole，进行替换***
            if instance.iam_instance_profile and instance.iam_instance_profile['Arn'] != instance_profile.arn:
                logger.info('实例 {} 已有 role {} 绑定'.format(
                    instance.id,
                    instance.iam_instance_profile['Arn']
                ))
                # 虽然每个实例只能绑定一个 profile, 但可能也存在正在绑定/解绑的 profile
                filters = [
                    {
                        'Name': 'instance-id',
                        'Values': [instance.id]
                    },
                    {
                        'Name': 'state',
                        'Values': ['associated']
                    },
                ]
                associations = self._ec2.meta.client.describe_iam_instance_profile_associations(
                    Filters=filters
                )
                try:
                    # 直接替换只能是 running 状态
                    # response = self.__ec2_client.replace_iam_instance_profile_association(
                    #     IamInstanceProfile={
                    #         'Arn': iam_instance_profile_arn
                    #     },
                    #     AssociationId=associations['IamInstanceProfileAssociations'][0]['AssociationId']
                    # )
                    self._ec2.meta.client.disassociate_iam_instance_profile(
                        AssociationId=associations['IamInstanceProfileAssociations'][0]['AssociationId']
                    )
                    # logger.info('成功完成实例 {} role 替换, 现在 role 为 {}'.format(
                    #     response['IamInstanceProfileAssociation']['InstanceId'],
                    #     response['IamInstanceProfileAssociation']['IamInstanceProfile']['Arn']
                    # ))
                except ClientError as error:
                    print(error.response['Error']['Code'])
                    raise error
            # 已经是 CloudWatchAgentServerRole 就不处理了
            elif instance.iam_instance_profile and instance.iam_instance_profile['Arn'] == instance_profile.arn:
                continue
            # 当前没有 profile 绑定, 因为最终一致性, 可能报参数错误
            i = 0
            while i < 20:
                try:
                    response = self._ec2.meta.client.associate_iam_instance_profile(
                        IamInstanceProfile={
                            'Arn': instance_profile.arn
                        },
                        InstanceId=instance.id
                    )
                    logger.info('成功完成 role {} 绑定到实例 {}'.format(
                        response['IamInstanceProfileAssociation']['IamInstanceProfile']['Arn'],
                        response['IamInstanceProfileAssociation']['InstanceId']
                    ))
                except ClientError as error:
                    if error.response['Error']['Code'] in ['InvalidParameterValue']:
                        sleep(5)
                        continue
                    else:
                        print(error.response['Error']['Code'])
                        raise error
                break
        return instance_list
