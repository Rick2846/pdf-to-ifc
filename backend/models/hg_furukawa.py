"""CubiCasa5K Hourglass model (hg_furukawa_original) ported for PyTorch 2.x."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class Residual(nn.Module):
    def __init__(self, num_in: int, num_out: int):
        super().__init__()
        self.num_in = num_in
        self.num_out = num_out
        mid = num_out // 2

        self.bn = nn.BatchNorm2d(num_in)
        self.relu = nn.ReLU(inplace=True)
        self.conv1 = nn.Conv2d(num_in, mid, kernel_size=1, bias=True)
        self.bn1 = nn.BatchNorm2d(mid)
        self.conv2 = nn.Conv2d(mid, mid, kernel_size=3, stride=1, padding=1, bias=True)
        self.bn2 = nn.BatchNorm2d(mid)
        self.conv3 = nn.Conv2d(mid, num_out, kernel_size=1, bias=True)

        if num_in != num_out:
            self.conv4 = nn.Conv2d(num_in, num_out, kernel_size=1, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.relu(self.bn(x))
        out = self.relu(self.bn1(self.conv1(out)))
        out = self.relu(self.bn2(self.conv2(out)))
        out = self.conv3(out)
        if self.num_in != self.num_out:
            residual = self.conv4(x)
        return out + residual


def _upsample_add(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Upsample *x* to match *y* then add."""
    _, _, h, w = y.size()
    if x.shape != y.shape:
        x = F.interpolate(x, size=(h, w), mode="bilinear", align_corners=False)
    return x + y


class HGFurukawa(nn.Module):
    """Hourglass network for floor-plan segmentation (CubiCasa5K).

    Multi-task output: ``[heatmaps(21) | rooms(12) | icons(11)]`` = 44 channels.
    """

    N_CLASSES = 44
    INPUT_SLICE = (21, 12, 11)
    WALL_ROOM_CLASS = 2  # "Wall" in rooms_selected

    def __init__(self, n_classes: int = 44):
        super().__init__()
        self.conv1_ = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=True)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu1 = nn.ReLU(inplace=True)
        self.r01 = Residual(64, 128)
        self.maxpool = nn.MaxPool2d(kernel_size=2, stride=2)
        self.r02 = Residual(128, 128)
        self.r03 = Residual(128, 128)
        self.r04 = Residual(128, 256)

        # Encoder arm-a
        self.maxpool1 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.r11_a = Residual(256, 256)
        self.r12_a = Residual(256, 256)
        self.r13_a = Residual(256, 256)

        self.maxpool2 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.r21_a = Residual(256, 256)
        self.r22_a = Residual(256, 256)
        self.r23_a = Residual(256, 256)

        self.maxpool3 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.r31_a = Residual(256, 256)
        self.r32_a = Residual(256, 256)
        self.r33_a = Residual(256, 256)

        self.maxpool4 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.r41_a = Residual(256, 256)
        self.r42_a = Residual(256, 256)
        self.r43_a = Residual(256, 256)
        self.r44_a = Residual(256, 512)
        self.r45_a = Residual(512, 512)
        self.upsample4 = nn.ConvTranspose2d(512, 512, kernel_size=2, stride=2)

        # Skip arm-b
        self.r41_b = Residual(256, 256)
        self.r42_b = Residual(256, 256)
        self.r43_b = Residual(256, 512)

        self.r4_ = Residual(512, 512)
        self.upsample3 = nn.ConvTranspose2d(512, 512, kernel_size=2, stride=2)

        self.r31_b = Residual(256, 256)
        self.r32_b = Residual(256, 256)
        self.r33_b = Residual(256, 512)

        self.r3_ = Residual(512, 512)
        self.upsample2 = nn.ConvTranspose2d(512, 512, kernel_size=2, stride=2)

        self.r21_b = Residual(256, 256)
        self.r22_b = Residual(256, 256)
        self.r23_b = Residual(256, 512)

        self.r2_ = Residual(512, 512)
        self.upsample1 = nn.ConvTranspose2d(512, 512, kernel_size=2, stride=2)

        self.r11_b = Residual(256, 256)
        self.r12_b = Residual(256, 256)
        self.r13_b = Residual(256, 512)

        # Head
        self.conv2_ = nn.Conv2d(512, 512, kernel_size=1, bias=True)
        self.bn2 = nn.BatchNorm2d(512)
        self.relu2 = nn.ReLU(inplace=True)
        self.conv3_ = nn.Conv2d(512, 256, kernel_size=1, bias=True)
        self.bn3 = nn.BatchNorm2d(256)
        self.relu3 = nn.ReLU(inplace=True)
        self.conv4_ = nn.Conv2d(256, n_classes, kernel_size=1, bias=True)
        self.upsample = nn.ConvTranspose2d(n_classes, n_classes, kernel_size=4, stride=4)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.relu1(self.bn1(self.conv1_(x)))
        out = self.maxpool(out)
        out = self.r01(out)
        out = self.r02(out)
        out = self.r03(out)
        out = self.r04(out)

        # --- level 1 ---
        out1a = self.r13_a(self.r12_a(self.r11_a(self.maxpool1(out))))
        out1b = self.r13_b(self.r12_b(self.r11_b(out)))

        # --- level 2 ---
        out2a = self.r23_a(self.r22_a(self.r21_a(self.maxpool2(out1a))))
        out2b = self.r23_b(self.r22_b(self.r21_b(out1a)))

        # --- level 3 ---
        out3a = self.r33_a(self.r32_a(self.r31_a(self.maxpool3(out2a))))
        out3b = self.r33_b(self.r32_b(self.r31_b(out2a)))

        # --- level 4 (bottleneck) ---
        out4a = self.r45_a(self.r44_a(self.r43_a(self.r42_a(self.r41_a(self.maxpool4(out3a))))))
        out4b = self.r43_b(self.r42_b(self.r41_b(out3a)))

        # --- decoder ---
        out4 = self.r4_(_upsample_add(self.upsample4(out4a), out4b))
        out3 = self.r3_(_upsample_add(self.upsample3(out4), out3b))
        out2 = self.r2_(_upsample_add(self.upsample2(out3), out2b))
        out = _upsample_add(self.upsample1(out2), out1b)

        # --- head ---
        out = self.relu2(self.bn2(self.conv2_(out)))
        out = self.relu3(self.bn3(self.conv3_(out)))
        out = self.upsample(self.conv4_(out))

        out[:, :21] = self.sigmoid(out[:, :21])
        return out
