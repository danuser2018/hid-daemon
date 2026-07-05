# Registro de cambios

Todos los cambios notables de este proyecto se documentan en este fichero.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## Guía de uso

Cada versión se documenta bajo su número de versión y fecha de publicación.
Los cambios se agrupan en las siguientes categorías:

- **Añadido** — nuevas funcionalidades.
- **Cambiado** — cambios en funcionalidades existentes.
- **Obsoleto** — funcionalidades que serán eliminadas en versiones futuras.
- **Eliminado** — funcionalidades eliminadas en esta versión.
- **Corregido** — corrección de errores.
- **Seguridad** — correcciones de vulnerabilidades.

---

## [1.0.0] - 2026-07-05 

### Añadido

- Implementación de la primera versión del daemon de eventos de teclas físicas (`hid-daemon`).
- Soporte para mapeos de teclas físicas utilizando la biblioteca `evdev` y ejecución de comandos con subprocesos.
- Soporte para modos de bindings `TOGGLE` y `PTT` (Push-To-Talk).
- Manejo resiliente ante fallos de conexión de dispositivos con reintentos y backoff.
- Validación de configuración robusta y soporte de sobreescritura con variables de entorno (`HID_DEVICE_PATH`, `HID_DEVICE_NAME`, `HID_RECONNECT_DELAY_S`).
- Unidad de servicio systemd de usuario (`systemd/hid-daemon.service`) y flujo de pruebas continuas (`.github/workflows/pr-tests.yml`).
- Fichero `CONTRIBUTING.md` con el flujo de trabajo Trunk Based Development,
  convenciones de commits, guía de Pull Requests y buenas prácticas para
  desarrollo asistido con IA.
- Fichero `CHANGELOG.md` con el formato Keep a Changelog v1.1.0 en castellano.

---

<!-- Plantilla para nuevas versiones:

## [X.Y.Z] - AAAA-MM-DD

### Añadido
-

### Cambiado
-

### Obsoleto
-

### Eliminado
-

### Corregido
-

### Seguridad
-

-->

[Sin publicar]: https://github.com/danuser2018/hid-daemon/compare/HEAD...HEAD
