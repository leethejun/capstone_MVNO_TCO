"""모빙 공개 사이트의 DNS TLS HTTP 단계를 인증서 검증을 유지해 진단한다."""
from datetime import datetime
import json
from pathlib import Path
import socket
import ssl
from zoneinfo import ZoneInfo

import requests


def audit():
    host = 'www.mobing.co.kr'
    result = {'checked_at': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
              'url': f'https://{host}/product/plan', 'probes': []}
    result['local_dns'] = sorted({row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    for resolver in ('https://dns.google/resolve', 'https://cloudflare-dns.com/dns-query'):
        try:
            response = requests.get(resolver, params={'name': host, 'type': 'A'},
                                    headers={'Accept': 'application/dns-json'}, timeout=15)
            response.raise_for_status()
            result.setdefault('public_dns', {})[resolver] = response.json().get('Answer', [])
        except requests.RequestException as exc:
            result.setdefault('public_dns_errors', {})[resolver] = str(exc)
    context = ssl.create_default_context()
    context.set_alpn_protocols(['http/1.1'])
    for path in ('/product/plan', '/favicon.ico'):
        probe = {'path': path, 'certificate_verification': 'required', 'hostname_verification': True}
        try:
            with socket.create_connection((host, 443), timeout=15) as connection:
                with context.wrap_socket(connection, server_hostname=host) as tls:
                    cert = tls.getpeercert()
                    probe.update(tls_version=tls.version(), cipher=tls.cipher()[0],
                                 alpn=tls.selected_alpn_protocol(), tls_verified=True,
                                 certificate_subject=cert.get('subject'),
                                 certificate_expires=cert.get('notAfter'))
                    tls.sendall((f'GET {path} HTTP/1.1\r\nHost: {host}\r\n'
                                 'User-Agent: Mozilla/5.0\r\nAccept: text/html,*/*\r\n'
                                 'Connection: close\r\n\r\n').encode())
                    data = tls.recv(4096)
                    probe['http_response_bytes'] = len(data)
                    probe['http_status_line'] = data.split(b'\r\n', 1)[0].decode('ascii', errors='replace')
                    probe['http_response_received'] = data.startswith(b'HTTP/')
        except (OSError, ssl.SSLError) as exc:
            probe['error'] = str(exc)
        result['probes'].append(probe)
    return result


if __name__ == '__main__':
    result = audit()
    output = Path('runtime') / ('mobing-connection-' + datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d-%H%M%S') + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(result, audit_path=str(output)), ensure_ascii=False, indent=2))
