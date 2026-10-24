import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/Rapid-OS/',
    component: ComponentCreator('/Rapid-OS/', '079'),
    routes: [
      {
        path: '/Rapid-OS/',
        component: ComponentCreator('/Rapid-OS/', 'b12'),
        routes: [
          {
            path: '/Rapid-OS/',
            component: ComponentCreator('/Rapid-OS/', 'a24'),
            routes: [
              {
                path: '/Rapid-OS/architecture/orchestration',
                component: ComponentCreator('/Rapid-OS/architecture/orchestration', '3cc'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/architecture/rapid-os-v2',
                component: ComponentCreator('/Rapid-OS/architecture/rapid-os-v2', 'da3'),
                exact: true
              },
              {
                path: '/Rapid-OS/architecture/rapid-os-v3',
                component: ComponentCreator('/Rapid-OS/architecture/rapid-os-v3', 'f76'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/documentation-scope',
                component: ComponentCreator('/Rapid-OS/audit/documentation-scope', '70f'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/sprint-1-validation',
                component: ComponentCreator('/Rapid-OS/audit/sprint-1-validation', 'f80'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/sprint-2-validation',
                component: ComponentCreator('/Rapid-OS/audit/sprint-2-validation', 'aca'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/sprint-3-validation',
                component: ComponentCreator('/Rapid-OS/audit/sprint-3-validation', '0eb'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/sprint-4-validation',
                component: ComponentCreator('/Rapid-OS/audit/sprint-4-validation', '98e'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/sprint-5-validation',
                component: ComponentCreator('/Rapid-OS/audit/sprint-5-validation', 'd81'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/cli',
                component: ComponentCreator('/Rapid-OS/cli', '583'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/architecture',
                component: ComponentCreator('/Rapid-OS/concepts/architecture', '757'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/core-concepts',
                component: ComponentCreator('/Rapid-OS/concepts/core-concepts', 'acf'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/infrastructure-services',
                component: ComponentCreator('/Rapid-OS/concepts/infrastructure-services', '489'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/product-boundaries',
                component: ComponentCreator('/Rapid-OS/concepts/product-boundaries', '1ba'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/project-docs',
                component: ComponentCreator('/Rapid-OS/concepts/project-docs', '86e'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/security-baseline',
                component: ComponentCreator('/Rapid-OS/concepts/security-baseline', 'e24'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/stacks',
                component: ComponentCreator('/Rapid-OS/concepts/stacks', '101'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/what-is-rapid-os',
                component: ComponentCreator('/Rapid-OS/concepts/what-is-rapid-os', '073'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/why-rapid-os',
                component: ComponentCreator('/Rapid-OS/concepts/why-rapid-os', '879'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/contributing/documentation',
                component: ComponentCreator('/Rapid-OS/contributing/documentation', 'eb4'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/cookbooks/behavioral-evaluations',
                component: ComponentCreator('/Rapid-OS/cookbooks/behavioral-evaluations', 'c53'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/cookbooks/evidence-engine',
                component: ComponentCreator('/Rapid-OS/cookbooks/evidence-engine', '481'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/cookbooks/harness-profiles',
                component: ComponentCreator('/Rapid-OS/cookbooks/harness-profiles', '3a8'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/cookbooks/policies-and-contracts',
                component: ComponentCreator('/Rapid-OS/cookbooks/policies-and-contracts', '242'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started',
                component: ComponentCreator('/Rapid-OS/getting-started', '5a2'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started/existing-project',
                component: ComponentCreator('/Rapid-OS/getting-started/existing-project', '55b'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started/first-context',
                component: ComponentCreator('/Rapid-OS/getting-started/first-context', 'a26'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started/first-project',
                component: ComponentCreator('/Rapid-OS/getting-started/first-project', '786'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started/first-spec',
                component: ComponentCreator('/Rapid-OS/getting-started/first-spec', '494'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started/next-steps',
                component: ComponentCreator('/Rapid-OS/getting-started/next-steps', 'f6b'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started/when-the-agent-stops',
                component: ComponentCreator('/Rapid-OS/getting-started/when-the-agent-stops', '630'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/governance-loop',
                component: ComponentCreator('/Rapid-OS/governance-loop', 'c9d'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/ci-cd-integration',
                component: ComponentCreator('/Rapid-OS/guides/ci-cd-integration', 'abe'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/deployment',
                component: ComponentCreator('/Rapid-OS/guides/deployment', 'cbc'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/modes',
                component: ComponentCreator('/Rapid-OS/guides/modes', 'f31'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/modes/bugfix',
                component: ComponentCreator('/Rapid-OS/guides/modes/bugfix', 'ebf'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/modes/feature',
                component: ComponentCreator('/Rapid-OS/guides/modes/feature', 'd20'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/modes/hardening',
                component: ComponentCreator('/Rapid-OS/guides/modes/hardening', '4e6'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/modes/refactor',
                component: ComponentCreator('/Rapid-OS/guides/modes/refactor', 'be2'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/modes/research',
                component: ComponentCreator('/Rapid-OS/guides/modes/research', 'd44'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/permissions-capabilities',
                component: ComponentCreator('/Rapid-OS/guides/permissions-capabilities', 'e59'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/project-layout',
                component: ComponentCreator('/Rapid-OS/guides/project-layout', '4bd'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/setup-json-migration',
                component: ComponentCreator('/Rapid-OS/guides/setup-json-migration', '78b'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/shortcuts',
                component: ComponentCreator('/Rapid-OS/guides/shortcuts', '7f3'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/use-cases',
                component: ComponentCreator('/Rapid-OS/guides/use-cases', '1ca'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation',
                component: ComponentCreator('/Rapid-OS/installation', '367'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation/linux',
                component: ComponentCreator('/Rapid-OS/installation/linux', '745'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation/macos',
                component: ComponentCreator('/Rapid-OS/installation/macos', '1d8'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation/requirements',
                component: ComponentCreator('/Rapid-OS/installation/requirements', '38f'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation/upgrade',
                component: ComponentCreator('/Rapid-OS/installation/upgrade', 'f69'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation/verification',
                component: ComponentCreator('/Rapid-OS/installation/verification', 'cd9'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation/windows',
                component: ComponentCreator('/Rapid-OS/installation/windows', 'e84'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/installation/wsl',
                component: ComponentCreator('/Rapid-OS/installation/wsl', '786'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/integrations',
                component: ComponentCreator('/Rapid-OS/integrations', '4f5'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/integrations/antigravity',
                component: ComponentCreator('/Rapid-OS/integrations/antigravity', '466'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/integrations/claude-code',
                component: ComponentCreator('/Rapid-OS/integrations/claude-code', '2dd'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/integrations/codex',
                component: ComponentCreator('/Rapid-OS/integrations/codex', 'eb3'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/integrations/cursor',
                component: ComponentCreator('/Rapid-OS/integrations/cursor', '15c'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/integrations/vscode',
                component: ComponentCreator('/Rapid-OS/integrations/vscode', '3a1'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/operations/documentation-deployment',
                component: ComponentCreator('/Rapid-OS/operations/documentation-deployment', '778'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/operations/documentation-maintenance',
                component: ComponentCreator('/Rapid-OS/operations/documentation-maintenance', '1f2'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/operations/documentation-rollback',
                component: ComponentCreator('/Rapid-OS/operations/documentation-rollback', '1fc'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/release-checklist',
                component: ComponentCreator('/Rapid-OS/release-checklist', '1de'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/release-v3.0.0',
                component: ComponentCreator('/Rapid-OS/release-v3.0.0', 'fda'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/release-v3.1.0',
                component: ComponentCreator('/Rapid-OS/release-v3.1.0', 'a6a'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/release-v3.1.1',
                component: ComponentCreator('/Rapid-OS/release-v3.1.1', 'b84'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/troubleshooting/diagnostics',
                component: ComponentCreator('/Rapid-OS/troubleshooting/diagnostics', '3be'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/troubleshooting/installation',
                component: ComponentCreator('/Rapid-OS/troubleshooting/installation', '153'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/troubleshooting/tutorials',
                component: ComponentCreator('/Rapid-OS/troubleshooting/tutorials', '3d8'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/tutorials',
                component: ComponentCreator('/Rapid-OS/tutorials', '851'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/tutorials/bugfix-lab',
                component: ComponentCreator('/Rapid-OS/tutorials/bugfix-lab', '8a5'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/tutorials/feature-lab',
                component: ComponentCreator('/Rapid-OS/tutorials/feature-lab', '9c9'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/tutorials/first-governed-project',
                component: ComponentCreator('/Rapid-OS/tutorials/first-governed-project', '4cf'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/tutorials/hardening-lab',
                component: ComponentCreator('/Rapid-OS/tutorials/hardening-lab', 'e86'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/tutorials/refactor-lab',
                component: ComponentCreator('/Rapid-OS/tutorials/refactor-lab', '863'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/tutorials/research-lab',
                component: ComponentCreator('/Rapid-OS/tutorials/research-lab', '42c'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/',
                component: ComponentCreator('/Rapid-OS/', '40e'),
                exact: true,
                sidebar: "docs"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
