"""KubeSphere专门测试问题集

基于实际KubeSphere知识库内容构造的评估问题，
用于测试RAG系统在KubeSphere相关问题上的表现。
"""

from typing import List
from dataclasses import dataclass


@dataclass
class KubeSphereTestQuestion:
    """KubeSphere测试问题"""
    question: str
    category: str  # 问题类别
    difficulty: str  # 难度等级
    expected_knowledge: str  # 期望知识点
    ground_truth_answer: str  # 标准答案
    specific_docs: List[str] = None  # 相关文档（可选）


class KubeSphereQuestionBank:
    """KubeSphere问题库"""

    @staticmethod
    def get_all_questions() -> List[KubeSphereTestQuestion]:
        """获取所有KubeSphere测试问题"""
        return [
            *KubeSphereQuestionBank.get_observability_questions(),
            *KubeSphereQuestionBank.get_deployment_questions(),
            *KubeSphereQuestionBank.get_architecture_questions(),
            *KubeSphereQuestionBank.get_notification_questions(),
            *KubeSphereQuestionBank.get_troubleshooting_questions(),
            *KubeSphereQuestionBank.get_configuration_questions(),
        ]

    @staticmethod
    def get_observability_questions() -> List[KubeSphereTestQuestion]:
        """可观测性相关问题"""
        return [
            KubeSphereTestQuestion(
                question="KubeSphere中的日志收集是如何实现的？",
                category="可观测性",
                difficulty="中等",
                expected_knowledge="KubeSphere日志收集架构和实现方式",
                ground_truth_answer="KubeSphere的日志收集通过Fluent Bit组件实现。Fluent Bit作为DaemonSet部署在集群中，负责从各个节点收集容器日志、系统日志等。收集的日志会被转发到Elasticsearch或其他日志存储系统中。KubeSphere提供了统一的日志查询界面，支持多种过滤条件，包括项目、工作负载、容器等维度的日志检索和分析。",
                specific_docs=["logging-alert-notifaction.md"]
            ),
            KubeSphereTestQuestion(
                question="什么是KubeSphere的可观测性三大支柱？",
                category="可观测性",
                difficulty="简单",
                expected_knowledge="监控、日志、链路追踪三大支柱的概念",
                ground_truth_answer="KubeSphere的可观测性基于三大支柱：1) 监控(Monitoring) - 通过Prometheus收集集群、节点、工作负载等各层面的监控指标；2) 日志(Logging) - 通过Fluent Bit收集和聚合容器日志、审计日志等；3) 链路追踪(Tracing) - 支持分布式链路追踪，帮助定位微服务调用链中的性能瓶颈。这三者结合为用户提供全方位的系统可观测能力。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere如何实现告警通知的？详细说明其架构和工作原理。",
                category="可观测性",
                difficulty="困难",
                expected_knowledge="Notification Manager架构、CRD定义、多租户通知机制",
                ground_truth_answer="KubeSphere通过Notification Manager实现告警通知。架构核心包括三个CRD：1) NotificationManager - 配置全局参数如镜像、副本数等；2) Config - 定义发送方配置，如邮件服务器、企业微信应用信息等；3) Receiver - 定义接收方信息，如邮件地址、微信群等。工作原理：Notification Manager监控CRD变更并动态重载配置，采用发送配置与接收配置分离的模式，支持全局和租户两种类型。告警消息根据namespace标签路由到相应Receiver，实现多租户通知隔离。",
                specific_docs=["logging-alert-notifaction.md"]
            ),
            KubeSphereTestQuestion(
                question="在KubeSphere中如何配置邮件告警通知？",
                category="可观测性",
                difficulty="中等",
                expected_knowledge="邮件通知配置步骤、Config和Receiver的使用",
                ground_truth_answer="配置邮件告警通知需要两个步骤：1) 创建Config资源定义邮件发送配置，包括SMTP服务器地址、端口、用户名密码等；2) 创建Receiver资源定义邮件接收配置，指定收件人邮箱地址。Config和Receiver通过标签选择器关联。管理员可以设置全局的Email Config，租户只需配置具体的接收邮箱即可完成邮件通知配置。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere的日志和告警功能对于DevOps有什么价值？",
                category="可观测性",
                difficulty="中等",
                expected_knowledge="可观测性在DevOps流程中的作用和价值",
                ground_truth_answer="日志和告警功能是DevOps流程中的关键组成部分：1) 及时发现问题 - 告警通知帮助运维团队第一时间发现系统异常；2) 快速定位问题 - 统一的日志收集和查询功能让问题排查更高效；3) 持续改进 - 通过日志分析识别系统瓶颈和优化点；4) 责任明确 - 支持多租户的通知机制确保问题能准确通知到责任人；5) 降低运维成本 - 自动化的监控告警减少人工巡检工作量。",
            ),
        ]

    @staticmethod
    def get_deployment_questions() -> List[KubeSphereTestQuestion]:
        """部署相关问题"""
        return [
            KubeSphereTestQuestion(
                question="如何在ARM版麒麟V10上部署KubeSphere？",
                category="部署安装",
                difficulty="困难",
                expected_knowledge="ARM环境下KubeSphere部署流程和注意事项",
                ground_truth_answer="在ARM版麒麟V10上部署KubeSphere需要以下步骤：1) 系统准备：配置LVM存储，创建PV、VG、LV并挂载到/data目录；2) 下载KubeKey：使用KubeKey v3.0.13版本，支持ARM架构；3) 配置集群：创建集群配置文件，指定ARM节点信息；4) 存储配置：由于KubeKey不支持自定义Containerd数据目录，需要通过软链接方式将/var/lib/containerd链接到/data/containerd；5) 执行部署：运行kk create cluster命令进行自动化部署。整个过程需要注意ARM架构的兼容性和存储路径配置。",
                specific_docs=["deploy-kubesphere-on-arm-kylin-v10.md"]
            ),
            KubeSphereTestQuestion(
                question="使用KubeKey部署KubeSphere的优势是什么？",
                category="部署安装",
                difficulty="中等",
                expected_knowledge="KubeKey工具的特点和优势",
                ground_truth_answer="KubeKey是KubeSphere官方的部署工具，具有以下优势：1) 一键部署 - 同时安装Kubernetes和KubeSphere，简化部署流程；2) 多架构支持 - 支持AMD64和ARM64架构；3) 高可用支持 - 自动配置多Master节点的高可用集群；4) 可扩展性 - 支持集群节点的动态添加和删除；5) 配置灵活 - 通过YAML文件灵活配置集群参数；6) 离线部署 - 支持离线环境部署；7) 版本管理 - 支持Kubernetes和KubeSphere版本的统一管理和升级。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere部署过程中如何配置存储？详细说明LVM配置步骤。",
                category="部署安装",
                difficulty="困难",
                expected_knowledge="LVM配置、PV、VG、LV创建和挂载过程",
                ground_truth_answer="LVM存储配置步骤如下：1) 创建物理卷：pvcreate /dev/vdb；2) 创建卷组：vgcreate data /dev/vdb；3) 创建逻辑卷：lvcreate -l 100%VG data -n lvdata（使用所有空间）；4) 格式化：mkfs.xfs /dev/mapper/data-lvdata；5) 创建挂载点：mkdir /data；6) 挂载：mount /dev/mapper/data-lvdata /data；7) 设置自动挂载：在/etc/fstab中添加挂载配置；8) 创建软链接：ln -s /data/containerd /var/lib/containerd，解决KubeKey不支持自定义Containerd数据目录的问题。",
                specific_docs=["deploy-kubesphere-on-arm-kylin-v10.md"]
            ),
            KubeSphereTestQuestion(
                question="KubeSphere最小化部署需要哪些系统资源？",
                category="部署安装",
                difficulty="简单",
                expected_knowledge="CPU、内存、磁盘等资源需求",
                ground_truth_answer="KubeSphere最小化部署的系统资源需求：1) CPU：至少4核（推荐8核）；2) 内存：至少8GB（推荐16GB）；3) 磁盘：系统盘至少40GB，数据盘至少100GB；4) 网络：各节点间网络互通，开放相应端口；5) 操作系统：支持Ubuntu 16.04+、CentOS 7.x+、RHEL 7.x+等Linux发行版。对于生产环境，建议使用更高配置以确保系统稳定运行。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere高可用集群部署的架构是怎样的？",
                category="部署安装",
                difficulty="中等",
                expected_knowledge="多节点集群架构、Master节点配置",
                ground_truth_answer="KubeSphere高可用集群架构包括：1) Master节点：至少3个奇数个Master节点，运行Kubernetes控制平面组件和KubeSphere控制器；2) Worker节点：运行应用工作负载；3) etcd集群：通常与Master节点部署在一起，形成分布式键值存储；4) 负载均衡：在Master节点前配置负载均衡器，实现API Server的高可用访问；5) 存储：配置共享存储或分布式存储确保数据持久化；6) 网络：配置Pod网络和Service网络，确保集群内部通信。这种架构确保任何单个节点故障都不会影响集群整体可用性。",
            ),
        ]

    @staticmethod
    def get_architecture_questions() -> List[KubeSphereTestQuestion]:
        """架构相关问题"""
        return [
            KubeSphereTestQuestion(
                question="KubeSphere作为容器编排平台的核心架构是什么？",
                category="架构设计",
                difficulty="中等",
                expected_knowledge="KubeSphere整体架构、与Kubernetes的关系",
                ground_truth_answer="KubeSphere是基于Kubernetes构建的容器编排平台，采用分层架构设计：1) 基础层：Kubernetes集群提供容器编排能力；2) 存储层：支持多种存储后端如Ceph、GlusterFS等；3) 网络层：基于Calico、Flannel等CNI实现；4) 服务层：包括DevOps、服务网格、多租户等核心功能模块；5) 接口层：提供Web控制台、API和CLI等多种交互方式；6) 应用层：支持应用商店、应用模板等。整体架构具有高可扩展性、模块化和云原生的特点。",
            ),
            KubeSphereTestQuestion(
                question="Notification Manager是如何实现多租户通知管理的？",
                category="架构设计",
                difficulty="困难",
                expected_knowledge="多租户架构、Config和Receiver分离模式、标签选择机制",
                ground_truth_answer="Notification Manager通过以下机制实现多租户通知管理：1) 配置分离：采用Config定义发送配置，Receiver定义接收配置的分离模式；2) 标签区分：使用type标签区分全局(global)、默认(default)和租户(tenant)类型的资源；3) 选择器关联：Receiver通过标签选择器选择对应的Config；4) 消息路由：根据告警消息的namespace标签将通知路由到相应租户的Receiver；5) 权限隔离：全局Receiver只能使用全局Config，租户Receiver可以使用租户Config和全局Config；6) 动态配置：通过监控CRD变更实现配置的动态更新。这种设计既保证了租户间的隔离，又实现了配置的灵活复用。",
                specific_docs=["logging-alert-notifaction.md"]
            ),
            KubeSphereTestQuestion(
                question="KubeSphere中CRD的作用是什么？举例说明。",
                category="架构设计",
                difficulty="中等",
                expected_knowledge="自定义资源定义的概念和在KubeSphere中的应用",
                ground_truth_answer="CRD（Custom Resource Definition）在KubeSphere中用于扩展Kubernetes API，定义自定义资源类型。主要作用：1) 功能扩展：为KubeSphere特有功能定义资源模型；2) 声明式管理：通过YAML文件管理复杂的业务逻辑；3) 控制器模式：配合Custom Controller实现自动化运维。典型例子：Notification Manager定义了三个CRD - NotificationManager用于配置通知管理器本身，Config定义通知渠道的发送配置，Receiver定义接收方信息。这些CRD使得告警通知系统可以通过Kubernetes原生的资源管理方式进行配置和操作。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere如何实现租户隔离？",
                category="架构设计",
                difficulty="困难",
                expected_knowledge="多租户架构、命名空间隔离、权限管理",
                ground_truth_answer="KubeSphere通过多层次机制实现租户隔离：1) 工作空间隔离：顶层抽象，包含多个项目和DevOps项目；2) 项目隔离：基于Kubernetes Namespace实现资源隔离；3) 网络隔离：通过Network Policy控制租户间网络访问；4) 存储隔离：支持租户专用存储类和存储配额；5) 权限隔离：基于RBAC的细粒度权限控制，支持平台、工作空间、项目三级权限；6) 资源隔离：通过Resource Quota限制租户资源使用；7) 监控隔离：租户只能查看自己的监控数据；8) 日志隔离：日志按租户进行过滤和展示。这种多维度隔离确保了租户间的安全性和独立性。",
            ),
        ]

    @staticmethod
    def get_notification_questions() -> List[KubeSphereTestQuestion]:
        """通知管理相关问题"""
        return [
            KubeSphereTestQuestion(
                question="Notification Manager定义了哪些CRD？每个CRD的作用是什么？",
                category="通知管理",
                difficulty="中等",
                expected_knowledge="NotificationManager、Config、Receiver三个CRD的定义和作用",
                ground_truth_answer="Notification Manager定义了三个核心CRD：1) NotificationManager：用于配置Notification Manager本身，包括镜像、副本数、volumes、亲和性、污点、资源配额等部署参数，同时定义发送通知所需的全局配置、接收者选择器和租户管理配置；2) Config：用于定义通知渠道发送方的配置信息，如邮件发送服务器设置、企业微信用于发送消息的APP信息、Slack的Webhook地址等；3) Receiver：用于定义通知渠道接收方的信息，如邮件接收地址、企业微信群聊、Slack频道等。这三个CRD协同工作，实现了灵活的多租户通知配置管理。",
                specific_docs=["logging-alert-notifaction.md"]
            ),
            KubeSphereTestQuestion(
                question="KubeSphere中全局Receiver和租户Receiver有什么区别？",
                category="通知管理",
                difficulty="中等",
                expected_knowledge="全局和租户级别的通知配置差异、标签区分方式",
                ground_truth_answer="全局Receiver和租户Receiver的区别：1) 标签区分：全局Receiver使用type: global标签，租户Receiver使用type: tenant标签；2) 权限范围：全局Receiver只能使用全局Config(type: default)，租户Receiver可以使用租户Config和全局Config；3) 消息接收：所有通知消息都会发送到全局Receiver，租户Receiver只接收对应namespace的消息；4) 管理权限：全局Receiver由集群管理员管理，租户Receiver由租户管理员管理；5) 配置复用：全局Config可以被所有租户复用，实现了配置共享和简化管理。",
            ),
            KubeSphereTestQuestion(
                question="如何在KubeSphere中配置企业微信告警通知？",
                category="通知管理",
                difficulty="中等",
                expected_knowledge="企业微信APP配置、通知渠道设置",
                ground_truth_answer="配置企业微信告警通知的步骤：1) 创建企业微信应用：在企业微信管理后台创建应用，获取CorpID、AgentID和Secret；2) 创建Config资源：定义企业微信的发送配置，包括API地址、CorpID、AgentID、Secret等信息；3) 创建Receiver资源：指定接收消息的用户或部门，可以通过toUser、toParty或toTag指定接收范围；4) 配置标签选择：Receiver通过标签选择器关联对应的企业微信Config；5) 测试验证：发送测试告警验证配置是否正确。企业微信通知支持文本、Markdown等多种消息格式。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere的通知消息是如何根据namespace进行路由的？",
                category="通知管理",
                difficulty="困难",
                expected_knowledge="消息路由机制、租户标签匹配、通知发送逻辑",
                ground_truth_answer="通知消息的namespace路由机制：1) 全局路由：所有通知消息都会发送到全局Receiver，无论namespace是否为空；2) namespace为空：消息只发送到全局Receiver；3) namespace非空：Notification Manager根据namespace查找待通知的租户列表，然后将消息发送到对应租户的Receiver；4) 租户匹配：通过namespace标签匹配机制确定消息应该路由到哪些租户Receiver；5) 标签选择：消息路由时会考虑Receiver的标签选择器配置，确保消息发送到正确的接收方；6) 多重发送：一条消息可能同时发送到多个Receiver，包括全局Receiver和多个租户Receiver。这种机制实现了灵活的多租户通知分发。",
                specific_docs=["logging-alert-notifaction.md"]
            ),
        ]

    @staticmethod
    def get_troubleshooting_questions() -> List[KubeSphereTestQuestion]:
        """故障排除问题"""
        return [
            KubeSphereTestQuestion(
                question="KubeSphere部署失败时应该如何排查？",
                category="故障排除",
                difficulty="中等",
                expected_knowledge="常见部署问题、日志查看方法、调试技巧",
                ground_truth_answer="KubeSphere部署失败的排查步骤：1) 检查系统资源：确认CPU、内存、磁盘空间是否满足最小要求；2) 验证网络连通性：检查节点间网络是否正常，防火墙设置是否正确；3) 查看部署日志：使用kubectl logs查看安装器和各组件的日志；4) 检查容器状态：使用kubectl get pods -A查看所有Pod状态，找出异常Pod；5) 验证配置文件：检查KubeKey配置文件语法是否正确；6) 检查依赖服务：确认Docker/Containerd、etcd等基础服务状态；7) 存储检查：验证存储类和持久卷是否正常；8) 重新部署：清理失败的安装，重新执行部署命令。",
            ),
            KubeSphereTestQuestion(
                question="Containerd数据目录空间不足时如何解决？",
                category="故障排除",
                difficulty="中等",
                expected_knowledge="软链接方案、目录迁移、存储扩展",
                ground_truth_answer="解决Containerd数据目录空间不足的方法：1) 停止服务：systemctl stop containerd；2) 创建新存储：挂载更大的磁盘到新目录如/data/containerd；3) 迁移数据：cp -a /var/lib/containerd/* /data/containerd/；4) 创建软链接：rm -rf /var/lib/containerd && ln -s /data/containerd /var/lib/containerd；5) 重启服务：systemctl start containerd；6) 验证功能：确认容器和镜像正常工作。注意：KubeKey不支持自定义Containerd数据目录，只能通过软链接方式解决。在部署前预先配置可以避免后期问题。",
                specific_docs=["deploy-kubesphere-on-arm-kylin-v10.md"]
            ),
            KubeSphereTestQuestion(
                question="KubeSphere中告警通知不生效应该检查哪些配置？",
                category="故障排除",
                difficulty="中等",
                expected_knowledge="通知配置排查、CRD状态检查、网络连通性验证",
                ground_truth_answer="告警通知不生效的排查清单：1) CRD配置检查：验证NotificationManager、Config、Receiver资源是否正确创建和配置；2) 标签匹配：检查Receiver的标签选择器是否正确匹配Config；3) 服务状态：确认notification-manager服务运行正常；4) 网络连通性：测试到邮件服务器、企业微信API等外部服务的网络连接；5) 认证信息：验证邮箱密码、企业微信Secret等认证信息是否正确；6) 告警规则：检查Prometheus告警规则是否触发；7) 日志分析：查看notification-manager日志排查具体错误；8) 权限验证：确认相关ServiceAccount具有必要权限。",
            ),
            KubeSphereTestQuestion(
                question="如何排查KubeSphere日志收集功能异常？",
                category="故障排除",
                difficulty="困难",
                expected_knowledge="日志组件状态、配置检查、网络和存储问题排查",
                ground_truth_answer="日志收集功能异常的排查方法：1) 组件状态检查：确认fluent-bit、elasticsearch、kibana等日志相关Pod运行正常；2) 配置验证：检查fluent-bit配置是否正确，输出目标是否配置正确；3) 存储检查：验证日志存储空间是否充足，elasticsearch存储是否正常；4) 网络连通性：测试fluent-bit到elasticsearch的网络连接；5) 权限验证：确认fluent-bit具有读取容器日志的权限；6) 日志路径：检查容器日志文件路径是否正确挂载；7) 过滤规则：验证日志过滤和解析规则是否正确；8) 索引模板：检查elasticsearch索引模板和映射配置；9) 查看组件日志：分析各日志组件的详细错误日志。",
            ),
        ]

    @staticmethod
    def get_configuration_questions() -> List[KubeSphereTestQuestion]:
        """配置管理问题"""
        return [
            KubeSphereTestQuestion(
                question="KubeKey配置文件中的关键参数有哪些？",
                category="配置管理",
                difficulty="中等",
                expected_knowledge="KubeKey配置文件结构、节点配置、组件设置",
                ground_truth_answer="KubeKey配置文件的关键参数包括：1) apiVersion和kind：定义配置文件版本和类型；2) metadata：配置集群名称等元信息；3) spec.hosts：定义集群节点信息，包括节点IP、用户名、密码、角色等；4) spec.roleGroups：定义节点角色分组，如etcd、master、worker；5) spec.controlPlaneEndpoint：配置负载均衡器地址和端口；6) spec.kubernetes：指定Kubernetes版本、容器运行时、网络插件等；7) spec.kubesphere：配置KubeSphere版本和功能组件启用状态；8) spec.registry：配置镜像仓库地址；9) spec.addons：定义需要安装的附加组件。正确配置这些参数确保集群部署成功。",
            ),
            KubeSphereTestQuestion(
                question="如何在KubeSphere中配置持久化存储？",
                category="配置管理",
                difficulty="中等",
                expected_knowledge="存储类配置、PV/PVC创建、动态存储供应",
                ground_truth_answer="KubeSphere持久化存储配置步骤：1) 创建存储类(StorageClass)：定义存储提供商、回收策略、卷绑定模式等参数；2) 配置存储后端：如Ceph、GlusterFS、NFS等，确保存储服务正常运行；3) 创建持久卷(PV)：手动创建或通过动态供应自动创建；4) 创建持久卷声明(PVC)：应用通过PVC申请存储资源；5) 应用绑定：在Pod或Deployment中引用PVC；6) 监控存储：通过KubeSphere控制台监控存储使用情况；7) 备份策略：配置存储数据备份和恢复机制。KubeSphere支持多种存储类型，建议根据业务需求选择合适的存储方案。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere集群节点的角色分配原则是什么？",
                category="配置管理",
                difficulty="中等",
                expected_knowledge="master节点、worker节点、etcd节点的职责分工",
                ground_truth_answer="KubeSphere集群节点角色分配原则：1) Master节点：运行Kubernetes控制平面组件(API Server、Controller Manager、Scheduler)和KubeSphere控制器，建议奇数个(3/5/7)确保高可用；2) Worker节点：运行业务工作负载，可根据业务需求弹性扩展；3) etcd节点：存储集群状态数据，通常与Master节点共置，独立部署时也需要奇数个；4) 边缘节点：可选，用于暴露服务到集群外部；5) 资源隔离：Master节点通常设置污点避免调度业务Pod；6) 网络考虑：确保节点间网络互通，Master节点需要稳定的网络连接；7) 存储规划：Master节点需要可靠存储，Worker节点根据业务需求配置。",
            ),
            KubeSphereTestQuestion(
                question="如何优化KubeSphere在ARM架构上的性能？",
                category="配置管理",
                difficulty="困难",
                expected_knowledge="ARM架构特点、性能调优、资源配置优化",
                ground_truth_answer="ARM架构上的KubeSphere性能优化策略：1) 镜像优化：使用ARM原生镜像，避免x86镜像转换带来的性能损失；2) 内存管理：ARM处理器内存带宽相对较低，合理设置Pod内存限制和节点内存预留；3) CPU调度：根据ARM处理器核心数量调整Kubernetes调度策略，设置合适的CPU资源限制；4) 存储优化：选择适合ARM架构的高性能存储方案，如NVMe SSD；5) 网络配置：选择轻量级网络插件，如Flannel，减少网络开销；6) 组件精简：禁用不必要的KubeSphere功能组件，减少资源消耗；7) 监控调优：调整监控采集频率，平衡监控精度与性能消耗；8) 节点规划：根据ARM处理器特性合理规划节点数量和规格。",
            ),
        ]

    @staticmethod
    def get_questions_by_category(category: str) -> List[KubeSphereTestQuestion]:
        """根据类别获取问题"""
        all_questions = KubeSphereQuestionBank.get_all_questions()
        return [q for q in all_questions if q.category == category]

    @staticmethod
    def get_questions_by_difficulty(difficulty: str) -> List[KubeSphereTestQuestion]:
        """根据难度获取问题"""
        all_questions = KubeSphereQuestionBank.get_all_questions()
        return [q for q in all_questions if q.difficulty == difficulty]

    @staticmethod
    def get_random_questions(count: int = 10) -> List[KubeSphereTestQuestion]:
        """随机获取指定数量的问题"""
        import random
        all_questions = KubeSphereQuestionBank.get_all_questions()
        return random.sample(all_questions, min(count, len(all_questions)))

    @staticmethod
    def get_quick_test_set() -> List[KubeSphereTestQuestion]:
        """获取快速测试集（平衡各类别和难度）"""
        return [
            # 简单问题
            KubeSphereTestQuestion(
                question="什么是KubeSphere？",
                category="基础概念",
                difficulty="简单",
                expected_knowledge="KubeSphere的定义和基本功能",
                ground_truth_answer="KubeSphere是一个开源的容器编排平台，基于Kubernetes构建。它提供了一个完整的企业级容器管理解决方案，包括多租户管理、DevOps、微服务治理、应用商店、可观测性(监控、日志、链路追踪)等功能。KubeSphere旨在简化Kubernetes的使用复杂度，为企业提供易用的云原生应用管理平台，支持混合云和多云部署场景。",
            ),
            KubeSphereTestQuestion(
                question="KubeSphere最小化部署需要哪些系统资源？",
                category="部署安装",
                difficulty="简单",
                expected_knowledge="CPU、内存、磁盘等资源需求",
                ground_truth_answer="KubeSphere最小化部署的系统资源需求：1) CPU：至少4核（推荐8核）；2) 内存：至少8GB（推荐16GB）；3) 磁盘：系统盘至少40GB，数据盘至少100GB；4) 网络：各节点间网络互通，开放相应端口；5) 操作系统：支持Ubuntu 16.04+、CentOS 7.x+、RHEL 7.x+等Linux发行版。对于生产环境，建议使用更高配置以确保系统稳定运行。",
            ),

            # 中等问题
            KubeSphereTestQuestion(
                question="KubeSphere中的日志收集是如何实现的？",
                category="可观测性",
                difficulty="中等",
                expected_knowledge="KubeSphere日志收集架构和实现方式",
                ground_truth_answer="KubeSphere的日志收集通过Fluent Bit组件实现。Fluent Bit作为DaemonSet部署在集群中，负责从各个节点收集容器日志、系统日志等。收集的日志会被转发到Elasticsearch或其他日志存储系统中。KubeSphere提供了统一的日志查询界面，支持多种过滤条件，包括项目、工作负载、容器等维度的日志检索和分析。",
            ),
            KubeSphereTestQuestion(
                question="如何在KubeSphere中配置邮件告警通知？",
                category="可观测性",
                difficulty="中等",
                expected_knowledge="邮件通知配置步骤、Config和Receiver的使用",
                ground_truth_answer="配置邮件告警通知需要两个步骤：1) 创建Config资源定义邮件发送配置，包括SMTP服务器地址、端口、用户名密码等；2) 创建Receiver资源定义邮件接收配置，指定收件人邮箱地址。Config和Receiver通过标签选择器关联。管理员可以设置全局的Email Config，租户只需配置具体的接收邮箱即可完成邮件通知配置。",
            ),
            KubeSphereTestQuestion(
                question="Notification Manager定义了哪些CRD？每个CRD的作用是什么？",
                category="通知管理",
                difficulty="中等",
                expected_knowledge="NotificationManager、Config、Receiver三个CRD的定义和作用",
                ground_truth_answer="Notification Manager定义了三个核心CRD：1) NotificationManager：用于配置Notification Manager本身，包括镜像、副本数、volumes、亲和性、污点、资源配额等部署参数，同时定义发送通知所需的全局配置、接收者选择器和租户管理配置；2) Config：用于定义通知渠道发送方的配置信息，如邮件发送服务器设置、企业微信用于发送消息的APP信息、Slack的Webhook地址等；3) Receiver：用于定义通知渠道接收方的信息，如邮件接收地址、企业微信群聊、Slack频道等。这三个CRD协同工作，实现了灵活的多租户通知配置管理。",
            ),

            # 困难问题
            KubeSphereTestQuestion(
                question="KubeSphere如何实现告警通知的？详细说明其架构和工作原理。",
                category="可观测性",
                difficulty="困难",
                expected_knowledge="Notification Manager架构、CRD定义、多租户通知机制",
                ground_truth_answer="KubeSphere通过Notification Manager实现告警通知。架构核心包括三个CRD：1) NotificationManager - 配置全局参数如镜像、副本数等；2) Config - 定义发送方配置，如邮件服务器、企业微信应用信息等；3) Receiver - 定义接收方信息，如邮件地址、微信群等。工作原理：Notification Manager监控CRD变更并动态重载配置，采用发送配置与接收配置分离的模式，支持全局和租户两种类型。告警消息根据namespace标签路由到相应Receiver，实现多租户通知隔离。",
            ),
            KubeSphereTestQuestion(
                question="如何在ARM版麒麟V10上部署KubeSphere？",
                category="部署安装",
                difficulty="困难",
                expected_knowledge="ARM环境下KubeSphere部署流程和注意事项",
                ground_truth_answer="在ARM版麒麟V10上部署KubeSphere需要以下步骤：1) 系统准备：配置LVM存储，创建PV、VG、LV并挂载到/data目录；2) 下载KubeKey：使用KubeKey v3.0.13版本，支持ARM架构；3) 配置集群：创建集群配置文件，指定ARM节点信息；4) 存储配置：由于KubeKey不支持自定义Containerd数据目录，需要通过软链接方式将/var/lib/containerd链接到/data/containerd；5) 执行部署：运行kk create cluster命令进行自动化部署。整个过程需要注意ARM架构的兼容性和存储路径配置。",
            ),
            KubeSphereTestQuestion(
                question="Notification Manager是如何实现多租户通知管理的？",
                category="架构设计",
                difficulty="困难",
                expected_knowledge="多租户架构、Config和Receiver分离模式、标签选择机制",
                ground_truth_answer="Notification Manager通过以下机制实现多租户通知管理：1) 配置分离：采用Config定义发送配置，Receiver定义接收配置的分离模式；2) 标签区分：使用type标签区分全局(global)、默认(default)和租户(tenant)类型的资源；3) 选择器关联：Receiver通过标签选择器选择对应的Config；4) 消息路由：根据告警消息的namespace标签将通知路由到相应租户的Receiver；5) 权限隔离：全局Receiver只能使用全局Config，租户Receiver可以使用租户Config和全局Config；6) 动态配置：通过监控CRD变更实现配置的动态更新。这种设计既保证了租户间的隔离，又实现了配置的灵活复用。",
            ),
        ]


