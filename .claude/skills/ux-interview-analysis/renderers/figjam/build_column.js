// FigJam renderer for one board column (Figma Plugin API, run through the Figma MCP `use_figma`).
// Do not edit by hand per run: `scripts/figjam_code.py` fills __SPEC__ and __X__ from the board JSON.
// Creates: a Summary section (title, context, coloured cards, note) and, when the column has steps,
// a Walkthrough section below it (one card per step: 800×477 screenshot slot + status pill + title + body).
// Returns: created section ids, screenshot slot ids per step key, FNV-1a hash per text (for board_hashcheck.py).
const SPEC = __SPEC__;
const X = __X__;
await figma.loadFontAsync({ family: 'Inter', style: 'Regular' });
await figma.loadFontAsync({ family: 'Inter', style: 'Bold' });
const INK = { r: 0.1176, g: 0.1176, b: 0.1176 }, MUTED = { r: 0.42, g: 0.42, b: 0.45 }, WHITE = { r: 1, g: 1, b: 1 };
const CARD = { grey: { r: 0.95, g: 0.95, b: 0.96 }, red: { r: 0.99, g: 0.93, b: 0.93 }, blue: { r: 0.93, g: 0.96, b: 0.99 }, green: { r: 0.93, g: 0.97, b: 0.93 }, amber: { r: 1, g: 0.96, b: 0.88 } };
const GREEN = { r: 0.2, g: 0.66, b: 0.33 }, ORANGE = { r: 0.93, g: 0.6, b: 0.1 }, RED = { r: 0.88, g: 0.2, b: 0.25 }, GREY = { r: 0.45, g: 0.45, b: 0.48 };
const PILL = { 'OK': GREEN, 'Borderline': ORANGE, 'Hraniční': ORANGE, 'Problem': RED, 'Problém': RED, 'Info': GREY };
const hashes = {}, created = [];
function fnv(s) { let h = 0x811c9dc5; for (const ch of s) { h ^= ch.codePointAt(0); h = Math.imul(h, 0x01000193) >>> 0; } return h >>> 0; }
function txt(parent, key, chars, size, bold, width, color) {
  const t = figma.createText();
  t.fontName = { family: 'Inter', style: bold ? 'Bold' : 'Regular' };
  t.fontSize = size; t.characters = chars; t.fills = [{ type: 'SOLID', color: color || INK }];
  parent.appendChild(t);
  if (width) { t.resize(width, t.height); t.textAutoResize = 'HEIGHT'; } else { t.textAutoResize = 'WIDTH_AND_HEIGHT'; }
  t.name = key.split('/').pop(); hashes[SPEC.id + '/' + key] = fnv(chars); return t;
}
function vbox(parent, name, width, pad, gap, fill, radius) {
  const f = figma.createAutoLayout('VERTICAL', { name });
  parent.appendChild(f);
  f.resize(width, 10); f.counterAxisSizingMode = 'FIXED'; f.primaryAxisSizingMode = 'AUTO';
  f.paddingTop = f.paddingBottom = pad[0]; f.paddingLeft = f.paddingRight = pad[1]; f.itemSpacing = gap;
  f.fills = fill ? [{ type: 'SOLID', color: fill }] : []; f.cornerRadius = radius || 0;
  return f;
}
// Summary section
const sec = figma.createSection(); sec.name = 'Summary · ' + SPEC.name; sec.x = X; sec.y = 0; created.push(sec.id);
const content = vbox(sec, 'Summary content', 1648, [40, 48], 24, WHITE, 0); content.x = 0; content.y = 0;
txt(content, 'title', SPEC.title, 34, true, 1552);
txt(content, 'context', SPEC.context, 16, false, 1552);
SPEC.cards.forEach((c, i) => {
  const card = vbox(content, 'Card ' + c.heading, 1552, [24, 28], 10, CARD[c.color], 16);
  txt(card, 'card' + i + '/heading', c.heading, 18, true, 1496);
  txt(card, 'card' + i + '/body', c.body, 15, false, 1496);
});
if (SPEC.note) txt(content, 'note', SPEC.note, 13, false, 1552, MUTED);
sec.resizeWithoutConstraints(1648, content.height + 40);
// Walkthrough section
const slots = {};
let sec2 = null;
if (SPEC.steps.length) {
  sec2 = figma.createSection(); sec2.name = 'Walkthrough · ' + SPEC.name; sec2.x = X; sec2.y = sec.height + 120; created.push(sec2.id);
  const steps = figma.createAutoLayout('VERTICAL', { name: 'Steps' }); sec2.appendChild(steps); steps.x = 0; steps.y = 0;
  steps.paddingTop = steps.paddingBottom = steps.paddingLeft = steps.paddingRight = 24; steps.itemSpacing = 32; steps.fills = [];
  for (const s of SPEC.steps) {
    const card = figma.createAutoLayout('HORIZONTAL', { name: 'Step ' + s.key }); steps.appendChild(card);
    card.paddingTop = card.paddingBottom = card.paddingLeft = card.paddingRight = 24; card.itemSpacing = 32; card.cornerRadius = 16;
    card.fills = [{ type: 'SOLID', color: WHITE }]; card.strokes = [{ type: 'SOLID', color: { r: 0.86, g: 0.86, b: 0.88 } }]; card.strokeWeight = 1;
    const rect = figma.createRectangle(); card.appendChild(rect); rect.name = 'Screenshot ' + s.key; rect.resize(800, 477); rect.cornerRadius = 8;
    rect.fills = [{ type: 'SOLID', color: { r: 0.9, g: 0.9, b: 0.92 } }]; slots[s.key] = rect.id;
    const tf = figma.createAutoLayout('VERTICAL', { name: 'Text' }); card.appendChild(tf); tf.itemSpacing = 12; tf.fills = [];
    const pill = figma.createAutoLayout('HORIZONTAL', { name: 'Status ' + s.status }); tf.appendChild(pill);
    pill.paddingTop = pill.paddingBottom = 4; pill.paddingLeft = pill.paddingRight = 12; pill.cornerRadius = 999; pill.fills = [{ type: 'SOLID', color: PILL[s.status] || GREY }];
    txt(pill, 'step:' + s.key + '/status', s.status, 13, true, 0, WHITE);
    txt(tf, 'step:' + s.key + '/title', s.title, 22, true, 712);
    txt(tf, 'step:' + s.key + '/body', s.body, 15, false, 712);
  }
  sec2.resizeWithoutConstraints(steps.width, steps.height);
}
return { createdNodeIds: created, summary: [sec.id, sec.width, sec.height], walkthrough: sec2 ? [sec2.id, sec2.y, sec2.width, sec2.height] : null, slots, hashes };
