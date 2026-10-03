"""Register real screenshots and reproject onto a full equirectangular sphere.

Unobserved pixels remain transparent. No generated/inpainted scene content.
"""
from pathlib import Path
import argparse
import json
import math
import sys
import time
import base64

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'deps'))
import cv2 as cv
import numpy as np


def read(path):
    img = cv.imdecode(np.fromfile(path, dtype=np.uint8), cv.IMREAD_COLOR)
    if img is None:
        raise ValueError('Cannot read ' + str(path))
    return img


def save(path, img):
    ok, encoded = cv.imencode(path.suffix, img)
    if not ok:
        raise RuntimeError('Image encoding failed')
    encoded.tofile(str(path))


def register(paths, output):
    # Smooth pavement has real texture that default SIFT discards. Enhance only
    # the matching copy; rendering still reads the untouched original screenshots.
    finder = cv.SIFT_create(nfeatures=5000, contrastThreshold=0.01)
    contrast = cv.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    features = []
    scale = 0.5
    def feature_for(path, index):
        small = cv.resize(read(path), None, fx=scale, fy=scale)
        gray = contrast.apply(cv.cvtColor(small, cv.COLOR_BGR2GRAY))
        mask = np.full(gray.shape, 255, np.uint8)
        mask[-20:] = 0  # UID and latency overlay, never used for matching
        feature = cv.detail.computeImageFeatures2(finder, gray, mask)
        feature.img_idx = index
        return feature
    for i, path in enumerate(paths):
        features.append(feature_for(path, i))
        if i % 10 == 0:
            print(f'Features {i + 1}/{len(paths)}', flush=True)
    matcher = cv.detail_BestOf2NearestMatcher(False, 0.55)
    pairs = matcher.apply2(features)
    matcher.collectGarbage()
    indices = cv.detail.leaveBiggestComponent(features, pairs, 0.7)
    # Recompute on retained images to avoid depending on Python list mutation.
    selected = [int(i) for i in indices]
    print(f'Connected images: {len(selected)}/{len(paths)}', flush=True)
    if len(selected) < 3:
        raise RuntimeError('Too few images could be registered')
    if len(selected) != len(paths):
        paths = [paths[i] for i in selected]
        features = []
        for i, path in enumerate(paths):
            features.append(feature_for(path, i))
        pairs = matcher.apply2(features)
    estimator = cv.detail_HomographyBasedEstimator()
    ok, cameras = estimator.apply(features, pairs, None)
    if not ok:
        raise RuntimeError('Camera estimation failed')
    for camera in cameras:
        camera.R = camera.R.astype(np.float32)
    adjuster = cv.detail_BundleAdjusterRay()
    adjuster.setConfThresh(0.7)
    ok, cameras = adjuster.apply(features, pairs, cameras)
    if not ok:
        raise RuntimeError('Rotation bundle adjustment failed')
    # Image x axes remain horizontal for the game's yaw/pitch camera.
    # Their least-squares common normal is the world vertical.
    rights = np.array([cam.R[:, 0] for cam, path in zip(cameras, paths) if 'middle' in str(path)])
    # Capture files themselves have no row names; all x axes can be used.
    if len(rights) < 3:
        rights = np.array([cam.R[:, 0] for cam in cameras])
    _, _, vt = np.linalg.svd(rights, full_matrices=False)
    down = vt[-1]
    if np.dot(down, cameras[0].R[:, 1]) < 0:
        down = -down
    forward = cameras[0].R[:, 2]
    forward = forward - down * np.dot(forward, down)
    forward /= np.linalg.norm(forward)
    right = np.cross(down, forward)
    alignment = np.stack([right, down, forward])
    records = []
    for cam, path in zip(cameras, paths):
        K = cam.K()
        K[:2] /= scale
        R = alignment @ cam.R
        u, _, vt = np.linalg.svd(R)
        R = u @ vt
        records.append({'image': str(path), 'K': K.tolist(), 'R': R.tolist()})
    (output / 'cameras.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    return records


def render(records, output, width):
    height = width // 2
    total = np.zeros((height, width, 3), np.float32)
    weights = np.zeros((height, width), np.float32)
    best_weights = np.zeros((height, width), np.float32)
    sharp = np.zeros((height, width, 3), np.uint8)
    owners = np.full((height, width), -1, np.int16)
    patches = []
    longitudes = ((np.arange(width, dtype=np.float32) + 0.5) / width - 0.5) * (2 * math.pi)
    latitudes = ((np.arange(height, dtype=np.float32) + 0.5) / height - 0.5) * math.pi
    for i, record in enumerate(records):
        img = read(record['image'])
        h, w = img.shape[:2]
        K = np.array(record['K'], np.float32)
        R = np.array(record['R'], np.float32)
        # Inverse projection avoids OpenCV's pole-crossing ROI truncation.
        # A bounding spherical cap contains all four source corners.
        center_lat = math.asin(float(np.clip(R[1, 2], -1, 1)))
        center_lon = math.atan2(float(R[0, 2]), float(R[2, 2]))
        dxmax = max(K[0, 2], w - K[0, 2]) / K[0, 0]
        dymax = max(K[1, 2], h - K[1, 2]) / K[1, 1]
        radius = math.atan(math.hypot(dxmax, dymax)) + 0.01
        ys = np.where(np.abs(latitudes - center_lat) <= radius)[0]
        if abs(center_lat) + radius >= math.pi / 2:
            xs = np.arange(width)
        else:
            half_lon = math.asin(min(1, math.sin(radius) / math.cos(center_lat)))
            distance = (longitudes - center_lon + math.pi) % (2 * math.pi) - math.pi
            xs = np.where(np.abs(distance) <= half_lon)[0]
        lat = latitudes[ys, None]
        lon = longitudes[None, xs]
        dx, dy, dz = np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)
        px = R[0, 0] * dx + R[1, 0] * dy + R[2, 0] * dz
        py = R[0, 1] * dx + R[1, 1] * dy + R[2, 1] * dz
        pz = R[0, 2] * dx + R[1, 2] * dy + R[2, 2] * dz
        mx = (K[0, 0] * px / np.maximum(pz, 1e-6) + K[0, 2]).astype(np.float32)
        my = (K[1, 1] * py / np.maximum(pz, 1e-6) + K[1, 2]).astype(np.float32)
        valid = (pz > 0) & (mx >= 1) & (mx < w - 2) & (my >= 1) & (my < h - 40)
        xx, yy = (mx - w / 2) / (w / 2), (my - h / 2) / (h / 2)
        ww = np.maximum(1 - xx**2, 0) * np.maximum(1 - yy**2, 0)
        ww = np.where(valid, np.maximum(ww**3, 1e-5), 0).astype(np.float32)
        colors = cv.remap(img, mx, my, cv.INTER_LINEAR, borderMode=cv.BORDER_CONSTANT)
        total[np.ix_(ys, xs)] += colors * ww[:, :, None]
        weights[np.ix_(ys, xs)] += ww
        previous = best_weights[np.ix_(ys, xs)]
        chosen = ww > previous
        patch = sharp[np.ix_(ys, xs)]
        patch[chosen] = colors[chosen]
        sharp[np.ix_(ys, xs)] = patch
        owner_patch = owners[np.ix_(ys, xs)]
        owner_patch[chosen] = i
        owners[np.ix_(ys, xs)] = owner_patch
        best_weights[np.ix_(ys, xs)] = np.maximum(previous, ww)
        patches.append((ys, xs, colors))
        if i % 10 == 0:
            print(f'Rendered {i + 1}/{len(records)}', flush=True)
    mask = weights > 1e-7
    image = np.clip(total / np.maximum(weights[:, :, None], 1e-7), 0, 255).astype(np.uint8)
    alpha = (mask * 255).astype(np.uint8)
    save(output / 'panorama.png', np.dstack([image, alpha]))
    save(output / 'panorama-sharp.png', np.dstack([sharp, alpha]))
    save(output / 'preview-sharp.jpg', cv.resize(sharp, (1600, 800)))
    # Single-source seam ownership avoids averaging moving operators. Blend
    # low-frequency exposure across those seams with a Laplacian pyramid.
    blender = cv.detail_MultiBandBlender()
    blender.setNumBands(5)
    blender.prepare((0, 0, width, height))
    for i, (ys, xs, colors) in enumerate(patches):
        splits = np.split(np.arange(len(xs)), np.where(np.diff(xs) != 1)[0] + 1)
        for part in splits:
            seam_mask = ((owners[np.ix_(ys, xs[part])] == i) * 255).astype(np.uint8)
            if seam_mask.any():
                blender.feed(colors[:, part].astype(np.int16), seam_mask, (int(xs[part[0]]), int(ys[0])))
    blended, blended_mask = blender.blend(None, None)
    blended = np.clip(blended, 0, 255).astype(np.uint8)
    save(output / 'panorama.png', np.dstack([blended, alpha]))
    save(output / 'coverage.png', alpha)
    preview = cv.resize(blended, (1600, 800))
    save(output / 'preview.jpg', preview)
    coverage = float(mask.mean())
    # Report rows with complete azimuth coverage; do not invent missing poles.
    full_rows = np.where(mask.mean(axis=1) > 0.999)[0]
    report = {'width': width, 'height': height, 'registered_images': len(records),
              'observed_fraction': coverage, 'unobserved_pixels': int((~mask).sum()),
              'complete_rows': [int(full_rows.min()), int(full_rows.max())] if len(full_rows) else None,
              'method': 'CLAHE + low-contrast SIFT / rotation bundle adjustment / inverse spherical reprojection / single-source seams / multiband blend',
              'note': 'Real screenshots only; transparent pixels have no captured source. Dynamic scenery may ghost.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    template = (ROOT / 'viewer-template.html').read_text(encoding='utf-8')
    data = 'data:image/png;base64,' + base64.b64encode((output / 'panorama.png').read_bytes()).decode('ascii')
    (output / 'view-panorama.html').write_text(template.replace('__IMAGE_DATA__', data).replace('__COVERAGE__', f'{coverage * 100:.2f}'), encoding='utf-8')
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--width', type=int, default=4096)
    parser.add_argument('--reuse', type=Path)
    parser.add_argument('--captures', type=Path, default=ROOT / 'captures')
    parser.add_argument('--output', type=Path, help='New output directory; existing directories are rejected')
    args = parser.parse_args()
    if args.width % 2 or not 512 <= args.width <= 8192:
        raise SystemExit('Width must be even and between 512 and 8192')
    output = args.output or ROOT / 'output' / time.strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    if args.reuse:
        records = json.loads(args.reuse.read_text(encoding='utf-8'))
    else:
        paths = []
        for manifest in sorted(args.captures.glob('*/manifest.json')):
            paths.extend(Path(row['image']) for row in json.loads(manifest.read_text(encoding='utf-8')))
        records = register(list(dict.fromkeys(paths)), output)
    (output / 'cameras.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    render(records, output, args.width)
    print('Output: ' + str(output), flush=True)


if __name__ == '__main__':
    main()
