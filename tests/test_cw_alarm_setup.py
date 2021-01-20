"""测试报警设置

"""
import boto3

from src.cloudwatch_alarm_setter import CloudWatchAlarmSetter
from src.connect_setter import ConnectSetter
from src.config import TestConfig as Config
from src.utils import topic_create

session = boto3.Session(region_name=Config.REGION_NAME)


def test_alarm_put():
    # setup
    ec2 = session.resource('ec2')
    subnet_id = list(ec2.subnets.all())[0].subnet_id
    image_id = 'ami-0b9e03ed3ef793940' if Config.REGION_NAME == 'cn-northwest-1' else 'ami-0f30329b403b2cd2f'
    instances = []
    for i in range(5):
        instance = ec2.create_instances(
            InstanceType='t3.nano',
            SubnetId=subnet_id,
            ImageId=image_id,
            MaxCount=1,
            MinCount=1,
        ).pop()
        instance.wait_until_running()
        instances.append(instance)
    sns = session.resource('sns')
    cw = session.resource('cloudwatch')
    topics = sns.topics.all()
    result = [t for t in topics if t.attributes.get('TopicArn', '').split(':')[-1:][0] == Config.SNS_TOPIC_NAME]
    if result:
        result.pop().delete()
    topic = topic_create()
    cw_setter = CloudWatchAlarmSetter(topic)
    ak = ''
    sk = ''
    e164_number = ''
    params = {
        'ak': ak,
        'sk': sk,
        'e164_phone_number': e164_number,
        'topic': topic
    }
    connect_setter = ConnectSetter(params)
    connect_setter.sns_subscribe()
    for alarm in cw.alarms.all():
        alarm.delete()
    alarms = []

    # when world is clean
    cw_setter.ebs_disk_alarm_put()
    cw_setter.ec2_cpu_alarm_put()
    cw_setter.ec2_mem_alarm_put()
    cw_setter.ec2_net_alarm_put()
    cw_setter.ec2_net_anomaly_detection_put()

    # once more
    CloudWatchAlarmSetter(topic)
    alarms.extend(cw_setter.ebs_disk_alarm_put())
    alarms.extend(cw_setter.ec2_cpu_alarm_put())
    alarms.extend(cw_setter.ec2_mem_alarm_put())
    alarms.extend(cw_setter.ec2_net_alarm_put())
    alarms.extend(cw_setter.ec2_net_anomaly_detection_put())
    for alarm in alarms:
        alarm.set_state(
            StateValue='ALARM',
            StateReason='Test'
        )
        assert alarm.state_value == 'ALARM'
        break

    # teardown
    topic.delete()
    for alarm in alarms:
        alarm.delete()
    for instance in instances:
        instance.terminate()
