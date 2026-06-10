export const inputs = [
  {
    id: "person",
    label: "User photo",
    file: "은수형 사진.jpg",
    path: "/assets/processed/person-oriented.jpg",
    role: "Body source",
    accept: "image/*",
    fit: "cover"
  },
  {
    id: "top-front",
    label: "Top front",
    file: "top_front.png",
    path: "/assets/processed/top-front-cutout.png",
    role: "Garment",
    accept: "image/*",
    fit: "contain"
  },
  {
    id: "top-back",
    label: "Top back",
    file: "top_back.png",
    path: "/assets/processed/top-back-cutout.png",
    role: "Garment",
    accept: "image/*",
    fit: "contain"
  },
  {
    id: "pants-front",
    label: "Pants front",
    file: "front_pants.png",
    path: "/assets/processed/pants-front-cutout.png",
    role: "Garment",
    accept: "image/*",
    fit: "contain"
  },
  {
    id: "pants-back",
    label: "Pants back",
    file: "back_pants.png",
    path: "/assets/processed/pants-back-cutout.png",
    role: "Garment",
    accept: "image/*",
    fit: "contain"
  }
];

export const steps = [
  { key: "preprocess", label: "01", title: "Preprocess assets", meta: "crop, masks, garment cutouts" },
  { key: "sam", label: "02", title: "SAM 3D Body", meta: "mesh and body measurements" },
  { key: "guides", label: "03", title: "Render guides", meta: "front, side, back maps" },
  { key: "base", label: "04", title: "Build mannequin base", meta: "neutral front, side, back views" },
  { key: "vton", label: "05", title: "Generate outfit", meta: "top then pants VTON candidates" },
  { key: "finalize", label: "06", title: "Finalize output", meta: "SAM body mask-lock and viewer sync" }
];

export const viewerAssets = {
  front: {
    src: "/assets/results/display/sam-body-only-front-contrast.png?v=viewer-bg-match-20260610",
    alt: "앞면 마네킹 가상피팅 결과",
    caption: "SAM body locked front view"
  },
  side: {
    src: "/assets/results/display/sam-body-only-side-contrast.png?v=viewer-bg-match-20260610",
    alt: "옆면 마네킹 가상피팅 결과",
    caption: "SAM body generated side view"
  },
  back: {
    src: "/assets/results/display/sam-body-only-back-contrast.png?v=viewer-bg-match-20260610",
    alt: "뒷면 마네킹 가상피팅 결과",
    caption: "SAM body locked back view"
  }
};

export const proofAssets = [
  { title: "SAM mesh preview", label: "Mesh", path: "/assets/pipeline/sam3d/sam3d_preview_front.png" },
  { title: "Front silhouette", label: "Mask", path: "/assets/pipeline/guides/front_silhouette.png" },
  { title: "Front depth", label: "Depth", path: "/assets/pipeline/guides/front_depth.png" },
  { title: "Front normal", label: "Normal", path: "/assets/pipeline/guides/front_normal.png" },
  { title: "Side normal", label: "Normal", path: "/assets/pipeline/guides/side_normal.png" },
  { title: "Back normal", label: "Normal", path: "/assets/pipeline/guides/back_normal.png" },
  { title: "Front body lines", label: "Lines", path: "/assets/pipeline/alignment/front_body_lines.png" },
  { title: "Side body lines", label: "Lines", path: "/assets/pipeline/alignment/side_body_lines.png" },
  { title: "Back body lines", label: "Lines", path: "/assets/pipeline/alignment/back_body_lines.png" },
  { title: "Mask-locked viewer", label: "Result", path: "/assets/results/display/sam-body-only-front-contrast.png" }
];
