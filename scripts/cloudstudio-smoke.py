"""隔离数据目录中的部署连通性验收；不在已有用户的站点执行。"""
import argparse
from http.cookiejar import CookieJar
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor


def run(base, origin):
    checks = []
    owner = build_opener(HTTPCookieProcessor(CookieJar()))
    guest = build_opener()

    def call(path, method='GET', data=None, origin_header=None, opener=owner, raw=None, content_type=None):
        headers = {}
        if origin_header:
            headers['Origin'] = origin_header
        if data is not None:
            raw = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        if content_type:
            headers['Content-Type'] = content_type
        request = Request(base + path, data=raw, headers=headers, method=method)
        try:
            response = opener.open(request, timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            return response.code, response.headers, body

    deadline = time.monotonic() + 120
    while True:
        try:
            if call('/api/health')[0] == 200:
                break
        except (URLError, TimeoutError, ConnectionError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('服务在 120 秒内未就绪')
        time.sleep(1)
    checks.append('health_ready')
    assert call('/')[0] == 200
    for path in ['/app.js', '/campus.js', '/experience.js', '/style.css', '/vendor/vue.global.prod.js']:
        assert call(path)[0] == 200, path
    checks.append('frontend_and_api_same_port')
    assert json.loads(call('/api/products')[2])['total'] == 0, '仅在空的隔离数据库执行'
    checks.append('no_automatic_demo_seed')
    credentials = {'username': 'cloud_smoke', 'password': 'DeploySmoke2026!', 'nickname': '部署验收同学'}
    status, headers, _ = call('/api/auth/register', 'POST', credentials, origin)
    assert status == 201 and 'HttpOnly' in headers.get('Set-Cookie', '')
    checks.append('trusted_https_origin_register_cookie')
    assert call('/api/me')[0] == 200
    checks.append('session_cookie_round_trip')
    assert call('/api/auth/logout', 'POST', origin_header='https://untrusted.example.test')[0] == 403
    checks.append('foreign_origin_rejected')
    image = (Path(__file__).resolve().parents[1] / 'evidence/upload-fixture.png').read_bytes()
    boundary = 'XishiCloudSmokeBoundary'
    multipart = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="proof.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
                 + image + f'\r\n--{boundary}--\r\n'.encode())
    status, _, body = call('/api/verification-images', 'POST', origin_header=origin, raw=multipart,
                          content_type='multipart/form-data; boundary=' + boundary)
    assert status == 201
    image_url = json.loads(body)['url']
    assert call(image_url)[0] == 200 and call(image_url)[1]['Cache-Control'] == 'no-store'
    assert call(image_url, opener=guest)[0] == 401
    checks.append('private_proof_upload_and_access_control')
    status, _, _ = call('/api/me/verification', 'POST',
                        {'real_name':'测试学生', 'student_no':'CLOUD2026', 'college':'测试学院', 'image_urls':[image_url]}, origin)
    assert status == 200
    checks.append('verification_submission_through_proxy')
    assert call('/api/admin/overview')[0] == 403
    checks.append('no_automatic_admin_privileges')
    assert call('/api/auth/logout', 'POST', origin_header=origin)[0] == 200
    assert call('/api/me')[0] == 401
    checks.append('logout')
    return {'status': 'PASS', 'checks': checks, 'check_count': len(checks), 'scope': 'same-port cloud startup and proxy-origin simulation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8011')
    parser.add_argument('--origin', default='https://preview.example.test')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = run(args.base_url.rstrip('/'), args.origin.rstrip('/'))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
