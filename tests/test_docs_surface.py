from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


class DocsSurfaceTest(unittest.TestCase):
    def test_current_surface_does_not_expose_repair_facade(self) -> None:
        self.assertIsNone(importlib.util.find_spec('openclaw_watchdog.repair'))

        readme_text = Path('README.md').read_text(encoding='utf-8')
        architecture_text = Path('docs/internal-architecture.md').read_text(encoding='utf-8')
        lifecycle_text = Path('docs/rescue-lifecycle.md').read_text(encoding='utf-8')

        self.assertNotIn('openclaw_watchdog/repair.py', readme_text)
        self.assertNotIn('compatibility facade', readme_text)
        self.assertNotIn('openclaw_watchdog/repair.py', architecture_text)
        self.assertNotIn('compatibility facade', architecture_text)
        self.assertNotIn('compatibility `repair.py` facade', lifecycle_text)

    def test_plan_docs_do_not_reference_legacy_watchdog_v2_surface(self) -> None:
        for path in sorted(Path('docs/plans').glob('*.md')):
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('watchdog_v2', text, str(path))
            self.assertNotIn('openclaw-watchdog-v2', text, str(path))
            self.assertNotIn('MIGRATION-v2', text, str(path))

    def test_current_faq_does_not_advertise_v2_shims(self) -> None:
        faq_text = Path('docs/faq.md').read_text(encoding='utf-8')

        self.assertNotIn('`-v2`', faq_text)
        self.assertNotIn('migration shims', faq_text)

    def test_changelog_no_longer_describes_v2_shim_support_as_current(self) -> None:
        changelog_text = Path('CHANGELOG.md').read_text(encoding='utf-8')

        self.assertNotIn('Deprecated `v2` wrappers were reduced to migration shims', changelog_text)
        self.assertNotIn('Deprecated shim scripts remain available for transition', changelog_text)

    def test_current_docs_frame_project_as_openclaw_specific_fallback_system(self) -> None:
        readme_text = Path('README.md').read_text(encoding='utf-8')
        architecture_text = Path('docs/internal-architecture.md').read_text(encoding='utf-8')
        lifecycle_text = Path('docs/rescue-lifecycle.md').read_text(encoding='utf-8')
        faq_text = Path('docs/faq.md').read_text(encoding='utf-8')

        self.assertIn('OpenClaw fallback', readme_text)
        self.assertIn('OpenClaw-specific', architecture_text)
        self.assertIn('fallback system', lifecycle_text)
        self.assertIn('fallback system', faq_text)
        self.assertNotIn('recovery toolkit', readme_text)
        self.assertNotIn('generic watchdog toolkit', architecture_text)

    def test_deployment_and_rehearsal_docs_keep_detect_only_and_no_install_model(self) -> None:
        deployment_text = Path('docs/first-deployment.md').read_text(encoding='utf-8')
        rehearsal_text = Path('rehearsal/README.md').read_text(encoding='utf-8')
        acceptance_text = Path('docs/live-acceptance-checklist.md').read_text(encoding='utf-8')

        self.assertIn('detect-only', deployment_text)
        self.assertIn('does not install missing rescue tools', deployment_text)
        self.assertIn('codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent', deployment_text)
        self.assertIn('without installing anything', rehearsal_text)
        self.assertIn('without installing extra software', rehearsal_text)
        self.assertIn('critical', rehearsal_text)
        self.assertIn('fallback system', acceptance_text)

    def test_readme_points_first_rollout_to_first_deployment_and_live_acceptance(self) -> None:
        readme_text = Path('README.md').read_text(encoding='utf-8')

        self.assertIn('docs/first-deployment.md', readme_text)
        self.assertIn('live acceptance', readme_text.lower())

    def test_first_deployment_spells_out_the_operator_quick_path(self) -> None:
        deployment_text = Path('docs/first-deployment.md').read_text(encoding='utf-8')

        self.assertIn('detect -> check -> status --summary -> report --message', deployment_text)
        self.assertIn('scripts/openclaw-watchdog-live-acceptance.sh', deployment_text)

    def test_release_readiness_docs_are_linked_from_current_surfaces(self) -> None:
        readme_text = Path('README.md').read_text(encoding='utf-8')
        docs_index_text = Path('docs/README.md').read_text(encoding='utf-8')

        self.assertIn('docs/release-readiness.md', readme_text)
        self.assertIn('docs/release-notes-v0.2.0-draft.md', readme_text)
        self.assertIn('release-readiness.md', docs_index_text)
        self.assertIn('release-notes-v0.2.0-draft.md', docs_index_text)

    def test_release_readiness_docs_cover_live_rollout_and_next_release(self) -> None:
        readiness_text = Path('docs/release-readiness.md').read_text(encoding='utf-8')
        release_notes_text = Path('docs/release-notes-v0.2.0-draft.md').read_text(encoding='utf-8')

        self.assertIn('live acceptance', readiness_text.lower())
        self.assertIn('v0.2.0', readiness_text)
        self.assertIn('python 3.11+', readiness_text.lower())
        self.assertIn('v0.2.0', release_notes_text)
        self.assertIn('critical rehearsal', release_notes_text.lower())

    def test_release_surfaces_identify_the_next_release_candidate(self) -> None:
        readme_text = Path('README.md').read_text(encoding='utf-8')
        changelog_text = Path('CHANGELOG.md').read_text(encoding='utf-8')
        pyproject_text = Path('pyproject.toml').read_text(encoding='utf-8')

        self.assertIn('v0.2.0', readme_text)
        self.assertIn('planned next release', changelog_text.lower())
        self.assertIn('version = "0.2.0"', pyproject_text)

    def test_python_classifiers_match_the_documented_ci_versions(self) -> None:
        pyproject_text = Path('pyproject.toml').read_text(encoding='utf-8')
        readme_text = Path('README.md').read_text(encoding='utf-8')
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        self.assertIn('Programming Language :: Python :: 3.13', pyproject_text)
        self.assertIn('python3.13', readme_text.lower())
        self.assertIn("'3.13'", workflow_text)

    def test_release_runbook_is_linked_from_current_release_surfaces(self) -> None:
        readme_text = Path('README.md').read_text(encoding='utf-8')
        docs_index_text = Path('docs/README.md').read_text(encoding='utf-8')
        readiness_text = Path('docs/release-readiness.md').read_text(encoding='utf-8')
        release_notes_text = Path('docs/release-notes-v0.2.0-draft.md').read_text(encoding='utf-8')

        self.assertIn('docs/release-v0.2.0-runbook.md', readme_text)
        self.assertIn('release-v0.2.0-runbook.md', docs_index_text)
        self.assertIn('release-v0.2.0-runbook.md', readiness_text)
        self.assertIn('release-v0.2.0-runbook.md', release_notes_text)

    def test_release_runbook_names_tag_and_publish_steps(self) -> None:
        runbook_text = Path('docs/release-v0.2.0-runbook.md').read_text(encoding='utf-8')

        self.assertIn('git tag -a v0.2.0', runbook_text)
        self.assertIn('git push origin main', runbook_text)
        self.assertIn('git push origin v0.2.0', runbook_text)
        self.assertIn('OpenClaw Watchdog v0.2.0', runbook_text)
        self.assertIn('docs/p7a-live/', runbook_text)

    def test_changelog_roadmap_and_live_samples_match_fallback_system_positioning(self) -> None:
        changelog_text = Path('CHANGELOG.md').read_text(encoding='utf-8')
        roadmap_text = Path('docs/roadmap.md').read_text(encoding='utf-8')
        live_samples_text = Path('docs/live-samples.md').read_text(encoding='utf-8')

        self.assertIn('OpenClaw fallback', changelog_text)
        self.assertIn('OpenClaw rescue chain', roadmap_text)
        self.assertIn('OpenClaw fallback system', live_samples_text)
        self.assertNotIn('generic install path', changelog_text)
        self.assertNotIn('hosted incident-management product', roadmap_text)

    def test_docs_include_experimental_macos_launchd_path(self) -> None:
        readme_text = Path('README.md').read_text(encoding='utf-8')
        deployment_text = Path('docs/first-deployment.md').read_text(encoding='utf-8')
        supported_text = Path('docs/supported-environments.md').read_text(encoding='utf-8')
        architecture_text = Path('docs/internal-architecture.md').read_text(encoding='utf-8')

        self.assertIn('macOS', readme_text)
        self.assertIn('launchd', readme_text)
        self.assertIn('experimental', readme_text)
        self.assertIn('macOS', deployment_text)
        self.assertIn('launchd', deployment_text)
        self.assertIn('macOS', supported_text)
        self.assertIn('experimental', supported_text)
        self.assertIn('launchd', architecture_text)
        self.assertTrue(Path('launchd/com.eudonline.openclaw-watchdog.plist').exists())
        self.assertTrue(Path('scripts/install-openclaw-watchdog-launchd.sh').exists())


if __name__ == '__main__':
    unittest.main()
