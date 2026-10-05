/* Optional dashboard controls. No market requests or external media until requested. */
(() => {
  'use strict';
  const themes = [['dark', 'Dark'], ['light', 'Light'], ['midnight', 'Midnight'], ['ocean', 'Ocean'],
    ['divine', 'Divine Ascension'], ['void', 'Crimson Void'], ['astral', 'Astral Dreamscape'],
    ['forest', 'Forest'], ['ember', 'Ember'], ['sakura', 'Anime: Sakura'], ['neon', 'Anime: Neon']];
  const root = document.documentElement;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const snapshots = new Map();
  const fillSnapshots = new Map();
  const cueTimers = new WeakMap();
  let initialized = false, currentView = '', uptime = null;
  const sessionPreferences = new Map();
  const read = (key, fallback) => { if (sessionPreferences.has(key)) return sessionPreferences.get(key); try { return localStorage.getItem(key) || fallback; } catch (_) { return fallback; } };
  const save = (key, value) => { sessionPreferences.set(key, value); try { localStorage.setItem(key, value); } catch (_) { /* Retain preferences in memory for this session. */ } };
  const allowedTheme = value => themes.some(([id]) => id === value) ? value : 'dark';

  function updateRenderStatus() {
    const panel=document.getElementById('experienceRenderStatus');if(!panel)return;
    const world=worlds[root.dataset.world]?.name||root.dataset.theme||'None';
    const view=(root.dataset.worldView||currentView||'overview').replace(/-/g,' ');
    const tier=(root.dataset.visualResolved||root.dataset.visualDetail||'adaptive').toUpperCase();
    const motionState=(root.dataset.motion||'off').toUpperCase();
    const aura=document.querySelector('.world-aura')?.dataset.state||'CPU';
    panel.querySelector('[data-render-world]').textContent='WORLD '+String(world).toUpperCase();
    panel.querySelector('[data-render-view]').textContent='VIEW '+String(view).toUpperCase();
    panel.querySelector('[data-render-tier]').textContent='RENDER '+tier;
    panel.querySelector('[data-render-motion]').textContent='MOTION '+motionState;
    panel.querySelector('[data-render-aura]').textContent='AURA '+String(aura).toUpperCase();
  }

  function motion() {
    root.dataset.motion = read('icarus-motion', 'system') === 'off' || reduced.matches ? 'off' : 'live';
    if (root.dataset.motion === 'off') document.querySelectorAll('.experience-cue, .experience-fill-cue').forEach(el => {
      clearTimeout(cueTimers.get(el));
      el.classList.remove('experience-cue', 'experience-fill-cue');
    });
    window.IcarusWorldMotion?.refresh();
    window.IcarusWorldImmersion?.sync();
    const note = document.getElementById('experienceMotionNote');
    if (note) note.textContent = reduced.matches ? 'Your system requests reduced motion; all cues are off.' :
      root.dataset.motion === 'off' ? 'All motion is off.' : 'Cinematic scenery and coordinated panel entrances. Market cues remain tied to actual state changes.';
    updateRenderStatus();
  }

  function cue(symbol, kind) {
    if (!initialized || root.dataset.motion !== 'live' || document.hidden) return;
    const card = Array.from(document.querySelectorAll('.asset[data-sym]')).find(el => el.dataset.sym === symbol);
    const target = card || (currentView === 'asset:' + symbol ? document.getElementById('assetHead') : null);
    if (!target) return;
    clearTimeout(cueTimers.get(target));
    target.classList.add(kind === 'fill' ? 'experience-fill-cue' : 'experience-cue');
    cueTimers.set(target, setTimeout(() => target.classList.remove('experience-cue', 'experience-fill-cue'), 700));
  }

  function update(data, view) {
    const changedView=currentView !== view;
    if (changedView) window.IcarusWorldCinema?.enterView();
    currentView = view;
    if (changedView) syncSceneView(view);
    if (uptime !== null && Number(data.uptime_sec) < uptime) { snapshots.clear(); fillSnapshots.clear(); }
    uptime = Number(data.uptime_sec);
    const active = new Set();
    for (const asset of data.assets || []) {
      active.add(asset.symbol);
      const state = asset.state || {};
      const next = {ready: asset.warm === true && !asset.rewarming, bar: asset.bar_index,
        signature: JSON.stringify([state.rate_uptrend, state.rate_regime_str, state.pulse_state, asset.position])};
      const previous = snapshots.get(asset.symbol);
      if (previous && previous.ready && next.ready && next.bar > previous.bar && next.signature !== previous.signature) cue(asset.symbol, 'state');
      if (!next.ready || (previous && next.bar < previous.bar)) fillSnapshots.delete(asset.symbol);
      snapshots.set(asset.symbol, next);
    }
    for (const symbol of snapshots.keys()) if (!active.has(symbol)) { snapshots.delete(symbol); fillSnapshots.delete(symbol); }
    updateRenderStatus();
  }

  function chart(data, windowSize, element) {
    window.IcarusWorldCinema?.enterChart(data.symbol, element);
    const rows = data.fills || [];
    const key = fill => JSON.stringify([fill.ts, fill.bar, fill.id, fill.side, fill.qty, fill.price, fill.kind, fill.comment, fill.profit, fill.pos]);
    const previous = fillSnapshots.get(data.symbol);
    const sameWindow = previous && previous.liveFrom === data.live_from && previous.windowSize === windowSize;
    const latest = Math.max(0, ...rows.map(fill => Number(fill.ts) || 0));
    const ready = snapshots.get(data.symbol)?.ready;
    if (ready && sameWindow && rows.some(fill =>
      fill.live === true && fill.ts >= previous.latest && !previous.keys.has(key(fill)))) cue(data.symbol, 'fill');
    // First response, a different requested history window and a new process establish a baseline.
    fillSnapshots.set(data.symbol, {liveFrom: data.live_from, windowSize, latest: sameWindow ? Math.max(latest, previous.latest) : latest,
      keys: new Set(rows.map(key))});
  }

  const worlds = {
    divine: {name: 'Divine Ascension', title: 'The one above all.', caption: 'A throne above the clouds. A horizon without limits.', mark: 'I', phase: 'CROWN / LIGHT / INFINITY'},
    void: {name: 'Crimson Void', title: 'Market Destroyer.', caption: 'From the silence. Beyond the noise.', mark: 'II', phase: 'RUPTURE / SILENCE / EMBER'},
    astral: {name: 'Astral Dreamscape', title: 'Beyond the horizon.', caption: 'An observatory at the edge of possibility.', mark: 'III', phase: 'ORBIT / AETHER / HORIZON'},
  };
  const viewInsignia = {
    overview:['◇','OVERVIEW'],asset:['◈','ASSET CHAMBER'],system:['⌬','SYSTEM'],golive:['▲','GO LIVE'],agent:['◎','FIELD AGENT'],
    inputs:['≡','INPUTS'],backtest:['∿','BACKTEST'],research:['∆','RESEARCH'],sources:['⌁','FINANCIAL / DATA'],'market-data':['⋮','MARKET DATA'],
    brain:['◉','ADAPTIVE BRAIN'],evolution:['↟','MCP EVOLUTION'],parallax:['⟁','PARALLAX / DREAMSTATE'],possibility:['Ψ','ICARUS Ψ'],
    pantheon:['✦','PANTHEON / AETHER'],sibyl:['Ω','SIBYL Ω'],apex:['⌬','APEX Ω'],ascendancy:['↑','ASCENDANCY'],
    learning:['∞','LEARNING FABRIC'],chronofold:['Ξ','ICARUS Ξ'],commissioning:['◫','COMMISSIONING'],integrity:['◆','DATA INTEGRITY'],
    'engine-control':['⌘','ENGINE CONTROL'],commands:['⌗','COMMANDS'],log:['▥','ENGINE LOG'],autopilot:['➤','TACTICAL AUTOPILOT']
  };
  let scenery, sceneObserver;
  function syncSceneView(view=currentView||'overview') {
    if(!scenery)return;
    const key=String(view||'overview').startsWith('asset:')?'asset':String(view||'overview').replace(/^#/,'');
    const meta=viewInsignia[key]||['◇',key.replace(/-/g,' ').toUpperCase()];
    const badge=scenery.querySelector('.world-view-insignia');if(!badge)return;
    badge.querySelector('i').textContent=meta[0];badge.querySelector('b').textContent=meta[1];
    badge.dataset.view=key;badge.classList.remove('world-view-insignia-shift');void badge.offsetWidth;badge.classList.add('world-view-insignia-shift');
    setTimeout(()=>badge?.classList.remove('world-view-insignia-shift'),760);
  }
  const preference = (key, values, fallback) => {
    const value = read('icarus-' + key, fallback);
    return values.includes(value) ? value : fallback;
  };
  function appearance() {
    const world = worlds[root.dataset.theme];
    root.dataset.world = world ? root.dataset.theme : '';
    root.dataset.experience = preference('experience', ['cinematic', 'balanced', 'focus'], 'cinematic');
    root.dataset.density = preference('density', ['comfortable', 'compact'], 'comfortable');
    root.dataset.accent = preference('accent', ['world', 'gold', 'ice', 'amethyst'], 'world');
    root.dataset.visualDetail = preference('visual-detail', ['adaptive', 'rich', 'light'], 'adaptive');
    root.dataset.sceneSize = preference('scene-size', ['compact', 'grand', 'panorama'], 'grand');
    root.dataset.lighting = preference('lighting', ['original', 'obsidian'], 'obsidian');
    root.dataset.introLength = preference('intro-length', ['12', '20'], '20');
    if (!scenery) return;
    scenery.hidden = !world || root.dataset.experience === 'focus';
    const previousWorld = scenery.dataset.activeWorld;
    const changedWorld = scenery.dataset.activeWorld !== root.dataset.world;
    scenery.dataset.activeWorld = root.dataset.world;
    if (world) {
      document.getElementById('worldName').textContent = world.name;
      document.getElementById('worldTitle').textContent = world.title;
      document.getElementById('worldTitle').setAttribute('aria-label',world.title);
      document.getElementById('worldCaption').textContent = world.caption;
      document.getElementById('worldMark').textContent = world.mark;
      document.getElementById('worldCoordinatePhase').textContent = world.phase;
      // Exact local assets only. No market data or authenticated URLs enter this layer.
      scenery.style.setProperty('--world-art', `url("/worlds/${root.dataset.theme}.webp")`);
    }
    if (world && changedWorld) {
      const art = scenery.querySelector('.world-art');
      art.classList.remove('world-enter');
      void art.offsetWidth;
      art.classList.add('world-enter');
      window.IcarusWorldCinema?.transitionWorld(scenery,previousWorld);
    }
    for (const button of scenery.querySelectorAll('[data-world-choice]')) button.setAttribute('aria-pressed', String(button.dataset.worldChoice === root.dataset.theme));
    window.IcarusWorldMotion?.refresh();
    window.IcarusWorldImmersion?.sync();
    const focus = document.getElementById('experienceFocus');
    focus.setAttribute('aria-pressed', String(root.dataset.experience === 'focus'));
    focus.textContent = root.dataset.experience === 'focus' ? 'Restore scenery' : 'Focus';
    document.getElementById('experienceMode').value = root.dataset.experience;
    updateRenderStatus();
  }

  function init({onThemeChanged} = {}) {
    if (initialized) return;
    initialized = true;
    root.dataset.theme = allowedTheme(read('icarus-theme', 'divine'));
    const controls = document.createElement('div');
    controls.className = 'experience-controls';
    controls.innerHTML = `<details class="experience-settings"><summary aria-label="Appearance and motion settings">Style</summary><div>
      <label>Theme<select id="experienceTheme"></select></label>
      <label>Atmosphere<select id="experienceMode"><option value="balanced">Balanced · still scenery</option><option value="cinematic">Cinematic · Eclipse Loom</option><option value="focus">Focus · essentials</option></select></label>
      <label>Accent<select id="experienceAccent"><option value="world">World signature</option><option value="gold">Sovereign gold</option><option value="ice">Glacier silver</option><option value="amethyst">Astral amethyst</option></select></label>
      <label>Visual detail<select id="experienceVisualDetail"><option value="adaptive">Adaptive</option><option value="rich">Rich · full atmosphere</option><option value="light">Light · lean geometry</option></select></label>
      <label>Scene scale<select id="experienceSceneSize"><option value="compact">Compact</option><option value="grand">Grand</option><option value="panorama">Panorama</option></select></label>
      <label>Lighting<select id="experienceLighting"><option value="obsidian">Obsidian · dark divinity</option><option value="original">Original world palette</option></select></label>
      <label>Opening<select id="experienceIntroLength"><option value="20">Epic · 20 seconds</option><option value="12">Classic · 12 seconds</option></select></label>
      <label>Density<select id="experienceDensity"><option value="comfortable">Comfortable</option><option value="compact">Trading desk</option></select></label>
      <label>Motion<select id="experienceMotion"><option value="system">Follow system</option><option value="off">No motion</option></select></label>
      <div class="experience-render-status" id="experienceRenderStatus" aria-live="polite"><span data-render-world>WORLD —</span><span data-render-view>VIEW —</span><span data-render-tier>RENDER —</span><span data-render-motion>MOTION —</span><span data-render-aura>AURA —</span></div>
      <button type="button" id="experienceSound" class="sm" aria-pressed="false">Enable celestial sound</button>
      <button type="button" id="experienceReplay" class="sm">Replay cinematic intro</button><p id="experienceMotionNote"></p><p>Original anime worlds. Scenic titles and effects are decorative, independent of market activity.</p>
      </div></details><button class="icon-btn" id="experienceFocus" aria-pressed="false">Focus</button><button class="icon-btn" id="experienceMusicToggle" aria-expanded="false" aria-controls="experienceMusic">Music</button>`;
    document.getElementById('btnTheme').insertAdjacentElement('afterend', controls);
    const select = document.getElementById('experienceTheme');
    for (const [id, label] of themes) { const option = document.createElement('option'); option.value = id; option.textContent = label; select.appendChild(option); }
    select.value = root.dataset.theme;
    select.addEventListener('change', () => {
      root.dataset.theme = allowedTheme(select.value);
      save('icarus-theme', root.dataset.theme);
      appearance();
      onThemeChanged?.();
      window.IcarusWorldCinema?.enterView();
    });
    document.getElementById('btnTheme').addEventListener('click', () => { select.value = allowedTheme(root.dataset.theme); appearance(); });
    const motionSelect = document.getElementById('experienceMotion');
    motionSelect.value = read('icarus-motion', 'system') === 'off' ? 'off' : 'system';
    motionSelect.addEventListener('change', () => { save('icarus-motion', motionSelect.value); motion(); });
    reduced.addEventListener('change', motion);
    scenery = document.createElement('section');
    scenery.className = 'world-scene'; scenery.hidden = true;
    scenery.setAttribute('aria-label', 'ICARUS visual world');
    scenery.innerHTML = `<div class="world-art" aria-hidden="true"></div>
      <div class="world-preview" aria-hidden="true"><i></i><b></b></div>
      <div class="world-orbit" aria-hidden="true"><i></i><i></i><i></i><b>◇</b></div>
      <div class="world-coordinate" aria-hidden="true">ECLIPSE LOOM <span id="worldCoordinatePhase">CROWN / LIGHT / INFINITY</span></div>
      <div class="world-scene-threshold" aria-hidden="true"><i></i><b></b><span></span></div>
      <div class="world-view-insignia" aria-hidden="true" data-view="overview"><span>ACTIVE DOMAIN</span><i>◇</i><b>OVERVIEW</b></div>
      <div class="world-copy"><div class="world-eyebrow">ICARUS <span> / </span><span id="worldName"></span></div>
      <h1 id="worldTitle"></h1><p id="worldCaption"></p>
      <div class="world-switch" role="group" aria-label="Choose visual world">
        <button type="button" data-world-choice="divine">01 <span>Divine</span></button>
        <button type="button" data-world-choice="void">02 <span>Void</span></button>
        <button type="button" data-world-choice="astral">03 <span>Astral</span></button>
      </div></div><div class="world-edition" aria-hidden="true"><span id="worldMark"></span> / ICARUS WORLDS</div>`;
    document.getElementById('view').insertAdjacentElement('beforebegin', scenery);
    const preview=scenery.querySelector('.world-preview');
    const clearWorldPreview=()=>{
      if(!preview)return;preview.classList.remove('active');preview.removeAttribute('data-preview-world');preview.style.removeProperty('--preview-art');
      scenery.removeAttribute('data-preview-world');
    };
    const showWorldPreview=id=>{
      if(!preview||!worlds[id]||id===root.dataset.world)return clearWorldPreview();
      preview.dataset.previewWorld=id;preview.style.setProperty('--preview-art',`url('/worlds/${id}.webp')`);
      scenery.dataset.previewWorld=id;preview.classList.add('active');
    };
    for (const button of scenery.querySelectorAll('[data-world-choice]')) {
      button.addEventListener('pointerenter',()=>showWorldPreview(button.dataset.worldChoice),{passive:true});
      button.addEventListener('pointerleave',clearWorldPreview,{passive:true});
      button.addEventListener('focus',()=>showWorldPreview(button.dataset.worldChoice));
      button.addEventListener('blur',clearWorldPreview);
      button.addEventListener('click', () => {
        clearWorldPreview();
        select.value = button.dataset.worldChoice;
        select.dispatchEvent(new Event('change'));
      });
    }
    for (const [id, key, values, fallback] of [
      ['experienceMode', 'experience', ['cinematic', 'balanced', 'focus'], 'cinematic'],
      ['experienceAccent', 'accent', ['world', 'gold', 'ice', 'amethyst'], 'world'],
      ['experienceVisualDetail', 'visual-detail', ['adaptive', 'rich', 'light'], 'adaptive'],
      ['experienceSceneSize', 'scene-size', ['compact', 'grand', 'panorama'], 'grand'],
      ['experienceLighting', 'lighting', ['original', 'obsidian'], 'obsidian'],
      ['experienceIntroLength', 'intro-length', ['12', '20'], '20'],
      ['experienceDensity', 'density', ['comfortable', 'compact'], 'comfortable'],
    ]) {
      const input = document.getElementById(id);
      input.value = preference(key, values, fallback);
      input.addEventListener('change', () => {
        save('icarus-' + key, input.value); appearance(); onThemeChanged?.();
      });
    }
    document.getElementById('experienceFocus').addEventListener('click', () => {
      const next = root.dataset.experience === 'focus' ? preference('previous-atmosphere', ['cinematic', 'balanced'], 'balanced') : 'focus';
      if (next === 'focus') save('icarus-previous-atmosphere', root.dataset.experience);
      save('icarus-experience', next); appearance();
    });
    const pauseScenery = () => { root.dataset.scenePaused = document.hidden ? 'true' : 'false'; };
    document.addEventListener('visibilitychange', pauseScenery); pauseScenery();
    if ('IntersectionObserver' in window) {
      sceneObserver = new IntersectionObserver(entries => {
        scenery.dataset.visible = entries[0].isIntersecting ? 'true' : 'false';
      });
      sceneObserver.observe(scenery);
    }
    syncSceneView(currentView||'overview');
    window.IcarusWorldMotion?.init(scenery);
    const renderObserver=new MutationObserver(updateRenderStatus);
    renderObserver.observe(root,{attributes:true,attributeFilter:['data-world','data-world-view','data-visual-resolved','data-visual-detail','data-motion','data-experience']});
    const auraObserver=new MutationObserver(updateRenderStatus);
    const auraNode=document.querySelector('.world-aura');if(auraNode)auraObserver.observe(auraNode,{attributes:true,attributeFilter:['data-state']});
    appearance(); motion();updateRenderStatus();
    document.getElementById('experienceReplay').addEventListener('click', () => window.IcarusWorldMotion?.playIntro());
    document.getElementById('experienceSound').addEventListener('click', event => window.IcarusWorldCinema?.toggleSound(event.currentTarget));
    window.IcarusWorldMotion?.startup();

    const panel = document.createElement('section');
    panel.id = 'experienceMusic'; panel.className = 'experience-music'; panel.hidden = true;
    panel.setAttribute('aria-label', 'Dreambound music player');
    panel.innerHTML = `<header><h2>Dreambound</h2><button class="sm" id="experienceMusicClose">Close &amp; stop</button></header>
      <div class="experience-player" id="experiencePlayer"><button id="experienceMusicLoad">Load public playlist</button></div>
      <p><a href="https://www.youtube.com/@Dreambound/videos" target="_blank" rel="noopener noreferrer">Official channel and full public catalog</a>
      &middot; <a href="https://www.youtube.com/playlist?list=UUo9OXAWEwN6nnX5c3hL0OaA" target="_blank" rel="noopener noreferrer">Open uploads on YouTube</a></p>
      <p id="experienceMusicNote">Loads YouTube only when you choose the playlist. Use the player's play, pause, volume and playlist controls.</p>
      <p>Availability is controlled by YouTube and the uploaders. Private, deleted, age- or region-restricted, and embed-blocked videos may not play here. If the player is blank or unavailable, open the uploads on YouTube.</p>`;
    document.body.appendChild(panel);
    const toggle = document.getElementById('experienceMusicToggle');
    const player = document.getElementById('experiencePlayer');
    const load = document.getElementById('experienceMusicLoad');
    const close = () => {
      player.querySelector('iframe')?.remove();
      player.appendChild(load); load.hidden = false; panel.hidden = true;
      toggle.setAttribute('aria-expanded', 'false'); toggle.focus();
    };
    toggle.addEventListener('click', () => {
      if (!panel.hidden) { close(); return; }
      panel.hidden = false; toggle.setAttribute('aria-expanded', 'true');
      document.getElementById('experienceMusicClose').focus();
    });
    document.getElementById('experienceMusicClose').addEventListener('click', close);
    panel.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } });
    load.addEventListener('click', () => {
      const iframe = document.createElement('iframe');
      iframe.title = 'Dreambound public uploads - YouTube player';
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      iframe.allow = 'encrypted-media; fullscreen; picture-in-picture';
      iframe.allowFullscreen = true;
      iframe.src = 'https://www.youtube-nocookie.com/embed/videoseries?list=UUo9OXAWEwN6nnX5c3hL0OaA&listType=playlist&autoplay=0&playsinline=1';
      player.replaceChildren(iframe);
    });
  }

  window.IcarusExperience = Object.freeze({init, update, chart});
})();
