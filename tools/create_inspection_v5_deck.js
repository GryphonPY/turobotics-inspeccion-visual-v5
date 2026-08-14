const pptxgen = require('pptxgenjs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const outDir = path.join(root, 'docs');
const asset = (...parts) => path.join(root, ...parts);

const IMG = {
  pass: asset('data', 'v5', 'reports', 'ui_review', 'pass.png'),
  fail: asset('data', 'v5', 'reports', 'ui_review', 'fail.png'),
  piece: asset('docs', 'current_piece_zoom.png'),
  board: asset('tests_v5', 'fixtures', 'board_complete.png'),
  complete: asset('tests_v5', 'fixtures', 'complete.png'),
  missing: asset('tests_v5', 'fixtures', 'missing_c08.png'),
  unsafe: asset('tests_v5', 'fixtures', 'bad_light.png'),
};

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_16x9';
pptx.author = 'TuRobotics / Inspección Visual V5';
pptx.company = 'TuRobotics';
pptx.subject = 'Explicación sencilla del sistema de inspección visual';
pptx.title = 'Inspección visual del ensamble';
pptx.lang = 'es-MX';
pptx.theme = {
  headFontFace: 'Arial',
  bodyFontFace: 'Arial',
  lang: 'es-MX',
};
pptx.defineLayout({ name: 'CUSTOM', width: 13.333, height: 7.5 });
pptx.layout = 'CUSTOM';

const S = pptx.ShapeType;
const C = {
  navy: '071321',
  ink: '102338',
  card: '102A40',
  card2: '163A52',
  white: 'F7FAFC',
  muted: 'A9B9CB',
  cyan: '2DD4FF',
  green: '26E27A',
  red: 'FF5264',
  amber: 'FFC83D',
  line: '35536C',
  pale: 'EAF1F5',
  pale2: 'D7E4EA',
  black: '101418',
};

function addText(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    margin: opts.margin ?? 0,
    fontFace: opts.fontFace || 'Arial',
    fontSize: opts.fontSize || 18,
    color: opts.color || C.ink,
    bold: opts.bold || false,
    italic: opts.italic || false,
    align: opts.align || 'left',
    valign: opts.valign || 'mid',
    breakLine: false,
    fit: 'shrink',
    paraSpaceAfterPt: opts.paraSpaceAfterPt || 0,
  });
}

function addTitle(slide, kicker, title, dark = false) {
  addText(slide, kicker.toUpperCase(), 0.62, 0.35, 4.8, 0.25, {
    fontSize: 10, bold: true, color: dark ? C.cyan : '087E9B',
  });
  addText(slide, title, 0.62, 0.65, 12.0, 0.58, {
    fontSize: 29, bold: true, color: dark ? C.white : C.ink,
  });
}

function addFooter(slide, n, dark = false) {
  addText(slide, `TUROBOTICS  /  INSPECCIÓN VISUAL  ·  ${String(n).padStart(2, '0')}`, 0.62, 7.14, 5.6, 0.18, {
    fontSize: 8.5, bold: true, color: dark ? '7591A5' : '668093',
  });
  slide.addShape(S.line, { x: 11.55, y: 7.18, w: 1.15, h: 0, line: { color: dark ? C.line : 'B9CBD4', width: 1 } });
}

function darkSlide(kicker, title, n) {
  const slide = pptx.addSlide();
  slide.background = { color: C.navy };
  addTitle(slide, kicker, title, true);
  addFooter(slide, n, true);
  return slide;
}

function lightSlide(kicker, title, n) {
  const slide = pptx.addSlide();
  slide.background = { color: C.pale };
  addTitle(slide, kicker, title, false);
  addFooter(slide, n, false);
  return slide;
}

function card(slide, x, y, w, h, fill = C.white, line = 'D6E2E8', radius = true) {
  slide.addShape(radius ? S.roundRect : S.rect, {
    x, y, w, h,
    rectRadius: 0.08,
    fill: { color: fill },
    line: { color: line, width: 1 },
    shadow: { type: 'outer', color: '172B3A', blur: 2, offset: 1, angle: 135, opacity: 0.10 },
  });
}

