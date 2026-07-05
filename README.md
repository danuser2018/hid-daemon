# hid-daemon

El **HID Daemon** (`hid-daemon`) es un servicio nativo de Linux para el ecosistema Nova-2 que actúa como controlador de bajo nivel para capturar eventos de entrada desde dispositivos HID físicos (como botones USB, pedales o interruptores de hardware dedicados) y ejecutar comandos lógicos configurables por el usuario.

Este servicio permite asociar pulsaciones de botones físicos directamente a acciones del asistente (por ejemplo, `mic-start` y `mic-stop` para controlar la grabación de voz), funcionando de forma autónoma sin depender de los entornos de escritorio gráfico o gestores de atajos de teclado complejos.

---

## Características

- **Acceso directo mediante `evdev`**: Monitoreo de dispositivos de entrada a bajo nivel en Linux (`/dev/input/event*`).
- **Modos de funcionamiento**:
  - `TOGGLE`: Ejecuta un comando al presionar el botón por primera vez y otro al presionarlo por segunda vez (alternando el estado interno).
  - `PTT` (Push-To-Talk): Ejecuta un comando al mantener presionado el botón y otro al liberarlo.
- **Resiliencia ante desconexiones**: Bucle automático de reconexión si el dispositivo USB se desconecta físicamente.
- **Filtrado de repetición de teclas**: Ignora eventos duplicados (`value=2` en el kernel) cuando se mantiene pulsado el dispositivo.
- **Seguridad**: Ejecutado en el espacio de usuario mediante `systemd --user` sin necesidad de permisos de superusuario (`root`), requiriendo únicamente pertenecer al grupo `input`.

---

## Requisitos previos

Para poder leer los eventos de entrada directamente sin privilegios de root, el usuario que ejecuta el daemon debe pertenecer al grupo de sistema `input`:

```bash
sudo usermod -aG input $USER
```

*Nota: Es necesario reiniciar o volver a iniciar sesión para que el cambio de grupo surta efecto.*

---

## Configuración

La configuración se lee desde un archivo YAML y se puede sobrescribir selectivamente mediante variables de entorno (conforme a **ADR-010**).

### Archivo YAML (`config/hid-daemon.yaml`)

El archivo de configuración principal se define con el siguiente formato:

```yaml
# Ruta directa del dispositivo (ej: "/dev/input/event0")
device_path: null

# Nombre del dispositivo a buscar si device_path es null
device_name: "USB Foot Switch"

# Tiempo de reintento de conexión (en segundos)
reconnect_delay_s: 5.0

# Definición de atajos y comandos asociados
bindings:
  KEY_F9:
    mode: "TOGGLE"                 # "TOGGLE" o "PTT"
    press: "mic-start"             # Comando a ejecutar al presionar
    release: "mic-stop"            # Comando a ejecutar al liberar (opcional en TOGGLE)
```

### Variables de Entorno

Se pueden configurar las siguientes variables de entorno para anular los valores del archivo YAML:

| Variable | Tipo | Descripción |
|---|---|---|
| `HID_CONFIG_PATH` | String | Ruta absoluta al archivo YAML de bindings (por defecto busca en el directorio padre de `src`). |
| `HID_DEVICE_PATH` | String | Sobrescribe la ruta del dispositivo a monitorear. |
| `HID_DEVICE_NAME` | String | Sobrescribe el nombre del dispositivo a buscar. |
| `HID_RECONNECT_DELAY_S` | Float | Sobrescribe el intervalo de reconexión. |

---

## Gestión del Servicio

El daemon se despliega como servicio de usuario de systemd.

```bash
# Ver estado del servicio
systemctl --user status hid-daemon

# Iniciar / Detener / Reiniciar el servicio
systemctl --user start hid-daemon
systemctl --user stop hid-daemon
systemctl --user restart hid-daemon

# Ver los logs del servicio en tiempo real
journalctl --user -u hid-daemon -f
```
