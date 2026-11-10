# Bajar video

Página local con un campo de enlace y dos acciones: **Descargar MP3** y **Descargar MP4**. El MP3 se baja directo. El MP4 pregunta la calidad antes de guardar el archivo.

Usa [yt-dlp](https://github.com/yt-dlp/yt-dlp) para leer el video y un FFmpeg incluido en `imageio-ffmpeg` para unir video y audio o convertir a MP3. No hace falta instalar FFmpeg en el sistema.

## Requisitos

- Linux con Python 3.12
- `curl`, para que `run.sh` pueda instalar pip si la máquina no lo trae
- Salida a internet cuando se consulta o descarga un video

## Correrlo

Desde la carpeta del proyecto:

```bash
chmod +x run.sh
./run.sh
```

La primera vez crea `.vendor/` e instala lo que está en `requirements.txt`. Las siguientes veces arranca directo. Abre [http://127.0.0.1:5050](http://127.0.0.1:5050).

Para pararlo, `Ctrl+C` en esa terminal.

Si el puerto 5050 ya está ocupado, cambia el puerto al final de `app.py`:

```python
app.run(host="127.0.0.1", port=5050, debug=False)
```

## Instalación manual

Sirve si prefieres un entorno virtual en vez de `.vendor/`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH="" .venv/bin/python app.py
```

En Debian/Ubuntu, el módulo `venv` a veces no viene instalado (`apt install python3.12-venv`). `run.sh` evita eso instalando las dependencias dentro de `.vendor/`.

## Uso

1. Pega un enlace `http` o `https` de un video público.
2. **Descargar MP3** convierte el mejor audio disponible a MP3 de 192 kbps.
3. **Descargar MP4** consulta las resoluciones y muestra un diálogo. La más alta queda marcada. Al confirmar, baja video y audio y los entrega en un solo `.mp4`.
4. El navegador guarda el archivo en su carpeta de descargas. El servidor no conserva una copia: usa un directorio temporal y lo borra al terminar de enviarlo.

Si el sitio no informa la altura del video, el diálogo ofrece **Mejor disponible**.

## Probarlo

Con el servidor corriendo:

```bash
# La página responde
curl -fsS http://127.0.0.1:5050/ -o /dev/null

# Un enlace inválido debe responder 400
curl -sS -X POST http://127.0.0.1:5050/api/download \
  -H 'Content-Type: application/json' \
  -d '{"url":"notaurl","kind":"mp3"}'

# Calidades de un video público de YouTube
curl -sS -X POST http://127.0.0.1:5050/api/qualities \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=aqz-KE-bpKQ"}'

# MP4 corto, sin resolución publicada: el diálogo dice "Mejor disponible"
curl -sS -X POST http://127.0.0.1:5050/api/qualities \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"}'

# Descargar ese mismo clip
curl -sS -D - -o /tmp/flower.mp4 -X POST http://127.0.0.1:5050/api/download \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4","kind":"mp4","height":0}'
file /tmp/flower.mp4

curl -sS -D - -o /tmp/flower.mp3 -X POST http://127.0.0.1:5050/api/download \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4","kind":"mp3"}'
file /tmp/flower.mp3
```

En el navegador, el recorrido equivalente es: pegar el enlace, pulsar **Descargar MP4**, ver el diálogo, confirmar, y comprobar el texto "Listo. Revisa tu carpeta de descargas." Luego repetir con **Descargar MP3**.

## Estructura

```
app.py              servidor y lógica de descarga
templates/index.html  página, estilos y botones
requirements.txt    Flask, yt-dlp e imageio-ffmpeg
run.sh              instala .vendor/ si falta y arranca
.vendor/            dependencias locales; no se versiona
```

## Dónde modificar

| Qué cambiar | Dónde |
| --- | --- |
| Textos, colores, diálogo de calidad | `templates/index.html` |
| Puerto, validación del enlace, calidades, bitrate del MP3 | `app.py` |
| Bitrate del MP3 | `preferredquality` en `app.py` (ahora `"192"`) |
| Cómo se elige el MP4 | `mp4_format()` en `app.py` |
| Dependencias | `requirements.txt` y luego borrar `.vendor/` y volver a ejecutar `./run.sh` |

`video_qualities()` agrupa los formatos de video por altura y se queda con el de mayor bitrate. `height: 0` significa "el mejor que haya", sin tope.

Con `debug=True` en `app.run(...)`, Flask recarga solo al guardar `app.py`. Las plantillas se leen en cada petición, así que un cambio en `index.html` se ve al recargar el navegador.

## API

`POST /api/qualities`

```json
{ "url": "https://..." }
```

Respuesta:

```json
{
  "title": "Nombre del video",
  "qualities": [{ "height": 1080, "label": "1080p" }]
}
```

`POST /api/download`

```json
{ "url": "https://...", "kind": "mp3" }
```

```json
{ "url": "https://...", "kind": "mp4", "height": 720 }
```

Si sale bien, responde el archivo como descarga. Si falla, responde `400` con `{ "error": "..." }`. Solo acepta enlaces `http` y `https`, y un video por enlace (`noplaylist`).

## Límites

- Pensada para usarla en esta máquina. Escucha solo en `127.0.0.1`.
- Un video largo mantiene la petición abierta hasta que termina de bajar y convertir.
- YouTube y los archivos directos públicos funcionan. Facebook y sitios que piden sesión suelen fallar; el mensaje de yt-dlp aparece en la página.
- Guarda contenido al que tengas derecho a acceder.
