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

    def test_changelog_roadmap_and_live_samples_match_fallback_system_positioning(self) -> None:
        changelog_text = Path('CHANGELOG.md').read_text(encoding='utf-8')
        roadmap_text = Path('docs/roadmap.md').read_text(encoding='utf-8')
        live_samples_text = Path('docs/live-samples.md').read_text(encoding='utf-8')

        self.assertIn('OpenClaw fallback', changelog_text)
        self.assertIn('OpenClaw rescue chain', roadmap_text)
        self.assertIn('OpenClaw fallback system', live_samples_text)
        self.assertNotIn('generic install path', changelog_text)
        self.assertNotIn('hosted incident-management product', roadmap_text)


if __name__ == '__main__':
    unittest.main()