function pill(slide, label, x, y, w, color, textColor = C.navy) {
  slide.addShape(S.roundRect, { x, y, w, h: 0.33, rectRadius: 0.06, fill: { color }, line: { color, transparency: 100 } });
  addText(slide, label, x, y + 0.01, w, 0.27, { fontSize: 10, bold: true, color: textColor, align: 'center' });
}

function imageContain(slide, imagePath, x, y, w, h, border = null) {
  if (border) {
    slide.addShape(S.roundRect, { x: x - 0.05, y: y - 0.05, w: w + 0.1, h: h + 0.1, rectRadius: 0.05, fill: { color: C.white }, line: { color: border, width: 1.1 } });
  }
  slide.addImage({ path: imagePath, x, y, w, h, sizing: { type: 'contain', x, y, w, h } });
}

function arrow(slide, x1, y1, x2, y2, color = C.cyan, width = 2.2) {
  slide.addShape(S.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color, width, beginArrowType: 'none', endArrowType: 'triangle' } });
}

function iconCircle(slide, x, y, label, fill, color = C.navy) {
  slide.addShape(S.ellipse, { x, y, w: 0.68, h: 0.68, fill: { color: fill }, line: { color: fill, transparency: 100 } });
  addText(slide, label, x, y + 0.02, 0.68, 0.6, { fontSize: 16, bold: true, color, align: 'center' });
}

function componentMap(slide, x, y, scale = 1, missingId = null) {
  const pieces = [
    ['C01', 0.82, 0.00, 0.58, 0.35], ['C02', 1.48, 0.00, 0.58, 0.35],
    ['C03', 0.55, 0.42, 0.88, 0.35], ['C04', 1.45, 0.42, 0.88, 0.35],
    ['C05', 0.95, 0.84, 0.70, 0.35],
    ['C06', 0.55, 1.25, 0.88, 0.35], ['C07', 1.45, 1.25, 0.88, 0.35],
    ['C08', 0.95, 1.67, 0.70, 0.35],
    ['C09', 0.55, 2.08, 0.88, 0.35], ['C10', 1.45, 2.08, 0.88, 0.35],
  ];
  for (const [label, px, py, pw, ph] of pieces) {
    const missing = label === missingId;
    slide.addShape(S.roundRect, {
      x: x + px * scale, y: y + py * scale, w: pw * scale, h: ph * scale,
      rectRadius: 0.05,
      fill: { color: missing ? '3C2028' : C.card2 },
      line: { color: missing ? C.red : C.cyan, width: 1.5 },
    });
    addText(slide, label, x + px * scale, y + (py + 0.05) * scale, pw * scale, 0.22 * scale, {
      fontSize: Math.max(7, 10 * scale), bold: true, color: missing ? C.red : C.white, align: 'center',
    });
  }
}

function note(slide, text) {
  if (typeof slide.addNotes === 'function') slide.addNotes(text);
}

// 1 — portada
{
  const slide = pptx.addSlide();
  slide.background = { color: C.navy };
  slide.addShape(S.rect, { x: 0, y: 0, w: 5.35, h: 7.5, fill: { color: C.card }, line: { color: C.card, transparency: 100 } });
  slide.addShape(S.rect, { x: 5.35, y: 0, w: 7.983, h: 7.5, fill: { color: C.black }, line: { color: C.black, transparency: 100 } });
  imageContain(slide, IMG.piece, 5.55, 0.22, 7.55, 6.86);
  addText(slide, 'TUROBOTICS', 0.72, 0.72, 3.6, 0.3, { fontSize: 13, bold: true, color: C.cyan });
  addText(slide, 'Inspección visual\ndel ensamble', 0.72, 1.48, 4.45, 1.52, { fontSize: 34, bold: true, color: C.white, valign: 'top' });
  addText(slide, 'Una cámara comprueba que las 10 piezas estén presentes antes de aceptar el producto.', 0.75, 3.45, 3.85, 0.88, { fontSize: 18, color: C.muted, valign: 'top' });
  pill(slide, 'EXPLICACIÓN DEL SISTEMA', 0.75, 5.05, 2.35, C.green, C.navy);
  addText(slide, 'Sección para la presentación del proyecto', 0.75, 5.55, 3.9, 0.3, { fontSize: 12, color: '7F9CB0' });
  addFooter(slide, 1, true);
  note(slide, 'Esta sección explica qué hace el sistema, qué necesita y cómo toma una decisión. No es necesario conocer programación para entenderlo.');
}

