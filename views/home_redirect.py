"""Root landing page for the Commons Simulator."""

import streamlit as st


st.html(
    """
    <style>
    :root {
      --landing-ink: #10110f;
      --landing-paper: #f4f1e8;
      --landing-acid: #c9fa1a;
      --landing-green: #74a91c;
      --landing-line: rgba(16, 17, 15, .22);
    }

    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapsedControl"],
    #MainMenu,
    footer {
      display: none !important;
    }

    .stApp {
      background: var(--landing-paper);
      color: var(--landing-ink);
    }

    .block-container {
      width: 100%;
      max-width: none;
      padding: 0 !important;
    }

    [data-testid="stVerticalBlock"],
    [data-testid="stVerticalBlockBorderWrapper"] {
      gap: 0 !important;
    }

    .landing-shell {
      min-height: 100svh;
      padding: clamp(2rem, 4.5vw, 5.25rem) clamp(1.5rem, 5.5vw, 7rem)
        clamp(2rem, 4vw, 4.5rem);
      display: grid;
      grid-template-rows: auto 1fr;
      overflow: hidden;
      background:
        radial-gradient(circle at 74% 52%, rgba(255, 255, 255, .33), transparent 32rem),
        var(--landing-paper);
    }

    .landing-nav {
      position: relative;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 2rem;
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: clamp(.76rem, 1.2vw, 1.05rem);
      font-weight: 500;
      letter-spacing: -.035em;
      text-transform: uppercase;
    }

    .landing-brand,
    .landing-nav a {
      color: var(--landing-ink) !important;
      text-decoration: none !important;
    }

    .landing-links {
      display: flex;
      align-items: center;
      gap: clamp(1.4rem, 3.5vw, 4rem);
    }

    .landing-nav a {
      position: relative;
      padding: .25rem 0;
    }

    .landing-nav a::after {
      content: "";
      position: absolute;
      left: 0;
      right: 100%;
      bottom: -.15rem;
      height: 1px;
      background: var(--landing-ink);
      transition: right 180ms ease;
    }

    .landing-nav a:hover::after,
    .landing-nav a:focus-visible::after {
      right: 0;
    }

    .landing-hero {
      display: grid;
      grid-template-columns: minmax(22rem, .82fr) minmax(32rem, 1.18fr);
      align-items: center;
      gap: clamp(2rem, 4vw, 5rem);
      min-height: 0;
    }

    .landing-copy {
      position: relative;
      z-index: 4;
      padding: clamp(4rem, 10vh, 8.5rem) 0 clamp(2rem, 6vh, 5rem)
        clamp(0rem, 2.6vw, 3.25rem);
    }

    .landing-title {
      margin: 0 !important;
      color: var(--landing-ink) !important;
      font-family: "Manrope", Arial, sans-serif !important;
      font-size: clamp(4.2rem, 7.35vw, 8.8rem) !important;
      font-weight: 600 !important;
      letter-spacing: -.075em !important;
      line-height: .88 !important;
      max-width: 8ch;
    }

    .landing-deck {
      margin: clamp(2.2rem, 5vh, 4.7rem) 0 0 !important;
      max-width: 22ch;
      color: var(--landing-ink) !important;
      font-family: "Manrope", Arial, sans-serif !important;
      font-size: clamp(1.15rem, 1.65vw, 1.8rem) !important;
      font-weight: 600;
      letter-spacing: -.035em;
      line-height: 1.5;
    }

    .landing-enter {
      display: inline-flex;
      align-items: center;
      justify-content: space-between;
      gap: 2rem;
      min-width: min(100%, 27rem);
      margin-top: clamp(2.2rem, 5vh, 4.6rem);
      padding: 1.15rem 1.65rem 1.15rem 2rem;
      border: 0;
      border-radius: 999px;
      background: var(--landing-acid);
      color: var(--landing-ink) !important;
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: clamp(.9rem, 1.25vw, 1.2rem);
      font-weight: 600;
      letter-spacing: -.045em;
      line-height: 1;
      text-decoration: none !important;
      transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }

    .landing-enter span {
      font-size: 1.35em;
      transition: transform 180ms ease;
    }

    .landing-enter:hover,
    .landing-enter:focus-visible {
      background: #d6ff41;
      box-shadow: 0 .8rem 2.2rem rgba(100, 135, 0, .18);
      transform: translateY(-2px);
    }

    .landing-enter:hover span,
    .landing-enter:focus-visible span {
      transform: translateX(.3rem);
    }

    .landing-enter:focus-visible,
    .landing-nav a:focus-visible {
      outline: 2px solid var(--landing-ink);
      outline-offset: 5px;
    }

    .landing-principles {
      position: relative;
      z-index: 5;
      width: min(76vw, 78rem);
      margin-top: clamp(3.2rem, 7vh, 6rem);
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      color: var(--landing-ink);
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
    }

    .landing-principle {
      min-width: 0;
      display: grid;
      grid-template-columns: 4.4rem minmax(0, 1fr);
      align-items: center;
      gap: 1.25rem;
      padding: .2rem clamp(1.3rem, 2.4vw, 2.8rem);
    }

    .landing-principle:first-child {
      padding-left: 0;
    }

    .landing-principle + .landing-principle {
      border-left: 1px solid rgba(16, 17, 15, .17);
    }

    .landing-principle h3 {
      margin: 0 0 .5rem !important;
      color: var(--landing-ink) !important;
      font-family: inherit !important;
      font-size: clamp(.78rem, .95vw, 1rem) !important;
      font-weight: 600 !important;
      letter-spacing: -.035em !important;
      line-height: 1.25 !important;
    }

    .landing-principle p {
      margin: 0 !important;
      color: rgba(16, 17, 15, .5) !important;
      font-family: inherit !important;
      font-size: clamp(.7rem, .86vw, .92rem) !important;
      letter-spacing: -.035em;
      line-height: 1.65;
    }

    .principle-icon {
      position: relative;
      display: block;
      width: 4rem;
      height: 4rem;
      color: var(--landing-acid);
    }

    .principle-icon--actors {
      display: grid;
      grid-template-columns: repeat(3, .72rem);
      grid-template-rows: repeat(3, .72rem);
      place-content: center;
      gap: .38rem;
    }

    .principle-icon--actors i {
      width: .72rem;
      height: .72rem;
      border-radius: 50%;
      background: currentColor;
      box-shadow: 0 0 .6rem rgba(201, 250, 26, .3);
    }

    .principle-icon--actors i:nth-child(3n + 1) { opacity: .55; }
    .principle-icon--actors i:nth-child(5) { opacity: 0; }

    .principle-icon--connection::before {
      content: "";
      position: absolute;
      width: 3.2rem;
      height: 1px;
      left: .45rem;
      top: 1rem;
      background: currentColor;
      transform: rotate(47deg);
      transform-origin: left center;
      opacity: .65;
    }

    .principle-icon--connection i {
      position: absolute;
      width: .82rem;
      height: .82rem;
      border-radius: 50%;
      background: currentColor;
      box-shadow: 0 0 .65rem rgba(201, 250, 26, .36);
    }

    .principle-icon--connection i:first-child {
      left: .15rem;
      top: .55rem;
    }

    .principle-icon--connection i:nth-child(2) {
      left: 1.55rem;
      top: 2rem;
      width: .5rem;
      height: .5rem;
      opacity: .64;
    }

    .principle-icon--connection i:last-child {
      right: .1rem;
      bottom: .35rem;
    }

    .principle-icon--future {
      display: grid;
      place-items: center;
      border: 2px solid rgba(201, 250, 26, .62);
      border-radius: 50%;
      box-shadow:
        0 0 .7rem rgba(201, 250, 26, .16),
        inset 0 0 .55rem rgba(201, 250, 26, .09);
    }

    .principle-icon--future i {
      width: .75rem;
      height: .75rem;
      border-radius: 50%;
      background: currentColor;
      box-shadow: 0 0 .7rem rgba(201, 250, 26, .42);
    }

    .landing-visual {
      position: relative;
      align-self: stretch;
      min-height: min(76vw, 62rem);
      pointer-events: none;
    }

    .living-network-stage {
      position: absolute;
      width: min(52vw, 63rem);
      aspect-ratio: 1.08;
      left: 50%;
      top: 52%;
      transform: translate(-44%, -47%);
      isolation: isolate;
    }

    .living-network {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      overflow: visible;
    }

    .commons-core {
      position: absolute;
      z-index: 3;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      padding: 2.4rem 3.5rem;
      border-radius: 50%;
      background:
        radial-gradient(
          ellipse at center,
          var(--landing-paper) 0 45%,
          rgba(244, 241, 232, .96) 62%,
          rgba(244, 241, 232, 0) 76%
        );
      color: var(--landing-ink);
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: clamp(.7rem, 1vw, 1.05rem);
      font-weight: 500;
      letter-spacing: -.04em;
      line-height: 1;
      white-space: nowrap;
    }

    .landing-about {
      min-height: 68svh;
      padding: clamp(5rem, 10vw, 11rem) clamp(1.5rem, 8vw, 10rem);
      display: grid;
      grid-template-columns: minmax(12rem, .55fr) minmax(18rem, 1fr);
      gap: clamp(2rem, 8vw, 9rem);
      align-items: start;
      border-top: 1px solid rgba(16, 17, 15, .16);
      background: #ebe8df;
    }

    .landing-about-label {
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: .82rem;
      letter-spacing: .08em;
      text-transform: uppercase;
    }

    .landing-about h2 {
      margin: 0 0 2rem !important;
      max-width: 12ch;
      color: var(--landing-ink) !important;
      font-size: clamp(2.6rem, 5vw, 5.8rem) !important;
      font-weight: 600 !important;
      letter-spacing: -.065em !important;
      line-height: .97 !important;
    }

    .landing-about p {
      max-width: 46rem;
      color: var(--landing-ink) !important;
      font-size: clamp(1.05rem, 1.5vw, 1.45rem) !important;
      line-height: 1.65;
    }

    @media (max-width: 900px) {
      .landing-shell {
        min-height: auto;
      }

      .landing-hero {
        grid-template-columns: 1fr;
      }

      .landing-copy {
        padding: clamp(5rem, 14vh, 8rem) 0 1rem;
      }

      .landing-title {
        font-size: clamp(4rem, 15vw, 7.8rem) !important;
      }

      .landing-deck {
        font-size: clamp(1.1rem, 4vw, 1.45rem) !important;
      }

      .landing-enter {
        min-width: min(100%, 25rem);
      }

      .landing-visual {
        min-height: min(92vw, 43rem);
      }

      .living-network-stage {
        width: min(94vw, 46rem);
        left: 52%;
        top: 48%;
        transform: translate(-50%, -50%);
      }

      .landing-principles {
        width: 100%;
      }
    }

    @media (max-width: 760px) {
      .landing-principles {
        grid-template-columns: 1fr;
        margin-top: 3rem;
      }

      .landing-principle {
        padding: 1.35rem 0;
      }

      .landing-principle + .landing-principle {
        border-top: 1px solid rgba(16, 17, 15, .14);
        border-left: 0;
      }
    }

    @media (max-width: 600px) {
      .landing-shell {
        padding: 1.35rem 1.15rem 2.5rem;
      }

      .landing-links {
        gap: 1rem;
      }

      .landing-brand {
        max-width: 8rem;
        line-height: 1.2;
      }

      .landing-copy {
        padding-top: 5.5rem;
      }

      .landing-title {
        font-size: clamp(3.85rem, 19vw, 5.4rem) !important;
      }

      .landing-deck {
        margin-top: 2rem !important;
      }

      .landing-enter {
        width: 100%;
        min-width: 0;
        margin-top: 2.2rem;
        padding: 1rem 1.35rem 1rem 1.55rem;
      }

      .landing-about {
        grid-template-columns: 1fr;
        min-height: auto;
        padding: 5rem 1.25rem;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .landing-enter,
      .landing-enter span,
      .landing-nav a::after {
        transition: none;
      }

      .commons-core {
        padding: 1.8rem 2.6rem;
      }
    }
    </style>

    <main>
      <section class="landing-shell" aria-labelledby="landing-title">
        <nav class="landing-nav" aria-label="Primary navigation">
          <a class="landing-brand" href="./">Commons Evolver</a>
          <div class="landing-links">
            <a href="#about">About</a>
            <a href="./commons-map">Explore</a>
          </div>
        </nav>

        <div class="landing-hero">
          <div class="landing-copy">
            <h1 class="landing-title" id="landing-title">Commons<br>Evolver</h1>
            <p class="landing-deck">A strategic simulation for shared systems and collective decision-making.</p>
            <a class="landing-enter" href="./commons">
              Enter the simulator <span aria-hidden="true">→</span>
            </a>

            <div class="landing-principles" aria-label="How the simulator works">
              <div class="landing-principle">
                <span class="principle-icon principle-icon--actors" aria-hidden="true">
                  <i></i><i></i><i></i>
                  <i></i><i></i><i></i>
                  <i></i><i></i><i></i>
                </span>
                <div>
                  <h3>Many actors</h3>
                  <p>Diverse voices<br>shape the system.<br /> This is multiscale.</p>
                </div>
              </div>

              <div class="landing-principle">
                <span class="principle-icon principle-icon--connection" aria-hidden="true">
                  <i></i><i></i><i></i>
                </span>
                <div>
                  <h3>Connected choices</h3>
                  <p>Actions influence<br>what comes next. <br />This is nonlinear.</p>
                </div>
              </div>

              <div class="landing-principle">
                <span class="principle-icon principle-icon--future" aria-hidden="true">
                  <i></i>
                </span>
                <div>
                  <h3>Evolving futures</h3>
                  <p>No fixed path.<br>Multiple possibilities.<br />This is emergent.</p>
                </div>
              </div>
            </div>
          </div>

          <div class="landing-visual" aria-hidden="true">
            <div class="living-network-stage">
              <canvas class="living-network"></canvas>
              <div class="commons-core">[[ commons ]]</div>
            </div>
          </div>
        </div>
      </section>

      <section class="landing-about" id="about" aria-labelledby="about-title">
        <div class="landing-about-label">About the simulation</div>
        <div>
          <h2 id="about-title">One situation. One strategic move.</h2>
          <p>
            Choose how you would act when a shared resource reaches a threshold,
            explain why, and add your anonymous trajectory to the Commons Map.
          </p>
        </div>
      </section>
    </main>

    <script>
    (() => {
      const script = document.currentScript;
      const root = script && script.parentElement;
      const canvas = root && root.querySelector(".living-network");
      if (!canvas || canvas.dataset.networkReady) return;
      canvas.dataset.networkReady = "true";

      const context = canvas.getContext("2d");
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
      const TAU = Math.PI * 2;
      const INK = [16, 17, 15];
      const GREEN = [93, 132, 31];
      const links = new Map();
      let width = 0;
      let height = 0;
      let pixelRatio = 1;
      let animationFrame = 0;

      function randomGenerator(seed) {
        return function random() {
          seed |= 0;
          seed = seed + 0x6D2B79F5 | 0;
          let value = Math.imul(seed ^ seed >>> 15, 1 | seed);
          value = value + Math.imul(value ^ value >>> 7, 61 | value) ^ value;
          return ((value ^ value >>> 14) >>> 0) / 4294967296;
        };
      }

      const random = randomGenerator(20260724);
      const actors = Array.from({ length: 34 }, (_, index) => ({
        index,
        family: Math.floor(random() * 6),
        phase: random() * TAU,
        noisePhase: random() * TAU,
        direction: random() > .45 ? 1 : -1,
        speed: .09 + random() * .14,
        radiusX: .27 + random() * .29,
        radiusY: .17 + random() * .25,
        radiusZ: .16 + random() * .3,
        rotateX: (random() - .5) * 1.7,
        rotateY: (random() - .5) * 1.55,
        rotateZ: random() * TAU,
        noise: .025 + random() * .055,
        drift: .012 + random() * .025,
        driftSpeed: .05 + random() * .09,
        size: 2.2 + random() * 5.2 + (index % 11 === 0 ? 4.5 : 0),
        green: random() < .28,
      }));

      const orbitActors = actors.filter((_, index) => index < 12);

      function clamp(value, minimum = 0, maximum = 1) {
        return Math.max(minimum, Math.min(maximum, value));
      }

      function rgba(color, alpha) {
        return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
      }

      function rotate3d(point, actor) {
        let { x, y, z } = point;
        let cosine = Math.cos(actor.rotateX);
        let sine = Math.sin(actor.rotateX);
        [y, z] = [y * cosine - z * sine, y * sine + z * cosine];

        cosine = Math.cos(actor.rotateY);
        sine = Math.sin(actor.rotateY);
        [x, z] = [x * cosine + z * sine, -x * sine + z * cosine];

        cosine = Math.cos(actor.rotateZ);
        sine = Math.sin(actor.rotateZ);
        [x, y] = [x * cosine - y * sine, x * sine + y * cosine];
        return { x, y, z };
      }

      function worldPosition(actor, angle, time) {
        const organicRadius =
          1
          + actor.noise * Math.sin(angle * 3 + actor.noisePhase)
          + actor.noise * .42 * Math.sin(angle * 7 - actor.noisePhase * .6);
        const local = {
          x:
            actor.radiusX * organicRadius * Math.cos(angle)
            + actor.noise * .7 * Math.sin(angle * 5 + actor.noisePhase),
          y:
            actor.radiusY * (1 + actor.noise * Math.cos(angle * 4)) * Math.sin(angle)
            + actor.noise * .55 * Math.cos(angle * 3 - actor.noisePhase),
          z:
            actor.radiusZ * (
              .72 * Math.sin(angle * 2 + actor.noisePhase)
              + .28 * Math.sin(angle * 3 - actor.noisePhase * .45)
            ),
        };
        const world = rotate3d(local, actor);
        const slowDrift = Math.sin(time * actor.driftSpeed + actor.noisePhase);
        world.x += actor.drift * slowDrift;
        world.y += actor.drift * Math.cos(time * actor.driftSpeed * .77 + actor.phase);
        world.z += actor.drift * .7 * Math.sin(time * actor.driftSpeed * .61 + actor.phase);
        return world;
      }

      function project(point) {
        const scale = Math.min(width, height) * .91;
        const camera = 2.25;
        const perspective = camera / (camera - point.z * .7);
        return {
          x: width * .5 + point.x * scale * perspective,
          y: height * .5 + point.y * scale * perspective,
          depth: clamp((point.z + .72) / 1.44),
          world: point,
        };
      }

      function pairSeed(first, second) {
        const value = Math.sin((first + 1) * 12.9898 + (second + 1) * 78.233);
        return value * 43758.5453 - Math.floor(value * 43758.5453);
      }

      function resizeCanvas() {
        const bounds = canvas.getBoundingClientRect();
        if (!bounds.width || !bounds.height) return false;
        const nextRatio = Math.min(window.devicePixelRatio || 1, 1.75);
        const nextWidth = Math.round(bounds.width);
        const nextHeight = Math.round(bounds.height);
        if (
          nextWidth === width
          && nextHeight === height
          && nextRatio === pixelRatio
        ) {
          return false;
        }

        width = nextWidth;
        height = nextHeight;
        pixelRatio = nextRatio;
        canvas.width = Math.round(width * pixelRatio);
        canvas.height = Math.round(height * pixelRatio);
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        return true;
      }

      function drawOrbit(actor, time) {
        const segments = 72;
        let previous = null;
        const color = actor.green ? GREEN : INK;
        for (let step = 0; step <= segments; step += 1) {
          const angle = step / segments * TAU;
          const point = project(worldPosition(actor, angle, time));
          if (previous) {
            const depth = (previous.depth + point.depth) * .5;
            context.beginPath();
            context.moveTo(previous.x, previous.y);
            context.lineTo(point.x, point.y);
            context.strokeStyle = rgba(color, .012 + depth * .105);
            context.lineWidth = .45 + depth * .55;
            context.stroke();
          }
          previous = point;
        }
      }

      function updateConnections(positions, time) {
        const visible = [];
        for (let first = 0; first < positions.length; first += 1) {
          for (let second = first + 1; second < positions.length; second += 1) {
            const a = positions[first];
            const b = positions[second];
            const dx = a.world.x - b.world.x;
            const dy = a.world.y - b.world.y;
            const dz = a.world.z - b.world.z;
            const distance = Math.hypot(dx, dy, dz);
            const seed = pairSeed(first, second);
            const sameFamily = actors[first].family === actors[second].family;
            const proximity = clamp(1 - distance / .31);
            const affinityWave = .5 + .5 * Math.sin(time * (.12 + seed * .05) + seed * 31);
            const affinityPulse = Math.pow(affinityWave, 9);
            const affinityBridge =
              (sameFamily || seed > .84)
              && distance < .62
              && affinityPulse > .54;
            const target = Math.max(
              proximity * .82,
              affinityBridge ? affinityPulse * .36 : 0,
            );
            const key = `${first}:${second}`;
            const current = links.get(key) || 0;
            const easing = target > current ? .07 : .018;
            const strength = current + (target - current) * easing;

            if (strength > .008 || target > 0) links.set(key, strength);
            else links.delete(key);
            if (strength > .018) {
              visible.push({ a, b, first, second, seed, strength });
            }
          }
        }
        return visible;
      }

      function drawConnection(link, time) {
        const { a, b, seed, strength } = link;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const depth = (a.depth + b.depth) * .5;
        const bend =
          (seed - .5) * distance * .23
          + Math.sin(time * .09 + seed * 18) * distance * .035;
        const middleX = (a.x + b.x) * .5 - dy / distance * bend;
        const middleY = (a.y + b.y) * .5 + dx / distance * bend;
        const bothGreen = actors[link.first].green && actors[link.second].green;
        const color = bothGreen ? GREEN : INK;

        context.beginPath();
        context.moveTo(a.x, a.y);
        if (seed > .42) context.quadraticCurveTo(middleX, middleY, b.x, b.y);
        else context.lineTo(b.x, b.y);
        context.strokeStyle = rgba(color, strength * (.018 + depth * .12));
        context.lineWidth = .42 + strength * .7;
        context.stroke();
      }

      function drawActor(actor, point, nextPoint) {
        const color = actor.green ? GREEN : INK;
        const alpha = .14 + point.depth * .76;
        const radius = actor.size * (.72 + point.depth * .58);
        const angle = Math.atan2(nextPoint.y - point.y, nextPoint.x - point.x);

        context.save();
        context.translate(point.x, point.y);
        context.rotate(angle);
        context.shadowColor = rgba(color, alpha * .55);
        context.shadowBlur = radius * 2.8;
        context.fillStyle = rgba(color, alpha * .32);
        context.beginPath();
        context.ellipse(0, 0, radius * 1.75, radius * .82, 0, 0, TAU);
        context.fill();

        context.shadowBlur = radius * 1.1;
        context.fillStyle = rgba(color, alpha);
        context.beginPath();
        context.ellipse(0, 0, radius * 1.06, radius * .52, 0, 0, TAU);
        context.fill();
        context.restore();
      }

      function clearCommonsSpace() {
        const radius = Math.min(width, height);
        context.save();
        context.globalCompositeOperation = "destination-out";
        context.beginPath();
        context.ellipse(
          width * .5,
          height * .5,
          radius * .145,
          radius * .095,
          0,
          0,
          TAU,
        );
        context.fill();
        context.restore();
      }

      function draw(time) {
        if (!width || !height) return;
        context.clearRect(0, 0, width, height);
        context.lineCap = "round";
        context.lineJoin = "round";
        orbitActors.forEach((actor) => drawOrbit(actor, time));

        const positions = actors.map((actor) => {
          const angle = actor.phase + actor.direction * actor.speed * time;
          const world = worldPosition(actor, angle, time);
          const point = project(world);
          const next = project(worldPosition(actor, angle + .012, time));
          return { ...point, next };
        });

        updateConnections(positions, time)
          .sort((first, second) => {
            const firstDepth = first.a.depth + first.b.depth;
            const secondDepth = second.a.depth + second.b.depth;
            return firstDepth - secondDepth;
          })
          .forEach((link) => drawConnection(link, time));

        positions
          .map((point, index) => ({ point, actor: actors[index] }))
          .sort((first, second) => first.point.depth - second.point.depth)
          .forEach(({ actor, point }) => drawActor(actor, point, point.next));
        clearCommonsSpace();
      }

      function stop() {
        window.cancelAnimationFrame(animationFrame);
        animationFrame = 0;
      }

      function frame(milliseconds) {
        if (!canvas.isConnected) {
          stop();
          observer.disconnect();
          reducedMotion.removeEventListener?.("change", motionPreferenceChanged);
          return;
        }
        resizeCanvas();
        draw(milliseconds / 1000);
        animationFrame = window.requestAnimationFrame(frame);
      }

      function start() {
        stop();
        resizeCanvas();
        if (reducedMotion.matches) draw(38);
        else animationFrame = window.requestAnimationFrame(frame);
      }

      function motionPreferenceChanged() {
        start();
      }

      const observer = new ResizeObserver(() => {
        if (resizeCanvas() && reducedMotion.matches) draw(38);
      });
      observer.observe(canvas);
      reducedMotion.addEventListener?.("change", motionPreferenceChanged);
      start();
    })();
    </script>
    """,
    unsafe_allow_javascript=True,
)
