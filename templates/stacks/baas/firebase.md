# 🔥 TECH STACK: FIREBASE (BaaS)
- **Backend como servicio:** Firebase (Cloud Firestore, Authentication, Cloud Storage, Cloud Functions y Hosting).
- **Datos:** colecciones y documentos de Firestore; las consultas dictan el modelo y los índices viven en el repositorio.
- **Seguridad de datos:** reglas de Firestore y de Storage con denegación por defecto (`allow read, write: if false;`), probadas en el emulador con `@firebase/rules-unit-testing`; App Check activo en producción.
- **Credenciales:** la configuración web (incluida su `apiKey`) identifica el proyecto y no es secreta; las credenciales de cuenta de servicio y el Admin SDK solo existen en el servidor.
- **Funciones en servidor:** Cloud Functions for Firebase (Node.js 20 o 22) en `functions/src/<módulo>/`; el código TypeScript se compila a `functions/lib/`.
- **Desarrollo local:** Firebase CLI y Emulator Suite (`firebase emulators:start`, `firebase emulators:exec`); lo ejecuta la persona. Los emuladores no son para producción.
- **Testing:** `firebase emulators:exec "<test del frontend>"`, que levanta los emuladores y corre las pruebas de reglas y del frontend.
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
