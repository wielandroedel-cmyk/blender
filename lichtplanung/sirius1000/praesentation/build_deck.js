// Blendungsbewertung SIRIUS 1000 – Blende heute vs. 50 % Lochung
// Stil nach dem Siteco-Datenblatt "Sirius CUT-RS06 Trenntrafo" (Artefakt): Tinte, Akzentblau,
// Hellgrau-Raster, Kopfzeile mit Revision/Datum/Bearbeiter.
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "data.json"), "utf8"));
const IMG = (f) => path.join(__dirname, f);

const THEME = {
  name: "Siteco Datenblatt",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "17202B", lt1: "FFFFFF", dk2: "5B6673", lt2: "F6F7F8",
    accent1: "0B5CAD", accent2: "A35A00", accent3: "E3EEF9", accent4: "D5DBE1",
    accent5: "2F9A46", accent6: "FBF0E1", hlink: "0B5CAD", folHlink: "5B6673",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "Blendungsbewertung SIRIUS 1000 – außenliegende Blende";
pres.author = "W. Rödel";
pres.subject = "Vergleich Blende wie geliefert (Lochung 3,4 %) und Lochung 50 %";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const FOOT = "Siteco SIRIUS 1000 · Blendungsbewertung außenliegende Blende · Rev. C · 26.10.2026 · Entwurf zur Prüfung";

// ---------------------------------------------------------------- Layouts
pres.defineSlideMaster({
  title: "TITEL",
  background: { color: C.background2 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: 0.8, y: 1.2, w: 11.7, h: 0.4,
      fontSize: 13, color: C.accent1, bold: true, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.75, w: 11.7, h: 2.2,
      fontSize: 44, bold: true, color: C.text1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "subtitle", type: "body", x: 0.8, y: 4.1, w: 10.5, h: 1.1,
      fontSize: 18, color: C.text2, valign: "top", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "meta", type: "body", x: 0.8, y: 6.2, w: 11.7, h: 0.4,
      fontSize: 12, color: C.text2, margin: 0 }, text: "" } },
  ],
});

pres.defineSlideMaster({
  title: "INHALT",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.8, 0.6],
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: 0.6, y: 0.38, w: 12.1, h: 0.3,
      fontSize: 11, color: C.accent1, bold: true, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.7, w: 12.1, h: 0.85,
      fontSize: 28, bold: true, color: C.text1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { text: { text: FOOT, options: { x: 0.6, y: 7.0, w: 10.5, h: 0.3, fontSize: 9,
      color: C.text2, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 9, color: C.text2, align: "right" },
});

// ---------------------------------------------------------------- Helfer
function content(section, eyebrow, title) {
  const s = pres.addSlide({ masterName: "INHALT", sectionTitle: section });
  s.addText(eyebrow, { placeholder: "eyebrow" });
  s.addText(title, { placeholder: "title" });
  return s;
}

function kpi(s, x, y, w, h, big, label, name, bigColor) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.background2 },
    line: { color: C.accent4, width: 0.75 }, objectName: name + " Kachel" });
  s.addText(big, { x: x + 0.25, y: y + 0.2, w: w - 0.5, h: 0.75, fontSize: 30, bold: true,
    color: bigColor || C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: name + " Wert" });
  s.addText(label, { x: x + 0.25, y: y + 1.0, w: w - 0.5, h: h - 1.15, fontSize: 12,
    color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: name + " Text" });
}

function numberedBlock(s, x, y, w, num, head, body, name) {
  s.addText(num, { x, y, w: 0.5, h: 0.45, fontSize: 20, bold: true, color: C.accent1, margin: 0,
    isTextBox: true, objectName: name + " Nummer" });
  s.addText(head, { x: x + 0.55, y, w: w - 0.55, h: 0.45, fontSize: 17, bold: true, color: C.text1,
    margin: 0, valign: "middle", isTextBox: true, objectName: name + " Titel" });
  s.addText(body, { x: x + 0.55, y: y + 0.5, w: w - 0.55, h: 1.6, fontSize: 14, color: C.text1,
    margin: 0, valign: "top", isTextBox: true, objectName: name + " Text" });
}

const cell = (text, o = {}) => ({ text, options: { fontSize: 13, color: C.text1, ...o } });
const head = (text, o = {}) => cell(text, { bold: true, color: C.text2, fontSize: 11, ...o });
const BORDER = { type: "solid", pt: 0.75, color: HEX.accent4 };
const tableOpts = (x, y, w, colW, extra = {}) => ({
  x, y, w, colW, border: [BORDER, { type: "none" }, BORDER, { type: "none" }],
  margin: [0.06, 0.1, 0.06, 0.1], valign: "middle", autoPage: false, ...extra,
});
const fmtDE = (v, nd = 0) => v.toLocaleString("de-DE", { minimumFractionDigits: nd, maximumFractionDigits: nd });

const CHART_TEXT = { catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.dk2,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 11,
  valAxisLabelFontSize: 11, valGridLine: { color: HEX.accent4, size: 0.5 },
  catGridLine: { style: "none" }, legendFontFace: "+mn-lt", legendFontSize: 11,
  legendColor: HEX.dk2, titleFontFace: "+mn-lt", titleColor: HEX.dk1, titleFontSize: 13,
  catAxisTitleFontFace: "+mn-lt", valAxisTitleFontFace: "+mn-lt", catAxisTitleColor: HEX.dk2,
  valAxisTitleColor: HEX.dk2, catAxisTitleFontSize: 11, valAxisTitleFontSize: 11 };

// ================================================================= 1 Titel
pres.addSection({ title: "Einleitung" });
{
  const s = pres.addSlide({ masterName: "TITEL", sectionTitle: "Einleitung" });
  s.addText("BLENDUNGSBEWERTUNG · LICHTTECHNIK", { placeholder: "eyebrow" });
  s.addText("SIRIUS 1000 mit außenliegender Blende: Lochung 3,4 % oder 50 %?", { placeholder: "title" });
  s.addText("Bewertung beider Blendenvarianten für eine sitzende Person 8 m hinter der Leuchte und " +
    "für Zuschauer in einer Arena, bei 5 m und 8 m Montagehöhe – inklusive Vergleich mit zwei " +
    "Lichtverteilungen ohne externe Blende",
    { placeholder: "subtitle" });
  s.addText("Rev. A  ·  23.10.2026  ·  Bearbeiter W. Rödel  ·  Status: Entwurf zur Prüfung",
    { placeholder: "meta" });
  s.addNotes("Ziel: Entscheidung, welche Blendenausführung aus Sicht der Blendung hinter der Leuchte " +
    "besser ist. Grundlage: gemessene LDT der SIRIUS 2000 (auf ein Modul halbiert), CAD-Modell der " +
    "Blende, Lichtberechnung in Blender/Cycles und analytisch aus der LVK.");
}

// ================================================================= 2 Ergebnis
{
  const s = content("Einleitung", "ERGEBNIS AUF EINEN BLICK",
    "Die gelieferte Blende blendet weniger als die 50-%-Lochung");
  const y = 1.85, h = 2.05, w = 2.85, gap = 0.233;
  kpi(s, 0.6, y, w, h, "24,0 → 26,8", "Glare Rating GR bei 5 m (Boden ρ 20 %). Grenzwerte 45–55: " +
    "beide unkritisch", "KPI GR");
  kpi(s, 0.6 + (w + gap), y, w, h, "+34 %", "Lichtstärke zur Person bei 5 m: 4.789 → 6.409 cd",
    "KPI Lichtstärke", C.accent2);
  kpi(s, 0.6 + 2 * (w + gap), y, w, h, "55 → 74 lx", "Beleuchtungsstärke am Auge bei 5 m. " +
    "Störlicht-Richtwert E4: 25 lx", "KPI Auge", C.accent2);
  kpi(s, 0.6 + 3 * (w + gap), y, w, h, "+48 %", "Mittlere Beleuchtungsstärke an der Rückwand " +
    "bei 5 m: 7,1 → 10,5 lx", "KPI Rückwand", C.accent2);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.25, w: 12.1, h: 2.0, fill: { color: C.accent3 },
    line: { type: "none" }, objectName: "Bewertung Hintergrund" });
  s.addText([
    { text: "Bewertung", options: { bold: true, fontSize: 16, color: C.accent1, breakLine: true } },
    { text: "Für die Blendung hinter der Leuchte ist die Blende wie geliefert (Lochung 3,4 %) " +
      "besser als die 50-%-Lochung. Die 50-%-Lochung bleibt nach Glare Rating unkritisch, lässt aber deutlich mehr " +
      "Licht zur Person und auf die Rückwand.", options: { fontSize: 15, breakLine: true,
      paraSpaceAfter: 6 } },
    { text: "Noch besser schneiden die Lichtverteilungen ohne externe Blende ab: Mit „Blende 2“ sinkt " +
      "die Blendung der Person auf GR 9,8 (5 m) – siehe Abschnitt „Ohne externe Blende“.",
      options: { fontSize: 15 } },
  ], { x: 0.9, y: 4.45, w: 11.5, h: 1.7, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    objectName: "Bewertung Text" });
  s.addNotes("Kernaussage: GR ist bei beiden Varianten weit unter den Grenzwerten. Die Unterschiede " +
    "zeigen sich bei Lichtstärke, Beleuchtungsstärke am Auge und an der Rückwand. Dort ist die " +
    "Blende wie geliefert klar besser.");
}

