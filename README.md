
---

# SMART on FHIR 集成

这个项目展示了如何使用  SMART on FHIR 标准来构建一个简单的健康数据应用程序，使用python。
使用了FHIRCLient 4.1.0， 接入API对应地为R4版本
2024.1 可使用测试服务器   
Oauth服务器：https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d  
需要在https://code-console.cerner.com注册 用以获取授权的客户端id

## 安装

```
virtualenv -p python3 env
. env/bin/activate
pip install -r requirements.txt
python demo.py
```

## OAuth 验证流程概述
OAuth 2.0 流程设计用来授权第三方应用程序访问用户在资源服务器上的受保护资源，而无需暴露用户的凭据。  
OAuth 验证包括以下六个步骤，如下图摘自RFC 6749：

![Oauth](Oauth.png)

1. **(A) 授权请求 (Authorization Request)**:
   - 客户端（Client）向资源拥有者（Resource Owner）请求授权。这通常通过将用户重定向到授权服务器，并在此过程中提供客户端的身份信息以及请求的权限范围。

2. **(B) 授权发放 (Authorization Grant)**:
   - 如果资源拥有者同意，授权服务器将发放授权凭证给客户端。授权凭证是一个代表资源拥有者授权的凭据，它的形式可能是授权码、一个代表用户身份的令牌等。

3. **(C) 令牌请求 (Authorization Grant)**:
   - 客户端收到授权凭证后，将它发送给授权服务器以获取访问令牌。此步骤通常是对授权服务器的后端请求，其中包含授权凭证和客户端的身份验证信息。

4. **(D) 令牌发放 (Access Token)**:
   - 授权服务器验证客户端和授权凭证后，发放访问令牌给客户端，代表了客户端获取资源的权限。

5. **(E) 资源请求 (Access Token)**:
   - 客户端使用访问令牌向资源服务器请求受保护的资源。这通常是通过在HTTP请求的Authorization头中发送令牌来完成。

6. **(F) 资源发放 (Protected Resource)**:
   - 资源服务器验证访问令牌的有效性，如果验证通过，则向客户端提供请求的受保护资源。


## SMART on FHIR 设置

smart 对象是 fhirclient 库的一个实例，代表了一个 SMART on FHIR 客户端用于处理与 FHIR 服务器的所有交互，包括授权和资源请求。

SMART对象包含以下信息：

- **`app_id`**: 应用程序客户端的唯一标识符。
- **`api_base`**: FHIR服务器的URL。
- **`redirect_uri`**: 授权服务器将发送响应的客户端URL。
- **`scope`**: 应用程序请求访问的权限范围，定义了它可以访问哪些资源和操作。
- **`state`**: 一个防止跨站点请求伪造攻击的值，必须在授权请求中包含，并在回调时验证。
- **`session`**： SMART对象将存储访问令牌在每一个用户唯一的**`session`**对象中。

```python
smart_defaults = {
    'app_id': 'd8ec5b28-c1fd-4a97-9210-bb3576f737e8',
    'api_base': 'https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d',
    'redirect_uri': 'http://localhost:8000/fhir-app/',
    'scope': 'launch/patient patient/Patient.read',
}
```
以上信息用以初始化smart对象

## 主页路由处理函数

这个函数是 Flask 应用的主页路由处理函数，参与Oauth认证流程的A B E F四个过程。  
它首先尝试获取一个 `smart` 客户端对象。如果用户尚未授权，则页面会提供一个授权链接重定向到授权服务器，完成Oauth认证流程的A步骤。授权服务器完成授权后会将用户重定向回'/fhir-app/'下，完成步骤B。如果用户已通过授权，则将通过smart请求patient的信息，如果资源获取成功，则将信息输出，完成步骤EF。

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

- `smart.handle_callback(request.url)`：调用 `handle_callback` 方法处理从授权服务器重定向回来的请求。该方法负责处理 OAuth2 认证流程中的回调逻辑，它会从url中提取授权吗，并用说授权码和客户端信息向认证服务器申请令牌，这一步对用户不可见,完成OAUTH验证流程的C/D步骤。


- `return redirect('/')`：如果回调处理成功（无异常抛出），则重定向用户回到应用的主页。

这个函数是 OAuth2 认证流程的关键部分，确保了在用户完成授权后，应用能够正确处理并响应回调请求。


## 参考
R4 FHIR: https://fhir-ru.github.io/summary.html
python on FHIR: https://github.com/smart-on-fhir/client-py
Oauth2.0: https://www.ruanyifeng.com/blog/2014/05/oauth_2_0.html


