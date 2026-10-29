import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


def step_code(name):
    steps = workflow('mvn-publish.yml')['jobs']['publish']['steps']
    return next(step['run'] for step in steps if step['name'] == name)


BUNDLE = {'__name__': 'test_bundle'}
exec(compile(step_code('Validate, sign and bundle'), 'bundle-step', 'exec'), BUNDLE)


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.staging = self.root / 'staging'
        self.staging.mkdir()

    def artifact(self, name='uetlib-example', group='ch.ubique.uetlib', version='1.0.0', packaging='jar', attachments=True, recipes=False):
        directory = self.staging / Path(*group.split('.')) / name / version
        directory.mkdir(parents=True)
        prefix = name + '-' + version
        pom = directory / (prefix + '.pom')
        pom.write_text(f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>{group}</groupId><artifactId>{name}</artifactId><version>{version}</version><packaging>{packaging}</packaging></project>')
        if packaging == 'jar':
            for suffix in ('.jar', '-sources.jar', '-javadoc.jar') if attachments else ('.jar',):
                with zipfile.ZipFile(directory / (prefix + suffix), 'w') as jar:
                    jar.writestr('META-INF/rewrite/example.yml' if recipes else 'Example.class', 'recipe' if recipes else 'bytecode')
        return directory

    def test_bundle_contains_signatures_and_correct_checksums_but_no_metadata(self):
        directory = self.artifact()
        (directory / 'maven-metadata.xml').write_text('not a release artifact')
        (directory / 'uetlib-example-1.0.0.jar.sha1').write_text('stale')
        target = self.root / 'bundle.zip'
        count = BUNDLE['build_bundle'](self.staging, '1.0.0', target, lambda file: b'signature')
        self.assertEqual(count, 4)
        with zipfile.ZipFile(target) as bundle:
            self.assertFalse(any('metadata' in name for name in bundle.namelist()))
            for file in BUNDLE['collect_artifacts'](self.staging, '1.0.0'):
                name = file.relative_to(self.staging).as_posix()
                self.assertEqual(bundle.read(name + '.asc'), b'signature')
                for algorithm in ('md5', 'sha1', 'sha256', 'sha512'):
                    self.assertEqual(bundle.read(name + '.' + algorithm).decode(), hashlib.new(algorithm, file.read_bytes()).hexdigest())

    def test_parent_poms_publish_without_source_or_javadoc_jars(self):
        self.artifact(packaging='pom')
        self.assertEqual(len(BUNDLE['collect_artifacts'](self.staging, '1.0.0')), 1)

    def test_coverage_and_testapp_artifacts_are_excluded(self):
        self.artifact(packaging='pom')
        self.artifact(name='uetlib-example-coverage', attachments=False)
        self.artifact(name='uetlib-testapp', attachments=False)
        self.assertEqual(len(BUNDLE['collect_artifacts'](self.staging, '1.0.0')), 1)

    def test_private_coordinates_fail_before_signing(self):
        self.artifact()
        self.artifact(name='private-app', group='ch.ubique.private')
        signed = []
        with self.assertRaises(ValueError):
            BUNDLE['build_bundle'](self.staging, '1.0.0', self.root / 'bundle.zip', lambda path: signed.append(path))
        self.assertEqual(signed, [])

    def test_missing_java_documentation_fails(self):
        self.artifact(attachments=False)
        with self.assertRaisesRegex(ValueError, 'required artifact'):
            BUNDLE['collect_artifacts'](self.staging, '1.0.0')

    def test_resource_only_recipes_get_sources_and_documentation_jars(self):
        directory = self.artifact(attachments=False, recipes=True)
        self.assertEqual(len(BUNDLE['collect_artifacts'](self.staging, '1.0.0')), 4)
        with zipfile.ZipFile(directory / 'uetlib-example-1.0.0-sources.jar') as jar:
            self.assertEqual(jar.read('META-INF/rewrite/example.yml'), b'recipe')
        with zipfile.ZipFile(directory / 'uetlib-example-1.0.0-javadoc.jar') as jar:
            self.assertIn('no Java API', jar.read('README.txt').decode())

    def test_wrong_versions_and_empty_staging_fail(self):
        with self.assertRaises(ValueError):
            BUNDLE['collect_artifacts'](self.staging, '1.0.0')
        self.artifact(version='1.0.1')
        with self.assertRaises(ValueError):
            BUNDLE['collect_artifacts'](self.staging, '1.0.0')

    def test_symlink_artifacts_are_rejected(self):
        directory = self.artifact()
        jar = directory / 'uetlib-example-1.0.0.jar'
        external = self.root / 'external.jar'
        jar.rename(external)
        jar.symlink_to(external)
        with self.assertRaises(ValueError):
            BUNDLE['collect_artifacts'](self.staging, '1.0.0')


class ReleaseValidationTest(unittest.TestCase):
    def validate(self, ref='refs/tags/v1.0.0', repo='UbiqueInnovation/uetlib-example', group='ch.ubique.uetlib', reachable=True):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / 'pom.xml').write_text(f'<project xmlns="http://maven.apache.org/POM/4.0.0"><groupId>{group}</groupId><artifactId>uetlib-example</artifactId></project>')
            env = {'POM': 'pom.xml', 'RELEASE_REF': ref, 'REPOSITORY': repo, 'DEFAULT_BRANCH': 'main', 'GITHUB_OUTPUT': str(directory / 'output')}
            code = workflow('mvn-publish.yml')['jobs']['validate']['steps'][1]['run']
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ, env), patch('subprocess.check_output', return_value='refs/remotes/origin/main\n'), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0 if reachable else 1)):
                    exec(compile(code, 'validate-step', 'exec'), {})
                return (directory / 'output').read_text()
            finally:
                os.chdir(previous)

    def test_semver_and_composite_release_tags(self):
        self.assertEqual(self.validate(), 'version=1.0.0\n')
        self.assertEqual(self.validate(ref='refs/tags/v4.1.1-2026.11.0'), 'version=4.1.1-2026.11.0\n')

    def test_non_tag_snapshot_foreign_repository_and_private_group_are_rejected(self):
        for arguments in ({'ref': 'refs/heads/main'}, {'ref': 'refs/tags/v1.0.0-SNAPSHOT'}, {'repo': 'UbiqueInnovation/private-app'}, {'repo': 'another-org/uetlib-example'}, {'repo': 'UbiqueInnovation/uetlib-testapp'}, {'group': 'ch.ubique.private'}, {'reachable': False}):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit):
                self.validate(**arguments)


