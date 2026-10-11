# Laboratorios Prácticos de RAPID OS

Bienvenido a la sección de **Laboratorios Prácticos (Hands-on Tutorials & Reproducible Labs)** de RAPID OS v3.

Esta colección de tutoriales técnicos está diseñada para aprender a gobernar flujos de desarrollo asistidos por IA mediante ejercicios reales, código ejecutable y verificación estricta de evidencia determinista.

---

## Filosofía de Aprendizaje: Product Truth & External Execution

En RAPID OS distinguimos de forma absoluta dos actores:

1. **RAPID OS (El Plano de Gobernanza):** Gobierna contratos de ejecución (`ExecutionContract`), estados versionados (`RunState`), resolución declarada de capacidades de herramientas (`HarnessProfile`), ingesta append-only de evidencias verificadas (`RunEvidence`) y evaluación determinista de resultados (`EvaluationReport`). RAPID OS **no ejecuta de forma autónoma a los modelos LLM ni modifica código por sí mismo**.
2. **Coding Harness o Desarrollador (El Plano de Ejecución Externa):** Edita código en el disco, invoca subagentes, ejecuta pruebas unitarias en la terminal e interactúa con herramientas de desarrollo dentro de los límites y permisos de su entorno.

---

## Progresión Pedagógica

Los laboratorios siguen una ruta progresiva desde los fundamentos del Governance Loop hasta escenarios avanzados de refactorización y endurecimiento:

| Laboratorio | Nivel | Modo | Foco Principal | Ejemplo de Código |
|---|---|---|---|---|
| [1. Primer Proyecto Gobernado](first-governed-project.md) | Principiante | `feature` | Governance Loop completo (de `init` a `eval` y `validate`) | [`examples/first-governed-project`](https://github.com/alyconr/Rapid-OS/tree/main/examples/first-governed-project) |
| [2. Feature Engineering](feature-lab.md) | Intermedio | `feature` | Criterios de aceptación, validación de disponibilidad y gates de tests | [`examples/feature-lab`](https://github.com/alyconr/Rapid-OS/tree/main/examples/feature-lab) |
| [3. Bugfix Engineering](bugfix-lab.md) | Intermedio | `bugfix` | Captura de baseline, reproducción de defecto y tests de regresión | [`examples/bugfix-lab`](https://github.com/alyconr/Rapid-OS/tree/main/examples/bugfix-lab) |
| [4. Refactor Engineering](refactor-lab.md) | Avanzado | `refactor` | Desacoplamiento arquitectónico preservando contratos de API pública | [`examples/refactor-lab`](https://github.com/alyconr/Rapid-OS/tree/main/examples/refactor-lab) |
| [5. Hardening & Security](hardening-lab.md) | Avanzado | `hardening` | Elevación de riesgo, mitigación defensiva y aislamiento de workspace | [`examples/hardening-lab`](https://github.com/alyconr/Rapid-OS/tree/main/examples/hardening-lab) |
| [6. Research & Spikes](research-lab.md) | Intermedio | `research` | Spikes exploratorios sin sobreingeniería con evidencia empírica | [`examples/research-lab`](https://github.com/alyconr/Rapid-OS/tree/main/examples/research-lab) |

---

## Estructura Canónica de Cada Laboratorio

Cada laboratorio en esta sección implementa una estructura idéntica y verificable:
- **Overview:** Contexto, problema y objetivos.
- **Learning Outcomes:** Capacidades concretas adquiridas.
- **Initial State:** Estado del repositorio base antes del cambio.
- **Engineering Requirements:** Requerimientos técnicos y criterios de aceptación.
- **Guided Procedure:** Comandos del CLI y explicaciones paso a paso.
- **Expected Artifacts:** Archivos generados bajo `.rapid-os/`.
- **External Execution:** Modificaciones reales del código o suite de tests realizadas externamente.
- **Evidence Collection:** Registro de evidencias canónicas con validación de hash SHA-256.
- **Evaluation:** Ejecución del evaluador determinista (`rapid eval run`) e interpretación del veredicto.
- **Validation:** Validación de integridad con `rapid validate`.
- **Troubleshooting & Assessment:** Diagnóstico de errores comunes y criterios de éxito.
