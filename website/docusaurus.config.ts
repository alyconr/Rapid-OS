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
    defaultLocale: 'en',
    locales: ['en', 'es'],
    localeConfigs: {
      en: {label: 'English', htmlLang: 'en-US'},
      es: {label: 'Español', htmlLang: 'es-ES'},
    },
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
    metadata: [
      {name: 'description', content: 'Official RAPID OS v3 documentation: a deterministic governance platform for engineering processes assisted by AI agents and coding harnesses.'},
      {name: 'keywords', content: 'rapid-os, ai-coding-harness, software-engineering, deterministic-governance, prompt-engineering, specification-driven, qa-automation'},
      {property: 'og:title', content: 'Rapid OS — Contract-Driven Engineering OS for AI Coding Harnesses'},
      {property: 'og:description', content: 'Deterministic governance, execution contracts, evidence engine, and behavioral evaluations for coding harnesses.'},
      {property: 'og:type', content: 'website'},
      {name: 'twitter:card', content: 'summary_large_image'},
      {name: 'twitter:title', content: 'Rapid OS — Contract-Driven Engineering OS for AI Coding Harnesses'},
      {name: 'twitter:description', content: 'Deterministic governance, execution contracts, evidence engine, and behavioral evaluations for coding harnesses.'},
    ],
    navbar: {
      title: 'Rapid OS',
      items: [
        {to: '/', label: 'Home', position: 'left'},
        {to: '/installation', label: 'Installation', position: 'left'},
        {to: '/getting-started', label: 'Getting Started', position: 'left'},
        {to: '/guides/shortcuts', label: 'Shortcuts', position: 'left'},
        {to: '/guides/modes', label: 'Modes', position: 'left'},
        {to: '/cookbooks/policies-and-contracts', label: 'Cookbooks', position: 'left'},
        {to: '/governance-loop', label: 'Governance v3', position: 'left'},
        {to: '/cli', label: 'CLI', position: 'left'},
        {type: 'localeDropdown', position: 'right'},
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
          title: 'Learn',
          items: [
            {label: 'What is Rapid OS', to: '/concepts/what-is-rapid-os'},
            {label: 'Why Rapid OS', to: '/concepts/why-rapid-os'},
            {label: 'Installation', to: '/installation'},
            {label: 'Getting Started', to: '/getting-started'},
            {label: 'Shortcuts', to: '/guides/shortcuts'},
            {label: 'Engineering Modes', to: '/guides/modes'},
            {label: 'Use Cases', to: '/guides/use-cases'},
          ],
        },
        {
          title: 'Governance and Practice',
          items: [
            {label: 'Policies and Contracts', to: '/cookbooks/policies-and-contracts'},
            {label: 'Capabilities and Profiles', to: '/cookbooks/harness-profiles'},
            {label: 'Evidence Engine', to: '/cookbooks/evidence-engine'},
            {label: 'Behavioral Evals', to: '/cookbooks/behavioral-evaluations'},
            {label: 'CI/CD Integration', to: '/guides/ci-cd-integration'},
          ],
        },
        {
          title: 'Reference',
          items: [
            {label: 'CLI', to: '/cli'},
            {label: 'RAPIDxxx Diagnostics', to: '/troubleshooting/diagnostics'},
            {label: 'v3 Architecture', to: '/architecture/rapid-os-v3'},
            {label: 'Orchestration Architecture', to: '/architecture/orchestration'},
            {label: 'Release v3.1.1', to: '/release-v3.1.1'},
          ],
        },
        {
          title: 'Project',
          items: [
            {label: 'Repository', href: 'https://github.com/alyconr/Rapid-OS'},
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
