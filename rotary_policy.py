"""Frozen C005 tile selection; importable without accelerator packages."""

CHOICES = ("4", "8", "16", "auto")


def resolve_head_tile(policy, batch, length, width):
    if str(policy) not in CHOICES:
        raise ValueError("rotary head tile must be 4, 8, 16 or auto")
    if min(batch, length, width) < 1:
        raise ValueError("positive rotary dimensions required")
    if str(policy) == "auto":
        return 16 if width == 128 and batch >= 16 and length in (1, 2) else 4
    return int(policy)
