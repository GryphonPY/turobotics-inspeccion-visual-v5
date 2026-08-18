from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")

from training_v5.model import V5PresenceNet


def test_presence_model_has_ten_components_and_global_output() -> None:
    model = V5PresenceNet(pretrained=False).eval()
    output = model(torch.zeros((2, 3, 224, 224), dtype=torch.float32))

    assert tuple(output.shape) == (2, 11)
    assert torch.isfinite(output).all()
