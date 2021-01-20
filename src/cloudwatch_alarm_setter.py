"""CW告警设置

"""
import logging
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from src.config import config

logging.basicConfig(level=config.LOGLEVEL)
logger = logging.getLogger(__name__)

session = boto3.Session(region_name=config.REGION_NAME)


class CloudWatchAlarmSetter(object):
    def __init__(self, topic):
        self.topic = topic
        self._cw = session.resource('cloudwatch')
        self._metrics = self._metrics_get()

    # 得到 metrics 列表, 只收录近 3 小时有数据上报的 metrics
    def _metrics_get(self):
        # 首先取得 3 小时内有数据的 metrics
        try:
            metric_iterator = self._cw.metrics.filter(
                RecentlyActive='PT3H')
        except ClientError as error:
            print(error.response['Error']['Code'])
            raise error
        return metric_iterator

    # 确认近 10 分钟是否有数据上传
    def _metric_data_stat_get(self, metric):
        response = self._cw.meta.client.get_metric_statistics(
            Namespace=metric.namespace,
            MetricName=metric.metric_name,
            Dimensions=metric.dimensions,
            StartTime=datetime.utcnow() - timedelta(minutes=10),
            EndTime=datetime.utcnow(),
            Period=600,
            Statistics=[
                'Sum',
            ]
        )
        return response.get('Datapoints')

    # 告警配置1： 每分钟检查一次，如果 5 次检查中有 3 次，内存平均占用等于或超过 90% 则触发报警状态
    def ec2_mem_alarm_put(self):
        alarms = []
        alarm_description = '实例内存不足.'
        alarm_actions = self.topic.arn
        alarm_name_prefix = 'InsufficientMemory'
        namespace = 'CWAgent'
        metric_name = 'mem_used_percent'
        metrics = [m for m in self._metrics if m.namespace == namespace and m.metric_name == metric_name]
        for metric in metrics:
            # 10 分钟内没有过数据则跳过
            if not self._metric_data_stat_get(metric):
                continue
            instance_ids = [d.get('Value') for d in metric.dimensions if d.get('Name') == 'InstanceId']
            if instance_ids:
                instance_id = instance_ids.pop()
                alarm_name = alarm_name_prefix + '-' + instance_id
                try:
                    alarm = metric.put_alarm(
                        AlarmName=alarm_name,
                        AlarmDescription=alarm_description,
                        ActionsEnabled=True,
                        AlarmActions=[
                            alarm_actions,
                        ],
                        Dimensions=metric.dimensions,
                        Statistic='Average',
                        Period=60,
                        Unit='Percent',
                        EvaluationPeriods=5,
                        DatapointsToAlarm=3,
                        Threshold=90.0,
                        ComparisonOperator='GreaterThanOrEqualToThreshold'
                    )
                    logger.info('成功添加或更新 Alarm {}.'.format(alarm.alarm_name))
                    alarms.append(alarm)
                except ClientError as error:
                    print(error.response['Error']['Code'])
                    raise error
        return alarms

    # 告警配置2： 每 2 分钟检查一次，如果 3 次检查中有 2 次 CPUCreditBalance 平均低于或等于 5 则触发报警状态
    def ec2_cpu_alarm_put(self):
        alarms = []
        alarm_description = 'T 系列实例 CPU 信用余额不足.'
        alarm_actions = self.topic.arn
        alarm_name_prefix = 'CPUCreditBalance'
        namespace = 'AWS/EC2'
        metric_name = 'CPUCreditBalance'
        metrics = [m for m in self._metrics if m.namespace == namespace and m.metric_name == metric_name]
        for metric in metrics:
            # 10 分钟内没有过数据则跳过
            if not self._metric_data_stat_get(metric):
                continue
            instance_ids = [d.get('Value') for d in metric.dimensions if d.get('Name') == 'InstanceId']
            if instance_ids:
                instance_id = instance_ids.pop()
                alarm_name = alarm_name_prefix + '-' + instance_id
                try:
                    alarm = metric.put_alarm(
                        AlarmName=alarm_name,
                        AlarmDescription=alarm_description,
                        ActionsEnabled=True,
                        AlarmActions=[
                            alarm_actions,
                        ],
                        Dimensions=metric.dimensions,
                        Statistic='Average',
                        Period=120,
                        Unit='Count',
                        EvaluationPeriods=3,
                        DatapointsToAlarm=2,
                        Threshold=5,
                        ComparisonOperator='LessThanOrEqualToThreshold'
                    )
                    logger.info('成功添加或更新 Alarm {}.'.format(alarm.alarm_name))
                    alarms.append(alarm)
                except ClientError as error:
                    print(error.response['Error']['Code'])
                    raise error
        return alarms

    # 告警配置3： 每分钟检查一次，如果 5 检查中有 2 次，磁盘 BurstBalance 等于或低于 10% 则触发报警
    def ebs_disk_alarm_put(self):
        alarms = []
        alarm_description = 'gp2 类型 SSD 突发余额不足.'
        alarm_actions = self.topic.arn
        alarm_name_prefix = 'EBSBurstBalance'
        namespace = 'AWS/EBS'
        metric_name = 'BurstBalance'
        metrics = [m for m in self._metrics if m.namespace == namespace and m.metric_name == metric_name]
        for metric in metrics:
            # 10 分钟内没有过数据则跳过
            if not self._metric_data_stat_get(metric):
                continue
            volume_ids = [d.get('Value') for d in metric.dimensions if d.get('Name') == 'VolumeId']
            if volume_ids:
                volume_id = volume_ids.pop()
                alarm_name = alarm_name_prefix + '-' + volume_id
                try:
                    alarm = metric.put_alarm(
                        AlarmName=alarm_name,
                        AlarmDescription=alarm_description,
                        ActionsEnabled=True,
                        AlarmActions=[
                            alarm_actions,
                        ],
                        Dimensions=metric.dimensions,
                        Statistic='Average',
                        Period=60,
                        Unit='Percent',
                        EvaluationPeriods=5,
                        DatapointsToAlarm=2,
                        Threshold=10,
                        ComparisonOperator='LessThanOrEqualToThreshold'
                    )
                    logger.info('成功添加或更新 Alarm {}.'.format(alarm.alarm_name))
                    alarms.append(alarm)
                except ClientError as error:
                    print(error.response['Error']['Code'])
                    raise error
        return alarms

    # 告警配置4：每 5 分钟检查一次，如果 3 次检查中有 1 次，NetworkIn/NetworkOut 合计等于或高于 10M bps 则触发报警
    def ec2_net_alarm_put(self):
        alarms = []
        alarm_description = '网络流量超出.'
        alarm_actions = self.topic.arn
        alarm_name_prefix = 'NetThroughput'
        namespace = 'AWS/EC2'
        metric_names = ('NetworkIn', 'NetworkOut')
        metrics = [m for m in self._metrics if m.namespace == namespace and m.metric_name == metric_names[0]]
        for metric in metrics:
            # 10 分钟内没有过数据则跳过
            if not self._metric_data_stat_get(metric):
                continue
            instance_ids = [d.get('Value') for d in metric.dimensions if d.get('Name') == 'InstanceId']
            if instance_ids:
                instance_id = instance_ids.pop()
                alarm_name = alarm_name_prefix + '-' + instance_id
                try:
                    self._cw.meta.client.put_metric_alarm(
                        AlarmName=alarm_name,
                        AlarmDescription=alarm_description,
                        ActionsEnabled=True,
                        AlarmActions=[
                            alarm_actions,
                        ],
                        Metrics=[
                            {
                                'Id': 'in',
                                'MetricStat': {
                                    'Metric': {
                                        'Namespace': namespace,
                                        'MetricName': metric_names[0],
                                        'Dimensions': metric.dimensions
                                    },
                                    'Period': 300,
                                    'Stat': 'Sum',
                                    'Unit': 'Bytes'
                                },
                                'ReturnData': False,
                            },
                            {
                                'Id': 'out',
                                'MetricStat': {
                                    'Metric': {
                                        'Namespace': namespace,
                                        'MetricName': metric_names[1],
                                        'Dimensions': metric.dimensions
                                    },
                                    'Period': 300,
                                    'Stat': 'Sum',
                                    'Unit': 'Bytes'
                                },
                                'ReturnData': False,
                            },
                            {
                                'Id': 'combined',
                                'Expression': '(in + out)/300*8/1024/1024',
                                'Label': 'NetThroughput',
                                'ReturnData': True,
                                'Period': 300
                            }
                        ],
                        EvaluationPeriods=3,
                        DatapointsToAlarm=1,
                        Threshold=10,
                        ComparisonOperator='GreaterThanOrEqualToThreshold'
                    )
                    alarm = self._cw.Alarm(alarm_name)
                    logger.info('成功添加或更新 Alarm {}.'.format(alarm.alarm_name))
                    alarms.append(alarm)
                except ClientError as error:
                    print(error.response['Error']['Code'])
                    raise error
        return alarms

    # 告警配置5: 网络流量异常, 连续 2 个周期 (5*2 = 10分钟), 出站流量平均值波动超过 3 个标准差即报警
    # 不支持表达式
    def ec2_net_anomaly_detection_put(self):
        alarms = []
        alarm_description = '网络流量异常.'
        alarm_actions = self.topic.arn
        alarm_name_prefix = 'NetAnomalyDetection'
        namespace = 'AWS/EC2'
        metric_name = 'NetworkOut'
        metrics = [m for m in self._metrics if m.namespace == namespace and m.metric_name == metric_name]
        for metric in metrics:
            # 10 分钟内没有过数据则跳过
            if not self._metric_data_stat_get(metric):
                continue
            instance_ids = [d.get('Value') for d in metric.dimensions if d.get('Name') == 'InstanceId']
            if instance_ids:
                instance_id = instance_ids.pop()
                alarm_name = alarm_name_prefix + '-' + instance_id
                try:
                    self._cw.meta.client.put_metric_alarm(
                        AlarmName=alarm_name,
                        AlarmDescription=alarm_description,
                        ActionsEnabled=True,
                        AlarmActions=[
                            alarm_actions,
                        ],
                        Metrics=[
                            {
                                'Id': 'out',
                                'MetricStat': {
                                    'Metric': {
                                        'Namespace': namespace,
                                        'MetricName': metric_name,
                                        'Dimensions': metric.dimensions
                                    },
                                    'Period': 300,
                                    'Stat': 'Average',
                                    'Unit': 'Bytes'
                                },
                                'ReturnData': True,
                            },
                            {
                                "Id": "ad",
                                "Expression": "ANOMALY_DETECTION_BAND(out, 3)"
                            }
                        ],
                        EvaluationPeriods=2,
                        ThresholdMetricId="ad",
                        ComparisonOperator='LessThanLowerOrGreaterThanUpperThreshold'
                    )
                    alarm = self._cw.Alarm(alarm_name)
                    logger.info('成功添加或更新 Alarm {}.'.format(alarm.alarm_name))
                    alarms.append(alarm)
                except ClientError as error:
                    print(error.response['Error']['Code'])
                    raise error
        return alarms
