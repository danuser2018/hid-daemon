# Documento de Refinamiento: Primera Implementación del HID Daemon

- **Documento de Origen**: [implementation.md](file:///home/danuser2018/workspace/hid-daemon/doc/features/implementation.md)
- **Estado**: Refinado / Listo para revisión de DoR

---

## 1. Resumen y Contexto de Negocio

El **HID Daemon** (`hid-daemon`) es un nuevo servicio nativo para Linux que forma parte del ecosistema Nova-2. Su objetivo es actuar como un controlador de bajo nivel que escucha eventos de entrada desde dispositivos HID físicos (como botones USB, pedales o teclas de hardware dedicadas) y ejecuta comandos del sistema configurables por el usuario.

Específicamente, este daemon mapea pulsaciones de un botón físico a comandos lógicos del sistema (por ejemplo, `mic-start` y `mic-stop` para iniciar o detener la grabación en `mic-daemon`), permitiendo la interacción por voz sin depender de gestores de atajos de teclado del entorno gráfico (como `sxhkd`, GNOME o KDE Custom Shortcuts). Esto resulta fundamental para despliegues empotrados ("headless") o entornos donde se prefiera un botón físico dedicado, manteniendo al mismo tiempo la flexibilidad original de ejecutar cualquier comando.

---

## 2. Análisis de Servicios e Impacto

| Servicio | Tipo de Cambio | Descripción del Impacto |
| :--- | :--- | :--- |
| `hid-daemon` | **[NEW]** | Creación completa del servicio: estructura de código en Python, configuración mediante archivo YAML y variables de entorno, sistema de escucha con `evdev`, ejecución de comandos con subprocesos, tests unitarios con mocks y flujo de integración continua en GitHub Actions. |
| `home-assistant` | **[MODIFY]** | Integración del instalador (`scripts/install.sh`), desinstalador (`scripts/uninstall.sh`), salud (`scripts/healthcheck.sh`), configuración centralizada (`config/hid-daemon.env` y `config/hid-daemon.yaml.example`) y documentación global del sistema. |
| Otros servicios de Nova | **Ninguno** | Este daemon es autónomo y se comunica a través del sistema operativo ejecutando comandos, por lo que no altera el código de otros microservicios. |

---

## 3. Especificación de Comportamiento (Criterios de Aceptación)

### Escenario 1: Alternar ejecución de comando mediante pulsación en modo Toggle
```gherkin
Scenario: Toggle command execution using physical button press
  Given that the daemon is running with key bindings configured from HID_CONFIG_PATH
  And a binding is configured for key HID_KEY_CODE with mode = "TOGGLE"
  And the press command is configured as "mic-start"
  And the release command is configured as "mic-stop"
  And the HID device is connected
  And the current toggle state for HID_KEY_CODE is inactive
  When the user presses the button with code HID_KEY_CODE (event value = 1)
  Then the daemon must execute the command "mic-start"
  And update the internal toggle state to active
  When the user presses the button with code HID_KEY_CODE again (event value = 1)
  Then the daemon must execute the command "mic-stop"
  And update the internal toggle state to inactive
```

### Escenario 2: Ejecutar comandos al pulsar y soltar en modo Push-to-Talk (PTT)
```gherkin
Scenario: Execute commands on press and release (Push-to-Talk)
  Given that the daemon is running with key bindings configured from HID_CONFIG_PATH
  And a binding is configured for key HID_KEY_CODE with mode = "PTT"
  And the press command is configured as "mic-start"
  And the release command is configured as "mic-stop"
  And the HID device is connected
  When the user presses and holds the button with code HID_KEY_CODE (event value = 1)
  Then the daemon must execute the command "mic-start"
  When the user releases the button (event value = 0)
  Then the daemon must execute the command "mic-stop"
```

### Escenario 3: Dispositivo HID no disponible al arrancar
```gherkin
Scenario: HID device is missing at startup
  Given that the daemon starts up
  And the device specified by HID_DEVICE_PATH or HID_DEVICE_NAME is not found
  Then the daemon must log a warning message
  And the daemon must NOT crash
  And it must enter a reconnection loop, retrying every HID_RECONNECT_DELAY_S seconds
  When the device is later connected and detected
  Then the daemon must successfully connect to it and start listening to events
```

### Escenario 4: Dispositivo HID se desconecta durante el funcionamiento
```gherkin
Scenario: HID device is disconnected during operation
  Given that the daemon is actively listening to a connected HID device
  When the device is disconnected (raising an OSError or FileNotFoundError)
  Then the daemon must log the error
  And it must stop listening to events
  And it must enter the reconnection loop, retrying every HID_RECONNECT_DELAY_S seconds
```

---

## 4. Diseño Técnico y Contratos

### Estructura de Directorios (English)

Para mantener total homogeneidad con `mic-daemon` y `speaker-watchdog`, se establece la siguiente estructura en `hid-daemon`:

```text
hid-daemon/
├── README.md                    # Documentación del proyecto
├── CONTRIBUTING.md              # Normas de contribución y flujo de trabajo
├── CHANGELOG.md                 # Historial de cambios
├── LICENSE                      # Licencia del proyecto
├── .gitignore                   # Filtro de Git
├── requirements.txt             # Dependencias del proyecto (incluye evdev y PyYAML)
│
├── .github/
│   └── workflows/
│       └── pr-tests.yml         # GitHub Action para ejecutar tests en PRs
│
├── config/
│   └── hid-daemon.yaml.example  # Plantilla de ejemplo para la configuración de bindings
│
├── src/
│   ├── __init__.py
│   ├── config.py                # Cargador y validador de configuración (YAML + Env overrides)
│   ├── executor.py              # Ejecutor de comandos del sistema (subprocess)
│   ├── listener.py              # Lógica de escucha de evdev y reconexión
│   └── hid_daemon.py            # Punto de entrada principal, mapeo de eventos y bucle del servicio
│
├── systemd/
│   └── hid-daemon.service       # Fichero de unidad systemd --user
│
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_executor.py
    ├── test_listener.py
    └── test_hid_daemon.py
```

### Configuración (Variables de Entorno y YAML)

La configuración principal de bindings se define en el archivo centralizado `config/hid-daemon.yaml` dentro de `home-assistant`. Se pueden sobrescribir ciertos parámetros mediante variables de entorno en `config/hid-daemon.env` (conforme a **ADR-010**).

#### Formato del archivo YAML (`config/hid-daemon.yaml`):
```yaml
device_path: null                  # Ruta directa del dispositivo (ej: "/dev/input/event0")
device_name: "USB Foot Switch"     # Nombre a buscar si device_path no se define
reconnect_delay_s: 5.0             # Tiempo de espera antes de reconectar

bindings:
  KEY_F9:
    mode: "TOGGLE"                 # "TOGGLE" o "PTT"
    press: "mic-start"             # Comando a ejecutar al presionar
    release: "mic-stop"            # Comando a ejecutar al liberar (opcional en TOGGLE)
```

#### Variables de Entorno en `config/hid-daemon.env`:
| Variable de Entorno | Tipo | Valor por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `HID_CONFIG_PATH` | String | `$PROJECT_DIR/config/hid-daemon.yaml` | Ruta absoluta al archivo YAML de bindings y configuración. |
| `HID_DEVICE_PATH` | String | `None` | Sobrescribe `device_path` del YAML (ej: `/dev/input/event0`). |
| `HID_DEVICE_NAME` | String | `None` | Sobrescribe `device_name` del YAML (ej: `USB Foot Switch`). |
| `HID_RECONNECT_DELAY_S` | Float | `None` | Sobrescribe `reconnect_delay_s` del YAML. |

### Contratos Lógicos de Clases y Métodos (English)

#### Clases de Configuración (`src/config.py`):
```python
from pathlib import Path
from typing import Dict, Any

class BindingConfig:
    def __init__(self, mode: str, press_command: str | None, release_command: str | None):
        self.mode = mode  # "TOGGLE" or "PTT"
        self.press_command = press_command
        self.release_command = release_command

class Config:
    config_path: Path
    device_path: str | None
    device_name: str | None
    reconnect_delay_s: float
    bindings: Dict[str, BindingConfig]  # Maps key names or codes to their binding configuration

    def load_from_yaml(self) -> None:
        """Loads and parses settings and bindings from YAML file."""
        pass

    def apply_env_overrides(self) -> None:
        """Applies environment variables values over YAML loaded settings."""
        pass
```

#### Clase `CommandExecutor` (`src/executor.py`):
```python
class CommandExecutor:
    def execute(self, command: str) -> bool:
        """
        Executes a system command as a subprocess.
        Returns True if successful (exit status 0), False otherwise.
        """
        pass
```

#### Clase `DeviceListener` (`src/listener.py`):
```python
from typing import Iterator
from evdev import InputDevice

class DeviceListener:
    def __init__(self, device_path: str | None, device_name: str | None):
        self.device_path = device_path
        self.device_name = device_name
        self.device: InputDevice | None = None

    def find_device_by_name(self) -> str | None:
        """Scans /dev/input/event* and returns the path of the device matching device_name."""
        pass

    def connect(self) -> bool:
        """
        Attempts to connect to the configured HID device.
        Returns True if successful, False otherwise.
        """
        pass

    def read_events(self) -> Iterator[Any]:
        """
        Yields input events from the device.
        Raises OSError or FileNotFoundError if the device is disconnected.
        """
        pass
```

---

## 5. Casos de Borde y Manejo de Errores

1.  **Falta de permisos sobre `/dev/input/event*`**:
    - El daemon se ejecuta como servicio de usuario (`systemd --user`). Para leer los dispositivos de entrada directamente, el usuario físico de Linux debe pertenecer al grupo de sistema `input`.
    - **Solución**: Si el daemon encuentra un error de permisos (`PermissionError`), debe loguear un mensaje de error crítico indicando que añada al usuario al grupo `input` y terminar. Además, el script de instalación (`install.sh`) verificará proactivamente si el usuario pertenece al grupo y emitirá instrucciones claras al respecto.
2.  **Múltiples eventos de tecla duplicados (Key Repeat)**:
    - Cuando se mantiene presionada una tecla, el kernel de Linux puede generar eventos repetidos (`value=2`).
    - **Solución**: La lógica en `hid_daemon.py` debe ignorar los eventos con `value=2` para evitar ejecuciones repetidas e indeseadas de los comandos.
3.  **Desconexión física / Hotplug**:
    - Si el dispositivo USB se desconecta físicamente durante la ejecución, la lectura de eventos lanzará un `OSError` o `FileNotFoundError`.
    - **Solución**: El daemon debe capturar estas excepciones, detener el hilo de escucha, loguear un aviso y entrar en el bucle de reconexión `connect()` reintentando cada `HID_RECONNECT_DELAY_S` segundos.
4.  **Búsqueda por nombre ambiguo**:
    - Si `HID_DEVICE_NAME` coincide con más de un dispositivo de entrada en `/dev/input/`.
    - **Solución**: Se seleccionará el primer dispositivo que coincida con el nombre y se registrará un aviso en los logs indicando la ruta física seleccionada.
5.  **Fallo en la ejecución de comandos**:
    - Si el comando configurado falla en ejecución o no existe en el PATH (ej: script `mic-start` no disponible).
    - **Solución**: El `CommandExecutor` debe capturar fallos de ejecución, registrar el error en logs y continuar funcionando de manera ininterrumpida sin propagar excepciones que cuelguen el daemon.

---

## 6. Estrategia de Testing

-   **Tests de Configuración (`tests/test_config.py`)**:
    - Validar la lectura y parseo del fichero YAML.
    - Validar la carga de variables de entorno y que sobrescriban correctamente los campos del YAML.
    - Validar restricciones lógicas (ej. que los modos declarados solo sean `TOGGLE` o `PTT`).
-   **Tests del Ejecutor (`tests/test_executor.py`)**:
    - Probar la ejecución correcta de comandos exitosos e inexistentes usando mocks de `subprocess`.
-   **Tests del Listener (`tests/test_listener.py`)**:
    - Usar mocks sobre `evdev.InputDevice` y `evdev.list_devices` para simular dispositivos físicos.
    - Probar la detección y filtrado de eventos.
-   **Tests del Bucle del Daemon (`tests/test_hid_daemon.py`)**:
    - Simular el flujo completo del daemon (inicialización, lectura de eventos, mapeo de acciones y ejecución de comandos) inyectando stubs y mocks.
    - Validar la respuesta correcta del daemon ante desconexiones físicas (`OSError`).

---

## 7. Plan de Implementación

-   `[ ]` **Tarea 1: Estructuración y Entorno de Desarrollo**
    - Crear `requirements.txt` declarando `evdev>=1.7.0`, `PyYAML>=6.0` y dependencias de test (`pytest>=8.0.0`, `pytest-cov>=5.0.0`).
-   `[ ]` **Tarea 2: Documentación Base y Configuración del Servicio (README.md)**
    - Rellenar el `README.md` del servicio en castellano, especificando la arquitectura de control, configuración mediante YAML y variables de entorno, y la necesidad del grupo `input`.
    - Crear `config/hid-daemon.yaml.example` en el repositorio.
-   `[ ]` **Tarea 3: Implementación del Cargador de Configuración**
    - Implementar `src/config.py` encargada de leer el YAML y aplicar overrides de variables de entorno, junto con sus tests en `tests/test_config.py`.
-   `[ ]` **Tarea 4: Implementación del Ejecutor de Comandos**
    - Desarrollar `src/executor.py` que abstraiga la llamada a comandos del sistema mediante `subprocess`.
    - Crear `tests/test_executor.py` para verificar el manejo de códigos de salida.
-   `[ ]` **Tarea 5: Implementación del Listener y Búsqueda de Dispositivos**
    - Implementar `src/listener.py` encapsulando la librería `evdev` y la lógica de mapeo por nombre de dispositivo.
    - Desarrollar `tests/test_listener.py` mockeando el acceso al hardware.
-   `[ ]` **Tarea 6: Bucle del Daemon y Mapeador de Eventos**
    - Implementar `src/hid_daemon.py` con el mapeo de eventos, gestión de reconexiones limpias y control de señales POSIX (`SIGTERM` para apagados ordenados).
    - Desarrollar `tests/test_hid_daemon.py` cubriendo los flujos de ejecución en modos TOGGLE y PTT.
-   `[ ]` **Tarea 7: Fichero de Servicio Systemd**
    - Crear `systemd/hid-daemon.service` configurado como servicio de usuario systemd que se ejecute en el entorno virtual (`venv`) apuntando a `src/hid_daemon.py` y cargando variables desde `$PROJECT_DIR/config/hid-daemon.env`.
-   `[ ]` **Tarea 8: Automatización en Integración Continua (GitHub Action)**
    - Crear `.github/workflows/pr-tests.yml` configurando un runner de Ubuntu, instalando dependencias y ejecutando la suite de pruebas.
-   `[ ]` **Tarea 9: Registro en Changelog**
    - Registrar la nueva funcionalidad bajo la sección `[Sin publicar]` de `CHANGELOG.md`.
-   `[ ]` **Tarea 10: Integración en el Repositorio Central `home-assistant`**
    - Crear el archivo de variables `config/hid-daemon.env` y el archivo de mapeos predeterminados `config/hid-daemon.yaml.example`.
    - Modificar `scripts/install.sh` and `scripts/uninstall.sh` para soportar la creación de entornos virtuales y el control del servicio systemd de `hid-daemon`. Añadir verificación interactiva sobre el grupo `input` del usuario.
    - Modificar `scripts/healthcheck.sh` para verificar el estado de salud de `hid-daemon` (si está instalado y habilitado).
-   `[ ]` **Tarea 11: Documentación Global del Sistema**
    - Actualizar `docs/architecture.md` (Plano de Hardware), `docs/services.md` (Catálogo de Servicios) y `docs/installation.md` para incluir `hid-daemon` como un servicio de host opcional para botones físicos dedicados.
-   `[ ]` **Tarea 12: Creación de ADR-012 y Sincronización de Referencias**
    - Redactar `docs/adr/adr-012-integracion-hid-daemon.md` documentando formalmente la decisión arquitectónica.
    - Actualizar la sección de Referencias de las skills transversales afectadas (`service-responsibilities`, `system-deployment` y `feature-refinement`) con el enlace al nuevo ADR.
