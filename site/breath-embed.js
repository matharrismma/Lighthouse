/* breath-embed.js — THE BREATH as an embeddable, living panel.
 *
 * The map of the verified body, drawn by evidence (verified/concordant glow; resonance
 * faint; retired muted-red; source a gap), mountable inside any surface so the Shepherd
 * and Scribe walk you ACROSS it. Exposes a tiny API:
 *
 *   NHBreath.mount(canvasEl, {height, onReady})   -> start rendering breath-graph.json
 *   NHBreath.focus(names)    -> ease the view to the node(s) whose title matches a name
 *   NHBreath.highlight(names)-> glow the matching node(s) + the edges around them
 *   NHBreath.clear()         -> drop the highlight
 *
 * `names` is a string or array of strings; matching is case-insensitive substring on the
 * node title, so the Walk can pass a precedent summary / card title / trail names and the
 * map finds where they stand. Honest by construction: it never invents a match.
 */
(function (global) {
  var EV = {
    source:    [255,240,210], verified: [150,240,170], concordant:[110,200,235],
    mixed:     [232,200,120], resonance:[122,114,150], retired:  [208,96,90]
  };
  var ALPHA = { source:1, verified:1, concordant:.9, mixed:.8, resonance:.3, retired:.6 };
  var SZ    = { source:1, verified:1.25, concordant:1, mixed:.85, resonance:.6, retired:.8 };

  var S = null; // single mounted instance state

  function sprite(rgb, soft) {
    var s = 64, oc = document.createElement('canvas'); oc.width = oc.height = s;
    var c = oc.getContext('2d'), g = c.createRadialGradient(s/2,s/2,0,s/2,s/2,s/2);
    g.addColorStop(0, soft ? 'rgba('+rgb[0]+','+rgb[1]+','+rgb[2]+',0)' : 'rgba('+rgb[0]+','+rgb[1]+','+rgb[2]+',1)');
    g.addColorStop(soft?.45:.25, 'rgba('+rgb[0]+','+rgb[1]+','+rgb[2]+',.55)');
    g.addColorStop(1, 'rgba('+rgb[0]+','+rgb[1]+','+rgb[2]+',0)');
    c.fillStyle = g; c.fillRect(0,0,s,s); return oc;
  }

  function mount(cv, opts) {
    opts = opts || {};
    var ctx = cv.getContext('2d');
    var DPR = Math.min(global.devicePixelRatio || 1, 2);
    var reduce = !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
    fetch('/breath-graph.json').then(function (r) { return r.json(); }).then(function (D) {
      var N = D.x.length, X = D.x, Y = D.y, NEV = D.node_ev || [], NAME = D.name || [],
          E = D.edges || [], EEV = D.edge_ev || [], SRC = D.src || [];
      var isSrc = new Uint8Array(N); SRC.forEach(function (i) { isSrc[i] = 1; });
      var sp = {}; for (var k in EV) sp[k] = sprite(EV[k], k === 'source');
      var minx=1e9,maxx=-1e9,miny=1e9,maxy=-1e9;
      for (var i=0;i<N;i++){ if(X[i]<minx)minx=X[i]; if(X[i]>maxx)maxx=X[i]; if(Y[i]<miny)miny=Y[i]; if(Y[i]>maxy)maxy=Y[i]; }
      var cx=(minx+maxx)/2, cy=(miny+maxy)/2;
      var W,H,fit=1, view={s:1,ox:0,oy:0}, target=null, hi=new Uint8Array(N), hiOn=false;
      function resize(){ W=cv.clientWidth; H=cv.clientHeight; cv.width=W*DPR; cv.height=H*DPR;
        fit=Math.min(W/(maxx-minx+80), H/(maxy-miny+100)); }
      global.addEventListener('resize', resize); resize();
      function sx(i){ return (X[i]-cx)*fit*view.s + W/2 + view.ox; }
      function sy(i){ return (Y[i]-cy)*fit*view.s + H/2 + view.oy; }

      function matchNodes(names){
        if (!names) return [];
        if (!Array.isArray(names)) names = [names];
        var needles = names.map(function(s){return String(s||'').toLowerCase().trim();}).filter(function(s){return s.length>=4;});
        var hits=[];
        for (var i=0;i<N;i++){ var t=(NAME[i]||'').toLowerCase();
          for (var j=0;j<needles.length;j++){ if(t && (t.indexOf(needles[j])>=0 || needles[j].indexOf(t)>=0)){ hits.push(i); break; } } }
        return hits;
      }

      var inst = {
        focus: function(names){ var h=matchNodes(names); if(!h.length) return 0;
          var ax=0,ay=0; h.forEach(function(i){ ax+=X[i]; ay+=Y[i]; }); ax/=h.length; ay/=h.length;
          target={x:ax,y:ay,s:2.4}; return h.length; },
        highlight: function(names){ hi=new Uint8Array(N); var h=matchNodes(names);
          h.forEach(function(i){ hi[i]=1; }); hiOn=h.length>0; this.focus(names); return h.length; },
        clear: function(){ hi=new Uint8Array(N); hiOn=false; target={x:cx,y:cy,s:1}; }
      };

      function frame(){
        // ease toward target (focus)
        if(target){ view.ox += (W/2 - (target.x-cx)*fit*(target.s) - W/2 - view.ox)*0.08;
          view.oy += (H/2 - (target.y-cy)*fit*(target.s) - H/2 - view.oy)*0.08;
          view.s += (target.s - view.s)*0.08; }
        ctx.setTransform(DPR,0,0,DPR,0,0);
        ctx.globalCompositeOperation='source-over';
        ctx.fillStyle='rgba(6,7,11,'+(reduce?1:0.4)+')'; ctx.fillRect(0,0,W,H);
        ctx.globalCompositeOperation='lighter';
        // edges (faint; proven brighter)
        function ed(want,rgba,lw){ ctx.lineWidth=lw; ctx.strokeStyle=rgba; ctx.beginPath();
          for(var e=0;e<E.length;e++){ if((EEV[e]||'resonance')===want){ ctx.moveTo(sx(E[e][0]),sy(E[e][0])); ctx.lineTo(sx(E[e][1]),sy(E[e][1])); } } ctx.stroke(); }
        ed('resonance','rgba(122,114,150,0.05)',0.5); ed('concordant','rgba(110,200,235,0.22)',0.7); ed('verified','rgba(150,240,170,0.5)',1);
        // nodes
        for(var i=0;i<N;i++){ var ek=isSrc[i]?'source':(NEV[i]||'resonance');
          var r=(1.8+Math.sqrt((D.deg&&D.deg[i]||1)/40)*11)*(SZ[ek]||.6)*Math.min(2.2,Math.max(.6,view.s*fit));
          var a=(ALPHA[ek]||.3); if(hiOn) a=hi[i]?1:a*0.28;
          ctx.globalAlpha=a; ctx.drawImage(sp[ek]||sp.resonance, sx(i)-r, sy(i)-r, r*2, r*2);
          if(hiOn&&hi[i]){ ctx.globalAlpha=0.9; ctx.strokeStyle='rgba(243,236,213,0.9)'; ctx.lineWidth=1.4;
            ctx.beginPath(); ctx.arc(sx(i),sy(i),r+5,0,6.283); ctx.stroke(); } }
        ctx.globalAlpha=1;
        global.requestAnimationFrame(frame);
      }
      frame();
      S = inst;
      if (opts.onReady) opts.onReady(inst);
    }).catch(function(){ if (opts.onError) opts.onError(); });
  }

  global.NHBreath = {
    mount: mount,
    focus: function(n){ return S && S.focus(n); },
    highlight: function(n){ return S && S.highlight(n); },
    clear: function(){ return S && S.clear(); }
  };
})(window);