// ================================================================= 3 Situation
pres.addSection({ title: "Grundlagen" });
{
  const s = content("Grundlagen", "SITUATION", "Leuchte frei im Raum, Person sitzt 8 m dahinter");
  s.addImage({ path: IMG("uebersicht_5m.png"), x: 0.6, y: 1.8, w: 7.3, h: 4.818,
    altText: "Blender-Szene: Leuchte in 5 m Höhe, Maßstäbe, Person vor der Rückwand mit " +
      "Falschfarben-Messfeld", objectName: "Szene Übersicht" });
  s.addText("Blender-Szene mit Maßstäben und Messfeld an der Rückwand (5 m Montagehöhe)",
    { x: 0.6, y: 6.65, w: 7.3, h: 0.3, fontSize: 10, color: C.text2, margin: 0, isTextBox: true,
      objectName: "Bildunterschrift Szene" });
  const rows = [
    [head("PARAMETER"), head("WERT")],
    [cell("Leuchte"), cell("SIRIUS 1000, 1 Modul, 5000 K")],
    [cell("Lichtstrom"), cell("111.246 lm, 985,5 W")],
    [cell("Montage"), cell("Glas nach unten, 5 m / 8 m")],
    [cell("Hauptstrahl"), cell("nach vorn, C0, γ 35°")],
    [cell("Blende"), cell("hinten, zur Person, 200 mm")],
    [cell("Person"), cell("8 m hinter der Leuchte, sitzend, Augenhöhe 1,2 m")],
    [cell("Blickrichtung"), cell("nach vorn, 2° nach unten")],
    [cell("Raum"), cell("12 × 18 m, Reflexion 0 %")],
  ];
  s.addTable(rows, tableOpts(8.3, 1.8, 4.4, [1.45, 2.95]));
  s.addNotes("Die Leuchte strahlt von der Person weg. Die Person sieht die Leuchte schräg von hinten " +
    "unter γ 64,6° (5 m) bzw. 49,6° (8 m) in der C180-Ebene, also genau in dem Bereich, den die " +
    "Blende abschirmt.");
}

// ================================================================= 4 Varianten
{
  const s = content("Grundlagen", "DIE ZWEI LÖSUNGEN", "Gleiches Raster, Lochdurchmesser fast vervierfacht");
  s.addImage({ path: IMG("blende_vergleich.png"), x: 0.6, y: 1.85, w: 7.3, h: 3.65,
    altText: "Renderings der Blende: links mit 50 % Lochung (Ø 9,6 mm), rechts wie geliefert (Ø 2,5 mm)",
    objectName: "Blende Vergleich" });
  s.addText("Links: Lochung 50 % (Ø 9,57 mm) · rechts: wie geliefert (Ø 2,5 mm)",
    { x: 0.6, y: 5.6, w: 7.3, h: 0.3, fontSize: 10, color: C.text2, margin: 0, isTextBox: true,
      objectName: "Bildunterschrift Blende" });
  const rows = [
    [head(""), head("HEUTE"), head("LOCHUNG 50 %")],
    [cell("Lochdurchmesser"), cell("2,5 mm"), cell("9,57 mm", { bold: true })],
    [cell("Raster"), cell("12 mm quadr."), cell("12 mm quadr.")],
    [cell("Blechdicke"), cell("1,5 mm"), cell("1,5 mm")],
    [cell("Offene Fläche"), cell("3,4 %"), cell("50 %", { bold: true })],
    [cell("Steg"), cell("9,5 mm"), cell("2,4 mm")],
    [cell("Löcher"), cell("607"), cell("607")],
    [cell("LVK"), cell("gemessen"), cell("abgeschätzt", { color: C.accent2, bold: true })],
  ];
  s.addTable(rows, tableOpts(8.3, 1.85, 4.4, [1.75, 1.2, 1.45]));
  s.addText("Gelocht sind Stirnblech (325 Löcher) und beide Seitenwangen (je 141). Die Löcher wurden " +
    "im CAD-Modell an denselben Mittelpunkten aufgebohrt.", { x: 8.3, y: 5.3, w: 4.4, h: 1.2,
    fontSize: 12, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: "Hinweis Blende" });
  s.addNotes("Die Flächenbilanz der aufgebohrten Bleche wurde im CAD-Modell nachgeprüft. Die LVK der " +
    "50-%-Variante ist mit einem Strahlenmodell aus der gemessenen LVK abgeschätzt.");
}

// ================================================================= 5 LVK
{
  const s = content("Grundlagen", "LICHTVERTEILUNG", "Mehr Licht nach hinten nur dort, wo die Blende abdeckt");
  const labels = D.gamma.map((g) => (g % 15 === 0 ? String(g) : ""));
  const clamp = (a) => a.map((v) => Math.max(v, 1));
  s.addChart(pres.charts.LINE, [
    { name: "C180 nach hinten, heute", labels: D.gamma.map(String), values: clamp(D.c180_heute) },
    { name: "C180 nach hinten, Lochung 50 %", labels: D.gamma.map(String), values: clamp(D.c180_perf50) },
    { name: "C0 nach vorn", labels: D.gamma.map(String), values: clamp(D.c0) },
  ], {
    x: 0.6, y: 1.8, w: 8.0, h: 4.9, ...CHART_TEXT,
    chartColors: [HEX.dk1, HEX.accent2, HEX.accent4], lineSize: 2, lineDataSymbol: "none",
    valAxisLogScaleBase: 10, valAxisMinVal: 1, valAxisMaxVal: 100000,
    showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "Lichtstärke [cd]",
    showCatAxisTitle: true, catAxisTitle: "Ausstrahlungswinkel γ [°] (0 = senkrecht nach unten)",
    catAxisLabelFrequency: 3, objectName: "LVK Diagramm",
  });
  const rows = [
    [head("C180, γ"), head("HEUTE"), head("50 %")],
    [cell("49,6° (Person 8 m)"), cell("10.371 cd"), cell("11.647 cd")],
    [cell("64,6° (Person 5 m)"), cell("4.789 cd"), cell("6.409 cd")],
    [cell("75°"), cell("287 cd"), cell("1.710 cd")],
    [cell("80°"), cell("48 cd"), cell("793 cd")],
  ];
  s.addTable(rows, tableOpts(8.8, 1.85, 3.9, [1.9, 1.0, 1.0]));
  s.addText("Ab etwa 72° liegt die ganze Lichtaustrittsfläche hinter der Blende. Dort lässt heute nur " +
    "die Lochung Licht durch, künftig ein Vielfaches. Gesamtlichtstrom +2,3 %.",
    { x: 8.8, y: 4.25, w: 3.9, h: 2.0, fontSize: 13, color: C.text1, margin: 0, valign: "top",
      isTextBox: true, objectName: "LVK Kommentar" });
  s.addNotes("Logarithmische Achse. Die C0-Seite (nach vorn) ist unverändert. Die Erhöhung betrifft " +
    "nur die C180-Seite ab etwa 50°, also die Richtung zur Person und zur Rückwand.");
}

