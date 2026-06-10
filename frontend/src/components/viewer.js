import { viewerAssets } from "../config/assets.js";
import { runtimeState } from "../state/runtime.js";


export function renderViewerThumbs(viewerThumbs, onSelect) {
  viewerThumbs.innerHTML = Object.entries(viewerAssets)
    .map(
      ([view, asset]) => `
        <button class="viewer-thumb ${view === "front" ? "active" : ""}" type="button" data-thumb-view="${view}">
          <img data-src="${asset.src}" alt="${asset.alt}">
          <span>${view[0].toUpperCase()}${view.slice(1)}</span>
        </button>
      `
    )
    .join("");
  viewerThumbs.querySelectorAll("[data-thumb-view]").forEach((button) => {
    button.addEventListener("click", () => onSelect(button.dataset.thumbView));
  });
}

export function setViewer(view, elements) {
  const asset = viewerAssets[view];
  if (!runtimeStateSafeComplete()) {
    elements.viewerImage.removeAttribute("src");
    elements.viewerCaption.textContent = "";
    elements.viewerThumbs.querySelectorAll("[data-src]").forEach((image) => {
      image.removeAttribute("src");
    });
    return;
  }
  hydrateViewerThumbs(elements.viewerThumbs);
  elements.viewerImage.src = asset.src;
  elements.viewerImage.alt = asset.alt;
  elements.viewerCaption.textContent = asset.caption;
  applyViewerZoom(elements);
  elements.viewTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === view);
    tab.setAttribute("aria-selected", String(tab.dataset.view === view));
  });
  elements.viewerThumbs.querySelectorAll("[data-thumb-view]").forEach((thumb) => {
    thumb.classList.toggle("active", thumb.dataset.thumbView === view);
  });
}

export function openViewer(elements) {
  elements.viewerBlock.classList.add("open");
  elements.viewerLaunch.classList.add("hidden");
  elements.viewerContent.classList.remove("hidden");
  elements.openViewerButton.textContent = "Expand";
  setViewer("front", elements);
  elements.viewerBlock.scrollIntoView({ behavior: "smooth", block: "center" });
}

export function adjustViewerZoom(elements, delta) {
  if (!runtimeStateSafeComplete()) return;
  runtimeState.viewerZoom = clampZoom(runtimeState.viewerZoom + delta);
  applyViewerZoom(elements);
}

export function resetViewerZoom(elements) {
  runtimeState.viewerZoom = 1;
  applyViewerZoom(elements);
}

function runtimeStateSafeComplete() {
  return runtimeState.complete === true;
}

function hydrateViewerThumbs(viewerThumbs) {
  viewerThumbs.querySelectorAll("[data-src]").forEach((image) => {
    if (!image.src) image.src = image.dataset.src;
  });
}

function applyViewerZoom(elements) {
  elements.viewerImage.style.setProperty("--viewer-zoom", runtimeState.viewerZoom.toFixed(2));
  if (elements.viewerZoomOut) {
    elements.viewerZoomOut.disabled = runtimeState.viewerZoom <= 0.75;
  }
  if (elements.viewerZoomIn) {
    elements.viewerZoomIn.disabled = runtimeState.viewerZoom >= 1.6;
  }
}

function clampZoom(value) {
  return Math.min(1.6, Math.max(0.75, Math.round(value * 100) / 100));
}
