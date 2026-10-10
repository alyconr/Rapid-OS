import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    {
      type: 'category',
      label: 'Introducción y Conceptos',
      collapsed: false,
      items: [
        'index',
        'concepts/what-is-rapid-os',
        'concepts/why-rapid-os',
        'concepts/core-concepts',
        'concepts/product-boundaries',
        'guides/use-cases',
      ],
    },
    {
      type: 'category',
      label: 'Instalación',
      collapsed: false,
      items: [
        'installation/index',
        'installation/requirements',
        'installation/windows',
        'installation/linux',
        'installation/macos',
        'installation/wsl',
        'installation/verification',
        'installation/upgrade',
        'troubleshooting/installation',
      ],
    },
    {
      type: 'category',
      label: 'Primeros pasos',
      collapsed: false,
      link: {type: 'doc', id: 'getting-started'},
      items: [
        'getting-started/first-project',
        'getting-started/existing-project',
        'getting-started/first-spec',
        'getting-started/first-context',
        'getting-started/next-steps',
      ],
    },
    {
      type: 'category',
      label: 'Modos de ingeniería',
      collapsed: false,
      link: {type: 'doc', id: 'guides/modes/index'},
      items: [
        'guides/modes/feature',
        'guides/modes/bugfix',
        'guides/modes/refactor',
        'guides/modes/hardening',
        'guides/modes/research',
      ],
    },
    {
      type: 'category',
      label: 'Laboratorios Prácticos',
      collapsed: false,
      link: {type: 'doc', id: 'tutorials/index'},
      items: [
        'tutorials/first-governed-project',
        'tutorials/feature-lab',
        'tutorials/bugfix-lab',
        'tutorials/refactor-lab',
        'tutorials/hardening-lab',
        'tutorials/research-lab',
        'troubleshooting/tutorials',
      ],
    },
    {
      type: 'category',
      label: 'Integraciones con Coding Harnesses',
      collapsed: false,
      link: {type: 'doc', id: 'integrations/index'},
      items: [
        'integrations/codex',
        'integrations/claude-code',
        'integrations/cursor',
        'integrations/vscode',
        'integrations/antigravity',
      ],
    },
    {
      type: 'category',
      label: 'Cookbooks de Gobernanza',
      collapsed: false,
      items: [
        'cookbooks/policies-and-contracts',
        'cookbooks/harness-profiles',
        'cookbooks/evidence-engine',
        'cookbooks/behavioral-evaluations',
      ],
    },
    {
      type: 'category',
      label: 'Cómo funciona',
      collapsed: false,
      items: [
        'governance-loop',
        'guides/permissions-capabilities',
        'guides/project-layout',
        'guides/ci-cd-integration',
      ],
    },
    {
      type: 'category',
      label: 'Diagnósticos y Referencia',
      items: [
        'troubleshooting/diagnostics',
        'cli',
        'architecture/rapid-os-v3',
      ],
    },
    {
      type: 'category',
      label: 'Operación y release',
      items: [
        'release-v3.0.0',
        'release-checklist',
        'audit/documentation-scope',
        'audit/sprint-1-validation',
        'audit/sprint-2-validation',
        'audit/sprint-3-validation',
        'contributing/documentation',
      ],
    },
  ],
};

export default sidebars;