// ================================================================= 6 Methode
{
  const s = content("Grundlagen", "BEWERTUNGSVERFAHREN", "Glare Rating als Maßstab, ergänzt um Licht am Auge");
  numberedBlock(s, 0.6, 1.9, 3.85, "1", "Glare Rating GR",
    "CIE 112 / EN 12464-2:\nGR = 27 + 24 · log(L_vl / L_ve^0,9)\nSkala 10 (unmerklich) bis 90 " +
    "(unerträglich). Grenzwerte 45–55.", "Methode GR");
  numberedBlock(s, 4.73, 1.9, 3.85, "2", "Schleierleuchtdichte",
    "Leuchte: L_vl = 10 · E_Auge / θ²\nUmgebung: L_ve = 0,035 · ρ · E_h / π\nθ = Winkel zwischen " +
    "Blickrichtung und Leuchte.", "Methode Schleier");
  numberedBlock(s, 8.86, 1.9, 3.85, "3", "Licht am Auge",
    "Lichtstärke zur Person und vertikale Beleuchtungsstärke E_v, eingeordnet an den " +
    "Störlicht-Richtwerten (EN 12464-2 / CIE 150).", "Methode Störlicht");
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.0, w: 12.1, h: 2.05, fill: { color: C.background2 },
    line: { color: C.accent4, width: 0.75 }, objectName: "Annahmen Kasten" });
  s.addText([
    { text: "Annahmen", options: { bold: true, color: C.accent1, fontSize: 15, breakLine: true } },
    { text: "Blick horizontal nach vorn, 2° nach unten (CIE 112)", options: { bullet: true, breakLine: true } },
    { text: "GR braucht Umgebungsleuchtdichte: gerechnet mit Boden-Reflexionsgrad ρ = 20 % (10 % und 30 % " +
      "zum Vergleich). Bei 0 % wäre GR nicht definiert.", options: { bullet: true, breakLine: true } },
    { text: "Wirkung der Blende steckt in der LVK; Person nicht als Hindernis berücksichtigt",
      options: { bullet: true } },
  ], { x: 0.9, y: 4.15, w: 11.5, h: 1.8, fontSize: 14, color: C.text1, margin: 0, valign: "top",
    paraSpaceAfter: 4, isTextBox: true, objectName: "Annahmen Text" });
  s.addNotes("UGR nach EN 12464-1 ist für eine einzelne Flutlichtleuchte ohne Innenraum-Hintergrund " +
    "nicht anwendbar, deshalb GR nach CIE 112.");
}

// ================================================================= 7 Ergebnisse Tabelle
pres.addSection({ title: "Ergebnisse" });
{
  const s = content("Ergebnisse", "ERGEBNISSE AM AUGE DER PERSON",
    "Die 50-%-Lochung erhöht alle Werte, GR bleibt weit unter 45");
  const hl = { fill: { color: HEX.accent3 } };
  const rows = [
    [head(""), head("5 m · HEUTE"), head("5 m · LOCHUNG 50 %"), head("8 m · HEUTE"), head("8 m · LOCHUNG 50 %")],
    [cell("Abstand Auge – Leuchte"), cell("8,86 m"), cell("8,86 m"), cell("10,50 m"), cell("10,50 m")],
    [cell("Winkel zur Blickrichtung θ"), cell("27,4°"), cell("27,4°"), cell("42,4°"), cell("42,4°")],
    [cell("Ausstrahlungswinkel (C180)"), cell("γ 64,6°"), cell("γ 64,6°"), cell("γ 49,6°"), cell("γ 49,6°")],
    [cell("Lichtstärke zur Person"), cell("4.789 cd"), cell("6.409 cd", { color: C.accent2, bold: true }),
      cell("10.371 cd"), cell("11.647 cd", { color: C.accent2, bold: true })],
    [cell("Sichtbarer Glasanteil"), cell("46 %"), cell("70 %"), cell("69 %"), cell("82 %")],
    [cell("Leuchtdichte sichtbares Glas"), cell("107 kcd/m²"), cell("94 kcd/m²"), cell("101 kcd/m²"), cell("96 kcd/m²")],
    [cell("E_v am Auge"), cell("55 lx"), cell("74 lx", { color: C.accent2, bold: true }), cell("72 lx"),
      cell("81 lx", { color: C.accent2, bold: true })],
    [cell("Schleierleuchtdichte L_vl"), cell("0,72 cd/m²"), cell("0,97 cd/m²"), cell("0,39 cd/m²"), cell("0,44 cd/m²")],
    [cell("GR (ρ 20 %)", { bold: true, ...hl }), cell("24,0", { bold: true, ...hl }), cell("26,8", { bold: true, ...hl }),
      cell("21,0", { bold: true, ...hl }), cell("22,1", { bold: true, ...hl })],
    [cell("GR (ρ 10 % / 30 %)"), cell("30,5 / 20,1"), cell("33,3 / 23,0"), cell("27,5 / 17,2"), cell("28,6 / 18,3")],
  ];
  s.addTable(rows, tableOpts(0.6, 1.8, 12.1, [3.3, 2.2, 2.2, 2.2, 2.2]));
  s.addNotes("Orange markiert: Werte, die sich mit der 50-%-Lochung verschlechtern. Die Leuchtdichte " +
    "des sichtbaren Glases bleibt bei etwa 100 kcd/m²; man sieht durch die Lochung nur mehr Glasfläche.");
}

// ================================================================= 8 GR über Abstand
{
  const s = content("Ergebnisse", "GLARE RATING ÜBER DEN ABSTAND", "GR bleibt an jeder Position hinter der Leuchte unter 32");
  const sw = D.sweep;
  const lab = sw.heute_5.d.map((d) => fmtDE(d, 1));
  s.addChart(pres.charts.LINE, [
    { name: "5 m, heute", labels: lab, values: sw.heute_5.GR },
    { name: "5 m, Lochung 50 %", labels: lab, values: sw.perf50_5.GR },
    { name: "8 m, heute", labels: lab, values: sw.heute_8.GR },
    { name: "8 m, Lochung 50 %", labels: lab, values: sw.perf50_8.GR },
    { name: "Grenzwert Sport-Wettkampf GR 50", labels: lab, values: lab.map(() => 50) },
  ], {
    x: 0.6, y: 1.8, w: 8.3, h: 4.9, ...CHART_TEXT,
    chartColors: [HEX.accent1, HEX.accent2, HEX.dk1, "C58A3A", HEX.accent4],
    lineSize: 2, lineDataSymbol: "none", valAxisMinVal: 0, valAxisMaxVal: 60, valAxisMajorUnit: 10,
    showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "GR (Boden ρ 20 %)",
    showCatAxisTitle: true, catAxisTitle: "Abstand hinter der Leuchte [m]", catAxisLabelFrequency: 2,
    objectName: "GR Diagramm",
  });
  s.addText([
    { text: "5 m: ", options: { bold: true } },
    { text: "Maximum bei etwa 4,5 m hinter der Leuchte, GR 30 (heute) bzw. 31 (50 %). An der Person " +
      "(8 m) 24,0 gegen 26,8.", options: { breakLine: true, paraSpaceAfter: 10 } },
    { text: "8 m: ", options: { bold: true } },
    { text: "GR steigt bis zur Person stetig an, die Kurven liegen nah beieinander (21,0 gegen 22,1).",
      options: { breakLine: true, paraSpaceAfter: 10 } },
    { text: "Die höhere Montage senkt GR, weil die Leuchte weiter aus dem Blickfeld rückt.",
      options: {} },
  ], { x: 9.2, y: 1.9, w: 3.5, h: 4.7, fontSize: 14, color: C.text1, margin: 0, valign: "top",
    isTextBox: true, objectName: "GR Kommentar" });
  s.addNotes("GR-Skala: 10 unmerklich, 30 merklich, 50 störend, 70 unzumutbar, 90 unerträglich.");
}

// ================================================================= 9 E_v am Auge
{
  const s = content("Ergebnisse", "LICHT AM AUGE", "Am Auge liegen beide Lösungen über jedem Störlicht-Richtwert");
  const sw = D.sweep;
  const lab = sw.heute_5.d.map((d) => fmtDE(d, 1));
  s.addChart(pres.charts.LINE, [
    { name: "5 m, heute", labels: lab, values: sw.heute_5.Ev },
    { name: "5 m, Lochung 50 %", labels: lab, values: sw.perf50_5.Ev },
    { name: "8 m, heute", labels: lab, values: sw.heute_8.Ev },
    { name: "8 m, Lochung 50 %", labels: lab, values: sw.perf50_8.Ev },
    { name: "Richtwert E4 vor Sperrzeit (25 lx)", labels: lab, values: lab.map(() => 25) },
  ], {
    x: 0.6, y: 1.8, w: 8.3, h: 4.9, ...CHART_TEXT,
    chartColors: [HEX.accent1, HEX.accent2, HEX.dk1, "C58A3A", HEX.accent4],
    lineSize: 2, lineDataSymbol: "none", valAxisMinVal: 0, valAxisMaxVal: 350, valAxisMajorUnit: 50,
    showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "E_v am Auge [lx]",
    showCatAxisTitle: true, catAxisTitle: "Abstand hinter der Leuchte [m]", catAxisLabelFrequency: 2,
    objectName: "Ev Diagramm",
  });
  const rows = [
    [head("AN DER PERSON"), head("HEUTE"), head("50 %")],
    [cell("E_v, 5 m"), cell("55 lx"), cell("74 lx")],
    [cell("E_v, 8 m"), cell("72 lx"), cell("81 lx")],
    [cell("I, 5 m"), cell("4.789 cd"), cell("6.409 cd")],
    [cell("I, 8 m"), cell("10.371 cd"), cell("11.647 cd")],
  ];
  s.addTable(rows, tableOpts(9.2, 1.85, 3.5, [1.3, 1.1, 1.1]));
  s.addText("Richtwerte vor Sperrzeit: E_v 5 / 10 / 25 lx (E2 / E3 / E4), Lichtstärke 7.500 / 10.000 / " +
    "25.000 cd. Sie gelten für Fenster von Anwohnern und dienen hier zur Einordnung.",
    { x: 9.2, y: 4.25, w: 3.5, h: 2.3, fontSize: 12, color: C.text2, margin: 0, valign: "top",
      isTextBox: true, objectName: "Störlicht Hinweis" });
  s.addNotes("Die Lichtstärke hält bei 5 m die Richtwerte für E2 bis E4 ein (beide Varianten), bei 8 m " +
    "nur E4. Die Beleuchtungsstärke am Auge überschreitet in jeder Zone.");
}