// 2 — problema
{
  const slide = lightSlide('01 · El problema', 'Revisar 10 piezas a simple vista puede fallar', 2);
  card(slide, 0.65, 1.55, 5.55, 4.85, C.white);
  addText(slide, 'Revisión manual', 0.95, 1.88, 3.0, 0.3, { fontSize: 21, bold: true, color: C.ink });
  addText(slide, 'Cuando las piezas se tocan, una puede faltar y el conjunto todavía parecer completo.', 0.95, 2.35, 4.35, 0.7, { fontSize: 16, color: '51697A', valign: 'top' });
  imageContain(slide, IMG.missing, 1.28, 3.20, 2.2, 2.55);
  pill(slide, 'DIFÍCIL DE NOTAR', 3.75, 4.18, 1.7, C.amber, C.ink);
  addText(slide, 'La revisión depende del cansancio y de la atención de la persona.', 3.75, 4.75, 1.95, 0.86, { fontSize: 13, color: '51697A', valign: 'top' });

  card(slide, 7.12, 1.55, 5.55, 4.85, C.ink, C.ink);
  addText(slide, 'Con el sistema', 7.42, 1.88, 3.0, 0.3, { fontSize: 21, bold: true, color: C.white });
  addText(slide, 'La cámara revisa una por una las 10 posiciones definidas.', 7.42, 2.35, 4.35, 0.65, { fontSize: 16, color: C.muted, valign: 'top' });
  componentMap(slide, 8.2, 2.98, 1.05);
  pill(slide, '10/10 PRESENTES', 7.42, 5.72, 2.0, C.green, C.navy);
  addText(slide, 'La decisión se muestra en grande: PASA o NO PASA.', 9.65, 5.70, 2.5, 0.45, { fontSize: 13, color: C.muted, valign: 'mid' });
  note(slide, 'La idea no es contar contornos separados, porque las piezas están unidas. Se revisan las diez zonas conocidas del ensamble.');
}

// 3 — estación
{
  const slide = darkSlide('02 · La estación', 'La hoja hace que la cámara entienda siempre el mismo lugar', 3);
  imageContain(slide, IMG.board, 0.75, 1.53, 5.18, 4.98, '3C586F');
  const markers = [
    ['1', 0.98, 1.84], ['2', 5.02, 1.84], ['3', 0.98, 5.28], ['4', 5.02, 5.28],
  ];
  for (const [label, x, y] of markers) {
    iconCircle(slide, x, y, label, C.cyan);
  }
  card(slide, 6.65, 1.55, 5.95, 4.9, C.card, C.line);
  const items = [
    ['CÁMARA', 'El celular funciona como webcam.'],
    ['REFERENCIA', 'Las cuatro marcas corrigen el ángulo.'],
    ['ZONA DE REVISIÓN', 'La pieza se coloca dentro del rectángulo central.'],
    ['FONDO OSCURO', 'Ayuda a separar las piezas del tablero.'],
  ];
  items.forEach(([head, body], i) => {
    const y = 1.95 + i * 0.95;
    slide.addShape(S.rect, { x: 7.02, y: y + 0.05, w: 0.08, h: 0.42, fill: { color: i === 2 ? C.green : C.cyan }, line: { color: i === 2 ? C.green : C.cyan, transparency: 100 } });
    addText(slide, head, 7.32, y, 2.35, 0.22, { fontSize: 12, bold: true, color: i === 2 ? C.green : C.cyan });
    addText(slide, body, 7.32, y + 0.29, 4.65, 0.34, { fontSize: 14, color: C.white });
  });
  addText(slide, 'La hoja no analiza la pieza: sólo fija la referencia para que la imagen sea comparable.', 6.98, 5.65, 4.95, 0.48, { fontSize: 14, italic: true, color: C.muted, valign: 'top' });
  note(slide, 'Las marcas de las esquinas permiten enderezar la imagen aunque el celular esté un poco inclinado. La hoja debe estar plana.');
}

