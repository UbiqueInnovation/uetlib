import json
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


class ReleaseValidationTest(unittest.TestCase):
    def validate(self, ref='refs/tags/v1.0.0', changelog='AUTO'):
        steps = workflow('mvn-publish.yml')['jobs']['validate']['steps']
        script = next(s['with']['script'] for s in steps if s.get('id') == 'release')
        harness = """
          const script = require('fs').readFileSync(0, 'utf8');
          const outputs = {};
          new Function('context', 'core', 'require', script)(
            {ref: process.argv[1]}, {setOutput: (key, value) => outputs[key] = value}, require);
          console.log(JSON.stringify(outputs));
        """
        with tempfile.TemporaryDirectory() as temp:
            if changelog == 'AUTO':
                changelog = '## ' + ref.removeprefix('refs/tags/v') + '\n\n- Release changes.\n'
            if changelog is not None:
                (Path(temp) / 'CHANGELOG.md').write_text(changelog)
            result = subprocess.run(['node', '-e', harness, ref], input=script, cwd=temp,
                                    text=True, capture_output=True)
        if result.returncode:
            raise ValueError(result.stderr)
        return json.loads(result.stdout)

    def test_semver_calendar_prerelease_and_composite_tags(self):
        for version in ('1.0.0', '2026.11.0', '3.0.0-alpha.1', '4.1.1-2026.11.0'):
            with self.subTest(version=version):
                self.assertEqual(self.validate('refs/tags/v' + version)['version'], version)

    def test_branches_snapshots_and_malformed_tags_are_rejected(self):
        for ref in ('refs/heads/main', 'refs/tags/1.0.0', 'refs/tags/v1.0.0-SNAPSHOT',
                    'refs/tags/v1.0.0-snapshot', 'refs/tags/v', 'refs/tags/v1.2', 'refs/tags/vbad'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                self.validate(ref)

    def test_stable_releases_require_an_exact_version_heading_and_entry(self):
        for changelog in (None, '# Changelog\n', '## 1.0.01\n- Other version.\n',
                          'Mention 1.0.0 in prose.\n', '## 1.0.0\n\n## 0.9.0\n- Older changes.\n',
                          '## 1.0.0\n### Changes\n'):
            with self.subTest(changelog=changelog), self.assertRaises(ValueError):
                self.validate(changelog=changelog)

    def test_common_changelog_headings_and_nested_sections(self):
        for heading in ('# 1.0.0', '## [1.0.0] - 2026-11-02', '## v1.0.0',
                        '## [v1.0.0]', '## 1.0.0 (unreleased)'):
            with self.subTest(heading=heading):
                result = self.validate(changelog=heading + '\r\n\r\n### Fixes\r\n- A fix.\r\n')
                self.assertEqual(result['prerelease'], 'false')

    def test_prereleases_do_not_need_a_changelog(self):
        for version in ('1.0.0-alpha.1', '1.0.0-rc.2', '1.0.0-1'):
            with self.subTest(version=version):
                result = self.validate('refs/tags/v' + version, changelog=None)
                self.assertEqual(result['prerelease'], 'true')

    def test_calendar_and_starter_parent_releases_require_changelogs(self):
        for version in ('2026.11.0', '4.1.1-2026.11.0'):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    self.validate('refs/tags/v' + version, changelog=None)
                self.assertEqual(self.validate('refs/tags/v' + version)['prerelease'], 'false')


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

    def test_setup_java_configures_the_same_credentials_used_by_maven(self):
        config = workflow('mvn-publish.yml')
        publish = config['jobs']['publish']
        setup = next(s for s in publish['steps'] if s['name'] == 'Set up Java')['with']
        deploy = next(s for s in publish['steps'] if s['name'] == 'Publish to Maven Central')
        self.assertEqual(setup['server-id'], 'central')
        for setting in ('server-username-env-var', 'server-password-env-var', 'gpg-passphrase-env-var'):
            self.assertIn(setup[setting], deploy['env'])
        self.assertEqual(setup['gpg-private-key'], '${{ secrets.MAVEN_SIGNING_KEY_ARMOR_ASC }}')
        self.assertEqual(deploy['env']['MAVEN_GPG_PASSPHRASE'], '${{ secrets.MAVEN_SIGNING_KEY_PASSPHRASE }}')
        self.assertIn('-Pcentral-release clean deploy', deploy['run'])
        self.assertNotIn('gpg.skip', deploy['run'])

    def test_credentials_are_environment_gated_and_only_four_secrets_are_required(self):
        config = workflow('mvn-publish.yml')
        self.assertNotIn('secrets.', str(config['jobs']['validate']))
        publish = config['jobs']['publish']
        self.assertEqual(publish['needs'], 'validate')
        self.assertEqual(publish['environment'], '${{ inputs.environment }}')
        call = config.get('on', config.get(True))['workflow_call']
        self.assertEqual(set(call['secrets']), {
            'MAVEN_SIGNING_KEY_ARMOR_ASC', 'MAVEN_SIGNING_KEY_PASSPHRASE',
            'MAVEN_CENTRAL_USERNAME', 'MAVEN_CENTRAL_PASSWORD'})
        self.assertNotIn('MAVEN_SIGNING_KEY_ID', str(config))

    def test_github_release_is_created_only_after_maven_publication(self):
        steps = workflow('mvn-publish.yml')['jobs']['publish']['steps']
        names = [s['name'] for s in steps]
        self.assertLess(names.index('Publish to Maven Central'), names.index('Create GitHub release'))
        release = next(s for s in steps if s['name'] == 'Create GitHub release')
        self.assertEqual(release['if'], '${{ inputs.create-github-release }}')
        self.assertNotIn('always()', release['if'])
        self.assertIn('--verify-tag', release['run'])
        self.assertEqual(release['env']['PRERELEASE'], '${{ needs.validate.outputs.prerelease }}')
        self.assertIn('$PRERELEASE', release['run'])

    def test_embedded_shell_scripts_are_valid_bash(self):
        for name in ('mvn-install.yml', 'mvn-publish.yml'):
            for job in workflow(name)['jobs'].values():
                for step in job['steps']:
                    if 'run' in step and step.get('shell', job.get('defaults', {}).get('run', {}).get('shell')) == 'bash':
                        result = subprocess.run(['bash', '-n'], input=step['run'], text=True, capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr)


class NativeInputsTest(unittest.TestCase):
    def run_step(self, workflow_name, step_name, env, cwd):
        for job in workflow(workflow_name)['jobs'].values():
            for step in job['steps']:
                if step['name'] == step_name:
                    return subprocess.run(['bash', '-e', '-c', step['run']], cwd=cwd, text=True,
                                          capture_output=True, env={**os.environ, **env})
        raise KeyError(step_name)

    def test_native_artifacts_are_required_and_merged_into_resources(self):
        for name in ('mvn-install.yml', 'mvn-publish.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temp:
                checkout, downloads = Path(temp, 'checkout'), Path(temp, 'native-artifacts')
                checkout.mkdir()
                for artifact, classifier in (('native-a', 'linux-x86_64'), ('native-b', 'macos-aarch64')):
                    Path(downloads, artifact, classifier).mkdir(parents=True)
                    Path(downloads, artifact, classifier, 'lib.so').write_text(artifact)
                Path(downloads, 'native-empty').mkdir()

                def stage(artifacts):
                    return self.run_step(name, 'Stage native artifacts',
                                         {'RUNNER_TEMP': temp, 'ARTIFACTS': artifacts}, checkout)

                result = stage('native-a native-b')
                self.assertEqual(result.returncode, 0, result.stderr)
                resources = checkout / 'src/main/resources/native'
                self.assertEqual((resources / 'linux-x86_64/lib.so').read_text(), 'native-a')
                self.assertEqual((resources / 'macos-aarch64/lib.so').read_text(), 'native-b')
                for artifacts in ('native-a native-missing', 'native-empty', '..', 'native-a/../native-b'):
                    with self.subTest(artifacts=artifacts):
                        self.assertNotEqual(stage(artifacts).returncode, 0)

    def test_system_package_names_are_validated(self):
        for name in ('mvn-install.yml', 'mvn-publish.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temp:
                log = Path(temp, 'sudo.log')
                Path(temp, 'sudo').write_text(f'#!/bin/sh\necho "$@" >> {log}\n')
                Path(temp, 'sudo').chmod(0o755)
                env = {'PATH': temp + os.pathsep + os.environ['PATH']}

                result = self.run_step(name, 'Install system packages',
                                       {**env, 'PACKAGES': 'libwebp7 libpng16-16 g++'}, temp)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('install -y --no-install-recommends libwebp7 libpng16-16 g++', log.read_text())
                for packages in ('-o=evil', 'pkg;id', 'Upper'):
                    with self.subTest(packages=packages):
                        log.unlink(missing_ok=True)
                        result = self.run_step(name, 'Install system packages', {**env, 'PACKAGES': packages}, temp)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertFalse(log.exists())

    def test_native_inputs_run_before_maven(self):
        for name, job in (('mvn-install.yml', 'build'), ('mvn-publish.yml', 'publish')):
            with self.subTest(workflow=name):
                names = [s['name'] for s in workflow(name)['jobs'][job]['steps']]
                self.assertLess(names.index('Stage native artifacts'), names.index('Set up Java'))
                self.assertLess(names.index('Install system packages'), names.index('Set up Java'))


class SonarTest(unittest.TestCase):
    def test_analysis_reuses_install_results(self):
        config = workflow('mvn-install.yml')
        call = config.get('on', config.get(True))['workflow_call']
        self.assertFalse(call['inputs']['sonar']['default'])
        self.assertFalse(call['secrets']['SONAR_TOKEN']['required'])
        steps = config['jobs']['build']['steps']
        build = next(s for s in steps if s['name'] == 'Build, test and install')
        scan = next(s for s in steps if s['name'] == 'Run SonarCloud analysis')
        self.assertLess(steps.index(build), steps.index(scan))
        self.assertEqual(scan['if'], '${{ inputs.sonar }}')
        self.assertNotIn('SONAR_TOKEN', build['env'])
        self.assertEqual(scan['env']['SONAR_TOKEN'], '${{ secrets.SONAR_TOKEN }}')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            maven = root / 'mvn'
            maven.write_text('#!/bin/bash\n'
                             'if [[ "$*" == *"clean install" ]]; then\n'
                             '  touch coverage.xml\n'
                             'elif [[ "$*" == *"sonar-maven-plugin:sonar" ]]; then\n'
                             '  test -f coverage.xml || exit 1\n'
                             'else exit 1; fi\n'
                             'echo "$*" >> calls\n')
            maven.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'], POM='pom.xml')
            for step in (build, scan):
                subprocess.run(['bash', '-e', '-c', step['run']], cwd=root, env=env, check=True)
            calls = (root / 'calls').read_text().splitlines()
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0].endswith('clean install'))
            self.assertTrue(calls[1].endswith('org.sonarsource.scanner.maven:sonar-maven-plugin:sonar'))
            self.assertNotRegex(calls[1], r'\b(test|verify|install|clean)\b')


if __name__ == '__main__':
    unittest.main()
