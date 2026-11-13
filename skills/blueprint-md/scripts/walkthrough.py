"""Interactive walkthrough page for blueprint-md: the diagram plus a step-by-step player.

Each step highlights the two components involved, animates the connection between them
and explains what happens. Scenarios come from `walkthroughs:` and `flows:` in architecture.yaml.
"""
import json
import re


def find_conn(m, a, b):
    """Return (connection, reversed) for a step from a to b, or (None, False)."""
    for e in m["conns"]:
        if (e["src"], e["dst"]) == (a, b):
            return e, False
    for e in m["conns"]:
        if (e["src"], e["dst"]) == (b, a):
            return e, True
    return None, False


def scenarios(m):
    """Explicit walkthroughs first, then every flow that has no walkthrough of the same title."""
    out = list(m["walkthroughs"])
    titles = {w["title"] for w in out}
    for f in m["flows"]:
        if f["name"] in titles or len(f["steps"]) < 2:
            continue
        steps = []
        for a, b in zip(f["steps"], f["steps"][1:]):
            e, _ = find_conn(m, a, b)
            steps.append({"from": a, "to": b, "at": None,
                          "title": (e and e["label"]) or f"{m['comps'][a]['name']} → {m['comps'][b]['name']}",
                          "via": (e and e["protocol"]) or "", "detail": (e and str(e["about"]).strip()) or "",
                          "code": []})
        out.append({"title": f["name"], "summary": "", "steps": steps})
    return out


def render_walkthrough(diagram_html, m, diagram_file):
    data = {"diagram": diagram_file, "scenarios": scenarios(m)}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = diagram_html.replace("<title>", "<title>Walkthrough · ", 1)
    page = re.sub(r"(<h1>)(.*?)(</h1>)", r"\1\2 · walkthrough\3", page, count=1)
    return page.replace("</body>", PLAYER.replace("/*WALKTHROUGH_DATA*/null", payload) + "\n</body>", 1)


def markdown(m):
    """Walkthrough section for ARCHITECTURE.md (explicit walkthroughs only; flows have their own section)."""
    if not m["walkthroughs"]:
        return []
    comps = m["comps"]
    L = ["## Walkthroughs", "", "Step-by-step scenarios; `walkthrough.html` plays them on the diagram.", ""]
    for w in m["walkthroughs"]:
        L += [f"### {w['title']}", ""]
        if w["summary"]:
            L += [w["summary"], ""]
        for i, s in enumerate(w["steps"], 1):
            where = comps[s["at"]]["name"] if s["at"] else f"{comps[s['from']]['name']} → {comps[s['to']]['name']}"
            line = f"{i}. **{s['title']}** ({where}"
            line += f"; {s['via']})" if s["via"] else ")"
            if s["detail"]:
                line += f": {s['detail']}"
            L.append(line)
            if s["code"]:
                L.append("   Code: " + ", ".join(f"`{c}`" for c in s["code"]))
        L.append("")
    return L