// 4 — flujo
{
  const slide = lightSlide('03 · Funcionamiento', 'Del celular a una decisión en unos segundos', 4);
  const steps = [
    ['1', 'Cámara', 'Toma la imagen desde arriba', C.cyan],
    ['2', 'Enderezar', 'Corrige el ángulo de la hoja', '62CBE8'],
    ['3', 'Estabilizar', 'Espera a que la pieza no se mueva', C.amber],
    ['4', 'Comparar', 'Revisa las 10 posiciones', '8E7CFF'],
    ['5', 'Decidir', 'Muestra PASA o NO PASA', C.green],
  ];
  const y = 2.45;
  steps.forEach(([n, head, body, color], i) => {
    const x = 0.75 + i * 2.48;
    card(slide, x, y, 1.92, 2.02, C.white);
    iconCircle(slide, x + 0.62, y + 0.24, n, color, C.navy);
    addText(slide, head, x + 0.18, y + 1.05, 1.56, 0.25, { fontSize: 15, bold: true, color: C.ink, align: 'center' });
    addText(slide, body, x + 0.18, y + 1.39, 1.56, 0.45, { fontSize: 11.5, color: '5B7282', align: 'center', valign: 'top' });
    if (i < steps.length - 1) arrow(slide, x + 1.96, y + 1.02, x + 2.35, y + 1.02, '7595A8', 1.4);
  });
  addText(slide, 'La persona sólo coloca la pieza y espera el resultado.', 2.22, 5.55, 8.9, 0.48, { fontSize: 21, bold: true, color: C.ink, align: 'center' });
  addText(slide, 'Si la imagen no es segura, el sistema no adivina: avisa que hay que repetir la captura.', 2.05, 6.08, 9.2, 0.32, { fontSize: 14, color: '5B7282', align: 'center' });
  note(slide, 'Este es el flujo completo. La parte importante es que una mala imagen no se convierte en un resultado engañoso.');
}

// 5 — componentes
{
  const slide = darkSlide('04 · Qué revisa', 'No cuenta “manchas”: revisa las 10 piezas definidas', 5);
  card(slide, 0.68, 1.48, 5.0, 5.15, C.card, C.line);
  addText(slide, 'Mapa del ensamble', 1.0, 1.78, 2.8, 0.3, { fontSize: 18, bold: true, color: C.white });
  componentMap(slide, 1.45, 2.25, 1.48);
  addText(slide, 'Cada recuadro representa una posición que debe estar presente.', 1.05, 6.03, 4.2, 0.34, { fontSize: 13, color: C.muted, align: 'center' });
  imageContain(slide, IMG.complete, 6.18, 1.58, 2.55, 4.88, '3C586F');
  card(slide, 9.05, 1.48, 3.57, 5.15, C.card, C.line);
  addText(slide, 'Qué compara', 9.35, 1.78, 2.0, 0.3, { fontSize: 18, bold: true, color: C.white });
  const checks = [
    ['FORMA', 'La silueta general'],
    ['UNIONES', 'Dónde se juntan las piezas'],
    ['POSICIÓN', 'La zona que ocupa cada componente'],
    ['ESTABILIDAD', 'Que el resultado se repita en varios cuadros'],
  ];
  checks.forEach(([head, body], i) => {
    const yy = 2.35 + i * 0.82;
    slide.addShape(S.ellipse, { x: 9.37, y: yy + 0.03, w: 0.22, h: 0.22, fill: { color: C.green }, line: { color: C.green, transparency: 100 } });
    addText(slide, head, 9.76, yy, 2.4, 0.18, { fontSize: 11, bold: true, color: C.green });
    addText(slide, body, 9.76, yy + 0.23, 2.35, 0.32, { fontSize: 12.5, color: C.white });
  });
  note(slide, 'El color amarillo de una pieza no es la regla. La verificación usa forma, posición y uniones, por eso puede trabajar con piezas grises.');
}