// ================================================================= 10 Rückwand
{
  const s = content("Ergebnisse", "AUFHELLUNG HINTER DER PERSON", "An der Rückwand wird es mit 50 % Lochung deutlich heller");
  const iw = 5.9, ih = 5.9 * 0.5408;
  s.addText("Heute (Lochung 3,4 %) · 5 m", { x: 0.6, y: 1.75, w: iw, h: 0.35, fontSize: 14, bold: true,
    color: C.text1, margin: 0, isTextBox: true, objectName: "Rückwand heute Titel" });
  s.addImage({ path: IMG("mf_5m_heute.png"), x: 0.6, y: 2.15, w: iw, h: ih,
    altText: "Falschfarben der vertikalen Beleuchtungsstärke an der Rückwand, Blende heute, 5 m",
    objectName: "Rückwand heute" });
  s.addText("Lochung 50 % · 5 m", { x: 6.8, y: 1.75, w: iw, h: 0.35, fontSize: 14, bold: true,
    color: C.accent2, margin: 0, isTextBox: true, objectName: "Rückwand 50 Titel" });
  s.addImage({ path: IMG("mf_5m_perf50.png"), x: 6.8, y: 2.15, w: iw, h: ih,
    altText: "Falschfarben der vertikalen Beleuchtungsstärke an der Rückwand, Lochung 50 %, 5 m",
    objectName: "Rückwand 50" });
  const rows = [
    [head("RÜCKWAND, 10 m HINTER DER LEUCHTE"), head("HEUTE"), head("LOCHUNG 50 %"), head("ÄNDERUNG")],
    [cell("5 m: Emittel / Emax"), cell("7,1 / 37,3 lx"), cell("10,5 / 49,1 lx"), cell("+48 % / +32 %", { color: C.accent2, bold: true })],
    [cell("8 m: Emittel / Emax"), cell("16,1 / 48,0 lx"), cell("20,5 / 54,6 lx"), cell("+27 % / +14 %", { color: C.accent2, bold: true })],
  ];
  s.addTable(rows, tableOpts(0.6, 5.5, 12.1, [4.3, 2.6, 2.6, 2.6]));
  s.addNotes("Messfeld 2 cm vor der Rückwand, Reflexion im Raum 0 %, also reines Direktlicht aus der " +
    "LVK. Oberhalb von etwa 4 m bleibt es bei beiden Varianten fast dunkel.");
}

// ================================================================= 11 Matrix
pres.addSection({ title: "Bewertung" });
{
  const s = content("Bewertung", "BEWERTUNGSMATRIX", "In allen Blendungskriterien liegt die Blende wie geliefert vorn");
  const win = (t) => cell(t, { bold: true, color: C.accent1 });
  const eq = (t) => cell(t, { color: C.text2 });
  const rows = [
    [head("KRITERIUM"), head("HEUTE (3,4 %)"), head("LOCHUNG 50 %"), head("VORTEIL")],
    [cell("Glare Rating, 5 m"), cell("24,0"), cell("26,8"), win("heute")],
    [cell("Glare Rating, 8 m"), cell("21,0"), cell("22,1"), win("heute (knapp)")],
    [cell("Lichtstärke zur Person, 5 m"), cell("4.789 cd"), cell("6.409 cd"), win("heute")],
    [cell("Beleuchtungsstärke am Auge, 5 m"), cell("55 lx"), cell("74 lx"), win("heute")],
    [cell("Leuchtdichte sichtbares Glas"), cell("≈ 107 kcd/m²"), cell("≈ 94 kcd/m²"), eq("gleichwertig, beide sehr hoch")],
    [cell("Aufhellung Rückwand, 5 m"), cell("7,1 lx"), cell("10,5 lx"), win("heute")],
    [cell("Nutzlichtstrom"), cell("111.246 lm"), cell("≈ 113.650 lm"), cell("50 % (+2 %)", { color: C.accent2, bold: true })],
    [cell("Datengrundlage"), cell("gemessene LDT"), cell("abgeschätzte LVK"), win("heute")],
  ];
  s.addTable(rows, tableOpts(0.6, 1.8, 12.1, [4.0, 2.5, 2.5, 3.1]));
  s.addText("Die 50-%-Lochung bringt nur beim Lichtstrom einen kleinen Gewinn. Dieser Mehrlichtstrom " +
    "geht nach hinten, also genau dorthin, wo er blendet und aufhellt.", { x: 0.6, y: 5.45, w: 12.1,
    h: 0.75, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    objectName: "Matrix Fazit" });
  s.addNotes("Gleichwertig bei der Leuchtdichte: Die Leuchtdichte des Glases ändert sich nicht, nur die " +
    "sichtbare Fläche. Für die Bewertung zählt deshalb vor allem Lichtstärke und GR.");
}

// ================================================================= 12 Empfehlung
{
  const s = content("Bewertung", "EMPFEHLUNG", "Blende wie geliefert beibehalten, 50 % nur nach Messung");
  const items = [
    ["1", "Blende wie geliefert beibehalten", "Wenn die Blendung hinter der Leuchte das Kriterium ist, " +
      "ist die Lochung 3,4 % in allen Punkten besser."],
    ["2", "Falls 50 % gewünscht: 8 m bevorzugen", "Bei 8 m steigt die Lichtstärke zur Person nur um 12 %, " +
      "GR um 1,1. Bei 5 m sind es 34 % und 2,8."],
    ["3", "LVK der 50-%-Variante messen", "Die neue LVK ist abgeschätzt. Vor einer Entscheidung am " +
      "Goniophotometer messen."],
    ["4", "Störlicht prüfen", "E_v am Auge liegt bei beiden Varianten über E4. Bei Anwohnern oder " +
      "Arbeitsplätzen hinter der Leuchte: Neigung, Abstand oder geschlossene Blende prüfen."],
  ];
  items.forEach(([n, h, b], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    numberedBlock(s, 0.6 + col * 6.2, 1.9 + row * 2.35, 5.9, n, h, b, "Empfehlung " + n);
  });
  s.addNotes("Reihenfolge nach Wirkung: Die Wahl der Blende hat den größten Einfluss auf die Blendung " +
    "hinter der Leuchte; die Montagehöhe beeinflusst GR und Licht am Auge gegenläufig.");
}

