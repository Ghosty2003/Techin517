"""CLIP-based zero-shot object recognizer.

Standalone utility class — no ROS2 dependency.
Import this in state_machine.py or use it in a standalone script.

Usage:
    recognizer = CLIPRecognizer(["screwdriver", "scissors", "roll of tape"])
    obj, confidence = recognizer.classify(image_np)  # image_np: H x W x 3 uint8
    if obj is not None:
        print(f"Detected: {obj} ({confidence:.1%})")
"""

import numpy as np
import torch
import torch.nn.functional as F
from transformers import CLIPModel, CLIPProcessor


class CLIPRecognizer:
    """Frozen CLIP model for zero-shot object classification.

    Args:
        object_classes: List of class name strings, e.g. ["screwdriver", "scissors"].
            Use 2-3 word descriptive names for best accuracy ("roll of tape" > "tape").
        model_name: HuggingFace CLIP model ID.
        threshold: Minimum softmax probability to count as a detection.
            Raise this if you get false positives; lower it if CLIP misses objects.
        device: Torch device. Defaults to cuda if available.
    """

    def __init__(
        self,
        object_classes: list[str],
        model_name: str = "openai/clip-vit-base-patch32",
        threshold: float = 0.40,
        device: str | None = None,
    ):
        self.object_classes = object_classes
        self.threshold = threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self._model = CLIPModel.from_pretrained(model_name).to(self.device)
        self._processor = CLIPProcessor.from_pretrained(model_name)

        # Freeze — CLIP is never trained here
        for p in self._model.parameters():
            p.requires_grad = False
        self._model.eval()

        # Pre-compute and cache text embeddings for all class labels
        self._text_feats = self._encode_texts(object_classes)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, image: np.ndarray) -> tuple[str | None, float]:
        """Classify the object in the image.

        Args:
            image: H x W x 3 uint8 numpy array (RGB).

        Returns:
            (class_name, confidence) if confidence >= threshold, else (None, confidence).
        """
        img_feat = self._encode_image(image)
        sims = img_feat @ self._text_feats.T          # (1, n_classes)
        probs = sims.softmax(dim=-1).squeeze(0)       # (n_classes,)

        best_idx = probs.argmax().item()
        confidence = probs[best_idx].item()

        if confidence >= self.threshold:
            return self.object_classes[best_idx], confidence
        return None, confidence

    def scores(self, image: np.ndarray) -> dict[str, float]:
        """Return softmax probability for every class (useful for debugging)."""
        img_feat = self._encode_image(image)
        sims = img_feat @ self._text_feats.T
        probs = sims.softmax(dim=-1).squeeze(0)
        return {cls: probs[i].item() for i, cls in enumerate(self.object_classes)}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @torch.no_grad()
    def _encode_texts(self, texts: list[str]) -> torch.Tensor:
        tok = self._processor(text=texts, return_tensors="pt", padding=True)
        feats = self._model.get_text_features(
            input_ids=tok["input_ids"].to(self.device),
            attention_mask=tok["attention_mask"].to(self.device),
        )
        if not isinstance(feats, torch.Tensor):
            feats = feats.pooler_output
        return F.normalize(feats, dim=-1)

    @torch.no_grad()
    def _encode_image(self, image: np.ndarray) -> torch.Tensor:
        tok = self._processor(images=image, return_tensors="pt")
        feats = self._model.get_image_features(
            pixel_values=tok["pixel_values"].to(self.device)
        )
        if not isinstance(feats, torch.Tensor):
            feats = feats.pooler_output
        return F.normalize(feats, dim=-1)
