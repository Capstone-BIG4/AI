import { proofAssets } from "../config/assets.js";


export function renderProofGrid(proofGrid) {
  proofGrid.innerHTML = proofAssets
    .map(
      (item) => `
        <figure class="proof-card">
          <img src="${item.path}" alt="${item.title}">
          <figcaption>
            <span>${item.label}</span>
            <strong>${item.title}</strong>
          </figcaption>
        </figure>
      `
    )
    .join("");
}

export function renderProofPlaceholders(proofGrid) {
  proofGrid.innerHTML = proofAssets
    .map(
      (item) => `
        <figure class="proof-card proof-card-placeholder">
          <div class="proof-placeholder" aria-hidden="true"></div>
          <figcaption>
            <span>${item.label}</span>
            <strong>${item.title}</strong>
          </figcaption>
        </figure>
      `
    )
    .join("");
}
