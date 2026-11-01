# Skills de yestoall

Skills para la IA de tu ordenador, hechas para las apps de yestoall. Un plugin
por app; de momento, [Nevera](https://www.yestoall.com/nevera).

[Read it in English](README.md)

Versión 0.6.0

## nevera-recipes

Dale a tu IA una lista de vídeos de cocina y de webs de recetas, y te devuelve
un `.zip` que abres con Nevera en el teléfono: cada receta con sus
ingredientes, sus pasos y una foto del plato terminado.

- **Vídeos de YouTube**: la receta sale de la descripción y de lo que se dice
  en el vídeo. Usa los subtítulos si los tiene y, si no, transcribe el audio
  con Whisper, en tu ordenador.
- **Reels y posts de Instagram**: la receta sale del texto del post y de lo que
  se dice en el reel, transcrito con Whisper.
- **Webs de recetas**: la receta que la página lleva para los buscadores o, si
  no la lleva, su texto.
- **Una foto por receta**: un fotograma del plato terminado, recortado en
  cuadrado, sin títulos ni marcas de agua. De una web, su propia foto.
- **Se salta los enlaces que ya convirtió**: guarda un registro en `~/Downloads/nevera/`,
  así que puedes pasarle la misma lista dos veces.
- **Lo que falló, y por qué**: un vídeo privado, una página que no responde, un
  enlace sin receta. Un enlace nunca para a los demás.
- **Un Lote a medias no se pierde**: la próxima vez te dice qué dejó y te
  pregunta si lo sigues o empiezas de cero.
- **Lo revisas antes de enviarlo**: te lista las recetas y las deja en un fichero
  de texto que puedes leer y cambiar en cualquier editor, o dile a tu IA qué
  corregir.

### Instagram y tu navegador

Instagram enseña algunos posts solo a quien tiene la sesión abierta. La skill
saca primero lo que ve cualquiera. Si un post pide sesión, te pregunta una sola
vez por Lote: tú decides si puede usar la sesión de Instagram de un navegador
de tu ordenador, y de cuál. `yt-dlp` lee las cookies de ese navegador en
memoria, solo para esas descargas. Nunca se guardan en un fichero ni salen de
tu ordenador, y no necesita tu contraseña. Si dices que no, esos posts van al
informe y el siguiente Lote los vuelve a intentar.

En un Mac, leer las cookies de Safari pide Acceso total al disco para tu
terminal, y Chrome, Brave y Edge piden una vez permiso para su entrada del
llavero.

### Instalar

Con cualquier IA que lea skills (Claude Code, Codex, Antigravity CLI), y con
Node 22 o más:

```bash
npx skills add yestoall/skills --skill nevera-recipes
```

En Claude Code también puedes añadir este repositorio como marketplace de
plugins:

```text
/plugin marketplace add yestoall/skills
/plugin install nevera@yestoall
```

### Usar

Pídeselo a tu IA con tus palabras, y pégale los enlaces o dile en qué fichero
están:

> Hazme un Lote de Nevera con estos: https://youtu.be/… https://www.…

La primera vez, la skill instala lo que le falta y te avisa antes: `yt-dlp` (las
descargas) y `ffmpeg` (las fotos). Whisper (`faster-whisper`, unos 480 MB con su
modelo) solo se instala cuando un vídeo no tiene subtítulos, en una carpeta
propia, `~/Downloads/nevera/.venv`. Usa Homebrew en un Mac, winget en Windows y
apt en Linux. En un Mac, macOS te pide una vez permiso para que tu terminal entre
en Descargas. Si `yt-dlp` se queda atrás con YouTube, la skill lo actualiza y te
avisa antes.

Conserva `~/Downloads/nevera/` cuando limpies Descargas: sin ella, la skill vuelve
a instalar Whisper y ya no sabe qué enlaces convirtió.

Al terminar te da la ruta del Lote, `~/Downloads/nevera-lote-AAAA-MM-DD.zip`. En un
Mac te pregunta cómo quieres pasarlo al teléfono: lo copia a iCloud Drive, o te
enseña el fichero en el Finder para que hagas clic derecho → **Compartir** →
**AirDrop**. Desde otro ordenador, usa Quick Share, iCloud Drive, Google Drive o
un cable. Luego ábrelo:

- **En un iPhone**, en la app Archivos (AirDrop lo deja en Descargas), mantén
  pulsado el fichero y toca **Compartir** → Nevera.
- **En Android**, ábrelo desde Archivos o Descargas y elige Nevera.
- **En los dos**, desde Nevera: toca **Elegir archivo** en la pantalla de
  importar.

Nevera te enseña todas las recetas antes de guardar ninguna.

### Dónde funciona

| Sistema | Estado |
| --- | --- |
| macOS | Probada |
| Linux (Debian, Ubuntu) | Probada en Debian 12, en Docker: `docker build -t yestoall-skills-test . && docker run --rm yestoall-skills-test` lanza la prueba |
| Windows | Todavía sin probar |

En Windows, la skill instala con `winget install --id yt-dlp.yt-dlp -e`,
`winget install --id Gyan.FFmpeg -e`, `winget install --id DenoLand.Deno -e` y
`winget install --id Python.Python.3.12 -e`. Si la pruebas, cuéntanos cómo te ha
ido en un [issue](https://github.com/yestoall/skills/issues).

### El formato del Lote

El `.zip` lleva un `recipes.json` y una carpeta `photos/`:

```json
{
  "version": 1,
  "recipes": [
    {
      "name": "Tortilla de patatas",
      "author": "Cocina con Carmen",
      "url": "https://www.youtube.com/watch?v=uc8Pwe7alJ8",
      "category": "huevos",
      "preparationTime": "45 min",
      "photo": "tortilla.jpg",
      "ingredients": [{ "name": "Patatas", "quantity": "750 g" }],
      "preparationSteps": ["Pela las patatas y córtalas en láminas."]
    }
  ]
}
```

Cualquier herramienta puede escribir un Lote. Comprueba el tuyo con el
validador, que solo necesita Python 3.9 o más:

```bash
python3 plugins/nevera/skills/nevera-recipes/scripts/batch.py validate mi-lote.zip
```

### Para quien quiera contribuir

```bash
python3 -m unittest
```

Los tests solo usan la biblioteca estándar. La skill vive en
`plugins/nevera/skills/nevera-recipes/`: el `SKILL.md` y sus `scripts/`. Cada
versión es una etiqueta (`v0.4.0`), con su entrada en `CHANGELOG.md` y su número
en el `plugin.json` del plugin, en `marketplace.json` y al principio de los dos
README; `tests/test_version.py` falla si alguno se queda atrás. El formato del
Lote tiene su propia versión (`"version": 1`), que solo sube cuando Nevera sabe
leer la nueva y sigue leyendo la anterior.

## Licencia

[MIT](LICENSE)