class CentralUploadTest(unittest.TestCase):
    def run_upload(self, states):
        deployment = '12345678-1234-1234-1234-123456789abc'
        with tempfile.TemporaryDirectory() as temp:
            env = {'CENTRAL_USERNAME': 'test-user', 'CENTRAL_PASSWORD': 'test-password', 'BUNDLE': temp + '/bundle.zip', 'GITHUB_STEP_SUMMARY': temp + '/summary'}
            responses = [io.BytesIO(__import__('json').dumps({'deploymentState': state}).encode()) for state in states]
            code = step_code('Upload and await publication')
            with patch.dict(os.environ, env), patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, deployment, '')) as upload, patch('urllib.request.urlopen', side_effect=responses), patch('time.sleep'), patch('sys.stdout', new_callable=io.StringIO):
                exec(compile(code, 'upload-step', 'exec'), {})
            command = upload.call_args.args[0]
            self.assertIn('publishingType=AUTOMATIC', command[-1])
            self.assertNotIn('test-password', ' '.join(command))
            self.assertIn('Authorization: Bearer ', upload.call_args.kwargs['input'])
            self.assertIn(deployment, Path(temp + '/summary').read_text())

    def test_upload_waits_until_published(self):
        self.run_upload(['VALIDATING', 'PUBLISHING', 'PUBLISHED'])

    def test_failed_validation_does_not_succeed(self):
        with self.assertRaisesRegex(SystemExit, 'Central validation failed'):
            self.run_upload(['FAILED'])


class WorkflowConfigurationTest(unittest.TestCase):
    def test_defaults_and_action_pins(self):
        for name in ('mvn-install.yml', 'mvn-publish.yml'):
            config = workflow(name)
            call = config.get('on', config.get(True))['workflow_call']
            self.assertEqual(call['inputs']['java-version']['default'], '25')
            for job in config['jobs'].values():
                for step in job['steps']:
                    if 'uses' in step:
                        self.assertRegex(step['uses'], r'@[a-f0-9]{40}$')
                    if step.get('shell') == 'python':
                        compile(step['run'], name, 'exec')

    def test_secrets_are_only_used_after_environment_gate_and_after_maven_build(self):
        config = workflow('mvn-publish.yml')
        self.assertNotIn('secrets.', str(config['jobs']['validate']))
        publish = config['jobs']['publish']
        self.assertEqual(publish['needs'], 'validate')
        self.assertEqual(publish['environment'], '${{ inputs.environment }}')
        build = next(s for s in publish['steps'] if s['name'] == 'Build, test and stage artifacts')
        self.assertNotIn('secrets.', str(build))
        self.assertIn('file://$STAGING', build['run'])
        self.assertNotIn('maven-source-plugin', build['run'])
        self.assertIn('clean install', build['run'])


if __name__ == '__main__':
    unittest.main()