// ================================================================= Arena
pres.addSection({ title: "Arena" });
{
  const s = content("Arena", "ARENA · BELEUCHTUNGSSTÄRKE",
    "Arena: 8 m erreicht Klasse I, 5 m ist zu ungleichmäßig");
  s.addImage({ path: IMG("arena_beleuchtung.png"), x: 0.6, y: 1.75, w: 8.0, h: 4.103,
    altText: "Falschfarben der horizontalen Beleuchtungsstärke in der Halle bei 5 m und 8 m " +
      "Montagehöhe, drei Leuchten im Abstand von 6 m", objectName: "Arena Beleuchtung" });
  s.addText("Drei Leuchten im Abstand von 6 m, Blende heute, Direktlicht, Wartungsfaktor 0,8. " +
    "Gestrichelt: Bewertungsfeld 18 × 8 m. Reihe = durchgehende Reihe mit Leuchten alle 6 m.", { x: 0.6, y: 5.95, w: 8.0, h: 0.5, fontSize: 10,
    color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: "Arena Bildunterschrift" });
  const ok = (t) => cell(t, { bold: true, color: C.accent1 });
  const no = (t) => cell(t, { color: C.accent2, bold: true });
  const rows = [
    [head("FELD 18 × 8 m"), head("Ē"), head("U0"), head("EN 12193")],
    [cell("3 Leuchten, 5 m"), cell("1.166 lx"), cell("0,16"), no("keine")],
    [cell("3 Leuchten, 8 m"), cell("832 lx"), cell("0,46"), no("keine")],
    [cell("Reihe, 5 m"), cell("1.349 lx"), cell("0,24"), no("keine")],
    [cell("Reihe, 8 m"), cell("1.080 lx"), cell("0,70"), ok("Klasse I")],
  ];
  s.addTable(rows, tableOpts(8.85, 1.8, 3.85, [1.55, 0.85, 0.55, 0.9], { fontSize: 12 }));
  s.addText("Der Mittelwert reicht überall für Klasse I (750 lx). Bei 5 m entsteht ein heller Fleck " +
    "3 m vor der Reihe. Eine einseitige Reihe leuchtet etwa 8 m tief; ein ganzes Spielfeld braucht " +
    "weitere Reihen.", { x: 8.85, y: 4.15, w: 3.85, h: 2.4, fontSize: 13, color: C.text1, margin: 0,
    valign: "top", isTextBox: true, objectName: "Arena Kommentar" });
  s.addNotes("EN 12193 Hallensport (Handball, Basketball, Volleyball): Klasse I 750 lx / U0 0,7, " +
    "Klasse II 500 lx / U0 0,7, Klasse III 200 lx / U0 0,5. Die 50-%-Lochung ändert die " +
    "Feldwerte nur um etwa 1 %.");
}
{
  const s = content("Arena", "ARENA · BLENDUNG DER ZUSCHAUER",
    "Zuschauer kaum geblendet, gelieferte Blende bleibt besser");
  s.addImage({ path: IMG("arena_blendung.png"), x: 0.6, y: 1.7, w: 6.6, h: 4.824,
    altText: "Karten des Glare Rating für Zuschauerplätze hinter der Leuchtenreihe, beide Blenden, " +
      "5 m und 8 m Montagehöhe", objectName: "Arena Blendungskarten" });
  const rows = [
    [head("GR ZUSCHAUER"), head("HEUTE"), head("50 %")],
    [cell("5 m, Platz 8 m dahinter"), cell("14,6"), cell("17,3", { color: C.accent2, bold: true })],
    [cell("5 m, ungünstigster Platz"), cell("19"), cell("20")],
    [cell("8 m, Platz 8 m dahinter"), cell("13,2"), cell("14,4", { color: C.accent2, bold: true })],
    [cell("8 m, ungünstigster Platz"), cell("13"), cell("15")],
    [cell("E_v am Auge, 5 m"), cell("76 lx"), cell("99 lx", { color: C.accent2, bold: true })],
  ];
  s.addTable(rows, tableOpts(7.5, 1.8, 5.2, [2.6, 1.3, 1.3]));
  s.addText("Alle Werte liegen weit unter „störend“ (GR 50). Die Zuschauer schauen in die helle Arena, " +
    "das dämpft die Blendung. Am stärksten blendet es bei 5 m auf den Plätzen 4–6 m hinter der " +
    "Reihe, direkt unter der Blendenkante.", { x: 7.5, y: 4.55, w: 5.2, h: 2.0, fontSize: 13,
    color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "Arena Blendung Kommentar" });
  s.addNotes("GR nach CIE 112 mit drei Leuchten, Augenhöhe 1,2 m, Blick in die Halle 2° nach unten, " +
    "Hallenboden ρ 20 %, Umgebungsleuchtdichte aus dem mittleren E_h des Feldes. Auf einer " +
    "ansteigenden Tribüne können hintere Reihen stärker geblendet werden.");
}
{
  const s = content("Arena", "ARENA · EMPFEHLUNG", "Für die Arena: gelieferte Blende und 8 m Montagehöhe");
  const items = [
    ["1", "Blende wie geliefert", "Die 50-%-Lochung bringt dem Spielfeld nur etwa 1 % mehr Licht, " +
      "erhöht aber die Blendung der Zuschauer (GR +1 bis +3) und das Licht am Auge."],
    ["2", "Montagehöhe 8 m", "Gleichmäßiges Feld (U0 0,70 mit durchgehender Reihe, Klasse I) und " +
      "geringere Blendung der Zuschauer als bei 5 m."],
    ["3", "Reihe durchgehend planen", "Mit nur drei Leuchten fällt das Licht an den Rändern ab. Für ein " +
      "ganzes Spielfeld weitere Reihen oder die Gegenseite einplanen."],
    ["4", "50 % nur für TV-Tribünenlicht", "Soll die Tribüne für Übertragungen bewusst aufgehellt " +
      "werden, kann die 50-%-Lochung sinnvoll sein; dann die LVK vorher messen."],
  ];
  items.forEach(([n, h, b], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    numberedBlock(s, 0.6 + col * 6.2, 1.9 + row * 2.35, 5.9, n, h, b, "Arena Empfehlung " + n);
  });
  s.addNotes("Die Empfehlung gilt für Zuschauer hinter der Leuchtenreihe, die in die Halle schauen. " +
    "Für konkrete Spielfeldmaße und Sportart sollte die Anlage vollständig gerechnet werden.");
}

