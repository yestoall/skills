# Skills de yestoall

Skills para la IA de tu ordenador, hechas para las apps y herramientas de
yestoall. Un plugin para cada una: [Nevera](https://www.yestoall.com/nevera) y
[Tipos](https://www.yestoall.com/tipos).

[Read it in English](README.md)

Versión 0.13.0

## nevera-recipes

Dale a tu IA una lista de vídeos de cocina y de webs de recetas, y te devuelve
un `.zip` que abres con Nevera en el teléfono: cada receta con sus
ingredientes, sus pasos y una foto del plato terminado.

- **Vídeos de YouTube**: la receta sale de la descripción y de lo que se dice
  en el vídeo. Usa los subtítulos si los tiene y, si no, transcribe el audio
  con Whisper, en tu ordenador.
- **Reels y posts de Instagram**: la receta sale del texto del post y de lo que
  se dice en el reel, transcrito con Whisper.
- **Vídeos de TikTok**: la receta sale del texto del post y de lo que se dice en
  el vídeo, transcrito con Whisper.
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

### Actualizar

Actualízala igual que la instalaste:

```bash
# con npx skills
npx skills update nevera-recipes

# como plugin de Claude Code; luego abre una sesión nueva
claude plugin marketplace update yestoall && claude plugin update nevera@yestoall
```

No tienes que estar pendiente. Cada vez que la usas, la skill lee un fichero
público de GitHub para ver si hay una versión nueva, y no envía nada. Si la hay,
te lo dice lo primero, en un bloque destacado con el comando, y sigue con la
versión que tienes. Lo mismo te dice de un `yt-dlp` viejo, que actualiza ella.

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

Al terminar te da la ruta del Lote, `~/Downloads/nevera-lote-AAAA-MM-DD.zip`, y te
pregunta cómo quieres pasarlo al teléfono.

Primero te ofrece un QR. Escanéalo con la cámara del teléfono y Nevera se abre con
las recetas, bajadas directamente de tu ordenador por tu wifi. Necesitas Nevera 2.9.0
o posterior y el teléfono en la misma wifi. Nadie lo ha probado aún en Android, así
que si la cámara no abre Nevera, usa otra vía. Una red de invitados o un cortafuegos
también pueden impedirlo.

En un Mac también puede abrir AirDrop con el fichero para que solo elijas tu
teléfono, o copiarlo a iCloud Drive. AirDrop necesita Xcode o
las Command Line Tools. Sin ellas, la skill te enseña el fichero en el Finder para
que hagas clic derecho → **Compartir** → **AirDrop**. Desde otro ordenador, usa
Quick Share, iCloud Drive, Google Drive o un cable. Por cualquiera de estas vías,
luego ábrelo:

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
      "subtitle": "con cebolla y jugosa por dentro",
      "author": "Cocina con Carmen",
      "url": "https://www.youtube.com/watch?v=uc8Pwe7alJ8",
      "category": "huevos",
      "categories": ["huevos", "cenas"],
      "preparationTime": "45 min",
      "photo": "tortilla.jpg",
      "ingredients": [{ "name": "Patatas", "quantity": "750 g" }],
      "preparationSteps": ["Pela las patatas y córtalas en láminas."]
    }
  ]
}
```

Una receta puede tener varios tipos: `categories` los lleva todos, y `category`
el primero, que es lo único que lee una Nevera anterior a los tipos de la 2.9.0.
`subtitle` es opcional: una línea que dice qué es el plato cuando el nombre no
lo cuenta, y `""` cuando sí. Una Nevera sin subtítulos lo ignora.

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
en el `plugin.json` del plugin, en `marketplace.json`, en `doctor.py` y al
principio de los dos README; `tests/test_version.py` falla si alguno se queda atrás. El formato del
Lote tiene su propia versión (`"version": 1`), que solo sube cuando Nevera sabe
leer la nueva y sigue leyendo la anterior.

## tipos

Cambia la tipografía de tu web o de tu App con
[Tipos](https://www.yestoall.com/tipos), viéndola antes de ponerla. Tu IA lee tu
código, encuentra las piezas de tu interfaz que llevan tipografía propia (los
botones, las etiquetas, los títulos de sección) y te abre cada una en Tipos con
la tipografía y las palabras que tiene hoy. La ajustas a ojo, pulsas **Copiar para tu
agente** y se lo pegas. Tu IA la pone en tu código y pasa a la siguiente.

- **Parte de tu tipografía**: fuente, tamaño, interlineado, peso y espaciado, leídos
  de tu CSS, de tus clases de Tailwind o Uniwind o de tus estilos de React
  Native.
- **Las piezas las nombras tú**: «el botón», «las etiquetas». Cada una se
  queda en una clase, `type-boton`, `type-etiquetas`, y vive en un solo sitio.
- **Una pieza cada vez**: la ajustas, la pegas, comprueba que el proyecto
  compila y pasa a la siguiente.
- **Nada que no hayas pedido**: si una pieza lleva tipografías distintas en sitios
  distintos, tu IA te enseña dónde antes de unificarlas. Si un componente no
  deja pasar la clase, te pregunta primero.
- **Las fuentes del catálogo de Tipos**, todas con licencia OFL: Allo, Inter,
  Inrond, Pollen y Google Sans Flex. Si la tuya no está, empiezas por la más
  parecida, y tu IA te lo dice.

### Instalar

Con cualquier IA que lea skills, con Node 22 o posterior:

```bash
npx skills add yestoall/skills --skill tipos
```

En Claude Code, también puedes añadir este repositorio como marketplace de
plugins:

```text
/plugin marketplace add yestoall/skills
/plugin install tipos@yestoall
```

### Usar

Pídeselo a tu IA con tus palabras:

> Cambia la tipografía de mi App con Tipos

Te enseña las piezas que ha encontrado, cada una con su tipografía y dónde está, y
te pregunta cuáles quieres ajustar y cómo llamarlas. Luego te abre Tipos en el
navegador con la primera. Tipos está en castellano y en inglés, y tu IA te abre
el de tu idioma.

Cuando te guste, pulsa **Copiar para tu agente**, debajo del texto en Tipos, y
pégalo en el chat. Copia solo la tipografía: la fuente, las medidas y las
alternativas, sin código. Tu IA la escribe como tu proyecto ya pone la suya, y
lo que no sea tipografía te lo enseña y te pregunta. Al terminar, te da un resumen
de lo que ha cambiado y de lo que queda.

## Licencia

[MIT](LICENSE)