// 6 — live
{
  const slide = lightSlide('05 · Modo live', 'El modo live libera el siguiente ciclo automáticamente', 6);
  imageContain(slide, IMG.pass, 0.72, 1.48, 6.1, 4.98, 'B5C8D0');
  card(slide, 7.23, 1.48, 5.4, 4.98, C.ink, C.ink);
  const live = [
    ['ESPERA', 'Detecta que el área está libre'],
    ['ENTRA', 'La pieza aparece y se estabiliza'],
    ['REVISA', 'Junta varios cuadros confiables'],
    ['MUESTRA', 'Congela el resultado'],
    ['RETIRA', 'Desbloquea el siguiente ciclo'],
  ];
  live.forEach(([head, body], i) => {
    const yy = 1.88 + i * 0.79;
    const col = i === 3 ? C.green : C.cyan;
    slide.addShape(S.ellipse, { x: 7.62, y: yy + 0.02, w: 0.25, h: 0.25, fill: { color: col }, line: { color: col, transparency: 100 } });
    if (i < live.length - 1) slide.addShape(S.line, { x: 7.745, y: yy + 0.28, w: 0, h: 0.53, line: { color: C.line, width: 1.2 } });
    addText(slide, head, 8.05, yy - 0.01, 1.2, 0.2, { fontSize: 12, bold: true, color: col });
    addText(slide, body, 9.23, yy - 0.01, 2.9, 0.28, { fontSize: 13, color: C.white });
  });
  addText(slide, 'Así no hay que presionar “espacio” para cada nueva pieza.', 7.62, 5.88, 4.36, 0.3, { fontSize: 14, bold: true, color: C.green });
  note(slide, 'La interfaz no cuenta dos veces la misma pieza. Espera a que se retire antes de aceptar una nueva inspección.');
}

// 7 — resultados
{
  const slide = darkSlide('06 · Resultado', 'Tres respuestas claras, sin porcentajes confusos', 7);
  const results = [
    ['PASA', 'Las 10 piezas están presentes', C.green, IMG.pass],
    ['NO PASA', 'Falta una o más piezas', C.red, IMG.fail],
    ['CAPTURA NO CONFIABLE', 'La imagen debe repetirse', C.amber, IMG.unsafe],
  ];
  results.forEach(([head, body, color, image], i) => {
    const x = 0.68 + i * 4.2;
    card(slide, x, 1.55, 3.8, 4.95, C.card, C.line);
    imageContain(slide, image, x + 0.26, 1.83, 3.28, 2.35);
    pill(slide, head, x + 0.28, 4.45, i === 2 ? 2.45 : 1.42, color, C.navy);
    addText(slide, body, x + 0.28, 5.12, 3.2, 0.55, { fontSize: 15, color: C.white, valign: 'top' });
  });
  addText(slide, 'Si la imagen es mala, el sistema prefiere pedir otra captura antes que inventar un resultado.', 1.35, 6.72, 10.6, 0.25, { fontSize: 14, italic: true, color: C.muted, align: 'center' });
  note(slide, 'La tercera respuesta es importante: una cámara desenfocada o una mano tapando el tablero no debe terminar en un falso aprobado.');
}

// 8 — validación
{
  const slide = lightSlide('07 · Confiabilidad', 'La solidez se demuestra con pruebas', 8);
  card(slide, 0.7, 1.55, 4.1, 4.9, C.ink, C.ink);
  addText(slide, 'Prueba física realizada', 1.05, 1.93, 3.3, 0.3, { fontSize: 20, bold: true, color: C.white });
  addText(slide, '60', 1.05, 2.58, 1.1, 0.9, { fontSize: 56, bold: true, color: C.cyan });
  addText(slide, 'ciclos con cámara Android y piezas reales', 2.14, 2.82, 2.1, 0.55, { fontSize: 14, color: C.muted, valign: 'mid' });
  pill(slide, '0 FALSOS PASA', 1.05, 4.08, 2.0, C.green, C.navy);
  addText(slide, 'El conjunto de prueba no aceptó defectos ni capturas inseguras como producto bueno.', 1.05, 4.7, 3.15, 0.72, { fontSize: 14, color: C.white, valign: 'top' });
  card(slide, 5.2, 1.55, 7.42, 4.9, C.white);
  addText(slide, 'Puertas antes de la presentación', 5.58, 1.93, 4.5, 0.3, { fontSize: 20, bold: true, color: C.ink });
  const gates = [
    ['01', 'Pruebas automáticas', 'El sistema responde igual al repetir las mismas escenas.'],
    ['02', 'Batería física completa', 'Buenas, faltantes, reacomodadas y condiciones inseguras.'],
    ['03', 'Ensayo en la tele', 'Resultado legible y operación sencilla para el expositor.'],
    ['04', 'Respaldo', 'V4 conservada como plan de recuperación.'],
  ];
  gates.forEach(([num, head, body], i) => {
    const yy = 2.55 + i * 0.78;
    iconCircle(slide, 5.65, yy, num, i < 2 ? C.cyan : C.green);
    addText(slide, head, 6.55, yy + 0.02, 2.75, 0.22, { fontSize: 13, bold: true, color: C.ink });
    addText(slide, body, 9.15, yy + 0.02, 2.95, 0.29, { fontSize: 12.5, color: '5B7282' });
  });
  note(slide, 'El challenge de 60 ciclos ya salió sin falsos PASA. La batería completa y el ensayo de televisión son las últimas puertas para llamarlo liberado.');
}

