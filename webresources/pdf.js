// A small PDF writer for Stu's pages (deployed as clt_/pages/pdf.js by build_app.py): text, tables and rules on
// US Letter pages, in Helvetica. No library and nothing sent anywhere: the file is made in the browser.
// Plain code with no Dataverse or page calls, so tests/test_selection.py builds a document in Node and reads it back.
//
//   CLTPdf.make({ title, footer, blocks }) -> the file's bytes as a string (one character per byte)
//   CLTPdf.save(name, bytes)               -> hands the file to the browser to save (page only)
//   blocks: { h: "Heading" } | { p: "Paragraph", bold, size } | { gap: points }
//         | { table: { columns: [{ label, width, align: "right" }], rows: [[...]] } }      width in points
//         | { sign: ["Board Observer", "Staff"] }                                          signature lines
var CLTPdf = (function () {
  var W = 612, H = 792, MARGIN = 54, BOTTOM = 64;   // US Letter, 3/4 inch margins, room for the page number
  // Helvetica's character widths (thousandths of the font size) for the characters from space to ~.
  var WIDTHS = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556,
    556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722,
    778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556,
    556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584];

  // Only characters a standard PDF font can show: curly quotes and dashes become plain ones, the rest "?".
  function clean(text) {
    return String(text == null ? "" : text).replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"').replace(/[\u2013\u2014]/g, "-")
      .replace(/\u2026/g, "...").replace(/\u00A0/g, " ").replace(/[^\x20-\x7E\xA1-\xFF]/g, "?");
  }
  function width(text, size, bold) {
    var w = 0, s = clean(text);
    for (var i = 0; i < s.length; i++) { var c = s.charCodeAt(i); w += c >= 32 && c <= 126 ? WIDTHS[c - 32] : 556; }
    return w * size / 1000 * (bold ? 1.07 : 1);
  }
  function literal(text) {
    return "(" + clean(text).replace(/[\\()]/g, "\\$&").replace(/[\x80-\xFF]/g, function (c) { return "\\" + c.charCodeAt(0).toString(8); }) + ")";
  }
  function wrap(text, size, bold, max) {
    var out = [];
    clean(text).split("\n").forEach(function (para) {
      var line = "";
      para.split(/\s+/).forEach(function (word) {
        var next = line ? line + " " + word : word;
        if (line && width(next, size, bold) > max) { out.push(line); line = word; } else line = next;
      });
      out.push(line);
    });
    return out;
  }
  function n(x) { return String(Math.round(x * 100) / 100); }

  function make(doc) {
    var pages = [], ops = [], y = H - MARGIN;
    function text(s, x, yy, size, bold) { ops.push("BT /F" + (bold ? 2 : 1) + " " + size + " Tf " + n(x) + " " + n(yy) + " Td " + literal(s) + " Tj ET"); }
    function rule(x1, yy, x2, weight) { ops.push(n(weight || 0.5) + " w " + n(x1) + " " + n(yy) + " m " + n(x2) + " " + n(yy) + " l S"); }
    function page() { if (ops.length) pages.push(ops); ops = []; y = H - MARGIN; }
    function need(h) { if (y - h < BOTTOM) page(); }
    function para(s, size, bold, gapAfter) {
      wrap(s, size, bold, W - 2 * MARGIN).forEach(function (line) { need(size * 1.4); y -= size * 1.4; text(line, MARGIN, y, size, bold); });
      y -= gapAfter || 0;
    }
    if (doc.title) { para(doc.title, 16, true, 4); }
    (doc.blocks || []).forEach(function (b) {
      if (b.gap) { y -= b.gap; return; }
      if (b.h) { need(40); y -= 10; para(b.h, 12, true, 2); return; }
      if (b.p !== undefined) { para(b.p, b.size || 10, b.bold, 3); return; }
      if (b.sign) {
        b.sign.forEach(function (who) {
          need(46); y -= 34;
          rule(MARGIN, y, MARGIN + 250); rule(MARGIN + 290, y, MARGIN + 430);
          text(who, MARGIN, y - 11, 9); text("Date", MARGIN + 290, y - 11, 9);
          y -= 12;
        });
        return;
      }
      if (b.table) {
        var cols = b.table.columns, size = 9.5, lead = 15, x0 = MARGIN;
        var xs = [], x = x0; cols.forEach(function (c) { xs.push(x); x += c.width; });
        var head = function () {
          need(lead * 3); y -= lead;
          cols.forEach(function (c, i) {
            var tx = c.align === "right" ? xs[i] + c.width - 8 - width(c.label, size, true) : xs[i];
            text(c.label, tx, y, size, true);
          });
          y -= 4; rule(x0, y, x, 0.8);
        };
        head();
        (b.table.rows || []).forEach(function (row) {
          if (y - lead < BOTTOM) { page(); head(); }
          y -= lead;
          cols.forEach(function (c, i) {
            var s = row[i] == null ? "" : String(row[i]);
            text(s, c.align === "right" ? xs[i] + c.width - 8 - width(s, size) : xs[i], y, size, c.bold);
          });
        });
        y -= 6; rule(x0, y, x, 0.3); y -= 6;
      }
    });
    page();
    if (!pages.length) pages.push([]);
    pages.forEach(function (p, i) {
      var foot = "Page " + (i + 1) + " of " + pages.length;
      p.push("BT /F1 8 Tf " + n(MARGIN) + " 36 Td " + literal(doc.footer || doc.title || "") + " Tj ET");
      p.push("BT /F1 8 Tf " + n(W - MARGIN - width(foot, 8)) + " 36 Td " + literal(foot) + " Tj ET");
    });

    // The file: numbered objects, then a table saying where each one starts.
    var objs = [], kids = [];
    objs[1] = "<< /Type /Catalog /Pages 2 0 R >>";
    objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>";
    objs[4] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>";
    pages.forEach(function (p, i) {
      var stream = p.join("\n"), pageNo = 5 + i * 2;
      kids.push(pageNo + " 0 R");
      objs[pageNo] = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 " + W + " " + H + "] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents " + (pageNo + 1) + " 0 R >>";
      objs[pageNo + 1] = "<< /Length " + stream.length + " >>\nstream\n" + stream + "\nendstream";
    });
    objs[2] = "<< /Type /Pages /Kids [" + kids.join(" ") + "] /Count " + pages.length + " >>";
    var out = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n", offsets = [];
    for (var k = 1; k < objs.length; k++) { offsets[k] = out.length; out += k + " 0 obj\n" + objs[k] + "\nendobj\n"; }
    var start = out.length, pad = function (v) { v = String(v); while (v.length < 10) v = "0" + v; return v; };
    out += "xref\n0 " + objs.length + "\n0000000000 65535 f \n";
    for (k = 1; k < objs.length; k++) out += pad(offsets[k]) + " 00000 n \n";
    out += "trailer\n<< /Size " + objs.length + " /Root 1 0 R >>\nstartxref\n" + start + "\n%%EOF\n";
    return out;
  }

  // Hand the file to the browser to save. Returns false where the browser won't allow it.
  function save(name, bytes) {
    try {
      var data = new Uint8Array(bytes.length);
      for (var i = 0; i < bytes.length; i++) data[i] = bytes.charCodeAt(i) & 255;
      var url = URL.createObjectURL(new Blob([data], { type: "application/pdf" })), a = document.createElement("a");
      a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
      return true;
    } catch (e) { return false; }
  }

  var api = { make: make, save: save, width: width, clean: clean };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
