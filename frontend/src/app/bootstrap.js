import { renderProofPlaceholders } from "../components/proofGrid.js";
import { renderInputs } from "../components/uploads.js";
import { adjustViewerZoom, openViewer, renderViewerThumbs, resetViewerZoom, setViewer } from "../components/viewer.js";
import { createFittingSession } from "../features/fitting/session.js";
import { runtimeState } from "../state/runtime.js";
import { getAppElements } from "./elements.js";


export function bootstrap() {
  const elements = getAppElements();
  const fittingSession = createFittingSession(elements);

  renderInputs(elements.inputCards, elements.uploadCount);
  renderViewerThumbs(elements.viewerThumbs, (view) => {
    if (!runtimeState.complete) return;
    setViewer(view, elements);
  });
  renderProofPlaceholders(elements.proofGrid);

  elements.navLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setRoute(link.dataset.route, elements);
    });
  });
  window.addEventListener("popstate", () => setRoute(currentRoute(), elements, { updateUrl: false }));
  setRoute(currentRoute(), elements, { updateUrl: false });

  elements.viewTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      if (!runtimeState.complete) return;
      setViewer(tab.dataset.view, elements);
    });
  });
  elements.openViewerButton.addEventListener("click", () => {
    if (!runtimeState.complete) return;
    runtimeState.viewerOpen = true;
    openViewer(elements);
  });
  elements.viewerZoomOut.addEventListener("click", () => adjustViewerZoom(elements, -0.1));
  elements.viewerZoomIn.addEventListener("click", () => adjustViewerZoom(elements, 0.1));
  elements.startButton.addEventListener("click", fittingSession.run);
  elements.resetButton.addEventListener("click", () => {
    resetViewerZoom(elements);
    fittingSession.reset();
  });
  fittingSession.reset();
}

function currentRoute() {
  return window.location.hash === "#analytics" ? "analytics" : "studio";
}

function setRoute(route, elements, options = {}) {
  const nextRoute = route === "analytics" ? "analytics" : "studio";
  const isAnalytics = nextRoute === "analytics";
  elements.studioWorkspace.classList.toggle("screen-hidden", isAnalytics);
  elements.studioWorkspace.setAttribute("aria-hidden", String(isAnalytics));
  elements.analyticsView.classList.toggle("screen-hidden", !isAnalytics);
  elements.analyticsView.setAttribute("aria-hidden", String(!isAnalytics));
  elements.navLinks.forEach((item) => {
    item.classList.toggle("active", item.dataset.route === nextRoute);
  });

  if (options.updateUrl === false) return;
  const nextHash = isAnalytics ? "#analytics" : "#studio";
  if (window.location.hash !== nextHash) {
    window.history.pushState(null, "", nextHash);
  }
}