// ================================================================= Varianten ohne externe Blende
pres.addSection({ title: "Ohne externe Blende" });
{
  const s = content("Ohne externe Blende", "VIER LICHTVERTEILUNGEN IM VERGLEICH",
    "Ohne externe Blende geht deutlich weniger Licht nach hinten");
  const clamp = (a) => a.map((v) => Math.max(v, 1));
  const lab = D.gamma.map(String);
  s.addChart(pres.charts.LINE, [
    { name: "V2 heute (3,4 %)", labels: lab, values: clamp(D.c180_heute) },
    { name: "V2 Lochung 50 %", labels: lab, values: clamp(D.c180_perf50) },
    { name: "ohne ext. Blende – Blende 2", labels: lab, values: clamp(D.c180_b2) },
    { name: "ohne ext. Blende – Blende 3", labels: lab, values: clamp(D.c180_b3) },
  ], {
    x: 0.6, y: 1.8, w: 7.9, h: 4.9, ...CHART_TEXT,
    chartColors: [HEX.dk1, HEX.accent2, HEX.accent1, HEX.accent5], lineSize: 2,
    lineDataSymbol: "none", valAxisLogScaleBase: 10, valAxisMinVal: 1, valAxisMaxVal: 100000,
    showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "Lichtstärke [cd], C180",
    showCatAxisTitle: true, catAxisTitle: "Ausstrahlungswinkel γ nach hinten [°]",
    catAxisLabelFrequency: 3, objectName: "Vergleich LVK C180",
  });
  const rows = [
    [head("C180, γ"), head("V2"), head("B2"), head("B3")],
    [cell("49,6° (8 m)"), cell("10.371"), cell("4.874"), cell("5.383")],
    [cell("64,6° (5 m)"), cell("4.789"), cell("1.290"), cell("1.905")],
    [cell("über 90°, vorn"), cell("≤ 1.000"), cell("0"), cell("0")],
  ];
  s.addTable(rows, tableOpts(8.8, 1.85, 3.9, [1.45, 0.95, 0.75, 0.75], { fontSize: 12 }));
  s.addText("Werte in cd bei je 111.246 lm. B2 und B3 sind relative LDT (4000 K, CRI 70), auf den " +
    "gleichen Lichtstrom gesetzt und um 90° gedreht (Hauptstrahl C90 → C0). Ohne externe Blende " +
    "kein Licht über die Horizontale.", { x: 8.8, y: 3.9, w: 3.9, h: 2.7, fontSize: 12,
    color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: "Vergleich LVK Hinweis" });
  s.addNotes("Die Namen Blende 2/3 und der harte Abfall in den Daten deuten auf eine interne Blende in " +
    "der Optik hin. Der Hauptstrahl ist bei B2/B3 etwa 10 % kräftiger als bei V2.");
}
{
  const s = content("Ohne externe Blende", "PERSON 8 m HINTER DER LEUCHTE",
    "Blende 2 halbiert die Blendung der Person gegenüber V2");
  const cats = ["V2 heute", "V2 50 %", "Blende 2", "Blende 3"];
  s.addChart(pres.charts.BAR, [
    { name: "5 m Montagehöhe", labels: cats, values: [24.0, 26.8, 9.8, 14.0] },
    { name: "8 m Montagehöhe", labels: cats, values: [21.0, 22.1, 12.4, 13.7] },
  ], {
    x: 0.6, y: 1.8, w: 5.9, h: 4.9, barDir: "col", barGrouping: "clustered", ...CHART_TEXT,
    chartColors: [HEX.accent1, HEX.accent4], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFontSize: 11, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt",
    dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 30, valAxisMajorUnit: 5,
    showLegend: true, legendPos: "b", showTitle: true, title: "GR der Person (Boden ρ 20 %)",
    objectName: "Vergleich GR Person",
  });
  const best = (t) => cell(t, { bold: true, color: C.accent1 });
  const rows = [
    [head(""), head("V2"), head("V2 50 %"), head("B2"), head("B3")],
    [cell("I zur Person, 5 m"), cell("4.789 cd"), cell("6.409 cd"), best("1.290 cd"), cell("1.905 cd")],
    [cell("I zur Person, 8 m"), cell("10.371 cd"), cell("11.647 cd"), best("4.874 cd"), cell("5.383 cd")],
    [cell("E_v Auge, 5 m"), cell("55 lx"), cell("74 lx"), best("15 lx"), cell("22 lx")],
    [cell("E_v Auge, 8 m"), cell("72 lx"), cell("81 lx"), best("34 lx"), cell("37 lx")],
    [cell("Rückwand Ē, 5 m"), cell("7,1 lx"), cell("10,4 lx"), best("2,5 lx"), cell("3,4 lx")],
    [cell("Rückwand Ē, 8 m"), cell("16,0 lx"), cell("20,3 lx"), best("5,3 lx"), cell("6,6 lx")],
  ];
  s.addTable(rows, tableOpts(6.75, 1.85, 5.95, [1.75, 1.05, 1.05, 1.05, 1.05], { fontSize: 11 }));
  s.addText("Mit Blende 2 bleibt die Beleuchtungsstärke am Auge bei 5 m unter dem Störlicht-Richtwert " +
    "E4 (25 lx).", { x: 6.75, y: 5.3, w: 5.95, h: 0.9, fontSize: 13, color: C.text1, margin: 0,
    valign: "top", isTextBox: true, objectName: "Vergleich Person Kommentar" });
  s.addNotes("Gleiche Methode wie in den vorigen Abschnitten: eine Leuchte, Person sitzend 8 m dahinter, " +
    "Blick nach vorn 2° nach unten, GR nach CIE 112. Ohne externe Blende ist die ganze Glasfläche sichtbar.");
}
{
  const s = content("Ohne externe Blende", "ARENA · BLENDUNG UND FELD",
    "Arena: B2 und B3 blenden kaum, V2 hält Klasse I besser");
  s.addImage({ path: IMG("vergleich_arena.png"), x: 0.6, y: 1.7, w: 8.6, h: 3.937,
    altText: "GR-Karten der Zuschauer für V2, V2 50 %, Blende 2 und Blende 3 bei 5 m und 8 m",
    objectName: "Vergleich Arena Karten" });
  const ok = (t) => cell(t, { bold: true, color: C.accent1 });
  const rows = [
    [head("8 m, REIHE"), head("Ē"), head("U0"), head("KLASSE")],
    [cell("V2"), cell("1.080 lx"), cell("0,70"), ok("I")],
    [cell("V2 50 %"), cell("1.094 lx"), cell("0,70"), ok("I")],
    [cell("Blende 2"), cell("1.235 lx"), cell("0,64"), cell("III", { color: C.accent2, bold: true })],
    [cell("Blende 3"), cell("1.179 lx"), cell("0,69"), cell("III", { color: C.accent2, bold: true })],
  ];
  s.addTable(rows, tableOpts(9.45, 1.8, 3.25, [0.95, 0.85, 0.55, 0.9], { fontSize: 12 }));
  s.addText("GR der Zuschauer bei 8 m: max 13 (V2), 15 (V2 50 %), 7 (B2), 9 (B3). B2/B3 bündeln " +
    "stärker: helleres Feld, etwas geringere Gleichmäßigkeit.", { x: 9.45, y: 4.2, w: 3.25, h: 2.3,
    fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    objectName: "Vergleich Arena Kommentar" });
  s.addText("Drei Leuchten im Abstand von 6 m bzw. durchgehende Reihe, Wartungsfaktor 0,8, je 111.246 lm",
    { x: 0.6, y: 5.75, w: 8.6, h: 0.35, fontSize: 10, color: C.text2, margin: 0, isTextBox: true,
      objectName: "Vergleich Arena Bildunterschrift" });
  s.addNotes("U0 0,69 bei Blende 3 liegt knapp unter der Grenze für Klasse I; mit leichter Neigung oder " +
    "etwas kleinerem Abstand dürfte Klasse I erreichbar sein (zu prüfen).");
}
{
  const s = content("Ohne externe Blende", "GESAMTBEWERTUNG",
    "Für Blendung und Störlicht ist Blende 2 die beste Lösung");
  const win = (t) => cell(t, { bold: true, color: C.accent1 });
  const rows = [
    [head("KRITERIUM"), head("V2 HEUTE"), head("V2 50 %"), head("BLENDE 2"), head("BLENDE 3")],
    [cell("Blendung Person (GR 5 m / 8 m)"), cell("24,0 / 21,0"), cell("26,8 / 22,1"), win("9,8 / 12,4"), cell("14,0 / 13,7")],
    [cell("Licht am Auge (E_v 5 m)"), cell("55 lx"), cell("74 lx"), win("15 lx"), cell("22 lx")],
    [cell("Blendung Zuschauer (GR max 8 m)"), cell("13"), cell("15"), win("7"), cell("9")],
    [cell("Aufhellung Rückwand (Ē 5 m)"), cell("7,1 lx"), cell("10,4 lx"), win("2,5 lx"), cell("3,4 lx")],
    [cell("Licht über die Horizontale"), cell("bis 1.000 cd"), cell("bis 1.000 cd"), win("keins"), win("keins")],
    [cell("Feld 8 m, durchgehende Reihe"), win("Klasse I"), win("Klasse I"), cell("Klasse III (U0 0,64)"), cell("Klasse III (U0 0,69)")],
    [cell("Datengrundlage"), win("gemessen, absolut"), cell("abgeschätzt"), cell("relativ, 4000 K"), cell("relativ, 4000 K")],
  ];
  s.addTable(rows, tableOpts(0.6, 1.8, 12.1, [3.4, 2.15, 2.15, 2.2, 2.2], { fontSize: 12 }));
  s.addText([
    { text: "Empfehlung: ", options: { bold: true, color: C.accent1 } },
    { text: "Blende 2 oder Blende 3 bei 8 m Montagehöhe statt der außenliegenden Blende V2. Vorher die " +
      "absoluten Lichtströme der Ausführungen ohne Blende beim Hersteller abfragen und für Klasse I die " +
      "Gleichmäßigkeit mit Neigung oder Abstand nachweisen." },
  ], { x: 0.6, y: 5.0, w: 12.1, h: 1.0, fontSize: 14, color: C.text1, margin: 0, valign: "top",
    isTextBox: true, objectName: "Gesamtbewertung Empfehlung" });
  s.addNotes("Der Vergleich gilt bei gleichem Lichtstrom. Weichen die echten Lichtströme ab, ändern sich " +
    "alle Lux- und Candela-Werte im selben Verhältnis, die Rangfolge bei der Blendung aber kaum.");
}

