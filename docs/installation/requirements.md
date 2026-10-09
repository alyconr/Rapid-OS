---
title: Requisitos del sistema
description: Prerrequisitos de software, versiones de Python y dependencias opcionales de Rapid OS.
---

# Requisitos del sistema

Rapid OS fue diseñado bajo una filosofía de mínima sobrecarga técnica: el núcleo de gobernanza no tiene dependencias runtime obligatorias de terceros y corre sobre la biblioteca estándar de Python.

---

## Prerrequisitos obligatorios

Para ejecutar el CLI de Rapid OS en cualquier sistema operativo necesitas:

| Requisito | Versión mínima | Notas |
| :--- | :--- | :--- |
| **Python** | `3.10` o superior | Probado exhaustivamente en CI bajo Python `3.10`, `3.11`, `3.12` y `3.13`. |
| **Git** | `2.20` o superior | Utilizado para operaciones de control de versiones e inspección de repositorio. |
| **Terminal** | Consola estándar | PowerShell 5.1+ o 7+ en Windows; Bash o Zsh en Linux/macOS. |

### Verificación de requisitos

Antes de instalar, comprueba tus herramientas en la terminal:

```bash
python --version   # o python3 --version
git --version
```

Ambos comandos deben responder satisfactoriamente con versiones compatibles.

---

## Dependencias opcionales

:::note No requeridas para el CLI principal
El ciclo de gobernanza v3 (`scan`, `spec`, `context`, `policy`, `run`, `harness`, `evidence`, `eval`, `validate`) **NO** requiere Node.js ni npm.
:::

Existen únicamente dos escenarios donde herramientas adicionales pueden ser requeridas:

1. **Gestión remota de skills (`rapid skill add`):**
   Si utilizas la funcionalidad heredada de agregar skills de terceros mediante npx, se requiere tener disponible `node` (Node.js 18+) y `npx` en tu PATH.
2. **Desarrollo y compilación del portal de documentación (Docusaurus):**
   Si deseas clonar y compilar localmente este portal de documentación ubicado en `website/`, requieres Node.js 20+ y `npm`.

---

## Conectividad y permisos

- **Conectividad a Internet:** Requerida únicamente durante la descarga inicial del repositorio/paquete. Todo el ciclo de gobernanza posterior opera **100% offline**, sin realizar llamadas a APIs en la nube.
- **Permisos de usuario:** No se requieren privilegios de administrador (`root` o `Administrator`) para instalar ni usar Rapid OS. Se instala en el directorio de usuario (`$HOME/.rapid-os`).
