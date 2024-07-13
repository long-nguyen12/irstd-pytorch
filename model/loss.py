import torch.nn as nn
import numpy as np
import torch
import torch.nn.functional as F
from skimage import measure


def SoftIoULoss(pred, target):
    pred = torch.sigmoid(pred)

    smooth = 1

    intersection = pred * target
    intersection_sum = torch.sum(intersection, dim=(1, 2, 3))
    pred_sum = torch.sum(pred, dim=(1, 2, 3))
    target_sum = torch.sum(target, dim=(1, 2, 3))

    loss = (intersection_sum + smooth) / (
        pred_sum + target_sum - intersection_sum + smooth
    )

    loss = 1 - loss.mean()

    return loss


def Dice(pred, target, warm_epoch=1, epoch=1, layer=0):
    pred = torch.sigmoid(pred)

    smooth = 1

    intersection = pred * target
    intersection_sum = torch.sum(intersection, dim=(1, 2, 3))
    pred_sum = torch.sum(pred, dim=(1, 2, 3))
    target_sum = torch.sum(target, dim=(1, 2, 3))

    loss = (2 * intersection_sum + smooth) / (
        pred_sum + target_sum + intersection_sum + smooth
    )

    loss = 1 - loss.mean()

    return loss


class SLSIoULoss(nn.Module):
    def __init__(self):
        super(SLSIoULoss, self).__init__()

    def forward(self, pred_log, target, warm_epoch, epoch, with_shape=True):
        pred = torch.sigmoid(pred_log)
        smooth = 0.0

        intersection = pred * target

        intersection_sum = torch.sum(intersection, dim=(1, 2, 3))
        pred_sum = torch.sum(pred, dim=(1, 2, 3))
        target_sum = torch.sum(target, dim=(1, 2, 3))

        dis = torch.pow((pred_sum - target_sum) / 2, 2)

        alpha = (torch.min(pred_sum, target_sum) + dis + smooth) / (
            torch.max(pred_sum, target_sum) + dis + smooth
        )

        loss = (intersection_sum + smooth) / (
            pred_sum + target_sum - intersection_sum + smooth
        )
        lloss = LLoss(pred, target)

        if epoch > warm_epoch:
            siou_loss = alpha * loss
            if with_shape:
                loss = 1 - siou_loss.mean() + lloss
            else:
                loss = 1 - siou_loss.mean()
        else:
            loss = 1 - loss.mean()
        return loss


def LLoss(pred, target):
    loss = torch.tensor(0.0, requires_grad=True).to(pred)

    patch_size = pred.shape[0]
    h = pred.shape[2]
    w = pred.shape[3]
    x_index = torch.arange(0, w, 1).view(1, 1, w).repeat((1, h, 1)).to(pred) / w
    y_index = torch.arange(0, h, 1).view(1, h, 1).repeat((1, 1, w)).to(pred) / h
    smooth = 1e-8
    for i in range(patch_size):

        pred_centerx = (x_index * pred[i]).mean()
        pred_centery = (y_index * pred[i]).mean()

        target_centerx = (x_index * target[i]).mean()
        target_centery = (y_index * target[i]).mean()

        angle_loss = (4 / (torch.pi**2)) * (
            torch.square(
                torch.arctan((pred_centery) / (pred_centerx + smooth))
                - torch.arctan((target_centery) / (target_centerx + smooth))
            )
        )

        pred_length = torch.sqrt(
            pred_centerx * pred_centerx + pred_centery * pred_centery + smooth
        )
        target_length = torch.sqrt(
            target_centerx * target_centerx + target_centery * target_centery + smooth
        )

        length_loss = (torch.min(pred_length, target_length)) / (
            torch.max(pred_length, target_length) + smooth
        )

        loss = loss + (1 - length_loss + angle_loss) / patch_size

    return loss


class SoftLoULoss(nn.Module):
    def __init__(self):
        super(SoftLoULoss, self).__init__()

    def forward(self, pred, target):
        pred = torch.sigmoid(pred)
        smooth = 1

        intersection = pred * target

        intersection_sum = torch.sum(intersection, dim=(1, 2, 3))
        pred_sum = torch.sum(pred, dim=(1, 2, 3))
        target_sum = torch.sum(target, dim=(1, 2, 3))
        loss = (intersection_sum + smooth) / (
            pred_sum + target_sum - intersection_sum + smooth
        )

        loss = 1 - torch.mean(loss)

        return loss


class SoftIoUL1NromLoss(nn.Module):
    def __init__(self, lambda_iou=0.8, lambda_l1=0.2):
        super(SoftIoUL1NromLoss, self).__init__()
        self.softiou = SoftLoULoss()
        self.lambda_iou = lambda_iou
        self.lambda_l1 = lambda_l1

    def forward(self, pred, target):
        iouloss = self.softiou(pred, target)

        batch_size, C, height, width = pred.size()
        pred = (pred > 0).float()
        l1loss = torch.sum(pred) / (batch_size * C * height * width)

        loss = self.lambda_iou * iouloss + self.lambda_l1 * l1loss
        return loss


class StructureLoss(nn.Module):
    def __init__(self) -> None:
        super().__init__()

    def forward(self, pred, mask):
        weit = 1 + 5 * torch.abs(
            F.avg_pool2d(mask, kernel_size=31, stride=1, padding=15) - mask
        )
        wbce = F.binary_cross_entropy_with_logits(pred, mask, reduction="none")
        wbce = (weit * wbce).sum(dim=(2, 3)) / weit.sum(dim=(2, 3))

        pred = torch.sigmoid(pred)
        inter = ((pred * mask) * weit).sum(dim=(2, 3))
        union = ((pred + mask) * weit).sum(dim=(2, 3))
        wiou = 1 - (inter + 1) / (union - inter + 1)
        return (wbce + wiou).mean()


class AverageMeter(object):
    """Computes and stores the average and current value"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count
