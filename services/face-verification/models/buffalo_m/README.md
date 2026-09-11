# buffalo_m — model provisioning

The five ONNX files this directory needs are **not committed**. They are
InsightFace pretrained weights, and InsightFace licenses its model packs for
non-commercial research use only — a separate licence from the MIT code. This
is an operational screening system, so publishing them here would redistribute
them under terms the upstream project has not granted.

Nothing about the runtime changes: the pipeline loads these paths as it always
has. A fresh clone simply has to supply them.

## Expected files

| File | Size | Used by |
| --- | --- | --- |
| `w600k_r50.onnx` | 167 MB | ArcFace R50 embeddings — **required** |
| `det_2.5g.onnx` | 3.2 MB | SCRFD face detection — **required** |
| `2d106det.onnx` | 4.8 MB | landmarks (loaded by the InsightFace pack) |
| `1k3d68.onnx` | 137 MB | 3D landmarks (loaded by the InsightFace pack) |
| `genderage.onnx` | 1.3 MB | attribute head (loaded by the InsightFace pack) |

Only the first two are used by the screening path. The rest ship in the same
pack and are loaded when the pack is initialised.

## Obtaining them

Download the `buffalo_m` pack from the InsightFace model zoo and unpack it here,
so the files sit directly in this directory:

    services/face-verification/models/buffalo_m/w600k_r50.onnx
    services/face-verification/models/buffalo_m/det_2.5g.onnx
    ...

Verify before use — the pipeline will fail to start with a clear
`FileNotFoundError` naming the missing path if any are absent.

## Before production

Confirm with the licence holder that the intended deployment is permitted at
all. The restriction is on *use*, not only on redistribution: if a
non-commercial term binds this deployment, the answer is a differently licensed
recogniser, not a different way of shipping these files.
