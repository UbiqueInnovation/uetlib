#!/usr/bin/env python3
"""Assemble immutable Artifactory bundles, then submit one Central deployment."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

GROUP = 'ch/uetlib/central-bundles'
CENTRAL = 'https://repo.maven.apache.org/maven2'
API = 'https://central.sonatype.com/api/v1/publisher'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def credentials(user, password, scheme='Basic'):
    value = base64.b64encode((os.environ[user] + ':' + os.environ[password]).encode()).decode()
    return {'Authorization': scheme + ' ' + value}


def fetch(url, headers=None, missing=False):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if missing and error.code == 404:
            return None
        raise RuntimeError(f'HTTP {error.code} fetching {url}') from error


def read_bundle(data, manifest, repo, version):
    if manifest['repository'] != 'UbiqueInnovation/' + repo or manifest['version'] != version:
        raise ValueError('Bundle identity does not match selection: ' + repo)
    if not re.fullmatch('[0-9a-f]{40}', manifest['commit']):
        raise ValueError('Invalid source commit: ' + repo)
    if digest(data) != manifest['sha256']:
        raise ValueError('Bundle checksum mismatch: ' + repo)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(names) != len(set(names)) or set(names) != set(manifest['files']):
            raise ValueError('Duplicate or unexpected bundle files: ' + repo)
        files = {}
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or not name.startswith('ch/uetlib/'):
                raise ValueError('Invalid artifact path: ' + name)
            content = archive.read(name)
            if digest(content) != manifest['files'][name]:
                raise ValueError('Artifact checksum mismatch: ' + name)
            files[name] = content
    poms = [name for name in files if name.endswith('.pom')]
    if not poms or any(PurePosixPath(name).parent.name != version for name in poms):
        raise ValueError('Invalid POM versions in bundle: ' + repo)
    for name in files:
        if name.endswith(('.pom', '.jar')) and name + '.asc' not in files:
            raise ValueError('Missing signature: ' + name)
    return files


def assemble(selection, output, base, headers):
    selected = json.loads(Path(selection).read_text())['repositories']
    combined = {}
    report = {'included': [], 'alreadyPublished': []}
    for repo, version in selected.items():
        if not re.fullmatch(r'uetlib-[a-z0-9-]+', repo) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-\d{4}\.\d+\.\d+)?', version):
            raise ValueError('Only exact stable versions can be promoted: ' + repo)
        prefix = f'{base.rstrip("/")}/{GROUP}/{repo}/{version}/{repo}-{version}'
        manifest = json.loads(fetch(prefix + '-manifest.json', headers))
        files = read_bundle(fetch(prefix + '.zip', headers), manifest, repo, version)
        # Check every original file: complete identical releases can be skipped safely.
        existing = {name: fetch(CENTRAL + '/' + name, missing=True) for name in files}
        present = [name for name, data in existing.items() if data is not None]
        if present:
            if len(present) != len(files) or any(existing[name] != files[name] for name in present):
                raise ValueError('Partially published or different Central contents: ' + repo + ':' + version)
            report['alreadyPublished'].append({'repository': repo, 'version': version})
            continue
        for name, data in files.items():
            if name in combined:
                raise ValueError('Conflicting bundle paths: ' + name)
            combined[name] = data
        report['included'].append({'repository': repo, 'version': version, 'commit': manifest['commit'], 'sha256': manifest['sha256']})
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output / 'central-bundle.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(combined.items()):
            archive.writestr(name, data)
    report['sha256'] = digest((output / 'central-bundle.zip').read_bytes())
    report['selectionSha256'] = digest(Path(selection).read_bytes())
    (output / 'batch.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return bool(combined)


def publish(directory, name):
    directory = Path(directory)
    report = json.loads((directory / 'batch.json').read_text())
    if not report['included']:
        print('All selected versions are already on Central; nothing to publish.')
        return
    data = (directory / 'central-bundle.zip').read_bytes()
    if digest(data) != report['sha256']:
        raise ValueError('Assembled bundle changed after review')
    auth = credentials('MAVEN_CENTRAL_USERNAME', 'MAVEN_CENTRAL_PASSWORD', 'Bearer')
    boundary = 'uetlib-' + report['sha256']
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="bundle"; filename="central-bundle.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode() + data + f'\r\n--{boundary}--\r\n'.encode())
    query = urllib.parse.urlencode({'name': name, 'publishingType': 'AUTOMATIC'})
    request = urllib.request.Request(API + '/upload?' + query, data=body, headers={**auth, 'Content-Type': 'multipart/form-data; boundary=' + boundary}, method='POST')
    # Never retry the upload automatically: a lost response may already represent a deployment.
    with urllib.request.urlopen(request, timeout=300) as response:
        deployment = response.read().decode().strip()
    report['deploymentId'] = deployment
    (directory / 'batch.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Central deployment:', deployment, flush=True)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as file:
            file.write(f'Central deployment: `{deployment}`\n')
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        request = urllib.request.Request(API + '/status?' + urllib.parse.urlencode({'id': deployment}), data=b'', headers=auth, method='POST')
        with urllib.request.urlopen(request, timeout=120) as response:
            status = json.load(response)
        state = status['deploymentState']
        if state == 'FAILED':
            raise RuntimeError(json.dumps(status))
        if state in ('VALIDATED', 'PUBLISHING', 'PUBLISHED'):
            print('Validation succeeded; state:', state)
            return
        time.sleep(10)
    raise TimeoutError('Validation timed out; inspect deployment ' + deployment + ' before retrying')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('assemble')
    build.add_argument('--selection', default='central-release.json')
    build.add_argument('--output', default='central-batch')
    upload = commands.add_parser('publish')
    upload.add_argument('--directory', default='central-batch')
    upload.add_argument('--name', required=True)
    args = parser.parse_args()
    if args.command == 'assemble':
        base = os.environ['UB_ARTIFACTORY_URL'] + os.environ['UB_ARTIFACTORY_REPO_UBIQUE']
        assemble(args.selection, args.output, base, credentials('UB_ARTIFACTORY_USER', 'UB_ARTIFACTORY_PASSWORD'))
    else:
        publish(args.directory, args.name)


if __name__ == '__main__':
    main()
