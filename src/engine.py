# ==========================================================
# pvBG - Private Background Removal
# Copyright (C) 2026 Saw it See had
# Licensed under the MIT License
# ==========================================================

import os
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter


class Engine:
    """
    pvBG Inference Engine.

    Loads a pvBG .onnx model and exposes a single public method:
        result_image = engine.remove_background(input_path)

    Returns a PIL RGBA Image with the background removed,
    preserving soft transparency on hair and fine edges.

    Dependencies: onnxruntime, Pillow, numpy
    No PyTorch required.
    """

    INPUT_SIZE = 224

    _MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    _STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, model_path: str):
        """
        Initialize the pvBG ONNX engine.

        Automatically selects CUDAExecutionProvider if a compatible GPU
        is available, otherwise falls back to CPUExecutionProvider.

        Args:
            model_path (str): Full path to the pvBG .onnx model file.

        Raises:
            FileNotFoundError: If the model file does not exist.
            RuntimeError: If the ONNX session fails to initialize.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"[pvBG] Model file not found: {model_path}")

        available   = ort.get_available_providers()
        use_cuda    = "CUDAExecutionProvider" in available
        providers   = ["CUDAExecutionProvider", "CPUExecutionProvider"] if use_cuda \
                        else ["CPUExecutionProvider"]

        try:
            self._session = ort.InferenceSession(model_path, providers=providers)
        except Exception as e:
            raise RuntimeError(f"[pvBG] Failed to initialize ONNX session: {e}")

        self._input_name  = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name

        provider_used = self._session.get_providers()[0]
        device_label  = "GPU (CUDA)" if "CUDA" in provider_used else "CPU"
        print(f"[pvBG] Engine running on : {device_label}")
        print(f"[pvBG] Model loaded      : {os.path.basename(model_path)}")

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """
        Resize and normalize a PIL RGB image into a float32 NCHW array
        ready for ONNX inference.

        Applies ImageNet mean/std normalization matching the training pipeline.

        Args:
            image (PIL.Image.Image): Input RGB image of any size.

        Returns:
            np.ndarray: Float32 array of shape (1, 3, INPUT_SIZE, INPUT_SIZE).
        """
        img = image.resize((self.INPUT_SIZE, self.INPUT_SIZE), Image.Resampling.BILINEAR)
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = (arr - self._MEAN) / self._STD
        arr = arr.transpose(2, 0, 1)
        return np.expand_dims(arr, axis=0)

    def _refine_mask(self, mask_np: np.ndarray) -> np.ndarray:
        """
        Post-process the raw alpha mask to produce clean, smooth edges
        while preserving semi-transparency on hair strands.

        Steps:
        1. Soft threshold  — keep transitional (hair) values as semi-transparent.
        2. Gaussian blur   — smooth jagged edges with a light anti-alias pass.
        3. Final threshold — lock solid foreground/background regions cleanly.

        Args:
            mask_np (np.ndarray): Grayscale mask array, values in [0, 255].

        Returns:
            np.ndarray: Refined mask array, values in [0, 255].
        """
        mask_soft = np.where(mask_np < 15,  0,
                    np.where(mask_np > 240, 255,
                            mask_np)).astype(np.uint8)

        mask_pil  = Image.fromarray(mask_soft, mode='L')
        mask_blur = mask_pil.filter(ImageFilter.GaussianBlur(radius=1.2))
        mask_np2  = np.array(mask_blur)

        final = np.where(mask_np2 > 200, 255,
                np.where(mask_np2 < 20,  0,
                        mask_np2)).astype(np.uint8)

        return final

    def remove_background(self, input_path: str) -> Image.Image | None:
        """
        Remove the background from an image file.

        Runs the pvBG ONNX model on the given image, post-processes the
        predicted alpha mask to preserve fine hair and smooth edges,
        then composites the result as an RGBA image.

        Args:
            input_path (str): Path to the input image file (JPG / PNG / WEBP).

        Returns:
            PIL.Image.Image: RGBA image with background removed,
                            or None if an error occurs.
        """
        try:
            original_image = Image.open(input_path).convert("RGB")
            original_size  = original_image.size

            input_tensor = self._preprocess(original_image)

            outputs  = self._session.run([self._output_name], {self._input_name: input_tensor})
            mask_raw = outputs[0].squeeze()

            mask_np  = (mask_raw * 255).clip(0, 255).astype(np.uint8)
            mask_img = Image.fromarray(mask_np, mode='L')
            mask_img = mask_img.resize(original_size, Image.Resampling.LANCZOS)

            mask_refined = self._refine_mask(np.array(mask_img))
            final_mask   = Image.fromarray(mask_refined, mode='L')

            result = original_image.convert("RGBA")
            result.putalpha(final_mask)

            return result

        except Exception as e:
            print(f"[pvBG] Inference error: {e}")
            return None