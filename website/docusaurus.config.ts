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
  trailingSlash: false,
  favicon: 'img/rapid-os-social-card.svg',

  i18n: {
    defaultLocale: 'es',
    locales: ['es', 'en'],
    localeConfigs: {
      es: {label: 'Español', htmlLang: 'es-ES'},
      en: {label: 'English', htmlLang: 'en-US'},
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          path: '../docs',
          // Keep the source documentation in Spanish; English translations live under i18n/en/.
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
    metadata: [
      {name: 'description', content: 'Documentación oficial de RAPID OS v3: plataforma de gobernanza determinista para procesos de ingeniería asistidos por agentes de IA y coding harnesses.'},
      {name: 'keywords', content: 'rapid-os, ai-coding-harness, software-engineering, deterministic-governance, prompt-engineering, specification-driven, qa-automation'},
      {property: 'og:title', content: 'Rapid OS — Contract-Driven Engineering OS for AI Coding Harnesses'},
      {property: 'og:description', content: 'Gobernanza determinista, contratos de ejecución, evidence engine y evaluaciones conductuales para coding harnesses.'},
      {property: 'og:type', content: 'website'},
      {name: 'twitter:card', content: 'summary_large_image'},
      {name: 'twitter:title', content: 'Rapid OS — Contract-Driven Engineering OS for AI Coding Harnesses'},
      {name: 'twitter:description', content: 'Gobernanza determinista, contratos de ejecución, evidence engine y evaluaciones conductuales para coding harnesses.'},
    ],
    navbar: {
      title: 'Rapid OS',
      items: [
        {to: '/', label: 'Inicio', position: 'left'},
        {to: '/installation', label: 'Instalación', position: 'left'},
        {to: '/getting-started', label: 'Primeros pasos', position: 'left'},
        {to: '/guides/shortcuts', label: 'Shortcuts', position: 'left'},
        {to: '/guides/modes', label: 'Modos', position: 'left'},
        {to: '/cookbooks/policies-and-contracts', label: 'Cookbooks', position: 'left'},
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
            {label: 'Shortcuts', to: '/guides/shortcuts'},
            {label: 'Modos de ingeniería', to: '/guides/modes'},
            {label: 'Casos de uso', to: '/guides/use-cases'},
          ],
        },
        {
          title: 'Gobernanza y Práctica',
          items: [
            {label: 'Políticas y Contratos', to: '/cookbooks/policies-and-contracts'},
            {label: 'Capabilities y Perfiles', to: '/cookbooks/harness-profiles'},
            {label: 'Evidence Engine', to: '/cookbooks/evidence-engine'},
            {label: 'Behavioral Evals', to: '/cookbooks/behavioral-evaluations'},
            {label: 'Integración CI/CD', to: '/guides/ci-cd-integration'},
          ],
        },
        {
          title: 'Referencia',
          items: [
            {label: 'CLI', to: '/cli'},
            {label: 'Diagnósticos RAPIDxxx', to: '/troubleshooting/diagnostics'},
            {label: 'Arquitectura v3', to: '/architecture/rapid-os-v3'},
            {label: 'Arquitectura de orquestación', to: '/architecture/orchestration'},
            {label: 'Release v3.1.1', to: '/release-v3.1.1'},
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
      additionalLanguages: ['bash', 'powershell', 'json', 'toml', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
