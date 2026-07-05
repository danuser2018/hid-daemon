# Especificación de Requisitos
# Nova HID Daemon
**Versión:** 1.0  
**Estado:** Borrador

---

# 1. Objetivo

El **HID Daemon** es un servicio de host opcional encargado de integrar dispositivos HID (Human Interface Devices) con el ecosistema Nova.

Su responsabilidad consiste en traducir eventos físicos generados por dispositivos HID en comandos del sistema que puedan ser consumidos por Nova.

No implementa lógica de negocio ni conoce el funcionamiento interno del asistente.

---

# 2. Objetivos de diseño

- Ser completamente opcional.
- No modificar el comportamiento actual de Nova.
- No depender de una sesión gráfica.
- Ejecutarse como servicio `systemd --user`.
- Ser independiente del tipo de dispositivo HID.
- Permitir añadir nuevos dispositivos sin modificar Nova.

---

# 3. Alcance

Versión inicial:

- Lectura de eventos HID mediante `evdev`.
- Soporte para un único dispositivo.
- Ejecución de comandos configurables al pulsar y soltar botones.
- Arranque automático mediante `systemd --user`.

Fuera del alcance:

- Vibración.
- LEDs.
- Gestión de múltiples dispositivos.
- Configuración dinámica.
- Interfaz gráfica.

---

# 4. Arquitectura

```
                HID Device
                     │
                     ▼
             +----------------+
             | HID Daemon     |
             +----------------+
                     │
             Traducción eventos
                     │
                     ▼
        Ejecuta comandos configurados
                     │
                     ▼
          mic-start / mic-stop
                     │
                     ▼
                  Nova
```

El daemon actúa exclusivamente como adaptador entre el hardware y Nova.

---

# 5. Responsabilidades

El daemon deberá:

- Detectar el dispositivo HID configurado.
- Escuchar eventos del dispositivo.
- Identificar pulsaciones y liberaciones.
- Ejecutar los comandos asociados.
- Permanecer en ejecución hasta ser detenido.

El daemon no deberá:

- Gestionar grabaciones.
- Conocer el estado interno de Nova.
- Acceder al Interaction Manager.
- Comunicarse con Docker.
- Implementar lógica de conversación.

---

# 6. Arquitectura interna

## Device Manager

Responsable de:

- localizar el dispositivo HID
- abrirlo
- detectar desconexiones

---

## Event Listener

Responsable de:

- recibir eventos `evdev`
- filtrar únicamente eventos relevantes

---

## Mapper

Convierte eventos físicos en acciones lógicas.

Ejemplo:

```
BTN_GAMEPAD press
        ↓
mic-start
```

```
BTN_GAMEPAD release
        ↓
mic-stop
```

---

## Command Executor

Responsable de ejecutar el comando asociado.

No realiza ninguna interpretación.

---

# 7. Configuración

El daemon utilizará un fichero YAML.

Ejemplo:

```yaml
device: /dev/input/by-id/usb-20bc_Twin_USB_Joystick-event-joystick

bindings:

  BTN_GAMEPAD:

    press:
      command: mic-start

    release:
      command: mic-stop
```

---

# 8. Requisitos funcionales

## RF-01

El daemon deberá abrir el dispositivo HID configurado.

---

## RF-02

El daemon deberá permanecer escuchando eventos hasta finalizar.

---

## RF-03

Cuando se produzca una pulsación configurada deberá ejecutar el comando asociado.

---

## RF-04

Cuando se produzca la liberación del botón deberá ejecutar el comando configurado.

---

## RF-05

El daemon deberá escribir mensajes en el log indicando:

- inicio
- parada
- dispositivo encontrado
- dispositivo desconectado
- comando ejecutado
- errores

---

## RF-06

Si el dispositivo desaparece deberá intentar reconectarlo automáticamente.

---

## RF-07

La ausencia del daemon no deberá impedir el funcionamiento de Nova.

---

# 9. Requisitos no funcionales

## RNF-01

Debe ejecutarse como servicio `systemd --user`.

---

## RNF-02

Debe funcionar sin sesión gráfica utilizando `loginctl enable-linger`.

---

## RNF-03

No deberá depender de X11 ni Wayland.

---

## RNF-04

Debe consumir una cantidad mínima de CPU en reposo.

---

## RNF-05

No deberá requerir privilegios de administrador una vez instalado.

---

## RNF-06

El tiempo entre la pulsación y la ejecución del comando deberá ser inferior a 50 ms.

---

# 10. Instalación

## Dependencias

- Python 3
- evdev
- systemd

Instalación:

```
pip install evdev pyyaml
```

---

## Instalación del servicio

Copiar el ejecutable:

```
~/.local/bin/hid-daemon
```

Copiar la configuración:

```
~/.config/nova/hid-daemon.yaml
```

Crear el servicio:

```
~/.config/systemd/user/hid-daemon.service
```

Contenido:

```ini
[Unit]
Description=Nova HID Daemon

[Service]
ExecStart=%h/.local/bin/hid-daemon
Restart=always

[Install]
WantedBy=default.target
```

Habilitar:

```
systemctl --user daemon-reload

systemctl --user enable hid-daemon

systemctl --user start hid-daemon
```

Para mantenerlo funcionando incluso sin sesión gráfica:

```
sudo loginctl enable-linger <usuario>
```

---

# 11. Interfaz con Nova

La interfaz pública del daemon se limita a la ejecución de comandos.

Versión inicial:

```
mic-start
mic-stop
```

Nova no necesita conocer la existencia del daemon.

---

# 12. Manejo de errores

Si:

- el dispositivo no existe
- el dispositivo se desconecta
- un comando falla

el daemon deberá:

- registrar el error
- continuar funcionando
- intentar recuperar el dispositivo automáticamente

No deberá finalizar salvo error irrecuperable.

---

# 13. Evolución prevista

Sin modificar la arquitectura será posible incorporar:

- múltiples dispositivos HID
- perfiles de configuración
- vibración
- control de LEDs
- batería
- hot-plug
- botones multimedia
- pedales USB
- botones Bluetooth
- mandos de consola adicionales

Todo ello manteniendo la misma interfaz pública (`mic-start` / `mic-stop`) o ampliándola cuando Nova lo requiera.

---

# 14. Filosofía

El HID Daemon no forma parte del núcleo de Nova.

Es un adaptador opcional cuya única responsabilidad consiste en convertir eventos generados por dispositivos HID en acciones del sistema.

Nova continúa siendo completamente funcional aunque el daemon no esté instalado.