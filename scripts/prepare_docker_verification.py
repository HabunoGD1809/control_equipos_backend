"""Generate private credentials for a new isolated Compose project; never read .env."""
import json
from pathlib import Path
import secrets
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.seed_demo import private_json


def main():
    project = 'control-equipos-test-' + uuid4().hex[:12]
    directory = ROOT / 'verification' / project
    directory.mkdir(parents=True, exist_ok=False)
    values = {
        'ENV_FILE': './verification/' + project + '/stack.env',
        'POSTGRES_DB': 'control_equipos_docker_test', 'POSTGRES_SERVER': 'db', 'POSTGRES_PORT': '5432',
        'POSTGRES_USER': 'control_test', 'POSTGRES_PASSWORD': secrets.token_hex(24),
        'SECRET_KEY': secrets.token_hex(48), 'REFRESH_TOKEN_SECRET_KEY': secrets.token_hex(48),
        'SUPERUSER_USERNAME': 'admin', 'SUPERUSER_EMAIL': 'docker.admin@example.com',
        'SUPERUSER_PASSWORD': 'Qa!1' + secrets.token_hex(24),
        'REDIS_PASSWORD': secrets.token_hex(24), 'REPORT_EXECUTION_MODE': 'celery',
        'SMTP_HOST': 'mailpit', 'SMTP_PORT': '1025', 'SMTP_STARTTLS': 'false', 'SMTP_FROM': 'control@example.com',
        'AWS_ACCESS_KEY_ID': 'test' + secrets.token_hex(10), 'AWS_SECRET_ACCESS_KEY': secrets.token_hex(24),
        'AWS_BUCKET_NAME': 'control-test', 'AWS_ENDPOINT_URL': 'http://minio:9000', 'AWS_REGION': 'us-east-1',
        'DATABASE_PUBLIC_PORT': '15433', 'BACKEND_PUBLIC_PORT': '18086', 'FRONTEND_PUBLIC_PORT': '13000',
        'MAILPIT_PUBLIC_PORT': '18025', 'MINIO_PUBLIC_PORT': '19000',
        'FRONTEND_BUILD_CONTEXT': str(ROOT.parent.parent / 'control-equipos-frontend').replace('\\', '/'),
    }
    # Apply an ACL before writing any credentials. All generated values avoid shell metacharacters.
    env_path = directory / 'stack.env'
    private_json(env_path, {})
    env_path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()), encoding='utf-8')
    manifest = {'project': project, 'directory': str(directory), 'env_file': str(env_path), 'database': values['POSTGRES_DB']}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
