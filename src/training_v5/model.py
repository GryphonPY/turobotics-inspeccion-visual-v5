from __future__ import annotations

import torch
from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


class V5PresenceNet(nn.Module):
    """Compact 10-component plus global-presence classifier."""

    output_count = 11

    def __init__(self, *, pretrained: bool = False) -> None:
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        backbone = mobilenet_v3_small(weights=weights)
        classifier = list(backbone.classifier)
        classifier[-1] = nn.Linear(classifier[-1].in_features, self.output_count)
        backbone.classifier = nn.Sequential(*classifier)
        self.backbone = backbone

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return self.backbone(batch)


def load_checkpoint(path: str, *, pretrained: bool = False) -> V5PresenceNet:
    model = V5PresenceNet(pretrained=pretrained)
    state = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model
