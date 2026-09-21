// Count-up animation for KPI numbers and the trip counter.
// Only the existing text node's value is changed, so React keeps full control of the DOM.
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var PARSE = /^([^\d-]*)(-?[\d,]*\.?\d+)(.*)$/;

  function animate(el) {
    var node = el.firstChild;
    if (!node || node.nodeType !== 3) { return; }
    var target = node.nodeValue;
    if (target === el.__shown) { return; }
    var m = target.match(PARSE);
    if (!m || reduce) { el.__shown = target; return; }
    var to = parseFloat(m[2].replace(/,/g, ''));
    var decimals = (m[2].split('.')[1] || '').length;
    var commas = m[2].indexOf(',') > -1 || to >= 1000;
    var from = typeof el.__num === 'number' ? el.__num : 0;
    el.__num = to;
    if (from === to) { el.__shown = target; return; }
    var start = performance.now(), dur = 900;
    cancelAnimationFrame(el.__raf);
    function fmt(v) {
      var s = v.toFixed(decimals);
      if (commas) { var p = s.split('.'); p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ','); s = p.join('.'); }
      return m[1] + s + m[3];
    }
    function step(now) {
      var k = Math.min(1, (now - start) / dur);
      var e = 1 - Math.pow(1 - k, 4);
      var txt = k < 1 ? fmt(from + (to - from) * e) : target;
      el.__shown = txt;
      if (el.firstChild === node) { node.nodeValue = txt; }
      if (k < 1) { el.__raf = requestAnimationFrame(step); }
    }
    el.__shown = fmt(from);
    node.nodeValue = el.__shown;
    el.__raf = requestAnimationFrame(step);
  }

  var pending = false;
  function scan() {
    pending = false;
    document.querySelectorAll('.count-up').forEach(animate);
  }
  // Watch only the KPI band and the trip counter, never the charts (hovering charts
  // mutates the DOM constantly and would waste frames).
  var obs = new MutationObserver(function () {
    if (!pending) { pending = true; requestAnimationFrame(scan); }
  });
  function attach() {
    var targets = ['kpis', 'summary'].map(function (id) { return document.getElementById(id); });
    if (targets.some(function (t) { return !t; })) { return setTimeout(attach, 300); }
    targets.forEach(function (t) { obs.observe(t, { childList: true, subtree: true, characterData: true }); });
    scan();
  }
  attach();
})();