def render_gif(tour_path, gif_path, width, height, scenario=0, out_width=1400):
    """Record one scenario of walkthrough.html as light and dark animated GIFs."""
    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image
    except ImportError:
        raise RuntimeError("--gif needs Playwright and Pillow: pip install playwright pillow && "
                           "python3 -m playwright install chromium")
    import io
    still = (".wt-panel{display:none!important}body.wt{padding-right:20px!important}"
             "*{transition:none!important;animation:none!important}")
    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme, suffix in (("light", ""), ("dark", "-dark")):
            page = browser.new_page(viewport={"width": width + 120, "height": height + 400}, color_scheme=theme)
            page.goto(tour_path.resolve().as_uri())
            page.add_style_tag(content=still)
            page.evaluate(f"document.documentElement.dataset.theme='{theme}'; walkthrough.fit(false); walkthrough.select({scenario})")
            canvas = page.locator(".canvas")
            shot = lambda: Image.open(io.BytesIO(canvas.screenshot())).convert("RGB")
            frames, durations = [], []
            for n, step in enumerate(page.evaluate(f"walkthrough.steps({scenario})")):
                page.evaluate(f"walkthrough.go({n}); walkthrough.pause()")
                if not step.get("at"):
                    for k in range(9):
                        page.evaluate(f"walkthrough.dot({k / 8})")
                        frames.append(shot())
                        durations.append(70)
                frames.append(shot())
                durations.append(1500 if step.get("at") else 1100)
            durations[-1] = 2500
            page.close()
            scale = min(1, out_width / frames[0].width)
            size = (round(frames[0].width * scale), round(frames[0].height * scale))
            frames = [f.resize(size, Image.LANCZOS) for f in frames]
            sample = Image.new("RGB", (size[0], size[1] * 3))
            for k, f in enumerate((frames[0], frames[len(frames) // 2], frames[-1])):
                sample.paste(f, (0, size[1] * k))
            palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
            frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
            target = gif_path.with_name(gif_path.stem + suffix + ".gif")
            frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
            written.append(target)
        browser.close()
    return written


PLAYER = r"""
<style>
body.wt{padding-right:420px}
body.wt .frame{overflow:auto}
.wt-panel{position:fixed;top:0;right:0;bottom:0;width:400px;display:flex;flex-direction:column;background:var(--paper);border-left:1px solid var(--tile-line);font-family:var(--sans);color:var(--ink);z-index:20}
.wt-head{padding:18px 18px 10px;border-bottom:1px solid var(--tile-line)}
.wt-head h2{font-size:15px;font-weight:700;display:flex;justify-content:space-between;align-items:center}
.wt-head a{font:11px var(--mono);color:var(--muted);text-decoration:none}
.wt-head a:hover{color:var(--accent)}
.wt-tabs{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.wt-tabs button,.wt-ctrl button{border:1px solid var(--tile-line);background:var(--tile);color:var(--ink);border-radius:8px;padding:6px 10px;font:12px var(--sans);cursor:pointer}
.wt-tabs button.on{border-color:var(--accent);color:var(--accent);font-weight:650}
.wt-summary{margin-top:10px;font-size:12.5px;line-height:1.55;color:var(--muted)}
.wt-ctrl{display:flex;gap:6px;align-items:center;padding:10px 18px;border-bottom:1px solid var(--tile-line)}
.wt-ctrl button:disabled{opacity:.4;cursor:default}
.wt-ctrl .wt-count{margin-left:auto;font:12px var(--mono);color:var(--muted)}
.wt-ctrl .wt-fit{font:11px var(--mono)}
.wt-card{padding:16px 18px;border-bottom:1px solid var(--tile-line);max-height:45vh;overflow:auto}
.wt-card .wt-route{font:11px var(--mono);color:var(--accent);letter-spacing:.02em}
.wt-card h3{font-size:16px;margin:6px 0 8px;line-height:1.3}
.wt-card .wt-via{display:inline-block;font:11px var(--mono);background:var(--tile);border:1px solid var(--tile-line);border-radius:6px;padding:2px 6px;margin-bottom:8px}
.wt-card p{font-size:13px;line-height:1.6}
.wt-card code,.wt-list code,.wt-summary code{font:12px var(--mono);background:var(--tile);border:1px solid var(--tile-line);border-radius:4px;padding:0 3px}
.wt-files{margin-top:10px;display:flex;flex-direction:column;gap:3px}
.wt-files span{font:11px var(--mono);color:var(--muted);word-break:break-all}
.wt-list{flex:1;overflow:auto;padding:8px 10px 24px;margin:0;list-style:none;counter-reset:s}
.wt-list li{counter-increment:s;display:flex;gap:10px;padding:7px 8px;border-radius:8px;font-size:12.5px;line-height:1.4;cursor:pointer;color:var(--muted)}
.wt-list li::before{content:counter(s);flex:0 0 22px;height:22px;border-radius:50%;display:grid;place-items:center;font:600 11px var(--mono);border:1px solid var(--tile-line);background:var(--tile)}
.wt-list li.done{color:var(--ink)}
.wt-list li.on{background:var(--tile);color:var(--ink);font-weight:650;box-shadow:inset 0 0 0 1px var(--accent)}
.wt-list li.on::before{background:var(--accent);border-color:var(--accent);color:#fff}
.wt-hint{padding:8px 18px;font:11px var(--mono);color:var(--muted);border-top:1px solid var(--tile-line)}
body.wt-run .node{opacity:.28;transition:opacity .25s}
body.wt-run .node.wt-seen{opacity:.7}
body.wt-run .node.wt-active{opacity:1}
body.wt-run .node.wt-active .tile{border-color:var(--accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 25%,transparent);animation:wtpulse 1.6s ease-in-out infinite}
@keyframes wtpulse{50%{box-shadow:0 0 0 9px color-mix(in srgb,var(--accent) 10%,transparent)}}
body.wt-run svg.edges{opacity:.22;transition:opacity .25s}
svg.wt-layer{position:absolute;inset:0;pointer-events:none;overflow:visible}
.wt-edge{fill:none;stroke:var(--accent);stroke-width:3.2;stroke-linecap:round;stroke-linejoin:round}
.wt-edge.virtual{stroke-dasharray:7 6}
.wt-trail{fill:none;stroke:var(--accent);stroke-width:1.6;opacity:.35}
.wt-dot{fill:var(--accent);filter:drop-shadow(0 0 4px var(--accent))}
.wt-callout{position:absolute;max-width:240px;padding:6px 10px;border-radius:8px;background:var(--accent);color:#fff;font:600 12px var(--sans);line-height:1.35;box-shadow:0 4px 14px rgba(20,30,50,.25);pointer-events:none;z-index:5;transition:left .3s,top .3s}
.wt-callout b{font:700 11px var(--mono);opacity:.85;margin-right:6px}
@media (max-width:1100px){body.wt{padding-right:20px;padding-bottom:55vh}.wt-panel{top:auto;left:0;width:auto;height:52vh;border-left:none;border-top:1px solid var(--tile-line)}}
</style>
<aside class="wt-panel" aria-label="Walkthrough">
  <div class="wt-head">
    <h2>Walkthrough <a class="wt-back" href="#">plain diagram →</a></h2>
    <div class="wt-tabs" role="tablist"></div>
    <p class="wt-summary"></p>
  </div>
  <div class="wt-ctrl">
    <button class="wt-prev" title="Previous (←)">◀ Prev</button>
    <button class="wt-play" title="Play / pause (space)">▶ Play</button>
    <button class="wt-next" title="Next (→)">Next ▶</button>
    <button class="wt-fit" title="Fit diagram to window (f)">fit</button>
    <span class="wt-count"></span>
  </div>
  <div class="wt-card" aria-live="polite">
    <div class="wt-route"></div>
    <h3></h3>
    <span class="wt-via" hidden></span>
    <p class="wt-detail"></p>
    <div class="wt-files"></div>
  </div>
  <ol class="wt-list"></ol>
  <div class="wt-hint">← → step · space play · 1–9 scenario · f fit · esc reset</div>
</aside>
<script>
(function () {
  const DATA = /*WALKTHROUGH_DATA*/null;
  const SVGNS = 'http://www.w3.org/2000/svg';
  const $ = (s, r = document) => r.querySelector(s);
  const canvas = $('.canvas'), frame = $('.frame'), baseSvg = $('svg.edges'), panel = $('.wt-panel');
  document.body.classList.add('wt');
  $('.wt-back', panel).href = DATA.diagram;

  const nodes = {};
  document.querySelectorAll('.node[data-id]').forEach((el) => {
    const x = parseFloat(el.style.left), y = parseFloat(el.style.top);
    nodes[el.dataset.id] = { el, name: $('.name', el).textContent.trim(), cx: x + 68, cy: y + 30, x0: x + 38, y0: y, x1: x + 98 };
  });
  const edges = [...baseSvg.querySelectorAll('path.edge[data-from]')].map((p) => ({ d: p.getAttribute('d'), a: p.dataset.from, b: p.dataset.to }));
  const findEdge = (f, t) => {
    let e = edges.find((x) => x.a === f && x.b === t);
    if (e) return { e, rev: false };
    e = edges.find((x) => x.a === t && x.b === f);
    return e ? { e, rev: true } : null;
  };

  const layer = document.createElementNS(SVGNS, 'svg');
  layer.setAttribute('class', 'wt-layer');
  layer.setAttribute('width', baseSvg.getAttribute('width'));
  layer.setAttribute('height', baseSvg.getAttribute('height'));
  baseSvg.after(layer);
  const trails = document.createElementNS(SVGNS, 'g');
  const active = document.createElementNS(SVGNS, 'path');
  const dot = document.createElementNS(SVGNS, 'circle');
  dot.setAttribute('r', '6'); dot.setAttribute('class', 'wt-dot');
  layer.append(trails, active, dot);
  const callout = document.createElement('div');
  callout.className = 'wt-callout'; callout.hidden = true;
  canvas.append(callout);

  const stepPath = (st) => {
    if (st.at) return null;
    const hit = findEdge(st.from, st.to);
    if (hit) return { d: hit.e.d, rev: hit.rev, virtual: false };
    const a = nodes[st.from], b = nodes[st.to];
    const mx = (a.cx + b.cx) / 2, my = (a.cy + b.cy) / 2 - Math.max(60, Math.abs(a.cx - b.cx) * 0.15);
    return { d: `M${a.cx} ${a.cy} Q${mx} ${my} ${b.cx} ${b.cy}`, rev: false, virtual: true };
  };

  // Renders `code` spans without innerHTML.
  const rich = (el, text) => {
    el.textContent = '';
    String(text || '').trim().split('`').forEach((part, i) => {
      if (!part) return;
      if (i % 2) { const c = document.createElement('code'); c.textContent = part; el.append(c); }
      else el.append(part);
    });
  };

  let sIdx = 0, i = -1, timer = null, raf = null, fit = false, cur = null;
  const tabs = $('.wt-tabs', panel), list = $('.wt-list', panel);
  DATA.scenarios.forEach((s, k) => {
    const b = document.createElement('button');
    b.textContent = `${k + 1}. ${s.title}`;
    b.onclick = () => selectScenario(k);
    tabs.append(b);
  });

  function selectScenario(k) {
    stop(); sIdx = k; i = -1;
    [...tabs.children].forEach((b, n) => b.classList.toggle('on', n === k));
    const s = DATA.scenarios[k];
    rich($('.wt-summary', panel), s.summary);
    list.textContent = '';
    s.steps.forEach((st, n) => {
      const li = document.createElement('li');
      li.textContent = st.title;
      li.onclick = () => { stop(); go(n); };
      list.append(li);
    });
    go(0);
  }

  function go(n) {
    const steps = DATA.scenarios[sIdx].steps;
    i = Math.max(0, Math.min(steps.length - 1, n));
    const st = steps[i];
    history.replaceState(null, '', `#${sIdx + 1}-${i + 1}`);
    document.body.classList.add('wt-run');

    Object.values(nodes).forEach((nd) => nd.el.classList.remove('wt-active', 'wt-seen'));
    steps.slice(0, i).forEach((p) => [p.at, p.from, p.to].forEach((id) => id && nodes[id].el.classList.add('wt-seen')));
    const ids = st.at ? [st.at] : [st.from, st.to];
    ids.forEach((id) => nodes[id].el.classList.add('wt-active'));

    trails.textContent = '';
    steps.slice(0, i).forEach((p) => {
      const sp = stepPath(p);
      if (!sp) return;
      const t = document.createElementNS(SVGNS, 'path');
      t.setAttribute('d', sp.d); t.setAttribute('class', 'wt-trail');
      trails.append(t);
    });

    cancelAnimationFrame(raf);
    cur = null;
    const sp = stepPath(st);
    active.style.display = dot.style.display = sp ? '' : 'none';
    if (sp) {
      active.setAttribute('d', sp.d);
      active.setAttribute('class', 'wt-edge' + (sp.virtual ? ' virtual' : ''));
      animate(sp.rev);
    }

    const target = nodes[st.at || st.to];
    callout.hidden = false;
    callout.textContent = '';
    const num = document.createElement('b'); num.textContent = i + 1;
    callout.append(num, st.title);
    const right = target.x1 + 10 + callout.offsetWidth > parseFloat(canvas.style.width);
    callout.style.left = (right ? target.x0 - 10 - callout.offsetWidth : target.x1 + 10) + 'px';
    callout.style.top = target.y0 - 34 + 'px';

    $('.wt-route', panel).textContent = st.at ? nodes[st.at].name : `${nodes[st.from].name}  →  ${nodes[st.to].name}`;
    $('h3', panel).textContent = `${i + 1}. ${st.title}`;
    const via = $('.wt-via', panel);
    via.hidden = !st.via; via.textContent = st.via || '';
    rich($('.wt-detail', panel), st.detail);
    const files = $('.wt-files', panel);
    files.textContent = '';
    (st.code || []).forEach((c) => { const s = document.createElement('span'); s.textContent = c; files.append(s); });

    [...list.children].forEach((li, n) => { li.classList.toggle('on', n === i); li.classList.toggle('done', n < i); });
    list.children[i].scrollIntoView({ block: 'nearest' });
    $('.wt-count', panel).textContent = `${i + 1} / ${steps.length}`;
    $('.wt-prev', panel).disabled = i === 0;
    $('.wt-next', panel).disabled = i === steps.length - 1;
    reveal(ids);
  }

  function place(t) {
    if (!cur) return;
    const p = active.getPointAtLength(cur.len * Math.min(1, Math.max(0, cur.rev ? 1 - t : t)));
    dot.setAttribute('cx', p.x); dot.setAttribute('cy', p.y);
    dot.style.opacity = t > 1 ? 0 : 1;
  }

  function animate(rev) {
    cur = { len: active.getTotalLength(), rev };
    const dur = Math.min(2200, 700 + cur.len * 1.4), t0 = performance.now();
    const tick = (now) => { place(((now - t0) % (dur + 400)) / dur); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
  }

  function reveal(ids) {
    if (fit) return;
    const xs = ids.flatMap((id) => [nodes[id].x0, nodes[id].x1]);
    frame.scrollTo({ left: (Math.min(...xs) + Math.max(...xs)) / 2 - frame.clientWidth / 2, behavior: 'smooth' });
    const y = Math.min(...ids.map((id) => nodes[id].y0));
    const top = frame.getBoundingClientRect().top + window.scrollY + y - window.innerHeight / 3;
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
  }

  function setFit(on) {
    fit = on;
    canvas.style.zoom = on ? Math.min(1, (frame.clientWidth - 2) / parseFloat(canvas.style.width)) : '';
    $('.wt-fit', panel).textContent = on ? '100%' : 'fit';
  }

  function play() {
    if (timer) return stop();
    const steps = DATA.scenarios[sIdx].steps;
    if (i >= steps.length - 1) go(0);
    $('.wt-play', panel).textContent = '❚❚ Pause';
    timer = setInterval(() => (i < steps.length - 1 ? go(i + 1) : stop()), 4200);
  }
  function stop() {
    clearInterval(timer); timer = null;
    $('.wt-play', panel).textContent = '▶ Play';
  }
  function reset() {
    stop(); cancelAnimationFrame(raf);
    document.body.classList.remove('wt-run');
    trails.textContent = ''; active.style.display = dot.style.display = 'none'; callout.hidden = true;
    Object.values(nodes).forEach((nd) => nd.el.classList.remove('wt-active', 'wt-seen'));
  }

  $('.wt-prev', panel).onclick = () => { stop(); go(i - 1); };
  $('.wt-next', panel).onclick = () => { stop(); go(i + 1); };
  $('.wt-play', panel).onclick = play;
  $('.wt-fit', panel).onclick = () => setFit(!fit);
  window.addEventListener('resize', () => fit && setFit(true));
  document.addEventListener('keydown', (e) => {
    if (e.target.closest('input,textarea')) return;
    if (e.key === 'ArrowRight') { stop(); go(i + 1); }
    else if (e.key === 'ArrowLeft') { stop(); go(i - 1); }
    else if (e.key === ' ') { e.preventDefault(); play(); }
    else if (e.key === 'f') setFit(!fit);
    else if (e.key === 'Escape') reset();
    else if (/^[1-9]$/.test(e.key) && DATA.scenarios[+e.key - 1]) selectScenario(+e.key - 1);
  });

  // Scripting hook, used by `build --gif` to record frames.
  window.walkthrough = {
    steps: (k) => DATA.scenarios[k].steps,
    select: selectScenario,
    go: (n) => { stop(); go(n); },
    fit: setFit,
    pause: () => cancelAnimationFrame(raf),
    dot: place,
  };

  const m = location.hash.match(/^#(\d+)-(\d+)$/);
  setFit(true);
  selectScenario(m && DATA.scenarios[+m[1] - 1] ? +m[1] - 1 : 0);
  if (m) go(+m[2] - 1);
})();
</script>"""
