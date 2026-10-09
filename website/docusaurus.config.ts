import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import {themes as prismThemes} from 'prism-react-renderer';

const config: Config = {
  title: 'Rapid OS',
  tagline: 'Contract-Driven Engineering OS for AI Coding Harnesses',
  url: 'https://alyconr.github.io',
  baseUrl: '/Rapid-OS/',
  organizationName: 'alyconr',
  projectName: 'Rapid-OS',
  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'es',
    locales: ['es'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          path: '../docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/alyconr/Rapid-OS/edit/main/docs/',
          showLastUpdateAuthor: true,
          showLastUpdateTime: true,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/rapid-os-social-card.svg',
    navbar: {
      title: 'Rapid OS',
      items: [
        {to: '/', label: 'Inicio', position: 'left'},
        {to: '/installation', label: 'Instalación', position: 'left'},
        {to: '/getting-started', label: 'Primeros pasos', position: 'left'},
        {to: '/governance-loop', label: 'Gobernanza v3', position: 'left'},
        {to: '/cli', label: 'CLI', position: 'left'},
        {
          href: 'https://github.com/alyconr/Rapid-OS',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Aprender',
          items: [
            {label: 'Qué es Rapid OS', to: '/concepts/what-is-rapid-os'},
            {label: 'Por qué Rapid OS', to: '/concepts/why-rapid-os'},
            {label: 'Instalación', to: '/installation'},
            {label: 'Primeros pasos', to: '/getting-started'},
            {label: 'Casos de uso', to: '/guides/use-cases'},
            {label: 'Capabilities y permisos', to: '/guides/permissions-capabilities'},
          ],
        },
        {
          title: 'Referencia',
          items: [
            {label: 'CLI', to: '/cli'},
            {label: 'Arquitectura v3', to: '/architecture/rapid-os-v3'},
            {label: 'Release v3.0.0', to: '/release-v3.0.0'},
          ],
        },
        {
          title: 'Proyecto',
          items: [
            {label: 'Repositorio', href: 'https://github.com/alyconr/Rapid-OS'},
            {label: 'Issues', href: 'https://github.com/alyconr/Rapid-OS/issues'},
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Rapid OS. MIT License.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'powershell', 'json', 'toml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