# 便捷导出函数
def get_kubesphere_questions(count: int = None,
                           category: str = None,
                           difficulty: str = None) -> List[KubeSphereTestQuestion]:
    """获取KubeSphere测试问题

    Args:
        count: 问题数量，None表示获取所有匹配的问题
        category: 问题类别过滤
        difficulty: 难度过滤

    Returns:
        KubeSphere测试问题列表
    """
    if category:
        questions = KubeSphereQuestionBank.get_questions_by_category(category)
    elif difficulty:
        questions = KubeSphereQuestionBank.get_questions_by_difficulty(difficulty)
    else:
        questions = KubeSphereQuestionBank.get_all_questions()

    if count:
        import random
        questions = random.sample(questions, min(count, len(questions)))

    return questions


def get_quick_evaluation_questions() -> List[KubeSphereTestQuestion]:
    """获取快速评估问题集"""
    return KubeSphereQuestionBank.get_quick_test_set()


if __name__ == "__main__":
    # 示例用法
    print("=== KubeSphere测试问题库 ===")

    all_questions = KubeSphereQuestionBank.get_all_questions()
    print(f"总问题数: {len(all_questions)}")

    categories = set(q.category for q in all_questions)
    print(f"问题类别: {', '.join(categories)}")

    difficulties = set(q.difficulty for q in all_questions)
    print(f"难度等级: {', '.join(difficulties)}")

    print("\n=== 快速测试集示例 ===")
    quick_test = get_quick_evaluation_questions()
    for i, q in enumerate(quick_test[:3], 1):
        print(f"{i}. [{q.category}] {q.question}")
        print(f"   难度: {q.difficulty}")
        print(f"   期望知识: {q.expected_knowledge}")
        print()