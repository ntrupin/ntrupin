(() => {
  const root = document.querySelector("[data-sidenote-root]");
  if (!root) return;

  const article = root.querySelector("article.prose");
  const column = root.querySelector("[data-sidenote-column]");
  if (!article || !column) return;

  const footnote = article.querySelector("div.footnote");
  const footnoteList = footnote ? footnote.querySelector("ol") : null;
  if (!footnote || !footnoteList) return;

  const DESKTOP_QUERY = "(min-width: 1260px)";
  const MIN_GAP_PX = 20;
  const desktopMatcher = window.matchMedia(DESKTOP_QUERY);
  const entries = [];

  const resolveReferenceFromBackref = (footnoteItem) => {
    const backref = footnoteItem.querySelector("a.footnote-backref[href^='#']");
    if (!backref) return null;

    const href = backref.getAttribute("href");
    if (!href) return null;

    const id = href.slice(1);
    if (!id) return null;
    return document.getElementById(id);
  };

  const resolveReference = (footnoteId) => {
    const referenceId = footnoteId.replace(/^fn/, "fnref");
    const byId = document.getElementById(referenceId);
    if (byId) return byId;

    const escapedId = referenceId.replace(/([:.])/g, "\\$1");
    return article.querySelector(`sup#${escapedId}`);
  };

  let index = 1;
  for (const footnoteItem of footnoteList.children) {
    if (!(footnoteItem instanceof HTMLElement)) continue;
    if (!footnoteItem.id) continue;

    const reference = resolveReferenceFromBackref(footnoteItem) || resolveReference(footnoteItem.id);
    if (!reference) continue;

    const clone = footnoteItem.cloneNode(true);
    clone.querySelectorAll("a.footnote-backref").forEach((node) => node.remove());

    const sidenote = document.createElement("div");
    sidenote.className = "sidenote-item";
    sidenote.innerHTML = `
      <div class="sidenote-index">${reference.textContent?.trim() || index}</div>
      <div class="sidenote-body">${clone.innerHTML}</div>
    `;
    column.appendChild(sidenote);

    reference.classList.add("sidenote-ref");

    const activate = () => {
      reference.classList.add("is-active");
      sidenote.classList.add("is-active");
    };

    const deactivate = () => {
      reference.classList.remove("is-active");
      sidenote.classList.remove("is-active");
    };

    reference.addEventListener("mouseenter", activate);
    reference.addEventListener("mouseleave", deactivate);
    reference.addEventListener("focusin", activate);
    reference.addEventListener("focusout", deactivate);
    sidenote.addEventListener("mouseenter", activate);
    sidenote.addEventListener("mouseleave", deactivate);

    entries.push({ reference, sidenote });
    index += 1;
  }

  if (entries.length === 0) return;

  let frameId = null;

  const setDesktopMode = (enabled) => {
    root.classList.toggle("has-desktop-sidenotes", enabled);
    footnote.hidden = enabled;
    column.hidden = !enabled;
  };

  const layoutSidenotes = () => {
    frameId = null;

    if (!desktopMatcher.matches) {
      setDesktopMode(false);
      return;
    }

    setDesktopMode(true);

    const articleRect = article.getBoundingClientRect();
    const placements = entries.map((entry, order) => {
      const refRect = entry.reference.getBoundingClientRect();
      return {
        entry,
        desiredTop: refRect.top - articleRect.top - 4,
        order,
      };
    });

    placements.sort((a, b) => {
      if (a.desiredTop === b.desiredTop) return a.order - b.order;
      return a.desiredTop - b.desiredTop;
    });

    let cursor = 0;

    for (const placement of placements) {
      const top = Math.max(placement.desiredTop, cursor);

      placement.entry.sidenote.style.top = `${Math.round(top)}px`;
      cursor = top + placement.entry.sidenote.offsetHeight + MIN_GAP_PX;
    }

    column.style.height = `${Math.max(cursor, article.scrollHeight)}px`;
  };

  const scheduleLayout = () => {
    if (frameId !== null) cancelAnimationFrame(frameId);
    frameId = requestAnimationFrame(layoutSidenotes);
  };

  if (window.ResizeObserver) {
    const resizeObserver = new ResizeObserver(scheduleLayout);
    resizeObserver.observe(article);
  }

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(scheduleLayout);
  }

  if (desktopMatcher.addEventListener) {
    desktopMatcher.addEventListener("change", scheduleLayout);
  } else {
    desktopMatcher.addListener(scheduleLayout);
  }

  window.addEventListener("resize", scheduleLayout, { passive: true });
  window.addEventListener("load", scheduleLayout, { once: true });

  // MathJax and deferred assets can shift reference positions after initial render.
  setTimeout(scheduleLayout, 150);
  setTimeout(scheduleLayout, 700);
  setTimeout(scheduleLayout, 1600);

  scheduleLayout();
})();