// ================================================================= Neue außenliegende Blende
pres.addSection({ title: "Neue außenliegende Blende" });
{
  const s = content("Neue außenliegende Blende", "AUSLEGUNG",
    "Ein 450 mm tiefes Stirnblech bildet Blende 3 außen nach");
  s.addImage({ path: IMG("ansicht_b3a_hinten.png"), x: 0.8, y: 1.85, w: 4.0, h: 3.362,
    altText: "SIRIUS 1000 mit neuer außenliegender Blende, Ansicht von hinten unten",
    objectName: "Neue Blende Ansicht hinten" });
  s.addText("Neue Blende B3a von hinten unten; Unter- und Seitenkanten 20 mm gekantet", { x: 0.8, y: 5.35, w: 4.0, h: 0.35,
    fontSize: 10, color: C.text2, margin: 0, isTextBox: true, objectName: "Neue Blende Bildunterschrift" });
  s.addText("V2 heute (211 mm)", { x: 5.45, y: 1.8, w: 3.0, h: 0.3, fontSize: 11, bold: true,
    color: C.text2, margin: 0, isTextBox: true, objectName: "Seitenansicht V2 Titel" });
  s.addImage({ path: IMG("ansicht_v2_seite.png"), x: 5.45, y: 2.15, w: 3.0, h: 1.397,
    altText: "Seitenansicht mit Blende V2", objectName: "Seitenansicht V2" });
  s.addText("B3a neu (450 mm)", { x: 5.45, y: 3.8, w: 3.0, h: 0.3, fontSize: 11, bold: true,
    color: C.accent1, margin: 0, isTextBox: true, objectName: "Seitenansicht B3a Titel" });
  s.addImage({ path: IMG("ansicht_b3a_seite.png"), x: 5.45, y: 4.1, w: 3.0, h: 2.15,
    altText: "Seitenansicht mit neuer Blende B3a", objectName: "Seitenansicht B3a" });
  kpi(s, 8.75, 1.85, 3.95, 1.45, "450 mm", "Stirnblech senkrecht; Seitenwangen wie V2, " +
    "211 → 89 mm tief", "Tiefe", C.accent1);
  kpi(s, 8.75, 3.45, 3.95, 1.45, "10 %", "Lochung Ø 4,3 mm im Raster 12 mm, Blech 1,5 mm, " +
    "1.204 Löcher", "Lochung");
  kpi(s, 8.75, 5.05, 3.95, 1.45, "–2 %", `Lichtstrom ${fmtDE(D.flux_b3a)} lm statt 111.246 lm ` +
    "(gleiche Optik wie V2)", "Lichtstrom");
  s.addNotes("Ausgelegt mit visor_design.py: Gittersuche über Tiefe, Neigung und Lochung, Ziel ist " +
    "die LVK der Blende 3 im hinteren Halbraum. Ein unter das Glas geneigtes Blech wäre kürzer, " +
    "kostet rund 7 % Lichtstrom. Wangen so tief wie das Stirnblech schneiden das Licht zur Seite ab: " +
    "dann verfehlt die Arena-Reihe Klasse I (U0 0,67–0,69, variant_study.txt). CAD: blende_b3_aussen.stp und sirius1000_blende_b3.stp.");
}
{
  const s = content("Neue außenliegende Blende", "LICHTVERTEILUNG NACH HINTEN",
    "Bis 55° wie Blende 3, darüber schärfer abgeschnitten");
  const clamp = (a) => a.map((v) => Math.max(v, 1));
  const lab = D.gamma.map(String);
  s.addChart(pres.charts.LINE, [
    { name: "V2 heute", labels: lab, values: clamp(D.c180_heute) },
    { name: "Blende 3 (ohne ext. Blende)", labels: lab, values: clamp(D.c180_b3) },
    { name: "B3a neue ext. Blende", labels: lab, values: clamp(D.c180_b3a) },
  ], {
    x: 0.6, y: 1.8, w: 7.9, h: 4.9, ...CHART_TEXT,
    chartColors: [HEX.dk1, HEX.accent5, HEX.accent1], lineSize: 2,
    lineDataSymbol: "none", valAxisLogScaleBase: 10, valAxisMinVal: 1, valAxisMaxVal: 100000,
    showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "Lichtstärke [cd], C180",
    showCatAxisTitle: true, catAxisTitle: "Ausstrahlungswinkel γ nach hinten [°]",
    catAxisLabelFrequency: 3, objectName: "B3a LVK C180",
  });
  const at = (arr, gam) => fmtDE(arr[D.gamma.indexOf(gam)]);
  const rows = [[head("C180, γ"), head("V2"), head("B3"), head("B3a")]];
  for (const [gam, lbl] of [[50, "50° (8 m)"], [55, "55°"], [60, "60°"], [65, "65° (5 m)"], [70, "70°"]]) {
    rows.push([cell(lbl), cell(at(D.c180_heute, gam)), cell(at(D.c180_b3, gam)),
      cell(at(D.c180_b3a, gam), { bold: true, color: C.accent1 })]);
  }
  s.addTable(rows, tableOpts(8.8, 1.85, 3.9, [1.3, 0.9, 0.85, 0.85], { fontSize: 12 }));
  s.addText("Werte in cd, je Lichtstrom der Variante. Das gerade Blech schneidet schärfer ab als die " +
    "Optik der Blende 3: bis 55° passt es, ab 60° geht weniger Licht nach hinten. Schräg nach " +
    "hinten (C150) bleibt es wie V2, weil die Wangen nicht tiefer sind. Nach vorn wie V2.", { x: 8.8, y: 4.25, w: 3.9, h: 2.4, fontSize: 12, color: C.text2, margin: 0,
    valign: "top", isTextBox: true, objectName: "B3a LVK Hinweis" });
  s.addNotes("LVK berechnet: Optik ohne Blende aus der gemessenen V2-LVK zurückgerechnet, neue " +
    "Abschattung mit Strahlenmodell (Lochung mit Blechdicke), Innenseite matt schwarz. " +
    "Dateien: SIRIUS1000_Blende_B3_aussen_berechnet.ldt und sirius1000_visor_b3.ies.");
}
{
  const s = content("Neue außenliegende Blende", "BEWERTUNG",
    "B3a blendet kaum mehr als Blende 3 und hält Klasse I");
  const win = (t) => cell(t, { bold: true, color: C.accent1 });
  const rows = [
    [head("KRITERIUM"), head("V2 HEUTE"), head("BLENDE 3"), head("B3a NEU")],
    [cell("Blendung Person, GR 5 m"), cell("24,0"), cell("14,0"), win("5,4")],
    [cell("Blendung Person, GR 8 m"), cell("21,0"), win("13,7"), cell("15,1")],
    [cell("Licht am Auge, E_v 5 m / 8 m"), cell("55 / 72 lx"), cell("22 / 37 lx"), cell("9 / 40 lx")],
    [cell("Blendung Zuschauer, GR max 8 m"), cell("13"), win("9"), cell("10")],
    [cell("Aufhellung Rückwand, Ē 5 m / 8 m"), cell("7,1 / 16,0 lx"), win("3,4 / 6,6 lx"), cell("4,9 / 10,1 lx")],
    [cell("Feld 8 m, durchgehende Reihe"), win("Klasse I (U0 0,70)"), cell("Klasse III (U0 0,69)"), win("Klasse I (U0 0,70)")],
    [cell("Umsetzung"), cell("vorhanden"), cell("andere Optik"), win("nur neues Blech")],
  ];
  s.addTable(rows, tableOpts(0.6, 1.8, 12.1, [3.7, 2.8, 2.8, 2.8], { fontSize: 12 }));
  s.addText([
    { text: "Einordnung: ", options: { bold: true, color: C.accent1 } },
    { text: "B3a kommt bei der Blendung nahe an Blende 3, braucht keine neue Optik und hält in der " +
      "Arena Klasse I wie V2 (U0 genau an der Grenze). Die Rückwand wird etwas heller als mit Blende 3. " +
      "Das freie Stirnblech ist an Unter- und Seitenkanten 20 mm nach hinten gekantet. Vor dem Einsatz " +
      "ein Muster bauen und vermessen." },
  ], { x: 0.6, y: 5.25, w: 12.1, h: 1.2, fontSize: 14, color: C.text1, margin: 0, valign: "top",
    isTextBox: true, objectName: "B3a Einordnung" });
  s.addNotes("Gleiche Methode wie im Abschnitt ohne externe Blende; für B3a ist der sichtbare " +
    "Glasanteil aus der neuen Blendengeometrie gerechnet. Vergleich der Optik bei gleichem Lichtstrom " +
    "111.246 lm vor Blende.");
}

