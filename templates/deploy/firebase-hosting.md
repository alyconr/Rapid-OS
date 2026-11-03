# Despliegue en Firebase Hosting

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- **Frontend estático o SPA**: `firebase init hosting` (desde la raíz del proyecto) y `firebase deploy --only hosting`. La carpeta que se despliega es `public` en `firebase.json` (por defecto se llama `public`; para un SPA con Vite pon la carpeta de salida del build). Un SPA necesita la reescritura `"rewrites": [{"source": "**", "destination": "/index.html"}]`, que sirve `index.html` para las rutas que no existen.
- **Funciones**: `firebase deploy --only functions` despliega las Cloud Functions de `functions/`; las reglas, `firebase deploy --only firestore`.
- **Aplicaciones con renderizado en servidor** (Next.js o Angular con SSR): Firebase recomienda App Hosting para las aplicaciones full-stack; Hosting clásico es para contenido estático.

## Configuración y secretos
- La configuración web de Firebase (incluida su `apiKey`) identifica el proyecto y no es un secreto: la protección son las reglas de seguridad y App Check. Puede ir en la configuración del frontend.
- Las credenciales de cuenta de servicio y el Admin SDK son solo del servidor: en entornos de Google usa las credenciales predeterminadas de la aplicación; si usas un archivo de clave, `GOOGLE_APPLICATION_CREDENTIALS` y guárdalo de forma segura, fuera del repositorio.
- Despliegue desde GitHub: `firebase init hosting:github` crea la cuenta de servicio, cifra su clave y la sube como secreto del repositorio.

## Servicios gestionados
| Rol | Opción |
|---|---|
| database | Cloud Firestore (documentos) |
| auth | Firebase Authentication |
| storage | Cloud Storage for Firebase |
| cache, queue, stream | Sin servicio gestionado documentado en esta guía: fuera de Firebase |

## Verificación y reversión
- Antes de producir, prueba reglas y funciones en el Emulator Suite (`firebase emulators:start`); los emuladores no son para producción.
- Comprueba el sitio y las reglas tras el despliegue. Reversión: vuelve a desplegar la versión anterior del contenido y de los archivos de reglas desde el repositorio.

## Fuentes oficiales
- https://firebase.google.com/docs/hosting/quickstart
- https://firebase.google.com/docs/hosting/full-config
- https://firebase.google.com/docs/hosting/github-integration
- https://firebase.google.com/docs/functions/get-started
- https://firebase.google.com/docs/admin/setup
- https://firebase.google.com/docs/projects/api-keys
