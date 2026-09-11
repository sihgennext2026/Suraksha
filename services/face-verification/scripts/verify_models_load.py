import os
import onnxruntime as ort

MODEL_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "buffalo_m"
)

MODELS = [
    "det_2.5g.onnx",
    "w600k_r50.onnx",
]


def inspect_model(filename):
    path = os.path.abspath(os.path.join(MODEL_DIR, filename))

    print("\n" + "=" * 60)
    print("MODEL:", filename)
    print("PATH :", path)

    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    session = ort.InferenceSession(
        path,
        providers=["CPUExecutionProvider"]
    )

    print("STATUS: LOADED")

    print("\nINPUTS:")
    for inp in session.get_inputs():
        print(
            f"  name={inp.name}, "
            f"shape={inp.shape}, "
            f"type={inp.type}"
        )

    print("\nOUTPUTS:")
    for out in session.get_outputs():
        print(
            f"  name={out.name}, "
            f"shape={out.shape}, "
            f"type={out.type}"
        )

    return session


if __name__ == "__main__":
    for model in MODELS:
        inspect_model(model)

    print("\n" + "=" * 60)
    print("STAGE 2 MODEL LOAD TEST: PASSED")
    print("=" * 60)