// Pointer feedback for every chart: when the pointer reaches a column, that column's
// track lights up, its bar glows and the others fade. Pure class toggles on the SVG
// (no re-plotting), so it stays smooth.
(function () {
  function clear(gd) {
    var els = gd.querySelectorAll('.gb-hot, .gb-dim, .gb-track-hot');
    for (var i = 0; i < els.length; i++) { els[i].classList.remove('gb-hot', 'gb-dim', 'gb-track-hot'); }
    gd.classList.remove('gb-hovering');
  }

  function layerNodes(gd, layerSel, pointSel) {
    // Map full-data trace index -> list of point elements, per trace type layer.
    var out = {};
    var fd = gd._fullData || [];
    var type = layerSel === '.barlayer' ? 'bar' : (layerSel === '.pielayer' ? 'pie' : 'scatter');
    var traces = gd.querySelectorAll(layerSel + ' .trace');
    var k = 0;
    for (var i = 0; i < fd.length; i++) {
      if (fd[i].type !== type || fd[i].visible === false) { continue; }
      if (traces[k]) { out[fd[i].index] = traces[k].querySelectorAll(pointSel); }
      k++;
    }
    return out;
  }

  function onHover(gd, ev) {
    clear(gd);
    if (!ev || !ev.points || !ev.points.length) { return; }
    var fd = gd._fullData || [];
    var hot = {};
    ev.points.forEach(function (p) {
      (hot[p.curveNumber] = hot[p.curveNumber] || {})[p.pointNumber] = true;
    });
    var groups = [layerNodes(gd, '.barlayer', '.point path'),
                  layerNodes(gd, '.scatterlayer', '.points path'),
                  layerNodes(gd, '.pielayer', '.slice path.surface')];
    groups.forEach(function (g) {
      Object.keys(g).forEach(function (ci) {
        var isTrack = fd[ci] && fd[ci].meta === 'track';
        var h = hot[ci];
        var nodes = g[ci];
        for (var j = 0; j < nodes.length; j++) {
          if (h && h[j]) { nodes[j].classList.add(isTrack ? 'gb-track-hot' : 'gb-hot'); }
          else if (!isTrack && Object.keys(hot).length) { nodes[j].classList.add('gb-dim'); }
        }
      });
    });
    gd.classList.add('gb-hovering');
  }


  function bind() {
    var plots = document.querySelectorAll('.js-plotly-plot');
    for (var i = 0; i < plots.length; i++) {
      var gd = plots[i];
      if (typeof gd.on !== 'function') { continue; }
      var ev = gd._ev;
      var h = gd.__gbHover;
      var bound = h && ev && typeof ev.listeners === 'function' && ev.listeners('plotly_hover').indexOf(h) !== -1;
      if (!bound) {
        (function (g) {
          g.__gbHover = function (e) { onHover(g, e); };
          g.on('plotly_hover', g.__gbHover);
          g.on('plotly_unhover', function () { clear(g); });
        })(gd);
      }
    }
  }
  setInterval(bind, 700);
})();
