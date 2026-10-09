import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/Rapid-OS/',
    component: ComponentCreator('/Rapid-OS/', 'ab6'),
    routes: [
      {
        path: '/Rapid-OS/',
        component: ComponentCreator('/Rapid-OS/', 'fbf'),
        routes: [
          {
            path: '/Rapid-OS/',
            component: ComponentCreator('/Rapid-OS/', '732'),
            routes: [
              {
                path: '/Rapid-OS/architecture/rapid-os-v2',
                component: ComponentCreator('/Rapid-OS/architecture/rapid-os-v2', '696'),
                exact: true
              },
              {
                path: '/Rapid-OS/architecture/rapid-os-v3',
                component: ComponentCreator('/Rapid-OS/architecture/rapid-os-v3', 'c9e'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/documentation-scope',
                component: ComponentCreator('/Rapid-OS/audit/documentation-scope', 'c44'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/audit/sprint-1-validation',
                component: ComponentCreator('/Rapid-OS/audit/sprint-1-validation', 'fe1'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/cli',
                component: ComponentCreator('/Rapid-OS/cli', '5c5'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/concepts/what-is-rapid-os',
                component: ComponentCreator('/Rapid-OS/concepts/what-is-rapid-os', 'a0a'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/contributing/documentation',
                component: ComponentCreator('/Rapid-OS/contributing/documentation', 'c7b'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/getting-started',
                component: ComponentCreator('/Rapid-OS/getting-started', 'cf2'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/governance-loop',
                component: ComponentCreator('/Rapid-OS/governance-loop', 'c61'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/permissions-capabilities',
                component: ComponentCreator('/Rapid-OS/guides/permissions-capabilities', 'b3f'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/project-layout',
                component: ComponentCreator('/Rapid-OS/guides/project-layout', 'f42'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/guides/use-cases',
                component: ComponentCreator('/Rapid-OS/guides/use-cases', 'cb8'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/release-checklist',
                component: ComponentCreator('/Rapid-OS/release-checklist', '526'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/release-v3.0.0',
                component: ComponentCreator('/Rapid-OS/release-v3.0.0', '968'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/Rapid-OS/',
                component: ComponentCreator('/Rapid-OS/', '0d4'),
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
