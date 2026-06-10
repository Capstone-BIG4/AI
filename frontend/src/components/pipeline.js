import { steps } from "../config/assets.js";
import { runtimeState } from "../state/runtime.js";


export function renderProgress(progressList, activeIndex = -1) {
  progressList.innerHTML = steps
    .map((step, index) => {
      const state = index < activeIndex ? "done" : index === activeIndex ? "active" : "";
      const stateText = index < activeIndex ? "Done" : index === activeIndex ? "Running" : "Queued";
      return `
        <li class="step-item ${state}">
          <span class="step-label">${step.label}</span>
          <div>
            <strong>${step.title}</strong>
            <small>${step.meta}</small>
          </div>
          <em>${stateText}</em>
        </li>
      `;
    })
    .join("");
}

export function renderJobProgress(progressList, job) {
  if (!job || typeof job.progress !== "number") return;
  const activeIndex = Math.min(steps.length, Math.floor((job.progress / 100) * steps.length));
  renderProgress(progressList, job.status === "completed" ? steps.length : Math.min(activeIndex, steps.length - 1));
}

export function startRuntime(pipelineRuntime) {
  window.clearInterval(runtimeState.runtimeTimer);
  runtimeState.runStartedAt = Date.now();
  pipelineRuntime.textContent = "Running";
  runtimeState.runtimeTimer = null;
}

export function stopRuntime() {
  window.clearInterval(runtimeState.runtimeTimer);
  runtimeState.runtimeTimer = null;
}
