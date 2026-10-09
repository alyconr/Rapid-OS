---
title: Casos de uso
description: Escenarios prácticos en los que Rapid OS aporta contexto, gobernanza y evidencia.
---

# Casos de uso

Rapid OS es útil cuando el valor no está solo en “generar código”, sino en poder demostrar **qué se pidió, bajo qué restricciones se ejecutó y qué evidencia existe del resultado**.

## 1. Implementar una feature con contexto controlado

Un equipo necesita agregar una funcionalidad sin permitir que el agente improvise arquitectura o reglas de negocio.

Flujo recomendado:

```bash
rapid scan --write
rapid spec create --title "Nueva feature" --mode feature --status ready
rapid context --spec nueva-feature --harness codex --manifest
rapid run create --spec nueva-feature --harness codex
```

El valor de Rapid OS está en fijar una Spec, compilar contexto con procedencia y crear un contrato de ejecución antes de que el harness cambie código.

## 2. Refactorizar un sistema legacy

En un sistema heredado, `rapid init` y `rapid scan` ayudan a separar:

- señales detectadas del repositorio;
- reglas confirmadas por el equipo;
- estándares que el agente debe respetar;
- alcance explícito de la refactorización.

Esto reduce el riesgo de que el agente imite patrones obsoletos solo porque existen en el código actual.

## 3. Cambios de alto riesgo

Una migración de esquema, autenticación, infraestructura o seguridad puede elevar el riesgo a `high` o `critical`.

Rapid OS puede requerir:

- workspace aislado;
- baseline;
- revisión manual;
- pruebas;
- security review;
- migration review;
- verificación final.

El run no puede avanzar ignorando las precondiciones del contrato.

## 4. Equipos que usan varios coding harnesses

Rapid OS modela profiles para `codex`, `claude`, `cursor`, `vscode`, `antigravity` y harnesses personalizados.

Esto permite responder:

> ¿Este harness declara soporte para todas las capabilities que exige este run?

La resolución puede ser `compatible`, `incompatible` o `unresolved`.

## 5. Evidencia para CI o procesos de revisión

Después de que una herramienta externa ejecuta pruebas o revisiones, sus resultados pueden registrarse como evidencia:

```bash
rapid evidence add --run checkout-r1-run-001 --input test-evidence.json
rapid evidence verify --run checkout-r1-run-001
rapid eval run --run checkout-r1-run-001 --require-pass
```

Rapid OS valida binding, secuencia, digests, tamaños y reglas semánticas antes de emitir un veredicto.

## 6. Context engineering reutilizable

Los flujos heredados continúan siendo útiles para:

- generar reglas de agentes;
- mantener estándares del proyecto;
- preparar MCP para editores;
- instalar skills;
- registrar referencias visuales;
- generar guías de despliegue;
- crear prompts estructurados.

## Cuándo Rapid OS no es necesario

Puede ser excesivo para tareas exploratorias muy pequeñas donde no se necesita trazabilidad, política ni evidencia. Su mayor valor aparece cuando la organización necesita **consistencia, control, repetibilidad y auditoría**.
