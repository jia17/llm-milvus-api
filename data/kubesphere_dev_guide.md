# KubeSphere扩展开发指南

本文档来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/

---

# 打包发布

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/packaging-and-release/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/packaging-and-
release/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 打包发布

# 打包发布

  * [打包扩展组件](/extension-dev-guide/zh/packaging-and-release/packaging/)

如何打包 KubeSphere 扩展组件

  * [测试扩展组件](/extension-dev-guide/zh/packaging-and-release/testing/)

将扩展组件上架到 KubeSphere 扩展市场中进行测试

  * [发布扩展组件](/extension-dev-guide/zh/packaging-and-release/release/)

将扩展组件发布到 KubeSphere Marketplace

[ __](/extension-dev-guide/zh/examples/external-link-example/
"外部链接")[__](/extension-dev-guide/zh/packaging-and-release/packaging/ "打包扩展组件")



---

# KubeSphere API reference

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references/kubesphere-api/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/references/kubesphere-
api.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [参考资料](/extension-dev-
guide/zh/references/) > KubeSphere API reference

# KubeSphere API reference

开发扩展组件时，如果需要调用 KubeSphere LuBan 中的 API，请查看 [KubeSphere Enterprise API
Docs](https://docs.kubesphere.com.cn/reference/api/v4.0.0/introduction/)。

#### 1\. ServiceAccount

> 在 KubeSphere 中，ServiceAccount（服务账号）为运行在 Pod 中的进程提供身份。默认情况下，Pod 不挂载
> KubeSphere ServiceAccount，但可以创建自定义 ServiceAccount 以赋予不同的权限。 ServiceAccount
> 用于通过 KubeSphere API 进行身份验证、访问/管理KubeSphere API、以及通过角色访问控制（RBAC）配置访问权限。可以在
> Pod 中的 annotations 字段中指定 `kubesphere.io/serviceaccount-name:
> ServiceAccount`。

##### 1.1 创建ServiceAccount

    
    
    cat <<EOF | kubectl apply -f -
    apiVersion: kubesphere.io/v1alpha1
    kind: ServiceAccount
    metadata:
      name: sample
      namespace: default
    secrets: []
    EOF
    

> 查看ServiceAccount
    
    
    [root@ks ~]# kubectl get serviceaccounts.kubesphere.io -n default
    NAME     AGE
    sample   28s
    
    [root@ks ~]# kubectl get serviceaccounts.kubesphere.io sample -n default -o jsonpath={.secrets[].name}
    sample-lqmbj
    
    # 查看 ServiceAccount 绑定的 Secrets
    [root@ks ~]# kubectl get secrets $(kubectl get serviceaccounts.kubesphere.io sample -n default -o jsonpath={.secrets[].name}) -n default
    NAME           TYPE                                  DATA   AGE
    sample-lqmbj   kubesphere.io/service-account-token   1      3m8s
    
    # 获取 ServiceAccount 绑定 Secrets 中保存的 Token 
    [root@ks ~]# kubectl get secrets $(kubectl get serviceaccounts.kubesphere.io sample -n default -o jsonpath={.secrets[].name}) -n default -o jsonpath={.data.token} | base64 -d
    eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8va3MtY29uc29sZS5rdWJlc3BoZXJlLXN5c3RlbS5zdmM6MzA4ODAiLCJzdWIiOiJrdWJlc3BoZXJlOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6c2FtcGxlIiwiaWF0IjoxNzIxMzI0MTY2LCJ0b2tlbl90eXBlIjoic3RhdGljX3Rva2VuIiwidXNlcm5hbWUiOiJrdWJlc3BoZXJlOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6c2FtcGxlIn0.jmJq-va5mQGwtWnM8t8Z2aFsCG2yPCFhCzPu8YuGBss
    

##### 1.2 使用 ServiceAccount

> 在 Pod 中使用 ServiceAccount

**在** `metadata.annotations` **中设置** `kubesphere.io/serviceaccount-name:
<name>`

    
    
    cat <<EOF | kubectl apply -f -
    apiVersion: v1
    kind: Pod
    metadata:
      annotations:
        kubesphere.io/creator: admin
        kubesphere.io/imagepullsecrets: '{}'
        kubesphere.io/serviceaccount-name: sample   # <----- 设置 ServiceAccount
      name: sample-pod
      namespace: default
    spec:
      containers:
      - image: nginx
        imagePullPolicy: IfNotPresent
        name: container-5tkfmj
        ports:
        - containerPort: 80
          name: http-80
          protocol: TCP
        resources: {}
    EOF
    

**查看 Pod 的yaml资源清单**

> 注意：ServiceAccount 会被自动注入到 Pod 的资源清单中，ServiceAccount 中的 Secrets 会自动挂载到
> `/var/run/secrets/kubesphere.io/serviceaccount` 目录下
    
    
    spec:
      containers:
      - image: nginx
        imagePullPolicy: IfNotPresent
        name: container-5tkfmj
       ...
        volumeMounts:
        - mountPath: /var/run/secrets/kubesphere.io/serviceaccount
          name: kubesphere-service-account
          readOnly: true
      ...
      volumes:
        - name: kubesphere-service-account
          projected:
            defaultMode: 420
            sources:
            - secret:
                items:
                - key: token
                  path: token
                name: sample-lqmbj
    

> 在 Deployment 中使用 ServiceAccount

**在** `spec.template.metadata.annotations` **中设置**
`kubesphere.io/serviceaccount-name: <name>`

    
    
    cat <<EOF | kubectl apply -f -
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      labels:
        app: sample-deploy
      name: sample-deploy
      namespace: default
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: sample-deploy
      template:
        metadata:
          annotations:
            kubesphere.io/creator: admin
            kubesphere.io/imagepullsecrets: '{}'
            kubesphere.io/serviceaccount-name: sample       # <----- 设置 ServiceAccount
          labels:
            app: sample-deploy
        spec:
          containers:
          - image: nginx
            imagePullPolicy: IfNotPresent
            name: nginx
            ports:
            - containerPort: 80
              name: http-80
              protocol: TCP
            resources: {}
    EOF
    

> 同理，KubeSphere 会根据 `kubesphere.io/serviceaccount-name` 这个 annotation 自动注入
> ServiceAccount，并将 ServiceAccount 中生成的 Secrets 挂载到
> `/var/run/secrets/kubesphere.io/serviceaccount` 目录下

##### 1.3 使用 ServiceAccount 访问 KubeSphere API

> 使用 KubeSphere Go SDK `kubesphere.io/client-go` 访问 KubeSphere API
    
    
    package main
    
    import (
    	"context"
    	"fmt"
    
    	v1 "k8s.io/api/core/v1"
    
    	"kubesphere.io/client-go/kubesphere/scheme"
    	"kubesphere.io/client-go/rest"
    )
    
    func main() {
    	config, err := rest.InClusterConfig()
    	if err != nil {
    		fmt.Println(err)
    	}
    	if err = rest.SetKubeSphereDefaults(config); err != nil {
    		fmt.Println(err)
    	}
    	config.GroupVersion = &v1.SchemeGroupVersion
    	config.NegotiatedSerializer = scheme.Codecs.WithoutConversion()
    
    	c, err := rest.RESTClientFor(config)
    
    	if err != nil {
    		fmt.Println(err)
    	}
        
    	// 可访问 KubeSphere API，但是显示权限不够
    	resp, err := c.Get().AbsPath("/kapis/tenant.kubesphere.io/v1beta1/clusters").Do(context.Background()).Raw()
    	if err != nil {
    		fmt.Println(err)
    	} else {
    		fmt.Println(string(resp))
    	}
    }
    

> 使用 ServiceAccount Token 访问 KubeSphere API
    
    
    token=$(kubectl get secrets $(kubectl get serviceaccounts.kubesphere.io sample -n default -o jsonpath={.secrets[].name}) -n default -o jsonpath={.data.token} | base64 -d)
    
    [root@ks ~]# kubectl get svc ks-apiserver -n kubesphere-system -o jsonpath={.spec.clusterIP}
    10.233.56.50
    
    [root@ks ~]# curl --location 'http://10.233.56.50:80/kapis/tenant.kubesphere.io/v1beta1/clusters' \
    --header 'Accept: application/json, text/plain, */*' \
    --header "Authorization: Bearer $token"
    
    # 可访问 KubeSphere API 但是显示权限不够
    {
      "kind": "Status",
      "apiVersion": "v1",
      "metadata": {},
      "status": "Failure",
      "message": "clusters.tenant.kubesphere.io is forbidden: User \"kubesphere:serviceaccount:default:sample\" cannot list resource \"clusters\" in API group \"tenant.kubesphere.io\" at the cluster scope",
      "reason": "Forbidden",
      "details": {
        "group": "tenant.kubesphere.io",
        "kind": "clusters"
      },
      "code": 403
    }
    

##### 1.4 ServiceAccount 授权

> GlobalRole 授权
    
    
    cat <<EOF | kubectl apply -f -
    apiVersion: iam.kubesphere.io/v1beta1
    kind: GlobalRoleBinding
    metadata:
      labels:
        iam.kubesphere.io/role-ref: platform-admin
      name: sample-platform-admin
    roleRef:
      apiGroup: iam.kubesphere.io
      kind: GlobalRole
      name: platform-admin
    subjects:
    - apiGroup: kubesphere.io
      kind: ServiceAccount
      name: sample
      namespace: default
    EOF
    

> ClusterRole 授权
    
    
    cat <<EOF | kubectl apply -f -
    apiVersion: iam.kubesphere.io/v1beta1
    kind: ClusterRoleBinding
    metadata:
      labels:
        iam.kubesphere.io/role-ref: cluster-admin
      name: sample-cluster-admin
    roleRef:
      apiGroup: iam.kubesphere.io
      kind: ClusterRole
      name: cluster-admin
    subjects:
    - apiGroup: kubesphere.io
      kind: ServiceAccount
      name: sample
      namespace: default
    EOF
    

> Role 授权
    
    
    cat <<EOF | kubectl apply -f -
    apiVersion: iam.kubesphere.io/v1beta1
    kind: Role
    metadata:
      annotations:
        kubesphere.io/creator: system
        kubesphere.io/description: '{"zh": "管理项目中的所有资源。", "en": "Manage all resources
          in the project."}'
      name: admin
      namespace: default
    rules:
    - apiGroups:
      - '*'
      resources:
      - '*'
      verbs:
      - '*'
    
    ---
    apiVersion: iam.kubesphere.io/v1beta1
    kind: RoleBinding
    metadata:
      labels:
        iam.kubesphere.io/role-ref: admin
      name: sample-admin
      namespace: default
    roleRef:
      apiGroup: iam.kubesphere.io
      kind: Role
      name: admin
    subjects:
    - apiGroup: kubesphere.io
      kind: ServiceAccount
      name: sample
      namespace: default
    EOF
    

> WorkspaceRole 授权
    
    
    cat <<EOF | kubectl apply -f -
    apiVersion: iam.kubesphere.io/v1beta1
    kind: WorkspaceRoleBinding
    metadata:
      labels:
        iam.kubesphere.io/role-ref: system-workspace-admin
        kubesphere.io/workspace: system-workspace
      name: sample-admin
    roleRef:
      apiGroup: iam.kubesphere.io
      kind: WorkspaceRole
      name: system-workspace-admin
    subjects:
    - apiGroup: kubesphere.io
      kind: ServiceAccount
      name: sample
      namespace: default
    EOF
    

[__](/extension-dev-guide/zh/references/create-ks-project/ "create-ks-project
CLI reference")[__](/extension-dev-guide/zh/references/kubesphere-api-
concepts/ "KubeSphere API 概念")



---

# 解析 Hello World 扩展组件

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/quickstart/hello-world-
extension-anatomy/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [快速入门](/extension-dev-
guide/zh/quickstart/) > 解析 Hello World 扩展组件

# 解析 Hello World 扩展组件

在前一节中，您已学习如何在本地运行 KubeSphere Console 并成功加载扩展组件。现在，让我们深入了解它的工作原理。

加载 Hello World 扩展组件时，它执行了以下三个关键任务，这对于 KubeSphere 扩展组件的开发至关重要。

  1. 在顶部导航栏注册了一个菜单按钮，以方便用户快速访问该扩展组件的页面。
  2. 添加了独立的页面路由，当用户访问 `http://localhost:8000/hello-world` 时可以正确地渲染扩展组件页面。
  3. 实现了扩展组件的页面内容。

现在，让我们更详细地查看 Hello World 扩展组件的文件结构和源代码，以深入了解这些功能是如何实现的。

### 扩展组件的目录结构

    
    
    $ tree extensions/hello-world
    extensions/hello-world
    ├── Dockerfile
    ├── README.md
    ├── package.json
    └── src
        ├── App.jsx
        ├── index.js
        ├── locales
        │   ├── en
        │   │   ├── base.json
        │   │   └── index.js
        │   ├── index.js
        │   └── zh
        │       ├── base.json
        │       └── index.js
        └── routes
            └── index.js
    

### 扩展组件的基础信息

`package.json` 文件中包含了扩展组件的基础信息与 `Node.js` 元数据。

    
    
    {
      "name": "hello-world",
      "version": "1.0.0",
      "private": true,
      "description": "Hello World!",
      "homepage": "",
      "author": "",
      "main": "dist/index.js",
      "files": ["dist"],
      "dependencies": {}
    }
    

### 扩展组件功能点

通过 `src/index.js` 向 ks-console 注册[导航栏](/extension-dev-guide/zh/feature-
customization/menu/)按钮、[多语言](/extension-dev-guide/zh/feature-
customization/internationalization/)等配置信息。

    
    
    import routes from './routes';
    import locales from './locales';
    
    const menus = [
      {
        parent: 'topbar',
        name: 'hello-world',
        title: 'Hello World',
        icon: 'cluster',
        order: 0,
        desc: 'Hello World!',
        skipAuth: true,
        isCheckLicense: false,
      },
    ];
    
    const extensionConfig = {
      routes,
      menus,
      locales,
    };
    
    export default extensionConfig;
    

通过 `src/routes/index.js` 向 ks-console 注册[页面路由](/extension-dev-
guide/zh/feature-customization/route/)，访问该路由地址会渲染扩展组件的功能页面。

    
    
    import React from 'react';
    import App from '../App';
    
    export default [
      {
        path: '/hello-world',
        element: <App />,
      },
    ];
    

### 扩展组件功能实现

通过 `src/App.jsx` 实现具体的功能，例如：展示 `Hello World!` 字样。

    
    
    import React from 'react';
    import styled from 'styled-components';
    
    const Wrapper = styled.h3`
      margin: 8rem auto;
      text-align: center;
    `;
    
    export default function App() {
      return <Wrapper>Hello World!</Wrapper>;
    }
    

[__](/extension-dev-guide/zh/quickstart/hello-world-extension/ "创建 Hello World
扩展组件")[__](/extension-dev-guide/zh/feature-customization/ "扩展能力")



---

# 快速入门

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/quickstart/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/quickstart/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 快速入门

# 快速入门

本章节将帮助您快速搭建扩展组件开发环境，并创建一个简单的扩展组件，以便理解开发 KubeSphere 扩展组件的基本原理和流程。

  * [搭建开发环境](/extension-dev-guide/zh/quickstart/prepare-development-environment/)

介绍如何搭建扩展组件的开发环境

  * [创建 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension/)

演示如何创建示例扩展组件 Hello World，帮助您快速了解扩展组件开发流程

  * [解析 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/)

解读 Hello World 扩展组件的工作方式

[ __](/extension-dev-guide/zh/overview/development-process/
"扩展组件开发流程")[__](/extension-dev-guide/zh/quickstart/prepare-development-
environment/ "搭建开发环境")



---

# 扩展能力

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 扩展能力

# 扩展能力

KubeSphere 提供了许多灵活的定制方法，供扩展组件扩展 KubeSphere 本身的能力。

  * [UI 扩展](/extension-dev-guide/zh/feature-customization/extending-ui/)

介绍如何扩展 UI

  * [API 扩展](/extension-dev-guide/zh/feature-customization/extending-api/)

介绍如何扩展 API

  * [挂载位置](/extension-dev-guide/zh/feature-customization/menu/)

介绍如何设置扩展组件在 KubeSphere Web 控制台的挂载位置

  * [访问控制](/extension-dev-guide/zh/feature-customization/access-control/)

介绍如何控制扩展组件定制资源的访问权限

  * [国际化](/extension-dev-guide/zh/feature-customization/internationalization/)

介绍如何实现扩展组件前端国际化

  * [页面路由](/extension-dev-guide/zh/feature-customization/route/)

创建新的功能页面并设置路由

  * [为扩展组件分配 Ingress](/extension-dev-guide/zh/feature-customization/ingress/)

介绍如何为扩展组件分配独立的 Ingress 访问入口

  * [自定义扩展组件的 license](/extension-dev-guide/zh/feature-customization/license/)

介绍如何自定义扩展组件的 license

[ __](/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/ "解析
Hello World 扩展组件")[__](/extension-dev-guide/zh/feature-
customization/extending-ui/ "UI 扩展")



---

# 发布扩展组件

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/packaging-and-release/release/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/packaging-and-
release/release/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [打包发布](/extension-dev-
guide/zh/packaging-and-release/) > 发布扩展组件

# 发布扩展组件

完成扩展组件的打包、测试之后，您可以使用 ksbuilder 将扩展组件提交到 [KubeSphere
Marketplace](https://kubesphere.com.cn/marketplace/)。

## 创建 API key

  1. 在 [KubeSphere Cloud](https://kubesphere.cloud/) 注册一个账号。

  2. 访问 [KubeSphere Marketplace](https://kubesphere.com.cn/marketplace/)，点击**入驻扩展市场** ，签署协议，成为扩展组件服务商（即开发者）。

  3. 打开 [KubeSphere Cloud 账号设置](https://kubesphere.cloud/user/setting/)，点击**安全** > **创建令牌** ，勾选**扩展组件** ，点击**创建** 。 生成的令牌即为 Cloud API key, 格式如 `kck-1e63267b-cb3c-4757-b739-3d94a06781aa`. 请妥善保存。

![token](/extension-dev-guide/zh/packaging-and-release/release/cloud-
token.png?width=600px)

## 下载 ksbuilder

访问 [ksbuilder 仓库](https://github.com/kubesphere/ksbuilder/releases)，下载最新的
ksbuilder。

## 使用 ksbuilder 提交扩展组件

  1. 绑定 Cloud API key。
         
         ➜  ksbuilder login
         
         Enter API token: ****************************************
         Login Succeeded
         

  2. 提交扩展组件，示例如下。
         
         ➜  ksbuilder push /Users/stone/Downloads/alc-1.1.0.tgz
         
         push extension /Users/stone/Downloads/alc-1.1.0.tgz
         Extension pushed and submitted to KubeSphere Cloud, waiting for review
         

  3. 查看扩展组件的状态，提交后，状态应为 `submitted`。
         
         ➜  ksbuilder list
         
         ID                   NAME   STATUS   LATEST VERSION
         516955082294618939   alc    draft
         
         
         ➜  ksbuilder get alc
         
         Name:     alc
         ID:       516955082294618939
         Status:   draft
         
         SNAPSHOT ID          VERSION   STATUS      UPDATE TIME
         516955082311396155   1.1.0     submitted   2024-06-06 07:27:20
         

  4. 提交扩展组件后，即可在名为 kscloud-beta 的 Helm 仓库中搜索到扩展组件的安装包。方法如下：

4.1. 将名为 kscloud-beta 的 Helm 仓库添加到 Helm 配置中。

         
         ➜  helm repo add kscloud-beta https://beta.app.kubesphere.cloud && helm repo update kscloud-beta
         
         "kscloud-beta" already exists with the same configuration, skipping
         Hang tight while we grab the latest from your chart repositories...
         ...Successfully got an update from the "kscloud-beta" chart repository
         Update Complete. ⎈Happy Helming!⎈
         

4.2. 在 Helm 仓库中搜索扩展组件的 Helm Chart 包。

         
         ➜  helm search repo alc
         
         NAME            	CHART VERSION	APP VERSION	DESCRIPTION
         kscloud-beta/alc	1.1.0        	           	alc is an example extension
         

  5. 等待扩展组件审批通过，即状态从 `submitted` 变为 `active`。
         
         ➜  ksbuilder get alc
         
         Name:     alc
         ID:       516955082294618939
         Status:   draft
         
         SNAPSHOT ID          VERSION   STATUS      UPDATE TIME
         516955082311396155   1.1.0     submitted   2024-06-06 07:27:20
         

  6. 扩展组件审批通过后，即可在[扩展市场](https://kubesphere.com.cn/marketplace/)，以及 KubeSphere 控制台的扩展市场，订阅并安装该扩展组件。

## 重要说明

  * 使用 ksbuilder push 命令提交扩展组件时，若扩展组件 extension.yaml 的 icon 或 screenshots 引用了安装包中的文件，这些文件将会被上传到 Kubesphere Cloud 的对象仓库中，icon 或 screenshots 将会被替换为文件在对象仓库中的 HTTP URL。ksbuilder 将会重新打包之后提交。整个过程是自动的。

  * 替换后，扩展组件安装包大小不能超过 1 MB, 否则会提交失败。

[ __](/extension-dev-guide/zh/packaging-and-release/testing/
"测试扩展组件")[__](/extension-dev-guide/zh/videos/ "视频演示")



---

# 扩展组件开发案例

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/best-practice/develop-example/


    /* This is an example application to demonstrate parsing an ID Token.
    */
    package main
    
    import (
        "crypto/rand"
        "encoding/base64"
        "encoding/json"
        "io"
        "log"
        "net/http"
        "time"
    
        "github.com/coreos/go-oidc/v3/oidc"
        "golang.org/x/net/context"
        "golang.org/x/oauth2"
    )
    
    var (
        clientID     = "test"
        clientSecret = "fake"
    )
    
    func randString(nByte int) (string, error) {
        b := make([]byte, nByte)
        if _, err := io.ReadFull(rand.Reader, b); err != nil {
            return "", err
        }
        return base64.RawURLEncoding.EncodeToString(b), nil
    }
    
    func setCallbackCookie(w http.ResponseWriter, r *http.Request, name, value string) {
        c := &http.Cookie{
            Name:     name,
            Value:    value,
            MaxAge:   int(time.Hour.Seconds()),
            Secure:   r.TLS != nil,
            HttpOnly: true,
        }
        http.SetCookie(w, c)
    }
    
    func main() {
        ctx := context.Background()
    
        provider, err := oidc.NewProvider(ctx, "http://ks-console.kubesphere-system.svc:30880")
        if err != nil {
            log.Fatal(err)
        }
        oidcConfig := &oidc.Config{
            ClientID: clientID,
        }
        verifier := provider.Verifier(oidcConfig)
    
        config := oauth2.Config{
            ClientID:     clientID,
            ClientSecret: clientSecret,
            Endpoint:     provider.Endpoint(),
            RedirectURL:  "http://10.8.0.2:5556/auth/google/callback",
            Scopes:       []string{oidc.ScopeOpenID, "profile", "email"},
        }
    
        http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
            state, err := randString(16)
            if err != nil {
                http.Error(w, "Internal error", http.StatusInternalServerError)
                return
            }
            nonce, err := randString(16)
            if err != nil {
                http.Error(w, "Internal error", http.StatusInternalServerError)
                return
            }
            setCallbackCookie(w, r, "state", state)
            setCallbackCookie(w, r, "nonce", nonce)
    
            http.Redirect(w, r, config.AuthCodeURL(state, oidc.Nonce(nonce)), http.StatusFound)
        })
    
        http.HandleFunc("/auth/google/callback", func(w http.ResponseWriter, r *http.Request) {
            state, err := r.Cookie("state")
            if err != nil {
                http.Error(w, "state not found", http.StatusBadRequest)
                return
            }
            if r.URL.Query().Get("state") != state.Value {
                http.Error(w, "state did not match", http.StatusBadRequest)
                return
            }
    
            oauth2Token, err := config.Exchange(ctx, r.URL.Query().Get("code"))
            if err != nil {
                http.Error(w, "Failed to exchange token: "+err.Error(), http.StatusInternalServerError)
                return
            }
            rawIDToken, ok := oauth2Token.Extra("id_token").(string)
            if !ok {
                http.Error(w, "No id_token field in oauth2 token.", http.StatusInternalServerError)
                return
            }
            idToken, err := verifier.Verify(ctx, rawIDToken)
            if err != nil {
                http.Error(w, "Failed to verify ID Token: "+err.Error(), http.StatusInternalServerError)
                return
            }
    
            nonce, err := r.Cookie("nonce")
            if err != nil {
                http.Error(w, "nonce not found", http.StatusBadRequest)
                return
            }
            if idToken.Nonce != nonce.Value {
                http.Error(w, "nonce did not match", http.StatusBadRequest)
                return
            }
    
            oauth2Token.AccessToken = "*REDACTED*"
    
            resp := struct {
                OAuth2Token   *oauth2.Token
                IDTokenClaims *json.RawMessage // ID Token payload is just JSON.
            }{oauth2Token, new(json.RawMessage)}
    
            if err := idToken.Claims(&resp.IDTokenClaims); err != nil {
                http.Error(w, err.Error(), http.StatusInternalServerError)
                return
            }
            data, err := json.MarshalIndent(resp, "", "    ")
            if err != nil {
                http.Error(w, err.Error(), http.StatusInternalServerError)
                return
            }
            w.Write(data)
        })
    
        log.Printf("listening on http://%s/", "10.8.0.2:5556")
        log.Fatal(http.ListenAndServe("10.8.0.2:5556", nil))
    }
    



---

# 快速入门

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/quickstart/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/quickstart/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 快速入门

# 快速入门

本章节将帮助您快速搭建扩展组件开发环境，并创建一个简单的扩展组件，以便理解开发 KubeSphere 扩展组件的基本原理和流程。

  * [搭建开发环境](/extension-dev-guide/zh/quickstart/prepare-development-environment/)

介绍如何搭建扩展组件的开发环境

  * [创建 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension/)

演示如何创建示例扩展组件 Hello World，帮助您快速了解扩展组件开发流程

  * [解析 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/)

解读 Hello World 扩展组件的工作方式

[ __](/extension-dev-guide/zh/overview/development-process/
"扩展组件开发流程")[__](/extension-dev-guide/zh/quickstart/prepare-development-
environment/ "搭建开发环境")



---

# Flomesh Service Mesh (FSM) 示例

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/videos/flomesh-service-mesh/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/videos/flomesh-service-
mesh.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [视频演示](/extension-dev-
guide/zh/videos/) > Flomesh Service Mesh (FSM) 示例

# Flomesh Service Mesh (FSM) 示例

[ __](/extension-dev-guide/zh/videos/databend-playground/ "Databend Playground
示例")[__](/extension-dev-guide/zh/best-practice/ "经验分享")



---

# FAQ

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/FAQ/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/faq/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > FAQ

# FAQ

  * [扩展组件 vs 应用](/extension-dev-guide/zh/faq/01-difference/)

介绍扩展组件和应用的不同点

[ __](/extension-dev-guide/zh/best-practice/databend-playground/ "Databend
Playground 开发小记")[__](/extension-dev-guide/zh/faq/01-difference/ "扩展组件 vs 应用")



---

# 扩展能力

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 扩展能力

# 扩展能力

KubeSphere 提供了许多灵活的定制方法，供扩展组件扩展 KubeSphere 本身的能力。

  * [UI 扩展](/extension-dev-guide/zh/feature-customization/extending-ui/)

介绍如何扩展 UI

  * [API 扩展](/extension-dev-guide/zh/feature-customization/extending-api/)

介绍如何扩展 API

  * [挂载位置](/extension-dev-guide/zh/feature-customization/menu/)

介绍如何设置扩展组件在 KubeSphere Web 控制台的挂载位置

  * [访问控制](/extension-dev-guide/zh/feature-customization/access-control/)

介绍如何控制扩展组件定制资源的访问权限

  * [国际化](/extension-dev-guide/zh/feature-customization/internationalization/)

介绍如何实现扩展组件前端国际化

  * [页面路由](/extension-dev-guide/zh/feature-customization/route/)

创建新的功能页面并设置路由

  * [为扩展组件分配 Ingress](/extension-dev-guide/zh/feature-customization/ingress/)

介绍如何为扩展组件分配独立的 Ingress 访问入口

  * [自定义扩展组件的 license](/extension-dev-guide/zh/feature-customization/license/)

介绍如何自定义扩展组件的 license

[ __](/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/ "解析
Hello World 扩展组件")[__](/extension-dev-guide/zh/feature-
customization/extending-ui/ "UI 扩展")



---

# FAQ

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/FAQ.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/faq/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > FAQ

# FAQ

  * [扩展组件 vs 应用](/extension-dev-guide/zh/faq/01-difference/)

介绍扩展组件和应用的不同点

[ __](/extension-dev-guide/zh/best-practice/databend-playground/ "Databend
Playground 开发小记")[__](/extension-dev-guide/zh/faq/01-difference/ "扩展组件 vs 应用")



---

# 外部链接

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/examples/external-link-example/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/examples/external-link-
example/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [开发示例](/extension-dev-
guide/zh/examples/) > 外部链接

# 外部链接

本节介绍如何在扩展组件中打开外部链接。

### 前端扩展组件开发

首先，从 GitHub 克隆示例代码，并根据 [创建 Hello World 扩展组件](/extension-dev-
guide/zh/quickstart/hello-world-extension/) 的指导文档，进行项目创建、本地开发及调试。

    
    
    cd ~/kubesphere-extensions
    git clone https://github.com/kubesphere/extension-samples.git
    cp -r ~/kubesphere-extensions/extension-samples/extensions-frontend/extensions/external-link ~/kubesphere-extensions/ks-console/extensions
    

接下来详细介绍如何在扩展组件中实现打开外部链接。

文件路径：`~/kubesphere-extensions/ks-console/extensions/external-link/src/App.jsx`

    
    
    import React, { useEffect } from "react";
    import { useNavigate } from "react-router-dom";
    import { Loading } from "@kubed/components";
    
    const LINK = "https://dev-guide.kubesphere.io/";
    
    export default function App() {
      const navigate = useNavigate();
    
      useEffect(() => {
        window.open(LINK);
        navigate(-1, { replace: true });
      }, []);
    
      return <Loading className="page-loading" />;
    }
    

以上代码实现以下功能：

  1. 在浏览器的新标签页打开指定的外部链接。
  2. 返回到之前的页面路径。

虽然示例中使用的方法可以直接打开外部链接，但可能会导致之前页面的状态丢失。

另一种方法是在 `App.jsx` 中使用 `<a href={LINK} target="_blank">Open Link</a>`
或者通过按钮来打开外部链接。

![open-external-link](/extension-dev-guide/zh/examples/external-link-
example/open-external-link.gif?width=1200px)

[ __](/extension-dev-guide/zh/examples/third-party-component-integration-
example/ "Weave Scope")[__](/extension-dev-guide/zh/packaging-and-release/
"打包发布")



---

# Gatekeeper

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/examples/gatekeeper-extension/


    kind : ClusterRole
    rules:
      - apiGroups:
        - ""
        resources:
        - events
        verbs:
        - create
        - patch
      - apiGroups:
        - '*'
        resources:
        - '*'
        verbs:
        - get
        - list
        - watch
      - apiGroups:
          - 'apiextensions.k8s.io'
        resources:
          - 'customresourcedefinitions'
        verbs:
          - '*'
      - apiGroups:
          - 'config.gatekeeper.sh'
          - 'constraints.gatekeeper.sh'
          - 'expansion.gatekeeper.sh'
          - 'externaldata.gatekeeper.sh'
          - 'mutations.gatekeeper.sh'
          - 'status.gatekeeper.sh'
          - 'templates.gatekeeper.sh'
        resources:
          - '*'
        verbs:
          - '*'
      - apiGroups:
          - 'rbac.authorization.k8s.io'
        resources:
          - 'clusterroles'
          - 'clusterrolebindings'
        verbs:
          - 'create'
          - 'delete'
      - apiGroups:
          - ''
        resources:
          - 'namespaces'
        verbs:
          - 'patch'
          - 'update'
      - apiGroups:
          - 'rbac.authorization.k8s.io'
        resources:
          - 'clusterroles'
        verbs:
          - '*'
        resourceNames:
          - gatekeeper-manager-role
          - gatekeeper-admin-upgrade-crds   
      - apiGroups:
          - 'rbac.authorization.k8s.io'
        resources:
          - 'clusterrolebindings'
        verbs:
          - '*'
        resourceNames:
          - gatekeeper-manager-rolebinding
          - gatekeeper-admin-upgrade-crds
      - apiGroups:
          - 'policy'
        resources:
          - 'podsecuritypolicies'
        verbs:
          - '*'
        resourceNames:
          - gatekeeper-admin
      - apiGroups:
          - 'policy'
        resources:
          - 'podsecuritypolicies'
        verbs:
          - 'create'
      - apiGroups:
          - 'admissionregistration.k8s.io'
        resources:
          - 'mutatingwebhookconfigurations'
        verbs:
          - '*'
      - apiGroups:
          - 'admissionregistration.k8s.io'
        resources:
          - 'validatingwebhookconfigurations'
        verbs:
          - '*'
    
    
    
    ---
    kind: Role
    rules:
      - verbs:
          - '*'
        apiGroups:
          - '*'
        resources:
          - '*'
    



---

# 扩展组件概述

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/overview/overview/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-
guide/content/zh/overview/overview/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [概述](/extension-dev-
guide/zh/overview/) > 扩展组件概述

# 扩展组件概述

KubeSphere 的使命是构建一个专注于云原生应用的分布式操作系统。自 3.x
版本开始，我们陆续提供了一些可插拔的系统组件。然而，由于先前的架构限制，3.x 版本的可插拔组件并不完美。

为了改进这一状况，我们对扩展组件进行了全面重新定义。

### 什么是 KubeSphere 扩展组件？

KubeSphere 扩展组件是遵循 KubeSphere 扩展组件开发规范的 Helm Chart，用于扩展 KubeSphere 的功能，并利用
Helm 进行编排。

云原生领域的开发者无需再花费大量时间学习私有的应用编排方式。

可访问 [KubeSphere
Marketplace](https://kubesphere.com.cn/extensions/marketplace/) 搜索、安装已发布的扩展组件。

### KubeSphere 扩展组件有哪些功能？

KubeSphere 提供了全面的扩展 API，从前端 UI 到后端
API，几乎覆盖了每个部分，使得每个部分都可以进行个性化定制和功能增强。事实上，KubeSphere 的核心功能也是基于这些扩展 API 构建的。

使用扩展 API，可以实现以下功能：

  1. **在导航栏中插入新的菜单** ：可以在项目、集群、企业空间等管理页面的左侧导航栏中插入新的菜单按钮，以支持更多类型的资源管理。

  2. **在模块化的功能页面中插入新的入口** ：除了导航栏，KubeSphere 还提供了众多模块化的功能页面，以便轻松扩展。例如，通过卡片方式在用户首页添加新的扩展入口。

  3. **通过 iframe 嵌入外部页面** ：通过 iframe 技术将已有的第三方功能组件页面嵌入到 KubeSphere 中，有效地降低开发成本。

  4. **覆盖 KubeSphere 已有的页面路由** ：覆盖 KubeSphere 已有的页面路由，从而实现独有的业务逻辑，使 KubeSphere 更好地适应特定业务场景。

  5. **对 KubeSphere 的 API 进行扩展** ：扩展 KubeSphere 的后端 API，复用 KubeSphere 提供的认证和鉴权功能。

### 如何构建扩展组件？

开发扩展组件简单易上手，无需大量时间和精力。请参阅[开发流程](/extension-dev-guide/zh/overview/development-
process/)章节了解如何构建扩展组件。

### 如何寻求帮助？

如果您在开发扩展组件时遇到问题，请尝试在以下渠道获得帮助：

  * [Slack Channel](https://join.slack.com/t/kubesphere/shared_invite/zt-26fio5qz5-Zqv85_vBcBvxe5SXWOwBmw)

  * [GitHub Issue](https://github.com/kubesphere/kubesphere/issues/new/choose)

[ __](/extension-dev-guide/zh/overview/ "概述")[__](/extension-dev-
guide/zh/overview/frontend-extension-architecture/ "前端扩展机制")



---

# 视频演示

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/videos/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/videos/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 视频演示

# 视频演示

  * [开发 KubeSphere 扩展组件](/extension-dev-guide/zh/videos/develop-an-extension/)

介绍如何开发 KubeSphere 扩展组件

  * [OpenKruiseGame Dashboard 示例](/extension-dev-guide/zh/videos/openkruisegame-dashboard/)

介绍 OpenKruiseGame Dashboard 示例

  * [Databend Playground 示例](/extension-dev-guide/zh/videos/databend-playground/)

介绍 Databend Playground 示例

  * [Flomesh Service Mesh (FSM) 示例](/extension-dev-guide/zh/videos/flomesh-service-mesh/)

介绍 Flomesh Service Mesh 示例

[ __](/extension-dev-guide/zh/packaging-and-release/release/
"发布扩展组件")[__](/extension-dev-guide/zh/videos/develop-an-extension/ "开发
KubeSphere 扩展组件")



---

# 概述

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/overview/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/overview/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 概述

# 概述

## 为什么在 KubeSphere 4.0 引入扩展机制

自 2018 年 KubeSphere 混合多云容器管理平台诞生以来，已经发布了十几个版本，包括 3
个大版本。为了满足不断增长的用户需求，KubeSphere
集成了众多企业级功能，如多租户管理、多集群管理、DevOps、GitOps、服务网格、微服务、可观测性（包括监控、告警、日志、审计、事件、通知等）、应用商店、边缘计算、网络与存储管理等。

首先，尽管这些功能满足了用户在容器管理平台方面的基本需求，却引发了一些挑战，比如：

  * 版本发布周期较长：需要等待所有组件完成开发、测试，并通过集成测试。这导致了不必要的等待时间，使用户难以及时获得新功能和修复。
  * 响应不及时：KubeSphere 的组件难以单独迭代，因此社区和用户提出的反馈需要等待 KubeSphere 发布新版本才能解决。这降低了对用户反馈的快速响应能力。
  * 前后端代码耦合：尽管目前已能实现单独启用/禁用特定组件，但这些组件的前后端代码仍然耦合在一起，容易相互影响，架构上不够清晰和模块化。
  * 组件默认启用：部分组件默认启用，这可能会占用过多的系统资源，尤其对于没有相关需求的用户。

其次，云原生领域的创新非常活跃。通常在同一个领域存在多种选择，例如：

  * GitOps 用户可以选用 ArgoCD 或 FluxCD；
  * 服务网格用户可以选择 Istio 或 Linkerd 或其它实现；
  * 联邦集群管理可选择 Karmada、OCM 或 Clusternet；
  * 日志管理可以采用 Elasticsearch 或 Loki；
  * 边缘计算框架可使用 KubeEdge、OpenYurt 或 SuperEdge；
  * 存储和网络领域也提供了众多选择。

KubeSphere 通常会优先支持其中一种实现，但用户常常有对其它实现的需求。

此外，在使用 KubeSphere 的过程中，用户通常会面临以下问题：

  * 用户将自己的应用发布到 KubeSphere 后，应用的管理界面无法与 KubeSphere 控制台无缝集成，因而无法在 KubeSphere 内一体化管理自己的应用。通常需要用户自行配置应用的 Service，如 NodePort 或 LB，以便在新窗口中管理应用；
  * 由于无法与 KubeSphere 控制台集成，用户的应用无法充分利用 KubeSphere 提供的认证鉴权、多租户管理等平台级功能，安全性受到影响；
  * 用户需求多种多样，不同用户对相同功能的需求存在显著差异，有时甚至相互冲突。原有架构由于耦合式的组件集成方式，难以满足用户多样化的需求；
  * 如果用户希望通过向 KubeSphere 提交 PR 来满足自己的需求，通常需要了解完整的 KubeSphere 开发流程。这包括前后端开发、调试、安装、部署和配置等一系列问题，门槛相对较高；
  * 此外，提交了 PR 后，需要等待 KubeSphere 发布新版本才能使用；
  * 由于发布周期较长，许多用户会自行在 KubeSphere 上定制化自己的需求，逐渐脱离社区，违背了开源社区 “upstream first” 的理念，从长远来看，将无法享受到上游越来越多的功能。

## KubeSphere 4.0 扩展机制简介

为了应对上述各种问题，KubeSphere 在 4.0 版本引入了全新的微内核架构，代号为 “LuBan”：

  * 通过 LuBan，可以实现前后端功能的动态扩展。
  * KubeSphere 的核心组件被精简为 ks-core，使得默认安装的 KubeSphere 变得更加轻量。
  * KubeSphere 已有的众多组件都被拆分为单独的 KubeSphere 扩展组件。这些扩展组件可以单独进行迭代，用户可以自行选择安装哪些扩展组件，以打造符合其需求的 KubeSphere 容器管理平台。
  * 用户可以借助相对简单的扩展组件开发指南，开发自己的扩展组件以扩展 KubeSphere 的功能。
  * 通过 KubeSphere 扩展中心，统一管理各扩展组件。
  * 为了丰富 KubeSphere 扩展组件的生态系统，我们还提供了 KubeSphere Marketplace 扩展市场。用户可以将自己开发的扩展组件上架至 KubeSphere 扩展市场，供其他用户使用甚至赚取收益。

## KubeSphere LuBan 架构的优势

KubeSphere LuBan 架构的优势可以从多个角度分析，包括 KubeSphere 维护者、KubeSphere
贡献者、云原生应用开发商（ISV）和其它开源项目、以及 KubeSphere 用户：

  * 对于 KubeSphere 维护者：LuBan 架构引入的扩展机制使维护者能够更专注于开发 KubeSphere 核心功能，使 ks-core 变得更轻量化，同时可以提高版本发布速度。对于其它功能，由于采用扩展组件实现，这些组件可以独立迭代，更及时地满足用户需求。

  * 对于 KubeSphere 贡献者：扩展机制的引入使 ks-core 和其它 KubeSphere 扩展组件之间更松耦合，开发也更加容易上手。

  * 对于云原生应用开发商（ISV）和其它开源项目：KubeSphere LuBan 架构的扩展机制允许 ISV 和其它开源项目以较低的成本将其产品或项目顺利集成到 KubeSphere 生态系统中。例如，Karmada 和 KubeEdge 的开发者可以基于这一扩展机制开发适用于 KubeSphere 的自定义控制台。

  * 对于 KubeSphere 用户：用户可以自由选择启用哪些 KubeSphere 扩展组件，还能将自己的组件顺利集成到 KubeSphere 控制台中。随着 KubeSphere 扩展组件生态的不断丰富，用户可以在 KubeSphere 扩展市场中选择更多丰富的产品和服务，实现容器管理平台的高度个性化。

[ __](/extension-dev-guide/zh/ "KubeSphere 扩展组件开发指南")[__](/extension-dev-
guide/zh/overview/overview/ "扩展组件概述")



---

# 搭建开发环境

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/quickstart/prepare-development-environment/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/quickstart/prepare-
development-environment/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [快速入门](/extension-dev-
guide/zh/quickstart/) > 搭建开发环境

# 搭建开发环境

搭建开发环境，需要安装 KubeSphere Luban 和扩展组件开发所需的开发工具。

  * KubeSphere Luban：准备 K8s 集群并部署 KubeSphere Luban Helm Chart，为扩展组件提供基础的运行环境。
  * 开发工具：安装 [create-ks-project](https://github.com/kubesphere/create-ks-project) 和 [ksbuilder](https://github.com/kubesphere/ksbuilder) 用于初始化扩展组件项目、打包和发布扩展组件，你也可能需要用到以下开发工具 Node.js、Helm、kubectl 等。

## 安装 KubeSphere Luban

  1. 准备 Kubernetes 集群

KubeSphere Luban 在任何 Kubernetes 集群上均可安装。可以使用
[KubeKey](https://github.com/kubesphere/kubekey) 快速部署 K8s 集群。

         
         curl -sfL https://get-kk.kubesphere.io | sh -
         ./kk create cluster --with-local-storage  --with-kubernetes v1.31.0 --container-manager containerd  -y
         

在 K8s 集群中[安装 Helm](https://helm.sh/zh/docs/intro/install/)。

         
         curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
         

  2. 安装 KubeSphere Luban Helm Chart。
         
         helm upgrade --install -n kubesphere-system --create-namespace ks-core  https://charts.kubesphere.io/main/ks-core-1.1.0.tgz --set apiserver.nodePort=30881 --debug --wait
         

更多配置参数，请参考[KubeSphere Helm Chart
配置](https://docs.kubesphere.com.cn/v4.0/03-install-and-uninstall/01-install-
ks-core/#_%E9%AB%98%E7%BA%A7%E9%85%8D%E7%BD%AE)。

## 安装开发工具

除了 K8s 和 KubeSphere Luban 的环境搭建，开发主机上需要用到以下工具。

  1. 安装开发扩展组件所需的开发工具

     * `Node.js` 和 `Yarn` 用于扩展组件的前端开发：安装 [Node.js](https://nodejs.org/en/download/package-manager) v16.17+ 和 [Yarn](https://classic.yarnpkg.com/lang/en/docs/install) v1.22+。
     * `Helm` 和 `kubectl` 用于扩展组件的编排和 K8s 集群管理： 安装 [Helm](https://helm.sh/docs/intro/install/) v3.8+ 和 [kubectl](https://kubernetes.io/zh-cn/docs/tasks/tools/#kubectl) v1.23+。
     * `ksbuilder` 用于扩展组件的打包与发布： 下载 [ksbuilder](https://github.com/kubesphere/ksbuilder/releases) 并保存到可执行文件目录。
  2. 配置开发环境

复制 K8s 集群的 [kubeconfig](https://kubernetes.io/zh-
cn/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
配置文件到开发主机上，确保使用 kubectl 可以正常访问 K8s 集群。

         
         ➜  ~ kubectl -n kubesphere-system get po
         NAME                                     READY   STATUS    RESTARTS       AGE
         ks-apiserver-7c67b4577b-tqqmd            1/1     Running   0              10d
         ks-console-7ffb5954d8-qr8tx              1/1     Running   0              10d
         ks-controller-manager-758dc948f5-8n4ll   1/1     Running   0              10d
         

[__](/extension-dev-guide/zh/quickstart/ "快速入门")[__](/extension-dev-
guide/zh/quickstart/hello-world-extension/ "创建 Hello World 扩展组件")



---

# 挂载位置

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/menu/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/menu/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [扩展能力](/extension-dev-
guide/zh/feature-customization/) > 挂载位置

# 挂载位置

本章节介绍如何设置扩展组件在 KubeSphere Web 控制台的挂载位置。

### 可选挂载位置

扩展组件可以挂载到以下位置：

  * 顶部菜单栏

![](./top-menu.png)

  * 扩展组件菜单

在顶部菜单栏点击 ![](./grid.svg) 图标打开菜单。

![](./platform-menu.png)

  * 左侧导航栏

KubeSphere 在集群管理、企业空间管理、项目管理、用户和角色管理、以及平台设置页面提供左侧导航栏。集群管理页面的左侧导航栏如下图所示。

![](./navigation-menu.png)

### 设置挂载位置

在扩展组件前端源代码的入口文件（如 `src/index.js`）中的 `menus` 设置挂载位置，例如：

    
    
    const menus = [
      { 
        parent: 'global',
        name: 'hello-world',
        link: '/hellow-world',
        title: 'HELLO_WORLD',
        icon: 'cluster',
        order: 0,
        desc: 'HELLO_WORLD_DESC',
        authKey: 'hello',
        authAction: 'hello-view',
        skipAuth: true,
        isCheckLicense: false,
      }
    ];
    

参数| 描述  
---|---  
parent| 扩展组件的挂载位置，取值可以为：

  * **topbar** ：挂载到顶部菜单栏。
  * **global** ：挂载到扩展组件菜单。
  * **access** ：挂载到用户和角色管理页面左侧导航栏。
  * **cluster** ：挂载到集群管理页面左侧导航栏。
  * **workspace** ：挂载到企业空间管理页面左侧导航栏。
  * **project** ：挂载到项目管理页面左侧导航栏。
  * **platformSettings** ：挂载到平台设置页面左侧导航栏。

若要挂载到当前菜单的子菜单下，设置 parent 的路径为： `parent: 'cluster.xxxx.xxxx'`  
name| 扩展组件在菜单上的位置标识。菜单的权限校验默认以 name 作为 key。设置 authKey
以指定模块权限进行校验。有关更多信息，请参阅[访问控制](../access-control)。  
link| 扩展组件的跳转路径。目前仅对 `parent` 取值为 `global` 和 `topbar` 时有效。  
title| 扩展组件在菜单上显示的名称。请勿直接将参数值设置为硬编码的字符串，建议将参数值设置为词条的键，并通过 KubeSphere
提供的国际化接口实现多语言。有关更多信息，请参阅[国际化](../internationalization)。  
icon| 扩展组件在菜单上显示的图标的名称。  
order| 扩展组件在菜单上的排列位次，取值为 `0` 或正整数。若取值为 `0`，表示扩展组件在菜单首位。  
desc| 扩展组件在菜单上显示的描述文字，目前仅对 `parent` 取值为 `global`
时有效。请勿直接将参数值设置为硬编码的字符串，建议将参数值设置为词条的键，并通过 KubeSphere
提供的国际化接口实现多语言。有关更多信息，请参阅[国际化](../internationalization)。  
skipAuth| 是否跳过用户权限检查。有关更多信息，请参阅[访问控制](../access-control)。  
authKey| 配置权限过滤。有关更多信息，请参阅[访问控制](../access-control)。  
authAction| 配置权限项。有关更多信息，请参阅[访问控制](../access-control)。  
isCheckLicense| 是否检测扩展组件许可，默认为 false  
  
[ __](/extension-dev-guide/zh/feature-customization/extending-api/ "API
扩展")[__](/extension-dev-guide/zh/feature-customization/access-control/ "访问控制")



---

# 迁移指南

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/migration/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/migration/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 迁移指南

# 迁移指南

此章节包含从旧版本的 KubeSphere 迁移到新版本的相关信息。

  * [从 4.0 升级到 4.1.x](/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/)

如何从 4.0.0 升级到 4.1.x 版本

[ __](/extension-dev-guide/zh/faq/01-difference/ "扩展组件 vs 应用")[__](/extension-
dev-guide/zh/migration/4.0.0-to-4.1.x/ "从 4.0 升级到 4.1.x")



---

# 快速入门

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/quickstart.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/quickstart/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 快速入门

# 快速入门

本章节将帮助您快速搭建扩展组件开发环境，并创建一个简单的扩展组件，以便理解开发 KubeSphere 扩展组件的基本原理和流程。

  * [搭建开发环境](/extension-dev-guide/zh/quickstart/prepare-development-environment/)

介绍如何搭建扩展组件的开发环境

  * [创建 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension/)

演示如何创建示例扩展组件 Hello World，帮助您快速了解扩展组件开发流程

  * [解析 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/)

解读 Hello World 扩展组件的工作方式

[ __](/extension-dev-guide/zh/overview/development-process/
"扩展组件开发流程")[__](/extension-dev-guide/zh/quickstart/prepare-development-
environment/ "搭建开发环境")



---

# 创建 Hello World 扩展组件

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/quickstart/hello-world-extension/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/quickstart/hello-world-
extension/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [快速入门](/extension-dev-
guide/zh/quickstart/) > 创建 Hello World 扩展组件

# 创建 Hello World 扩展组件

本章节帮助您快速了解：

  * 如何初始化扩展组件开发项目。
  * 如何在本地运行 KubeSphere Console。
  * 如何对扩展组件进行调试。

### 前提条件

您需要提前搭建扩展组件开发环境。有关更多信息，请参阅[搭建开发环境](/extension-dev-guide/zh/quickstart/prepare-
development-environment/)。

KubeSphere 扩展组件前端开发需要使用 React。有关更多信息，请访问 [React 官方网站](https://reactjs.org)。

### 初始化扩展组件开发项目

  1. 执行以下命令初始化扩展组件开发项目：
         
         mkdir -p ~/kubesphere-extensions
         cd ~/kubesphere-extensions
         yarn add global create-ks-project
         yarn create ks-project ks-console
         

KubeSphere 扩展组件开发项目中包含了一个可以在本地运行的 KubeSphere Console。

  2. 执行以下命令创建 Hello World 扩展组件：
         
         cd ks-console
         yarn create:ext
         

根据命令提示，设置扩展组件的名称、显示名称、描述、作者和语言等基础信息，完成扩展组件创建。

         
         Extension Name hello-world
         Display Name Hello World
         Description Hello World!
         Author demo
         Language JavaScript
         Create extension [hello-world]? Yes
         

以上命令执行完成后将生成如下目录结构：

         
         kubesphere-extensions
         └── ks-console                   # 扩展组件前端开发项目目录
             ├── babel.config.js
             ├── configs
             │   ├── config.yaml
             │   ├── local_config.yaml               # KubeSphere Console 的配置文件
             │   ├── webpack.config.js               # 脚手架 Webpack 配置文件
             │   └── webpack.extensions.config.js    # 扩展组件前端打包 Webpack 配置文件
             ├── extensions                          # 扩展组件源代码目录
             │   └── hello-world                     # Hello World 扩展组件的源代码目录
             │       ├── Dockerfile
             │       ├── README.md
             │       ├── package.json
             │       └── src
             │           ├── App.jsx
             │           ├── index.js
             │           ├── locales
             │           └── routes
             ├── package.json
             ├── tsconfig.base.json
             ├── tsconfig.json
             └── yarn.lock
         

### 配置本地运行环境

在配置本地运行环境之前，请先搭建好开发环境，获取 KubeSphere API Server 的访问地址。

然后在 `local_config.yaml` 文件中进行如下配置。

    
    
    server:
      apiServer:
        url: http://172.31.73.3:30881 # ks-apiserver 的 IP 与端口地址
        wsUrl: ws://172.31.73.3:30881 # ks-apiserver 的 IP 与端口地址
    

### 本地运行 KubeSphere Console 并加载扩展组件

  1. 执行以下命令运行 KubeSphere Console：
         
         yarn dev
         

  2. 打开浏览器，访问 `http://localhost:8000`，并使用默认用户名 `admin` 和密码 `P@88w0rd` 登录 KubeSphere Console。

页面顶部导航栏将出现 `Hello World` 扩展组件的访问入口，点击 `Hello World` 将打开 Hello World 扩展组件的页面。

![demo-plugin-dashboard.png](/extension-dev-guide/zh/quickstart/hello-world-
extension/hello-world-extension-dashboard.png?width=1080px)

### 调试扩展组件

Hello World 扩展组件的源代码保存在 `~/kubesphere-extensions/ks-console/extensions/hello-
word/src` 目录中。

您可以将页面显示的字符串修改为 `Test!`，如下图所示：

![coding.png](/extension-dev-guide/zh/quickstart/hello-world-
extension/coding.png?width=1080px)

![preview.png](/extension-dev-guide/zh/quickstart/hello-world-
extension/preview.png?width=1080px)

### 了解更多

当前示例仅包含了前端扩展，展示了扩展组件的基础能力，[开发示例](/extension-dev-
guide/zh/examples/)这个章节包含了更多的例子提供参考。

[ __](/extension-dev-guide/zh/quickstart/prepare-development-environment/
"搭建开发环境")[__](/extension-dev-guide/zh/quickstart/hello-world-extension-
anatomy/ "解析 Hello World 扩展组件")



---

# 迁移指南

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/migration.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/migration/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 迁移指南

# 迁移指南

此章节包含从旧版本的 KubeSphere 迁移到新版本的相关信息。

  * [从 4.0 升级到 4.1.x](/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/)

如何从 4.0.0 升级到 4.1.x 版本

[ __](/extension-dev-guide/zh/faq/01-difference/ "扩展组件 vs 应用")[__](/extension-
dev-guide/zh/migration/4.0.0-to-4.1.x/ "从 4.0 升级到 4.1.x")



---

# 页面路由

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/route/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/route/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [扩展能力](/extension-dev-
guide/zh/feature-customization/) > 页面路由

# 页面路由

在基于 `React` 的开发中，如果应用包含多个页面，那必然需要为应用设置路由。简单理解，路由是访问路径与 React 组件的映射关系。
在扩展组件开发中，路由的使用方法如下：

## 路由定义

KubeSphere 4.0 的前端路由使用了 [react-router
V6](https://reactrouter.com/en/6.20.1)。为了更方便地实现路由注册，采用了 `Route Object`
的方式书写路由，示例如下：

    
    
    let routes = [
        {
          path: "/",
          element: <Layout />,
          children: [
            { index: true, element: <Home /> },
            {
              path: "/courses",
              element: <Courses />,
              children: [
                { index: true, element: <CoursesIndex /> },
                { path: "/courses/:id", element: <Course /> },
              ],
            },
            { path: "*", element: <NoMatch /> },
          ],
        },
      ];
    

某些情形下，需要向已存在的路由插入或替换新的路由。这种情况下，需要指定路由的父路由
`parentRoute`。比如若想在集群管理的左侧菜单添加一个新的路由，首先需要查找 ks console 源码中对应的路由定义。在
`packages/clusters/src/routes/index.tsx` 文件中找到了对应的代码，如下：

    
    
    const PATH = '/clusters/:cluster';
    
    const routes: RouteObject[] = [
      {
        path: '/clusters',
        element: <Clusters />,
      },
      {
        path: PATH,
        element: <BaseLayout />,
        children: [
          {
            element: <ListLayout />,
            path: PATH,
            children: [
              {
                path: `${PATH}/overview`,
                element: <Overview />,
              },
              ...
    

如果要在 `Overview` 这一层新增一个路由，可以按以下方式进行定义：

    
    
    const PATH = '/clusters/:cluster';
    
    export default [
      {
        path: `${PATH}/demo`,
        element: <App />,
        parentRoute: PATH,
      },
    ];
    

这里定义的 `parentRoute` 是 `Overview` 路由的父级路由的 path。

## 路由注册

使用 `yarn create:ext` 初始化扩展组件目录后，默认会生成 routes 文件夹，目录结构如下：

    
    
    └── hello-world
        ├── Dockerfile
        ├── README.md
        ├── package.json
        └── src
            ├── App.jsx
            ├── index.js
            ├── locales
            │   ├── en
            │   │   ├── base.json
            │   │   └── index.js
            │   ├── index.js
            │   └── zh
            │       ├── base.json
            │       └── index.js
            └── routes
                └── index.js
    

将路由定义写在 `routes/index.js`文件中，然后在扩展组件的 entry file 里注册路由，如下：

    
    
    import routes from './routes';  // 引入路由文件
    import locales from './locales';  
    
    const menus = [
      {
        parent: 'topbar',
        name: 'hello-world',
        link: '/hello-world',
        title: 'HELLO_WORLD',
        icon: 'cluster',
        order: 0,
        desc: 'SAY_HELLO_WORLD',
        skipAuth: true,
      }
    ];
    
    const extensionConfig = {
      routes,
      menus,
      locales,
    };
    
    export default extensionConfig;
    

[__](/extension-dev-guide/zh/feature-customization/internationalization/
"国际化")[__](/extension-dev-guide/zh/feature-customization/ingress/ "为扩展组件分配
Ingress")



---

# 为扩展组件分配 Ingress

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/ingress/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/ingress/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [扩展能力](/extension-dev-
guide/zh/feature-customization/) > 为扩展组件分配 Ingress

# 为扩展组件分配 Ingress

在 4.1.1 版本中，ks-core chart 新增如下配置项，支持将外部 ingress 相关信息传递给扩展组件，以支持在扩展组件 chart
中创建和使用 ingress：

    
    
    extension:
      ingress:
        # 外部 ingress 的 ingressClassName
        ingressClassName: ""
        # 用于创建扩展组件访问入口的域名后缀。根据外部 ingress 地址，它可以是 LB 主机名地址（比如 xx.com）、{node_ip}.nip.io 或内部 DNS 地址（比如 kse.local）。
        domainSuffix: ""
        # ingress 的 http 端口
        httpPort: 80
        # ingress 的 https 端口
        httpsPort: 443
    

通过上面的配置，扩展组件 chart 中将会被自动注入如下值，可直接使用：

    
    
    global.extension.ingress.ingressClassName
    global.extension.ingress.domainSuffix
    global.extension.ingress.httpPort
    global.extension.ingress.httpsPort
    

## 使用示例

下面是一个示例，为一个扩展组件的 API 接口分配一个子域名以供外部访问。

前提条件是环境存在可使用的任意 ingress controller，在示例环境中使用了 nginx ingress controller，并且 LB
分配了一个域名 xx.com，根据这些信息更新 ks-core：

    
    
    helm upgrade ... --set extension.ingress.ingressClassName=nginx --set extension.ingress.domainSuffix=xx.com
    

扩展组件增加 ingress 配置项以及一些使用 ingress 的其它代码更改（如有必要）：

    
    
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: xx-api
      annotations:
        nginx.ingress.kubernetes.io/rewrite-target: /
    spec:
      ingressClassName: {{ .Values.global.extension.ingress.ingressClassName }}
      rules:
        - host: xxapi.{{ .Values.global.extension.ingress.domainSuffix }}
          http:
            paths:
              - pathType: Prefix
                path: "/"
                backend:
                  service:
                    name: xx-api-backend
                    port:
                      number: 80
    

打包、更新/升级扩展组件之后即可使用 `xxapi.xx.com` 来访问 API，上述示例中将流量转发到了扩展组件自身的一个 service
上，如需要转发到一个外部地址，可使用 `ExternalName` 类型的 service，示例如下：

    
    
    apiVersion: v1
    kind: Service
    metadata:
      name: my-service
    spec:
      type: ExternalName
      externalName: my.database.example.com
    
    ---
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: xx-api
      annotations:
        nginx.ingress.kubernetes.io/rewrite-target: /
    spec:
      ingressClassName: {{ .Values.global.extension.ingress.ingressClassName }}
      rules:
        - host: xxapi.{{ .Values.global.extension.ingress.domainSuffix }}
          http:
            paths:
              - pathType: Prefix
                path: "/"
                backend:
                  service:
                    name: my-service
                    port:
                      number: 80
    

[__](/extension-dev-guide/zh/feature-customization/route/
"页面路由")[__](/extension-dev-guide/zh/feature-customization/license/ "自定义扩展组件的
license")



---

# 打包发布

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/packaging-and-release.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/packaging-and-
release/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 打包发布

# 打包发布

  * [打包扩展组件](/extension-dev-guide/zh/packaging-and-release/packaging/)

如何打包 KubeSphere 扩展组件

  * [测试扩展组件](/extension-dev-guide/zh/packaging-and-release/testing/)

将扩展组件上架到 KubeSphere 扩展市场中进行测试

  * [发布扩展组件](/extension-dev-guide/zh/packaging-and-release/release/)

将扩展组件发布到 KubeSphere Marketplace

[ __](/extension-dev-guide/zh/examples/external-link-example/
"外部链接")[__](/extension-dev-guide/zh/packaging-and-release/packaging/ "打包扩展组件")



---

# ksbuilder CLI 参考

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references/ksbuilder/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-
guide/content/zh/references/ksbuilder/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [参考资料](/extension-dev-
guide/zh/references/) > ksbuilder CLI 参考

# ksbuilder CLI 参考

* * *

## ksbuilder

ksbuilder 是 KubeSphere 扩展组件的命令行接口。

    
    
    ksbuilder [flags]
    

### 可选项

    
    
      -h, --help   help for ksbuilder
    

## ksbuilder create

执行以下命令创建新的 KubeSphere 组件。

    
    
    ksbuilder create [flags]
    

## ksbuilder package

执行以下命令打包组件。

    
    
    ksbuilder package [flags]
    

## ksbuilder publish

执行以下命令将组件发布到扩展市场。

    
    
    ksbuilder publish [flags]
    

## ksbuilder unpublish

执行以下命令将组件从扩展市场中移除。

    
    
    ksbuilder unpublish [flags]
    

## ksbuilder version

执行以下命令查看组件版本。

    
    
    ksbuilder version [flags]
    

[__](/extension-dev-guide/zh/references/ "参考资料")[__](/extension-dev-
guide/zh/references/kubedesign/ "KubeDesign")



---

# 打包发布

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/packaging-and-release/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/packaging-and-
release/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 打包发布

# 打包发布

  * [打包扩展组件](/extension-dev-guide/zh/packaging-and-release/packaging/)

如何打包 KubeSphere 扩展组件

  * [测试扩展组件](/extension-dev-guide/zh/packaging-and-release/testing/)

将扩展组件上架到 KubeSphere 扩展市场中进行测试

  * [发布扩展组件](/extension-dev-guide/zh/packaging-and-release/release/)

将扩展组件发布到 KubeSphere Marketplace

[ __](/extension-dev-guide/zh/examples/external-link-example/
"外部链接")[__](/extension-dev-guide/zh/packaging-and-release/packaging/ "打包扩展组件")



---

# 前端扩展机制

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/overview/frontend-extension-architecture/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/overview/frontend-
extension-architecture/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [概述](/extension-dev-
guide/zh/overview/) > 前端扩展机制

# 前端扩展机制

为了提高 KubeSphere 的灵活性和可扩展性，KubeSphere 4.0
采用了`微内核+扩展组件`的架构。在这个架构中，`微内核`部分仅包含系统运行所需的基础功能，而各个独立的业务模块则被封装在各个扩展组件中。这允许在系统运行时动态地安装、卸载、启用或禁用扩展组件。

总体架构如下图所示：

![luban-frontend-extension-architecture](/extension-dev-
guide/zh/overview/frontend-extension-architecture/luban-frontend-extension-
architecture.png?width=800px)

## 设计思想

在解耦巨石应用和实现动态扩展时，不可避免会考虑到近年来备受欢迎的`微前端`解决方案。著名的微前端实现，如 qiankun 和 micro-
app，为了应对子应用的技术栈独立性和样式侵入问题，采取了大量措施，包括实施 JavaScript
沙箱和样式隔离等。然而，这种隔离通常是为了解决特定技术栈问题或团队协作问题而做出的妥协。如果将多个框架，如 React、Vue 和
Angular，融合到同一前端系统中，用户界面体验可能会不一致，而前端包的大小也可能显著增加。此外，各个子应用在各自独立的运行时中运行，可能与主应用的集成度不够紧密。

在这种背景下，我们希望减轻对隔离性的需求，以实现一种更轻量的"微前端"，或者可以称之为`微模块`。在微模块架构中，子应用和主应用共享相同的技术栈，可以共享运行时。这有助于实现更一致的用户体验、更高的集成度和更便捷的依赖共享，从而提高运行效率。如上面的架构图所示，扩展组件的开发依赖通用的
[KubeDesign](https://github.com/kubesphere/kube-design)、[@ks-
console/shared](https://www.npmjs.com/package/@ks-console/shared)
等库。然后，使用[脚手架](https://github.com/kubesphere/create-ks-project)、CLI
等工具打包和发布扩展组件。在 Core（基座）的部分注册和运行扩展组件。

## 内核

如上图所示，内核的主要功能包括：

  1. 扩展组件的管理

扩展组件的管理涉及两个重要方面，即在运行时完成扩展组件的 JavaScript bundle 加载以及扩展组件的注册。在 4.0 版本的架构中，采用了
SystemJS 来实现对扩展组件 JavaScript bundle 的加载。同时，制定了扩展组件的入口规范，以确保它们能够连接到核心系统并运行。

  2. 通讯机制

在内核中内置 EventBus（发布/订阅），以方便内核与扩展组件之间以及扩展组件之间的通信。

  3. 路由管理

基于 react-router，扩展组件定义的路由在扩展组件注册时会被统一管理到内核中。

  4. 国际化

采用 i18next 实现国际化。开发者可以在扩展组件中按照 i18next 的格式定义翻译文件，然后按照约定注册到内核中。

  5. 扩展中心

类似于 Chrome 浏览器的扩展程序，KubeSphere
也提供了一个可视化的扩展组件管理模块，允许用户在页面上轻松执行扩展组件的安装、卸载、启用、禁用等操作。

  6. 基础页面

包括系统运行所需的一些基本 UI 元素，例如登录页面和页面布局。

  7. BFF

基于 Koa 实现的 BFF 层。主要负责首页渲染、请求转发、数据转换以及一些轻量级的后端任务。

## 扩展组件

如上图所示，扩展组件分为 `In-Tree 扩展组件` 和 `Out-of-Tree 扩展组件`。区别在于：

  * `In-Tree 扩展组件` 基本上是系统必备或者常用的功能组件，它们在编译时与 `core` 一起打包。`In-Tree 扩展组件` 目前包括：

    1. Cluster 集群管理
    2. Access 访问控制
    3. Workspaces 工作空间
    4. Projects 项目管理
    5. Apps 应用商店
    6. Settings 平台设置
  * `Out-of-Tree 扩展组件` 是由开发者在自己的代码仓库中开发的扩展组件，需要独立进行编译和打包。这些组件将被发布到 `扩展市场`。用户安装后，内核会远程加载扩展组件的 `js bundle` 并将其注册到内核中。

`Out-of-Tree 扩展组件` 的前端部分统一使用 [create-ks-
project](https://github.com/kubesphere/create-ks-project)
脚手架工具进行初始化。初始化后的目录结构如下：

    
    
    .
    ├── babel.config.js
    ├── configs
    │   ├── config.yaml
    │   ├── local_config.yaml
    │   ├── webpack.config.js
    │   └── webpack.extensions.config.js
    ├── extensions
    │   └── hello-world
    │       ├── Dockerfile
    │       ├── README.md
    │       ├── package.json
    │       └── src
    │           ├── App.jsx
    │           ├── index.js
    │           ├── locales
    │           │   ├── en
    │           │   │   ├── base.json
    │           │   │   └── index.js
    │           │   ├── index.js
    │           │   └── zh
    │           │       ├── base.json
    │           │       └── index.js
    │           └── routes
    │               └── index.js
    ├── node_modules
    ├── package.json
    ├── tsconfig.base.json
    ├── tsconfig.json
    └── yarn.lock
    

该目录结构和普通的 react app 基本一样，不同之处在于对 entry 的定义，如示例中所示：

    
    
    import routes from './routes'; // 导入路由
    import locales from './locales'; // 导入国际化文件
    
    // 定义扩展组件入口
    const menus = [
      {
        parent: 'topbar', // 入口父级
        name: 'hello-world', // 入口 name 标识
        link: '/hello-world', // 入口 url
        title: 'Hello World', // 入口名称
        icon: 'cluster', // 入口 icon
        order: 0, // 菜单排序
        desc: 'This is hello-world extension', // 入口描述
        skipAuth: true, // 是否忽略权限检查
        isCheckLicense: false, // 是否进行许可检查
      },
    ];
    
    const extensionConfig = {
      routes,
      menus,
      locales,
    };
    
    export default extensionConfig;
    

如上所示，通过脚手架工具初始化后，定义扩展组件的入口文件。在开发过程中，其业务代码开发模式与普通前端项目相同。一旦开发完成，即可将扩展组件打包并发布到独立的代码仓库。这些扩展组件与内核部分相互独立，不会造成代码侵入。

## 开发赋能

为了提高扩展组件的开发效率，保持系统体验的一致性，确保良好的运行效率，KubeSphere 提供了一些通用的组件和工具库，供扩展组件开发使用。

  1. 通用组件库 [KubeDesign](https://github.com/kubesphere/kube-design)
  2. 前端脚手架工具 [create-ks-project](https://github.com/kubesphere/create-ks-project)
  3. 通用 util 库 [@ks-console/shared](https://www.npmjs.com/package/@ks-console/shared)

[ __](/extension-dev-guide/zh/overview/overview/ "扩展组件概述")[__](/extension-dev-
guide/zh/overview/backend-extension-architecture/ "后端扩展机制")



---

# Databend Playground 示例

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/videos/databend-playground/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/videos/databend-
playground.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [视频演示](/extension-dev-
guide/zh/videos/) > Databend Playground 示例

# Databend Playground 示例

[ __](/extension-dev-guide/zh/videos/openkruisegame-dashboard/ "OpenKruiseGame
Dashboard 示例")[__](/extension-dev-guide/zh/videos/flomesh-service-mesh/
"Flomesh Service Mesh \(FSM\) 示例")



---

# 访问控制

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/access-control/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/access-control/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [扩展能力](/extension-dev-
guide/zh/feature-customization/) > 访问控制

# 访问控制

本节介绍扩展组件如何对接 KubeSphere 访问控制。

## KubeSphere 中的访问控制

KubeSphere 是一个支持多租户的容器管理平台，与 Kubernetes 相同，KubeSphere
通过基于角色的访问控制（RBAC）对用户的权限加以控制，实现逻辑层面的资源隔离。

在 KubeSphere 中企业空间（Workspace）是最小的租户单元，企业空间提供了跨集群、跨项目（即 Kubernetes
中的命名空间）共享资源的能力。企业空间中的成员可以在授权集群中创建项目，并通过邀请授权的方式参与项目协同。

KubeSphere
中的资源被划分为平台、企业空间、集群、项目四个层级，所有的资源都会归属到这四个资源层级之中，各层级可以通过角色来控制用户的资源访问权限。

**平台角色：** 主要控制用户对平台资源的访问权限，如集群的管理、企业空间的管理、平台用户的管理等。

**企业空间角色：** 主要控制企业空间成员在企业空间下的资源访问权限，如企业空间下项目、企业空间成员的管理等。

**项目角色：** 主要控制项目下资源的访问权限，如工作负载的管理、流水线的管理、项目成员的管理等。

![rbac](/extension-dev-guide/zh/feature-customization/access-
control/rbac.png?width=900px)

### KubeSphere API

[KubeSphere API](/extension-dev-guide/zh/references/kubesphere-api-concepts/)
和 [Kubernertes API](https://kubernetes.io/zh-cn/docs/reference/using-api/api-
concepts/) 的设计模式相同，是通过 HTTP 提供的基于资源 (RESTful) 的编程接口。 它支持通过标准 HTTP
动词（POST、PUT、PATCH、DELETE、GET）检索、创建、更新和删除主要资源。

对于某些资源，API 包括额外的子资源，允许细粒度授权（例如：将 Pod 的详细信息与检索日志分开），
为了方便或者提高效率，可以以不同的表示形式接受和服务这些资源。

#### Kubernetes API 术语

Kubernetes 通常使用常见的 RESTful 术语来描述 API 概念：

  * **资源类型（Resource Type）** 是 URL 中使用的名称（`pods`、`namespaces`、`services`）。
  * 所有资源类型都有一个具体的表示（它们的对象模式），称为 **类别（Kind）** 。
  * 资源类型的实例的列表称为 **集合（Collection）** 。
  * 资源类型的单个实例称为 **资源（Resource）** ，通常也表示一个 **对象（Object）** 。
  * 对于某些资源类型，API 包含一个或多个**子资源（sub-resources）** ，这些子资源表示为资源下的 URI 路径。

大多数 Kubernetes API 资源类型都是[对象](https://kubernetes.io/zh-
cn/docs/concepts/overview/working-with-objects/)： 它们代表集群上某个概念的具体实例，例如 Pod
或名字空间。 少数 API 资源类型是“虚拟的”，它们通常代表的是操作而非对象本身， 例如权限检查（使用带有 JSON 编码的
`SubjectAccessReview` 主体的 POST 到 `subjectaccessreviews` 资源）， 或 Pod 的子资源
`eviction`（用于触发 [API-发起的驱逐](https://kubernetes.io/zh-
cn/docs/concepts/scheduling-eviction/api-eviction/)）。

##### 对象名称

通过 API 创建的所有对象都必须具有唯一的名称，以便实现幂等创建和检索，但如果虚拟资源类型不可检索或不依赖幂等性，它们可能没有唯一的名称。
在名字空间内，同一时刻只能有一个给定类别的对象具有给定名称。但如果删除了该对象，就可以创建一个具有相同名称的新对象。有些对象没有名字空间（例如：节点），因此它们的名称在整个集群中必须是唯一的。

#### API 动词

几乎所有对象资源类型都支持标准 HTTP 动词 - GET、POST、PUT、PATCH 和 DELETE。 Kubernetes
也使用自己的动词，这些动词通常写成小写，以区别于 HTTP 动词。

Kubernetes 使用术语 **list** 来描述返回资源集合，以区别于通常称为 **get** 的单个资源检索。 如果您发送带有 `?watch`
查询参数的 HTTP GET 请求，Kubernetes 将其称为 **watch** 而不是 **get** 。

对于 PUT 请求，Kubernetes 在内部根据现有对象的状态将它们分类为 **create** 或 **update** 。 **update**
不同于 **patch** ；**patch** 的 HTTP 动词是 PATCH。

#### 资源 URI

资源类型可以是：

平台作用域的（`(apis/kapis)/GROUP/VERSION/*`）

集群作用域的（`/clusters/CLUSTER/(apis/kapis)/GROUP/VERSION/*`）

企业空间作用域的（`(apis/kapis)/GROUP/VERSION/workspaces/WORKSPACE/*`）

名字空间作用域的（`/clusters/CLUSTER/(apis/kapis)/GROUP/VERSION/namespaces/NAMESPACE/*`）

注意：KubeSphere 支持 K8s 多集群纳管。只要在请求路径之前添加集群标识作为前缀，就可以通过 API 直接访问 member
集群。Kubernetes 核心资源使用 `/api` 而不是 `/apis`，并且不包含 GROUP 路径段。

示例：

  * `/apis/iam.kubesphere.io/v1beta1/users`
  * `/apis/cluster.kubesphere.io/v1alpha2/clusters`
  * `/cluster/host/api/v1/pods`
  * `/kapis/iam.kubesphere.io/v1beta1/workspaces/my-workspace/devopsprojects`
  * `/cluster/host/api/v1/namespaces/my-namespace/pods`

### RBAC

基于角色（Role）的访问控制（RBAC）是一种基于组织中用户的角色来调节控制对计算机或网络资源的访问的方法。

RBAC 鉴权机制使用 `iam.kubesphere.io` 来驱动鉴权决定，允许您通过 KubeSphere API 动态配置策略。

RBAC API 声明了八种 CRD 对象：**Role** 、**ClusterRole** 、**GlobalRole**
、**WorkspaceRole** 、**RoleBinding** 、 **ClusterRoleBinding**
、**GlobalRoleBinding** 和 **WorkspaceRoleBinding**

RBAC 的 **Role** 、**ClusterRole** 、**GlobalRole** 、**WorkspaceRole**
中包含一组代表相关权限的规则。 这些权限是纯粹累加的（不存在拒绝某操作的规则）。

Role 用于限制名字空间作用域资源的访问权限； ClusterRole 用于限制集群作用域的资源资源访问权限； WorkspaceRole
用于限制企业空间作用域的资源访问权限； GlobalRole 用于限制平台作用域的资源资源访问权限；

下面是一个位于 “default” 名字空间的 Role 的示例，可用来授予对 Pod 的读访问权限：

    
    
    apiVersion: iam.kubesphere.io/v1beta1
    kind: Role
    metadata:
      namespace: default
      name: pod-reader
    rules:
    - apiGroups: [""]
      resources: ["pods"]
      verbs: ["get", "watch", "list"]
    

下面的例子中，RoleBinding 将 “pod-reader” Role 授予在 “default” 名字空间中的用户 “jane”。 这样，用户
“jane” 就具有了读取 “default” 名字空间中所有 Pod 的权限。

    
    
    apiVersion: iam.kubesphere.io/v1beta1
    # 此角色绑定允许 "jane" 读取 "default" 名字空间中的 Pod
    # 您需要在该名字空间中有一个名为“pod-reader”的 Role
    kind: RoleBinding
    metadata:
      name: read-pods
      namespace: default
    subjects:
    # 您可以指定不止一个“subject（主体）”
    - kind: User
      name: jane # "name" 是区分大小写的
      apiGroup: iam.kubesphere.io
    roleRef:
      # "roleRef" 指定与某 Role 或 ClusterRole 的绑定关系
      kind: Role        # 此字段必须是 Role 或 ClusterRole
      name: pod-reader  # 此字段必须与您要绑定的 Role 或 ClusterRole 的名称匹配
      apiGroup: iam.kubesphere.io
    

## 自定义授权项

KubeSphere 支持通过授权项灵活地创建自定义角色，实现精细的访问控制。

### RoleTemplate

`RoleTemplate` 是由 KubeSphere 提供的 CRD，用于声明权限项，是 KubeSphere UI
中最小的权限分割单元，通常用来定义某一类型资源的访问权限。各资源层级中的角色都由权限组合而成，基于权限项，用户可以灵活地创建自定义角色，实现精细的访问控制。

在 Kubesphere 用户界面中，用户通常在获得一个资源时，同时也希望获得这个资源相关联的其他资源。把一组关联紧密的资源的权限放在一个
RoleTemplate 中，以满足在用户界面操作的使用需求。

**平台角色权限项：**

![global-role](/extension-dev-guide/zh/feature-customization/access-
control/global-role.png?width=1200px)

**企业空间角色权限项：**

![workspace-role](/extension-dev-guide/zh/feature-customization/access-
control/workspace-role.png?width=1200px)

**集群角色权限项：**

![cluster-role](/extension-dev-guide/zh/feature-customization/access-
control/cluster-role.png?width=1200px)

**项目角色权限项：**

![project-role](/extension-dev-guide/zh/feature-customization/access-
control/project-role.png?width=1200px)

### RoleTemplate 示例

假设扩展组件中定义了 CRD `custom-resource` `custom-resource-version`。期望 KubeSphere
用户在用户界面查看 custom-resource 时能够同时返回 custom-resource-version。以下 YAML 文件创建了
`global-custom-resource-view` 和 `global-custom-resource-manage`
两个自定义权限，分别授权用户查看和创建 `custom-resource` 类型的资源，其中 `global-custom-resource-manage`
依赖于 `global-custom-resource-view`。

    
    
    apiVersion: iam.kubesphere.io/v1beta1
    kind: RoleTemplate
    metadata:
      name: global-custom-resource-view
      labels:
        iam.kubesphere.io/category: custom-resource-management
        iam.kubesphere.io/scope: global
        kubesphere.io/managed: 'true'
    spec:
      displayName:
        en: Custom Resource Viewing
      rules:
        - apiGroups:
            - custom-api-group
          resources:
            - custom-resource
            - custom-resource-version
          verbs:
            - list
            - get
            - watch
    
    ---
    apiVersion: iam.kubesphere.io/v1beta1
    kind: RoleTemplate
    metadata:
      name: global-custom-resource-manage
      annotations:
        iam.kubesphere.io/dependencies: global-custom-resource-view
      labels:
        iam.kubesphere.io/category: custom-resource-management
        iam.kubesphere.io/scope: global
        kubesphere.io/managed: 'true'
    spec:
      displayName:
        en: Custom Resource Management
      rules:
        - apiGroups:
            - custom-api-group
          resources:
            - custom-resource
            - custom-resource-version
          verbs:
            - '*'
    

#### RoleTemplate 参数说明

以下介绍如何设置自定义权限的参数。

  * `apiVersion`：KubeSphere 访问控制 API 的版本。当前版本为 `iam.kubesphere.io/v1beta1`。
  * `kind`：自定义权限的资源类型。请将参数值设置为 `RoleTemplate`。
  * `metadata`：自定义权限的元数据。
    * `name`：自定义权限的资源名称。
    * `annotations`：
      * `iam.kubesphere.io/dependencies`: 在 Console 中会显示为依赖关系，当选中这个权限项时会自动选中依赖的权限项。
      * `iam.kubesphere.io/role-template-rules`: 具体控制 Console 权限规则，详见下文 [Console 前端权限控制](/extension-dev-guide/zh/#console-前端权限控制)。
    * `labels`：
      * `iam.kubesphere.io/scope`：自定义权限的资源标签。KubeSphere 将权限分为平台、集群、企业空间和项目权限。取值 `global` 表示当前权限为平台级别的权限。可选的值有 `global`、`cluster`、`workspace` 和 `namespace`。
      * `iam.kubespere.io/category`：标记权限项所属的类别。
      * `iam.kubespere.io/managed`：KubeSphere 管理的授权项。
  * `spec`
    * `displayName`：显示名称，支持国际化
      * `en`：英文显示名称。
      * `zh`：中文显示名称。
    * `rules`：自定义权限向用户授权的资源和操作。此参数为自定义权限内容的实际定义。
      * `apiGroups`：向用户授权的资源类型所属的 API 组。取值 `'*'` 表示当前权限级别的所有 API 组。
      * `resources`：向用户授权的资源类型，可以为 CRD（例如本节示例中的 `custom-resource`，`custom-resource-version`）或 Kubernetes 默认资源类型（例如 `deployment`）。取值 `'*'` 表示当前权限级别的所有资源类型。
      * `verbs`：向用户授权的操作。取值 `'*'` 当前权限级别的所有操作。有关资源操作类型的更多信息，请参阅 [Kubernetes 官方文档](https://kubernetes.io/docs/reference/access-authn-authz/authorization/)。

### RoleTemplate 自动聚合

通过标签匹配的方式将 RoleTemplate 聚合到角色中。role 中包含一个字段 `aggregationRoleTemplates`，其中包含一个
`roleSelector` 字段，用于匹配 RoleTemplate 的 label。匹配成功的 RoleTemplate 会自动聚合到 role 中。

    
    
    apiVersion: iam.kubesphere.io/v1beta1
    kind: GlobalRole
    metadata:
      annotations:
        ## 添加这个注解用来开启自动聚合功能
        iam.kubesphere.io/auto-aggregate: "true"
      name: authenticated
    aggregationRoleTemplates:
      roleSelector:
        matchLabels:
          iam.kubesphere.io/aggregate-to-authenticated: ""
          iam.kubesphere.io/scope: "global"
    rules:
     ......
    

将特定的 label 加到 RoleTemplate 中。例如，将 `iam.kubesphere.io/aggregate-to-
authenticated: ''` 加到 RoleTemplate 中，可以实现聚合上述的角色 globalrole authenticated。

    
    
    apiVersion: iam.kubesphere.io/v1beta1
    kind: RoleTemplate
    metadata:
      name: global-custom-resource-manage
      annotations:
        iam.kubesphere.io/dependencies: global-custom-resource-view
      labels:
        iam.kubesphere.io/category: custom-resource-management
        ## 注意 scope 要和聚合的角色匹配
        iam.kubesphere.io/scope: global
        ## 聚合到内置角色 authenticated
        iam.kubesphere.io/aggregate-to-authenticated: '' 
    spec:
      displayName:
        en: Custom Resource Viewing
      rules:
        - apiGroups:
            - custom-api-group
          resources:
            - custom-resource
            - custom-resource-version
          verbs:
            - *
    

大多数`内置角色`都支持自动聚合功能，这样可以减少用户的配置工作。

各个层级的 `admin` 角色可以自动聚合层级内的所有 RoleTemplate，例如某个 namespace 的 admin 可以自动聚合 scope
为 namespace 的所有 RoleTemplate。

对于`非 admin` 角色，支持使用以下 label 聚合到对应的角色：

#### workspace

  * iam.kubesphere.io/aggregate-to-viewer: ""
  * iam.kubesphere.io/aggregate-to-regular: ""
  * iam.kubesphere.io/aggregate-to-self-provisioner: ""

#### global

  * iam.kubesphere.io/aggregate-to-authenticated: ""

#### cluster

  * iam.kubesphere.io/aggregate-to-cluster-viewer: ""

#### namespace

  * iam.kubesphere.io/aggregate-to-operator: ""
  * iam.kubesphere.io/aggregate-to-viewer: ""

### Category

Category 用于标记 RoleTemplate 所属的类别。KubeSphere Console 将根据权限项的类别将权限项分组显示。对应
RoleTemplate 的 label `iam.kubesphere.io/category: custom-resource-management`。

    
    
    apiVersion: iam.kubesphere.io/v1beta1
    kind: Category
    metadata:
      name: custom-resource-management
      labels:
        iam.kubesphere.io/scope: global
        kubesphere.io/managed: 'true'  
    spec:
      displayName:        
        en: Custom Resource Management
    

#### Category 参数说明

  * `apiVersion`：KubeSphere 访问控制 API 的版本。当前版本为 `iam.kubesphere.io/v1beta1`。
  * `kind`：自定义权限的资源类型。请将参数值设置为 `Category`。
  * `metadata`：自定义权限的元数据。
    * `name`：自定义权限的资源名称。
    * `labels`：
      * `iam.kubesphere.io/scope`：自定义权限的资源标签。KubeSphere 将权限分为平台、集群、企业空间和项目权限。取值 `global` 表示当前权限为平台级别的权限。可选的值有 `global`、`cluster`、`workspace` 和 `namespace`。
      * `spec`
        * `displayName`：显示名称，支持国际化
          * `en`：英文显示名称。
          * `zh`：中文显示名称。

### 自定义角色创建

声明 RoleTemplate、Category 后，创建自定义角色：

![custom-role-template](/extension-dev-guide/zh/feature-customization/access-
control/custom-role-template.png)

## Console 前端权限控制

对于前端来说，RoleTemplate 至关重要，当给不同租户渲染页面时，会根据 RoleTemplate
的权限项来判断是否渲染某个页面或者某个按钮。具体的原理如下：

  1. 首先获取一个用户所绑定的各个层级的角色（globalrole, clusterrole, workspacerole, role）。

  2. 根据这些角色的 aggregationRoleTemplates 字段，获取到所有的 RoleTemplate。

  3. 根据所有获得的 RoleTemplate 来判断是否渲染某个页面或者某个按钮。

进入页面时，会依照不同层级的 RoleTemplate 从上到下（global > cluster > workspace >
namespace）的顺序来判断是否渲染某个页面或按钮，如果更高层级的 RoleTemplate 已经包含了需要用到的权限项，那么就不会再去判断更低层级的
RoleTemplate。

所以在开发一个扩展组件的交互功能时，您需要考虑好各租户的权限范围，以及他们能做的操作。

menus 权限设置

    
    
    // menus 涉及权限字段
    const menus = [
      { 
        name: 'hello-world',     // name 必填字段
        ksModule: 'hello-world',    
        authKey: 'hello-world',  
        authAction:'view',   
        skipAuth: true,      
      }
    ];
    

权限过滤效果

| 权限| 字段| 类型| 说明  
---|---|---|---|---  
1| 是否为平台管理员角色 (platform-admin)| `admin`| `boolean`| 为 `true` 则非平台管理员不显示，默认值
`false`  
2| 根据模块是否在当前集群中安装过滤| `clusterModule`| `string`| 在当前集群中未安装不显示，可以指定多个模块使用 `|`
进行分割  
3| 根据模块是否安装过滤| `ksModule`| `string`| 未安装模块不显示  
4| 根据模块是否安装并给了指定`annotation`值过滤| `annotation`| `string`|
模块没有指定`annotation`值不显示。注意：`annotation` 必须配合 `ksModule` 一起使用  
5| 根据配置权限过滤| `authKey` or `name`| `string`| 有 `authKey` 取 `authKey`，否则取 `name`  
6| 根据配置权限项| `authAction`| `string`| 默认值 `view`  
7| 跳过权限控制| `skipAuth`| `boolean`| 优先级最高，为 `true` 则忽略其他配置  
  
  * RoleTemplate 前端权限控制

    
    
    metadata:
      annotations:
        iam.kubesphere.io/role-template-rules: '{"pipelines":"view"}'
        iam.kubesphere.io/role-template-rules: '{"pipelines":"manage"}'
    

  * RoleTemplate 前端权限控制参数说明

    * `iam.kubesphere.io/role-template-rules`：控制前端权限的注解， `{key: action }` 格式 JSON 字符串。
    * `{key}`：前端权限的 key，对应前端权限的 `authKey` 或 `name` 字段。
    * `{action}`: 见 RoleTemplate 前端权限控制 action。
  * RoleTemplate 前端权限控制 action

    * `view`：有此字段，会显示对应的菜单和页面。但只有查看权限，没有操作权限。
    * `*`、`manage`：有完整查看和操作权限。
    * `create`: 有创建权限。
    * `delete`: 有删除权限。
    * `edit`: 有编辑权限。
    * 其他自定义值（配合前端硬编码）。

> 注：`create`、`delete`、`edit` 为前端权限，需配合前端代码，在对应操作的按钮上添加类似 `action: 'create'`
> 代码，下例。

    
    
    import { useActionMenu, DataTable } from '@ks-console/shared';
    const renderTableAction = useActionMenu({
      autoSingleButton: true,
      authKey,
      params,
      actions: [
        {
          key: 'invite',
          text: t('INVITE'),
          action: 'create',  //此处为具体 action 
          props: {
            color: 'secondary',
            shadow: true,
          },
          onClick: openCreate,
        },
      ],
    });
    return (<DataTable 
      // ... the other props
      toolbarRight={renderTableAction({})}
    />)
    

[__](/extension-dev-guide/zh/feature-customization/menu/
"挂载位置")[__](/extension-dev-guide/zh/feature-
customization/internationalization/ "国际化")



---

# Databend Playground 开发小记

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/best-practice/databend-playground/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/best-practice/databend-
playground/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [经验分享](/extension-dev-
guide/zh/best-practice/) > Databend Playground 开发小记

# Databend Playground 开发小记

12 月 5 日，Databend Labs 旗下 Databend Playground（社区尝鲜版）成功上架青云科技旗下 KubeSphere
Marketplace 云原生应用扩展市场，为用户提供一个快速学习和验证 Databend 解决方案的实验环境。

![Databend1](/extension-dev-guide/zh/best-practice/databend-
playground/Databend1.jpeg?width=1200px)

今天这篇文章主要从设计决策、实现选型、问题与解决方案等方面回顾一下 Databend Playground 在开发过程中的一些经验和总结。

## 设计决策

Databend 是使用 Rust 研发、完全⾯向云架构、基于对象存储构建的新一代云原生数据仓库。主要包含 Meta 和 Query
两个服务，在生产环境，往往需要以集群形式部署，其架构如下所示：

![Databend2](/extension-dev-guide/zh/best-practice/databend-
playground/Databend2.png?width=1200px)

KubeSphere 扩展组件可以利用 K8s 的资源管理和调度能力，提供可视化的操作界面，方便用户管理和监控相关资源。

一个很自然的想法就是使用扩展组件能力简化部署，但是简化部署是不够的，Databend 此前有上架 KubeSphere 应用商店，本身也提供 helm
charts 方便 K8s 用户使用，如果预先对相关机制有了解，部署使用 Databend 并不难。

进一步的想法主要是两个方面：

  * 一是用户可能不了解 Databend ，或者只是想验证部分能力，是不是可以提供一个默认的 All in One 的选项。就像 Docker 命令一次性拉起环境。
  * 二是用户可能更需要简化的连接和使用方式，继续折腾客户端、解决远程连接等问题是不现实的，最好是像 Databend Cloud 一样有一套 SQL IDE ，提供关于表和查询结果相关信息。

所以 Databend Playground 从最开始就希望成为一个面向刚接触 Databend 的新人的一站式简易环境搭建和 SQL IDE 支持方案。

## 实现选型

Databend Playground 扩展组件使用前端 iframe 嵌入扩展的形式，可以有效复用原有的 Web 服务和资源，大幅减轻了研发负担。

在学习并验证 KubeSphere 中扩展组件的开发方式和几个示例之后，就需要确定实现的方案了。官方支持前端扩展、后端扩展等多种形式，对于 Databend
Playground 这个案例，由于目标是解决部署问题并且提供 SQL IDE ，主要需要采用的是前端扩展的形式。

比较明确的需求是，在安装之后有一个对应的前端入口点，并且有一个前端 IDE 。从头开发需要的周期比较长，直接迁移 Databend Cloud
的方案又比较困难，最后将目光锁定在了早期为了方便用户体验而实现的 Databend Playground 这个项目上（这个扩展组件最后也继承了这个名字）。

![Databend3](/extension-dev-guide/zh/best-practice/databend-
playground/Databend3.jpeg?width=1200px)

最初的 Databend Playground 是一个服务端程序，它会代理 Databend 的 HTTP Handler
，供前端进行查询和展示。这个模式非常适合使用 KubeSphere 的 iframe
嵌入模式，尽管由于代码过时需要进行一定程度的更新维护，但避免了复杂的前端开发需要。

前端的问题解决了，接下来就是后端部署，后端部署涉及的组件非常清晰，在第一期的规划中仅仅考虑单 Meta 、单 Query 和单 Playground
实例，由于有存储后端需要，再附加一个 MinIO 实例。其实 KubeSphere 扩展组件相当于是一个伞形的 Helm Charts
以及一些描述文件，所以在不涉及后端拓展功能开发的情况下，可以复用 Helm 的部署方案，如果本身熟悉 K8s/KubeSphere 生态就会比较轻松。

## 当前状态与后续规划

借助 KubeSphere 的扩展系统，Databend Playground（社区尝鲜版）可以帮助用户快速部署和启动数据分析环境，并且集成前端 SQL
IDE，使用户能够轻松进行数据分析而无需担心规模化部署的复杂性。该扩展组件的主要目标用户是 Databend 新手或初学者，适用于学习 Databend 的
SQL 语法和体验数据分析方案。

目前，Databend Playground 仅支持单 Query 、单 Meta 、单 Playground
一键部署的模式。我们计划在此基础上继续迭代产品，未来将允许用户自定义存储后端、引入高可用 Meta
架构和计算资源的弹性扩展机制。此外，还将提供监控大盘和其他附加服务，以增强用户体验和系统的可管理性。

## 问题解决

略过具体的开发不提，这里讲讲实际过程中遇到的一些问题和解决方案。

  1. 远程集群和本地开发机的连接问题。

KubeSphere 开发文档中没有提示相关的情况，可能是考虑到用户本地环境可以部署开发集群，但是在部分发行版上可能不适用，需要将远程机器的 IP 添加到
K8s API Server 中，步骤可以参考这篇文章 [How to add a new hostname or IP address to a
Standalone Kubernetes API server](https://kloudle.com/academy/how-to-add-new-
hostname-ipaddress-to-kubernetes-api-server/)

  2. 开发时，前端嵌入时提示没有权限访问资源。

需要配置 Webpack 的 DevServer ，在代理请求时传递 username、password 等鉴权信息。在和 KubeSphere
的维护者沟通以后得到解决方案，目前文档也已经更新。

  3. 前端代理后无法正常显示页面。

首先需要检查路径的相对关系，保证你的前端入口和代理路径是一致的，也就是说，如果代理地址是/proxy/databend.playground 那么原本的
baseUrl 也需要进行调整。其次如果调试模式无法正常工作，可能需要在 index.js 下增加一行 export {} 以确保其不会被识别为
commonJS 。如果生产模式仍然故障的话，需要检查前端编译的产物，必要时和 KubeSphere 团队取得联系。

## 对于 KubeSphere 扩展组件开发者的建议

目前 KubeSphere 扩展组件市场正在积极建设之中，如果你有一个好的 Idea 不妨做着试试看。

这里也附带一个适合新手的快速后端部署 Demo 办法，希望能够帮到大家：

  * 使用 Docker 和 Docker Compose 组织并调试部署方案。
  * 利用 kompose convert 将 docker-compose.yaml 转换成 Helm Charts 。 根据实际情况调试和调整。
  * 如果有什么困难也可以和 KubeSphere 工程师团队的小伙伴们积极沟通，可以快速定位和解决问题。

期待看到其他更棒的扩展组件。

## 相关资料链接

Databend：https://github.com/datafuselabs/databend/

Databend Cloud: <https://databend.cn>

Databend 官方文档：https://docs.databend.cn

Databend Playground 扩展组件：https://github.com/datafuse-extras/databend-
playground-for-kubesphere

KubeSphere：https://kubesphere.io/

KubeSphere 扩展组件开发指南：https://dev-guide.kubesphere.io/

KubeSphere 扩展组件示例：https://github.com/kubesphere/extension-samples/

## 关于 Databend Labs

「Databend Labs」成立于 2021 年 3 月 5 日，是业内领先的开源 Data Cloud 基础设施服务商，也是背后支撑 Databend
开源项目的核心团队，致力于为用户、企业提供更低成本、更高性能、更加易用的数据建设处理一站式平台。目前，Databend
已经服务于多个行业客户，其中包括互联网、金融、人工智能、能源、运营商等领域。了解更多：https://www.databend.cn/。

[ __](/extension-dev-guide/zh/best-practice/develop-example/
"扩展组件开发案例")[__](/extension-dev-guide/zh/faq/ "FAQ")



---

# 自定义扩展组件的 license

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/license/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/license/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [扩展能力](/extension-dev-
guide/zh/feature-customization/) > 自定义扩展组件的 license

# 自定义扩展组件的 license

本节介绍如何自定义您的扩展组件的 license。

KubeSphere 企业版 4.x 中每个扩展组件都需要有自己相应的 license，否则将无法使用扩展组件功能。

License 提供基础的授权资源和授权时间的限制。为了支持扩展组件的多样性和灵活性，KubeSphere 企业版还允许扩展组件在 license
中自定义一些限制。

## 原理介绍

    
    
    -----BEGIN LICENSE-----
    H4sIAAAAAAAA/2SQydKyOgOEr8hTDIKyZCZRUIYwbSwJIIlMr4IBrv4v3/+rU1/V
    WfQinc5Tna5W2BQ2JhcCQ7QB3iPgDfpAwjqQwXNMYx0q/1QrHPOvQRG7GGi5RA/e
    +4apzy4GYG7455GNvqCtTOCWiXDETjAWwp6c9V/vJ088DtDxADrvA+hAQt6zpFdy
    lk+7WD7JeynbfeTTTgM99wZdu2ExbjEBcrVCWqxABt3EZ128YbtpcYfmTFg+ZeKT
    OmSk6BTO7+KuEGH7ZbtUXT2dY+7Kba7ls0s0cN42MC8evn3mQgy0vA9++YAC5lJ/
    cg00uZuGXEOV/y/tDggj99TbyiTWSv3v7Fctcg0ge5Eqe5E/e5G7dynYu5G/T75D
    dt6nSLVP0cVzaUpNkfzu8yxS9dthzVPvU6aQ5mgZi6T9sw3fVFZuYAeRC0XMdbg3
    6GGLBYXHndfGTsvyEMigzQ1koS+HlqnHFQLvZylsiiTm8hRu3w0qnpHy6bHyDz/9
    9ncmDLqpybup+T0bJjtbjBRpu+FkwYAODzdS36kOP9iO5yJR5lxQ/uNjIW5w5w1/
    M7Bd/p1bswSSexpMOGbkQtTF1Rf8/Utut1smLDwWgxa3/73DQjyXdjvn//bRlDqE
    yj8ndzBZrHKSccKLDEOvDBd483n28xM774ehwIPELfcbtDOFN0u8Kn04qc6hyGkn
    ti+ZUleOBrJeVyO8KLY3PwaewAhEM+DKc3ruCzlyDm/DZcptp5XDqaOGuLsSrPOv
    40tX9Up6HlGdYqJ1p4djYcOlrPcya3LsnTJwUnJ2xya+VvUbyUs5nqf34uzZeJLE
    T2aejaNG5btj9eimIc0SDeboR6bMYuHOoRuwG6pMKdzodBkKgG5Kc6+y4xNJ9foY
    -----END LICENSE-----
    

这是一个扩展组件的 license，license 通过压缩和编译后将输出给用户，用户使用这个 license 可以激活 KubeSphere
企业版上的某个组件。

license 在导入 KubeSphere 企业版后会以 secret（保密字典）的形式存储在 host 集群中，必须存储在 kubesphere-
system namespace 下，并且命名方式必须为 `kubesphere.license.<extension>`。

## 操作步骤

下面以 Gatekeeper 的 license 为例，介绍如何自定义您的扩展组件的 license。

  1. 执行以下命令获取 Gatekeeper license 的 secret。
         
         root@kse:~# kubectl get  secret -n kubesphere-system kubesphere.license.gatekeeper -oyaml
         

Gatekeeper license 的 secret 内容如下：

         
         apiVersion: v1
         kind: Secret
         metadata:
         annotations:
             config.kubesphere.io/license-imported-by: offline
             config.kubesphere.io/license-type: subscription
         creationTimestamp: "2024-05-08T07:07:41Z"
         labels:
             config.kubesphere.io/license-id: "504769748605609140"
             config.kubesphere.io/type: license
             kubesphere.io/extension-ref: gatekeeper
         name: kubesphere.license.gatekeeper
         namespace: kubesphere-system
         resourceVersion: "904299"
         uid: bc1dfb71-123b-44f1-b9f8-0b9667693c42
         data:
         profile: Y29ycG9yYXRpb246IOa1i+ivlUtTQ+iuuOWPr+ivgQppbXBvcnRlZEF0OiAiMjAyNC0wNS0wOFQxNTowNzo0MS4wMzI4MzQwNjErMDg6MDAiCmltcG9ydGVkQnk6IG9mZmxpbmUKaXNzdWVkQXQ6ICIyMDI0LTAzLTE0VDA1OjU2OjU1LjU5NTg2OTU4OFoiCmxpY2Vuc2VUeXBlOiBzdWJzY3JpcHRpb24Kbm90QWZ0ZXI6ICIyMDI0LTA2LTA4VDE5OjAwOjAwWiIKbm90QmVmb3JlOiAiMjAyNC0wMi0yNVQwOTo0NzowNVoiCnJlc291cmNlVHlwZTogVkNQVQo=
         raw: ZXlKaGJHY2lPaUpTVXpJMU5pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SnBaQ0k2SWpVd05EYzJPVGMwT0RZd05UWXdPVEUwTUNJc0luUjVjR1VpT2lKemRXSnpZM0pwY0hScGIyNGlMQ0p6ZFdKcVpXTjBJanA3SW1Odklqb2k1cldMNkstVlMxTkQ2SzY0NVktdjZLLUJJbjBzSW1semMzVmxjaUk2ZXlKamJ5STZJbXQxWW1WemNHaGxjbVV1WTJ4dmRXUWlmU3dpYm05MFFtVm1iM0psSWpvaU1qQXlOQzB3TWkweU5WUXdPVG8wTnpvd05Wb2lMQ0p1YjNSQlpuUmxjaUk2SWpJd01qUXRNRFl0TURoVU1UazZNREE2TURCYUlpd2lhWE56ZFdWQmRDSTZJakl3TWpRdE1ETXRNVFJVTURVNk5UWTZOVFV1TlRrMU9EWTVOVGc0V2lJc0ltTnZiWEJ2Ym1WdWRFNWhiV1VpT2lKbllYUmxhMlZsY0dWeUlpd2ljbVZ6YjNWeVkyVk1hVzFwZENJNmV5SnRZWGhXUTNCMUlqb3lNREI5TENKeVpYTnZkWEpqWlZSNWNHVWlPaUpXUTFCVkluMC5lNnFhODBUdC1ocnQ1Qk11NGlsd1lpa3pqVXZwc1l2LU1US3lwQ2hxME1VZWp1VDI1dXBfaElmcjZTMF9UV0s5dTBRNnpqQURIbTdwRmpCOUlTR2hpRHIwTzQzaGJac2RIaDRfbkNON3prNUR2Q1VQZkRvVGxuXzdlNm0zWkdMcDdUcF9EOWhVcmVveTl4bWJ1TGtQNFA1OGxGZUhmT1NmOHpUT2RDX2hvWXlmc202amhBQWlaWWtxVzlmWXNzQm9QeWxSSWhiaVhocUJlOHVEWHBLLXEyT292emhYMDVEM0ppZm9wQnhtUUg0Q3JKbkNIZTh0dlVHYTZRak41d290RVd4SGJZdktLZVdldU1wMFlnb2QtdzI4QjItQkFtejgxbjYxdWk4Ym1JR2d1MHF4VkZ6UW8ycm03QTZMQkhpRW1ueW02SUlUVms1VEFmUXlHR3l3UkNSakNtMHZWOHpjanNaU0Ewdm1hdmxGWGdmVFJWc296c05feHRaVnZXaE1qUldWam9CMTBIZjE1RUdMcVlzVG9hTkU2alFGRU1ncDdnMmd2blpZMktGR2RqSkJHWjUwZEhPNWhHVjE2UkVSVUhyLWV3RlZzZzNOVmNRYTRYY3ZhSC1oQjNPSU9GX0xtX25Hc3hkbFZzOWtKUjVCazlWQ1J5NU1LQ0dUWW05dXlSSUlNNDNtZDczWjQySV9EaEFkcjU2OExUQmxuWkZJN3BOZ0dzNWJiMDNEWkZtZTdpYnF1NFFtOU9QdjktbzdTTHJaMFcxdU9LOU5MZ0N1UHpDTWZDZmJrdTZ3dGppQzZzUXhmdDZjWkYtQWJicHR6cnN5bGVEczFhYWtUWDJ3
         violation: Y3VycmVudDogNApleHBlY3RlZDogMjAwCnR5cGU6IE5vIHZpb2xhdGlvbgp1cGRhdGVkQXQ6ICIyMDI0LTA1LTEzVDE1OjUxOjA5LjQ4MDYzMyswODowMCIK
         type: config.kubesphere.io/license
         

  2. 获取 license 原始数据，即 license secret 的 data.raw 字段，如下：
         
         ZXlKaGJHY2lPaUpTVXpJMU5pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SnBaQ0k2SWpVd05EYzJPVGMwT0RZd05UWXdPVEUwTUNJc0luUjVjR1VpT2lKemRXSnpZM0pwY0hScGIyNGlMQ0p6ZFdKcVpXTjBJanA3SW1Odklqb2k1cldMNkstVlMxTkQ2SzY0NVktdjZLLUJJbjBzSW1semMzVmxjaUk2ZXlKamJ5STZJbXQxWW1WemNHaGxjbVV1WTJ4dmRXUWlmU3dpYm05MFFtVm1iM0psSWpvaU1qQXlOQzB3TWkweU5WUXdPVG8wTnpvd05Wb2lMQ0p1YjNSQlpuUmxjaUk2SWpJd01qUXRNRFl0TURoVU1UazZNREE2TURCYUlpd2lhWE56ZFdWQmRDSTZJakl3TWpRdE1ETXRNVFJVTURVNk5UWTZOVFV1TlRrMU9EWTVOVGc0V2lJc0ltTnZiWEJ2Ym1WdWRFNWhiV1VpT2lKbllYUmxhMlZsY0dWeUlpd2ljbVZ6YjNWeVkyVk1hVzFwZENJNmV5SnRZWGhXUTNCMUlqb3lNREI5TENKeVpYTnZkWEpqWlZSNWNHVWlPaUpXUTFCVkluMC5lNnFhODBUdC1ocnQ1Qk11NGlsd1lpa3pqVXZwc1l2LU1US3lwQ2hxME1VZWp1VDI1dXBfaElmcjZTMF9UV0s5dTBRNnpqQURIbTdwRmpCOUlTR2hpRHIwTzQzaGJac2RIaDRfbkNON3prNUR2Q1VQZkRvVGxuXzdlNm0zWkdMcDdUcF9EOWhVcmVveTl4bWJ1TGtQNFA1OGxGZUhmT1NmOHpUT2RDX2hvWXlmc202amhBQWlaWWtxVzlmWXNzQm9QeWxSSWhiaVhocUJlOHVEWHBLLXEyT292emhYMDVEM0ppZm9wQnhtUUg0Q3JKbkNIZTh0dlVHYTZRak41d290RVd4SGJZdktLZVdldU1wMFlnb2QtdzI4QjItQkFtejgxbjYxdWk4Ym1JR2d1MHF4VkZ6UW8ycm03QTZMQkhpRW1ueW02SUlUVms1VEFmUXlHR3l3UkNSakNtMHZWOHpjanNaU0Ewdm1hdmxGWGdmVFJWc296c05feHRaVnZXaE1qUldWam9CMTBIZjE1RUdMcVlzVG9hTkU2alFGRU1ncDdnMmd2blpZMktGR2RqSkJHWjUwZEhPNWhHVjE2UkVSVUhyLWV3RlZzZzNOVmNRYTRYY3ZhSC1oQjNPSU9GX0xtX25Hc3hkbFZzOWtKUjVCazlWQ1J5NU1LQ0dUWW05dXlSSUlNNDNtZDczWjQySV9EaEFkcjU2OExUQmxuWkZJN3BOZ0dzNWJiMDNEWkZtZTdpYnF1NFFtOU9QdjktbzdTTHJaMFcxdU9LOU5MZ0N1UHpDTWZDZmJrdTZ3dGppQzZzUXhmdDZjWkYtQWJicHR6cnN5bGVEczFhYWtUWDJ3
         

  3. 使用[这里](https://gist.github.com/zhou1203/761aab16a9e0b4c18ac65cec10b4819e)的代码，解析 license 的原始数据，转换成 json 后导出，如下：
         
         {"id":"504769748605609140","type":"subscription","subject":{"co":"测试KSC许可证"},"issuer":{"co":"kubesphere.cloud"},"notBefore":"2024-02-25T09:47:05Z","notAfter":"2024-06-08T19:00:00Z","issueAt":"2024-03-14T05:56:55.595869588Z","componentName":"gatekeeper","resourceLimit":{"maxVCpu":200},"resourceType":"VCPU"}
         

  4. 自定义您的扩展组件的 license 字段。
         
         {
         "id": "508519857256408201",
         "type": "subscription",
         "subject": {
             "co": "KSE测试许可证"
         },
         "issuer": {
             "co": "kubesphere.cloud"
         },
         "notBefore": "2024-03-30T09:47:05Z",
         "notAfter": "2024-05-30T00:00:00Z",
         "issueAt": "2024-04-09T02:50:54.538228148Z",
         "componentName": "springcloud",
         "resourceLimit": {
             "maxVCpu": 500
         },
         "resourceType": "VCPU"
         }
         

以上字符串包含了此 license 对 KubeSphere 集群的基础限制。若需要添加额外的限制，可使用 `customParameters`
字段存储额外的信息。您必须预先设置好 customParameters，要求是**转义后的 json 字符串** ，然后在生成的 license 中配置好
customParameters 字段。

例如，RadonDB DMP 为了限制平台中数据库实例的数量，其 license 的 customParameters 字段配置如下：

         
         "{\"vCpuLimit\": {\"kafka\": 10,\"mysql\": 10,\"openmongo\": 10,\"opensearch\": 10,\"pg\": 10,\"rabbitmq\": 10,\"rediscluster\": 10,\"redissentinel\": 10}}"
         
         
         {
         "id": "508519857256408202",
         "type": "subscription",
         "subject": {
             "co": "KSE测试许可证"
         },
         "issuer": {
             "co": "kubesphere.cloud"
         },
         "notBefore": "2024-03-30T09:47:05Z",
         "notAfter": "2024-05-30T00:00:00Z",
         "issueAt": "2024-04-09T02:50:54.538228148Z",
         "componentName": "dmp",
         "resourceLimit": {
             "maxVCpu": 500
         },
         "resourceType": "VCPU",
         "customParameters": "{\"vCpuLimit\": {\"kafka\": 10,\"mysql\": 10,\"openmongo\": 10,\"opensearch\": 10,\"pg\": 10,\"rabbitmq\": 10,\"rediscluster\": 10,\"redissentinel\": 10}}"
         }
         

扩展组件在获取到解析过的 license 后，将根据 customParameters 中的参数完成扩展组件的限制逻辑。

[ __](/extension-dev-guide/zh/feature-customization/ingress/ "为扩展组件分配
Ingress")[__](/extension-dev-guide/zh/examples/ "开发示例")



---

# KubeDesign

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references/kubedesign/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-
guide/content/zh/references/kubedesign.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [参考资料](/extension-dev-
guide/zh/references/) > KubeDesign

# KubeDesign

KubeDesign 是一套为 KubeSphere 控制台创建的 React 组件库。

在[这里](https://design.kubesphere.io/)查看 KubeDesign 示例及相应的代码。

[ __](/extension-dev-guide/zh/references/ksbuilder/ "ksbuilder CLI
参考")[__](/extension-dev-guide/zh/references/create-ks-project/ "create-ks-
project CLI reference")



---

# 开发示例

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/examples.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/examples/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 开发示例

# 开发示例

  * [Gatekeeper](/extension-dev-guide/zh/examples/gatekeeper-extension/)

集成 Gatekeeper

  * [Weave Scope](/extension-dev-guide/zh/examples/third-party-component-integration-example/)

快速集成已有 Web UI 的第三方工具与系统

  * [外部链接](/extension-dev-guide/zh/examples/external-link-example/)

如何在扩展组件中打开外部链接

[ __](/extension-dev-guide/zh/feature-customization/license/ "自定义扩展组件的
license")[__](/extension-dev-guide/zh/examples/gatekeeper-extension/
"Gatekeeper")



---

# 扩展组件 vs 应用

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/faq/01-difference/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/faq/01-difference.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [FAQ](/extension-dev-
guide/zh/faq/) > 扩展组件 vs 应用

# 扩展组件 vs 应用

本节将从以下方面介绍扩展组件和应用的不同点。

特性| 扩展组件| 应用  
---|---|---  
**展示媒介**|  扩展市场| 应用商店  
**打包分发方式**|  Helm Chart，但扩展组件的 Helm Chart 里有更详细的元数据信息，如：基本信息、产品介绍、更新日志与权限等。|
应用仅是一个 Helm Chart，不提供其他的信息内容。  
**安装部署**|
扩展组件提供了多集群下不同的安装策略，例如：只在主集群，同时在主集群和子集群，在多个子集群。集群之间也可进行差异化配置。同时，扩展组件安装过程提供详细的日志信息，并可展示扩展组件之间的拓扑依赖关系。|
应用不支持多集群安装、分发策略功能，例如：无法将应用的管理端安装在主集群，业务端安装在子集群。因此，应用仅可选择一个集群安装。应用安装过程不提供日志信息，并无法展示应用之间的拓扑依赖关系。  
**配置更新**|  扩展组件可在安装后可视化地编辑配置信息，例如：全局配置、安装的集群、集群间的差异化配置，随后即可通过热更新的方式实时生效，在 UI
页面上展示。同时，扩展组件支持版本升级更新，并作用于所有集群上。| 应用仅可在安装时一次性完成配置，安装后不支持配置编辑与热更新。应用支持版本升级更新。  
**禁用与卸载**|  扩展组件支持临时禁用。同时，可一键进行卸载。| 应用不支持禁用。但可将应用模板下架，并直接删除应用。  
**层级**|  扩展组件提供平台级的产品能力，一般在全平台中仅安装部署一次。| 应用提供租户级的产品能力，可以视用户需求，在平台中并行安装多次。  
**产品体验**|  针对有 UI 页面的扩展组件，可直接在 KubeSphere 控制台中嵌入访问入口或 UI
页面，无需跳出即可直接访问。KubeSphere 控制台与扩展组件之间可打通账号体系、SSO 登录等。| 针对有 UI 页面的应用，需要在自行配置暴露
Service 后，从 KubeSphere 控制台中跳出访问 UI 页面。KubeSphere 控制台与应用之间未提供 SSO 登录，且账号体系独立。  
**权限**|  扩展组件可以对接 KubeSphere 的权限体系，实现细分的后端 API / 前端入口权限。| 应用无权限功能。  
**Admin 管理**|  平台管理员通过“扩展中心”对扩展组件进行一站式安装、配置与管理。|
平台管理员通过“应用商店管理”扩展组件对应用进行统一的分类、审核与上下架管控。  
**渠道**|  扩展组件由青云科技、合作的软件开发商和社区伙伴研发、测试，经过青云科技官方认证后提供。|
应用来自应用仓库或用户自行配置的应用模板。可将本地应用模板上传，经平台管理员审核，而后在应用商店进行应用分发。  
**商业售卖**|  针对 KSE 4.x 订阅版，扩展组件可通过扩展市场进行在线售卖与许可授权；对于 KSE 4.x
离线版，可通过线下商务方式进行售卖与授权。| 应用不支持商业售卖。  
  
[ __](/extension-dev-guide/zh/faq/ "FAQ")[__](/extension-dev-
guide/zh/migration/ "迁移指南")



---

# 开发 KubeSphere 扩展组件

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/videos/develop-an-extension/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/videos/develop-an-
extension.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [视频演示](/extension-dev-
guide/zh/videos/) > 开发 KubeSphere 扩展组件

# 开发 KubeSphere 扩展组件

[ __](/extension-dev-guide/zh/videos/ "视频演示")[__](/extension-dev-
guide/zh/videos/openkruisegame-dashboard/ "OpenKruiseGame Dashboard 示例")



---

# 扩展能力

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 扩展能力

# 扩展能力

KubeSphere 提供了许多灵活的定制方法，供扩展组件扩展 KubeSphere 本身的能力。

  * [UI 扩展](/extension-dev-guide/zh/feature-customization/extending-ui/)

介绍如何扩展 UI

  * [API 扩展](/extension-dev-guide/zh/feature-customization/extending-api/)

介绍如何扩展 API

  * [挂载位置](/extension-dev-guide/zh/feature-customization/menu/)

介绍如何设置扩展组件在 KubeSphere Web 控制台的挂载位置

  * [访问控制](/extension-dev-guide/zh/feature-customization/access-control/)

介绍如何控制扩展组件定制资源的访问权限

  * [国际化](/extension-dev-guide/zh/feature-customization/internationalization/)

介绍如何实现扩展组件前端国际化

  * [页面路由](/extension-dev-guide/zh/feature-customization/route/)

创建新的功能页面并设置路由

  * [为扩展组件分配 Ingress](/extension-dev-guide/zh/feature-customization/ingress/)

介绍如何为扩展组件分配独立的 Ingress 访问入口

  * [自定义扩展组件的 license](/extension-dev-guide/zh/feature-customization/license/)

介绍如何自定义扩展组件的 license

[ __](/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/ "解析
Hello World 扩展组件")[__](/extension-dev-guide/zh/feature-
customization/extending-ui/ "UI 扩展")



---

# 开发示例

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/examples/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/examples/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 开发示例

# 开发示例

  * [Gatekeeper](/extension-dev-guide/zh/examples/gatekeeper-extension/)

集成 Gatekeeper

  * [Weave Scope](/extension-dev-guide/zh/examples/third-party-component-integration-example/)

快速集成已有 Web UI 的第三方工具与系统

  * [外部链接](/extension-dev-guide/zh/examples/external-link-example/)

如何在扩展组件中打开外部链接

[ __](/extension-dev-guide/zh/feature-customization/license/ "自定义扩展组件的
license")[__](/extension-dev-guide/zh/examples/gatekeeper-extension/
"Gatekeeper")



---

# 概述

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/overview/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/overview/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 概述

# 概述

## 为什么在 KubeSphere 4.0 引入扩展机制

自 2018 年 KubeSphere 混合多云容器管理平台诞生以来，已经发布了十几个版本，包括 3
个大版本。为了满足不断增长的用户需求，KubeSphere
集成了众多企业级功能，如多租户管理、多集群管理、DevOps、GitOps、服务网格、微服务、可观测性（包括监控、告警、日志、审计、事件、通知等）、应用商店、边缘计算、网络与存储管理等。

首先，尽管这些功能满足了用户在容器管理平台方面的基本需求，却引发了一些挑战，比如：

  * 版本发布周期较长：需要等待所有组件完成开发、测试，并通过集成测试。这导致了不必要的等待时间，使用户难以及时获得新功能和修复。
  * 响应不及时：KubeSphere 的组件难以单独迭代，因此社区和用户提出的反馈需要等待 KubeSphere 发布新版本才能解决。这降低了对用户反馈的快速响应能力。
  * 前后端代码耦合：尽管目前已能实现单独启用/禁用特定组件，但这些组件的前后端代码仍然耦合在一起，容易相互影响，架构上不够清晰和模块化。
  * 组件默认启用：部分组件默认启用，这可能会占用过多的系统资源，尤其对于没有相关需求的用户。

其次，云原生领域的创新非常活跃。通常在同一个领域存在多种选择，例如：

  * GitOps 用户可以选用 ArgoCD 或 FluxCD；
  * 服务网格用户可以选择 Istio 或 Linkerd 或其它实现；
  * 联邦集群管理可选择 Karmada、OCM 或 Clusternet；
  * 日志管理可以采用 Elasticsearch 或 Loki；
  * 边缘计算框架可使用 KubeEdge、OpenYurt 或 SuperEdge；
  * 存储和网络领域也提供了众多选择。

KubeSphere 通常会优先支持其中一种实现，但用户常常有对其它实现的需求。

此外，在使用 KubeSphere 的过程中，用户通常会面临以下问题：

  * 用户将自己的应用发布到 KubeSphere 后，应用的管理界面无法与 KubeSphere 控制台无缝集成，因而无法在 KubeSphere 内一体化管理自己的应用。通常需要用户自行配置应用的 Service，如 NodePort 或 LB，以便在新窗口中管理应用；
  * 由于无法与 KubeSphere 控制台集成，用户的应用无法充分利用 KubeSphere 提供的认证鉴权、多租户管理等平台级功能，安全性受到影响；
  * 用户需求多种多样，不同用户对相同功能的需求存在显著差异，有时甚至相互冲突。原有架构由于耦合式的组件集成方式，难以满足用户多样化的需求；
  * 如果用户希望通过向 KubeSphere 提交 PR 来满足自己的需求，通常需要了解完整的 KubeSphere 开发流程。这包括前后端开发、调试、安装、部署和配置等一系列问题，门槛相对较高；
  * 此外，提交了 PR 后，需要等待 KubeSphere 发布新版本才能使用；
  * 由于发布周期较长，许多用户会自行在 KubeSphere 上定制化自己的需求，逐渐脱离社区，违背了开源社区 “upstream first” 的理念，从长远来看，将无法享受到上游越来越多的功能。

## KubeSphere 4.0 扩展机制简介

为了应对上述各种问题，KubeSphere 在 4.0 版本引入了全新的微内核架构，代号为 “LuBan”：

  * 通过 LuBan，可以实现前后端功能的动态扩展。
  * KubeSphere 的核心组件被精简为 ks-core，使得默认安装的 KubeSphere 变得更加轻量。
  * KubeSphere 已有的众多组件都被拆分为单独的 KubeSphere 扩展组件。这些扩展组件可以单独进行迭代，用户可以自行选择安装哪些扩展组件，以打造符合其需求的 KubeSphere 容器管理平台。
  * 用户可以借助相对简单的扩展组件开发指南，开发自己的扩展组件以扩展 KubeSphere 的功能。
  * 通过 KubeSphere 扩展中心，统一管理各扩展组件。
  * 为了丰富 KubeSphere 扩展组件的生态系统，我们还提供了 KubeSphere Marketplace 扩展市场。用户可以将自己开发的扩展组件上架至 KubeSphere 扩展市场，供其他用户使用甚至赚取收益。

## KubeSphere LuBan 架构的优势

KubeSphere LuBan 架构的优势可以从多个角度分析，包括 KubeSphere 维护者、KubeSphere
贡献者、云原生应用开发商（ISV）和其它开源项目、以及 KubeSphere 用户：

  * 对于 KubeSphere 维护者：LuBan 架构引入的扩展机制使维护者能够更专注于开发 KubeSphere 核心功能，使 ks-core 变得更轻量化，同时可以提高版本发布速度。对于其它功能，由于采用扩展组件实现，这些组件可以独立迭代，更及时地满足用户需求。

  * 对于 KubeSphere 贡献者：扩展机制的引入使 ks-core 和其它 KubeSphere 扩展组件之间更松耦合，开发也更加容易上手。

  * 对于云原生应用开发商（ISV）和其它开源项目：KubeSphere LuBan 架构的扩展机制允许 ISV 和其它开源项目以较低的成本将其产品或项目顺利集成到 KubeSphere 生态系统中。例如，Karmada 和 KubeEdge 的开发者可以基于这一扩展机制开发适用于 KubeSphere 的自定义控制台。

  * 对于 KubeSphere 用户：用户可以自由选择启用哪些 KubeSphere 扩展组件，还能将自己的组件顺利集成到 KubeSphere 控制台中。随着 KubeSphere 扩展组件生态的不断丰富，用户可以在 KubeSphere 扩展市场中选择更多丰富的产品和服务，实现容器管理平台的高度个性化。

[ __](/extension-dev-guide/zh/ "KubeSphere 扩展组件开发指南")[__](/extension-dev-
guide/zh/overview/overview/ "扩展组件概述")



---

# 经验分享

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/best-practice/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/best-practice/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 经验分享

# 经验分享

  * [扩展组件开发案例](/extension-dev-guide/zh/best-practice/develop-example/)

介绍一个扩展组件开发案列，包括完整的开发打包和发布流程

  * [Databend Playground 开发小记](/extension-dev-guide/zh/best-practice/databend-playground/)

介绍 Databend Playground 的开发经验和总结

[ __](/extension-dev-guide/zh/videos/flomesh-service-mesh/ "Flomesh Service
Mesh \(FSM\) 示例")[__](/extension-dev-guide/zh/best-practice/develop-example/
"扩展组件开发案例")



---

# 参考资料

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/references/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 参考资料

# 参考资料

  * [ksbuilder CLI 参考](/extension-dev-guide/zh/references/ksbuilder/)

ksbuilder 扩展组件打包、发布工具

  * [KubeDesign](/extension-dev-guide/zh/references/kubedesign/)

KubeDesign 前端 UI 组件库

  * [create-ks-project CLI reference](/extension-dev-guide/zh/references/create-ks-project/)

介绍 KubeSphere 前端开发脚手架工具

  * [KubeSphere API reference](/extension-dev-guide/zh/references/kubesphere-api/)

KubeSphere API

  * [KubeSphere API 概念](/extension-dev-guide/zh/references/kubesphere-api-concepts/)

KubeSphere API 概念

[ __](/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/ "从 4.0 升级到
4.1.x")[__](/extension-dev-guide/zh/references/ksbuilder/ "ksbuilder CLI 参考")



---

# 国际化

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/internationalization/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/internationalization/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [扩展能力](/extension-dev-
guide/zh/feature-customization/) > 国际化

# 国际化

本节介绍如何实现扩展组件前端页面的国际化。

KubeSphere Core 集成了 [i18next](https://www.i18next.com/)
作为国际化组件，支持通过自定义语言包实现扩展组件前端多语言显示。

## 语言包

扩展组件前端模块中的 `src/locales` 目录用于存放扩展组件的语言包。默认情况下，它包括英文语言包 `en` 和简体中文语言包
`zh`，还可以根据需要手动创建其他语言包。前端界面的词条通常保存在 JSON 文件中，支持在每个语言包中创建多个 JSON 文件。

    
    
    kubesphere-extensions
    └── frontend
        └── extensions
            └── hello-world
                └── src
                    └── locales
                        ├── en
                        │   ├── base.json
                        │   └── index.js
                        ├── index.js
                        └── zh
                            ├── base.json
                            └── index.js
    

## 开发步骤

下面以 [Hello World](/extension-dev-guide/zh/quickstart/hello-world-extension/)
扩展组件为例，演示如何在扩展组件前端分别显示英文词条 `Hello World! The current language code is
{languageCode}.` 和中文词条`你好世界！当前的语言代码为 {languageCode}。`，并向 `{languageCode}`
变量动态传入当前环境的语言代码。

  1. 在 `src/locales/en/base.json` 文件和 `src/locales/zh/base.json` 文件中分别添加以下词条：
         
         // src/locales/en/base.json
         {
           "HELLO_WORLD_DESC": "Hello World! The current language code is {languageCode}."
         }
         
         
         // src/locales/zh/base.json
         {
           "HELLO_WORLD_DESC": "你好世界！当前的语言代码为 {languageCode}。"
         }
         

为了避免 core 和各扩展组件的词条 key 重复，建议在词条前加上扩展组件 name 的前缀，例如
`HELLO_WORLD.HELLO_WORLD_DESC`。后续我们可能会对重复词条进行检测和限制。

  2. 在扩展组件的入口文件（例如 `src/index.js` ）中引入语言包：
         
         import routes from './routes';
         import locales from './locales';  // 引入语言包
         
         const menus = [
          {
            parent: 'topbar',
            name: 'hello-world',
            link: '/hello-world',
            title: 'HELLO_WORLD',
            icon: 'cluster',
            order: 0,
            desc: 'HELLO_WORLD_DESC',
            skipAuth: true,
         }
         ];
         
         const extensionConfig = {
           routes,
           menus,
           locales,
         };
         
         extensionConfig default extensionConfig;
         

  3. 在扩展组件前端开发过程中，使用全局函数 `t()` 获取词条内容并向变量传入动态值。例如，在 `src/App.jsx` 文件中编写以下代码：
         
         export default function App() {
           return <Wrapper>{t('HELLO_WORLD_DESC', {languageCode: globals.user.lang})}</Wrapper>;
         }
         

  4. 在 `frontend` 目录下执行 `yarn dev` 命令启动前端环境。

  5. 访问 `http://localhost:8000` 并登录，在页面右上角点击当前用户的名称，然后选择`用户设置`切换语言。

在 `English` 和`简体中文`语言环境下点击 `Hello World` 将分别显示以下文字：

![](./locale-demo-en.png) ![](./locale-demo-zh.png)

[__](/extension-dev-guide/zh/feature-customization/access-control/
"访问控制")[__](/extension-dev-guide/zh/feature-customization/route/ "页面路由")



---

# 迁移指南

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/migration/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/migration/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 迁移指南

# 迁移指南

此章节包含从旧版本的 KubeSphere 迁移到新版本的相关信息。

  * [从 4.0 升级到 4.1.x](/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/)

如何从 4.0.0 升级到 4.1.x 版本

[ __](/extension-dev-guide/zh/faq/01-difference/ "扩展组件 vs 应用")[__](/extension-
dev-guide/zh/migration/4.0.0-to-4.1.x/ "从 4.0 升级到 4.1.x")



---

# OpenKruiseGame Dashboard 示例

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/videos/openkruisegame-dashboard/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/videos/openkruisegame-
dashboard.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [视频演示](/extension-dev-
guide/zh/videos/) > OpenKruiseGame Dashboard 示例

# OpenKruiseGame Dashboard 示例

[ __](/extension-dev-guide/zh/videos/develop-an-extension/ "开发 KubeSphere
扩展组件")[__](/extension-dev-guide/zh/videos/databend-playground/ "Databend
Playground 示例")



---

# FAQ

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/FAQ/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/faq/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > FAQ

# FAQ

  * [扩展组件 vs 应用](/extension-dev-guide/zh/faq/01-difference/)

介绍扩展组件和应用的不同点

[ __](/extension-dev-guide/zh/best-practice/databend-playground/ "Databend
Playground 开发小记")[__](/extension-dev-guide/zh/faq/01-difference/ "扩展组件 vs 应用")



---

# FAQ

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/faq/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/faq/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > FAQ

# FAQ

  * [扩展组件 vs 应用](/extension-dev-guide/zh/faq/01-difference/)

介绍扩展组件和应用的不同点

[ __](/extension-dev-guide/zh/best-practice/databend-playground/ "Databend
Playground 开发小记")[__](/extension-dev-guide/zh/faq/01-difference/ "扩展组件 vs 应用")



---

# 参考资料

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/references/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 参考资料

# 参考资料

  * [ksbuilder CLI 参考](/extension-dev-guide/zh/references/ksbuilder/)

ksbuilder 扩展组件打包、发布工具

  * [KubeDesign](/extension-dev-guide/zh/references/kubedesign/)

KubeDesign 前端 UI 组件库

  * [create-ks-project CLI reference](/extension-dev-guide/zh/references/create-ks-project/)

介绍 KubeSphere 前端开发脚手架工具

  * [KubeSphere API reference](/extension-dev-guide/zh/references/kubesphere-api/)

KubeSphere API

  * [KubeSphere API 概念](/extension-dev-guide/zh/references/kubesphere-api-concepts/)

KubeSphere API 概念

[ __](/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/ "从 4.0 升级到
4.1.x")[__](/extension-dev-guide/zh/references/ksbuilder/ "ksbuilder CLI 参考")



---

# UI 扩展

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/extending-ui/


    System.register(["react","styled-components"],(function(t,e){var r={},n={};return{setters:[function(t){r.default=t.default},function(t){n.default=t.default}],execute:function(){t(function(){var t={477:function(t,e,r){var n={"./base.json":77};function o(t){var e=i(t);return r(e)}function i(t){if(!r.o(n,t)){var e=new Error("Cannot find module '"+t+"'");throw e.code="MODULE_NOT_FOUND",e}return n[t]}o.keys=function(){return Object.keys(n)},o.resolve=i,t.exports=o,o.id=477},422:function(t,e,r){var n={"./base.json":214};function o(t){var e=i(t);return r(e)}function i(t){if(!r.o(n,t)){var e=new Error("Cannot find module '"+t+"'");throw e.code="MODULE_NOT_FOUND",e}return n[t]}o.keys=function(){return Object.keys(n)},o.resolve=i,t.exports=o,o.id=422},725:function(t,e,r){var n=r(825).y;e.w=function(t){if(t||(t=1),!r.y.meta||!r.y.meta.url)throw console.error("__system_context__",r.y),Error("systemjs-webpack-interop was provided an unknown SystemJS context. Expected context.meta.url, but none was provided");r.p=n(r.y.meta.url,t)}},825:function(t,e,r){function n(t,e){var r=document.createElement("a");r.href=t;for(var n="/"===r.pathname[0]?r.pathname:"/"+r.pathname,o=0,i=n.length;o!==e&&i>=0;){"/"===n[--i]&&o++}if(o!==e)throw Error("systemjs-webpack-interop: rootDirectoryLevel ("+e+") is greater than the number of directories ("+o+") in the URL path "+t);var c=n.slice(0,i+1);return r.protocol+"//"+r.host+c}e.y=n;var o=Number.isInteger||function(t){return"number"==typeof t&&isFinite(t)&&Math.floor(t)===t}},726:function(t){"use strict";t.exports=r},815:function(t){"use strict";t.exports=n},77:function(t){"use strict";t.exports={name:"Name"}},214:function(t){"use strict";t.exports={name:"名称"}}},o={};function i(e){var r=o[e];if(void 0!==r)return r.exports;var n=o[e]={exports:{}};return t[e](n,n.exports,i),n.exports}i.y=e,i.d=function(t,e){for(var r in e)i.o(e,r)&&!i.o(t,r)&&Object.defineProperty(t,r,{enumerable:!0,get:e[r]})},i.g=function(){if("object"==typeof globalThis)return globalThis;try{return this||new Function("return this")()}catch(t){if("object"==typeof window)return window}}(),i.o=function(t,e){return Object.prototype.hasOwnProperty.call(t,e)},i.r=function(t){"undefined"!=typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(t,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(t,"__esModule",{value:!0})},function(){var t;i.g.importScripts&&(t=i.g.location+"");var e=i.g.document;if(!t&&e&&(e.currentScript&&(t=e.currentScript.src),!t)){var r=e.getElementsByTagName("script");if(r.length)for(var n=r.length-1;n>-1&&(!t||!/^http(s?):/.test(t));)t=r[n--].src}if(!t)throw new Error("Automatic publicPath is not supported in this browser");t=t.replace(/#.*$/,"").replace(/\?.*$/,"").replace(/\/[^\/]+$/,"/"),i.p=t}();var c={};return(0,i(725).w)(1),function(){"use strict";i.r(c),i.d(c,{default:function(){return j}});var t=i(726),e=i(815).default.h3.withConfig({displayName:"App__Wrapper",componentId:"sc-1bs6lxk-0"})(["margin:8rem auto;text-align:center;"]);function r(){return t.default.createElement(e,null,"Say hi to the world!")}var n=[{path:"/hello-world",element:t.default.createElement(r,null)}];function o(t){return o="function"==typeof Symbol&&"symbol"==typeof Symbol.iterator?function(t){return typeof t}:function(t){return t&&"function"==typeof Symbol&&t.constructor===Symbol&&t!==Symbol.prototype?"symbol":typeof t},o(t)}function u(t){var e=function(t,e){if("object"!=o(t)||!t)return t;var r=t[Symbol.toPrimitive];if(void 0!==r){var n=r.call(t,e||"default");if("object"!=o(n))return n;throw new TypeError("@@toPrimitive must return a primitive value.")}return("string"===e?String:Number)(t)}(t,"string");return"symbol"==o(e)?e:e+""}function a(t,e,r){return(e=u(e))in t?Object.defineProperty(t,e,{value:r,enumerable:!0,configurable:!0,writable:!0}):t[e]=r,t}function s(t,e){var r=Object.keys(t);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(t);e&&(n=n.filter((function(e){return Object.getOwnPropertyDescriptor(t,e).enumerable}))),r.push.apply(r,n)}return r}function f(t){for(var e=1;e<arguments.length;e++){var r=null!=arguments[e]?arguments[e]:{};e%2?s(Object(r),!0).forEach((function(e){a(t,e,r[e])})):Object.getOwnPropertyDescriptors?Object.defineProperties(t,Object.getOwnPropertyDescriptors(r)):s(Object(r)).forEach((function(e){Object.defineProperty(t,e,Object.getOwnPropertyDescriptor(r,e))}))}return t}for(var l=i(422),p=l.keys().filter((function(t){return"./index.ts"!==t})),y={},b=0;b<p.length;b+=1)p[b].startsWith(".")&&(y=f(f({},y),l(p[b])));var m=y;function d(t,e){var r=Object.keys(t);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(t);e&&(n=n.filter((function(e){return Object.getOwnPropertyDescriptor(t,e).enumerable}))),r.push.apply(r,n)}return r}function v(t){for(var e=1;e<arguments.length;e++){var r=null!=arguments[e]?arguments[e]:{};e%2?d(Object(r),!0).forEach((function(e){a(t,e,r[e])})):Object.getOwnPropertyDescriptors?Object.defineProperties(t,Object.getOwnPropertyDescriptors(r)):d(Object(r)).forEach((function(e){Object.defineProperty(t,e,Object.getOwnPropertyDescriptor(r,e))}))}return t}for(var h=i(477),O=h.keys().filter((function(t){return"./index.ts"!==t})),g={},w=0;w<O.length;w+=1)O[w].startsWith(".")&&(g=v(v({},g),h(O[w])));var j={routes:n,menus:[{parent:"topbar",name:"hello-world",title:"HELLO_WORLD",icon:"cluster",order:0,desc:"Say hi to the world!",skipAuth:!0}],locales:{zh:m,en:g}}}(),c}())}}}));
    



---

# 从 4.0 升级到 4.1.x

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-
guide/content/zh/migration/4.0.0-to-4.1.x/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [迁移指南](/extension-dev-
guide/zh/migration/) > 从 4.0 升级到 4.1.x

# 从 4.0 升级到 4.1.x

### 4.1.2

#### 前端

##### 安装/升级 KubeSphere 依赖包

安装/升级 `create-ks-project`

    
    
    npm install -g create-ks-project
    

安装/升级 KubeSphere Console 依赖包

  * [`@ks-console/appstore`](https://www.npmjs.com/package/@ks-console/appstore)
  * [`@ks-console/bootstrap`](https://www.npmjs.com/package/@ks-console/bootstrap)
  * [`@ks-console/console`](https://www.npmjs.com/package/@ks-console/console)
  * [`@ks-console/core`](https://www.npmjs.com/package/@ks-console/core)
  * [`@ks-console/locales`](https://www.npmjs.com/package/@ks-console/locales)
  * [`@ks-console/server`](https://www.npmjs.com/package/@ks-console/server)
  * [`@ks-console/shared`](https://www.npmjs.com/package/@ks-console/shared)

    
    
    yarn add -W \
      @ks-console/appstore@latest \
      @ks-console/bootstrap@latest \
      @ks-console/console@latest \
      @ks-console/core@latest \
      @ks-console/locales@latest \
      @ks-console/server@latest \
      @ks-console/shared@latest
    

`@ks-console/*` 的版本最好和 KubeSphere 的版本保持一致。

安装/升级 Kube Design

  * [`@kubed/charts`](https://www.npmjs.com/package/@kubed/charts)
  * [`@kubed/code-editor`](https://www.npmjs.com/package/@kubed/code-editor)
  * [`@kubed/components`](https://www.npmjs.com/package/@kubed/components)
  * [`@kubed/diff-viewer`](https://www.npmjs.com/package/@kubed/diff-viewer)
  * [`@kubed/hooks`](https://www.npmjs.com/package/@kubed/hooks)
  * [`@kubed/icons`](https://www.npmjs.com/package/@kubed/icons)
  * [`@kubed/log-viewer`](https://www.npmjs.com/package/@kubed/log-viewer)

    
    
    yarn add -W \
      @kubed/charts@latest \
      @kubed/code-editor@latest \
      @kubed/components@latest \
      @kubed/diff-viewer@latest \
      @kubed/hooks@latest \
      @kubed/icons@latest \
      @kubed/log-viewer@latest
    

如果 @ks-console/* 版本 >=4.1.0，需要将 Kube Design 等依赖升级到最新版本。

否则在本地运行和打包时，可能会出现报错信息。

##### 扩展组件外部依赖改变

在 KubeSphere 4.1.2 之前，core 会提供一些常用的依赖库，扩展组件无需安装这些依赖即可直接 import
使用，这些依赖被称为扩展组件的外部依赖。

然而，如果扩展组件的外部依赖导致功能异常时，扩展组件需要等待 core 更新依赖才能修复。这显然违背了扩展机制的初衷。

因此，从 4.1.2 开始，我们移除了一些扩展组件的外部依赖，具体如下：

  * lodash
  * react-is
  * react-markdown

扩展组件如需使用这些库，需要自行安装，import 和使用方法不变。

##### 拆分 Webpack 自定义配置

在 KubeSphere 4.1.2 之前，只有一个 Webpack 自定义配置文件，即
`configs/webpack.config.js`。该文件既用于本地运行 KubeSphere Console（`yarn dev` 和 `yarn
dev:client`）时的 Webpack 自定义配置，又用于打包扩展组件前端（`yarn build:ext`）时的 Webpack 自定义配置。

从 4.1.2 开始，Webpack 自定义配置文件分为 2 个：

  * `configs/webpack.config.js`：用于本地运行 KubeSphere Console（`yarn dev` 和 `yarn dev:client`）的 Webpack 自定义配置。
  * `configs/webpack.extensions.config.js`：用于打包扩展组件前端（`yarn build:ext`）的 Webpack 自定义配置。

##### 弃用本地 production 模式

由于可以直接访问远端的 KubeSphere Console 查看扩展组件，因此不再需要本地的 production 模式。

因此，弃用 `package.json` 中 `scripts` 的 `build:prod` 和 `start` 命令。

### 4.1.0

#### 前端

##### 扩展组件配置方式改变

从 KubeSphere 4.1.0 开始，扩展组件前端需要把配置导出

    
    
    export default extensionConfig;
    

而不是之前的注册扩展组件方式

    
    
    globals.context.registerExtension(extensionConfig);
    

[__](/extension-dev-guide/zh/migration/ "迁移指南")[__](/extension-dev-
guide/zh/references/ "参考资料")



---

# create-ks-project CLI reference

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references/create-ks-project/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/references/create-ks-
project.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [参考资料](/extension-dev-
guide/zh/references/) > create-ks-project CLI reference

# create-ks-project CLI reference

## create-ks-project

KubeSphere 前端开发脚手架工具，执行后将会在指定目录下创建一个前端脚手架文件夹，并安装相应前端依赖。

使用方式：

    
    
    yarn create ks-project [project-name]
    

可选参数：

    
    
      -V, --version    打印版本号
      -f, --fast-mode  直接使用打包好的依赖压缩包进行安装
    
      -h, --help       打印帮助信息
    

[__](/extension-dev-guide/zh/references/kubedesign/
"KubeDesign")[__](/extension-dev-guide/zh/references/kubesphere-api/
"KubeSphere API reference")



---

# 参考资料

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references/index.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/references/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 参考资料

# 参考资料

  * [ksbuilder CLI 参考](/extension-dev-guide/zh/references/ksbuilder/)

ksbuilder 扩展组件打包、发布工具

  * [KubeDesign](/extension-dev-guide/zh/references/kubedesign/)

KubeDesign 前端 UI 组件库

  * [create-ks-project CLI reference](/extension-dev-guide/zh/references/create-ks-project/)

介绍 KubeSphere 前端开发脚手架工具

  * [KubeSphere API reference](/extension-dev-guide/zh/references/kubesphere-api/)

KubeSphere API

  * [KubeSphere API 概念](/extension-dev-guide/zh/references/kubesphere-api-concepts/)

KubeSphere API 概念

[ __](/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/ "从 4.0 升级到
4.1.x")[__](/extension-dev-guide/zh/references/ksbuilder/ "ksbuilder CLI 参考")



---

# 后端扩展机制

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/overview/backend-extension-architecture/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/overview/backend-
extension-architecture/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [概述](/extension-dev-
guide/zh/overview/) > 后端扩展机制

# 后端扩展机制

KubeSphere 构建在 K8s 之上，和 K8s 一样也具备高度可配置和可扩展的特性，除了可以借助 [K8s
的扩展机制](https://kubernetes.io/docs/concepts/extend-kubernetes/)来扩展 KubeSphere
的平台能力之外，KubeSphere 还提供了更为灵活的扩展方式。

`ks-apiserver` 是 KubeSphere 的 API 网关，提供了统一的认证、鉴权和请求代理能力，借助 `ks-apiserver`
的聚合层，可以对 KubeSphere 的 API 进行扩展：

![luban-backend-extension-architecture](/extension-dev-
guide/zh/overview/backend-extension-architecture/luban-backend-extension-
architecture.png?width=800px)

### 认证与鉴权

KubeSphere 提供了统一的用户管理和 API 认证功能，同时还提供了多租户体系以及[基于角色的访问控制](/extension-dev-
guide/zh/feature-customization/access-control/)能力。在扩展 KubeSphere 的 API
时，可以轻松地重用这些能力。

### 请求代理

KubeSphere 的聚合层为扩展组件提供了统一的代理转发能力，通过简单的配置，即可将请求转发到集群内部、集群外部，或被纳管的 Kubernetes
集群中。详细信息请参考 [API 扩展](/extension-dev-guide/zh/feature-customization/extending-
api/)章节。

[ __](/extension-dev-guide/zh/overview/frontend-extension-architecture/
"前端扩展机制")[__](/extension-dev-guide/zh/overview/development-process/
"扩展组件开发流程")



---

# KubeSphere API 概念

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/references/kubesphere-api-concepts/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/references/kubesphere-
api-concepts.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [参考资料](/extension-dev-
guide/zh/references/) > KubeSphere API 概念

# KubeSphere API 概念

KubeSphere API 是 K8s API 的超集，沿用了 K8s API 的设计，通过 HTTP 提供了基于资源 (RESTful) 的编程接口。
它支持通过标准 HTTP 动词（POST、PUT、PATCH、DELETE、GET）来检索、创建、更新和删除主要资源。

在使用 KubeSphere API 之前，**您需要先阅读并理解** [K8s API 的概念](https://kubernetes.io/zh-
cn/docs/reference/using-api/api-concepts/)。

KubeSphere 提供了 K8s API 代理，通过 `/apis`、`/api` 前缀可以直接访问 K8s 的 API。此外，KubeSphere 在
K8s 的基础上支持额外的资源层级，包括平台级资源（例如用户、集群、企业空间等），以及企业空间级资源。KubeSphere 扩展的 API 通常以
`/kapis` 为前缀。

例如:

  * `/api/v1/namespaces`
  * `/api/v1/pods`
  * `/api/v1/namespaces/my-namespace/pods`
  * `/apis/apps/v1/deployments`
  * `/apis/apps/v1/namespaces/my-namespace/deployments`
  * `/apis/apps/v1/namespaces/my-namespace/deployments/my-deployment`
  * `/kapis/iam.kubesphere.io/v1beta1/users`
  * `/kapis/tenant.kubesphere.io/v1alpha2/workspaces/my-workspace/namespaces`

### 多集群

KubeSphere 支持 K8s 多集群纳管。只要在请求路径之前添加集群标识作为前缀，就可以通过 API 直接访问 member 集群。

例如:

  * `/clusters/host/api/v1/namespaces`
  * `/clusters/member/api/v1/namespaces`

[ __](/extension-dev-guide/zh/references/kubesphere-api/ "KubeSphere API
reference")[__](/extension-dev-guide/zh/references/ksbuilder/ "ksbuilder CLI
参考")



---

# 概述

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/overview.html

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/overview/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 概述

# 概述

## 为什么在 KubeSphere 4.0 引入扩展机制

自 2018 年 KubeSphere 混合多云容器管理平台诞生以来，已经发布了十几个版本，包括 3
个大版本。为了满足不断增长的用户需求，KubeSphere
集成了众多企业级功能，如多租户管理、多集群管理、DevOps、GitOps、服务网格、微服务、可观测性（包括监控、告警、日志、审计、事件、通知等）、应用商店、边缘计算、网络与存储管理等。

首先，尽管这些功能满足了用户在容器管理平台方面的基本需求，却引发了一些挑战，比如：

  * 版本发布周期较长：需要等待所有组件完成开发、测试，并通过集成测试。这导致了不必要的等待时间，使用户难以及时获得新功能和修复。
  * 响应不及时：KubeSphere 的组件难以单独迭代，因此社区和用户提出的反馈需要等待 KubeSphere 发布新版本才能解决。这降低了对用户反馈的快速响应能力。
  * 前后端代码耦合：尽管目前已能实现单独启用/禁用特定组件，但这些组件的前后端代码仍然耦合在一起，容易相互影响，架构上不够清晰和模块化。
  * 组件默认启用：部分组件默认启用，这可能会占用过多的系统资源，尤其对于没有相关需求的用户。

其次，云原生领域的创新非常活跃。通常在同一个领域存在多种选择，例如：

  * GitOps 用户可以选用 ArgoCD 或 FluxCD；
  * 服务网格用户可以选择 Istio 或 Linkerd 或其它实现；
  * 联邦集群管理可选择 Karmada、OCM 或 Clusternet；
  * 日志管理可以采用 Elasticsearch 或 Loki；
  * 边缘计算框架可使用 KubeEdge、OpenYurt 或 SuperEdge；
  * 存储和网络领域也提供了众多选择。

KubeSphere 通常会优先支持其中一种实现，但用户常常有对其它实现的需求。

此外，在使用 KubeSphere 的过程中，用户通常会面临以下问题：

  * 用户将自己的应用发布到 KubeSphere 后，应用的管理界面无法与 KubeSphere 控制台无缝集成，因而无法在 KubeSphere 内一体化管理自己的应用。通常需要用户自行配置应用的 Service，如 NodePort 或 LB，以便在新窗口中管理应用；
  * 由于无法与 KubeSphere 控制台集成，用户的应用无法充分利用 KubeSphere 提供的认证鉴权、多租户管理等平台级功能，安全性受到影响；
  * 用户需求多种多样，不同用户对相同功能的需求存在显著差异，有时甚至相互冲突。原有架构由于耦合式的组件集成方式，难以满足用户多样化的需求；
  * 如果用户希望通过向 KubeSphere 提交 PR 来满足自己的需求，通常需要了解完整的 KubeSphere 开发流程。这包括前后端开发、调试、安装、部署和配置等一系列问题，门槛相对较高；
  * 此外，提交了 PR 后，需要等待 KubeSphere 发布新版本才能使用；
  * 由于发布周期较长，许多用户会自行在 KubeSphere 上定制化自己的需求，逐渐脱离社区，违背了开源社区 “upstream first” 的理念，从长远来看，将无法享受到上游越来越多的功能。

## KubeSphere 4.0 扩展机制简介

为了应对上述各种问题，KubeSphere 在 4.0 版本引入了全新的微内核架构，代号为 “LuBan”：

  * 通过 LuBan，可以实现前后端功能的动态扩展。
  * KubeSphere 的核心组件被精简为 ks-core，使得默认安装的 KubeSphere 变得更加轻量。
  * KubeSphere 已有的众多组件都被拆分为单独的 KubeSphere 扩展组件。这些扩展组件可以单独进行迭代，用户可以自行选择安装哪些扩展组件，以打造符合其需求的 KubeSphere 容器管理平台。
  * 用户可以借助相对简单的扩展组件开发指南，开发自己的扩展组件以扩展 KubeSphere 的功能。
  * 通过 KubeSphere 扩展中心，统一管理各扩展组件。
  * 为了丰富 KubeSphere 扩展组件的生态系统，我们还提供了 KubeSphere Marketplace 扩展市场。用户可以将自己开发的扩展组件上架至 KubeSphere 扩展市场，供其他用户使用甚至赚取收益。

## KubeSphere LuBan 架构的优势

KubeSphere LuBan 架构的优势可以从多个角度分析，包括 KubeSphere 维护者、KubeSphere
贡献者、云原生应用开发商（ISV）和其它开源项目、以及 KubeSphere 用户：

  * 对于 KubeSphere 维护者：LuBan 架构引入的扩展机制使维护者能够更专注于开发 KubeSphere 核心功能，使 ks-core 变得更轻量化，同时可以提高版本发布速度。对于其它功能，由于采用扩展组件实现，这些组件可以独立迭代，更及时地满足用户需求。

  * 对于 KubeSphere 贡献者：扩展机制的引入使 ks-core 和其它 KubeSphere 扩展组件之间更松耦合，开发也更加容易上手。

  * 对于云原生应用开发商（ISV）和其它开源项目：KubeSphere LuBan 架构的扩展机制允许 ISV 和其它开源项目以较低的成本将其产品或项目顺利集成到 KubeSphere 生态系统中。例如，Karmada 和 KubeEdge 的开发者可以基于这一扩展机制开发适用于 KubeSphere 的自定义控制台。

  * 对于 KubeSphere 用户：用户可以自由选择启用哪些 KubeSphere 扩展组件，还能将自己的组件顺利集成到 KubeSphere 控制台中。随着 KubeSphere 扩展组件生态的不断丰富，用户可以在 KubeSphere 扩展市场中选择更多丰富的产品和服务，实现容器管理平台的高度个性化。

[ __](/extension-dev-guide/zh/ "KubeSphere 扩展组件开发指南")[__](/extension-dev-
guide/zh/overview/overview/ "扩展组件概述")



---

# Weave Scope

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/examples/third-party-component-integration-example/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/examples/third-party-
component-integration-example/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [开发示例](/extension-dev-
guide/zh/examples/) > Weave Scope

# Weave Scope

本节将以 Weave Scope 集成为例，介绍如何快速将已有 Web UI 的第三方工具和系统通过 iframe 整合到扩展组件中。

[Weave Scope](https://github.com/weaveworks/scope)
可以自动生成应用程序的映射，以便您直观地理解、监视和控制基于容器化微服务的应用程序。

### 部署 Weave Scope

参考文档[部署 Weave
Scope](https://www.weave.works/docs/scope/latest/installing)，或通过以下命令在 K8s
集群中一键部署 Weave Scope。

    
    
    kubectl apply -f https://raw.githubusercontent.com/kubesphere/extension-samples/master/extensions-backend/weave-scope/manifests.yaml
    

### 为 Weave Scope 创建反向代理

    
    
    kubectl apply -f https://raw.githubusercontent.com/kubesphere/extension-samples/master/extensions-backend/weave-scope/weave-scope-reverse-proxy.yaml
    

### 前端扩展组件开发

从 GitHub 上克隆本示例的代码，然后参照[创建 Hello World 扩展组件](/extension-dev-
guide/zh/quickstart/hello-world-extension/)进行创建项目、本地开发和调试。

    
    
    cd  ~/kubesphere-extensions
    git clone https://github.com/kubesphere/extension-samples.git
    cp -r ~/kubesphere-extensions/extension-samples/extensions-frontend/extensions/weave-scope ~/kubesphere-extensions/ks-console/extensions
    

接下来，将重点介绍如何将 Weave Scope 的页面集成到扩展组件。

文件路径： `~/kubesphere-extensions/ks-console/extensions/weave-scope/src/App.jsx`

    
    
    import React, { useState, useRef } from 'react';
    import { Loading } from '@kubed/components';
    import { useLocalStorage } from '@kubed/hooks';
    
    export default function App() {
      const [loading, setLoading] = useState(true);
    
      const FRAME_URL = '/proxy/weave.works/#!/state/{"topologyId":"pods"}';
    
      const iframeRef = useRef();
    
      const onIframeLoad = () => {
        const iframeDom = iframeRef.current?.contentWindow.document;
        if (iframeDom) {
          if (iframeDom.querySelector('#app > div > div.header > div')) {
            iframeDom.querySelector('#app > div > div.header > div').style.display = 'none';
          }
        }
        setLoading(false);
      };
    
      return (
        <>
          {loading && <Loading className="page-loading" />}
          <iframe
            ref={iframeRef}
            src={FRAME_URL}
            width="100%"
            height="100%"
            frameBorder="0"
            style={{
              height: 'calc(100vh - 68px)',
              display: loading ? 'none' : 'block',
            }}
            onLoad={onIframeLoad}
          />
        </>
      );
    }
    

以上代码主要完成了以下两个任务：

  1. 将 Weave Scope 页面以 `iframe` 的形式嵌入到扩展组件中。`FRAME_URL` 为 Weave Scope 的反向代理地址，且与 KubeSphere 页面地址**同源** 。

由于浏览器的同源策略（Same-Origin Policy），如果第三方系统网页与 KubeSphere 前端网页不同源，将无法使用 JavaScript
直接读取和操作第三方系统的 iframe。通常，需要由后端将第三方系统的前端访问地址处理成与 KubeSphere 前端访问地址同源（**同协议**
、**同主机** 、**同端口** ）的地址。

2\. 调整 Weave Scope 页面的样式。由于同源，扩展组件可以通过 `React` 的 `ref` 读取和操作 Weave Scope
页面（`iframe`）的 DOM，从而调整页面的样式，将 selector 部分隐藏。

通过 `yarn dev` 启动本地预览环境，然后通过扩展组件入口访问到以下页面。

![weave-scope-dashboard](/extension-dev-guide/zh/examples/third-party-
component-integration-example/sample-weave-scope-dashboard.png?width=1200px)

[ __](/extension-dev-guide/zh/examples/gatekeeper-extension/
"Gatekeeper")[__](/extension-dev-guide/zh/examples/external-link-example/
"外部链接")



---

# 开发示例

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/examples/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/examples/_index.md
"编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > 开发示例

# 开发示例

  * [Gatekeeper](/extension-dev-guide/zh/examples/gatekeeper-extension/)

集成 Gatekeeper

  * [Weave Scope](/extension-dev-guide/zh/examples/third-party-component-integration-example/)

快速集成已有 Web UI 的第三方工具与系统

  * [外部链接](/extension-dev-guide/zh/examples/external-link-example/)

如何在扩展组件中打开外部链接

[ __](/extension-dev-guide/zh/feature-customization/license/ "自定义扩展组件的
license")[__](/extension-dev-guide/zh/examples/gatekeeper-extension/
"Gatekeeper")



---

# 测试扩展组件

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/packaging-and-release/testing/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/packaging-and-
release/testing/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [打包发布](/extension-dev-
guide/zh/packaging-and-release/) > 测试扩展组件

# 测试扩展组件

扩展组件打包好之后，需要将扩展组件推送到远端环境，通过扩展组件商店进行部署测试。

## 推送扩展组件

通过 `ksbuilder publish <dir>/<extension package>` 命令，可以将扩展组件推送到远端的扩展组件商店。

    
    
    ➜  extension-samples git:(master) ✗ cd extensions
    ➜  extensions git:(master) ✗ ksbuilder package hello-world    
    package extension hello-world
    package saved to /Users/hongming/GitHub/extension-samples/extensions/hello-world-0.1.0.tgz
    ➜  extensions git:(master) ✗ ksbuilder publish hello-world-0.1.0.tgz 
    publish extension hello-world-0.1.0.tgz
    creating Extension hello-world
    creating ExtensionVersion hello-world-0.1.0
    creating ConfigMap extension-hello-world-0.1.0-chart
    

访问远端的 KubeSphere Console，在扩展组件商店可以看到推送上来的扩展组件。

![hello-world-extension](/extension-dev-guide/zh/packaging-and-
release/testing/hello-world-extension.png?width=1200px)

## 安装扩展组件

安装扩展组件

![install-hello-world-extension](/extension-dev-guide/zh/packaging-and-
release/testing/install-hello-world-extension.png?width=1200px)

扩展组件成功启用

![enable-hello-world-extension](/extension-dev-guide/zh/packaging-and-
release/testing/enable-hello-world-extension.png?width=1200px)

[ __](/extension-dev-guide/zh/packaging-and-release/packaging/
"打包扩展组件")[__](/extension-dev-guide/zh/packaging-and-release/release/ "发布扩展组件")



---

# 扩展组件开发流程

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/overview/development-process/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/overview/development-
process/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [概述](/extension-dev-
guide/zh/overview/) > 扩展组件开发流程

# 扩展组件开发流程

本章节介绍 KubeSphere 扩展组件的开发流程。

### 配置开发环境

在开发 KubeSphere 扩展组件之前，需要创建 K8s 集群并部署 KubeSphere Luban
为扩展组件提供基础的运行环境，安装必要的开发工具（Node.js、Yarn、create-ks-project、Helm、kubectl、ksbuilder
等等）。有关配置开发环境的更多信息，请参阅[搭建开发环境](/extension-dev-guide/zh/quickstart/prepare-
development-environment/)。

### 开发扩展组件

完成开发环境的配置后，请确保 KubeSphere Console 可以正常访问，开放必要的端口（kube-apiserver 6443, ks-
console 30880, ks-apiserver 30881 等端口），以便进行本地调试。

#### 创建扩展组件开发项目

如果你的扩展组件需要对 KubeSphere 的前端进行扩展，需要借助 `create-ks-project` 创建扩展组件的前端工程目录，步骤如下：

  1. 使用 `yarn create ks-project <NAME>` 初始化扩展组件的前端开发工程目录，借助此前端工程可本地运行 KubeSphere Console 并加载开发中的扩展组件。
  2. 使用 `yarn create:ext` 初始化扩展组件前端的源代码目录。

目录结构：

    
    
    kubesphere-extensions
    └── ks-console                              # 扩展组件前端开发工程目录
        ├── babel.config.js
        ├── configs
        │   ├── config.yaml
        │   ├── local_config.yaml               # KubeSphere Console 的配置文件
        │   ├── webpack.config.js               # 脚手架 Webpack 配置文件
        │   └── webpack.extensions.config.js    # 扩展组件前端打包 Webpack 配置文件
        ├── extensions                          # 扩展组件源代码目录
        │   └── hello-world                     # Hello World 扩展组件的源代码目录
        │       ├── package.json
        │       └── src
        │           ├── App.jsx                 # 扩展组件核心逻辑
        │           ├── index.js                # 扩展组件入口文件
        │           ├── locales                 # 扩展组件国际化
        │           └── routes                  # 扩展组件路由配置
        ├── package.json
        ├── tsconfig.base.json
        ├── tsconfig.json
        └── yarn.lock
    

如果你的扩展组件不包含前端扩展，可以跳过这一步骤。

#### 开发组件

完成扩展组件源代码目录的创建之后，即可开始编写扩展组件的核心逻辑。KubeSphere 提供了丰富的
API、和组件库，请参考[扩展能力](/extension-dev-guide/zh/feature-customization/)章节。

#### 本地调试

在扩展组件的开发过程中，[配置本地运行环境](/extension-dev-guide/zh/quickstart/hello-world-
extension/#配置本地运行环境)之后，可使用 `yarn dev` 命令在本地运行 KubeSphere Console 来调试扩展组件。

### 打包发布

开发完成后，需要借助 Helm、ksbuilder 对扩展组件进行编排、打包和发布。

#### 打包扩展组件

KubeSphere 使用 Helm 作为扩展组件的编排规范，若要了解更多信息，请参阅 [Helm
Docs](https://helm.sh/docs/)。在 Helm 的基础之上，KubeSphere
扩展组件提供了更丰富的元数据定义能力，详见[打包扩展组件](/extension-dev-guide/zh/packaging-and-
release/packaging/)。

#### 测试扩展组件

借助 ksbuilder 工具可以将编排好的扩展组件推送到开发环境中，以便进行部署与测试。详细信息请参考[测试扩展组件](/extension-dev-
guide/zh/packaging-and-release/testing/)。

#### 发布扩展组件

扩展组件经过测试后，可以使用 ksbuilder 工具将其提交到扩展市场（KubeSphere Marketplace）。

在将扩展组件提交到扩展市场之前，请务必详细阅读相关的协议、准则和条款。

[ __](/extension-dev-guide/zh/overview/backend-extension-architecture/
"后端扩展机制")[__](/extension-dev-guide/zh/quickstart/ "快速入门")



---

# API 扩展

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/feature-customization/extending-api/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/feature-
customization/extending-api/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [扩展能力](/extension-dev-
guide/zh/feature-customization/) > API 扩展

# API 扩展

## API 扩展

KubeSphere 提供灵活的 API 扩展方式，支持创建以下几种类型的 [Custom
Resource](https://kubernetes.io/docs/concepts/extend-kubernetes/api-
extension/custom-resources/)，以注册 API 或创建动态的代理规则。

在开始之前，请先了解 [KubeSphere API 概念](/extension-dev-guide/zh/references/kubesphere-
api-concepts/)，或查看[访问控制](/extension-dev-guide/zh/feature-customization/access-
control/)章节，了解更多有关 API 访问控制的内容。

在 KubeSphere 中，API 扩展主要有以下两种方式，它们适用于不同的场景。

### APIService

KubeSphere 提供了一种类似于 [Kubernetes API Aggregation
Layer](https://kubernetes.io/docs/concepts/extend-kubernetes/api-
extension/apiserver-aggregation/) 的 API 扩展机制，使用声明式的 API 注册机制。

APIService 是一种严格的声明式 API 定义方式，通过 API Group、API Version、Resource，以及 API
路径中定义的资源层级，与 KubeSphere 的访问控制和多租户权限管理体系紧密结合。对于那些可以抽象成声明式资源的 API，这是一种非常适用的扩展方式。

**APIService 示例与参数说明：**

    
    
     apiVersion: extensions.kubesphere.io/v1alpha1
    kind: APIService
    metadata:
      name: v1alpha1.example.kubesphere.io
    spec:
      group: example.kubesphere.io
      version: v1alpha1                                      
      url: http://apiserver.example.svc
    
    # caBundle: <Base64EncodedData>
    # insecureSkipTLSVerify: false
    
    # service:
    #   namespace: example
    #   name: apiserver
    #   port: 443
    

字段| 描述  
---|---  
`spec.group``spec.version`| 创建 APIService 类型的 CR 会向 ks-apiserver 动态注册
API，其中`spec.group`、`spec.version`表示所注册的 API 路径中的 API Group 与 API Version  
`spec.url``spec.caBundle``spec.insecureSkipTLSVerify`| 为 APIService 指定外部服务，将
API 请求代理到指定的 endpoint  
`spec.service`| 与 `spec.url` 类似，为 API 指定 K8s 集群内部的服务引用地址  
  
> 通过 `spec.service` 定义后端的 endpoint 默认需要启用 TLS，如需指定 HTTP 服务地址，需要通过 `spec.url`
> 显式指定 scheme 为 `http`。

### ReverseProxy

提供灵活的 API 反向代理声明，支持 rewrite、redirect、请求头注入、熔断、限流等配置。

需要用到 ks-apiserver 做反向代理，本地运行 KubeSphere Console 时需要增加如下 webpack 配置：

**webpack.config.js：**

    
    
     const { merge } = require('webpack-merge');
    const baseConfig = require('@ks-console/bootstrap/webpack/webpack.dev.conf');
    
    const webpackDevConfig = merge(baseConfig, {
      devServer: {
        proxy: {
          '/proxy': {
            target: 'http://172.31.73.3:30881', // 修改为目标 ks-apiserver 的地址
            onProxyReq: (proxyReq, req, res) => {
                const username = 'admin'        // 请求代理时的用户凭证
                const password = 'P@88w0rd'
                const auth = Buffer.from(`${username}:${password}`).toString("base64");
                proxyReq.setHeader('Authorization', `Basic ${auth}`);
              },
          },
        },
      },
    });
    
    module.exports = webpackDevConfig;
    

**ReverseProxy 示例与参数说明：**

    
    
     apiVersion: extensions.kubesphere.io/v1alpha1
    kind: ReverseProxy
    metadata:
      name: weave-scope
    spec:
      directives:
        headerUp:
        - -Authorization
        stripPathPrefix: /proxy/weave.works
      matcher:
        method: '*'
        path: /proxy/weave.works/*
      upstream:
        url: http://app.weave.svc
    
    #   service:
    #     namespace: example-system
    #     name: apiserver
    #     port: 443
    

字段| 描述  
---|---  
`spec.matcher`| API 的匹配规则，可以用来拦截特定的请求  
`spec.upstream`| 定义具体的服务后端，支持健康检查、TLS配置  
`spec.directives`| 向请求链注入不同的指令  
  
#### Directives

`method` 修改 HTTP 请求方法

    
    
    spec:
      directives:
        method: 'POST'
    

`stripPathPrefix` 移除请求路径中的前缀

    
    
    spec:
      directives:
        stripPathPrefix: '/path/prefix'
    

`stripPathSuffix` 移除请求路径中的后缀

    
    
    spec:
      directives:
        stripPathSuffix: '.html'
    

`headerUp` 为发送到上游的请求增加、删除或替换请求头

    
    
    spec:
      directives:
        headerUp:
        - '-Authorization'
        - 'Foo bar'
    

`headerDown` 为上游返回的响应增加、删除或替换响应头

    
    
    spec:
      directives:
        headerDown:
        - 'Content-Type "application/json"'
    

`rewrite` 重写发送到上游的请求路径以及查询参数

    
    
    spec:
      directives:
        rewrite:
        - * /foo.html
        - /api/* ?a=b
        - /api_v2/* ?{query}&a=b
        - * /index.php?{query}&p={path}
    
    # - "* /foo.html" ==> rewrite "/" to "/foo.html"
    # - "/api/* ?a=b" ==> rewrite "/api/abc" to "/api/abc?a=b"
    # - "/api_v2/* ?{query}&a=b" ==> rewrite "/api_v2/abc" to "/api_v2/abc?a=b"
    # - "* /index.php?{query}&p={path}" ==> rewrite "/foo/bar" to "/index.php?p=%2Ffoo%2Fbar"
    

`replace` 替换发送到上游的请求路径

    
    
    spec:
      directives:
        replace:
        - /docs/ /v1/docs/
    
    # - "/docs/ /v1/docs/" ==> rewrite "/docs/go" to "/v1/docs/go"
    

`pathRegexp` 正则替换发送到上游的请求路径

    
    
    spec:
      directives:
        pathRegexp:
        - /{2,} /
    
    # - "/{2,} /" ==> rewrite "/doc//readme.md" to "/doc/readme.md"
    

`authProxy` 向上游服务传递用户认证相关的请求头

    
    
    spec:
      directives:
        authProxy: true
    

上游服务会收到如下请求头

    
    
    X-Remote-Group: system:authenticated
    X-Remote-User: admin
    

## 针对 CRD 的 API 扩展

如果您已经借助 K8s CRD 定义了 API，在 KubSphere 中可以直接使用 K8s 提供的 API。此外，还可以利用 KubeSphere
增强您的 API。

### 多集群

通过 KubeSphere host 集群的 ks-apiserver 可以代理访问各 member 集群的资源，API 模式如下：
`/clusters/{cluster}/apis/{group}/{version}/{resources}`

通过 `/clusters/{cluster}` 前缀可以指定访问特定集群中的资源。

### 访问控制

KubeSphere API 支持多级访问控制，需要在 API 路径设计上严格遵循[KubeSphere API 的设计模式](/extension-
dev-guide/zh/references/kubesphere-api-
concepts/)。用户访问权限往往需要与前端联动，请参考[访问控制](/extension-dev-guide/zh/feature-
customization/access-control/)章节。

### 分页与模糊搜索

为 CRD 添加 Label `kubesphere.io/resource-served: 'true'`，KubeSphere 会为相关的 CR
资源提供分页和模糊查询 API 等功能。

> 如果使用了相同的 API Group 与 API Version，APIService 的优先级高于 KubeSphere Served
> Resource API。

**请求示例与参数说明：**

集群资源：`GET /clusters/{cluster}/kapis/{apiGroup}/{apiVersion}/{resources}`

企业空间资源：`GET
/clusters/{cluster}/kapis/{apiGroup}/{apiVersion}/workspaces/{workspace}/{resources}`

命名空间资源：`GET
/clusters/{cluster}/kapis/{apiGroup}/{apiVersion}/namespaces/{namespace}/{resources}`

查询参数| 描述| 是否必须| 默认值| 备注  
---|---|---|---|---  
page| 页码| 否| 1|  
limit| 页宽| 否| -1|  
sortBy| 排序字段，支持 name, createTime,creationTimestamp| 否| creationTimestamp|  
ascending| 升序| 否| false|  
name| 资源名，支持模糊搜索| 否| |   
names| 资源名集合，多个用英文逗号分开| 否| |   
uid| 资源 uid| 否| |   
namespace| namespace| 否| |   
ownerReference| ownerReference| 否| |   
ownerKind| ownerKind| 否| |   
annotation| 注解，支持‘=’, ‘!=’，单个annotation，键值对或单个键| 否| | annotation=ab=ok或annotation=ab  
labelSelector| 标签选择器，用法与 K8s labelSelector 一样，参考[labels#api](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#api)| 否| | labelSelector=environment in (production,qa),tier in (frontend)  
fieldSelector| 属性选择器，支持’=’, ‘==’, ‘!=’，多个用英文逗号分隔，从根开始查询所有路径属性  
支持大小写不敏感，需给值加上前缀`~`| 否| | fieldSelector=spec.ab=true,spec.bc!=ok  
大小写不敏感：fieldSelector=spec.ab=~ok,spec.bc!=~ok  
  
**响应：**

    
    
    {
        "apiVersion":"{Group}/{Version}",
        "items":[],
        "kind":"{CR}List",
        "metadata":{
            "continue":"",
            "remainingItemCount":0, 
            "resourceVersion":""
        }
    }
    

[__](/extension-dev-guide/zh/feature-customization/extending-ui/ "UI
扩展")[__](/extension-dev-guide/zh/feature-customization/menu/ "挂载位置")



---

# 打包扩展组件

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/packaging-and-release/packaging/

[__ 编辑当前页](https://github.com/kubesphere/dev-
guide/edit/master/sites/extension-dev-guide/content/zh/packaging-and-
release/packaging/_index.md "编辑当前页")

 ____[KubeSphere 扩展组件开发指南](/extension-dev-guide/zh/) > [打包发布](/extension-dev-
guide/zh/packaging-and-release/) > 打包扩展组件

# 打包扩展组件

扩展组件开发完成之后，需要遵循 Helm 规范对扩展组件进行编排。

## 初始化扩展组件包

使用 `ksbuilder create` 创建扩展组件包（Helm Chart）。

    
    
    ➜  extension-samples git:(master) cd extensions
    ➜  extensions git:(master) ksbuilder create   
    Please input extension name: hello-world
    ✔ other
    Please input extension author: hongming
    Please input Email (optional): hongming@kubesphere.io
    Please input author's URL (optional): 
    Directory: /Users/hongming/GitHub/extension-samples/extensions/hello-world
    

使用 [Helm](https://helm.sh/zh/docs/topics/charts/) 对扩展组件进行编排，扩展组件包的目录结构：

    
    
    ├── README.md
    ├── README_zh.md
    ├── charts             # 扩展组件的子 Chart，通常前后端扩展分为两个部分
    │   ├── backend        # 扩展组件支持多集群调度，多集群模式下需要添加 agent tag
    │   │   ├── Chart.yaml
    │   │   ├── templates  # 模板文件
    │   │   │   ├── NOTES.txt
    │   │   │   ├── deployment.yaml
    │   │   │   ├── extensions.yaml
    │   │   │   ├── helps.tpl
    │   │   │   └── service.yaml
    │   │   └── values.yaml
    │   └── frontend       # 前端扩展需要在 host 集群中部署，需要添加 extension tag
    │       ├── Chart.yaml
    │       ├── templates  # 模板文件
    │       │   ├── NOTES.txt
    │       │   ├── deployment.yaml
    │       │   ├── extensions.yaml
    │       │   ├── helps.tpl
    │       │   └── service.yaml
    │       └── values.yaml
    ├── extension.yaml     # extension 元数据声明文件
    ├── permissions.yaml   # 扩展组件安装时需要的资源授权
    ├── static             # 静态资源文件
    │   ├── favicon.svg
    │   └── screenshots
    │       └── screenshot.png
    └── values.yaml        # 扩展组件配置
    

### extension.yaml 的定义

`extension.yaml` 文件中包含了扩展组件的元数据信息：

    
    
    apiVersion: v1
    name: employee               # 扩展组件的名称（必填项）
    version: 0.1.0               # 扩展组件的版本，须符合语义化版本规范（必填项）
    displayName:                 # 扩展组件展示时使用的名称（必填项），Language Code 基于 ISO 639-1
      zh: 示例扩展组件
      en: Sample Extension
    description:                 # 扩展组件展示时使用的描述（必填项）
      zh: 这是一个示例扩展组件，这是它的描述
      en: This is a sample extension, and this is its description
    category: devops             # 扩展组件的分类（必填项）
    keywords:                    # 关于扩展组件特性的一些关键字（可选项）
      - others
    home: https://kubesphere.io  # 项目 home 页面的 URL（可选项）
    sources:                     # 项目源码的 URL 列表（可选项）
      - https://github.com/kubesphere # 扩展组件仓库
    docs: https://github.com/kubesphere # 扩展组件文档
    kubeVersion: ">=1.19.0"      # 扩展组件兼容的 Kubernetes 版本限制（可选项）
    ksVersion: ">=3.0.0"         # 扩展组件兼容的 KubeSphere 版本限制（可选项）
    maintainers:                 # 扩展组件维护者（可选项）
      - name: "ks"
        email: "ks@kubesphere.io"
        url: "https://www.kubesphere.io"
    provider:                    # 扩展组件提供商（必填项）
      zh:
        name: "青云科技"
        email: "ks@kubesphere.io"
        url: "https://www.qingcloud.com"
      en:
        name: "QingCloud"
        email: "ks@kubesphere.io"
        url: "https://www.qingcloud.com"
    staticFileDirectory: static  # 扩展组件静态文件存放目录，图标和 README 引用的静态文件等需存放到该目录（必填项）
    icon: ./static/favicon.svg   # 扩展组件展示时使用的图标，可以定义为本地的相对路径（必填项）
    screenshots:                 # 扩展组件截图（可选项）
      - ./static/screenshots/screenshot.png
    dependencies:                # 扩展组件依赖的 Helm Chart，语法与 Helm 的 Chart.yaml 中 dependencies 兼容（可选项）
      - name: extension
        tags:
          - extension
      - name: apiserver
        tags:
          - agent
    # 扩展组件的安装模式，它可以是 HostOnly 或 Multicluster。
    # HostOnly 模式下，扩展组件只会被安装到 host 集群。
    # Multicluster 模式下 tag 中带有 agent  的 subchart 可以选择集群进行部署。    
    installationMode: HostOnly
    # 对其它扩展组件的依赖（可选项）
    # externalDependencies:       
    #   - name: a
    #     type: extension
    #     version: ">= 2.6.0"
    #     required: true
    #   - name: b
    #     type: extension
    #     version: ">= 2.2.0"
    #     required: true
    

扩展组件包名(name)作为扩展组件的唯一标识，需要遵循以下规则：

  1. 包名只能包含小写字母、数字。
  2. 最大长度 32 个字符。
  3. 包名应该具有全球唯一性，以确保不与其他应用程序的包名发生冲突。

displayName、description 和 provider 字段支持国际化，Language Code 基于 [ISO
639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)，当浏览器、用户语言都无法匹配时，`en`
会作为的默认的语言区域。

扩展组件包是一个 Main Chart，可以在 KubeSphere
管理的集群中进行部署。通常扩展组件会被分为前端扩展和后端扩展两个部分，扩展组件支持多集群部署时，需要分别给前端扩展 Sub Chart 和后端扩展 Sub
Chart（在 extension.yaml中）添加 `extension` 和 `agent` tag。前端扩展只会被部署到 host
集群，后端扩展允许选择集群进行调度。

## 编排扩展组件

前端扩展请参考 [UI 扩展](/extension-dev-guide/zh/feature-customization/extending-
ui/)，后端扩展请参考 [API 扩展](/extension-dev-guide/zh/feature-customization/extending-
api/)

Helm Chart 编排规范及最佳实践请参考 <https://helm.sh/docs/>

扩展组件可以使用的全局参数：

参数| 说明  
---|---  
`global.clusterInfo.name`| 扩展组件安装所在的集群名称  
`global.clusterInfo.role`| 扩展组件安装所在的集群角色  
`global.imageRegistry`| 全局配置镜像仓库地址  
  
扩展组件的编排过程中需要遵循以下规则：

  1. 兼容 KubeSphere 的全局配置参数，比如全局的仓库地址，可以避免用户手动调整参数出错的概率。
  2. 子 Chart 尽可能引用本地文件而非远端 URL，避免网络问题导致扩展组件无法正确加载。

### permissions.yaml 的定义

`permissions.yaml` 定义了扩展组件安装时所需要的资源授权：

    
    
    kind: ClusterRole
    rules:  # 如果你的扩展组件需要创建、变更 Cluster 级别的资源，你需要编辑此授权规则
      - verbs:
          - 'create'
          - 'patch'
          - 'update'
        apiGroups:
          - 'extensions.kubesphere.io'
        resources:
          - '*'
    
    ---
    kind: Role
    rules:  # 如果你的扩展组件需要创建、变更 Namespace 级别的资源，你需要编辑此授权规则
      - verbs:
          - '*'
        apiGroups:
          - ''
          - 'apps'
          - 'batch'
          - 'app.k8s.io'
          - 'autoscaling'
        resources:
          - '*'
      - verbs:
          - '*'
        apiGroups:
          - 'networking.k8s.io'
        resources:
          - 'ingresses'
          - 'networkpolicies'
    

在定义扩展组件安装所需的资源授权时需要遵循以下规则：

  1. 尽可能减少不必要的权限，只读权限够用就不要申请编辑创建权限，编辑创建权限够用就不要申请删除资源的权限。
  2. 尽可能不要申请敏感权限，clusterrolebinding，rolebinding，secret，muutatingwebhookconfiguration 和 validatingwebhookconfiguration 等敏感资源的访问权限需要有明确的理由。
  3. 能通过 resourceNames 限制资源范围的权限项不要使用通配符(’*’)。

相关文档：

  1. <https://kubernetes.io/docs/reference/access-authn-authz/rbac/>
  2. <https://helm.sh/docs/topics/rbac/>

## 扩展组件打包

可以直接从 GitHub 上克隆 hello-world 这个示例扩展组件的安装包。

    
    
    git clone https://github.com/kubesphere/extension-samples.git
    

使用 `ksbuilder package` 命令可以将编排好的扩展组件进行打包为压缩文件，便于分发。

    
    
    ➜  extension-samples git:(master) ✗ cd extensions
    ➜  extensions git:(master) ✗ ksbuilder package hello-world    
    package extension hello-world
    package saved to /Users/hongming/GitHub/extension-samples/extensions/hello-world-0.1.0.tgz
    

接下来您可以参考[测试扩展组件](/extension-dev-guide/zh/packaging-and-
release/testing/)，将扩展组件提交到扩展市场中部署测试。

[ __](/extension-dev-guide/zh/packaging-and-release/ "打包发布")[__](/extension-
dev-guide/zh/packaging-and-release/testing/ "测试扩展组件")



---

# KubeSphere 扩展组件开发指南

来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/

__navigation

# KubeSphere 扩展组件开发指南

KubeSphere LuBan 实现了灵活的扩展机制，开发者可以在不修改 KubeSphere 核心代码的前提下，通过扩展组件功能无缝地拓展
KubeSphere 的功能。您可以通过以下章节的内容，学习如何从零开始开发 KubeSphere 扩展组件或无缝集成您的云原生应用。

  * [概述](/extension-dev-guide/zh/overview/)

介绍 KubeSphere 4.0 扩展机制的背景和优势

    * [扩展组件概述](/extension-dev-guide/zh/overview/overview/)

介绍 KubeSphere LuBan 的扩展机制及系统架构

    * [前端扩展机制](/extension-dev-guide/zh/overview/frontend-extension-architecture/)

如何对 KubeSphere 的前端 UI 进行扩展？

    * [后端扩展机制](/extension-dev-guide/zh/overview/backend-extension-architecture/)

如何对 KubeSphere 的后端 API 进行扩展？

    * [扩展组件开发流程](/extension-dev-guide/zh/overview/development-process/)

介绍 KubeSphere 扩展组件的开发流程

  * [快速入门](/extension-dev-guide/zh/quickstart/)

创建并运行您的第一个 KubeSphere 扩展组件

    * [搭建开发环境](/extension-dev-guide/zh/quickstart/prepare-development-environment/)

介绍如何搭建扩展组件的开发环境

    * [创建 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension/)

演示如何创建示例扩展组件 Hello World，帮助您快速了解扩展组件开发流程

    * [解析 Hello World 扩展组件](/extension-dev-guide/zh/quickstart/hello-world-extension-anatomy/)

解读 Hello World 扩展组件的工作方式

  * [扩展能力](/extension-dev-guide/zh/feature-customization/)

KubeSphere 提供了非常多的定制方法，供扩展组件扩展 KubeSphere 本身的能力

    * [UI 扩展](/extension-dev-guide/zh/feature-customization/extending-ui/)

介绍如何扩展 UI

    * [API 扩展](/extension-dev-guide/zh/feature-customization/extending-api/)

介绍如何扩展 API

    * [挂载位置](/extension-dev-guide/zh/feature-customization/menu/)

介绍如何设置扩展组件在 KubeSphere Web 控制台的挂载位置

    * [访问控制](/extension-dev-guide/zh/feature-customization/access-control/)

介绍如何控制扩展组件定制资源的访问权限

    * [国际化](/extension-dev-guide/zh/feature-customization/internationalization/)

介绍如何实现扩展组件前端国际化

    * [页面路由](/extension-dev-guide/zh/feature-customization/route/)

创建新的功能页面并设置路由

    * [为扩展组件分配 Ingress](/extension-dev-guide/zh/feature-customization/ingress/)

介绍如何为扩展组件分配独立的 Ingress 访问入口

    * [自定义扩展组件的 license](/extension-dev-guide/zh/feature-customization/license/)

介绍如何自定义扩展组件的 license

  * [开发示例](/extension-dev-guide/zh/examples/)

本章节包含了一些更典型、更高阶的扩展组件开发示例教程

    * [Gatekeeper](/extension-dev-guide/zh/examples/gatekeeper-extension/)

集成 Gatekeeper

    * [Weave Scope](/extension-dev-guide/zh/examples/third-party-component-integration-example/)

快速集成已有 Web UI 的第三方工具与系统

    * [外部链接](/extension-dev-guide/zh/examples/external-link-example/)

如何在扩展组件中打开外部链接

  * [打包发布](/extension-dev-guide/zh/packaging-and-release/)

介绍如何打包和发布扩展组件

    * [打包扩展组件](/extension-dev-guide/zh/packaging-and-release/packaging/)

如何打包 KubeSphere 扩展组件

    * [测试扩展组件](/extension-dev-guide/zh/packaging-and-release/testing/)

将扩展组件上架到 KubeSphere 扩展市场中进行测试

    * [发布扩展组件](/extension-dev-guide/zh/packaging-and-release/release/)

将扩展组件发布到 KubeSphere Marketplace

  * [视频演示](/extension-dev-guide/zh/videos/)

相关视频资料

    * [开发 KubeSphere 扩展组件](/extension-dev-guide/zh/videos/develop-an-extension/)

介绍如何开发 KubeSphere 扩展组件

    * [OpenKruiseGame Dashboard 示例](/extension-dev-guide/zh/videos/openkruisegame-dashboard/)

介绍 OpenKruiseGame Dashboard 示例

    * [Databend Playground 示例](/extension-dev-guide/zh/videos/databend-playground/)

介绍 Databend Playground 示例

    * [Flomesh Service Mesh (FSM) 示例](/extension-dev-guide/zh/videos/flomesh-service-mesh/)

介绍 Flomesh Service Mesh 示例

  * [经验分享](/extension-dev-guide/zh/best-practice/)

开发经验和建议、最佳实践

    * [扩展组件开发案例](/extension-dev-guide/zh/best-practice/develop-example/)

介绍一个扩展组件开发案列，包括完整的开发打包和发布流程

    * [Databend Playground 开发小记](/extension-dev-guide/zh/best-practice/databend-playground/)

介绍 Databend Playground 的开发经验和总结

  * [FAQ](/extension-dev-guide/zh/faq/)

常见问题

    * [扩展组件 vs 应用](/extension-dev-guide/zh/faq/01-difference/)

介绍扩展组件和应用的不同点

  * [迁移指南](/extension-dev-guide/zh/migration/)

如何升级到最新版 KubeSphere

    * [从 4.0 升级到 4.1.x](/extension-dev-guide/zh/migration/4.0.0-to-4.1.x/)

如何从 4.0.0 升级到 4.1.x 版本

  * [参考资料](/extension-dev-guide/zh/references/)

CLI 工具、API 参考资料

    * [ksbuilder CLI 参考](/extension-dev-guide/zh/references/ksbuilder/)

ksbuilder 扩展组件打包、发布工具

    * [KubeDesign](/extension-dev-guide/zh/references/kubedesign/)

KubeDesign 前端 UI 组件库

    * [create-ks-project CLI reference](/extension-dev-guide/zh/references/create-ks-project/)

介绍 KubeSphere 前端开发脚手架工具

    * [KubeSphere API reference](/extension-dev-guide/zh/references/kubesphere-api/)

KubeSphere API

    * [KubeSphere API 概念](/extension-dev-guide/zh/references/kubesphere-api-concepts/)

KubeSphere API 概念

[ __](/extension-dev-guide/zh/overview/ "概述")



---

