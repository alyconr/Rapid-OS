# 🔥 TECH STACK: FIREBASE (BaaS)
- **Backend como servicio:** Firebase (Cloud Firestore, Authentication, Cloud Storage, Cloud Functions y Hosting).
- **Datos:** colecciones y documentos de Firestore; las consultas dictan el modelo y los índices viven en el repositorio.
- **Seguridad de datos:** reglas de Firestore y de Storage con denegación por defecto (`allow read, write: if false;`), probadas en el emulador con `@firebase/rules-unit-testing`; App Check activo en producción.
- **Credenciales:** la configuración web (incluida su `apiKey`) identifica el proyecto y no es secreta; las credenciales de cuenta de servicio y el Admin SDK solo existen en el servidor.
- **Funciones en servidor:** Cloud Functions for Firebase (Node.js 20 o 22) en `functions/src/<módulo>/`; el código TypeScript se compila a `functions/lib/`.
- **Desarrollo local:** Firebase CLI y Emulator Suite (`firebase emulators:start`, `firebase emulators:exec`); lo ejecuta la persona. Los emuladores no son para producción.
- **Testing:** el comando de test del proyecto es el del frontend (`gate.tests` pasa sin Java ni emuladores). Las reglas se prueban con `firebase emulators:exec "<gestor> run test:rules"` en el job de CI y, en local, lo ejecuta la persona.
- **Cadena de suministro:** el gestor de paquetes del proyecto no instala versiones publicadas hace menos de siete días: con pnpm, los ajustes de `pnpm-workspace.yaml` de la plantilla del frontend; con npm, `.npmrc` con `min-release-age=7` (días; npm 11.10 o posterior); con Yarn, `.yarnrc.yml` con `npmMinimalAgeGate: "7d"` (Yarn 4.10 o posterior). Sin ellos semgrep `p/owasp-top-ten` falla el workflow de seguridad. Fuentes: https://docs.npmjs.com/cli/v11/using-npm/config#min-release-age, https://yarnpkg.com/configuration/yarnrc#npmMinimalAgeGate.
- **Version Control:** Git.
<!-- Fuentes (documentación oficial, verificadas al escribir esta plantilla):
  https://firebase.google.com/docs/emulator-suite/install_and_configure
  https://firebase.google.com/docs/rules/unit-tests
  https://firebase.google.com/docs/firestore/security/get-started
  https://firebase.google.com/docs/app-check
  https://firebase.google.com/docs/admin/setup
  https://firebase.google.com/docs/projects/api-keys
  https://firebase.google.com/docs/functions/get-started
  https://firebase.google.com/docs/functions/typescript -->