// 9 — demo
{
  const slide = darkSlide('08 · En la presentación', 'El profesor sólo necesita ver tres cosas', 9);
  const demo = [
    ['1', 'Colocar', 'Poner el ensamble dentro del rectángulo'],
    ['2', 'Esperar', 'La pantalla muestra que está analizando'],
    ['3', 'Leer', 'PASA, NO PASA o repetir captura'],
  ];
  demo.forEach(([n, head, body], i) => {
    const x = 0.85 + i * 4.1;
    card(slide, x, 1.65, 3.45, 2.15, C.card, C.line);
    iconCircle(slide, x + 0.28, 1.98, n, i === 0 ? C.cyan : i === 1 ? C.amber : C.green);
    addText(slide, head, x + 1.12, 2.02, 1.95, 0.28, { fontSize: 20, bold: true, color: C.white });
    addText(slide, body, x + 0.3, 2.78, 2.8, 0.52, { fontSize: 14, color: C.muted, valign: 'top' });
  });
  imageContain(slide, IMG.pass, 0.86, 4.32, 5.7, 2.04, '3C586F');
  imageContain(slide, IMG.fail, 6.78, 4.32, 5.7, 2.04, '3C586F');
  addText(slide, 'La lógica completa cabe en una frase:', 4.05, 3.98, 5.3, 0.25, { fontSize: 13, color: C.cyan, align: 'center' });
  addText(slide, '“¿Están las 10 piezas? Sí: PASA. No: NO PASA. ¿La imagen es mala? Repetir.”', 1.08, 6.72, 11.2, 0.24, { fontSize: 14, bold: true, color: C.white, align: 'center' });
  note(slide, 'La explicación final para el público es sencilla: el sistema verifica las diez piezas y muestra un resultado que cualquiera puede leer.');
}

// 10 — cierre
{
  const slide = pptx.addSlide();
  slide.background = { color: C.green };
  addText(slide, 'INSPECCIÓN VISUAL', 0.75, 0.72, 4.5, 0.3, { fontSize: 13, bold: true, color: C.navy });
  addText(slide, 'De revisar a ojo\na comprobar con evidencia.', 0.75, 1.55, 7.6, 1.45, { fontSize: 39, bold: true, color: C.navy, valign: 'top' });
  addText(slide, 'Una cámara, una referencia fija y una decisión clara para cada ensamble.', 0.78, 3.45, 5.9, 0.62, { fontSize: 19, color: '16432A', valign: 'top' });
  slide.addShape(S.ellipse, { x: 8.48, y: 1.15, w: 3.45, h: 3.45, fill: { color: C.navy }, line: { color: C.navy, transparency: 100 } });
  addText(slide, '10/10', 8.86, 1.87, 2.7, 0.68, { fontSize: 47, bold: true, color: C.green, align: 'center' });
  addText(slide, 'PRESENTES', 8.85, 2.73, 2.75, 0.36, { fontSize: 18, bold: true, color: C.white, align: 'center' });
  addText(slide, 'Sistema de inspección visual V5', 0.78, 6.78, 5.4, 0.24, { fontSize: 12, bold: true, color: '16432A' });
  addText(slide, 'TUROBOTICS  /  10', 11.15, 6.78, 1.3, 0.24, { fontSize: 10, bold: true, color: '16432A', align: 'right' });
  note(slide, 'Cierre: el sistema convierte una revisión visual repetitiva en una decisión clara y trazable.');
}

pptx.writeFile({ fileName: path.join(outDir, 'Presentacion_Inspeccion_Visual_V5.pptx') });
