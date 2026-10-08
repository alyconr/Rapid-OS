import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    {
      type: 'category',
      label: 'Empieza aquí',
      collapsed: false,
      items: [
        'index',
        'concepts/what-is-rapid-os',
        'getting-started',
        'guides/use-cases',
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
      ],
    },
  ],
};

export default sidebars;
