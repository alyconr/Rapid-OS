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
      label: 'Cómo funciona',
      collapsed: false,
      items: [
        'governance-loop',
        'guides/permissions-capabilities',
        'guides/project-layout',
      ],
    },
    {
      type: 'category',
      label: 'Referencia',
      items: [
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
        'contributing/documentation',
      ],
    },
  ],
};

export default sidebars;
