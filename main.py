"""入口程序.

菜单选择，完成各项操作
"""
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.formatted_text import HTML
from src.cloudwatch_alarm_setter import CloudWatchAlarmSetter
from src.cloudwatch_agent_installer import CloudWatchAgentInstaller
from src.iam_role_manger import IamRoleManger
from src.connect_setter import ConnectSetter
from src.utils import topic_create
from src.config import config

if __name__ == '__main__':
    while True:
        result = radiolist_dialog(
            title="功能选择",
            text="选择您需要完成的功能：",
            values=[
                ("role_create_assoc", "1.生成和绑定IAM Role, 用于 SSM Agent"),
                ("cwa_install", "2.安装CloudWatch Agent, 用于收集内存/Swap指标"),
                ("cw_alarm_put", "3.CloudWatch报警设置, 包括 普通/多指标计算/异常检测"),
                ("voice_alarm_setup", "4.Amazon Connect语音报警设置, 需提供海外区域AK/SK"),
                ("exit", "0.退出程序")
            ]
        ).run()
        if result == "exit":
            exit(0)
        elif result == "role_create_assoc":
            role_manager = IamRoleManger()
            # 绑定 role 到 EC2 实例
            role_manager.instances_role_attach()
        elif result == "cwa_install":
            cwa_installer = CloudWatchAgentInstaller()
            # 写入 CloudWatch Agent 配置
            cwa_installer.cwa_para_write()
            # 安装并配置 CloudWatch Agent
            cwa_installer.cwa_install()
        elif result == "cw_alarm_put":
            # 先创建 SNS Topic
            topic = topic_create(config.SNS_TOPIC_NAME)
            cw_setter = CloudWatchAlarmSetter(topic)
            # 设置报警
            cw_setter.ebs_disk_alarm_put()
            cw_setter.ec2_cpu_alarm_put()
            cw_setter.ec2_mem_alarm_put()
            cw_setter.ec2_net_alarm_put()
            cw_setter.ec2_net_anomaly_detection_put()
        elif result == "voice_alarm_setup":
            def bottom_toolbar():
                return HTML('请输入 AWS 海外区域<b><style bg="ansired">Access Key/Secret Key</style></b>!')


            ak = prompt('请输入 Access Key:> ', bottom_toolbar=bottom_toolbar)
            sk = prompt('请输入 Secret Key (不会回显):> ', bottom_toolbar=bottom_toolbar, is_password=True)
            phone_number = prompt('请输入运维人员国内手机号码:> ')
            e164_phone_number = '+86' + phone_number[-11:]
            topic = topic_create(config.SNS_TOPIC_NAME)
            params = (
                {
                    'ak': ak,
                    'sk': sk,
                    'e164_phone_number': e164_phone_number,
                    'topic': topic
                }
            )
            connect_setter = ConnectSetter(params)
            connect_setter.sns_subscribe()
