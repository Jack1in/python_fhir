from flask import Flask, session, request, redirect
from fhirclient import client

# Flask 应用配置
app = Flask(__name__)

# SMART on FHIR 客户端的默认配置
smart_defaults = {
    'app_id': 'd8ec5b28-c1fd-4a97-9210-bb3576f737e8',
    'api_base': 'https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d',
    'redirect_uri': 'http://localhost:8000/fhir-app/',
    'scope': 'launch/patient patient/Patient.read',
}

def _save_state(state):
    session['state'] = state

def _get_smart():
    if 'state' in session:
        print("Have state")
        return client.FHIRClient(state=session['state'], save_func=_save_state)
    else:
        print("Not Have state")
        return client.FHIRClient(settings=smart_defaults, save_func=_save_state)

@app.route('/')
@app.route('/index.html')
def index():
    smart = _get_smart()
    body = "<h1>Hello</h1>"
    if smart.ready and smart.patient is not None:
        name = smart.human_name(smart.patient.name[0] if smart.patient.name and len(smart.patient.name) > 0 else 'Unknown')
        body += "<p>You are authorized and ready to make API requests for <em>{0}</em>.</p>".format(name)
        print(smart.patient.as_json())
        body += """<p><a href="/logout">Change patient</a></p>"""
    else:
        auth_url = smart.authorize_url
        if auth_url is not None:
            body += """<p>Please <a href="{0}">authorize</a>.</p>""".format(auth_url)
        else:
            body += "<p>Running against a no-auth server, nothing to demo here. "
        body += """<p><a href="/reset" style="font-size:small;">Reset</a></p>"""
    return body

@app.route('/fhir-app/')
def callback():
    smart = _get_smart()
    try:
        smart.handle_callback(request.url)
    except Exception as e:
        return "<h1>Authorization Error</h1><p>{0}</p><p><a href='/'>Start over</a></p>".format(e)
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('state', None)
    return redirect('/')

@app.route('/reset')
def reset():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, port=8000)
