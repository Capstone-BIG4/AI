export const DEFAULT_OBJ_ASSET_PATH =
  import.meta.env.VITE_VIEWER_DEFAULT_OBJ_PATH ||
  "/home/bys0626/capstone/output/me_real_test/full_run/reconstruction/job_local_me_20260328133649/raw_mesh.obj";

export function resolveAssetUrl(assetPath: string): string {
  const trimmed = assetPath.trim();

  if (!trimmed) {
    return "";
  }

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }

  if (trimmed.startsWith("/@fs/")) {
    return trimmed;
  }

  if (trimmed.startsWith("/")) {
    return `/@fs${trimmed}`;
  }

  return trimmed;
}

export function resolveObjAssetUrl(assetPath: string): string {
  return resolveAssetUrl(assetPath);
}
