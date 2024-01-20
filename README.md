
---

# SMART on FHIR 集成

这个项目展示了如何使用  SMART on FHIR 标准来构建一个简单的健康数据应用程序，使用python。
使用了FHIRCLient 4.0， 接入API应该对应地为R4版本
2024.1 可供使用测试服务器   
Oauth服务器：https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d
需要在https://code-console.cerner.com注册app 用以授权的客户端id

## 安装

```
virtualenv -p python3 env
. env/bin/activate
pip install -r requirements_flask_app.txt
python flask_app.py
```

## 初始化

引入必要的模块：

```python
from fhirclient import client
from fhirclient.models.medication import Medication
from fhirclient.models.medicationrequest import MedicationRequest
from flask import Flask, request, redirect, session
```

- `fhirclient` 是一个用于与 FHIR 服务器进行交互的 SMART on FHIR 客户端库。
- `flask` 是一个python的app架构。

## OAuth 验证流程概述
OAuth 验证有以下几个步骤：

请求授权: 应用程序请求用户的授权，通过将用户重定向到服务提供商的授权页面来完成。  
用户授权: 用户在服务提供商的页面上授权第三方应用访问其信息。   
重定向回客户端服务器：完成验证后，将用户从认证服务器重定向回客户端服务器或应用程序。smart提供自带的init函数会重定向回根目录（程序起始点），本程序将业务内容放在了“/fhir-app/”下区分处理  
获取访问令牌: 一旦用户授权，服务提供商会向应用程序提供一个访问令牌。此令牌将用于访问用户的数据。  
访问用户数据: 应用程序使用访问令牌来安全地访问服务提供商上的用户数据。  
在 FHIR框架中，服务提供商确实通常同时提供数据服务和验证服务。
![Oauth](Oauth.png)

## SMART on FHIR 设置

```python
smart_defaults = {
    'app_id': 'd8ec5b28-c1fd-4a97-9210-bb3576f737e8',
    'api_base': 'https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d',
    'redirect_uri': 'http://localhost:8000/fhir-app/',
    'scope': 'launch/patient patient/Patient.read patient/MedicationRequest.read patient/Medication.read',
}
```

这里包括了客户端 ID、重定向 URI、API地址和所请求的权限范围。
- `scope` 请按照https://build.fhir.org/ig/HL7/smart-app-launch/scopes-and-launch-context.html。

## 主页路由处理函数

用于处理客户端通过验证后的请求：

```python
@app.route('/')
@app.route('/index.html')
def index():
    """ The app's main page.
    """
    import fhirclient.models.patient as p
    smart = _get_smart()
    body = "<h1>Hello</h1>"
    
    # 检查是否已授权且有患者信息
    if smart.ready and smart.patient is not None:  # "ready" 可能为真，但访问令牌可能已过期，导致 smart.patient 为空
        # 获取患者名称，如果没有则显示 "Unknown"
        name = smart.human_name(smart.patient.name[0] if smart.patient.name and len(smart.patient.name) > 0 else 'Unknown')
        # 生成简单的正文文本
        body += "<p>You are authorized and ready to make API requests for <em>{0}</em>.</p>".format(name)
        # 打印患者信息的 JSON 表示
        print(smart.patient.as_json())
        # 添加一个链接以更换患者
        body += """<p><a href="/logout">Change patient</a></p>"""
    else:
        # 获取授权 URL
        auth_url = smart.authorize_url
        if auth_url is not None:
            # 如果有授权 URL，则提供一个链接供用户授权
            body += """<p>Please <a href="{0}">authorize</a>.</p>""".format(auth_url)
        else:
            # 如果在无需授权的服务器上运行，说明没有展示内容
            body += """<p>Running against a no-auth server, nothing to demo here. """
        # 提供重置链接
        body += """<p><a href="/reset" style="font-size:small;">Reset</a></p>"""
    return body
```

这个函数是 Flask 应用的主页路由处理函数。它首先尝试获取一个 `smart` 客户端对象。如果用户已通过授权并且有关联的患者信息，页面会显示欢迎消息和患者的名字。如果用户尚未授权或者无法获取患者信息（例如，访问令牌可能已过期），则页面会提供一个授权链接或显示一条消息，表明当前运行在无需授权的服务器上。此外，还提供了更换患者和重置应用状态的链接。


## OAuth2 回调处理函数

用于处理 OAuth2 认证过程中的回调：

```python
@app.route('/fhir-app/')
def callback():
    """ OAuth2 callback interception.
    """
    smart = _get_smart()
    try:
        # 处理 OAuth2 回调
        smart.handle_callback(request.url)
    except Exception as e:
        # 如果在处理过程中发生异常，显示授权错误信息并提供重新开始的链接
        return """<h1>Authorization Error</h1><p>{0}</p><p><a href="/">Start over</a></p>""".format(e)
    # 如果一切顺利，重定向到主页
    return redirect('/')
```

此函数定义了一个路由 `/fhir-app/`，它作为 OAuth2 认证流程中的回调接口。在用户完成授权服务器的认证流程后，将被重定向到这个路由。

- `smart = _get_smart()`：这一行获取或初始化一个 `FHIRClient` 实例，用于处理 FHIR 相关操作。

- `smart.handle_callback(request.url)`：调用 `handle_callback` 方法处理从授权服务器重定向回来的请求。该方法负责处理 OAuth2 认证流程中的回调逻辑，例如提取授权码、交换访问令牌等。

- `except Exception as e`：如果在处理回调过程中发生任何异常（如授权错误），则捕获这个异常，并向用户显示一个错误消息。这里的 `{0}` 会被异常信息（`e`）替换。

- `return redirect('/')`：如果回调处理成功（无异常抛出），则重定向用户回到应用的主页。

这个函数是 OAuth2 认证流程的关键部分，确保了在用户完成授权后，应用能够正确处理并响应回调请求。

## 验证流程
请求授权: 在index函数中处理了这个步骤，当用户访问应用的主页面时，程序会生成一个授权URL并提示用户点击以进行授权。这通过smart.authorize_url实现。
用户授权: 这一步是在服务提供商的页面上进行的。用户在这里登录并授权您的应用程序访问他们的数据。
重定向回客户端服务器: 一旦用户授权，服务提供商会将用户重定向回“/fhir-app/”。
获取访问令牌: 通过smart.handle_callback(request.url)来处理回调并获取访问令牌。
访问用户数据: 一旦获得访问令牌，您的应用可以使用它来访问用户的FHIR数据。在index函数中，如果用户已经授权，应用将尝试获取并显示患者数据。

## 访问开放型 FHIR 服务器的流程

用于从开放型 FHIR 服务器获取数据的函数：

```python
def openserver():
    from fhirclient import client
    import fhirclient.models.patient as p

    # 设置 FHIR 服务器
    settings = {
        'app_id': 'my_web_app',
        'api_base': 'https://hapi.fhir.org/baseR4'
    }
    smart = client.FHIRClient(settings=settings)
    
    # 获取患者信息
    patient = p.Patient.read('example', smart.server)
    print(patient.as_json())
```

- `smart = client.FHIRClient(settings=settings)`: 使用前面定义的 `settings` 创建一个 `FHIRClient` 实例。

- `patient = p.Patient.read('example', smart.server)`: 这行代码获取服务器上特定 ID的患者信息。