// ================================================================= Kompakte Blende
pres.addSection({ title: "Kompakte Blende" });
{
  const s = content("Kompakte Blende", "KOMPAKTE BLENDE · PRINZIP",
    "Eine Lamelle unter dem Glas spart mehr als die halbe Bautiefe");
  numberedBlock(s, 0.6, 1.85, 5.9, "1", "Warum B3a 450 mm tief ist",
    "Ein Stirnblech allein muss die ganze Glaslänge von 766 mm abdecken: Tiefe = Länge / tan γ, " +
    "für 60° rund 440 mm.", "Prinzip 1");
  numberedBlock(s, 0.6, 3.5, 5.9, "2", "Lamelle teilt die Fläche",
    "Eine Lamelle unter der Glasmitte halbiert die abzudeckende Länge. Um 30° nach vorn geneigt, " +
    "lässt sie den Hauptstrahl (C0, γ 35°) durch.", "Prinzip 2");
  numberedBlock(s, 0.6, 5.15, 5.9, "3", "Seitliche Form: ohne Wangen",
    "Wangen schneiden Licht zur Seite ab: je nach Länge 2–20 % Lichtstrom und Gleichmäßigkeit " +
    "weg, ohne die Blendung nach hinten zu senken.", "Prinzip 3");
  const idx = D.mini_depths.map((d, i) => [d, i]).filter(([d]) => [100, 125, 150, 175, 200].includes(d));
  const lab = idx.map(([d]) => String(d));
  s.addChart(pres.charts.LINE, [
    { name: "nur Stirnblech", labels: lab, values: idx.map(([, i]) => D.mini_gr5["0"][i]) },
    { name: "Stirnblech + 1 Lamelle", labels: lab, values: idx.map(([, i]) => D.mini_gr5["1"][i]) },
  ], {
    x: 6.9, y: 1.8, w: 5.8, h: 4.9, ...CHART_TEXT,
    chartColors: [HEX.dk1, HEX.accent1], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 7,
    valAxisMinVal: 0, valAxisMaxVal: 30, valAxisMajorUnit: 5, showLegend: true, legendPos: "b",
    showTitle: true, title: "GR der Person bei 5 m (bestes Ergebnis je Bautiefe)",
    showCatAxisTitle: true, catAxisTitle: "Bautiefe unter dem Glas [mm]",
    objectName: "Kompakt Studie GR",
  });
  s.addNotes("visor_mini.py: 550 Varianten (0–3 Lamellen, Tiefe 100–300 mm, Neigung 0–45°, Wangen " +
    "kurz/lang/keine). Im Diagramm nur Varianten mit höchstens 5 % Lichtverlust und U0 ≥ 0,66. " +
    "Zwei und mehr Lamellen kosten über 5 % Lichtstrom.");
}
{
  const s = content("Kompakte Blende", "AUSLEGUNG B3k",
    "B3k: 188 mm statt 450 mm Bautiefe");
  s.addImage({ path: IMG("ansicht_b3k_hinten.png"), x: 0.6, y: 1.9, w: 4.4, h: 3.269,
    altText: "SIRIUS 1000 mit kompakter Blende B3k, Ansicht von hinten unten",
    objectName: "B3k Ansicht hinten" });
  s.addText("B3k von hinten unten: Stirnblech gelocht, Lamelle geschlossen", { x: 0.6, y: 5.3, w: 4.4,
    h: 0.35, fontSize: 10, color: C.text2, margin: 0, isTextBox: true, objectName: "B3k Bildunterschrift" });
  s.addText("B3a (450 mm)", { x: 5.3, y: 1.8, w: 3.1, h: 0.3, fontSize: 11, bold: true,
    color: C.text2, margin: 0, isTextBox: true, objectName: "Seitenansicht B3a Titel" });
  s.addImage({ path: IMG("ansicht_b3a_seite.png"), x: 5.3, y: 2.1, w: 3.1, h: 2.222,
    altText: "Seitenansicht mit Blende B3a", objectName: "Seitenansicht B3a klein" });
  s.addText("B3k (188 mm)", { x: 5.3, y: 4.5, w: 3.1, h: 0.3, fontSize: 11, bold: true,
    color: C.accent1, margin: 0, isTextBox: true, objectName: "Seitenansicht B3k Titel" });
  s.addImage({ path: IMG("ansicht_b3k_seite.png"), x: 5.3, y: 4.8, w: 3.1, h: 1.611,
    altText: "Seitenansicht mit kompakter Blende B3k", objectName: "Seitenansicht B3k" });
  kpi(s, 8.75, 1.85, 3.95, 1.45, "188 mm", "58 % flacher als B3a; Stirnblech senkrecht, " +
    "eine Lamelle unter der Glasmitte", "B3k Tiefe", C.accent1);
  kpi(s, 8.75, 3.45, 3.95, 1.45, "30°", "Lamelle geschlossen, nach vorn geneigt, 15 mm unter " +
    "dem Glas; Stirnblech 10 % gelocht", "B3k Lamelle");
  kpi(s, 8.75, 5.05, 3.95, 1.45, "–4,1 %", `Lichtstrom ${fmtDE(D.flux_b3k)} lm; keine ` +
    "Seitenwangen", "B3k Lichtstrom");
  s.addNotes("Die Lamelle beginnt 15 mm unter dem Glas, unter dem Gehäuserahmen. Ihre Befestigung an " +
    "den Stirnseiten des Gehäuses ist noch nicht konstruiert. CAD: blende_b3k_kompakt.stp.");
}
{
  const s = content("Kompakte Blende", "BEWERTUNG",
    "B3k blendet wie B3a, erreicht in der Arena aber nur Klasse III");
  const win = (t) => cell(t, { bold: true, color: C.accent1 });
  const rows = [
    [head("KRITERIUM"), head("V2 HEUTE"), head("BLENDE 3"), head("B3a"), head("B3k KOMPAKT")],
    [cell("Bautiefe unter dem Glas"), cell("211 mm"), cell("–"), cell("450 mm"), win("188 mm")],
    [cell("Lichtstrom gegenüber V2"), cell("100 %"), cell("100 % (gesetzt)"), cell("98 %"), cell("96 %")],
    [cell("Blendung Person, GR 5 m / 8 m"), cell("24,0 / 21,0"), cell("14,0 / 13,7"), win("5,4 / 15,1"), win("6,5 / 14,7")],
    [cell("Licht am Auge, E_v 5 m / 8 m"), cell("55 / 72 lx"), cell("22 / 37 lx"), cell("9 / 40 lx"), cell("10 / 37 lx")],
    [cell("Blendung Zuschauer, GR max 8 m"), cell("13"), win("9"), cell("10"), win("9")],
    [cell("Aufhellung Rückwand, Ē 5 m / 8 m"), cell("7,1 / 16,0 lx"), win("3,4 / 6,6 lx"), cell("4,9 / 10,1 lx"), cell("3,7 / 8,2 lx")],
    [cell("Feld 8 m, durchgehende Reihe"), win("Klasse I (U0 0,70)"), cell("Klasse III (0,69)"), win("Klasse I (U0 0,70)"), cell("Klasse III (0,66)")],
  ];
  s.addTable(rows, tableOpts(0.6, 1.8, 12.1, [3.3, 2.1, 2.2, 2.2, 2.3], { fontSize: 12 }));
  s.addText([
    { text: "Einordnung: ", options: { bold: true, color: C.accent1 } },
    { text: "B3k erreicht die Blendungswerte von B3a mit 42 % der Bautiefe. Die Lamelle schattet etwas " +
      "Licht nach unten ab; am vorderen Feldrand fällt U0 dadurch auf 0,66. Wo Klasse I gefordert ist, " +
      "bleibt B3a die Lösung, sonst ist B3k die handlichere Blende." },
  ], { x: 0.6, y: 5.35, w: 12.1, h: 1.1, fontSize: 14, color: C.text1, margin: 0, valign: "top",
    isTextBox: true, objectName: "B3k Einordnung" });
  s.addNotes("Werte aus vergleich_blenden.txt. Keine Lamellen-Variante mit höchstens 5 % Lichtverlust " +
    "erreicht U0 0,70; schon V2 liegt bei 0,699.");
}

// ================================================================= 13 Annahmen
pres.addSection({ title: "Anhang" });
{
  const s = content("Anhang", "ANNAHMEN UND GRENZEN", "Was die Bewertung abdeckt und was nicht");
  s.addText([
    { text: "Grundlage", options: { bold: true, color: C.accent1, fontSize: 15, breakLine: true } },
    { text: "LDT der SIRIUS 2000 (5XA7100W40A13DA-Z, außenliegende Blende V2), auf ein Modul halbiert: " +
      "111.246 lm, 985,5 W", options: { bullet: true, breakLine: true } },
    { text: "CAD-Modell der Blende aus der STEP-Datei, Löcher geometrisch aufgebohrt", options: { bullet: true, breakLine: true } },
    { text: "Direktlicht analytisch aus der LVK, gegengeprüft mit Blender/Cycles (Abweichung 3–7 %)",
      options: { bullet: true, breakLine: true, paraSpaceAfter: 10 } },
    { text: "Grenzen", options: { bold: true, color: C.accent2, fontSize: 15, breakLine: true } },
    { text: "LVK der 50-%-Lochung ist mit einem Strahlenmodell abgeschätzt, nicht gemessen; " +
      "Reflexion an der Blende wie gemessen angenommen", options: { bullet: true, breakLine: true } },
    { text: "GR mit angenommenem Boden-Reflexionsgrad 20 %; bei 0 % Reflexion nicht definiert",
      options: { bullet: true, breakLine: true } },
    { text: "Ein Blickpunkt (sitzend, 8 m hinter der Leuchte, Blick nach vorn); direkter Blick zur " +
      "Leuchte nicht mit GR bewertet", options: { bullet: true, breakLine: true } },
    { text: "Person nicht als Hindernis im Messfeld berücksichtigt", options: { bullet: true, breakLine: true } },
    { text: "Arena: drei Leuchten bzw. durchgehende Reihe alle 6 m, Wartungsfaktor 0,8, Direktlicht, " +
      "Zuschauer in Augenhöhe 1,2 m (keine ansteigende Tribüne)", options: { bullet: true, breakLine: true } },
    { text: "Blende 2/3: relative LDT (4000 K, CRI 70), auf 111.246 lm gesetzt und um 90° gedreht; " +
      "Vergleich bei gleichem Lichtstrom", options: { bullet: true, breakLine: true } },
    { text: "B3a/B3k: Blende und LVK berechnet (Strahlenmodell, Innenseite matt schwarz), nicht gemessen",
      options: { bullet: true } },
  ], { x: 0.6, y: 1.85, w: 12.1, h: 4.9, fontSize: 16, color: C.text1, margin: 0, valign: "top",
    paraSpaceAfter: 6, isTextBox: true, objectName: "Annahmen Liste" });
  s.addNotes("Skripte und Szenen: lichtplanung/sirius1000 auf dem Branch, Pakete sirius1000_raum_paket.zip " +
    "und sirius1000_perf50_paket.zip.");
}

(async () => {
  const out = path.join(__dirname, "Blendungsbewertung_SIRIUS1000_Blende.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("geschrieben:", out);
})();
